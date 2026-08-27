"""D-10 real per-profile rates, computed against the vendored corpus over the EXACT P-16
rendered-node set (`pipeline.rendering_scope`, 980 technologies) -- Task 2's "then compute the
real per-profile rates and report them against the projections" (CLAUDE.md's "Availability
evaluator" section), corrected in Task 3 to use the exact closure instead of the earlier
Vanilla+Gigastructures-only 973-node approximation.

**Corrected (Stage 2 cleanup session) to load `inline_script`-EXPANDED technology documents, not
raw ones.** The previous version of this file parsed `common/technology` directly with no
expansion, which silently treats all 50 `giga_tech_repeatable_*_cap` technologies as having NO
`potential` block at all -- their real `potential` field, like their `tier` field (P-2's
tier-source audit), only exists after `inline_script` expansion (`giga_mega_repeatable.txt`'s
template). Unexpanded, those 50 default to unconditionally AVAILABLE regardless of their real
gating condition, which undercounted `unconditionalUncertainty` by exactly 50: expanded-block
evaluation initially measured **259/980 (26.4%)**.

**Corrected again (giga_mega_repeatable review session): those same 50 don't belong in
`unconditionalUncertainty` at all.** The template's `potential` is
`NOT{has_global_flag=$name$_disabled} AND has_global_flag=$name$_capped_r` -- both are
mod-configuration toggles (`pipeline.trigger_text.MOD_CONFIG_TOGGLE_SUFFIXES`), not undecidable
game/story state: confirmed by the user that no core Gigastructures preset sets a cap to the
"1+r" mode `_capped_r` names, so the flag is unset by default, and the technology's `potential`
resolves DEFINITIVELY to FALSE, not UNKNOWN. These 50 are genuinely unavailable in a default
game, for a fully known reason -- `CONFIG_GATED`, D-10's new fourth state (spec/decisions.md),
never `UNCERTAIN`. Real, final figure: **209/980 (21.33%)** -- see
`test_repeatable_cap_group_evaluated_with_expanded_gating_conditions_present` below for the
permanent regression guard (now checking CONFIG_GATED, not unconditional-uncertain membership).
**209 is the same number the pre-Stage-2-cleanup-session (raw-block) code reported, by
coincidence, not by the same reasoning** -- that number was wrong for being computed from data
that skipped these 50 nodes entirely; this number is right for evaluating all 980 correctly and
finding the same 50 belong in a different, newly-introduced state instead of either bucket. See
CLAUDE.md's "Availability evaluator" section for the full writeup and the defect-class note this
joined (tier resolution, `is_repeatable`, and this measurement have each independently produced a
plausible wrong answer from reading `giga_tech_repeatable_*`-family data by the wrong route).

Skipped when vendor/ isn't populated, same posture as tests/test_overwrites_corpus.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.availability import (
    CONFIG_GATED,
    LOCKED,
    build_d10_diagnostics_section,
    build_missing_lock_reason_overrides,
    classify_d10_status,
    evaluate_trigger_block,
    set_perk_potentials,
    survey_uncertainty,
)
from pipeline.clausewitz import Assignment, Block, parse_file
from pipeline.dataset_schema import validate_diagnostics
from pipeline.dataset_schema.empire_profile import all_profiles_in_canonical_order
from pipeline.inline_scripts import collect_scripts, expand_document
from pipeline.lock_reason_overrides import load_overrides as load_lock_reason_overrides
from pipeline.overwrite_overrides import load_overrides
from pipeline.overwrites import collect_technology_definitions, resolve_technology_overwrites
from pipeline.rendering_scope import rendered_technology_keys
from pipeline.scripted_triggers import expand_scripted_triggers, load_scripted_trigger_catalog
from pipeline.trigger_text import ReasonCategory
from pipeline.variables import build_variable_table

REPO_ROOT = Path(__file__).resolve().parent.parent
VENDOR_ROOT = REPO_ROOT / "vendor"

_SOURCES_IN_LOAD_ORDER = [
    ("Vanilla", VENDOR_ROOT / "stellaris"),
    ("Gigastructural Engineering", VENDOR_ROOT / "mods" / "gigastructures"),
    ("ACOT", VENDOR_ROOT / "mods" / "acot"),
    ("AoT", VENDOR_ROOT / "mods" / "aot"),
]

_vendor_populated = VENDOR_ROOT.is_dir() and any(root.is_dir() for _, root in _SOURCES_IN_LOAD_ORDER)

pytestmark = pytest.mark.skipif(not _vendor_populated, reason="vendor/ not populated locally")


def _script_entries():
    entries = []
    for name, root in _SOURCES_IN_LOAD_ORDER:
        base = root / "common" / "inline_scripts"
        if not base.is_dir():
            continue
        for f in sorted(base.rglob("*.txt")):
            rel = f.relative_to(base).with_suffix("")
            entries.append((str(rel).replace("\\", "/"), str(f), f.read_text(encoding="utf-8")))
    return entries


def _load_technology_documents(scripts):
    return [
        (name, [expand_document(parse_file(f), scripts)[0] for f in sorted((root / "common" / "technology").glob("*.txt"))])
        for name, root in _SOURCES_IN_LOAD_ORDER
        if (root / "common" / "technology").is_dir()
    ]


def _load_variable_documents(scripts):
    return [
        (name, [expand_document(parse_file(f), scripts)[0] for f in sorted((root / "common" / "scripted_variables").glob("*.txt"))])
        for name, root in _SOURCES_IN_LOAD_ORDER
        if (root / "common" / "scripted_variables").is_dir()
    ]


def _potential_block(block: Block) -> Block | None:
    assignment = None
    for item in block.items:
        if isinstance(item, Assignment) and item.key_name == "potential":
            assignment = item
    if assignment is None or not isinstance(assignment.value, Block):
        return None
    return assignment.value


@pytest.fixture(scope="module")
def rendered_potentials():
    scripts = collect_scripts(_script_entries())
    tech_docs = _load_technology_documents(scripts)
    var_docs = _load_variable_documents(scripts)
    all_docs = [doc for _, docs in tech_docs for doc in docs] + [doc for _, docs in var_docs for doc in docs]
    variable_table = build_variable_table(all_docs)

    technology_history = collect_technology_definitions(tech_docs)
    overrides = load_overrides()
    records = resolve_technology_overwrites(technology_history, variable_table, overrides)
    rendered_keys = rendered_technology_keys(technology_history)

    result: dict[str, Block | None] = {}
    for key, occurrences in technology_history.items():
        if key not in rendered_keys:
            continue
        winner = occurrences[-1]
        result[key] = _potential_block(winner.block)
    assert set(result) <= set(records)  # sanity: every winner we kept has a resolved record
    return result


def _load_ascension_perk_documents(scripts):
    return [
        (name, [expand_document(parse_file(f), scripts)[0] for f in sorted((root / "common" / "ascension_perks").glob("*.txt"))])
        for name, root in _SOURCES_IN_LOAD_ORDER
        if (root / "common" / "ascension_perks").is_dir()
    ]


@pytest.fixture(scope="module", autouse=True)
def _registered_perk_potentials():
    """Item 2 (later session): `_evaluate_leaf`'s `has_ascension_perk` handling consults a
    module-level registry (`pipeline.availability.set_perk_potentials`) that only
    `pipeline.dataset_emit.build_context` populates in real production use -- this fixture mirrors
    that registration here too, autouse, so THIS file's own survey (`expanded_rendered_potentials`,
    built independently of `build_context`) reflects the SAME real behaviour rather than silently
    under-counting perk-driven resolutions. Without this, `has_ascension_perk` leaves here would
    always be EXCLUDED regardless of real axis restrictions -- exactly the "hidden global state
    depends on which fixture happened to run first" risk this project's own methodology warns
    against; making the registration explicit and unconditional here closes it, rather than
    leaving this test file's result order-dependent on some OTHER test module's `ctx` fixture
    having already called `set_perk_potentials` first."""
    scripts = collect_scripts(_script_entries())
    catalog = load_scripted_trigger_catalog(VENDOR_ROOT, scripts, _SOURCES_IN_LOAD_ORDER)
    perk_docs = _load_ascension_perk_documents(scripts)
    perk_history = collect_technology_definitions(perk_docs)
    perk_potentials = {
        key: expand_scripted_triggers(_potential_block(occurrences[-1].block), catalog)
        for key, occurrences in perk_history.items()
    }
    set_perk_potentials(perk_potentials)
    yield
    set_perk_potentials({})


@pytest.fixture(scope="module")
def expanded_rendered_potentials(rendered_potentials):
    """`rendered_potentials`, `pipeline.scripted_triggers`-expanded -- the same transform
    `pipeline.dataset_emit.build_context` applies via `ctx.expanded_potentials` (Item 2, "path to
    zero uncertain" follow-up session). Kept as a SEPARATE fixture from `rendered_potentials`
    itself (rather than expanding in place) so tests that specifically want the raw, unexpanded
    baseline (e.g. `test_repeatable_cap_group_evaluated_with_expanded_gating_conditions_present`,
    about `inline_script` expansion, an unrelated mechanism) are unaffected."""
    scripts = collect_scripts(_script_entries())
    catalog = load_scripted_trigger_catalog(VENDOR_ROOT, scripts, _SOURCES_IN_LOAD_ORDER)
    return {key: expand_scripted_triggers(block, catalog) for key, block in rendered_potentials.items()}


def test_rendered_scope_is_exactly_973(rendered_potentials):
    # D-18 (spec/decisions.md): 980 -> 977, the depth-1 ACOT/AoT closure.
    # Item 2c (user domain call, later session): 977 -> 973, 4 permanently-disabled technologies
    # (`potential = { always = no }`) excluded entirely.
    assert len(rendered_potentials) == 973


def test_real_rates_against_projections(expanded_rendered_potentials):
    profiles = all_profiles_in_canonical_order()
    survey = survey_uncertainty(expanded_rendered_potentials, profiles)

    total = survey.total_technologies
    assert total == 973  # this IS the rendered denominator the spec now requires (Task 1's D-10 split); D-18: 980 -> 977; Item 2c: 977 -> 973

    unconditional_rate = survey.unconditional_rate()
    worst_dependent_rate = survey.worst_profile_dependent_rate()

    print(f"\n--- D-10 real evaluator run ({total} rendered technologies, exact P-16 closure -- BOTH")
    print(f"    metrics below share this denominator, per Task 1's D-10 split) ---")
    print(f"unconditional uncertain: {len(survey.unconditional_uncertain)}/{total} ({unconditional_rate:.2%})")
    print(f"worst-case profile-dependent uncertain rate: {worst_dependent_rate:.2%} (over {total} rendered nodes)")
    for i in sorted(survey.profile_dependent_uncertain_by_profile_index):
        count = len(survey.profile_dependent_uncertain_by_profile_index[i])
        print(f"  profile {i} ({profiles[i]}): {count}/{total} ({count / total:.2%})")

    print("\n--- unconditional-uncertain category distribution ---")
    distribution = survey.category_distribution()
    for category, count in sorted(distribution.items(), key=lambda kv: -kv[1]):
        print(f"  {category.value}: {count} ({count / len(survey.unconditional_uncertain):.1%} of unconditional)")

    # HANDOFF.md's upper-bound projection, same 980-rendered-node denominator: 52 profile-dependent
    # (5.3%), 211 unconditional (21.53%). Regression bounds below, not exact equality -- the
    # projection was a coarser, hand-classified methodology; the real evaluator's short-circuit
    # logic is expected to land at or below the profile-dependent upper bound (it counted "could
    # vary by profile"), and in the same order of magnitude for the unconditional figure.
    assert worst_dependent_rate <= 0.10  # D-10 hard ceiling, worst profile
    assert worst_dependent_rate < 0.03  # comfortably back under the 3% warn threshold, see below

    # Corrected three times, see this module's docstring: 209 -> 259 (raw vs. expanded blocks) ->
    # 209 again (the 50 giga_tech_repeatable_*_cap nodes are CONFIG_GATED, not UNCERTAIN -- they
    # resolve definitively, they just aren't empire-state LOCKED either). Item 2's four resolution
    # rules (later session) then moved 209 -> 205: 4 fewer purely from Item 2c's denominator
    # shrink (the 4 excluded always-no technologies were themselves unconditionally uncertain, so
    # removing them removes them from this count 1:1) -- confirmed exactly, not assumed.
    # **205 -> 183, a later session (Item 1 of the "path to zero uncertain" follow-up): the
    # has_ancrel fix.** has_ancrel is `host_has_dlc = "Ancient Relics Story Pack"` (vendor/
    # stellaris/common/scripted_triggers/00_scripted_triggers.txt:2678), not a Gigastructures
    # relic-questline flag as a previous, never-verified pipeline.trigger_text comment claimed --
    # see CLAUDE.md's "Availability evaluator" defect-class writeup. Resolving it via
    # pipeline.availability.GROUND_FACT_BOOL (the same DLC-ownership rule as every other named
    # wrapper) moves 22 technologies (the tech_archeo_* family) from UNCERTAIN to AVAILABLE and 1
    # (tech_archeology_lab, `has_ancrel = no`) to LOCKED -- 23 technologies affected, 205 - 23 =
    # 182, but the real figure is 183: one further technology's MODE category (not its
    # uncertain/not-uncertain status) shifted from crisis_or_story_progress to origin_requirement
    # once has_ancrel's own contributed UNKNOWN stopped competing for "first responsible leaf" in
    # that technology's OR/AND combination -- a real, correct side effect of removing one UNKNOWN
    # branch, not a second bug.
    # **183 -> 176, the SAME session's Item 2 (`pipeline.scripted_triggers` general expansion).**
    # This fixture now runs `expand_scripted_triggers` first (matching
    # `pipeline.dataset_emit.build_context`'s real `ctx.expanded_potentials`, not the raw,
    # unexpanded `rendered_potentials` this test used before). 7 technologies' unconditional
    # uncertainty resolves once real scripted-trigger bodies (`is_wilderness_empire`,
    # `giga_can_use_habitables`, ...) let Kleene short-circuiting rule out axis-inconsistent
    # profiles, at the cost of a temporarily-higher worst PROFILE-DEPENDENT rate (the same 7, and
    # others, become genuinely profile-dependent instead of staying unconditionally stuck).
    # **176 -> 107, the SAME session's Item 3 (ethics/civic/origin as display gates).** 19 leaf
    # keys added to `pipeline.availability.EXCLUDED_KEYS` (`has_origin`, `has_ethic`,
    # `has_valid_civic`, `has_civic`, `is_wilderness_empire`, `is_megacorp`, ... -- see that
    # constant's own comment for the full list and the corpus evidence behind each). Real, dramatic
    # effect: `ORIGIN_REQUIREMENT` and `ETHICS_OR_CIVIC_REQUIREMENT` both drop to ZERO in the
    # unconditional distribution (their entire prior population was exactly what this item
    # excludes), and the worst profile-dependent rate falls all the way to 1.54% -- FAR under the
    # 3% warn threshold, the opposite direction from Item 2's own tradeoff. Exact equality here,
    # not a bound: this specific figure is what the regression test below exists to pin down, and
    # the category distribution below is the corroborating check.
    # **107 -> 34, a later session ("commit + close the loop" follow-up, Item 2): the
    # story-progression flag CLASS.** `pipeline.trigger_text.looks_like_story_progress`'s naming
    # pattern (crisis-faction fragments; `_possible`/`_solved`/`_unlocked`/`_happened`/`_complete`/
    # `_aborted`/`_knowledge`/`_opened` suffixes; `encountered_`/`completed_` prefixes) was applied
    # to RESOLUTION, not just display categorisation -- every sampled real setting site is a
    # genuine `is_triggered_only` country event with no empire-type restriction, the same evidence
    # shape as the already-approved `colossus_project` precedent
    # (`pipeline.availability.PROGRESSION_FLAGS_TRUE`). Real corpus: 64 distinct flag names (73
    # technologies) move UNCONDITIONALLY UNCERTAIN -> AVAILABLE for all 12 profiles -- none become
    # merely profile-dependent, which is why the worst profile-dependent rate below is UNCHANGED
    # (still 1.54%) even though the unconditional figure drops sharply.
    # Two real pattern matches are DELIBERATELY EXCLUDED from this resolution and stay UNCERTAIN:
    # `l_cluster_opened` and `encountered_first_lgate` are vanilla Stellaris L-Gate storyline
    # flags whose setting sites live in vanilla's `events`/`decisions`, which this project does not
    # vendor -- unlike every Gigastructures match, there is no corpus text to verify them against,
    # so resolving them would rest on outside-corpus knowledge rather than evidence. See
    # `pipeline.availability.PROGRESSION_PATTERN_EXCLUDED_FLAGS`'s own comment.
    # Six outliers the survey found NOT matching the pattern, and NOT resolved by it (reported for
    # user confirmation, not decided here): `can_build_star_eaters`, `acot_databank_sophia_agreed`,
    # `advanced_identity_creation`, `has_arcane_generator`, `has_quantum_catapult_insight`,
    # `has_encountered_psionic_auras`. Two more of the same non-matching shape turned up during
    # this pass and are reported the same way, not resolved: `finish_shroud_forged_liberation_flag`,
    # `machine_subspecies`.
    # **34 -> 31, a later session (the "Ring Segment / ascension-perk locking / gate-propagation"
    # follow-up, Items 1, 2 and 5).** Three independent, real fixes each removed exactly one
    # technology from the unconditional bucket:
    # - Item 1: `always` was never handled as a leaf at all (only `always = no` at a technology's
    #   own top level, via `pipeline.rendering_scope`'s permanently-disabled exclusion, which is a
    #   DIFFERENT mechanism). `tech_ring_world`'s whole `potential` is `{ always = yes }` -- the
    #   most trivially resolvable leaf in Clausewitz, reported uncertain for every profile. Fixed
    #   by adding `always = yes`/`always = no` handling to `_evaluate_leaf`.
    # - Item 5: `has_active_tradition` was never handled either (falls through to UNKNOWN
    #   unconditionally). `giga_tech_the_vat`'s `potential` contains `OR = {
    #   has_genetically_ascended = yes, has_active_tradition = tr_genetics_finish_extra_traits,
    #   has_ascension_perk = ap_mechromancy }` -- with the tradition leaf UNKNOWN, Kleene semantics
    #   left the whole OR (and thus the whole technology) UNKNOWN for every profile. Resolved:
    #   `has_active_tradition` now resolves TRUE by default, FALSE only for the one user-confirmed
    #   restricted category (`tr_genetics*`, unavailable to machine-intelligence empires) --
    #   `giga_tech_the_vat` now resolves AVAILABLE for all 12 profiles (non-machine via the
    #   tradition branch, machine via the still-open `ap_mechromancy` gate).
    # - Item 2's `_combine_or` correction (needed so an axis-locked ascension perk inside an OR
    #   doesn't wrongly close off a sibling that's still an open, achievable gate) resolved one
    #   further technology whose OR combination previously stayed UNKNOWN because a real FALSE
    #   sibling and a genuinely-open EXCLUDED sibling combined to UNKNOWN under the pre-fix rule.
    # See CLAUDE.md's "Ascension perks are gates ..." section and pipeline.availability's own
    # module docstring for the full writeup of all three fixes.
    assert len(survey.unconditional_uncertain) == 31
    assert unconditional_rate == pytest.approx(31 / 973)  # D-18: 980 -> 977; Item 2c: 977 -> 973
    assert dict(distribution) == {
        ReasonCategory.UNCLASSIFIED: 18,
        ReasonCategory.OPAQUE_COUNTRY_STATE: 12,
        ReasonCategory.CRISIS_OR_STORY_PROGRESS: 1,
    }  # crisis_or_story_progress falls from 72 to 1 -- the sole survivor is a technology whose
    # ONLY unconditional blocker is one of the two excluded vanilla L-Gate flags above; the other
    # excluded flag's technologies became profile-dependent instead (still ~1.6% worst rate).
    # ORIGIN_REQUIREMENT and ETHICS_OR_CIVIC_REQUIREMENT are still empty (0) -- Item 3's earlier
    # result, unaffected by this item. MOD_CONTENT_REQUIREMENT is still empty (0) -- unchanged from
    # before, for the same reason as before (Item 2d resolved has_acot/has_aot_mod already).


def test_uncertain_count_and_per_profile_breakdown_pinned(expanded_rendered_potentials):
    """Item 1 of the "commit + close the loop" follow-up session: makes the corpus-wide uncertain
    count a STRUCTURAL invariant rather than something only a manual re-survey catches.

    The precedent this closes: the `country_uses_bio_ships`/`exists=this` collision (this
    module's own docstring, Item 2 of the "path to zero uncertain" session) silently moved 110
    technologies to UNCERTAIN. Every mechanism-level unit test in `tests/test_scripted_triggers.py`
    stayed green throughout -- each tested the expansion rule faithfully in isolation, which is
    exactly why none of them could catch that the rule's OWN skip-list was wrong for one real,
    heavily-used key. Only a manual `test_real_rates_against_projections`-style re-run caught it,
    and only because a human remembered to re-run it. This test exists so that stops being
    optional: it pins BOTH the union count (any technology UNCERTAIN for >=1 of the 12 profiles --
    a number no earlier test computes at all) and the full per-profile breakdown, at the same
    grain as `test_real_rates_against_projections`'s unconditional/category pins, so a future
    collision of the same shape (a scripted-trigger skip-list gap, an axis-fact regression,
    anything that silently shifts which leaves resolve) fails an ordinary `pytest tests/` run
    instead of needing a human to remember to re-survey.

    Proven capable of failing, not just passing: temporarily removing `country_uses_bio_ships`
    from `pipeline.scripted_triggers._ALREADY_RESOLVED_KEYS` (this project's own historical bug,
    reintroduced by hand, then reverted) made this exact assertion fail loudly -- union count
    jumped 127 -> 213 -- before the removal was reverted. Not kept as a permanent mutation test
    (that bug's shape is already covered by `tests/test_scripted_triggers_corpus.py`'s
    zero-residual-`is_ai`-leaves guard and its own regression tests); this docstring records that
    the proof was done, per this project's "prove a negative result before believing it" rule.
    """
    profiles = all_profiles_in_canonical_order()
    survey = survey_uncertainty(expanded_rendered_potentials, profiles)

    union = set(survey.unconditional_uncertain)
    for indices in survey.profile_dependent_uncertain_by_profile_index.values():
        union |= set(indices)
    # 127 -> 54, Item 2 of the "commit + close the loop" follow-up session (this file's own
    # test_real_rates_against_projections docstring below has the full writeup): flags matching
    # pipeline.trigger_text.looks_like_story_progress's naming pattern now resolve TRUE as a
    # class, the same treatment already approved for colossus_project. All 73 technologies this
    # removed were previously UNCONDITIONALLY uncertain (true for all 12 profiles) and are now
    # AVAILABLE for all 12 -- none moved to profile-dependent, which is why the per-profile
    # breakdown below is UNCHANGED by this item.
    # 54 -> 53, a later session (Items 1, 2 and 5: `always`, ascension-perk axis-locking via the
    # `_combine_or` correction, and `has_active_tradition`) -- see
    # test_real_rates_against_projections's own writeup for the three fixes. This fixture now ALSO
    # registers real ascension-perk potentials (`set_perk_potentials`, the `_registered_perk_
    # potentials` autouse fixture above) so Item 2's effect is visible here at all -- without it,
    # this union count would read 52, not 53 (proven by running with that fixture disabled during
    # this session's own verification pass).
    assert len(union) == 53  # any technology UNCERTAIN for at least one of the 12 profiles

    per_profile_counts = {
        i: len(survey.profile_dependent_uncertain_by_profile_index.get(i, []))
        for i in range(len(profiles))
    }
    assert per_profile_counts == {
        0: 13,  # regular / mechanical / non-nomadic
        1: 6,  # regular / mechanical / nomadic
        2: 15,  # regular / biological / non-nomadic
        3: 8,  # regular / biological / nomadic
        4: 14,  # hive_mind / mechanical / non-nomadic
        5: 7,  # hive_mind / mechanical / nomadic
        6: 16,  # hive_mind / biological / non-nomadic (worst profile, ~1.64%)
        7: 9,  # hive_mind / biological / nomadic
        8: 8,  # machine_intelligence / mechanical / non-nomadic
        9: 1,  # machine_intelligence / mechanical / nomadic
        10: 10,  # machine_intelligence / biological / non-nomadic
        11: 3,  # machine_intelligence / biological / nomadic
    }


def test_warn_threshold_actually_fires_on_a_synthetic_worst_profile(expanded_rendered_potentials):
    # Task 3's consistency check: a threshold that stays silent on a real breach is worse than
    # none. The real worst-case profile-dependent rate took a real round trip within this single
    # session: 2.88% -> 2.77% (Item 2's four resolution rules then the has_ancrel fix, both real
    # improvements) -> 3.49% (Item 2's own `pipeline.scripted_triggers` expansion, a considered
    # tradeoff, see `tests/test_dataset_emit.py::
    # test_gate_classification_leaves_d10_uncertainty_unchanged`) -> 1.54% (Item 3's ethics/civic/
    # origin gate exclusions -- ORIGIN_REQUIREMENT and ETHICS_OR_CIVIC_REQUIREMENT were the bulk of
    # what was pushing individual profiles over 3%). The real corpus can no longer prove
    # classify_d10_status can return "warn" at all, so that's proven synthetically instead (this
    # project's own "prove a negative before believing it" standing rule), then the REAL rate is
    # asserted against its own real, current classification.
    assert classify_d10_status(0.035) == "warn"
    assert classify_d10_status(0.11) == "fail"
    assert classify_d10_status(0.01) == "ok"

    profiles = all_profiles_in_canonical_order()
    survey = survey_uncertainty(expanded_rendered_potentials, profiles)
    worst_rate = survey.worst_profile_dependent_rate()
    # 0.015416 -> 0.016444 (16/973), a later session (Items 1, 2, 5) -- see
    # test_gate_classification_leaves_d10_uncertainty_unchanged's own writeup.
    assert worst_rate == pytest.approx(0.016444, abs=1e-5)  # was 0.034944 before the earlier session's Item 3
    assert classify_d10_status(worst_rate) == "ok"

    diagnostics = build_d10_diagnostics_section(survey, profiles)
    statuses = {d["status"] for d in diagnostics["profileDependentUncertainty"]}
    assert statuses == {"ok"}  # every profile comfortably under the 3% warn threshold again
    assert "fail" not in statuses  # ceiling not breached
    assert "fail" not in statuses  # ceiling not breached


def test_d10_diagnostics_section_is_schema_valid(expanded_rendered_potentials):
    profiles = all_profiles_in_canonical_order()
    survey = survey_uncertainty(expanded_rendered_potentials, profiles)
    section = build_d10_diagnostics_section(survey, profiles)

    document = {
        "schemaVersion": "1.0.0",
        "profileDependentUncertainty": section["profileDependentUncertainty"],
        "unconditionalUncertainty": section["unconditionalUncertainty"],
        "uncertainTechnologies": [],
        "missingInlineScriptParameterCount": {"current": 0, "previous": 0},
        "tierPromotions": [],
        "swapsRenderingOnInheritedIcon": [],
        "unrecognisedGatePatterns": [],
        "missingLockReasonOverrides": [],
        "unresolvedTriggers": [],
        "unresolvedModDependencies": [],
        "unresolvableResearchPaths": [],
        "overwriteReport": {"technologyBlockOverwrites": [], "scriptedVariableOverwrites": []},
        "vendorSourcesLoaded": ["Vanilla", "Gigastructural Engineering", "ACOT", "AoT"],
        "placeholderTechnologiesAbsent": [],
        "vanillaTechnologiesRevertedFromAcotOverwrite": [],
        "weightGateSuppressions": [],
    }
    validate_diagnostics(document)  # raises on any schema violation


def test_repeatable_cap_group_evaluated_with_expanded_gating_conditions_present(rendered_potentials):
    """Permanent regression guard, two layers deep:

    1. All 50 `giga_tech_repeatable_*_cap` technologies must be evaluated against their REAL,
       inline_script-expanded `potential` condition, not silently treated as gate-free (which
       unexpanded parsing does -- their raw block has no `potential` field at all).
    2. Given that real condition, every one of the 50 must resolve to CONFIG_GATED under all
       twelve profiles -- not UNCERTAIN (that was the first, partial fix: recognising
       `_capped_r` stops the evaluator treating it as an opaque, undecidable leaf) and not plain
       LOCKED either (these 50 are gated by a mod-configuration toggle, not anything about the
       empire being played -- see spec/decisions.md's D-10). If a future change reintroduces
       raw/unexpanded loading, or `_capped_r` recognition regresses, or CONFIG_GATED collapses
       back into LOCKED, this test catches it directly rather than relying on an aggregate count
       drifting by 50 and someone noticing."""
    cap_keys = {k for k in rendered_potentials if k.startswith("giga_tech_repeatable_") and k.endswith("_cap")}
    assert len(cap_keys) == 50

    for key in cap_keys:
        potential = rendered_potentials[key]
        assert potential is not None, (
            f"{key}: potential block missing -- this technology's real gating condition only "
            f"exists after inline_script expansion; raw/unexpanded loading would silently treat "
            f"it as unconditionally available"
        )
        assert len(potential.items) > 0

    profiles = all_profiles_in_canonical_order()

    for key in cap_keys:
        potential = rendered_potentials[key]
        for profile in profiles:
            result = evaluate_trigger_block(potential, profile)
            assert result.state == CONFIG_GATED, f"{key} @ {profile}: expected config-gated, got {result.state}"
            assert result.category == ReasonCategory.MOD_CONFIGURATION

    # And the aggregate check: none of the 50 contributes to unconditionalUncertainty any more.
    survey = survey_uncertainty(rendered_potentials, profiles)
    assert cap_keys.isdisjoint(survey.unconditional_uncertain)


def test_no_locked_reasons_currently_need_a_lock_reason_override(rendered_potentials):
    # Task 3's finding behind config/lock_reason_overrides.txt being seeded empty: every leaf key
    # that can actually produce a LOCKED result in the real corpus already has a dedicated phrase
    # in pipeline/trigger_text.py. Regression-guarded here the same way
    # tests/test_overwrites_corpus.py guards P-15's "seeded empty" claim -- if a future corpus
    # refresh or a new AXIS_FACTS/GROUND_FACT_BOOL entry introduces an unphrased LOCKED leaf, this
    # fails instead of the gap going unnoticed.
    profiles = all_profiles_in_canonical_order()
    overrides = load_lock_reason_overrides()

    locked_results: dict = {}
    for key, block in rendered_potentials.items():
        for profile in profiles:
            result = evaluate_trigger_block(block, profile)
            if result.state == LOCKED:
                locked_results[key] = result
                break  # one LOCKED result per technology is enough to check its phrasing

    missing = build_missing_lock_reason_overrides(locked_results, overrides)
    assert missing == []
