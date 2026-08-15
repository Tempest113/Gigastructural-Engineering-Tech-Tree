"""End-to-end P-15 overwrite resolution against the real vendored corpus.

Skipped when vendor/ isn't populated, same posture as tests/clausewitz/test_roundtrip_full_corpus.py
-- vendor/ is gitignored (base-game and Steam Workshop content is not redistributable), so CI
never has it. Run this locally for the authoritative "does resolution actually work on the real
corpus" answer; tests/test_overwrites.py's synthetic fixtures are the CI-safe proxy.

Asserts the corrected survey counts from CLAUDE.md's "Source data" section (25 cross-source
technology-block overlaps: 2 gigastructures x vanilla, 4 acot x vanilla, 19 acot x aot, 0
three-or-deeper chains) so a future corpus refresh that silently changes these numbers fails a
test instead of going unnoticed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.clausewitz import parse_file
from pipeline.overwrite_overrides import load_overrides
from pipeline.overwrites import (
    alternative_prerequisite_groups,
    build_overwrite_report,
    collect_technology_definitions,
    collect_variable_definitions,
    resolve_technology_overwrites,
    resolve_variable_overwrites,
)
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


def _load_technology_documents():
    return [
        (name, [parse_file(f) for f in sorted((root / "common" / "technology").glob("*.txt"))])
        for name, root in _SOURCES_IN_LOAD_ORDER
        if (root / "common" / "technology").is_dir()
    ]


def _load_variable_documents():
    return [
        (name, [parse_file(f) for f in sorted((root / "common" / "scripted_variables").glob("*.txt"))])
        for name, root in _SOURCES_IN_LOAD_ORDER
        if (root / "common" / "scripted_variables").is_dir()
    ]


@pytest.fixture(scope="module")
def resolution():
    tech_docs = _load_technology_documents()
    var_docs = _load_variable_documents()

    all_docs = [doc for _, docs in tech_docs for doc in docs] + [doc for _, docs in var_docs for doc in docs]
    variable_table = build_variable_table(all_docs)

    technology_history = collect_technology_definitions(tech_docs)
    variable_history = collect_variable_definitions(var_docs)

    overrides = load_overrides()
    technology_records = resolve_technology_overwrites(technology_history, variable_table, overrides)
    variable_records = resolve_variable_overwrites(variable_history, technology_history)

    return technology_history, technology_records, variable_records


def test_corpus_resolves_with_no_override_needed(resolution):
    # If this ever raises OverwriteOverrideRequiredError, the corpus survey behind
    # config/overwrite_overrides.txt's "seeded empty" claim is stale -- a new ambiguous shape
    # appeared and needs a reviewed entry, not a code change to silently permit it.
    _, technology_records, _ = resolution
    assert len(technology_records) > 1000  # sanity: corpus actually loaded (1879 distinct keys at survey time)


def test_corrected_overlap_counts_match_survey(resolution):
    technology_history, _, _ = resolution
    cross_source = {k: v for k, v in technology_history.items() if len({occ.source for occ in v}) > 1}
    assert len(cross_source) == 25

    by_pattern = {}
    for key, occurrences in cross_source.items():
        pattern = tuple(sorted({occ.source for occ in occurrences}))
        by_pattern.setdefault(pattern, []).append(key)

    assert len(by_pattern[("Gigastructural Engineering", "Vanilla")]) == 2
    assert set(by_pattern[("Gigastructural Engineering", "Vanilla")]) == {"tech_ring_world", "tech_mega_engineering"}
    assert len(by_pattern[("ACOT", "Vanilla")]) == 4
    assert len(by_pattern[("ACOT", "AoT")]) == 19

    three_plus = [k for k, v in cross_source.items() if len({occ.source for occ in v}) >= 3]
    assert three_plus == []


def test_tech_ring_world_resolves_as_giga_over_vanilla(resolution):
    _, technology_records, _ = resolution
    record = technology_records["tech_ring_world"]
    assert record.defined_by == "Gigastructural Engineering"
    assert record.overwrites == "Vanilla"
    assert record.label == "Vanilla (modified by Gigastructural Engineering)"


def test_tech_mega_engineering_resolves_as_giga_over_vanilla(resolution):
    # The stronger regression anchor of the two giga x vanilla overwrites: this technology's
    # block exercises nested-OR prerequisites, an inline_script weight modifier, an @variable
    # weight, and nomadic-axis weight modifiers all in one block -- a single test here covers a
    # lot of surface at once. Also the technology whose absence from a stale vendored snapshot
    # triggered the re-vendor recorded in CLAUDE.md's "Source data" section.
    technology_history, technology_records, _ = resolution
    record = technology_records["tech_mega_engineering"]
    assert record.defined_by == "Gigastructural Engineering"
    assert record.overwrites == "Vanilla"
    assert record.label == "Vanilla (modified by Gigastructural Engineering)"

    # Corrected: OR-branch members are alternative prerequisites, not true (AND-required) ones --
    # ordered_prerequisites() now excludes them, leaving only the plain tech_zero_point_power
    # entry. alternative_prerequisite_groups() separately exposes the two independent OR groups
    # this technology carries (one of only 3 real-corpus technologies with more than one) --
    # confirms both functions handle real nested boolean structure, not just synthetic fixtures.
    assert set(record.prerequisites_ordered) == {"tech_zero_point_power"}

    winning_block = technology_history["tech_mega_engineering"][-1].block
    groups = alternative_prerequisite_groups(winning_block)
    assert len(groups) == 2
    assert {frozenset(g) for g in groups} == {
        frozenset({"tech_starbase_5", "tech_arkship_tier_3"}),
        frozenset({"tech_battleships", "tech_stingers"}),
    }

    # cost/weight are both @variable references (@tier5cost3 / @tier5weight3) on both sides of
    # the overwrite -- the raw mechanism is unchanged, so neither is in changed_fields, but the
    # raw form is still real @variable text, not a literal, confirming resolution ran.
    cost_change = next(fc for fc in record.field_changes if fc.field == "cost")
    weight_change = next(fc for fc in record.field_changes if fc.field == "weight")
    assert cost_change.before_raw == cost_change.after_raw == "@tier5cost3"
    assert weight_change.before_raw == weight_change.after_raw == "@tier5weight3"

    # Corroborating evidence the winning (Gigastructures) block really is the rich one described
    # above, not a stub -- inline_script and nomadic-axis weight modifiers live inside
    # weight_modifier, outside P-15's diffed fields, so check the raw block directly.
    winning_def = technology_history["tech_mega_engineering"][-1]
    assert winning_def.source == "Gigastructural Engineering"
    serialized_block_keys = {item.key_name for item in winning_def.block.items if hasattr(item, "key_name")}
    assert "weight_modifier" in serialized_block_keys


def test_tech_precursor_gateway_weight_mechanism_change_is_visible(resolution):
    # The known worked example: ACOT's NumberLiteral(0) weight becomes AoT's
    # VariableReference(tier5weight3). Resolved values may coincide, but the raw mechanism
    # change must still be inspectable.
    _, technology_records, _ = resolution
    record = technology_records["tech_precursor_gateway"]
    assert record.defined_by == "AoT"
    assert record.overwrites == "ACOT"
    weight_change = next(fc for fc in record.field_changes if fc.field == "weight")
    assert weight_change.before_raw == "0"
    assert weight_change.after_raw == "@tier5weight3"


def test_scripted_variable_layer_finds_real_acot_aot_overwrites(resolution):
    # s_pe_cost/m_pe_cost/etc (component-cost variables) are real acot x aot overlaps but are
    # never referenced by a technology's own cost/weight field (they gate component costs, a
    # different namespace), so they correctly produce no record here -- only variables that
    # actually affect a technology's effective cost/weight belong in this report. The
    # acot_tier*cost2 variables (from Gigastructures' compat-overwrite file) ARE referenced by
    # technology cost fields and are the real worked example for this layer.
    _, _, variable_records = resolution
    names = {vr.name for vr in variable_records}
    assert "s_pe_cost" not in names
    assert "acot_tier6cost2" in names
    record = next(vr for vr in variable_records if vr.name == "acot_tier6cost2")
    # Gigastructures' zz_giga_compat_overwrite_me.txt stubs this as a fallback for when ACOT
    # isn't installed; ACOT loads after Gigastructures, so ACOT's real definition wins when both
    # are present -- the stub is the one getting overwritten, not the other way round.
    assert record.defined_by == "ACOT"
    assert record.overwrites == "Gigastructural Engineering"
    assert len(record.affected_technologies) >= 1


def test_report_builds_without_error_and_has_both_sections(resolution):
    _, technology_records, variable_records = resolution
    report = build_overwrite_report(technology_records, variable_records)
    assert len(report["technologyBlockOverwrites"]) == 25
    assert len(report["scriptedVariableOverwrites"]) >= 1
