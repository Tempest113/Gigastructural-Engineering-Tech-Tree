"""Tests for pipeline.gate_patterns -- P-3 gate classification."""

from __future__ import annotations

from pipeline.availability import EXCLUDED_KEYS
from pipeline.clausewitz import parse_text
from pipeline.gate_patterns import (
    GATE_KIND_ASCENSION_PERK,
    GATE_KIND_TECHNOLOGY,
    GATE_LEAF_KEYS,
    WRAPPER_TO_PERK,
    classify_gates,
    order_gates,
)


def _block(text: str):
    doc = parse_text(f"tech_x = {text}\n", path="x.txt")
    return doc.items[0].value


# ---------------------------------------------------------------------------
# Basic pattern recognition -- one per registered mechanism.
# ---------------------------------------------------------------------------


def test_has_ascension_perk_produces_an_ascension_perk_gate():
    block = _block("{ potential = { has_ascension_perk = ap_vast_expanses } }")
    matches = classify_gates(block)
    assert len(matches) == 1
    assert matches[0].kind == GATE_KIND_ASCENSION_PERK
    assert matches[0].ref_id == "ap_vast_expanses"
    assert matches[0].source_leaf == "has_ascension_perk"


def test_has_technology_produces_a_technology_gate():
    block = _block("{ potential = { has_technology = tech_dark_matter_power_core_ae } }")
    matches = classify_gates(block)
    assert len(matches) == 1
    assert matches[0].kind == GATE_KIND_TECHNOLOGY
    assert matches[0].ref_id == "tech_dark_matter_power_core_ae"


def test_has_gigastructural_constructs_maps_to_its_wrapped_perk():
    block = _block("{ potential = { has_gigastructural_constructs = yes } }")
    matches = classify_gates(block)
    assert len(matches) == 1
    assert matches[0].kind == GATE_KIND_ASCENSION_PERK
    assert matches[0].ref_id == "ap_gigastructural_constructs"
    assert matches[0].source_leaf == "has_gigastructural_constructs"


def test_has_galactic_wonders_maps_to_the_canonical_base_perk():
    block = _block("{ potential = { has_galactic_wonders = yes } }")
    matches = classify_gates(block)
    assert len(matches) == 1
    assert matches[0].kind == GATE_KIND_ASCENSION_PERK
    assert matches[0].ref_id == "ap_galactic_wonders"


def test_no_potential_block_produces_no_gates():
    block = _block("{ cost = 100 }")
    assert classify_gates(block) == []


def test_unrelated_potential_content_produces_no_gates():
    block = _block("{ potential = { is_nomadic = yes country_uses_bio_ships = yes } }")
    assert classify_gates(block) == []


# ---------------------------------------------------------------------------
# Scope discipline -- mirrors pipeline.edges's count_country false-positive regression test.
# ---------------------------------------------------------------------------


def test_opaque_scope_is_not_searched():
    """A gate-shaped leaf nested inside an opaque block-valued field (count_country here, the
    same field pipeline.edges's own regression test uses) must NOT produce a gate -- matches
    P-14's scope discipline exactly (only AND/OR/NOT/NOR are descended into)."""
    block = _block(
        "{ potential = { count_country = { limit = { has_ascension_perk = ap_vast_expanses } } } }"
    )
    assert classify_gates(block) == []


def test_descends_into_and_or_wrappers():
    block = _block(
        "{ potential = { AND = { OR = { has_ascension_perk = ap_cosmogenesis has_technology = tech_x } } } }"
    )
    matches = classify_gates(block)
    assert {(m.kind, m.ref_id) for m in matches} == {
        (GATE_KIND_ASCENSION_PERK, "ap_cosmogenesis"),
        (GATE_KIND_TECHNOLOGY, "tech_x"),
    }


def test_negated_gate_leaf_is_excluded():
    """Zero real negated occurrences of any of the four registered keys exist under `potential`
    today (gate-classification survey) -- this proves the exclusion actually works, for the case
    that doesn't currently occur, rather than leaving it untested."""
    block = _block("{ potential = { NOT = { has_ascension_perk = ap_vast_expanses } } }")
    assert classify_gates(block) == []


def test_multiple_targets_of_the_same_mechanism_all_produce_gates():
    """tech_qnm_disruptors-shaped case (real corpus, gate-classification session): two distinct
    has_technology targets on one technology both become gates, not just the first."""
    block = _block(
        "{ potential = { has_technology = tech_a has_technology = tech_b } }"
    )
    matches = classify_gates(block)
    assert {m.ref_id for m in matches} == {"tech_a", "tech_b"}
    assert all(m.kind == GATE_KIND_TECHNOLOGY for m in matches)


# ---------------------------------------------------------------------------
# Ordering (D-3): ascension-perk gates before technology gates, declaration order preserved
# within a kind.
# ---------------------------------------------------------------------------


def test_order_gates_puts_ascension_perk_before_technology():
    block = _block(
        "{ potential = { has_technology = tech_cosmogenesis_world has_ascension_perk = ap_cosmogenesis } }"
    )
    ordered = order_gates(classify_gates(block))
    assert [m.kind for m in ordered] == [GATE_KIND_ASCENSION_PERK, GATE_KIND_TECHNOLOGY]
    assert ordered[0].ref_id == "ap_cosmogenesis"


def test_order_gates_is_stable_within_a_kind():
    block = _block(
        "{ potential = { has_technology = tech_b has_technology = tech_a } }"
    )
    ordered = order_gates(classify_gates(block))
    # declaration order preserved -- tech_b named first in source, stays first.
    assert [m.ref_id for m in ordered] == ["tech_b", "tech_a"]


# ---------------------------------------------------------------------------
# Cross-module consistency: the four registered gate keys must be exactly the four keys
# pipeline.availability already excludes from boolean combination (an identity-element state
# predating this module) -- if either list changes without the other, gate classification and
# availability evaluation silently diverge on what counts as a gate vs. a real uncertain leaf.
# ---------------------------------------------------------------------------


def test_gate_leaf_keys_matches_availabilitys_excluded_keys_exactly():
    assert GATE_LEAF_KEYS == EXCLUDED_KEYS


def test_detector_catches_a_deliberately_diverged_key_set():
    """Proves the equality check above is capable of failing, not just passing by construction --
    this project's own standing rule ('a clean run proves nothing until the detector is shown
    capable of a dirty one')."""
    diverged = GATE_LEAF_KEYS - {"has_technology"}
    assert diverged != EXCLUDED_KEYS


def test_wrapper_to_perk_has_exactly_the_two_confirmed_wrappers():
    assert WRAPPER_TO_PERK == {
        "has_gigastructural_constructs": "ap_gigastructural_constructs",
        "has_galactic_wonders": "ap_galactic_wonders",
    }
