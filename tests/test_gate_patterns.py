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
    matches = classify_gates("tech_x", block)
    assert len(matches) == 1
    assert matches[0].kind == GATE_KIND_ASCENSION_PERK
    assert matches[0].ref_id == "ap_vast_expanses"
    assert matches[0].source_leaf == "has_ascension_perk"


def test_has_technology_produces_a_technology_gate():
    block = _block("{ potential = { has_technology = tech_dark_matter_power_core_ae } }")
    matches = classify_gates("tech_x", block)
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
    matches = classify_gates("tech_x", block)
    assert len(matches) == 1
    assert matches[0].ref_id == "tech_cosmogenesis_escort"
    assert matches[0].alternative is True


def test_has_technology_at_the_and_top_level_is_not_alternative():
    block = _block("{ potential = { AND = { has_technology = tech_a is_nomadic = yes } } }")
    matches = classify_gates("tech_x", block)
    assert len(matches) == 1
    assert matches[0].alternative is False


def test_has_technology_inside_and_nested_in_or_is_still_alternative():
    # An OR ancestor anywhere in the chain marks the leaf alternative, even if a nearer AND
    # ancestor exists between it and the leaf.
    block = _block(
        "{ potential = { OR = { AND = { has_technology = tech_a is_nomadic = yes } has_technology = tech_b } } }"
    )
    matches = classify_gates("tech_x", block)
    assert len(matches) == 2
    assert all(m.alternative for m in matches)


def test_has_technology_inside_nor_is_still_alternative():
    block = _block("{ potential = { NOR = { has_technology = tech_a is_nomadic = yes } } }")
    matches = classify_gates("tech_x", block)
    # NOR negates -- has_technology becomes a negated match (a later session: negative gates are
    # kept, not excluded -- see module docstring's "Negative gates" section). `is_nomadic` isn't a
    # registered gate leaf, so it never becomes a second match.
    assert len(matches) == 1
    assert matches[0].kind == GATE_KIND_TECHNOLOGY
    assert matches[0].ref_id == "tech_a"
    assert matches[0].negated is True
    assert matches[0].alternative is True


def test_has_origin_produces_an_origin_gate():
    block = _block("{ potential = { has_origin = origin_mindwardens } }")
    matches = classify_gates("tech_x", block)
    assert len(matches) == 1
    assert matches[0].kind == GATE_KIND_ORIGIN
    assert matches[0].ref_id == "origin_mindwardens"
    assert matches[0].source_leaf == "has_origin"


def test_is_wilderness_empire_maps_to_its_wrapped_origin():
    block = _block("{ potential = { is_wilderness_empire = yes } }")
    matches = classify_gates("tech_x", block)
    assert len(matches) == 1
    assert matches[0].kind == GATE_KIND_ORIGIN
    assert matches[0].ref_id == "origin_wilderness"
    assert matches[0].source_leaf == "is_wilderness_empire"


def test_has_valid_civic_and_has_civic_both_produce_ethics_or_civic_gates():
    block = _block("{ potential = { has_valid_civic = civic_machine_assimilator has_civic = civic_dystopian_society } }")
    matches = classify_gates("tech_x", block)
    assert len(matches) == 2
    assert {m.ref_id for m in matches} == {"civic_machine_assimilator", "civic_dystopian_society"}
    assert all(m.kind == GATE_KIND_ETHICS_OR_CIVIC for m in matches)


def test_is_fanatic_spiritualist_maps_to_its_wrapped_ethic():
    block = _block("{ potential = { is_fanatic_spiritualist = yes } }")
    matches = classify_gates("tech_x", block)
    assert len(matches) == 1
    assert matches[0].kind == GATE_KIND_ETHICS_OR_CIVIC
    assert matches[0].ref_id == "ethic_fanatic_spiritualist"


def test_can_research_technology_produces_no_gate_match():
    # REMOVED from gate classification (a later session, user-reported polarity/meaning bug):
    # can_research_technology means "this OTHER technology is not currently locked out for your
    # empire" (a structural eligibility fact), not has_technology's "you have ALREADY completed
    # this" -- badging it "Needs Genome Mapping" told the player to go complete a technology
    # unrelated to their actual restriction. Real corpus: gate-propagation inherited this single
    # mis-badge onto 15 further descendants (16 technologies total) before the fix. Still excluded
    # from `pipeline.availability`'s boolean combination (an identity element there), unaffected
    # by this change -- only the gate BADGE is gone.
    block = _block("{ potential = { can_research_technology = tech_genome_mapping } }")
    assert classify_gates("tech_x", block) == []


def test_compound_excluded_key_produces_no_gate_match():
    # is_megacorp is availability-excluded but deliberately NOT gate-classified (compound/
    # non-origin-civic-ethic shaped) -- see NOT_GATE_CLASSIFIED_EXCLUDED_KEYS's own comment.
    block = _block("{ potential = { is_megacorp = yes } }")
    assert classify_gates("tech_x", block) == []


def test_has_gigastructural_constructs_maps_to_its_wrapped_perk():
    block = _block("{ potential = { has_gigastructural_constructs = yes } }")
    matches = classify_gates("tech_x", block)
    assert len(matches) == 1
    assert matches[0].kind == GATE_KIND_ASCENSION_PERK
    assert matches[0].ref_id == "ap_gigastructural_constructs"
    assert matches[0].source_leaf == "has_gigastructural_constructs"


def test_has_galactic_wonders_maps_to_the_canonical_base_perk():
    block = _block("{ potential = { has_galactic_wonders = yes } }")
    matches = classify_gates("tech_x", block)
    assert len(matches) == 1
    assert matches[0].kind == GATE_KIND_ASCENSION_PERK
    assert matches[0].ref_id == "ap_galactic_wonders"


def test_no_potential_block_produces_no_gates():
    block = _block("{ cost = 100 }")
    assert classify_gates("tech_x", block) == []


def test_unrelated_potential_content_produces_no_gates():
    block = _block("{ potential = { is_nomadic = yes country_uses_bio_ships = yes } }")
    assert classify_gates("tech_x", block) == []


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
    assert classify_gates("tech_x", block) == []


def test_descends_into_and_or_wrappers():
    block = _block(
        "{ potential = { AND = { OR = { has_ascension_perk = ap_cosmogenesis has_technology = tech_x } } } }"
    )
    matches = classify_gates("tech_x", block)
    assert {(m.kind, m.ref_id) for m in matches} == {
        (GATE_KIND_ASCENSION_PERK, "ap_cosmogenesis"),
        (GATE_KIND_TECHNOLOGY, "tech_x"),
    }


def test_negated_gate_leaf_becomes_a_negative_gate():
    """A later session (negative gates): a negated leaf is no longer dropped -- it becomes a
    GateMatch with negated=True, rendered as "Unavailable to X" rather than silently vanishing."""
    block = _block("{ potential = { NOT = { has_ascension_perk = ap_vast_expanses } } }")
    matches = classify_gates("tech_x", block)
    assert len(matches) == 1
    assert matches[0].kind == GATE_KIND_ASCENSION_PERK
    assert matches[0].ref_id == "ap_vast_expanses"
    assert matches[0].negated is True


def test_multiple_targets_of_the_same_mechanism_all_produce_gates():
    """tech_qnm_disruptors-shaped case (real corpus, gate-classification session): two distinct
    has_technology targets on one technology both become gates, not just the first."""
    block = _block(
        "{ potential = { has_technology = tech_a has_technology = tech_b } }"
    )
    matches = classify_gates("tech_x", block)
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
    ordered = order_gates(classify_gates("tech_x", block))
    assert [m.kind for m in ordered] == [GATE_KIND_ASCENSION_PERK, GATE_KIND_TECHNOLOGY]
    assert ordered[0].ref_id == "ap_cosmogenesis"


def test_order_gates_is_stable_within_a_kind():
    block = _block(
        "{ potential = { has_technology = tech_b has_technology = tech_a } }"
    )
    ordered = order_gates(classify_gates("tech_x", block))
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
    # Item 2 (later session): `has_ascension_perk` moved OUT of plain `EXCLUDED_KEYS` -- it now
    # gets its own leaf-evaluation branch in `pipeline.availability._evaluate_leaf` so it can
    # resolve a real LOCKED result when the referenced perk is axis-restricted, instead of always
    # being an identity-element exclusion. It is STILL gate-classified (GATE_LEAF_KEYS unchanged)
    # and still behaves like an EXCLUDED_KEYS entry for every perk that isn't axis-locked for the
    # current profile -- see pipeline.availability's module docstring. This invariant is corrected
    # to account for that one key moving to its own bucket, not silenced.
    assert GATE_LEAF_KEYS | NOT_GATE_CLASSIFIED_EXCLUDED_KEYS == EXCLUDED_KEYS | {"has_ascension_perk"}
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


# ---------------------------------------------------------------------------
# Gate-polarity fix (a later session, user-reported): a leaf's own literal boolean-false VALUE
# (`is_wilderness_empire = no`) is a negation channel independent of NOT/NOR wrapping, and was
# previously never checked -- the exact bug behind "habitat technologies marked as REQUIRING a
# wilderness empire" when the real corpus condition means the opposite.
# ---------------------------------------------------------------------------


def test_wrapper_key_with_literal_no_value_produces_a_negative_gate():
    # `is_wilderness_empire = no` means "needs a NON-wilderness empire" -- no NOT/NOR wrapper at
    # all, yet the leaf is negated. Real corpus: 31 technologies, tech_habitat_1/tech_habitat_2/
    # tech_gene_banks among them (a later session: rendered as "Unavailable to Wilderness Origin",
    # not dropped).
    block = _block("{ potential = { is_wilderness_empire = no } }")
    matches = classify_gates("tech_x", block)
    assert len(matches) == 1
    assert matches[0].kind == GATE_KIND_ORIGIN
    assert matches[0].ref_id == "origin_wilderness"
    assert matches[0].negated is True


def test_wrapper_key_with_literal_yes_value_still_produces_a_gate():
    # The positive case must be UNCHANGED by the fix -- a bare `= yes` (or omitted operator
    # equivalent) still gates normally.
    block = _block("{ potential = { is_wilderness_empire = yes } }")
    matches = classify_gates("tech_x", block)
    assert len(matches) == 1
    assert matches[0].kind == GATE_KIND_ORIGIN
    assert matches[0].ref_id == "origin_wilderness"
    assert matches[0].negated is False


def test_double_negation_of_literal_no_value_produces_a_real_gate():
    # NOR(is_wilderness_empire = no) = "NOT (NOT wilderness)" = "IS wilderness" -- a real, if
    # convoluted, positive requirement. Proves the fix is a genuine 3-way XOR (wrapper negation
    # combined with value-level negation), not merely "always exclude a `= no` leaf outright".
    block = _block("{ potential = { NOR = { is_wilderness_empire = no } } }")
    matches = classify_gates("tech_x", block)
    assert len(matches) == 1
    assert matches[0].kind == GATE_KIND_ORIGIN
    assert matches[0].ref_id == "origin_wilderness"
    assert matches[0].negated is False


def test_detector_catches_a_gate_mechanism_that_ignores_value_level_negation():
    """Proves the polarity fix is load-bearing: a naive matcher that only tracks NOT/NOR-wrapper
    negation (the pre-fix behaviour) would wrongly classify `is_wilderness_empire = no` as a
    POSITIVE gate. Reconstructs that naive behaviour directly (bypassing `_leaf_negated`) to show
    it disagrees with the real, fixed classifier -- which still produces a match (a later session:
    negative gates are kept, not dropped), but the correct, NEGATED one."""
    from pipeline.gate_patterns import _target_name
    from pipeline.clausewitz.nodes import Assignment

    block = _block("{ potential = { is_wilderness_empire = no } }")
    potential = block.items[-1]
    leaf = potential.value.items[0]
    assert isinstance(leaf, Assignment)
    naive_negated = False  # the pre-fix logic: no NOT/NOR ancestor -> never negated
    naive_would_gate_positive = _target_name(leaf.value) is not None and not naive_negated
    assert naive_would_gate_positive is True  # the bug, reconstructed
    [real_match] = classify_gates("tech_x", block)
    assert real_match.negated is True  # the real, fixed behaviour disagrees on polarity


# ---------------------------------------------------------------------------
# Nested AND-of-OR groupId fix (a later session, user-reported: Gargantuan Cloning Facilities
# showed "Needs Galactic Wonders" + "or: Mechromancy" as flat peers).
# ---------------------------------------------------------------------------


def test_mixed_and_or_gates_carry_distinguishing_group_ids():
    block = _block("""
    {
        potential = {
            has_galactic_wonders = yes
            OR = {
                has_genetically_ascended = yes
                has_ascension_perk = ap_mechromancy
            }
        }
    }
    """)
    matches = classify_gates("giga_tech_the_vat", block)
    assert len(matches) == 2
    unconditional = next(m for m in matches if m.ref_id == "ap_galactic_wonders")
    grouped = next(m for m in matches if m.ref_id == "ap_mechromancy")
    assert unconditional.alternative is False
    assert unconditional.group_id is None
    assert grouped.alternative is True
    assert grouped.group_id == "giga_tech_the_vat#gate-alt0"


def test_two_independent_or_groups_get_distinct_group_ids():
    block = _block("""
    {
        potential = {
            OR = { has_ascension_perk = ap_a has_ascension_perk = ap_b }
            OR = { has_ascension_perk = ap_c has_ascension_perk = ap_d }
        }
    }
    """)
    matches = classify_gates("tech_x", block)
    group_ids = {m.ref_id: m.group_id for m in matches}
    assert group_ids["ap_a"] == group_ids["ap_b"]
    assert group_ids["ap_c"] == group_ids["ap_d"]
    assert group_ids["ap_a"] != group_ids["ap_c"]


# ---------------------------------------------------------------------------
# Weight-condition gate extraction (a later session): `classify_weight_gate_condition`.
# ---------------------------------------------------------------------------


def test_weight_condition_not_wrapped_perk_produces_a_gate_despite_reading_negated():
    """`tech_lathe_*`'s real shape: `NOT = { ..., has_ascension_perk = ap_cosmogenesis }` inside
    a zero-factor `weight_modifier` condition. The leaf reads NEGATED under the standard
    `_scoped_gate_leaves` polarity (same as `classify_gates` would compute), but weight-condition
    extraction does not filter on polarity -- see `classify_weight_gate_condition`'s own
    docstring for why."""
    from pipeline.gate_patterns import classify_weight_gate_condition

    condition = _block("""
    {
        NOT = {
            any_owned_planet = { is_planet_class = pc_cosmogenesis_world }
            has_ascension_perk = ap_cosmogenesis
        }
    }
    """)
    matches = classify_weight_gate_condition("tech_lathe_overclocker", condition, 0)
    assert len(matches) == 1
    assert matches[0].kind == GATE_KIND_ASCENSION_PERK
    assert matches[0].ref_id == "ap_cosmogenesis"
    assert matches[0].alternative is False


def test_weight_condition_unwrapped_civic_produces_a_gate_from_either_polarity():
    """`tech_housing_2`/`tech_housing_agrarian_idyll`'s real civic-swap-pair shape: one names the
    civic completely unwrapped, the other under a `NOT` -- both must badge identically, since both
    name the same real fact (`civic_agrarian_idyll`) from opposite sides of the same swap."""
    from pipeline.gate_patterns import classify_weight_gate_condition

    unwrapped = _block("{ has_valid_civic = civic_agrarian_idyll }")
    wrapped = _block("{ NOT = { has_valid_civic = civic_agrarian_idyll } }")
    for condition in (unwrapped, wrapped):
        matches = classify_weight_gate_condition("tech_housing_2", condition, 0)
        assert len(matches) == 1
        assert matches[0].kind == GATE_KIND_ETHICS_OR_CIVIC
        assert matches[0].ref_id == "civic_agrarian_idyll"


def test_weight_condition_nor_of_perks_produces_an_alternative_group():
    """`tech_neuro_quantum_links`'s real shape: `NOR = { has_ascension_perk = X, Y, Z }` as a
    zero-factor condition means "offered only if the empire holds ANY of X/Y/Z" -- a genuine
    alternative group, all three members sharing one `group_id`."""
    from pipeline.gate_patterns import classify_weight_gate_condition

    condition = _block("""
    {
        NOR = {
            has_ascension_perk = ap_the_flesh_is_weak
            has_ascension_perk = ap_organo_machine_interfacing
            has_ascension_perk = ap_organo_machine_interfacing_assimilator
        }
    }
    """)
    matches = classify_weight_gate_condition("tech_neuro_quantum_links", condition, 0)
    assert len(matches) == 3
    assert all(m.kind == GATE_KIND_ASCENSION_PERK for m in matches)
    assert all(m.alternative is True for m in matches)
    assert len({m.group_id for m in matches}) == 1
    assert {m.ref_id for m in matches} == {
        "ap_the_flesh_is_weak", "ap_organo_machine_interfacing", "ap_organo_machine_interfacing_assimilator",
    }


def test_weight_condition_group_id_namespace_never_collides_with_potential_gate_alt():
    """`index` disambiguates a technology's own multiple `weight_modifier` entries from each
    other AND from `classify_gates`' own `#gate-alt` namespace -- both a `potential`-derived and a
    weight-derived alternative group on the SAME technology must get distinct group ids."""
    from pipeline.gate_patterns import classify_weight_gate_condition

    potential_block = _block("""
    { potential = { OR = { has_ascension_perk = ap_a has_ascension_perk = ap_b } } }
    """)
    potential_matches = classify_gates("tech_x", potential_block)
    weight_condition = _block("{ NOR = { has_ascension_perk = ap_c has_ascension_perk = ap_d } }")
    weight_matches = classify_weight_gate_condition("tech_x", weight_condition, 0)
    assert {m.group_id for m in potential_matches}.isdisjoint({m.group_id for m in weight_matches})
