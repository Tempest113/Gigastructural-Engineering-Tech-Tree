"""PERMANENT MUTATION HARNESS -- exists to keep the weight-gate polarity fix honest, forever.

Two polarity inversions shipped in two consecutive sessions before this file existed: the
alderson/disco-moon NOR-nested leaf miscount, and this one -- `classify_weight_gate_condition`
badging the `tech_housing_2`/`tech_housing_agrarian_idyll` civic-swap pair backwards. Both
produced plausible, confident, wrong output with an otherwise green suite: nothing failed, because
nothing exercised the ONE line (`invert_polarity=True` in `classify_weight_gate_condition`,
`pipeline/gate_patterns.py`) that makes the polarity come out right, in a way that would notice if
that line were removed again.

This file, like `tests/clausewitz/test_roundtrip_detects_mutations.py` (the established pattern
this one copies), monkeypatches away the specific fix and asserts the regression test THEN FAILS.
A monkeypatched-and-still-green test proves nothing; a monkeypatched-and-now-red test proves the
suite actually has teeth against this exact regression returning. Keep this file -- deleting it
once "the fix is obviously right" is exactly how the second inversion happened after the first.
"""

from __future__ import annotations

import pytest

from pipeline.clausewitz import parse_text
from pipeline.gate_patterns import _classify_leaves_in_block


def _block(text: str):
    doc = parse_text(f"tech_x = {text}\n", path="x.txt")
    return doc.items[0].value


def _broken_classify_weight_gate_condition(technology_key: str, condition_block, index: int):
    """Reproduces `classify_weight_gate_condition` exactly, MINUS `invert_polarity=True` -- the
    single-block, `potential`-only-correct formula applied unchanged to a weight condition. This
    is the real pre-fix behaviour, not a caricature of it: same function, same dispatch, one
    keyword argument removed."""
    return _classify_leaves_in_block(technology_key, condition_block, f"weight-gate{index}-alt")


def test_removing_invert_polarity_reverses_the_housing_pairs_reported_negation():
    """The mutation itself: with `invert_polarity` gone, `_leaf_negated`'s raw (potential-block)
    polarity leaks through unchanged, so both members of the housing swap pair report the OPPOSITE
    of their real-world meaning."""
    unwrapped = _block("{ has_valid_civic = civic_agrarian_idyll }")  # weight zero WHEN you have the civic -> excludes agrarian-idyll players
    wrapped = _block("{ NOT = { has_valid_civic = civic_agrarian_idyll } }")  # weight zero WITHOUT it -> needs the civic

    broken_unwrapped = _broken_classify_weight_gate_condition("tech_housing_2", unwrapped, 0)
    broken_wrapped = _broken_classify_weight_gate_condition("tech_housing_agrarian_idyll", wrapped, 0)

    assert len(broken_unwrapped) == 1 and len(broken_wrapped) == 1
    # The real, correct values (see test_gate_patterns.py's
    # test_known_corpus_pairs_badge_with_opposite_polarity) are unwrapped.negated=True,
    # wrapped.negated=False. Without invert_polarity, both come out flipped from that.
    assert broken_unwrapped[0].negated is False  # correct value: True
    assert broken_wrapped[0].negated is True  # correct value: False


def test_removing_invert_polarity_breaks_the_registered_housing_pair_assertion():
    """The harness proper: run test_gate_patterns.py's own registered-pair assertion (not a
    restatement of it -- the literal comparison it makes) against the broken classifier via
    monkeypatch, and assert THAT specific assertion then raises. This is the "proven capable of
    failing against a plausible near-fix" claim `tests/test_dataset_emit.py`'s
    `test_weight_gate_polarity_is_inverted_relative_to_potential` docstring already made by hand
    -- automated here so it can never silently stop being true."""
    import pipeline.gate_patterns as gate_patterns_module

    unwrapped_key, unwrapped_text = "tech_housing_2", "{ has_valid_civic = civic_agrarian_idyll }"
    wrapped_key, wrapped_text = "tech_housing_agrarian_idyll", "{ NOT = { has_valid_civic = civic_agrarian_idyll } }"

    def run_pair_assertion():
        unwrapped_matches = gate_patterns_module.classify_weight_gate_condition(
            unwrapped_key, _block(unwrapped_text), 0
        )
        wrapped_matches = gate_patterns_module.classify_weight_gate_condition(
            wrapped_key, _block(wrapped_text), 0
        )
        # Pinned to the real-world direction, not just "opposite of each other" -- an inverted
        # classifier ALSO produces two mutually-opposite values (both flipped from reality), so a
        # bare `!=` check can't distinguish a real fix from its own exact inverse and would pass
        # against this mutation too (confirmed while writing this harness).
        assert unwrapped_matches[0].negated is True
        assert wrapped_matches[0].negated is False

    # Sanity check first: the assertion passes against the REAL, unpatched function.
    run_pair_assertion()

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            gate_patterns_module, "classify_weight_gate_condition", _broken_classify_weight_gate_condition
        )
        with pytest.raises(AssertionError):
            run_pair_assertion()

    # And passes again once the patch is undone -- proves the failure above came from the
    # mutation, not from test pollution/order-dependence.
    run_pair_assertion()
