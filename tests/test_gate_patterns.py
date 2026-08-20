"""Tests for pipeline.gate_patterns -- P-3 gate classification."""

from __future__ import annotations

from pipeline.availability import EXCLUDED_KEYS
from pipeline.clausewitz import parse_text
from pipeline.gate_patterns import (
    GATE_KIND_ASCENSION_PERK,
    GATE_KIND_ETHICS_OR_CIVIC,
    GATE_KIND_ORIGIN,
    GATE_KIND_TECHNOLOGY,
    GATE_LEAF_KEYS,
    NOT_GATE_CLASSIFIED_EXCLUDED_KEYS,
    WRAPPER_TO_ETHIC,
    WRAPPER_TO_ORIGIN,
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
    assert matches[0].alternative is False  # AND-context (the only condition) -- unconditional


# ---------------------------------------------------------------------------
# Item 4 ("path to zero uncertain" follow-up): OR-context vs. AND-context gates
# ---------------------------------------------------------------------------


def test_has_technology_inside_an_or_is_marked_alternative():
    # Real shape: tech_torpedoes_1's potential -- country_uses_bio_ships=no OR has_tradition=...
    # OR has_crisis_level=... OR has_technology=tech_cosmogenesis_escort ("Riddle Escort").
    block = _block(
        "{ potential = { OR = { country_uses_bio_ships = no has_technology = tech_cosmogenesis_escort } } }"
    )
    matches = classify_gates(block)
    assert len(matches) == 1
    assert matches[0].ref_id == "tech_cosmogenesis_escort"
    assert matches[0].alternative is True


def test_has_technology_at_the_and_top_level_is_not_alternative():
    block = _block("{ potential = { AND = { has_technology = tech_a is_nomadic = yes } } }")
    matches = classify_gates(block)
    assert len(matches) == 1
    assert matches[0].alternative is False


def test_has_technology_inside_and_nested_in_or_is_still_alternative():
    # An OR ancestor anywhere in the chain marks the leaf alternative, even if a nearer AND
    # ancestor exists between it and the leaf.
    block = _block(
        "{ potential = { OR = { AND = { has_technology = tech_a is_nomadic = yes } has_technology = tech_b } } }"
    )
    matches = classify_gates(block)
    assert len(matches) == 2
    assert all(m.alternative for m in matches)


def test_has_technology_inside_nor_is_still_alternative():
    block = _block("{ potential = { NOR = { has_technology = tech_a is_nomadic = yes } } }")
    matches = classify_gates(block)
    # NOR negates -- has_technology becomes a negated match, excluded entirely (module docstring),
    # so this asserts zero matches rather than an alternative one.
    assert matches == []


def test_has_origin_produces_an_origin_gate():
    block = _block("{ potential = { has_origin = origin_mindwardens } }")
    matches = classify_gates(block)
    assert len(matches) == 1
    assert matches[0].kind == GATE_KIND_ORIGIN
    assert matches[0].ref_id == "origin_mindwardens"
    assert matches[0].source_leaf == "has_origin"


def test_is_wilderness_empire_maps_to_its_wrapped_origin():
    block = _block("{ potential = { is_wilderness_empire = yes } }")
    matches = classify_gates(block)
    assert len(matches) == 1
    assert matches[0].kind == GATE_KIND_ORIGIN
    assert matches[0].ref_id == "origin_wilderness"
    assert matches[0].source_leaf == "is_wilderness_empire"


def test_has_valid_civic_and_has_civic_both_produce_ethics_or_civic_gates():
    block = _block("{ potential = { has_valid_civic = civic_machine_assimilator has_civic = civic_dystopian_society } }")
    matches = classify_gates(block)
    assert len(matches) == 2
    assert {m.ref_id for m in matches} == {"civic_machine_assimilator", "civic_dystopian_society"}
    assert all(m.kind == GATE_KIND_ETHICS_OR_CIVIC for m in matches)


def test_is_fanatic_spiritualist_maps_to_its_wrapped_ethic():
    block = _block("{ potential = { is_fanatic_spiritualist = yes } }")
    matches = classify_gates(block)
    assert len(matches) == 1
    assert matches[0].kind == GATE_KIND_ETHICS_OR_CIVIC
    assert matches[0].ref_id == "ethic_fanatic_spiritualist"


def test_can_research_technology_produces_a_technology_gate():
    block = _block("{ potential = { can_research_technology = tech_genome_mapping } }")
    matches = classify_gates(block)
    assert len(matches) == 1
    assert matches[0].kind == GATE_KIND_TECHNOLOGY
    assert matches[0].ref_id == "tech_genome_mapping"


def test_compound_excluded_key_produces_no_gate_match():
    # is_megacorp is availability-excluded but deliberately NOT gate-classified (compound/
    # non-origin-civic-ethic shaped) -- see NOT_GATE_CLASSIFIED_EXCLUDED_KEYS's own comment.
    block = _block("{ potential = { is_megacorp = yes } }")
    assert classify_gates(block) == []


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
# Cross-module consistency: every key pipeline.availability excludes from boolean combination (an
# identity-element state) must be accounted for HERE too -- either as a real, badge-classified
# gate (GATE_LEAF_KEYS) or as a deliberately-excluded-but-not-badged compound trigger
# (NOT_GATE_CLASSIFIED_EXCLUDED_KEYS, "path to zero uncertain" follow-up, Item 3 -- see that
# constant's own comment for why each one there has no single clean gate target). If either list
# changes without a matching change here, gate classification and availability evaluation silently
# diverge on what counts as a gate vs. a real uncertain leaf vs. an availability-only exclusion.
# ---------------------------------------------------------------------------


def test_gate_leaf_keys_plus_not_classified_matches_availabilitys_excluded_keys_exactly():
    assert GATE_LEAF_KEYS | NOT_GATE_CLASSIFIED_EXCLUDED_KEYS == EXCLUDED_KEYS
    assert GATE_LEAF_KEYS.isdisjoint(NOT_GATE_CLASSIFIED_EXCLUDED_KEYS)


def test_detector_catches_a_deliberately_diverged_key_set():
    """Proves the equality check above is capable of failing, not just passing by construction --
    this project's own standing rule ('a clean run proves nothing until the detector is shown
    capable of a dirty one')."""
    diverged = GATE_LEAF_KEYS - {"has_technology"}
    assert diverged | NOT_GATE_CLASSIFIED_EXCLUDED_KEYS != EXCLUDED_KEYS


def test_wrapper_to_perk_has_exactly_the_two_confirmed_wrappers():
    assert WRAPPER_TO_PERK == {
        "has_gigastructural_constructs": "ap_gigastructural_constructs",
        "has_galactic_wonders": "ap_galactic_wonders",
    }
