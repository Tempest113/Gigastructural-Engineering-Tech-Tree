"""Fixture-driven tests for pipeline.localisation (Stage 1, per spec/00-overview.md).

Every construct here traces to a real, confirmed corpus finding from the Step 1 survey — see
each test's docstring for the source file/line and, where relevant, the raw byte count that
justified treating it as common rather than a one-off.
"""

from pathlib import Path

import pytest

from tests.localisation.conftest import LOC_FIXTURES_ROOT, parse_excerpt

from pipeline.localisation import (
    LocalisationEncodingError,
    LocalisationError,
    parse_file,
    parse_text,
)
from pipeline.localisation.nodes import (
    BracketCommand,
    ColorMarker,
    Comment,
    IconToken,
    LocEntry,
    MalformedEntry,
    VariableToken,
)

# ---------------------------------------------------------------------------
# Language header.
# ---------------------------------------------------------------------------


def test_header_declares_language():
    doc = parse_text('l_english:\nfoo: "bar"\n')
    assert doc.language == "english"


def test_missing_header_is_a_file_level_error():
    with pytest.raises(LocalisationError):
        parse_text('foo: "bar"\n')


def test_leading_blank_lines_before_header_are_tolerated():
    doc = parse_text('\n\nl_english:\nfoo: "bar"\n')
    assert doc.language == "english"


# ---------------------------------------------------------------------------
# Key syntax: version suffix, and the separator-spacing variants.
# ---------------------------------------------------------------------------


def test_versioned_key():
    doc = parse_text('l_english:\nfoo:0 "bar"\n')
    entry = doc.entries[0]
    assert entry.key == "foo"
    assert entry.version == "0"


def test_unversioned_key_is_the_dominant_acot_aot_form():
    # ACOT: 44/46 english files have zero versioned keys; AoT: 0/34 files ever use one.
    doc = parse_text('l_english:\nMESSAGE_ACOT_ARMY_UPGRADE_TITLE: "Army Tier Upgrade"\n')
    entry = doc.entries[0]
    assert entry.key == "MESSAGE_ACOT_ARMY_UPGRADE_TITLE"
    assert entry.version is None


def test_space_before_colon():
    # aot_00_events_l_english.yml:404 `precursor_situation_generic_type : "Research Development"`
    doc = parse_excerpt("aot/aot_00_events_space_before_colon_excerpt.yml")
    entry = next(e for e in doc.entries if e.key == "precursor_situation_generic_type")
    assert entry.value.raw == "Research Development"


def test_no_space_before_opening_quote():
    # giga_maginot_l_english.yml:512 `strategic_defence_command_platform_cap:"$..."`
    doc = parse_excerpt("gigastructures/giga_maginot_no_space_before_quote_excerpt.yml")
    entry = next(e for e in doc.entries if e.key == "strategic_defence_command_platform_cap")
    assert entry.value.raw == "$strategic_defence_command_platform$"


def test_no_space_before_opening_quote_and_no_version():
    # aot_00_starbase_buildings_l_english.yml:8, whole-file fixture.
    doc = parse_file(LOC_FIXTURES_ROOT / "aot" / "aot_00_starbase_buildings_l_english.yml")
    entry = next(e for e in doc.entries if e.key == "sm_command_center_enigmatic_fortress_desc")
    assert entry.version is None
    assert entry.value.raw.startswith("$sm_command_center_desc$")


KEY_CHAR_CASES = [
    ("astral_rift.3135-3140.desc.common", "dotted range-hyphen key"),
    ("NAME_VX-455", "hyphenated key"),
    ("opinion-3", "bare hyphen-suffixed key"),
]


@pytest.mark.parametrize("key,label", KEY_CHAR_CASES, ids=[c[1] for c in KEY_CHAR_CASES])
def test_confirmed_real_key_charset(key, label):
    doc = parse_text(f'l_english:\n{key}: "x"\n')
    assert doc.entries[0].key == key


# ---------------------------------------------------------------------------
# Value quoting: the first-to-last-quote rule, and its malformed counter-examples.
# ---------------------------------------------------------------------------


def test_value_with_internal_unescaped_quotes_scans_to_the_last_quote_on_the_line():
    # nemesis_content_l_english.yml:1409 `emperor.152.b:0 ""Imperial Justice" at its finest.""`
    # "scan to the next unescaped quote" (the Clausewitz rule) would truncate this to an empty
    # string; the correct rule is first-quote-to-last-quote-on-the-line.
    doc = parse_excerpt("stellaris/nemesis_content_internal_quotes_excerpt.yml")
    entry = next(e for e in doc.entries if e.key == "emperor.152.b")
    # Source line: `emperor.152.b:0 ""Imperial Justice" at its finest.""` -- 5 literal '"'
    # characters. First-to-last strips only the outermost pair; the internal trailing quote
    # (before the final closing one) is real content, preserved.
    assert entry.value.raw == '"Imperial Justice" at its finest."'


def test_value_with_many_internal_quotes_and_a_trailing_comment():
    text = 'l_english:\nk:0 ""a" b "c" d"" #trailing comment\n'
    doc = parse_text(text)
    entry = doc.entries[0]
    assert entry.value.raw == '"a" b "c" d"'


def test_escaped_quote_is_preserved_verbatim_in_raw():
    # giga_l_english_excerpt.yml already covers this (SHIP_AURA_PLANET_DESC), reused here.
    text = 'l_english:\nk:0 "she said \\"hello\\" to me"\n'
    doc = parse_text(text)
    assert doc.entries[0].value.raw == 'she said \\"hello\\" to me'


def test_missing_closing_quote_is_reported_not_raised():
    # acot_00_herculean_events_l_english.yml:219 — genuinely no closing quote on the line or
    # either of the two blank lines that follow.
    doc = parse_excerpt("acot/acot_herculean_missing_close_quote_excerpt.yml")
    assert len(doc.malformed) == 1
    m = doc.malformed[0]
    assert m.reason == "missing closing quote"
    assert "acot_herculean_built_score" in m.raw_line
    # the well-formed entries on either side still parsed.
    keys = {e.key for e in doc.entries}
    assert "acot_herculean_events.8.name" in keys
    assert "acot_is_system_owned_by_progenitor_empire" in keys


def test_missing_opening_quote_is_reported_not_raised():
    # acot_00_components_weapons_l_english.yml:1926 `ACOT_SC_GUNSHIP_4_DESC: Gunship"`
    doc = parse_excerpt("acot/acot_gunship_missing_open_quote_excerpt.yml")
    malformed_keys = [m.raw_line for m in doc.malformed]
    assert any("ACOT_SC_GUNSHIP_4_DESC" in line for line in malformed_keys)
    assert doc.malformed[0].reason == "missing opening quote"
    # the neighbouring well-formed entries still parsed.
    keys = {e.key for e in doc.entries}
    assert "ACOT_SC_GUNSHIP_5_DESC" in keys


def test_genuinely_unquoted_value():
    # acot_05_the_shadow_events_l_english.yml:40 `acot_omegan_blessed: Blessed By Light`
    doc = parse_excerpt("acot/acot_omegan_blessed_unquoted_value_excerpt.yml")
    entry = next(e for e in doc.entries if e.key == "acot_omegan_blessed")
    assert entry.value.raw == "Blessed By Light"
    assert entry.value.quoted is False


def test_unexpected_trailing_content_after_close_quote_is_malformed():
    doc = parse_text('l_english:\nk:0 "value" garbage\n')
    assert len(doc.malformed) == 1
    assert "unexpected content" in doc.malformed[0].reason


def test_trailing_hash_comment_after_value_is_not_malformed():
    doc = parse_text('l_english:\nk:0 "value" # a real trailing comment\n')
    assert doc.malformed == []
    assert doc.entries[0].value.raw == "value"


# ---------------------------------------------------------------------------
# Markup: colour codes, icon tokens, variable substitution, bracket commands.
# ---------------------------------------------------------------------------


def test_color_span_open_and_close_are_independent_unbalanced_markers():
    doc = parse_text('l_english:\nk:0 "§Yhello§!world§R!"\n')
    spans = doc.entries[0].value.spans
    colors = [s for s in spans if isinstance(s, ColorMarker)]
    assert [c.code for c in colors] == ["Y", None, "R"]


def test_color_span_with_no_matching_close_is_preserved_not_rejected():
    doc = parse_text('l_english:\nk:0 "§Yhello"\n')
    colors = [s for s in doc.entries[0].value.spans if isinstance(s, ColorMarker)]
    assert colors == [ColorMarker(code="Y", start=0, end=2)]


def test_icon_token_plain():
    doc = parse_text('l_english:\nk:0 "£energy£ cost"\n')
    icons = [s for s in doc.entries[0].value.spans if isinstance(s, IconToken)]
    assert icons[0].inner == "energy"


def test_icon_token_pipe_parameterised():
    # apocalypse_l_english.yml:350 `£fleet_status|2£`
    doc = parse_excerpt("stellaris/apocalypse_pipe_icon_param_excerpt.yml")
    entry = next(e for e in doc.entries if e.key == "FLEET_MANAGER_SHIP_DESIGN_UPGRADABLE_COUNT")
    icons = [s for s in entry.value.spans if isinstance(s, IconToken)]
    assert icons[0].inner == "fleet_status|2"


def test_icon_token_with_embedded_dollar_parameter():
    # main_3_l_english.yml:1364 `£leader_skill|$LEVEL$£`
    doc = parse_excerpt("stellaris/main_3_pipe_format_excerpt.yml")
    entry = next(e for e in doc.entries if e.key == "SKILL_VALUE")
    icons = [s for s in entry.value.spans if isinstance(s, IconToken)]
    assert icons[0].inner == "leader_skill|$LEVEL$"


def test_icon_token_trailing_space_inside_delimiters_preserved():
    # tutorial_l_english.yml:540 `£unity £` — a real typo in Paradox's own text.
    doc = parse_text('l_english:\nk:0 "£unity £§YUnity§!"\n')
    icons = [s for s in doc.entries[0].value.spans if isinstance(s, IconToken)]
    assert icons[0].inner == "unity "


def test_variable_token_plain_identifier():
    doc = parse_text('l_english:\nk:0 "$gc_mega$"\n')
    variables = [s for s in doc.entries[0].value.spans if isinstance(s, VariableToken)]
    assert variables[0].inner == "gc_mega"
    assert variables[0].is_scripted_variable is False


def test_variable_token_dotted_event_id_reference():
    doc = parse_text('l_english:\nk:0 "$crisis.2502.name$"\n')
    variables = [s for s in doc.entries[0].value.spans if isinstance(s, VariableToken)]
    assert variables[0].inner == "crisis.2502.name"


def test_variable_token_pipe_format_suffix():
    doc = parse_text('l_english:\nk:0 "$FLEET_COUNT|Y$"\n')
    variables = [s for s in doc.entries[0].value.spans if isinstance(s, VariableToken)]
    assert variables[0].inner == "FLEET_COUNT|Y"


def test_variable_token_scripted_variable_cross_reference_is_flagged_not_resolved():
    # grand_archive_mutations_l_english.yml:689 `$@shield_nullification_high|0%$` — a genuine
    # cross-reference into the Clausewitz @variable namespace.
    doc = parse_excerpt("stellaris/grand_archive_mutations_scripted_variable_ref_excerpt.yml")
    entry = next(e for e in doc.entries if e.key == "CAMOUFLAGE_1_TOOLTIP")
    variables = [s for s in entry.value.spans if isinstance(s, VariableToken)]
    scripted = next(v for v in variables if v.is_scripted_variable)
    assert scripted.inner == "@shield_nullification_high|0%"
    # not resolved -- the '@' sigil and the raw text are preserved exactly as authored.


def test_bracket_command_bare_dotted_chain():
    doc = parse_text('l_english:\nk:0 "[Root.GetName]"\n')
    brackets = [s for s in doc.entries[0].value.spans if isinstance(s, BracketCommand)]
    assert brackets[0].inner == "Root.GetName"
    assert brackets[0].children == []


def test_bracket_command_quoted_concept_link():
    doc = parse_text("l_english:\nk:0 \"['concept_technician']\"\n")
    brackets = [s for s in doc.entries[0].value.spans if isinstance(s, BracketCommand)]
    assert brackets[0].inner == "'concept_technician'"


def test_bracket_command_two_argument_comma_form():
    doc = parse_text("l_english:\nk:0 \"['concept_pc_frozen', Frozen Worlds]\"\n")
    brackets = [s for s in doc.entries[0].value.spans if isinstance(s, BracketCommand)]
    assert brackets[0].inner == "'concept_pc_frozen', Frozen Worlds"


def test_bracket_command_genuine_nesting():
    # civic_and_origin_concepts_l_english.yml:60
    # ['concept_roboticist', [roboticist.GetName]]
    doc = parse_excerpt("stellaris/civic_and_origin_concepts_nested_bracket_excerpt.yml")
    entry = next(e for e in doc.entries if e.key == "concept_robot_assembly_plant_desc")
    brackets = [s for s in entry.value.spans if isinstance(s, BracketCommand)]
    nested = next(b for b in brackets if "concept_roboticist" in b.inner)
    assert len(nested.children) == 1
    assert nested.children[0].inner == "roboticist.GetName"


def test_dollar_spans_are_adjacent_not_nested():
    # origins_l_english.yml:7 `$HOMEWORLD$$TABBED_NEW_LINE$` — confirmed real, back-to-back.
    doc = parse_text('l_english:\nk:0 "$HOMEWORLD$$TABBED_NEW_LINE$"\n')
    variables = [s for s in doc.entries[0].value.spans if isinstance(s, VariableToken)]
    assert [v.inner for v in variables] == ["HOMEWORLD", "TABBED_NEW_LINE"]


# ---------------------------------------------------------------------------
# Comments, blank lines.
# ---------------------------------------------------------------------------


def test_comment_preserved_verbatim():
    doc = parse_text('l_english:\n# a comment §H not live markup\nk:0 "v"\n')
    comment = next(i for i in doc.items if isinstance(i, Comment))
    assert comment.text == " a comment §H not live markup"


def test_blank_lines_produce_no_items():
    doc = parse_text('l_english:\n\n\nk:0 "v"\n\n')
    assert len(doc.items) == 1


# ---------------------------------------------------------------------------
# Encoding: BOM, CRLF vs LF, and the one non-UTF-8 case (hand-authored, no corpus evidence for
# it, but CLAUDE.md requires failing loudly rather than silently mangling it if one ever appears).
# ---------------------------------------------------------------------------


def test_bom_and_crlf_real_file_parses_cleanly():
    # acot_00_army_l_english.yml is BOM + CRLF + unversioned keys, all three at once.
    doc = parse_file(LOC_FIXTURES_ROOT / "acot" / "acot_00_army_unversioned_crlf_excerpt.yml")
    assert doc.language == "english"
    assert len(doc.entries) >= 5


def test_windows_1252_fails_as_an_encoding_error_not_a_silent_mangle():
    path = LOC_FIXTURES_ROOT / "malformed" / "windows-1252_l_english.yml"
    with pytest.raises(LocalisationEncodingError) as excinfo:
        parse_file(path)
    assert "utf-8" in str(excinfo.value).lower() or "encod" in str(excinfo.value).lower()
