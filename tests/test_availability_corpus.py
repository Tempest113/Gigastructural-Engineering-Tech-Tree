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


def test_rendered_scope_is_exactly_980(rendered_potentials):
    assert len(rendered_potentials) == 980


def test_real_rates_against_projections(rendered_potentials):
    profiles = all_profiles_in_canonical_order()
    survey = survey_uncertainty(rendered_potentials, profiles)

    total = survey.total_technologies
    assert total == 980  # this IS the rendered denominator the spec now requires (Task 1's D-10 split)

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
    assert worst_dependent_rate < 0.053  # real evaluator should land below the projected upper bound

    # Corrected twice, see this module's docstring: 209 -> 259 (raw vs. expanded blocks) -> 209
    # again (the 50 giga_tech_repeatable_*_cap nodes are CONFIG_GATED, not UNCERTAIN -- they
    # resolve definitively, they just aren't empire-state LOCKED either). Exact equality here,
    # not a bound: this specific figure is exactly what the regression test below exists to pin
    # down, and the category distribution below is the corroborating check that this 209 is the
    # SAME 209 the pre-correction figure happened to name, not a different set that sums to the
    # same size by coincidence.
    assert len(survey.unconditional_uncertain) == 209
    assert unconditional_rate == pytest.approx(209 / 980)
    assert dict(distribution) == {
        ReasonCategory.CRISIS_OR_STORY_PROGRESS: 89,
        ReasonCategory.ORIGIN_REQUIREMENT: 41,
        ReasonCategory.OPAQUE_COUNTRY_STATE: 34,
        ReasonCategory.ETHICS_OR_CIVIC_REQUIREMENT: 34,
        ReasonCategory.UNCLASSIFIED: 7,
        ReasonCategory.MOD_CONTENT_REQUIREMENT: 4,
    }


def test_warn_threshold_actually_fires_on_the_real_worst_profile(rendered_potentials):
    # Task 3's consistency check: a threshold that stays silent on a real breach is worse than
    # none. The real worst-case profile-dependent rate is consistently a few points above 3%
    # (3.37%-3.70% across recent runs as the evaluator gained resolution rules) -- confirm
    # classify_d10_status genuinely returns "warn" for it, not just that the number looks right
    # in a printed log.
    profiles = all_profiles_in_canonical_order()
    survey = survey_uncertainty(rendered_potentials, profiles)
    worst_rate = survey.worst_profile_dependent_rate()
    assert worst_rate > 0.03  # still a real breach at time of writing -- see printed rate above
    assert classify_d10_status(worst_rate) == "warn"

    diagnostics = build_d10_diagnostics_section(survey, profiles)
    statuses = {d["status"] for d in diagnostics["profileDependentUncertainty"]}
    assert "warn" in statuses
    assert "fail" not in statuses  # ceiling not breached


def test_d10_diagnostics_section_is_schema_valid(rendered_potentials):
    profiles = all_profiles_in_canonical_order()
    survey = survey_uncertainty(rendered_potentials, profiles)
    section = build_d10_diagnostics_section(survey, profiles)

    document = {
        "schemaVersion": "1.0.0",
        "profileDependentUncertainty": section["profileDependentUncertainty"],
        "unconditionalUncertainty": section["unconditionalUncertainty"],
        "missingInlineScriptParameterCount": {"current": 0, "previous": 0},
        "tierPromotions": [],
        "swapsRenderingOnInheritedIcon": [],
        "unrecognisedGatePatterns": [],
        "missingLockReasonOverrides": [],
        "unresolvedTriggers": [],
        "unresolvedModDependencies": [],
        "overwriteReport": {"technologyBlockOverwrites": [], "scriptedVariableOverwrites": []},
        "vendorSourcesLoaded": ["Vanilla", "Gigastructural Engineering", "ACOT", "AoT"],
        "placeholderTechnologiesAbsent": [],
        "vanillaTechnologiesRevertedFromAcotOverwrite": [],
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
