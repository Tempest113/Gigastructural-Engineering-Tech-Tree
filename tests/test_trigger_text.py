"""Tests for pipeline.trigger_text -- the shared trigger-condition -> text/category renderer
(HANDOFF.md's previously-flagged gap; also serves P-12.8's weight-modifier condition text)."""

from __future__ import annotations

from pipeline.clausewitz import parse_text
from pipeline.trigger_text import ReasonCategory, categorize_leaf, describe_condition


def _leaf(text: str):
    doc = parse_text(f"tech_x = {{ potential = {{ {text} }} }}\n", path="x.txt")
    assignment = doc.items[0]
    potential = next(item for item in assignment.value.items if item.key_name == "potential")
    return potential.value.items[0]


def _wrapper(text: str):
    doc = parse_text(f"tech_x = {{ potential = {text} }}\n", path="x.txt")
    assignment = doc.items[0]
    potential = next(item for item in assignment.value.items if item.key_name == "potential")
    return potential.value.items[0]


# ---------------------------------------------------------------------------
# describe_condition
# ---------------------------------------------------------------------------


def test_known_axis_leaf_gets_a_phrase():
    assert describe_condition(_leaf("is_nomadic = yes")) == "Nomadic empires"


def test_known_axis_leaf_no_value_gets_negated_phrase():
    assert describe_condition(_leaf("is_nomadic = no")) == "Not: nomadic empires"


def test_has_technology_gets_a_phrase():
    assert describe_condition(_leaf("has_technology = tech_lasers")) == "Requires researching tech_lasers"


def test_has_ascension_perk_gets_a_phrase():
    assert describe_condition(_leaf("has_ascension_perk = ap_colossus")) == "Requires the ap_colossus ascension perk"


def test_unknown_leaf_falls_back_to_raw_text():
    assert describe_condition(_leaf("some_unmapped_trigger = yes")) == "some_unmapped_trigger = yes"


def test_and_wrapper_joins_children():
    node = _wrapper("{ AND = { is_nomadic = yes country_uses_bio_ships = yes } }")
    assert describe_condition(node) == "Nomadic empires and Empires with a biological shipset"


def test_or_wrapper_joins_children():
    node = _wrapper("{ OR = { is_nomadic = yes is_gestalt = yes } }")
    text = describe_condition(node)
    assert " or " in text


def test_not_wrapper_negates():
    node = _wrapper("{ NOT = { is_nomadic = yes } }")
    assert describe_condition(node) == "not Nomadic empires"


def test_case_insensitive_wrapper_handled_same_as_uppercase():
    node = _wrapper("{ not = { is_nomadic = yes } }")
    assert describe_condition(node) == "not Nomadic empires"


# ---------------------------------------------------------------------------
# categorize_leaf -- corpus-derived taxonomy
# ---------------------------------------------------------------------------


def test_crisis_faction_country_flag_is_crisis_or_story():
    assert categorize_leaf(_leaf("has_country_flag = blokkat_laser_possible")) == ReasonCategory.CRISIS_OR_STORY_PROGRESS


def test_generic_progress_suffix_country_flag_is_crisis_or_story():
    assert categorize_leaf(_leaf("has_country_flag = encountered_first_lgate")) == ReasonCategory.CRISIS_OR_STORY_PROGRESS
    assert categorize_leaf(_leaf("has_country_flag = cosmogenesis_aborted")) == ReasonCategory.CRISIS_OR_STORY_PROGRESS


def test_unpatterned_country_flag_is_opaque_country_state():
    assert categorize_leaf(_leaf("has_country_flag = has_arcane_generator")) == ReasonCategory.OPAQUE_COUNTRY_STATE


def test_non_toggle_global_flag_with_story_pattern_is_crisis_or_story():
    assert categorize_leaf(_leaf("has_global_flag = compound_invasion_happened")) == ReasonCategory.CRISIS_OR_STORY_PROGRESS


def test_non_toggle_global_flag_without_story_pattern_is_unclassified():
    assert categorize_leaf(_leaf("has_global_flag = giga_rings_gar")) == ReasonCategory.UNCLASSIFIED


def test_origin_leaves_are_origin_requirement():
    assert categorize_leaf(_leaf("has_origin = origin_void_dwellers")) == ReasonCategory.ORIGIN_REQUIREMENT
    assert categorize_leaf(_leaf("giga_has_frameworld_origin = yes")) == ReasonCategory.ORIGIN_REQUIREMENT
    assert categorize_leaf(_leaf("is_wilderness_empire = yes")) == ReasonCategory.ORIGIN_REQUIREMENT


def test_ethics_and_civics_leaves_are_ethics_or_civic():
    assert categorize_leaf(_leaf("has_ethic = ethic_spiritualist")) == ReasonCategory.ETHICS_OR_CIVIC_REQUIREMENT
    assert categorize_leaf(_leaf("has_valid_civic = civic_natural_design")) == ReasonCategory.ETHICS_OR_CIVIC_REQUIREMENT


def test_has_acot_is_mod_content_requirement():
    assert categorize_leaf(_leaf("has_acot = yes")) == ReasonCategory.MOD_CONTENT_REQUIREMENT


def test_mod_config_toggle_flags_are_mod_configuration_not_unclassified():
    # The real corpus shape (giga_mega_repeatable.txt's template, 50 rendered technologies):
    # both suffixes classify as MOD_CONFIGURATION, distinct from MOD_CONTENT_REQUIREMENT (which
    # is about needing ACOT/AoT content present, not a Gigastructures options-menu toggle).
    assert categorize_leaf(_leaf("has_global_flag = giga_tech_repeatable_foo_capped_r")) == ReasonCategory.MOD_CONFIGURATION
    assert categorize_leaf(_leaf("has_global_flag = giga_tech_repeatable_foo_disabled")) == ReasonCategory.MOD_CONFIGURATION
    assert categorize_leaf(_leaf("has_global_flag = acot_weapons_forbidden")) == ReasonCategory.MOD_CONFIGURATION
    assert categorize_leaf(_leaf("has_global_flag = aot_phanon_content_OFF")) == ReasonCategory.MOD_CONFIGURATION


def test_mod_config_suffix_only_applies_to_has_global_flag_not_has_country_flag():
    # has_country_flag has no mod-config-toggle convention -- a country flag ending in
    # "_capped_r" (hypothetically) would still be real undecidable player state, not a mod
    # setting; only has_global_flag gets this special-cased.
    assert categorize_leaf(_leaf("has_country_flag = something_capped_r")) == ReasonCategory.OPAQUE_COUNTRY_STATE


def test_opaque_scope_and_structural_leaves():
    assert categorize_leaf(_leaf("country_uses_consumer_goods = yes")) == ReasonCategory.OPAQUE_COUNTRY_STATE
    assert categorize_leaf(_leaf("always = no")) == ReasonCategory.OPAQUE_COUNTRY_STATE


def test_completely_unseen_leaf_is_unclassified():
    assert categorize_leaf(_leaf("brand_new_trigger_nobody_has_seen = yes")) == ReasonCategory.UNCLASSIFIED


def test_has_ancrel_is_no_longer_classified_as_crisis_or_story_progress():
    # Corrected (later session): has_ancrel is `host_has_dlc = "Ancient Relics Story Pack"`
    # (vendor/stellaris/common/scripted_triggers/00_scripted_triggers.txt:2678), a DLC-ownership
    # check -- not a relic/precursor questline flag as an earlier, never-verified comment here
    # claimed. It's now resolved directly by pipeline.availability.GROUND_FACT_BOOL and never
    # reaches this categoriser as UNCERTAIN in the real pipeline (see
    # tests/test_availability.py's has_ancrel coverage), so it has no dedicated entry here any
    # more -- categorize_leaf's honest fallback for an unrecognised key is UNCLASSIFIED.
    assert categorize_leaf(_leaf("has_ancrel = yes")) == ReasonCategory.UNCLASSIFIED
    assert categorize_leaf(_leaf("has_ancrel = no")) == ReasonCategory.UNCLASSIFIED


def test_world_forger_and_genetically_ascended_are_ethics_or_civic():
    assert categorize_leaf(_leaf("is_world_forger_empire = yes")) == ReasonCategory.ETHICS_OR_CIVIC_REQUIREMENT
    assert categorize_leaf(_leaf("has_genetically_ascended = yes")) == ReasonCategory.ETHICS_OR_CIVIC_REQUIREMENT


def test_giga_can_use_habitables_is_origin_requirement():
    assert categorize_leaf(_leaf("giga_can_use_habitables = yes")) == ReasonCategory.ORIGIN_REQUIREMENT


def test_variable_referenced_global_flag_stays_unclassified():
    # has_global_flag = @giga_amb_flag -- the value is an unresolved @variable reference, not a
    # plain identifier/string; this evaluator doesn't chase @variable references for flag names,
    # so it correctly stays unclassified rather than being guessed at.
    assert categorize_leaf(_leaf("has_global_flag = @giga_amb_flag")) == ReasonCategory.UNCLASSIFIED
