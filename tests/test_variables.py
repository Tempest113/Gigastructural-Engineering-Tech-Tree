"""Tests for pipeline.variables — scripted-variable (@name) resolution.

Uses the real fixtures where the corpus has real cases (the ACOT compat-overwrite pair), and
the hand-authored tests/fixtures/variables/ fixtures where it doesn't (chains, cycles) — see
tests/fixtures/NOTES.md for why those had to be hand-authored.
"""

import pytest

from tests.conftest import FIXTURES_ROOT

from pipeline.clausewitz import parse_file, parse_text
from pipeline.clausewitz.nodes import Identifier, NumberLiteral, StringLiteral
from pipeline.variables import (
    InvalidVariableValueError,
    UndefinedVariableError,
    VariableCycleError,
    VariableTable,
    build_variable_table,
    collect_definitions,
    iter_variable_references,
)


# ---------------------------------------------------------------------------
# collect_definitions: last-definition-wins, in load order.
# ---------------------------------------------------------------------------


def test_duplicate_definition_within_one_document_last_one_wins():
    doc = parse_text("@x = 1\n@x = 2\n", path="<memory>")
    definitions = collect_definitions([doc])
    assert definitions["x"].value.value == 2


def test_later_source_overwrites_earlier_source_in_load_order():
    first = parse_text("@x = 1\n", path="source_a.txt")
    second = parse_text("@x = 2\n", path="source_b.txt")
    definitions = collect_definitions([first, second])
    assert definitions["x"].value.value == 2
    assert definitions["x"].source_path == "source_b.txt"


def test_acot_compat_stub_wins_when_acot_is_not_vendored():
    # The real case: Gigastructures' zz_giga_compat_overwrite_me.txt stubs @acot_tier6cost2 = 0
    # so the reference resolves even when ACOT isn't present at all.
    giga_compat = parse_file(
        FIXTURES_ROOT / "gigastructures" / "common" / "scripted_variables" / "zz_giga_compat_overwrite_me.txt"
    )
    definitions = collect_definitions([giga_compat])
    table = VariableTable(definitions)
    resolved = table.resolve("acot_tier6cost2")
    assert isinstance(resolved, NumberLiteral)
    assert resolved.value == 0


def test_acot_real_definition_overwrites_gigastructures_compat_stub_when_both_load():
    # Load order: Gigastructures (defines the placeholder) then ACOT (defines the real value) —
    # matching spec/00-overview.md's Sources and load order. ACOT must win.
    giga_compat = parse_file(
        FIXTURES_ROOT / "gigastructures" / "common" / "scripted_variables" / "zz_giga_compat_overwrite_me.txt"
    )
    acot_real = parse_file(FIXTURES_ROOT / "acot" / "common" / "scripted_variables" / "acot_scripted_variables_tech_cost.txt")
    definitions = collect_definitions([giga_compat, acot_real])
    table = VariableTable(definitions)
    resolved = table.resolve("acot_tier6cost2")
    assert isinstance(resolved, NumberLiteral)
    assert resolved.value == 80000  # the real ACOT value, not Gigastructures' 0 stub

    # And the reverse load order must NOT happen to work by accident — assert the function
    # really is order-sensitive (last wins), not doing something order-independent like "prefer
    # non-zero".
    definitions_wrong_order = collect_definitions([acot_real, giga_compat])
    table_wrong_order = VariableTable(definitions_wrong_order)
    assert table_wrong_order.resolve("acot_tier6cost2").value == 0


# ---------------------------------------------------------------------------
# Resolution: direct, chained (out of declaration order), and non-numeric.
# ---------------------------------------------------------------------------


def test_resolve_direct_numeric_value():
    doc = parse_text("@x = 42\n", path="<memory>")
    table = build_variable_table([doc])
    resolved = table.resolve("x")
    assert isinstance(resolved, NumberLiteral)
    assert resolved.value == 42


def test_resolve_chain_declared_in_reverse_dependency_order():
    # reference-chain.txt declares @chain_top first, even though it depends (transitively) on
    # @chain_middle then @chain_base, declared after it. A resolver that just evaluates
    # top-to-bottom in one sequential pass would get this wrong.
    doc = parse_file(FIXTURES_ROOT / "variables" / "reference-chain.txt")
    table = build_variable_table([doc])

    top = table.resolve("chain_top")
    assert isinstance(top, NumberLiteral)
    assert top.value == 1000

    # Every link resolves to the same terminal value.
    assert table.resolve("chain_middle").value == 1000
    assert table.resolve("chain_base").value == 1000


def test_resolve_to_bare_identifier_not_numeric():
    # @giga_amb_flag = giga_buildcap_j — must not assume every resolved value is numeric.
    doc = parse_file(FIXTURES_ROOT / "gigastructures" / "common" / "scripted_variables" / "giga_amb_variables.txt")
    table = build_variable_table([doc])
    resolved = table.resolve("giga_amb_flag")
    assert isinstance(resolved, Identifier)
    assert resolved.name == "giga_buildcap_j"


def test_resolve_to_string_literal():
    doc = parse_text('@x = "hello"\n', path="<memory>")
    table = build_variable_table([doc])
    resolved = table.resolve("x")
    assert isinstance(resolved, StringLiteral)
    assert resolved.value == "hello"


def test_giga_amb_flag_reference_site_resolves_through_its_definition_file():
    # The full round trip: a reference in one file (giga_17_alternative_mega_build.txt),
    # resolved against a definition collected from a different file (giga_amb_variables.txt).
    usage_doc = parse_file(FIXTURES_ROOT / "gigastructures" / "giga_17_alternative_mega_build.txt")
    definition_doc = parse_file(
        FIXTURES_ROOT / "gigastructures" / "common" / "scripted_variables" / "giga_amb_variables.txt"
    )
    table = build_variable_table([definition_doc])

    refs = list(iter_variable_references(usage_doc))
    matching = [r for r in refs if r.name == "giga_amb_flag"]
    assert matching, "expected a @giga_amb_flag reference in giga_17_alternative_mega_build.txt"

    resolved = table.resolve(matching[0].name)
    assert isinstance(resolved, Identifier)
    assert resolved.name == "giga_buildcap_j"


# ---------------------------------------------------------------------------
# Cycle detection.
# ---------------------------------------------------------------------------


def test_cycle_raises_and_names_the_full_chain_and_each_links_source():
    doc = parse_file(FIXTURES_ROOT / "variables" / "reference-cycle.txt")
    table = build_variable_table([doc])

    with pytest.raises(VariableCycleError) as excinfo:
        table.resolve("cycle_a")

    err = excinfo.value
    names_in_chain = {d.name for d in err.chain}
    assert names_in_chain == {"cycle_a", "cycle_b", "cycle_c"}
    message = str(err)
    # Every name and every link's source file appears in the message.
    for name in ("cycle_a", "cycle_b", "cycle_c"):
        assert f"@{name}" in message
        assert "reference-cycle.txt" in message


def test_cycle_detected_regardless_of_which_member_is_resolved_first():
    doc = parse_file(FIXTURES_ROOT / "variables" / "reference-cycle.txt")
    for start in ("cycle_a", "cycle_b", "cycle_c"):
        table = build_variable_table([doc])  # fresh table: no cross-test cache reuse
        with pytest.raises(VariableCycleError):
            table.resolve(start)


def test_self_reference_is_a_one_element_cycle():
    doc = parse_text("@x = @x\n", path="<memory>")
    table = build_variable_table([doc])
    with pytest.raises(VariableCycleError) as excinfo:
        table.resolve("x")
    assert {d.name for d in excinfo.value.chain} == {"x"}


# ---------------------------------------------------------------------------
# Undefined references.
# ---------------------------------------------------------------------------


def test_undefined_reference_raises_with_no_chain():
    doc = parse_text("", path="<memory>")
    table = build_variable_table([doc])
    with pytest.raises(UndefinedVariableError) as excinfo:
        table.resolve("nonexistent_variable")
    assert excinfo.value.chain == []
    assert "nonexistent_variable" in str(excinfo.value)


def test_undefined_reference_reached_transitively_carries_the_chain():
    doc = parse_text("@a = @b\n", path="<memory>")  # @b is never defined
    table = build_variable_table([doc])
    with pytest.raises(UndefinedVariableError) as excinfo:
        table.resolve("a")
    assert [d.name for d in excinfo.value.chain] == ["a"]
    assert "@b" in str(excinfo.value)


def test_undefined_reference_does_not_false_positive_on_legitimate_acot_absent_build():
    # The whole point of zz_giga_compat_overwrite_me.txt: every @acot_tier* Gigastructures
    # itself references must already be defined by the compat file alone, with no ACOT
    # vendored. This is a regression test for that guarantee, not just a design claim.
    giga_compat = parse_file(
        FIXTURES_ROOT / "gigastructures" / "common" / "scripted_variables" / "zz_giga_compat_overwrite_me.txt"
    )
    referencing_tech = parse_file(FIXTURES_ROOT / "gigastructures" / "giga_17_alternative_mega_build.txt")
    table = build_variable_table([giga_compat])
    errors = table.validate_all([referencing_tech])
    undefined_acot_errors = [
        e for e in errors if isinstance(e, UndefinedVariableError) and e.name.startswith("acot_tier")
    ]
    assert undefined_acot_errors == []


# ---------------------------------------------------------------------------
# Invalid (non-scalar, non-reference) variable values.
# ---------------------------------------------------------------------------


def test_block_valued_variable_is_an_error_not_a_silent_pass_through():
    doc = parse_text("@x = { 1 2 3 }\n", path="<memory>")
    table = build_variable_table([doc])
    with pytest.raises(InvalidVariableValueError):
        table.resolve("x")


# ---------------------------------------------------------------------------
# iter_variable_references: finds references at any depth, in both definitions and usages.
# ---------------------------------------------------------------------------


def test_iter_variable_references_finds_nested_reference():
    doc = parse_file(FIXTURES_ROOT / "gigastructures" / "giga_17_alternative_mega_build.txt")
    refs = list(iter_variable_references(doc))
    names = {r.name for r in refs}
    assert "giga_amb_flag" in names
    # This file also uses @tier3cost1 etc. at shallower depth — confirms the walk isn't
    # accidentally restricted to one nesting level.
    assert len(refs) > 5


def test_iter_variable_references_finds_variable_to_variable_reference_in_definitions():
    doc = parse_file(FIXTURES_ROOT / "variables" / "reference-chain.txt")
    refs = list(iter_variable_references(doc))
    names = {r.name for r in refs}
    assert names == {"chain_middle", "chain_base"}  # chain_base=1000 has no reference in it


# ---------------------------------------------------------------------------
# validate_all: eager, whole-corpus, batched — not stop-at-first-error.
# ---------------------------------------------------------------------------


def test_validate_all_batches_every_error_not_just_the_first():
    doc = parse_text("@a = @missing_one\n@b = @missing_two\n", path="<memory>")
    table = build_variable_table([doc])
    errors = table.validate_all([doc])
    assert len(errors) == 2
    assert {e.name for e in errors if isinstance(e, UndefinedVariableError)} == {"missing_one", "missing_two"}


def test_validate_all_deduplicates_a_cycle_reached_from_multiple_usage_sites():
    cycle_doc = parse_text("@x = @y\n@y = @x\n", path="cycle.txt")
    usage_doc = parse_text("tech_a = { cost = @x }\ntech_b = { cost = @x }\n", path="usage.txt")
    table = build_variable_table([cycle_doc])
    errors = table.validate_all([cycle_doc, usage_doc])
    cycle_errors = [e for e in errors if isinstance(e, VariableCycleError)]
    # Reached from tech_a's usage, tech_b's usage, and the cycle's own definitions — still one
    # reported error, not three.
    assert len(cycle_errors) == 1
