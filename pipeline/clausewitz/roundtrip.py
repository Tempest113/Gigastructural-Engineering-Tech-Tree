"""Round-trip corruption detector for the Clausewitz parser (spec/00-overview.md's lossless-AST
requirement).

`serializer.py` walks the AST back to text, naively. This module compares that output against
the original source and decides whether the two are "the same modulo insignificant whitespace" —
the *only* normalisation this detector is allowed to apply. Anything else that differs is a
parser bug: information was lost or misattached while building the AST, and no amount of
serialiser cleverness can paper over that (the AST itself would have to change).

Comparison method: **both texts are re-tokenised** (with the same `Tokenizer` the parser itself
uses) and the resulting token sequences are compared field-by-field: type, text, the
PARAMETER-only `default`/`safe` fields, and a `preceded_by_whitespace` boolean — whether *any*
whitespace character separated this token from the previous one in the text being scanned.
Line/column are ignored (line numbers legitimately shift once the serialiser's newline-per-item
layout diverges from the source's), but separator presence is not: it is the one bit that
distinguishes two adjacent tokens from one glued token, so it is compared exactly, never
normalised away. Quantity and kind of whitespace *within* a run (one space vs. four, tab vs.
space, one newline vs. three) genuinely don't matter and are folded into the same boolean.

An earlier version of this module tokenised both sides and compared type/text/default/safe alone,
treating the token stream itself as the complete normalisation — reasoning that whitespace is
"exactly what the tokeniser skips between tokens, so re-tokenising already accounts for it." That
reasoning is circular: both the source and the serialiser's output are tokenised with the *same*
tokeniser, so any tokeniser-level corruption (e.g. `flag@root` wrongly split into `flag` and
`@root`) reproduces identically on both sides and compares equal — the check would pass on the
exact bug class it exists to catch, because it silently assumes the tokeniser it's built on top of
is correct. Carrying `preceded_by_whitespace` doesn't fix that on its own (a wrong split still
tokenises to two IDENTIFIER-ish tokens either way) — the actual defence against tokeniser-level
corruption is the mutation-harness tests in `tests/clausewitz/test_roundtrip_detects_mutations.py`,
which reintroduce known historical corruption directly into serialised output (bypassing the
tokeniser entirely) and assert this comparison catches it. `preceded_by_whitespace` fixes a
narrower, previously-confirmed problem: a hand-rolled "collapse whitespace runs to one space"
string transform (the version before *this* one) produced false positives, because real source has
token pairs with *zero* whitespace between them (`{}`, `={`, `}}`) and collapsing-to-one-space
treats that as different from a single space, which it is not.

The rest of the normalisation set — small, closed, each entry justified:

1. **A UTF-8 BOM at the start of the file is stripped before comparison.** Already established,
   pre-existing pipeline behaviour (`__init__.py`'s `parse_file`) — the BOM is an encoding marker,
   never a token, and stripping it cannot change any token.
2. **CRLF/CR line endings are normalised to LF before comparison.** Also pre-existing pipeline
   behaviour (`_normalise_newlines`), matching Python's own universal-newlines handling. A line
   ending is whitespace in every context the tokeniser treats as whitespace; inside a string or
   comment (where it's data) both the source and the round-tripped text carry the same characters
   either way, since neither BOM-stripping nor CRLF-normalisation touches string/comment content.
3. **Whitespace ahead of the very first token is not compared.** It has no predecessor token to
   possibly merge into — there is nothing on the other side of it — so it is unambiguously
   insignificant, the same reasoning as 1 and 2, just for arbitrary leading blank lines/indentation
   rather than a fixed BOM/CRLF shape specifically.

Nothing else is normalised. In particular: comment text, string contents, number formatting,
identifier spelling, and block/conditional nesting are compared token-for-token — a difference in
any of those means the AST lost or misattached information, which is a parser bug to fix, not a
normalisation to add.
"""

from __future__ import annotations

from .tokenizer import Tokenizer
from .tokens import Token, TokenType


_WHITESPACE_CHARS = " \t\r\n"


def strip_bom_and_normalize_newlines(text: str) -> str:
    if text.startswith("﻿"):
        text = text[1:]
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _line_start_offsets(text: str) -> list[int]:
    """offsets[i] is the character offset where line i+1 (1-indexed, matching Token.line) starts."""
    offsets = [0]
    for i, ch in enumerate(text):
        if ch == "\n":
            offsets.append(i + 1)
    return offsets


def _token_start_offset(tok: Token, line_starts: list[int]) -> int:
    return line_starts[tok.line - 1] + (tok.column - 1)


def _token_key(tok: Token, preceded_by_whitespace: bool):
    return (tok.type, tok.text, tok.default, tok.safe, preceded_by_whitespace)


def tokenize_for_comparison(text: str) -> list:
    tokens = Tokenizer(text, "<roundtrip>").tokenize()
    line_starts = _line_start_offsets(text)
    result = []
    for tok in tokens:
        if tok.type is TokenType.EOF:
            continue
        if not result:
            # The very first token has no predecessor to possibly merge with, so leading
            # whitespace ahead of it (a blank line, leading indentation) is unambiguously
            # insignificant — there is nothing on the other side of it. Force False rather than
            # comparing it, so a source file that happens to start with a blank line doesn't
            # register as a divergence against the serialiser's output (which never has one).
            result.append(_token_key(tok, False))
            continue
        offset = _token_start_offset(tok, line_starts)
        preceded = offset > 0 and text[offset - 1] in _WHITESPACE_CHARS
        result.append(_token_key(tok, preceded))
    return result


def normalized_bytes_match(source_text: str, serialized_text: str) -> bool:
    """True if `source_text` (the original file, as decoded UTF-8 text) and `serialized_text`
    (this module's naive serialiser's output) tokenise to the identical sequence — i.e. they
    differ, if at all, only in insignificant whitespace."""
    source = strip_bom_and_normalize_newlines(source_text)
    return tokenize_for_comparison(source) == tokenize_for_comparison(serialized_text)


def first_token_divergence(source_text: str, serialized_text: str):
    """Returns (index, source_token_or_None, serialized_token_or_None) for the first point the
    two token streams disagree, or None if they match. Diagnostic helper, not used by the
    pass/fail check itself."""
    divergences = all_token_divergences(source_text, serialized_text)
    return divergences[0] if divergences else None


def all_token_divergences(source_text: str, serialized_text: str) -> list:
    """Returns every (index, source_token_or_None, serialized_token_or_None) where the two token
    streams disagree — not just the first. A single file can have many independent benign
    adjacency mismatches (e.g. the "empty block" pattern recurs once per technology in a large
    file), and the allowlist (see roundtrip_allowlist.py) needs every site, not just whichever one
    happens to sort first."""
    source = strip_bom_and_normalize_newlines(source_text)
    src_tokens = tokenize_for_comparison(source)
    ser_tokens = tokenize_for_comparison(serialized_text)
    divergences = []
    for i in range(max(len(src_tokens), len(ser_tokens))):
        s = src_tokens[i] if i < len(src_tokens) else None
        t = ser_tokens[i] if i < len(ser_tokens) else None
        if s != t:
            divergences.append((i, s, t))
    return divergences


def is_adjacency_only_divergence(source_token, serialized_token) -> bool:
    """True if a divergence pair differs *only* in preceded_by_whitespace (index 4 of the
    `_token_key` tuple) — type, text, default and safe are all identical. This is the one shape
    an allowlist entry is ever allowed to cover (see roundtrip_allowlist.py): both tokens exist,
    both are the same token in every way that carries meaning, and only whether a separator
    character happened to be present differs. Anything else — a missing token (`None` on either
    side), or a difference in type/text/default/safe — is a real divergence in content, never
    eligible for allowlisting."""
    if source_token is None or serialized_token is None:
        return False
    return source_token[:4] == serialized_token[:4] and source_token[4] != serialized_token[4]
