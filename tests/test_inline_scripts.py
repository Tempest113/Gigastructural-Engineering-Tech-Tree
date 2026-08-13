"""Tests for pipeline.inline_scripts — inline_script expansion.

Uses real fixtures for the shapes the corpus actually has (bare/structured invocation,
mid-token substitution, key-position substitution, block splice), and hand-constructed
parse_text cases for the failure paths the corpus has zero live cases of (cycles, depth/size
limits) — mirroring how pipeline/variables.py's tests are split.
"""

from pathlib import Path

import pytest

from tests.conftest import FIXTURES_ROOT

from pipeline.clausewitz import parse_file, parse_text
from pipeline.clausewitz.nodes import Assignment, Block, Identifier, NumberLiteral, ParameterReference, StringLiteral, VariableReference
from pipeline.inline_scripts import (
    MAX_EXPANSION_DEPTH,
    MAX_EXPANDED_SIZE,
    ExpansionDepthExceededError,
    ExpansionSizeExceededError,
    InlineScriptCycleError,
    ScriptDefinition,
    UnresolvedScriptError,
    collect_scripts,
    expand_document,
)


def _script_from_fixture(dest_relative: str, real_path: str) -> tuple[str, str, str]:
    """Build a (path, source_file, raw_text) entry, as collect_scripts expects, from a fixture
    file on disk. `real_path` is the logical `script = ...` path a technology would reference."""
    full = FIXTURES_ROOT / dest_relative
    return real_path, str(full), full.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# collect_scripts: last-definition-wins, in load order (same shape as pipeline.variables).
# ---------------------------------------------------------------------------


def test_duplicate_script_path_last_source_wins():
    entries = [
        ("x/y", "source_a.txt", "modifier = { factor = 1 }"),
        ("x/y", "source_b.txt", "modifier = { factor = 2 }"),
    ]
    table = collect_scripts(entries)
    assert table["x/y"].source_path == "source_b.txt"
    assert "factor = 2" in table["x/y"].raw_text


# ---------------------------------------------------------------------------
# Real corpus: bare invocation.
# ---------------------------------------------------------------------------


def test_bare_invocation_expands_and_splices():
    tech_doc = parse_file(FIXTURES_ROOT / "gigastructures" / "giga_12_asteroid_artillery.txt")
    scripts = collect_scripts(
        [
            _script_from_fixture(
                "gigastructures/common/inline_scripts/technology/tech_weight_boni/defensive_tech_weight_bonus.txt",
                "technology/tech_weight_boni/defensive_tech_weight_bonus",
            ),
            _script_from_fixture(
                "stellaris/common/inline_scripts/technologies/rare_technologies_weight_modifiers.txt",
                "technologies/rare_technologies_weight_modifiers",
            ),
        ]
    )
    expanded, report = expand_document(tech_doc, scripts)

    # No inline_script assignment survives anywhere in the expanded tree.
    assert not _find_key_anywhere(expanded.items, "inline_script")
    # The target's own content (a `modifier` field) is now present, spliced in.
    assert _find_key_anywhere(expanded.items, "modifier")
    assert report.missing_parameters == []


# ---------------------------------------------------------------------------
# Real corpus: structured invocation whose `script = ...` value is quoted.
# ---------------------------------------------------------------------------


def test_quoted_structured_script_path_resolves_to_the_same_file_as_a_bare_path():
    # stellaris/common/inline_scripts/buildings/regular_empire_capital_jobs.txt itself invokes
    # `inline_script = { script = "jobs/politician_add" AMOUNT = $AMOUNT$ }` — a real, shipped
    # quoted structured script path. Before the fix, the quotes were carried into the lookup
    # key (`_raw_source_text` on a StringLiteral re-wraps it in quotes), so this always raised
    # UnresolvedScriptError against a script that does exist under the unquoted path.
    tech_doc = parse_text(
        "tech_x = {\n\tinline_script = {\n\t\tscript = buildings/regular_empire_capital_jobs\n\t\tAMOUNT = 5\n\t}\n}\n",
        path="usage.txt",
    )
    scripts = collect_scripts(
        [
            _script_from_fixture(
                "stellaris/common/inline_scripts/buildings/regular_empire_capital_jobs.txt",
                "buildings/regular_empire_capital_jobs",
            ),
            _script_from_fixture(
                "stellaris/common/inline_scripts/jobs/politician_add.txt",
                "jobs/politician_add",
            ),
        ]
    )
    expanded, report = expand_document(tech_doc, scripts)

    tech = _find_assignment(expanded.items, "tech_x")
    assert not _find_key_anywhere(tech.value.items, "inline_script")
    # politician_add's own content (job_politician_add, substituted with the outer AMOUNT) is
    # spliced in — proof the quoted path actually resolved rather than failing.
    job = _find_assignment_anywhere(tech.value.items, "job_politician_add")
    assert isinstance(job.value, NumberLiteral)
    assert job.value.value == 5


# ---------------------------------------------------------------------------
# Real corpus: bare invocation whose path is quoted.
# ---------------------------------------------------------------------------


def test_quoted_bare_script_path_resolves_to_the_same_file_as_an_unquoted_path():
    # stellaris/common/technology/00_leviathans_tech.txt's tech_dragon_armor has
    # `ai_weight = { inline_script = "ai/armor_preference_weight" }` — the bare form, same as
    # `inline_script = ai/armor_preference_weight`, except the path is quoted (a StringLiteral
    # value rather than an Identifier). Confirmed real: 45 instances across 6 vanilla technology
    # files, all in ai_weight blocks, all resolving to one of five trivial weight-modifier
    # helper scripts the corpus elsewhere invokes unquoted. Before the fix this raised
    # InlineScriptError ("inline_script value must be a path or a block, not StringLiteral")
    # rather than resolving.
    tech_doc = parse_file(FIXTURES_ROOT / "stellaris" / "00_leviathans_tech.txt")
    scripts = collect_scripts(
        [
            _script_from_fixture(
                "stellaris/common/inline_scripts/ai/armor_preference_weight.txt",
                "ai/armor_preference_weight",
            )
        ]
    )
    expanded, report = expand_document(tech_doc, scripts)

    tech = _find_assignment(expanded.items, "tech_dragon_armor")
    ai_weight = _find_assignment(tech.value.items, "ai_weight")
    assert not _find_key_anywhere(ai_weight.value.items, "inline_script")
    # armor_preference_weight.txt's own content (two `modifier` blocks) is spliced in — proof
    # the quoted path actually resolved rather than failing.
    modifiers = [item for item in ai_weight.value.items if isinstance(item, Assignment) and item.key_name == "modifier"]
    assert len(modifiers) == 2


# ---------------------------------------------------------------------------
# Real corpus: structured invocation with whole-token parameter substitution.
# ---------------------------------------------------------------------------


def test_structured_invocation_substitutes_whole_token_parameter():
    # giga_01_physics.txt is the whole 1133-line source file and invokes many different
    # inline_scripts across its other technologies. Only giga_tech_war_moon_specialization
    # (lines 6-34) is under test here, so it's extracted and parsed on its own via parse_text
    # rather than resolving every invocation the rest of the file happens to make.
    full_text = (FIXTURES_ROOT / "gigastructures" / "giga_01_physics.txt").read_text(encoding="utf-8")
    lines = full_text.splitlines(keepends=True)
    excerpt = "".join(lines[5:34])  # lines 6-34, 1-indexed
    assert excerpt.startswith("giga_tech_war_moon_specialization")
    tech_doc = parse_text(excerpt, path="giga_01_physics.txt")
    scripts = collect_scripts(
        [
            _script_from_fixture(
                "stellaris/common/inline_scripts/technologies/rare_technologies_weight_modifiers.txt",
                "technologies/rare_technologies_weight_modifiers",
            ),
            _script_from_fixture(
                "gigastructures/common/inline_scripts/technology/tech_weight_boni/maniacal_or_spark_tech_weight_bonus.txt",
                "technology/tech_weight_boni/maniacal_or_spark_tech_weight_bonus",
            ),
        ]
    )
    expanded, report = expand_document(tech_doc, scripts)

    # giga_tech_war_moon_specialization's weight_modifier used this invocation (NOTES.md /
    # giga_01_physics.txt line ~24-27) — after expansion, its any_member.has_technology should
    # read the literal technology name substituted in for $TECHNOLOGY$.
    tech = _find_assignment(expanded.items, "giga_tech_war_moon_specialization")
    weight_modifier = _find_assignment(tech.value.items, "weight_modifier")
    assert not _find_key_anywhere([weight_modifier], "inline_script")
    federation = _find_assignment_anywhere([weight_modifier], "federation")
    any_member = _find_assignment(federation.value.items, "any_member")
    has_tech = _find_assignment(any_member.value.items, "has_technology")
    assert isinstance(has_tech.value, Identifier)
    assert has_tech.value.name == "giga_tech_war_moon_specialization"
    assert report.missing_parameters == []


# ---------------------------------------------------------------------------
# Real corpus: the giga_mega_repeatable case — block splice, key-position and mid-token
# substitution, and a supplied parameter (`name`) that is itself never a literal top-level
# field, only ever used to build other identifiers/strings.
# ---------------------------------------------------------------------------


def test_giga_mega_repeatable_block_splice_and_mid_token_substitution():
    tech_doc = parse_file(FIXTURES_ROOT / "gigastructures" / "giga_07_repeatables_megastructures.txt")
    scripts = collect_scripts(
        [
            _script_from_fixture(
                "gigastructures/common/inline_scripts/technology/giga_mega_repeatable.txt",
                "technology/giga_mega_repeatable",
            )
        ]
    )
    expanded, report = expand_document(tech_doc, scripts)

    tech = _find_assignment(expanded.items, "giga_tech_repeatable_vanilla_dyson_cap")
    assert not _find_key_anywhere(tech.value.items, "inline_script")

    # The target's fields are now direct children of the OUTER tech's block — not nested under
    # anything named after the invocation. This is the "block splice, not value substitution"
    # behaviour the giga_mega_repeatable case specifically requires.
    area = _find_assignment(tech.value.items, "area")
    assert isinstance(area.value, Identifier) and area.value.name == "physics"

    # cost = $cost$ substituted with the invocation's raw @variable reference, verbatim.
    cost = _find_assignment(tech.value.items, "cost")
    assert isinstance(cost.value, VariableReference)
    assert cost.value.name == "giga_grand_megastructure_base_tech_cost"

    # Mid-token substitution: $name$_disabled -> vanilla_dyson_disabled (bare identifier).
    potential = _find_assignment(tech.value.items, "potential")
    not_block = _find_assignment(potential.value.items, "not")
    flag = _find_assignment(not_block.value.items, "has_global_flag")
    assert isinstance(flag.value, Identifier)
    assert flag.value.name == "vanilla_dyson_disabled"

    # Mid-token substitution inside a quoted string: "giga_$name$_capacity_increase_title".
    prereqfor_desc = _find_assignment(tech.value.items, "prereqfor_desc")
    custom = _find_assignment(prereqfor_desc.value.items, "custom")
    title = _find_assignment(custom.value.items, "title")
    assert isinstance(title.value, StringLiteral)
    assert title.value.value == "giga_vanilla_dyson_capacity_increase_title"

    # The `name` parameter itself never appears as a literal top-level field — it was consumed
    # purely as substitution input.
    assert not _find_key_anywhere(tech.value.items, "name")

    assert report.missing_parameters == []
    assert report.unused_parameters == []


# ---------------------------------------------------------------------------
# Missing / unused parameters.
# ---------------------------------------------------------------------------


def test_missing_parameter_is_a_warning_not_a_failure_and_leaves_a_visible_marker():
    doc = parse_text("tech_x = {\n\tinline_script = {\n\t\tscript = s\n\t}\n}\n", path="usage.txt")
    scripts = collect_scripts([("s", "script.txt", "field = $NEEDED$\n")])
    expanded, report = expand_document(doc, scripts)

    assert len(report.missing_parameters) == 1
    warning = report.missing_parameters[0]
    assert warning.parameter == "NEEDED"
    assert warning.script_path == "s"
    assert warning.invocation_path == "usage.txt"

    # The unresolved reference is visible in the result, not silently dropped or fabricated.
    tech = _find_assignment(expanded.items, "tech_x")
    field = _find_assignment(tech.value.items, "field")
    assert isinstance(field.value, ParameterReference)
    assert field.value.name == "NEEDED"


def test_unused_parameter_is_logged_not_discarded():
    doc = parse_text("tech_x = {\n\tinline_script = {\n\t\tscript = s\n\t\tEXTRA = 1\n\t}\n}\n", path="usage.txt")
    scripts = collect_scripts([("s", "script.txt", "field = 1\n")])
    expanded, report = expand_document(doc, scripts)

    assert len(report.unused_parameters) == 1
    info = report.unused_parameters[0]
    assert info.parameter == "EXTRA"
    assert info.script_path == "s"
    assert report.missing_parameters == []


def test_misspelled_parameter_produces_both_a_missing_and_an_unused_entry():
    # The pairing that makes a typo diagnosable: script wants $COLOR$, invocation supplies
    # $COLOUR$ (a plausible real-world misspelling mismatch).
    doc = parse_text("tech_x = {\n\tinline_script = {\n\t\tscript = s\n\t\tCOLOUR = red\n\t}\n}\n", path="usage.txt")
    scripts = collect_scripts([("s", "script.txt", "field = $COLOR$\n")])
    _, report = expand_document(doc, scripts)

    assert [w.parameter for w in report.missing_parameters] == ["COLOR"]
    assert [u.parameter for u in report.unused_parameters] == ["COLOUR"]


# ---------------------------------------------------------------------------
# Unresolved script path: hard failure.
# ---------------------------------------------------------------------------


def test_unresolved_script_path_is_a_hard_failure():
    doc = parse_text("tech_x = {\n\tinline_script = nonexistent/path\n}\n", path="usage.txt")
    with pytest.raises(UnresolvedScriptError) as excinfo:
        expand_document(doc, scripts={})
    assert excinfo.value.path == "nonexistent/path"


def test_real_zzz_overwrites_fixture_fails_with_unresolved_script_not_a_false_expansion():
    # generic_parts/giga_toggled_code is deliberately not one of our fixtures. Confirms the
    # code = "..." multi-line string content is never mistaken for a second, nested
    # inline_script invocation to resolve — the error is about the ONE real invocation only.
    doc = parse_file(FIXTURES_ROOT / "gigastructures" / "common" / "scripted_triggers" / "zzz_overwrites.txt")
    with pytest.raises(UnresolvedScriptError) as excinfo:
        expand_document(doc, scripts={})
    assert excinfo.value.path == "generic_parts/giga_toggled_code"
    assert excinfo.value.chain == []  # the top-level invocation itself, not nested


# ---------------------------------------------------------------------------
# Cycle detection: hand-authored, since the corpus has zero genuine structural cycles.
# ---------------------------------------------------------------------------


def test_direct_cycle_is_detected():
    doc = parse_text("tech_x = {\n\tinline_script = a\n}\n", path="usage.txt")
    scripts = collect_scripts(
        [
            ("a", "a.txt", "inline_script = b\n"),
            ("b", "b.txt", "inline_script = a\n"),
        ]
    )
    with pytest.raises(InlineScriptCycleError) as excinfo:
        expand_document(doc, scripts)
    assert excinfo.value.chain[0] == "a"
    assert "a" in excinfo.value.chain and "b" in excinfo.value.chain


def test_quoted_script_shaped_text_is_never_mistaken_for_a_cycle():
    # The generic_parts/giga_toggled_code idiom: a script passes its OWN name as string data
    # to a helper. Structurally this must never be treated as the script invoking itself.
    doc = parse_text("tech_x = {\n\tinline_script = a\n}\n", path="usage.txt")
    scripts = collect_scripts(
        [
            ("a", "a.txt", 'inline_script = {\n\tscript = helper\n\tcode = "\n\t\tinline_script = a\n\t"\n}\n'),
            # helper splices the caller's "code" parameter back in verbatim, matching the real
            # generic_parts/giga_toggled_code idiom (see zzz_overwrites.txt fixture).
            ("helper", "helper.txt", "code = $code$\n"),
        ]
    )
    expanded, report = expand_document(doc, scripts)
    # Expands cleanly — no cycle, no crash — and the embedded text survives verbatim as a
    # StringLiteral's value, not as a second live inline_script invocation.
    tech = _find_assignment(expanded.items, "tech_x")
    code = _find_assignment(tech.value.items, "code")
    assert isinstance(code.value, StringLiteral)
    assert "inline_script = a" in code.value.value
    assert not _find_key_anywhere(tech.value.items, "inline_script")


# ---------------------------------------------------------------------------
# Depth and size limits: hard failures, named constants, chain in the error.
# ---------------------------------------------------------------------------


def test_expansion_depth_limit_is_a_hard_failure(monkeypatch):
    monkeypatch.setattr("pipeline.inline_scripts.MAX_EXPANSION_DEPTH", 3)
    doc = parse_text("tech_x = {\n\tinline_script = s0\n}\n", path="usage.txt")
    # A chain of 5 scripts, each invoking the next — deeper than the patched limit of 3.
    entries = [(f"s{i}", f"s{i}.txt", f"inline_script = s{i + 1}\n") for i in range(5)]
    entries.append(("s5", "s5.txt", "field = 1\n"))
    scripts = collect_scripts(entries)
    with pytest.raises(ExpansionDepthExceededError) as excinfo:
        expand_document(doc, scripts)
    assert len(excinfo.value.chain) > 3


def test_expansion_size_limit_is_a_hard_failure(monkeypatch):
    monkeypatch.setattr("pipeline.inline_scripts.MAX_EXPANDED_SIZE", 5)
    doc = parse_text("tech_x = {\n\tinline_script = s\n}\n", path="usage.txt")
    big_body = "\n".join(f"field{i} = {i}" for i in range(20))
    scripts = collect_scripts([("s", "s.txt", big_body)])
    with pytest.raises(ExpansionSizeExceededError):
        expand_document(doc, scripts)


def test_max_expansion_depth_matches_documented_headroom_over_observed_max():
    # Observed real max nesting depth in the corpus is 6 (buildings/elysium chain, per
    # spec/implementation-notes.md). The constant should stay comfortably above that.
    assert MAX_EXPANSION_DEPTH > 6


# ---------------------------------------------------------------------------
# Non-mutation: the original parsed AST is untouched by expansion.
# ---------------------------------------------------------------------------


def test_original_document_is_not_mutated():
    original = parse_file(FIXTURES_ROOT / "gigastructures" / "giga_12_asteroid_artillery.txt")
    scripts = collect_scripts(
        [
            _script_from_fixture(
                "gigastructures/common/inline_scripts/technology/tech_weight_boni/defensive_tech_weight_bonus.txt",
                "technology/tech_weight_boni/defensive_tech_weight_bonus",
            ),
            _script_from_fixture(
                "stellaris/common/inline_scripts/technologies/rare_technologies_weight_modifiers.txt",
                "technologies/rare_technologies_weight_modifiers",
            ),
        ]
    )
    before = _find_key_anywhere(original.items, "inline_script")
    assert before  # sanity: the fixture does contain inline_script before expansion
    expand_document(original, scripts)
    after = _find_key_anywhere(original.items, "inline_script")
    assert after  # still there — expand_document did not mutate `original`


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _find_assignment(items, key: str) -> Assignment:
    for item in items:
        if isinstance(item, Assignment) and item.key_name == key:
            return item
    raise AssertionError(f"no assignment with key {key!r} found among {len(items)} items")


def _find_assignment_anywhere(items, key: str):
    for item in items:
        if isinstance(item, Assignment):
            if item.key_name == key:
                return item
            if isinstance(item.value, Block):
                found = _find_assignment_anywhere(item.value.items, key)
                if found is not None:
                    return found
    return None


def _find_key_anywhere(items, key: str) -> bool:
    return _find_assignment_anywhere(items, key) is not None
