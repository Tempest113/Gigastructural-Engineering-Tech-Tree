"""
Fixture-driven tests for the Clausewitz tokeniser/parser (Stage 1, per spec/00-overview.md).

Scope: this parser handles Clausewitz script (`common/technology/**/*.txt` and the
`common/scripted_variables/`, `common/inline_scripts/`, `common/scripted_triggers/` files
those technologies reference). It does NOT handle localisation YAML
(`tests/fixtures/localisation/**/*.yml`) — 00-overview.md lists "Parse all technology files
into a lossless AST" and "Parse localisation YAML" as two separate Stage 1 concerns, and only
the first is in scope here. `§`/`£`/`$VAR$` tokens live exclusively in the YAML files (verified
during fixture curation, see tests/fixtures/NOTES.md) and never appear in Clausewitz script, so
there is nothing localisation-shaped for this parser to reject or accept.

This parser does not resolve `@variables` or expand `inline_script` — both are separate,
not-yet-built passes. A `@variable` reference must parse as an opaque reference node; an
`inline_script` line is just an ordinary assignment whose value happens to look like a path.
"""

from pathlib import Path

import pytest

from tests.conftest import FIXTURES_ROOT

from pipeline.clausewitz import ClausewitzError, parse_file, parse_text
from pipeline.clausewitz.nodes import (
    Assignment,
    Block,
    Comment,
    Identifier,
    NumberLiteral,
    StringLiteral,
    VariableReference,
)

# ---------------------------------------------------------------------------
# Fixture discovery
# ---------------------------------------------------------------------------

# Every directory that holds real (or malformed-but-Clausewitz-shaped) `.txt` script,
# discovered recursively so the dependency-closure files under common/ are included
# automatically. Deliberately excludes tests/fixtures/localisation/ (YAML, not Clausewitz).
_SCRIPT_DIRS = ["gigastructures", "stellaris", "acot", "aot"]


def _discover(*dirnames: str, pattern: str = "*.txt") -> list[Path]:
    paths: list[Path] = []
    for d in dirnames:
        root = FIXTURES_ROOT / d
        if root.is_dir():
            paths.extend(sorted(root.rglob(pattern)))
    return paths


VALID_SCRIPT_FIXTURES = _discover(*_SCRIPT_DIRS)

VALID_ENCODING_FIXTURES = [
    FIXTURES_ROOT / "encoding" / "utf8-bom.txt",
    FIXTURES_ROOT / "encoding" / "lf.txt",
    FIXTURES_ROOT / "encoding" / "crlf.txt",
]

MALFORMED_FIXTURES = sorted((FIXTURES_ROOT / "malformed").glob("*.txt"))

# windows-1252.txt is a Clausewitz-shaped file that is *not valid UTF-8* — it belongs in the
# "must fail loudly" set alongside malformed/, not the "must parse" set.
INVALID_ENCODING_FIXTURES = [FIXTURES_ROOT / "encoding" / "windows-1252.txt"]

ALL_MUST_PARSE = VALID_SCRIPT_FIXTURES + VALID_ENCODING_FIXTURES
ALL_MUST_FAIL = MALFORMED_FIXTURES + INVALID_ENCODING_FIXTURES


def _require_fixtures(paths: list[Path]) -> None:
    if not paths:
        pytest.fail(
            "tests/fixtures/ appears empty. Run `python tools/regenerate_fixtures.py` "
            "first (with vendor/ populated) — see tests/fixtures/NOTES.md."
        )


_require_fixtures(VALID_SCRIPT_FIXTURES)
_require_fixtures(MALFORMED_FIXTURES)


# ---------------------------------------------------------------------------
# Every fixture that should parse: it must parse, at all, without raising.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", ALL_MUST_PARSE, ids=lambda p: str(p.relative_to(FIXTURES_ROOT)))
def test_every_valid_fixture_parses_without_error(path: Path):
    doc = parse_file(path)
    assert doc.items, f"{path} parsed to an empty document (expected at least one statement)"


@pytest.mark.parametrize("path", ALL_MUST_PARSE, ids=lambda p: str(p.relative_to(FIXTURES_ROOT)))
def test_every_valid_fixture_has_only_assignments_and_comments_at_root(path: Path):
    doc = parse_file(path)
    for item in doc.items:
        assert isinstance(item, (Assignment, Comment)), (
            f"{path}: document root contained a bare {type(item).__name__}; "
            "root must be assignments/comments only"
        )


# ---------------------------------------------------------------------------
# malformed/ and the invalid-encoding fixture: each must fail, loudly, naming file + line.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", ALL_MUST_FAIL, ids=lambda p: str(p.relative_to(FIXTURES_ROOT)))
def test_every_malformed_fixture_raises_clausewitz_error(path: Path):
    with pytest.raises(ClausewitzError) as excinfo:
        parse_file(path)
    err = excinfo.value
    assert str(path) in str(err) or path.name in str(err), (
        f"error message does not name the offending file: {err}"
    )
    assert err.line is not None and err.line >= 1, (
        f"error does not name a line number: {err}"
    )


def test_unclosed_brace_names_the_unclosed_block():
    path = FIXTURES_ROOT / "malformed" / "unclosed-brace.txt"
    with pytest.raises(ClausewitzError) as excinfo:
        parse_file(path)
    err = excinfo.value
    # Outer tech block opens at line 1; the file ends with it (and weight_modifier) unclosed.
    assert err.line >= 1
    assert "unclosed" in str(err).lower() or "end of file" in str(err).lower() or "eof" in str(err).lower()


def test_unexpected_closing_brace_points_at_the_stray_brace():
    path = FIXTURES_ROOT / "malformed" / "unexpected-closing-brace.txt"
    with pytest.raises(ClausewitzError) as excinfo:
        parse_file(path)
    err = excinfo.value
    assert err.line == 13, f"expected the stray '}}' on line 13, got line {err.line}"


def test_unterminated_string_points_at_the_opening_quote_line():
    path = FIXTURES_ROOT / "malformed" / "unterminated-string.txt"
    with pytest.raises(ClausewitzError) as excinfo:
        parse_file(path)
    err = excinfo.value
    assert err.line == 6, f"expected the string's start line 6, got line {err.line}"
    assert "string" in str(err).lower()


def test_stray_token_points_at_the_stray_identifier_line():
    path = FIXTURES_ROOT / "malformed" / "stray-token.txt"
    with pytest.raises(ClausewitzError) as excinfo:
        parse_file(path)
    err = excinfo.value
    assert err.line == 9, f"expected the stray identifier's line 9, got line {err.line}"


def test_truncated_file_reports_unclosed_blocks_not_a_crash():
    path = FIXTURES_ROOT / "malformed" / "truncated-file.txt"
    with pytest.raises(ClausewitzError) as excinfo:
        parse_file(path)
    err = excinfo.value
    assert err.line >= 1


def test_windows_1252_fails_as_an_encoding_error_not_a_silent_mangle():
    path = FIXTURES_ROOT / "encoding" / "windows-1252.txt"
    with pytest.raises(ClausewitzError) as excinfo:
        parse_file(path)
    err = excinfo.value
    assert "encod" in str(err).lower() or "utf-8" in str(err).lower() or "decode" in str(err).lower()


# ---------------------------------------------------------------------------
# encoding/: BOM and CRLF must be transparent — same AST as the LF baseline.
# ---------------------------------------------------------------------------


def test_utf8_bom_does_not_leak_into_the_first_token():
    doc = parse_file(FIXTURES_ROOT / "encoding" / "utf8-bom.txt")
    first = doc.items[0]
    assert isinstance(first, Assignment)
    assert first.key.name == "tech_encoding_utf8_bom"


def test_crlf_and_lf_fixtures_parse_to_the_same_ast_shape():
    lf_doc = parse_file(FIXTURES_ROOT / "encoding" / "lf.txt")
    crlf_doc = parse_file(FIXTURES_ROOT / "encoding" / "crlf.txt")

    def shape(doc):
        # Structural shape only (keys/operators/value kinds) — line numbers legitimately
        # differ between line-ending, err, no they don't differ, but we don't want a change
        # in *how* we compare line numbers to hide a real \r-leaking-into-a-value bug either.
        return [
            (a.key.name, a.operator, type(a.value).__name__)
            for a in doc.items
            if isinstance(a, Assignment)
        ]

    assert shape(lf_doc) == shape(crlf_doc)

    # The specific risk called out in NOTES.md: a trailing \r must never end up inside a
    # parsed value (e.g. tier's value must be the clean identifier/number, not "2\r").
    def leaf_values(doc):
        out = []
        for item in doc.items:
            if isinstance(item, Assignment) and isinstance(item.value, Block):
                for sub in item.value.items:
                    if isinstance(sub, Assignment):
                        out.append(sub.value)
        return out

    for v in leaf_values(crlf_doc):
        if isinstance(v, (Identifier, StringLiteral)):
            assert "\r" not in v.value if isinstance(v, StringLiteral) else "\r" not in v.name


# ---------------------------------------------------------------------------
# Duplicate keys preserved as ordered lists, not collapsed into a dict.
# ---------------------------------------------------------------------------


def test_duplicate_modifier_keys_preserved_in_order():
    # giga_09_ehof_other.txt, tech_abstract_1's weight_modifier: eleven `modifier = {...}`
    # entries in one block (see NOTES.md). All eleven must survive, in source order.
    doc = parse_file(FIXTURES_ROOT / "gigastructures" / "giga_09_ehof_other.txt")
    tech = _find_assignment(doc.items, "tech_abstract_1")
    weight_modifier = _find_assignment(tech.value.items, "weight_modifier")
    modifiers = [a for a in weight_modifier.value.items if isinstance(a, Assignment) and a.key.name == "modifier"]
    assert len(modifiers) == 11


def test_duplicate_technology_swap_keys_preserved_with_distinct_payloads():
    # zz_giga_tech_overwrites.txt: `technology_swap` appears three times in tech_ring_world
    # with different `name` values (lines 16, 38, 54).
    doc = parse_file(FIXTURES_ROOT / "gigastructures" / "zz_giga_tech_overwrites.txt")
    tech = _find_assignment(doc.items, "tech_ring_world")
    swaps = [a for a in tech.value.items if isinstance(a, Assignment) and a.key.name == "technology_swap"]
    assert len(swaps) == 3
    names = [_find_assignment(swap.value.items, "name").value.name for swap in swaps]
    assert names == [
        "giga_tech_ring_world_swap",
        "giga_tech_ring_world_swap_no_habitables",
        "giga_tech_ring_world_swap_no_habitables_bio",
    ]


def test_duplicate_keys_grouped_view_is_a_dict_of_ordered_lists():
    doc = parse_file(FIXTURES_ROOT / "gigastructures" / "giga_09_ehof_other.txt")
    tech = _find_assignment(doc.items, "tech_abstract_1")
    weight_modifier = _find_assignment(tech.value.items, "weight_modifier")
    grouped = weight_modifier.value.assignments_by_key()
    assert len(grouped["modifier"]) == 11
    assert grouped["modifier"] == [
        a for a in weight_modifier.value.items if isinstance(a, Assignment) and a.key.name == "modifier"
    ]


# ---------------------------------------------------------------------------
# Comments: preserved with position; never mistaken for live directives; brace-safe.
# ---------------------------------------------------------------------------


def test_wholly_commented_file_parses_to_an_empty_document():
    # 000_documentation.txt is entirely `#`-prefixed. Must not error, must not fabricate
    # statements, and every line should surface as a Comment.
    doc = parse_file(FIXTURES_ROOT / "stellaris" / "000_documentation.txt")
    assert all(isinstance(item, Comment) for item in doc.items)
    assert len(doc.items) > 0


def test_braces_inside_comments_do_not_affect_block_nesting():
    # 000_documentation.txt's commented-out example script contains literal `{`/`}` inside
    # comment text (e.g. "# cost = {"). A naive brace counter that doesn't recognise comments
    # first would desync. Since the whole file is comments, a desynced counter would either
    # raise (unclosed/unexpected brace) or the parse would otherwise misbehave; either way,
    # asserting a clean, fully-commented result rules it out.
    doc = parse_file(FIXTURES_ROOT / "stellaris" / "000_documentation.txt")
    assert any("{" in c.text or "}" in c.text for c in doc.items), (
        "fixture no longer contains a brace-in-comment case — test needs a new source line"
    )


def test_commented_out_directive_is_not_treated_as_live():
    # giga_03_engineering.txt lines 105-106 are a commented-out `inline_script` alternative;
    # lines 72/135/170/205 carry the live, identical-looking directive uncommented.
    doc = parse_file(FIXTURES_ROOT / "gigastructures" / "giga_03_engineering.txt")
    live_inline_scripts = _count_live_inline_scripts(doc.items)
    assert live_inline_scripts >= 4  # the four active occurrences NOTES.md documents
    comment_texts = _collect_comment_texts(doc.items)
    assert any("inline_script" in t for t in comment_texts), (
        "expected to find the commented-out inline_script line as a Comment, not an Assignment"
    )


# ---------------------------------------------------------------------------
# Comparison operators other than `=`.
# ---------------------------------------------------------------------------


def test_bare_comparison_operators_parse_with_correct_operator_and_operands():
    # giga_17_alternative_mega_build.txt line 22 (inside weight_modifier > modifier > nor):
    # count_owned_megastructure = { count > 0 limit = {...} }
    doc = parse_file(FIXTURES_ROOT / "gigastructures" / "giga_17_alternative_mega_build.txt")
    count_check = _find_assignment_anywhere(doc.items, "count_owned_megastructure", value_type=Block)
    assert count_check is not None
    count_cmp = _find_assignment(count_check.value.items, "count")
    assert count_cmp.operator == ">"
    assert isinstance(count_cmp.value, NumberLiteral)
    assert count_cmp.value.value == 0


def test_value_shorthand_comparison_nested_several_scopes_deep():
    # 00_shroud_tech.txt: `opinion = { who = root value < 0 }`, several scopes below `OR`/`AND`.
    # "value" here is an ordinary key (an identifier literally spelled "value"), not special
    # syntax — this asserts the parser treats it exactly like any other Assignment.
    doc = parse_file(FIXTURES_ROOT / "stellaris" / "00_shroud_tech.txt")
    found = _find_operator_assignment_anywhere(doc.items, key="value", operator="<")
    assert found is not None, "expected to find a `value < ...` comparison somewhere in the file"
    assert isinstance(found.value, NumberLiteral)
    assert found.value.value == 0


def test_ge_and_le_operators_parse():
    # giga_06_special_project_tech.txt: `count >= 3/4/5`
    doc = parse_file(FIXTURES_ROOT / "gigastructures" / "giga_06_special_project_tech.txt")
    ge_found = _find_operator_assignment_anywhere(doc.items, key="count", operator=">=")
    assert ge_found is not None


# ---------------------------------------------------------------------------
# Negative numbers, empty blocks, quoted vs. bare list values.
# ---------------------------------------------------------------------------


def test_negative_and_positive_number_literals():
    # giga_04_repeatables.txt: `levels = -1` (infinite) and `levels = 40` (finite).
    doc = parse_file(FIXTURES_ROOT / "gigastructures" / "giga_04_repeatables.txt")
    levels = [
        a.value.value
        for item in doc.items
        if isinstance(item, Assignment)
        for a in item.value.items
        if isinstance(a, Assignment) and a.key.name == "levels"
    ]
    assert -1 in levels
    assert 40 in levels
    for v in levels:
        assert isinstance(v, int)


def test_empty_block_parses_to_a_block_with_no_items():
    # giga_17_alternative_mega_build.txt line 7: `prerequisites = {}` — zero whitespace inside.
    doc = parse_file(FIXTURES_ROOT / "gigastructures" / "giga_17_alternative_mega_build.txt")
    tech = doc.items[0]
    prereqs = _find_assignment(tech.value.items, "prerequisites")
    assert isinstance(prereqs.value, Block)
    assert prereqs.value.items == []


def test_bare_path_like_value_with_slashes_tokenises_as_one_identifier():
    # inline_script = technology/tech_weight_boni/defensive_tech_weight_bonus — unquoted,
    # contains '/'. Must be one Identifier token, not split at the slashes.
    doc = parse_file(FIXTURES_ROOT / "gigastructures" / "giga_12_asteroid_artillery.txt")
    tech = _find_assignment(doc.items, "giga_tech_asteroid_artillery")
    weight_modifier = _find_assignment(tech.value.items, "weight_modifier")
    inline = _find_assignment(weight_modifier.value.items, "inline_script")
    assert isinstance(inline.value, Identifier)
    assert inline.value.name == "technology/tech_weight_boni/defensive_tech_weight_bonus"


def test_scope_suffixed_flag_is_one_identifier_not_a_stray_variable_reference():
    # `has_star_flag = ehof_megastructure_system@root` — the '@root' here is a scope suffix
    # attached (no whitespace) to a flag name, not a scripted-variable reference. Before the
    # fix, the tokeniser silently split this into an Identifier missing its suffix plus an
    # unrelated top-level VariableReference('root') sibling — worse than an honest parse
    # failure, since it corrupted the flag name and fabricated a bogus @variable usage.
    doc = parse_file(FIXTURES_ROOT / "gigastructures" / "common" / "scripted_triggers" / "ehof_triggers.txt")
    ehof_travel_conditions = _find_assignment(doc.items, "ehof_travel_conditions")
    not_block = _find_assignment(ehof_travel_conditions.value.items, "NOT")
    flag = _find_assignment(not_block.value.items, "has_star_flag")
    assert isinstance(flag.value, Identifier)
    assert flag.value.name == "ehof_megastructure_system@root"

    empire_has_visited = _find_assignment(doc.items, "empire_has_visited")
    flag2 = _find_assignment(empire_has_visited.value.items, "has_star_flag")
    assert isinstance(flag2.value, Identifier)
    assert flag2.value.name == "empire_has_visited@root"


def test_event_id_namespace_dot_number_is_one_identifier():
    # `country_event = { id = acot_precursor_databank.8 }` — a dotted event-id, common across
    # scripted_triggers/ and ascension_perks/ (2,142 distinct namespace.number values in the
    # rescoped corpus). Before the fix this was an outright parse failure ("unexpected
    # character '.'"), not a mis-lex — every ascension_perks/ file in the corpus used this idiom
    # and none of them could parse at all.
    doc = parse_file(FIXTURES_ROOT / "acot" / "common" / "ascension_perks" / "acot_ascension_perks.txt")
    perk = _find_assignment(doc.items, "ap_precursor_dream")
    on_enabled = _find_assignment(perk.value.items, "on_enabled")
    hidden_effect = _find_assignment(on_enabled.value.items, "hidden_effect")
    country_event = _find_assignment(hidden_effect.value.items, "country_event")
    event_id = _find_assignment(country_event.value.items, "id")
    assert isinstance(event_id.value, Identifier)
    assert event_id.value.name == "acot_precursor_databank.8"


def test_chained_dotted_scope_reference_used_as_a_plain_value_is_one_identifier():
    # `is_same_species = root.owner` — a scope-chain reference (not @-prefixed) used directly
    # as a value. 129 occurrences across the rescoped corpus (dominated by `from.owner` and
    # `root.owner`), and the specific thing blocking stellaris/common/ascension_perks/
    # 00_ascension_perks.txt from parsing after the event-id fix alone.
    doc = parse_file(FIXTURES_ROOT / "stellaris" / "common" / "ascension_perks" / "00_ascension_perks.txt")
    perk = _find_assignment(doc.items, "ap_xeno_compatibility")
    is_same_species = _find_assignment_anywhere(perk.value.items, "is_same_species")
    assert isinstance(is_same_species.value, Identifier)
    assert is_same_species.value.name == "root.owner"

    # A leading '@' (not attached to a preceding identifier) is unaffected — still an ordinary
    # scripted-variable reference.
    variable_doc = parse_text("cost = @tier1cost1\n", path="usage.txt")
    cost = _find_assignment(variable_doc.items, "cost")
    assert isinstance(cost.value, VariableReference)
    assert cost.value.name == "tier1cost1"


def test_quoted_and_bare_scalars_both_valid_as_bare_block_members():
    # prerequisites = { "tech_mega_engineering" } (quoted) vs category = { voidcraft } (bare).
    doc = parse_file(FIXTURES_ROOT / "gigastructures" / "zz_giga_tech_overwrites.txt")
    tech = _find_assignment(doc.items, "tech_ring_world")
    prereqs = _find_assignment(tech.value.items, "prerequisites")
    assert any(isinstance(v, StringLiteral) for v in prereqs.value.items)
    category = _find_assignment(tech.value.items, "category")
    assert any(isinstance(v, Identifier) for v in category.value.items)


# ---------------------------------------------------------------------------
# @variable references: preserved as opaque nodes, never resolved.
# ---------------------------------------------------------------------------


def test_key_name_handles_a_variable_reference_key():
    # Every scripted_variables statement's key is `@name = value` — a VariableReference key,
    # not an Identifier. Assignment.key_name must handle this (regression: it used to fall
    # through to `self.key.raw`, which VariableReference doesn't have).
    doc = parse_file(FIXTURES_ROOT / "gigastructures" / "common" / "scripted_variables" / "giga_amb_variables.txt")
    definition = _find_assignment(doc.items, "giga_amb_flag")
    assert isinstance(definition.key, VariableReference)
    assert definition.key_name == "giga_amb_flag"


def test_variable_reference_is_preserved_unresolved():
    doc = parse_file(FIXTURES_ROOT / "gigastructures" / "giga_04_repeatables.txt")
    tech = _find_assignment(doc.items, "giga_tech_repeatable_dimensional_storage")
    cost = _find_assignment(tech.value.items, "cost")
    assert isinstance(cost.value, VariableReference)
    assert cost.value.name  # non-empty; whatever the raw @name was, verbatim
    assert not cost.value.name.startswith("@")  # '@' is the sigil, not part of .name


def test_variable_reference_usable_as_a_nested_value_not_just_top_level_cost():
    # giga_17_alternative_mega_build.txt: has_global_flag = @giga_amb_flag, inside a nested
    # potential block, not a top-level cost/weight assignment.
    doc = parse_file(FIXTURES_ROOT / "gigastructures" / "giga_17_alternative_mega_build.txt")
    found = _find_assignment_anywhere(doc.items, key="has_global_flag", value_type=VariableReference)
    assert found is not None


def test_scripted_variable_can_resolve_to_a_bare_identifier_not_just_a_number():
    # giga_amb_variables.txt line 5: @giga_amb_flag = giga_buildcap_j — a bare, unquoted
    # identifier value, not numeric. Confirms the AST already represents this correctly at the
    # parser layer (Assignment.value is an Identifier); the resolver (not built yet) must not
    # assume every resolved scripted-variable value is a NumberLiteral.
    doc = parse_file(FIXTURES_ROOT / "gigastructures" / "common" / "scripted_variables" / "giga_amb_variables.txt")
    definition = _find_assignment(doc.items, "giga_amb_flag")
    assert isinstance(definition.value, Identifier)
    assert definition.value.name == "giga_buildcap_j"


def test_giga_amb_flag_reference_and_definition_agree_on_name():
    # The reference site (giga_17_alternative_mega_build.txt's `has_global_flag =
    # @giga_amb_flag`) and the definition site (giga_amb_variables.txt) are two independently
    # parsed files; this is the parser-layer half of "resolves through it" — proving the two
    # ASTs actually name the same variable — ahead of the resolver, which will do the lookup
    # itself once built.
    usage_doc = parse_file(FIXTURES_ROOT / "gigastructures" / "giga_17_alternative_mega_build.txt")
    reference = _find_assignment_anywhere(usage_doc.items, key="has_global_flag", value_type=VariableReference)
    assert reference is not None

    definition_doc = parse_file(FIXTURES_ROOT / "gigastructures" / "common" / "scripted_variables" / "giga_amb_variables.txt")
    definition = _find_assignment(definition_doc.items, "giga_amb_flag")

    assert reference.value.name == definition.key.name == "giga_amb_flag"
    assert isinstance(definition.value, Identifier)
    assert definition.value.name == "giga_buildcap_j"


# ---------------------------------------------------------------------------
# Multi-line strings: real, confirmed corpus-wide (917 occurrences outside
# common/technology/), not just an inline_script curiosity. Strings scan to the next
# unescaped '"' or EOF, never stopping at '\n'.
# ---------------------------------------------------------------------------


def test_multiline_string_is_captured_as_one_opaque_string_literal():
    # zzz_overwrites.txt: `code = "..."` embeds a whole nested inline_script invocation,
    # spanning several lines, as string DATA — passed to generic_parts/giga_toggled_code,
    # which conditionally splices it back in. Stage 1 must not try to parse the string's
    # contents as script; it's opaque text until whatever consumes `code` decides otherwise.
    doc = parse_file(FIXTURES_ROOT / "gigastructures" / "common" / "scripted_triggers" / "zzz_overwrites.txt")
    tech = doc.items[0]
    or_block = _find_assignment(tech.value.items, "OR")
    inline = _find_assignment(or_block.value.items, "inline_script")
    code = _find_assignment(inline.value.items, "code")
    assert isinstance(code.value, StringLiteral)
    assert "has_building = building_acot_dm_enigmatic_lab" in code.value.value
    assert "has_building = building_acot_ae_institute" in code.value.value
    # The string's own newlines are preserved, not collapsed or stripped.
    assert code.value.value.count("\n") >= 4


def test_multiline_string_without_a_closing_quote_still_fails_at_its_start_line():
    # Regression guard: allowing strings to span lines must not turn a truly unterminated
    # string into a silent multi-file scan-to-EOF with a useless error location. The existing
    # malformed/unterminated-string.txt fixture already covers this — this just confirms the
    # multi-line change didn't move the reported line.
    with pytest.raises(ClausewitzError) as excinfo:
        parse_file(FIXTURES_ROOT / "malformed" / "unterminated-string.txt")
    assert excinfo.value.line == 6


def test_multiline_string_bare_word_list_form():
    # The other real shape (00_aot_vanilla_zones.txt): a parameter value that's a multi-line
    # string containing a bare list of words, used as pseudo-list data — not code this time.
    text = (
        'tech_x = {\n'
        '\tinline_script = {\n'
        '\t\tscript = zones/example\n'
        '\t\tBUILDING_SETS = "\n'
        '\t\t\tindustrial\n'
        '\t\t\turban_automation\n'
        '\t\t\torigin\n'
        '\t\t"\n'
        '\t}\n'
        '}\n'
    )
    doc = parse_text(text, path="<memory>")
    tech = doc.items[0]
    inline = _find_assignment(tech.value.items, "inline_script")
    building_sets = _find_assignment(inline.value.items, "BUILDING_SETS")
    assert isinstance(building_sets.value, StringLiteral)
    for word in ("industrial", "urban_automation", "origin"):
        assert word in building_sets.value.value


# ---------------------------------------------------------------------------
# Deep nesting (structural + boolean).
# ---------------------------------------------------------------------------


def test_deep_boolean_nesting_four_levels():
    # 00_strategic_resources_tech.txt tech_mine_dark_matter: NOR containing AND, and NOR
    # containing any_relation containing AND.
    doc = parse_file(FIXTURES_ROOT / "stellaris" / "00_strategic_resources_tech.txt")
    tech = _find_assignment(doc.items, "tech_mine_dark_matter")
    weight_modifier = _find_assignment(tech.value.items, "weight_modifier")
    modifier = _find_assignment(weight_modifier.value.items, "modifier")
    nor = _find_assignment(modifier.value.items, "NOR")
    assert isinstance(nor.value, Block)
    and_block = _find_assignment(nor.value.items, "AND")
    assert isinstance(and_block.value, Block)
    any_relation = _find_assignment(nor.value.items, "any_relation")
    inner_and = _find_assignment(any_relation.value.items, "AND")
    assert isinstance(inner_and.value, Block)


def test_deep_structural_nesting_five_levels():
    # 00_shroud_tech.txt (see NOTES.md): OR > AND > any_owned_nonprimary_starbase >
    # solar_system > OR > AND. Several other, shallower OR blocks exist earlier in the file
    # (e.g. the sibling `OR` member's own nested any_system_within_border), so walk this exact
    # path rather than assuming the first OR/AND found anywhere is the right one.
    doc = parse_file(FIXTURES_ROOT / "stellaris" / "00_shroud_tech.txt")

    def child(items, key):
        return next((a for a in items if isinstance(a, Assignment) and a.key.name == key), None)

    def find_chain(items):
        for item in items:
            if isinstance(item, Assignment):
                if item.key.name == "OR" and isinstance(item.value, Block):
                    and1 = child(item.value.items, "AND")
                    starbase = child(and1.value.items, "any_owned_nonprimary_starbase") if and1 else None
                    solar_system = child(starbase.value.items, "solar_system") if starbase else None
                    or2 = child(solar_system.value.items, "OR") if solar_system else None
                    and2 = child(or2.value.items, "AND") if or2 else None
                    if and2 is not None:
                        return and2
                if isinstance(item.value, Block):
                    found = find_chain(item.value.items)
                    if found is not None:
                        return found
        return None

    and2 = find_chain(doc.items)
    assert and2 is not None, (
        "expected to find OR > AND > any_owned_nonprimary_starbase > solar_system > OR > AND "
        "somewhere in the file"
    )
    assert isinstance(and2.value, Block)


# ---------------------------------------------------------------------------
# Mod-over-vanilla and mod-over-mod overwrite pairs: both sides must parse the same way
# (this test suite doesn't do overwrite *resolution* — that's Stage 2 — but Stage 1 must
# hand Stage 2 two independently-correct ASTs to resolve between).
# ---------------------------------------------------------------------------


def test_overwrite_pair_both_parse_and_disagree_on_potential():
    mod_doc = parse_file(FIXTURES_ROOT / "gigastructures" / "zz_giga_tech_overwrites.txt")
    vanilla_doc = parse_file(FIXTURES_ROOT / "stellaris" / "00_megastructures.txt")
    mod_tech = _find_assignment(mod_doc.items, "tech_ring_world")
    vanilla_tech = _find_assignment(vanilla_doc.items, "tech_ring_world")
    mod_potential = _find_assignment(mod_tech.value.items, "potential")
    vanilla_potential = _find_assignment(vanilla_tech.value.items, "potential")
    # Different content is the whole point of this fixture pair (see NOTES.md) — Stage 1 must
    # not merge or silently prefer one, just hand both over intact.
    assert mod_potential.value.items != vanilla_potential.value.items


def test_mod_over_mod_overwrite_pair_both_parse_and_disagree():
    acot_doc = parse_file(FIXTURES_ROOT / "acot" / "acot_tech_precursor_gateway.txt")
    aot_doc = parse_file(FIXTURES_ROOT / "aot" / "z_aot_mega_tech_override.txt")
    acot_tech = _find_assignment(acot_doc.items, "tech_precursor_gateway")
    aot_tech = _find_assignment(aot_doc.items, "tech_precursor_gateway")
    acot_weight = _find_assignment(acot_tech.value.items, "weight")
    aot_weight = _find_assignment(aot_tech.value.items, "weight")
    # ACOT's original is `weight = 0` (NumberLiteral); AoT's override is `weight =
    # @tier5weight3` (VariableReference) — different value *kinds*, not just different
    # numbers, so compare structurally rather than assuming both are numeric.
    assert _scalar_repr(acot_weight.value) != _scalar_repr(aot_weight.value)


def _scalar_repr(node):
    return (type(node).__name__, getattr(node, "value", getattr(node, "name", None)))


# ---------------------------------------------------------------------------
# Whitespace insensitivity: tab-indented and space-indented fixtures must parse identically.
# ---------------------------------------------------------------------------


def test_space_indented_file_parses_same_as_tab_indented():
    # 00_machine_age_tech.txt uses 4-space indentation; everything else uses tabs.
    doc = parse_file(FIXTURES_ROOT / "stellaris" / "00_machine_age_tech.txt")
    assert doc.items
    assert all(isinstance(item, (Assignment, Comment)) for item in doc.items)


# ---------------------------------------------------------------------------
# parse_text: direct string parsing, for tests that don't need a fixture file.
# ---------------------------------------------------------------------------


def test_parse_text_matches_parse_file_for_simple_input():
    text = 'tech_x = {\n\tarea = physics\n\tcost = @tier1cost1\n}\n'
    doc = parse_text(text, path="<memory>")
    assert len(doc.items) == 1
    tech = doc.items[0]
    assert isinstance(tech, Assignment)
    assert tech.key.name == "tech_x"


def test_escaped_quote_inside_string_does_not_terminate_it():
    # Not exercised by any real fixture (verified during fixture curation: no .txt tech file
    # contains a backslash-escaped quote), but Paradox script generally supports it and the
    # tokeniser should not break if upstream content starts using it.
    text = 'tech_x = {\n\tdesc = "he said \\"hello\\" to me"\n}\n'
    doc = parse_text(text, path="<memory>")
    tech = doc.items[0]
    desc = _find_assignment(tech.value.items, "desc")
    assert desc.value.value == 'he said "hello" to me'


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _find_assignment(items, key: str) -> Assignment:
    for item in items:
        if isinstance(item, Assignment) and item.key.name == key:
            return item
    raise AssertionError(f"no assignment with key {key!r} found among {len(items)} items")


def _find_assignment_anywhere(items, key: str, value_type=None) -> Assignment | None:
    for item in items:
        if isinstance(item, Assignment):
            if item.key.name == key and (value_type is None or isinstance(item.value, value_type)):
                return item
            if isinstance(item.value, Block):
                found = _find_assignment_anywhere(item.value.items, key, value_type)
                if found is not None:
                    return found
    return None


def _find_operator_assignment_anywhere(items, key: str, operator: str) -> Assignment | None:
    for item in items:
        if isinstance(item, Assignment):
            if item.key.name == key and item.operator == operator:
                return item
            if isinstance(item.value, Block):
                found = _find_operator_assignment_anywhere(item.value.items, key, operator)
                if found is not None:
                    return found
    return None


def _count_live_inline_scripts(items) -> int:
    count = 0
    for item in items:
        if isinstance(item, Assignment):
            if item.key.name == "inline_script":
                count += 1
            if isinstance(item.value, Block):
                count += _count_live_inline_scripts(item.value.items)
    return count


def _collect_comment_texts(items) -> list[str]:
    out = []
    for item in items:
        if isinstance(item, Comment):
            out.append(item.text)
        elif isinstance(item, Assignment) and isinstance(item.value, Block):
            out.extend(_collect_comment_texts(item.value.items))
    return out
