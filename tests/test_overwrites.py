"""Tests for pipeline.overwrites — P-15 technology overwrite resolution.

Synthetic fixtures throughout: the real corpus's overwrite shapes are small (2 giga x vanilla,
4 acot x vanilla, 19 acot x aot, 0 chains of 3+) and are exercised end-to-end against the real
vendored corpus in tests/test_overwrites_corpus.py instead. This file exercises the mechanisms
the real corpus doesn't happen to cover: field-level diff semantics, the presence-vs-absence
distinction, set-vs-order for prerequisites, the scripted-variable layer, and the override table.
"""

import pytest

from pipeline.clausewitz import parse_text
from pipeline.overwrite_overrides import OverwriteOverride
from pipeline.overwrites import (
    OverwriteOverrideRequiredError,
    UnknownSourceError,
    alternative_prerequisite_groups,
    build_overwrite_report,
    collect_technology_definitions,
    collect_variable_definitions,
    ordered_prerequisites,
    resolve_technology_overwrites,
    resolve_variable_overwrites,
)
from pipeline.variables import build_variable_table


def _doc(text, path):
    return parse_text(text, path=path)


def _table(*documents):
    return build_variable_table(documents)


# ---------------------------------------------------------------------------
# collect_technology_definitions
# ---------------------------------------------------------------------------


def test_collect_keeps_full_occurrence_history_in_load_order():
    vanilla = _doc("tech_a = { cost = 100 }\n", "vanilla.txt")
    giga = _doc("tech_a = { cost = 200 }\n", "giga.txt")
    history = collect_technology_definitions([("Vanilla", [vanilla]), ("Gigastructural Engineering", [giga])])
    assert [occ.source for occ in history["tech_a"]] == ["Vanilla", "Gigastructural Engineering"]


def test_collect_rejects_unknown_source_name():
    doc = _doc("tech_a = { cost = 100 }\n", "x.txt")
    with pytest.raises(UnknownSourceError):
        collect_technology_definitions([("Not A Real Source", [doc])])


# ---------------------------------------------------------------------------
# resolve_technology_overwrites: label, source, and the ambiguity guard
# ---------------------------------------------------------------------------


def test_never_redefined_technology_has_no_overwrite_and_plain_label():
    doc = _doc("tech_a = { cost = 100 }\n", "vanilla.txt")
    history = collect_technology_definitions([("Vanilla", [doc])])
    records = resolve_technology_overwrites(history, _table(doc))
    record = records["tech_a"]
    assert record.defined_by == "Vanilla"
    assert record.overwrites is None
    assert record.label == "Vanilla"
    assert record.changed_fields == []


def test_redefined_technology_carries_modified_by_label():
    vanilla = _doc("tech_a = { cost = 100 }\n", "vanilla.txt")
    acot = _doc("tech_a = { cost = 200 }\n", "acot.txt")
    history = collect_technology_definitions([("Vanilla", [vanilla]), ("ACOT", [acot])])
    records = resolve_technology_overwrites(history, _table(vanilla, acot))
    record = records["tech_a"]
    assert record.defined_by == "ACOT"
    assert record.overwrites == "Vanilla"
    assert record.label == "Vanilla (modified by ACOT)"


def test_mod_on_mod_overwrite_has_no_vanilla_baseline():
    # The dominant real-corpus pattern: AoT overwrites ACOT, no vanilla involved at all.
    acot = _doc("tech_a = { cost = 100 }\n", "acot.txt")
    aot = _doc("tech_a = { cost = 300 }\n", "aot.txt")
    history = collect_technology_definitions([("ACOT", [acot]), ("AoT", [aot])])
    records = resolve_technology_overwrites(history, _table(acot, aot))
    record = records["tech_a"]
    assert record.defined_by == "AoT"
    assert record.overwrites == "ACOT"
    assert record.label == "ACOT (modified by AoT)"
    assert record.changed_fields == ["cost"]


def test_three_source_chain_requires_override_entry():
    vanilla = _doc("tech_a = { cost = 100 }\n", "vanilla.txt")
    giga = _doc("tech_a = { cost = 200 }\n", "giga.txt")
    acot = _doc("tech_a = { cost = 300 }\n", "acot.txt")
    history = collect_technology_definitions(
        [("Vanilla", [vanilla]), ("Gigastructural Engineering", [giga]), ("ACOT", [acot])]
    )
    with pytest.raises(OverwriteOverrideRequiredError):
        resolve_technology_overwrites(history, _table(vanilla, giga, acot))


def test_same_source_duplicate_requires_override_entry():
    vanilla = _doc("tech_a = { cost = 100 }\n", "vanilla.txt")
    dupe_a = _doc("tech_a = { cost = 200 }\n", "giga_a.txt")
    dupe_b = _doc("tech_a = { cost = 300 }\n", "giga_b.txt")
    history = collect_technology_definitions([("Vanilla", [vanilla]), ("Gigastructural Engineering", [dupe_a, dupe_b])])
    with pytest.raises(OverwriteOverrideRequiredError):
        resolve_technology_overwrites(history, _table(vanilla, dupe_a, dupe_b))


def test_override_entry_picks_named_winner_for_ambiguous_chain():
    vanilla = _doc("tech_a = { cost = 100 }\n", "vanilla.txt")
    giga = _doc("tech_a = { cost = 200 }\n", "giga.txt")
    acot = _doc("tech_a = { cost = 300 }\n", "acot.txt")
    history = collect_technology_definitions(
        [("Vanilla", [vanilla]), ("Gigastructural Engineering", [giga]), ("ACOT", [acot])]
    )
    overrides = {"tech_a": OverwriteOverride("tech_a", "Gigastructural Engineering", "test", 1)}
    records = resolve_technology_overwrites(history, _table(vanilla, giga, acot), overrides)
    record = records["tech_a"]
    assert record.defined_by == "Gigastructural Engineering"


# ---------------------------------------------------------------------------
# Field diff: presence vs absence, sets vs order, resolved vs raw.
# ---------------------------------------------------------------------------


def test_field_present_in_before_and_absent_after_is_a_change():
    before = _doc("tech_a = { cost = 100\n weight = 5 }\n", "vanilla.txt")
    after = _doc("tech_a = { cost = 100 }\n", "acot.txt")
    history = collect_technology_definitions([("Vanilla", [before]), ("ACOT", [after])])
    records = resolve_technology_overwrites(history, _table(before, after))
    record = records["tech_a"]
    assert "weight" in record.changed_fields
    weight_change = next(fc for fc in record.field_changes if fc.field == "weight")
    assert weight_change.before_present is True
    assert weight_change.after_present is False


def test_field_never_present_on_either_side_is_not_a_change():
    before = _doc("tech_a = { cost = 100 }\n", "vanilla.txt")
    after = _doc("tech_a = { cost = 200 }\n", "acot.txt")
    history = collect_technology_definitions([("Vanilla", [before]), ("ACOT", [after])])
    records = resolve_technology_overwrites(history, _table(before, after))
    record = records["tech_a"]
    assert "weight" not in record.changed_fields
    weight_change = next(fc for fc in record.field_changes if fc.field == "weight")
    assert weight_change.before_present is False
    assert weight_change.after_present is False


def test_prerequisites_reordered_only_is_not_a_diff_change():
    before = _doc('tech_a = { prerequisites = { tech_x tech_y } }\n', "vanilla.txt")
    after = _doc('tech_a = { prerequisites = { tech_y tech_x } }\n', "acot.txt")
    history = collect_technology_definitions([("Vanilla", [before]), ("ACOT", [after])])
    records = resolve_technology_overwrites(history, _table(before, after))
    assert "prerequisites" not in records["tech_a"].changed_fields


def test_prerequisites_added_technology_is_a_diff_change():
    before = _doc('tech_a = { prerequisites = { tech_x } }\n', "vanilla.txt")
    after = _doc('tech_a = { prerequisites = { tech_x tech_z } }\n', "acot.txt")
    history = collect_technology_definitions([("Vanilla", [before]), ("ACOT", [after])])
    records = resolve_technology_overwrites(history, _table(before, after))
    assert "prerequisites" in records["tech_a"].changed_fields


def test_ordered_prerequisites_is_declaration_order_from_winning_definition():
    doc = _doc(
        'tech_a = { prerequisites = { tech_w tech_z } }\n', "giga.txt"
    )
    assignment = doc.items[0]
    order = ordered_prerequisites(assignment.value)
    assert order == ["tech_w", "tech_z"]


def test_ordered_prerequisites_excludes_or_branch_members():
    # Correction: OR-branch members are alternative prerequisites, not true (AND-required) ones
    # -- ordered_prerequisites must not flatten them in alongside tech_z.
    doc = _doc(
        'tech_a = { prerequisites = { tech_z OR = { tech_y tech_x } tech_z } }\n', "giga.txt"
    )
    assignment = doc.items[0]
    order = ordered_prerequisites(assignment.value)
    assert order == ["tech_z"]


def test_alternative_prerequisite_groups_extracts_or_members():
    doc = _doc(
        'tech_a = { prerequisites = { tech_z OR = { tech_y tech_x } } }\n', "giga.txt"
    )
    assignment = doc.items[0]
    groups = alternative_prerequisite_groups(assignment.value)
    assert groups == [["tech_y", "tech_x"]]


def test_alternative_prerequisite_groups_supports_multiple_groups_per_technology():
    # tech_mega_engineering's real shape: two independent OR groups in one prerequisites block.
    doc = _doc(
        'tech_a = { prerequisites = { '
        'tech_zero_point_power OR = { tech_starbase_5 tech_arkship_tier_3 } '
        'OR = { tech_battleships tech_stingers } } }\n',
        "giga.txt",
    )
    assignment = doc.items[0]
    assert ordered_prerequisites(assignment.value) == ["tech_zero_point_power"]
    groups = alternative_prerequisite_groups(assignment.value)
    assert groups == [["tech_starbase_5", "tech_arkship_tier_3"], ["tech_battleships", "tech_stingers"]]


def test_alternative_prerequisite_groups_empty_when_no_or():
    doc = _doc('tech_a = { prerequisites = { tech_z } }\n', "giga.txt")
    assignment = doc.items[0]
    assert alternative_prerequisite_groups(assignment.value) == []


def test_prerequisite_ordering_is_deterministic_across_repeated_runs():
    doc = _doc('tech_a = { prerequisites = { tech_c tech_a tech_b } }\n', "giga.txt")
    assignment = doc.items[0]
    first = ordered_prerequisites(assignment.value)
    second = ordered_prerequisites(assignment.value)
    assert first == second == ["tech_c", "tech_a", "tech_b"]


def test_weight_kind_change_literal_to_variable_reference_is_tracked_separately_from_value():
    # The real corpus case (tech_precursor_gateway): weight goes from a NumberLiteral to a
    # VariableReference. Retain both the raw (mechanism) and resolved (value) forms.
    variables = _doc("@w = 0\n", "vars.txt")
    before = _doc("tech_a = { weight = 0 }\n", "acot.txt")
    after = _doc("tech_a = { weight = @w }\n", "aot.txt")
    table = _table(variables, before, after)
    history = collect_technology_definitions([("ACOT", [before]), ("AoT", [after])])
    records = resolve_technology_overwrites(history, table)
    weight_change = next(fc for fc in records["tech_a"].field_changes if fc.field == "weight")
    assert weight_change.before_raw == "0"
    assert weight_change.after_raw == "@w"
    # Resolved values are equal (both 0) so this is a mechanism change, not a value change --
    # confirm it did NOT get reported as a changedFields entry purely on resolved-value grounds,
    # while still being individually inspectable via field_changes.
    assert weight_change.before_resolved == weight_change.after_resolved == "0"
    assert "weight" not in records["tech_a"].changed_fields


def test_indirect_scripted_variable_overwrite_changes_effective_cost():
    # Finding 5: the technology block is untouched, but the variable it references was
    # redefined by a later source -- the diff must catch this via resolution, not miss it.
    old_vars = _doc("@c = 100\n", "acot_vars.txt")
    new_vars = _doc("@c = 500\n", "aot_vars.txt")
    tech = _doc("tech_a = { cost = @c }\n", "acot.txt")
    table = _table(old_vars, new_vars, tech)
    # Same technology block on both sides of a synthetic "before/after" comparison, only the
    # variable table differs in principle -- exercised properly via resolve_variable_overwrites
    # below, since a same-block diff has nothing to compare. This confirms resolution picks the
    # LATEST variable value.
    assert table.resolve("c").value == 500


def test_flags_change_is_reported_as_single_flags_field():
    before = _doc("tech_a = { is_rare = yes }\n", "vanilla.txt")
    after = _doc("tech_a = { is_rare = yes\n is_dangerous = yes }\n", "acot.txt")
    history = collect_technology_definitions([("Vanilla", [before]), ("ACOT", [after])])
    records = resolve_technology_overwrites(history, _table(before, after))
    assert records["tech_a"].changed_fields == ["flags"]


# ---------------------------------------------------------------------------
# Scripted-variable overwrite layer
# ---------------------------------------------------------------------------


def test_variable_overwrite_reports_affected_technologies_distinct_from_tech_block_layer():
    acot_vars = _doc("@shared_cost = 100\n", "acot_vars.txt")
    aot_vars = _doc("@shared_cost = 500\n", "aot_vars.txt")
    # tech_untouched's own block is identical everywhere -- only ever defined once, by ACOT.
    tech = _doc("tech_untouched = { cost = @shared_cost }\n", "acot_tech.txt")

    variable_history = collect_variable_definitions([("ACOT", [acot_vars]), ("AoT", [aot_vars])])
    technology_history = collect_technology_definitions([("ACOT", [tech])])

    records = resolve_variable_overwrites(variable_history, technology_history)
    assert len(records) == 1
    record = records[0]
    assert record.name == "shared_cost"
    assert record.defined_by == "AoT"
    assert record.overwrites == "ACOT"
    assert record.affected_technologies == ["tech_untouched"]

    # And this technology has NO technology-block overwrite entry at all -- the two layers are
    # genuinely distinct.
    tech_records = resolve_technology_overwrites(technology_history, _table(acot_vars, aot_vars, tech))
    assert tech_records["tech_untouched"].overwrites is None


def test_variable_overwrite_layer_catches_tier_not_just_cost_and_weight():
    # P-2 layout tier-source audit finding: 83/980 real rendered nodes declare `tier` as a
    # @variable reference. This is the synthetic mechanism test for the fix -- a technology
    # whose OWN block is untouched can still have its effective declared tier change if the
    # variable it references is redefined cross-source.
    acot_vars = _doc("@shared_tier = 5\n", "acot_vars.txt")
    aot_vars = _doc("@shared_tier = 7\n", "aot_vars.txt")
    tech = _doc("tech_untouched = { tier = @shared_tier }\n", "acot_tech.txt")

    variable_history = collect_variable_definitions([("ACOT", [acot_vars]), ("AoT", [aot_vars])])
    technology_history = collect_technology_definitions([("ACOT", [tech])])

    records = resolve_variable_overwrites(variable_history, technology_history)
    assert len(records) == 1
    record = records[0]
    assert record.name == "shared_tier"
    assert record.defined_by == "AoT"
    assert record.overwrites == "ACOT"
    assert record.affected_technologies == ["tech_untouched"]


def test_variable_never_redefined_produces_no_overwrite_record():
    doc = _doc("@x = 1\n", "vanilla.txt")
    variable_history = collect_variable_definitions([("Vanilla", [doc])])
    technology_history = collect_technology_definitions([])
    assert resolve_variable_overwrites(variable_history, technology_history) == []


def test_variable_redefined_within_same_source_is_not_an_overwrite_record():
    doc = _doc("@x = 1\n@x = 2\n", "vanilla.txt")
    variable_history = collect_variable_definitions([("Vanilla", [doc])])
    technology_history = collect_technology_definitions([])
    assert resolve_variable_overwrites(variable_history, technology_history) == []


# ---------------------------------------------------------------------------
# S-2 report shape
# ---------------------------------------------------------------------------


def test_report_separates_technology_and_variable_sections():
    vanilla = _doc("tech_a = { cost = 100 }\n", "vanilla.txt")
    acot = _doc("tech_a = { cost = 200 }\n", "acot.txt")
    history = collect_technology_definitions([("Vanilla", [vanilla]), ("ACOT", [acot])])
    tech_records = resolve_technology_overwrites(history, _table(vanilla, acot))

    acot_vars = _doc("@x = 1\n", "acot_vars.txt")
    aot_vars = _doc("@x = 2\n", "aot_vars.txt")
    tech_ref = _doc("tech_b = { cost = @x }\n", "acot_tech.txt")
    var_history = collect_variable_definitions([("ACOT", [acot_vars]), ("AoT", [aot_vars])])
    tech_history_2 = collect_technology_definitions([("ACOT", [tech_ref])])
    var_records = resolve_variable_overwrites(var_history, tech_history_2)

    report = build_overwrite_report(tech_records, var_records)
    assert set(report.keys()) == {"technologyBlockOverwrites", "scriptedVariableOverwrites"}
    assert report["technologyBlockOverwrites"][0]["technology"] == "tech_a"
    assert report["scriptedVariableOverwrites"][0]["variable"] == "x"


def test_report_omits_never_overwritten_technologies():
    doc = _doc("tech_a = { cost = 100 }\n", "vanilla.txt")
    history = collect_technology_definitions([("Vanilla", [doc])])
    records = resolve_technology_overwrites(history, _table(doc))
    report = build_overwrite_report(records, [])
    assert report["technologyBlockOverwrites"] == []
