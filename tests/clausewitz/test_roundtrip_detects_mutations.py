"""PERMANENT MUTATION HARNESS — exists to keep the round-trip comparator honest, forever.

This file exists to prevent the round-trip comparator (`pipeline/clausewitz/roundtrip.py`) from
being weakened back into a check that cannot see the bug class it was built for. It is not a
one-off self-check to be deleted once trust is established: `preceded_by_whitespace` is easy to
mistake for excess caution once the corpus round-trip is green and quiet (see
`roundtrip_allowlist.json`'s 433 reviewed-benign sites — plausible-looking future "simplifications"
include dropping the separator-presence bit because it's "just noise," or trying to reconstruct
adjacency by asking the tokeniser whether a pair could lex differently if concatenated). Both of
those look like harmless cleanups and both would make the tests below fail to catch the exact
regressions they exist to catch — see roundtrip.py's module docstring for why "ask the tokeniser"
specifically doesn't work (it consults the same tool that's under test). Keep this file, and treat
a failure in it as a signal that the comparator just lost the one thing that makes it more than a
parse-doesn't-crash check.

A zero-findings round-trip run (see test_roundtrip.py) is only meaningful if the tool is
demonstrably capable of a non-zero one. This file reintroduces, one at a time, the exact two
historical tokeniser bugs the round-trip detector exists to catch — both real, both previously
shipped undetected until fixture assertions happened to notice them (see
tests/fixtures/NOTES.md and pipeline/clausewitz/tokenizer.py's `_consume_attached_continuations`
docstring) — and asserts `roundtrip.normalized_bytes_match` fails on each, reporting a usable
file/offset.

Both mutations patch `Tokenizer._consume_attached_continuations` (via `monkeypatch`, so the
patch is undone at the end of each test) to remove exactly one of its branches, reproducing the
narrowest possible slice of the pre-fix tokeniser: everything else about attached-continuation
handling stays intact, only the one historical gap reopens. Critically, the patch is in effect
for **both** the `parse_file` call (which builds the corrupted AST) and the
`normalized_bytes_match` call (which re-tokenises the original source for comparison) — the same
tokeniser instance class is used on both sides, exactly as it would be if this bug were
genuinely still live in the codebase. This matters: a version of this detector that only
compared token type/text/default/safe (no separator-presence bit) would tokenise the source with
the *same* broken tokeniser it used to build the AST, so a corruption that manifests as "this
token's text is now split across two tokens instead of one" reproduces identically on both sides
and silently passes — the exact failure mode this repo's round-trip work was reworked to close.
Each test below also runs the same comparison with a `_type_text_only` reduction (dropping the
`preceded_by_whitespace` field) to make that contrast concrete: it demonstrates *why* the
detector needs the separator-presence bit, not just that the full detector happens to fail.

This is in addition to, not a replacement for, the permanent regression coverage these two bugs
already have in tests/clausewitz/test_fixtures.py's `test_scope_suffixed_flag_is_one_identifier...`
and `test_parameter_reference_with_default_value`/NOTES.md's mid-token-$PARAM$ note — those assert
the *parser* gets these two specific inputs right; this file asserts the *round-trip comparator*
would notice if some future change made it wrong again, which is a different, narrower claim and
the one this file is for.
"""

from __future__ import annotations

from pipeline.clausewitz import parse_text
from pipeline.clausewitz.roundtrip import (
    first_token_divergence,
    normalized_bytes_match,
    tokenize_for_comparison,
)
from pipeline.clausewitz.serializer import serialize_document
from pipeline.clausewitz.tokenizer import Tokenizer
from pipeline.clausewitz.tokens import TokenType

_IDENTIFIER_START = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_")
_DIGITS = set("0123456789")
_IDENTIFIER_CONT = _IDENTIFIER_START | set("0123456789/:?")


def _consume_attached_continuations_without_at_suffix(self, chars: list[str]) -> None:
    """Reproduces the tokeniser as it stood before commit 5ab5c42 ("Fix tokeniser scope-suffix
    and dotted-identifier gaps"): every attached-continuation shape intact *except* the '@' +
    identifier-start scope-suffix case (`flag@root`, `flag@$SCOPE$`) — the exact gap that used
    to silently split a flag name from its scope suffix instead of keeping them one token."""
    while True:
        progressed = False
        while not self._at_end() and self._peek() in _IDENTIFIER_CONT:
            chars.append(self._advance())
            progressed = True
        if self._peek() == "." and (self._peek(1) in _IDENTIFIER_START or self._peek(1) in _DIGITS):
            chars.append(self._advance())
            progressed = True
            continue
        # '@' + identifier-start/'$' branch deliberately omitted — this is the mutation.
        if self._peek() == "|":
            chars.append(self._advance())
            if self._peek() == "$":
                self._consume_dollar_span(chars)
            elif self._peek() == "@":
                chars.append(self._advance())
            progressed = True
            continue
        if self._peek() == "$":
            self._consume_dollar_span(chars)
            progressed = True
            continue
        if not progressed:
            break


def _consume_attached_continuations_without_bare_dollar_splice(self, chars: list[str]) -> None:
    """Reproduces the tokeniser as it stood before this session's uncommitted fix (see
    tests/fixtures/NOTES.md's "A related, broader bug found while adding these fixtures" note):
    every attached-continuation shape intact *except* a bare '$PARAM$' embedded directly in
    running identifier text with no connecting '.'/'@'/'|' — the exact gap that used to silently
    split e.g. `crisis_stage_$STAGE|1$` into two disconnected block members instead of one
    value."""
    while True:
        progressed = False
        while not self._at_end() and self._peek() in _IDENTIFIER_CONT:
            chars.append(self._advance())
            progressed = True
        if self._peek() == "." and (self._peek(1) in _IDENTIFIER_START or self._peek(1) in _DIGITS):
            chars.append(self._advance())
            progressed = True
            continue
        if self._peek() == "@" and (self._peek(1) in _IDENTIFIER_START or self._peek(1) == "$"):
            chars.append(self._advance())
            if self._peek() == "$":
                self._consume_dollar_span(chars)
            progressed = True
            continue
        if self._peek() == "|":
            chars.append(self._advance())
            if self._peek() == "$":
                self._consume_dollar_span(chars)
            elif self._peek() == "@":
                chars.append(self._advance())
            progressed = True
            continue
        # bare '$' branch deliberately omitted — this is the mutation.
        if not progressed:
            break


def _type_text_only_tokens(text: str) -> list:
    """The comparison this repo used before separator-presence was added: type/text/default/safe
    only, no preceded_by_whitespace. Used here only to demonstrate the contrast."""
    return [key[:4] for key in tokenize_for_comparison(text)]


def test_mutation_reintroduces_flag_at_root_scope_suffix_split(monkeypatch):
    monkeypatch.setattr(Tokenizer, "_consume_attached_continuations", _consume_attached_continuations_without_at_suffix)

    source = "ehof_travel_conditions = { NOT = { has_star_flag = ehof_megastructure_system@root } }\n"
    doc = parse_text(source, path="<mutation:flag@root>")
    serialized = serialize_document(doc)

    # Sanity check the mutation actually reproduces the historical corruption at the AST level,
    # not just "some difference or other": the flag's value must have been truncated, with a
    # spurious sibling VariableReference('root') split off — matching NOTES.md's description of
    # the original bug exactly.
    not_block = doc.items[0].value.items[0]
    flag_assignment = not_block.value.items[0]
    assert flag_assignment.key_name == "has_star_flag"
    assert flag_assignment.value.name == "ehof_megastructure_system", (
        "mutation did not reproduce the truncation — fix the mutation, not the tokeniser"
    )
    stray_items = not_block.value.items[1:]
    assert len(stray_items) == 1 and getattr(stray_items[0], "name", None) == "root", (
        "mutation did not reproduce the fabricated sibling @variable reference"
    )

    # The bug this test reintroduces: does the round-trip detector actually fail on it?
    assert not normalized_bytes_match(source, serialized), (
        "round-trip detector FAILED TO CATCH the reintroduced flag@root scope-suffix split "
        "bug — it should have reported a mismatch and did not"
    )
    divergence = first_token_divergence(source, serialized)
    assert divergence is not None
    print(f"flag@root mutation: detector correctly failed; first divergence: {divergence}")

    # Contrast: the type/text-only comparison (no preceded_by_whitespace) that a weaker detector
    # would use. Both sides are tokenised with the SAME mutated tokeniser here (matching what
    # normalized_bytes_match itself does), so the corrupted split reproduces identically on both
    # sides and a type/text-only check cannot see it.
    source_tt = _type_text_only_tokens(source)
    serialized_tt = _type_text_only_tokens(serialized)
    assert source_tt == serialized_tt, (
        "expected the type/text-only comparison to be fooled by this mutation (demonstrating "
        "why preceded_by_whitespace is required) — it wasn't; the demonstration no longer holds "
        "and needs re-examining, not silently deleting"
    )


def test_mutation_reintroduces_dollar_param_glued_to_identifier_split(monkeypatch):
    monkeypatch.setattr(
        Tokenizer, "_consume_attached_continuations", _consume_attached_continuations_without_bare_dollar_splice
    )

    source = "has_crisis_stage = { has_global_flag = crisis_stage_$STAGE|1$ }\n"
    doc = parse_text(source, path="<mutation:param-glued>")
    serialized = serialize_document(doc)

    trigger_block = doc.items[0].value
    flag_assignment = trigger_block.items[0]
    assert flag_assignment.key_name == "has_global_flag"
    assert flag_assignment.value.name == "crisis_stage_", (
        "mutation did not reproduce the truncation — fix the mutation, not the tokeniser"
    )
    stray_items = trigger_block.items[1:]
    assert len(stray_items) == 1 and getattr(stray_items[0], "name", None) == "STAGE", (
        "mutation did not reproduce the disconnected $PARAM$ sibling"
    )
    assert getattr(stray_items[0], "default", None) == "1"

    assert not normalized_bytes_match(source, serialized), (
        "round-trip detector FAILED TO CATCH the reintroduced $PARAM$-glued-to-identifier split "
        "bug — it should have reported a mismatch and did not"
    )
    divergence = first_token_divergence(source, serialized)
    assert divergence is not None
    print(f"$PARAM$-glued mutation: detector correctly failed; first divergence: {divergence}")

    source_tt = _type_text_only_tokens(source)
    serialized_tt = _type_text_only_tokens(serialized)
    assert source_tt == serialized_tt, (
        "expected the type/text-only comparison to be fooled by this mutation (demonstrating "
        "why preceded_by_whitespace is required) — it wasn't; the demonstration no longer holds "
        "and needs re-examining, not silently deleting"
    )
