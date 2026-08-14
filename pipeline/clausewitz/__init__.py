"""Clausewitz tokeniser + recursive-descent parser (Stage 1 of the pipeline, spec/00-overview.md).

Produces a lossless AST: duplicate keys survive as ordered list entries (see
pipeline/clausewitz/nodes.py), block nesting is exact, comparison operators other than `=` are
preserved verbatim, and comments are preserved with their source position.

Deliberately out of scope here (separate, later passes — do not add them to this module):
  - Resolving `@variable` references against scripted_variables/.
  - Expanding `inline_script` directives.
  - Evaluating a `ConditionalBlock`'s guard (does the invocation supply that parameter?) —
    same deferred-resolution principle as `$PARAM$` substitution generally.
  - Interpreting boolean structure (`OR`/`AND`/`NOT`/`NOR`) — that's Stage 2's trigger evaluator.
  - Localisation YAML — a different file format, parsed separately (see
    tests/clausewitz/test_fixtures.py's module docstring for why).

Public API: `parse_file(path)`, `parse_text(text, path=...)`, `ClausewitzError`,
`ClausewitzEncodingError`.
"""

from __future__ import annotations

from pathlib import Path

from .errors import ClausewitzEncodingError, ClausewitzError
from .nodes import (
    Assignment,
    Block,
    Comment,
    ConditionalBlock,
    Document,
    Identifier,
    NumberLiteral,
    ParameterReference,
    StringLiteral,
    VariableReference,
)
from .parser import parse_tokens, tokenize_text

__all__ = [
    "ClausewitzError",
    "ClausewitzEncodingError",
    "parse_file",
    "parse_text",
    "Document",
    "Assignment",
    "Block",
    "Comment",
    "ConditionalBlock",
    "Identifier",
    "StringLiteral",
    "NumberLiteral",
    "VariableReference",
    "ParameterReference",
]


def _normalise_newlines(text: str) -> str:
    # Mirrors Python's own universal-newlines behaviour (str.open(newline=None)), applied
    # explicitly here because we decode from bytes ourselves to get clean encoding errors.
    return text.replace("\r\n", "\n").replace("\r", "\n")


def parse_text(text: str, path: str = "<string>") -> Document:
    """Parse Clausewitz script already available as a `str`. Does not touch encoding."""
    text = _normalise_newlines(text)
    tokens = tokenize_text(text, path)
    return parse_tokens(tokens, path)


def parse_file(path) -> Document:
    """Parse a Clausewitz script file from disk.

    Strips a UTF-8 BOM if present, normalises CRLF/CR to LF, and decodes strictly as UTF-8 —
    any other encoding (e.g. Windows-1252) raises `ClausewitzEncodingError` naming the file and
    an approximate line, rather than silently decoding as mojibake or crashing uninformatively.
    """
    path_str = str(path)
    raw = Path(path).read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        # Line count from a lenient re-decode of everything before the bad byte — good enough
        # for "which line is this near", which is all a byte-offset failure can promise.
        line = raw[: exc.start].decode("utf-8", errors="replace").count("\n") + 1
        bad_byte = raw[exc.start] if exc.start < len(raw) else None
        byte_desc = f"0x{bad_byte:02X}" if bad_byte is not None else "?"
        raise ClausewitzEncodingError(
            f"file is not valid UTF-8 ({exc.reason}); byte {byte_desc} at file offset "
            f"{exc.start} is not valid there — the file may be Windows-1252 or another "
            f"non-UTF-8 encoding",
            path_str,
            line,
        ) from exc

    text = _normalise_newlines(text)
    tokens = tokenize_text(text, path_str)
    return parse_tokens(tokens, path_str)
