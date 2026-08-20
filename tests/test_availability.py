"""Tests for pipeline.availability -- D-10/P-13 partial trigger evaluator.

Synthetic fixtures throughout, mirroring tests/test_overwrites.py's split: this file exercises
the evaluation mechanism (three-valued short-circuit logic, the three documented ground-fact
assumptions, has_technology exclusion); tests/test_availability_corpus.py runs the same evaluator
against the real vendored corpus and reports the actual per-profile rates.
"""

from __future__ import annotations

import pytest

from pipeline.clausewitz import parse_text
from pipeline.availability import (
    AVAILABLE,
    CONFIG_GATED,
    LOCKED,
    UNCERTAIN,
    build_d10_diagnostics_section,
    build_missing_lock_reason_overrides,
    build_profile_dependent_diagnostics,
    build_unconditional_diagnostic,
    classify_d10_status,
    evaluate_trigger_block,
    needs_lock_reason_override,
    resolve_lock_reason,
    survey_uncertainty,
)
from pipeline.lock_reason_overrides import LockReasonOverride
from pipeline.trigger_text import ReasonCategory

REGULAR_MECH_SEDENTARY = {"authority": "regular", "shipset": "mechanical", "nomadic": "no"}
HIVE_BIO_NOMADIC = {"authority": "hive_mind", "shipset": "biological", "nomadic": "yes"}
MACHINE_MECH_SEDENTARY = {"authority": "machine_intelligence", "shipset": "mechanical", "nomadic": "no"}


def _block(text: str):
    doc = parse_text(f"tech_x = {{ potential = {text} }}\n", path="x.txt")
    assignment = doc.items[0]
    potential = next(item for item in assignment.value.items if item.key_name == "potential")
    return potential.value


# ---------------------------------------------------------------------------
# No potential block at all
# ---------------------------------------------------------------------------


def test_no_potential_block_is_available():
    result = evaluate_trigger_block(None, REGULAR_MECH_SEDENTARY)
    assert result.state == AVAILABLE
    assert result.reason is None


# ---------------------------------------------------------------------------
# Axis facts
# ---------------------------------------------------------------------------


def test_axis_leaf_true_for_matching_profile():
    block = _block("{ is_nomadic = yes }")
    assert evaluate_trigger_block(block, HIVE_BIO_NOMADIC).state == AVAILABLE


def test_axis_leaf_false_for_non_matching_profile():
    block = _block("{ is_nomadic = yes }")
    result = evaluate_trigger_block(block, REGULAR_MECH_SEDENTARY)
    assert result.state == LOCKED
    assert result.reason == "is_nomadic = yes"


def test_axis_leaf_no_value_flips_polarity():
    block = _block("{ is_nomadic = no }")
    assert evaluate_trigger_block(block, REGULAR_MECH_SEDENTARY).state == AVAILABLE
    assert evaluate_trigger_block(block, HIVE_BIO_NOMADIC).state == LOCKED


def test_shipset_fact_is_country_uses_bio_ships_not_has_biological_ships():
    block = _block("{ country_uses_bio_ships = yes }")
    assert evaluate_trigger_block(block, HIVE_BIO_NOMADIC).state == AVAILABLE
    assert evaluate_trigger_block(block, MACHINE_MECH_SEDENTARY).state == LOCKED


def test_gestalt_covers_hive_and_machine_but_not_regular():
    block = _block("{ is_gestalt = yes }")
    assert evaluate_trigger_block(block, HIVE_BIO_NOMADIC).state == AVAILABLE
    assert evaluate_trigger_block(block, MACHINE_MECH_SEDENTARY).state == AVAILABLE
    assert evaluate_trigger_block(block, REGULAR_MECH_SEDENTARY).state == LOCKED


def test_not_equals_operator_negates_axis_check():
    block = _block("{ is_nomadic != yes }")
    assert evaluate_trigger_block(block, REGULAR_MECH_SEDENTARY).state == AVAILABLE
    assert evaluate_trigger_block(block, HIVE_BIO_NOMADIC).state == LOCKED


# ---------------------------------------------------------------------------
# The three documented ground-fact assumptions
# ---------------------------------------------------------------------------


def test_mod_config_forbidden_flag_resolves_unset_as_config_gated():
    # A bare (un-negated) mod-config-toggle flag being the reason a technology's potential
    # resolves FALSE is a CONFIG_GATED result, not LOCKED (D-10, spec/decisions.md) -- nothing
    # about the empire is stopping the player, a game option is. The flag still resolves to its
    # assumed-unset default (False) as before; only the resulting STATE label changed.
    block = _block("{ has_global_flag = acot_weapons_forbidden }")
    result = evaluate_trigger_block(block, REGULAR_MECH_SEDENTARY)
    assert result.state == CONFIG_GATED
    assert result.category == ReasonCategory.MOD_CONFIGURATION


def test_mod_config_off_flag_resolves_unset():
    block = _block("{ NOT = { has_global_flag = aot_phanon_content_OFF } }")
    result = evaluate_trigger_block(block, REGULAR_MECH_SEDENTARY)
    assert result.state == AVAILABLE  # flag unset -> NOT(false) -> true


def test_capped_r_flag_resolves_config_gated_not_locked():
    # The real corpus shape (giga_mega_repeatable.txt's template, 50 rendered technologies):
    # not-disabled AND capped_r. Confirmed by the user: no core Gigastructures preset sets a cap
    # to the "1+r" mode this flag names, so it's unset (False) by default -- the technology is
    # genuinely unavailable in a default game, but for a mod-configuration reason, not an
    # empire-state one.
    block = _block("{ NOT = { has_global_flag = giga_tech_repeatable_foo_disabled } "
                    "has_global_flag = giga_tech_repeatable_foo_capped_r }")
    result = evaluate_trigger_block(block, REGULAR_MECH_SEDENTARY)
    assert result.state == CONFIG_GATED
    assert result.category == ReasonCategory.MOD_CONFIGURATION
    assert "capped_r" in result.reason


def test_non_toggle_global_flag_is_undecidable():
    # herculean_built: real corpus mid-game player-state flag (HANDOFF.md's CHECK 2), matches
    # neither the mod-config-toggle suffix set nor Item 2's story-progression pattern.
    block = _block("{ has_global_flag = herculean_built }")
    result = evaluate_trigger_block(block, REGULAR_MECH_SEDENTARY)
    assert result.state == UNCERTAIN
    assert result.reason == "has_global_flag = herculean_built"


def test_story_progression_pattern_flags_resolve_true():
    # Item 2 ("commit + close the loop" follow-up session): flags matching
    # pipeline.trigger_text.looks_like_story_progress resolve TRUE, same treatment as the
    # user-approved colossus_project precedent -- confirmed by direct inspection that every
    # sampled real setting site is an is_triggered_only country event with no empire-type
    # restriction.
    block = _block("{ has_country_flag = blokkat_laser_possible }")
    assert evaluate_trigger_block(block, REGULAR_MECH_SEDENTARY).state == AVAILABLE

    block2 = _block("{ has_global_flag = ehof_code_3_complete }")
    assert evaluate_trigger_block(block2, REGULAR_MECH_SEDENTARY).state == AVAILABLE


def test_vanilla_lgate_flags_excluded_from_story_progression_resolution():
    # l_cluster_opened / encountered_first_lgate match the naming pattern (`_opened` suffix,
    # `encountered_` prefix) but are vanilla Stellaris storyline flags whose setting sites live in
    # vanilla's events/decisions -- not vendored, so unlike every Gigastructures match, there is no
    # corpus text to verify them against. Deliberately excluded (PROGRESSION_PATTERN_EXCLUDED_FLAGS),
    # stay UNCERTAIN.
    block = _block("{ has_global_flag = l_cluster_opened }")
    result = evaluate_trigger_block(block, REGULAR_MECH_SEDENTARY)
    assert result.state == UNCERTAIN
    assert result.category == ReasonCategory.CRISIS_OR_STORY_PROGRESS

    block2 = _block("{ has_country_flag = encountered_first_lgate }")
    result2 = evaluate_trigger_block(block2, REGULAR_MECH_SEDENTARY)
    assert result2.state == UNCERTAIN
    assert result2.category == ReasonCategory.CRISIS_OR_STORY_PROGRESS


def test_dlc_assumed_owned():
    block = _block("{ has_dlc = \"Utopia\" }")
    assert evaluate_trigger_block(block, REGULAR_MECH_SEDENTARY).state == AVAILABLE


def test_has_ancrel_resolves_true_as_a_dlc_ground_fact():
    # has_ancrel is `host_has_dlc = "Ancient Relics Story Pack"` (vendor/stellaris/common/
    # scripted_triggers/00_scripted_triggers.txt:2678) -- a DLC-ownership check, not a
    # Gigastructures relic-questline flag as a previous, never-verified comment claimed. See
    # CLAUDE.md's "Availability evaluator" defect-class writeup.
    block = _block("{ has_ancrel = yes }")
    assert evaluate_trigger_block(block, REGULAR_MECH_SEDENTARY).state == AVAILABLE
    block2 = _block("{ has_ancrel = no }")
    assert evaluate_trigger_block(block2, REGULAR_MECH_SEDENTARY).state == LOCKED


def test_not_fallen_empire_ground_fact():
    block = _block("{ is_fallen_empire = yes }")
    result = evaluate_trigger_block(block, REGULAR_MECH_SEDENTARY)
    assert result.state == LOCKED  # ground fact: never a fallen empire, so "= yes" fails

    block2 = _block("{ is_fallen_empire = no }")
    assert evaluate_trigger_block(block2, REGULAR_MECH_SEDENTARY).state == AVAILABLE


# ---------------------------------------------------------------------------
# has_technology exclusion
# ---------------------------------------------------------------------------


def test_has_technology_alone_does_not_make_potential_uncertain():
    block = _block("{ has_technology = tech_lasers }")
    result = evaluate_trigger_block(block, REGULAR_MECH_SEDENTARY)
    assert result.state == AVAILABLE  # excluded leaf -> no trigger-level constraint at all


def test_has_technology_does_not_suppress_a_real_sibling_condition():
    block = _block("{ has_technology = tech_lasers is_nomadic = yes }")
    result = evaluate_trigger_block(block, REGULAR_MECH_SEDENTARY)
    assert result.state == LOCKED
    assert result.reason == "is_nomadic = yes"


# ---------------------------------------------------------------------------
# Item 3, "path to zero uncertain" follow-up: ethics/civic/origin display gates
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("leaf_key", [
    "has_origin", "giga_has_frameworld_origin", "is_wilderness_empire", "is_void_dweller_empire",
    "has_void_dweller_origin", "is_giga_one_planet_origin", "has_ethic", "has_valid_civic",
    "has_civic", "is_fanatic_spiritualist", "is_fanatic_pacifist", "is_spiritualist",
    "is_natural_design_empire", "is_beastmasters_empire", "is_world_forger_empire", "is_megacorp",
    "is_individual_machine", "has_genetically_ascended", "is_infernal_empire",
    "can_research_technology",
])
def test_ethics_civic_origin_leaf_alone_does_not_make_potential_uncertain(leaf_key):
    block = _block(f"{{ {leaf_key} = some_value }}")
    result = evaluate_trigger_block(block, REGULAR_MECH_SEDENTARY)
    assert result.state == AVAILABLE  # excluded leaf (display gate) -> no trigger-level constraint


def test_ethics_civic_origin_leaf_does_not_suppress_a_real_sibling_condition():
    block = _block("{ has_origin = origin_wilderness is_nomadic = yes }")
    result = evaluate_trigger_block(block, REGULAR_MECH_SEDENTARY)
    assert result.state == LOCKED
    assert result.reason == "is_nomadic = yes"


def test_has_technology_does_not_manufacture_false_certainty_around_uncertain_sibling():
    block = _block("{ has_technology = tech_lasers has_country_flag = herculean_built }")
    result = evaluate_trigger_block(block, REGULAR_MECH_SEDENTARY)
    assert result.state == UNCERTAIN
    assert result.reason == "has_country_flag = herculean_built"


def test_has_ascension_perk_alone_does_not_make_potential_uncertain():
    # D-6/P-1: ascension perks are gates, not profile facts -- a perk check here is a P-3 gate
    # display concern, not a trigger this evaluator resolves.
    block = _block("{ has_ascension_perk = ap_colossus }")
    result = evaluate_trigger_block(block, REGULAR_MECH_SEDENTARY)
    assert result.state == AVAILABLE


# ---------------------------------------------------------------------------
# Boolean structure / short-circuiting -- the mechanism the whole metric split rests on
# ---------------------------------------------------------------------------


def test_and_short_circuits_false_over_uncertain_sibling():
    # A false axis branch under AND makes the whole block false regardless of an undecidable
    # sibling -- this is the exact mechanism distinguishing profile-dependent from unconditional.
    block = _block("{ AND = { is_nomadic = yes has_country_flag = mystery_flag } }")
    result = evaluate_trigger_block(block, REGULAR_MECH_SEDENTARY)  # not nomadic -> false branch
    assert result.state == LOCKED
    assert result.reason == "is_nomadic = yes"


def test_and_is_uncertain_when_no_branch_is_false():
    block = _block("{ AND = { is_nomadic = yes has_country_flag = mystery_flag } }")
    result = evaluate_trigger_block(block, HIVE_BIO_NOMADIC)  # nomadic -> true branch, leaves uncertain sibling
    assert result.state == UNCERTAIN
    assert result.reason == "has_country_flag = mystery_flag"


def test_or_short_circuits_true_over_uncertain_sibling():
    block = _block("{ OR = { is_nomadic = yes has_country_flag = mystery_flag } }")
    result = evaluate_trigger_block(block, HIVE_BIO_NOMADIC)  # nomadic -> true branch short-circuits OR
    assert result.state == AVAILABLE


def test_or_is_uncertain_when_no_branch_is_true():
    block = _block("{ OR = { is_nomadic = yes has_country_flag = mystery_flag } }")
    result = evaluate_trigger_block(block, REGULAR_MECH_SEDENTARY)  # not nomadic -> false branch, leaves uncertain
    assert result.state == UNCERTAIN
    assert result.reason == "has_country_flag = mystery_flag"


def test_nor_is_true_only_when_every_branch_false():
    block = _block("{ NOR = { is_nomadic = yes is_gestalt = yes } }")
    assert evaluate_trigger_block(block, REGULAR_MECH_SEDENTARY).state == AVAILABLE  # both false
    assert evaluate_trigger_block(block, HIVE_BIO_NOMADIC).state == LOCKED  # both true -> NOR false


def test_not_flips_true_to_false_and_false_to_true():
    block = _block("{ NOT = { is_nomadic = yes } }")
    assert evaluate_trigger_block(block, HIVE_BIO_NOMADIC).state == LOCKED
    assert evaluate_trigger_block(block, REGULAR_MECH_SEDENTARY).state == AVAILABLE


def test_not_of_uncertain_is_still_uncertain():
    block = _block("{ NOT = { has_country_flag = mystery_flag } }")
    result = evaluate_trigger_block(block, REGULAR_MECH_SEDENTARY)
    assert result.state == UNCERTAIN


def test_top_level_implicit_and_over_multiple_leaves():
    block = _block("{ is_nomadic = yes is_gestalt = yes }")
    # regular + non-nomadic: both leaves false -> locked on the first one evaluated
    result = evaluate_trigger_block(block, REGULAR_MECH_SEDENTARY)
    assert result.state == LOCKED


def test_boolean_wrappers_are_case_insensitive():
    # Confirmed real corpus shape: both `NOT = { ... }` and `not = { ... }` occur for the same
    # semantics (e.g. giga_02_society.txt). A wrapper matched only in uppercase would silently
    # treat the lowercase form as an unrecognised leaf instead of a combinator.
    block = _block("{ not = { is_nomadic = yes } }")
    assert evaluate_trigger_block(block, HIVE_BIO_NOMADIC).state == LOCKED
    assert evaluate_trigger_block(block, REGULAR_MECH_SEDENTARY).state == AVAILABLE

    block2 = _block("{ or = { is_nomadic = yes is_gestalt = yes } }")
    assert evaluate_trigger_block(block2, HIVE_BIO_NOMADIC).state == AVAILABLE
    assert evaluate_trigger_block(block2, REGULAR_MECH_SEDENTARY).state == LOCKED

    block3 = _block("{ and = { is_nomadic = yes is_gestalt = yes } }")
    assert evaluate_trigger_block(block3, HIVE_BIO_NOMADIC).state == AVAILABLE
    assert evaluate_trigger_block(block3, REGULAR_MECH_SEDENTARY).state == LOCKED

    block4 = _block("{ nor = { is_nomadic = yes is_gestalt = yes } }")
    assert evaluate_trigger_block(block4, HIVE_BIO_NOMADIC).state == LOCKED
    assert evaluate_trigger_block(block4, REGULAR_MECH_SEDENTARY).state == AVAILABLE


def test_nested_or_inside_and():
    block = _block("{ AND = { OR = { is_nomadic = yes is_gestalt = yes } country_uses_bio_ships = yes } }")
    assert evaluate_trigger_block(block, HIVE_BIO_NOMADIC).state == AVAILABLE
    assert evaluate_trigger_block(block, MACHINE_MECH_SEDENTARY).state == LOCKED  # bio_ships branch fails


# ---------------------------------------------------------------------------
# Unrecognised leaves: undecidable by default, never assumed either way
# ---------------------------------------------------------------------------


def test_unrecognised_leaf_is_uncertain_not_assumed():
    block = _block("{ is_ai_empire = yes }")
    result = evaluate_trigger_block(block, REGULAR_MECH_SEDENTARY)
    assert result.state == UNCERTAIN


# ---------------------------------------------------------------------------
# survey_uncertainty: the (a)/(b) metric split
# ---------------------------------------------------------------------------


def _profiles_2x2():
    return [
        {"authority": "regular", "shipset": "mechanical", "nomadic": "no"},
        {"authority": "regular", "shipset": "mechanical", "nomadic": "yes"},
    ]


def test_survey_splits_unconditional_from_profile_dependent():
    profiles = _profiles_2x2()
    technologies = {
        "tech_always_uncertain": _block("{ has_country_flag = mystery }"),  # uncertain for every profile
        "tech_sometimes_uncertain": _block(
            "{ AND = { is_nomadic = yes has_country_flag = mystery } }"
        ),  # false for non-nomadic, uncertain for nomadic
        "tech_always_available": _block("{ }"),
    }
    survey = survey_uncertainty(technologies, profiles)
    assert survey.unconditional_uncertain == ["tech_always_uncertain"]
    # index 1 is the nomadic profile in _profiles_2x2()
    assert survey.profile_dependent_uncertain_by_profile_index[1] == ["tech_sometimes_uncertain"]
    assert survey.profile_dependent_uncertain_by_profile_index[0] == []
    assert survey.unconditional_rate() == pytest.approx(1 / 3)
    assert survey.profile_dependent_rate(1) == pytest.approx(1 / 3)
    assert survey.profile_dependent_rate(0) == 0.0


def test_survey_records_category_for_unconditional_technologies():
    profiles = _profiles_2x2()
    technologies = {
        # l_cluster_opened, not blokkat_laser_possible: Item 2 now resolves blokkat_laser_possible
        # TRUE, so it can no longer illustrate an unconditionally-UNCERTAIN crisis/story-progress
        # technology. l_cluster_opened is deliberately excluded from that resolution (vanilla
        # L-Gate flag, see test_vanilla_lgate_flags_excluded_from_story_progression_resolution).
        "tech_crisis_locked": _block("{ has_global_flag = l_cluster_opened }"),
        "tech_opaque_locked": _block("{ has_country_flag = has_arcane_generator }"),
    }
    survey = survey_uncertainty(technologies, profiles)
    assert survey.category_distribution() == {
        ReasonCategory.CRISIS_OR_STORY_PROGRESS: 1,
        ReasonCategory.OPAQUE_COUNTRY_STATE: 1,
    }


# ---------------------------------------------------------------------------
# D-10 threshold classification and diagnostics
# ---------------------------------------------------------------------------


def test_classify_d10_status_boundaries():
    assert classify_d10_status(0.0) == "ok"
    assert classify_d10_status(0.03) == "ok"  # exactly at warn threshold: not yet crossed
    assert classify_d10_status(0.031) == "warn"
    assert classify_d10_status(0.10) == "warn"  # exactly at ceiling: not yet a failure
    assert classify_d10_status(0.101) == "fail"


def _two_profile_and_gated_technologies(count: int, uncertain_count: int) -> dict:
    # AND(is_nomadic = yes, has_country_flag = mystery): for the nomadic profile (index 1),
    # the axis branch is TRUE, leaving the block stuck on the undecidable sibling -> UNCERTAIN.
    # For the non-nomadic profile (index 0), the axis branch is FALSE -> definite LOCKED. This is
    # genuinely profile-dependent uncertainty, not unconditional (only one of the two profiles is
    # ever left uncertain), matching the mechanism the whole D-10 split rests on.
    technologies = {f"tech_{i}": None for i in range(count)}
    for i in range(uncertain_count):
        technologies[f"tech_{i}"] = _block("{ AND = { is_nomadic = yes has_country_flag = mystery } }")
    return technologies


def test_warn_actually_fires_at_a_real_measured_rate():
    # Regression anchor for the real evaluator's measured worst-case profile-dependent rate
    # (~3.37%-3.70% across recent runs, always > the 3% warn threshold) -- a threshold that
    # stays silent on a real breach is worse than none, so this is asserted directly rather than
    # only eyeballed from a printed test log.
    profiles = _profiles_2x2()
    # 35/1000 = 3.5%, comfortably matches the measured real-corpus order of magnitude.
    technologies = _two_profile_and_gated_technologies(1000, 35)
    survey = survey_uncertainty(technologies, profiles)
    diagnostics = build_profile_dependent_diagnostics(survey)
    assert diagnostics[1].rate == pytest.approx(0.035)  # index 1: the nomadic profile
    assert diagnostics[1].status == "warn"
    assert diagnostics[0].rate == 0.0
    assert diagnostics[0].status == "ok"


def test_fail_status_when_worst_profile_exceeds_ceiling():
    profiles = _profiles_2x2()
    technologies = _two_profile_and_gated_technologies(100, 15)  # 15% > 10% ceiling
    survey = survey_uncertainty(technologies, profiles)
    diagnostics = build_profile_dependent_diagnostics(survey)
    assert diagnostics[1].status == "fail"


def test_ratchet_flags_regression_even_under_the_ceiling():
    profiles = _profiles_2x2()
    technologies = _two_profile_and_gated_technologies(100, 4)  # 4% -- under the ceiling, still a regression
    survey = survey_uncertainty(technologies, profiles)
    diagnostics = build_profile_dependent_diagnostics(survey, previous_rates={1: 0.01})
    assert diagnostics[1].status == "warn"
    assert diagnostics[1].regressed is True


def test_unconditional_diagnostic_has_no_ceiling_status_but_has_a_ratchet():
    profiles = _profiles_2x2()
    technologies = {
        "tech_a": _block("{ has_country_flag = mystery }"),
        "tech_b": None,
    }
    survey = survey_uncertainty(technologies, profiles)
    diagnostic = build_unconditional_diagnostic(survey, previous_count=0)
    assert diagnostic.count == 1
    assert diagnostic.regressed is True
    # No `status` field at all -- unconditional uncertainty is never subject to D-10's ceiling.
    assert not hasattr(diagnostic, "status")


def test_phrased_locked_leaf_does_not_need_an_override():
    block = _block("{ is_nomadic = yes }")
    result = evaluate_trigger_block(block, REGULAR_MECH_SEDENTARY)
    assert result.state == LOCKED
    assert needs_lock_reason_override(result) is False
    reason, needs_warning = resolve_lock_reason("tech_x", result, {})
    assert needs_warning is False
    assert reason == result.description


def test_unphrased_locked_leaf_needs_an_override_when_none_provided():
    # has_shroud_dlc has no dedicated phrase in pipeline.trigger_text -- a `= no` check against
    # the all-DLC-owned ground fact resolves LOCKED with only the raw trigger text available.
    block = _block("{ has_shroud_dlc = no }")
    result = evaluate_trigger_block(block, REGULAR_MECH_SEDENTARY)
    assert result.state == LOCKED
    assert needs_lock_reason_override(result) is True

    reason, needs_warning = resolve_lock_reason("tech_x", result, {})
    assert needs_warning is True
    assert reason == "has_shroud_dlc = no"


def test_unphrased_locked_leaf_uses_the_override_text_when_provided():
    block = _block("{ has_shroud_dlc = no }")
    result = evaluate_trigger_block(block, REGULAR_MECH_SEDENTARY)
    override = LockReasonOverride(
        technology_key="tech_x", reason_text="Unavailable: incompatible with Shadows of the Shroud",
        justification="test", line=1,
    )
    reason, needs_warning = resolve_lock_reason("tech_x", result, {"tech_x": override})
    assert needs_warning is False
    assert reason == "Unavailable: incompatible with Shadows of the Shroud"


def test_build_missing_lock_reason_overrides_flags_only_unphrased_and_unoverridden():
    phrased = evaluate_trigger_block(_block("{ is_nomadic = yes }"), REGULAR_MECH_SEDENTARY)
    unphrased_no_override = evaluate_trigger_block(_block("{ has_shroud_dlc = no }"), REGULAR_MECH_SEDENTARY)
    unphrased_with_override = evaluate_trigger_block(_block("{ has_paragon_dlc = no }"), REGULAR_MECH_SEDENTARY)
    available = evaluate_trigger_block(None, REGULAR_MECH_SEDENTARY)

    locked_results = {
        "tech_phrased": phrased,
        "tech_unphrased_missing": unphrased_no_override,
        "tech_unphrased_covered": unphrased_with_override,
        "tech_available": available,
    }
    override = LockReasonOverride(
        technology_key="tech_unphrased_covered", reason_text="covered", justification="test", line=1
    )
    missing = build_missing_lock_reason_overrides(locked_results, {"tech_unphrased_covered": override})
    assert missing == ["tech_unphrased_missing"]


def test_build_d10_diagnostics_section_matches_schema_shape():
    profiles = _profiles_2x2()
    technologies = {
        "tech_a": _block("{ AND = { is_nomadic = yes has_country_flag = mystery } }"),
        "tech_b": _block("{ has_global_flag = l_cluster_opened }"),
    }
    survey = survey_uncertainty(technologies, profiles)
    section = build_d10_diagnostics_section(survey, profiles)

    assert len(section["profileDependentUncertainty"]) == 2
    for entry in section["profileDependentUncertainty"]:
        assert set(entry) == {"profile", "rate", "previousRate", "status"}

    unconditional = section["unconditionalUncertainty"]
    assert set(unconditional) == {"count", "previousCount", "rate", "previousRate", "categoryDistribution"}
    assert unconditional["categoryDistribution"] == [
        {"category": "crisis_or_story_progress", "count": 1}
    ]
