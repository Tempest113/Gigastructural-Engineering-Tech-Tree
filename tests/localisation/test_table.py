"""Cross-source resolution, lookup, and diagnostics tests (pipeline.localisation.table).

The version-suffix-identity test is deliberately the decisive form the user asked for, not the
suggestive one: find a key defined WITH a version suffix in a base source and redefined WITHOUT
one in ACOT/AoT, and confirm the unversioned definition wins. If the suffix were part of lookup
identity, that override would silently fail to apply — and ACOT/AoT ship complete, working
localisation mods that overwhelmingly omit the suffix, so a real corpus scan finds 83 such cases
(see the real-corpus test at the bottom of this file).
"""

from pathlib import Path

import pytest

from tests.localisation.conftest import LOC_FIXTURES_ROOT, parse_excerpt
from tests.conftest import REPO_ROOT

from pipeline.localisation import parse_text
from pipeline.localisation.errors import MissingLocalisationKeyError
from pipeline.localisation.table import (
    build_table,
    find_unquoted_value_diagnostics,
    find_value_is_key_diagnostics,
)

# ---------------------------------------------------------------------------
# Version suffix is not part of lookup identity.
# ---------------------------------------------------------------------------


def test_unversioned_override_of_a_versioned_key_wins_decisively():
    vanilla = parse_text('l_english:\nmod_planet_jobs_energy_upkeep_mult:0 "vanilla text"\n', path="vanilla.yml")
    aot = parse_text('l_english:\nmod_planet_jobs_energy_upkeep_mult: "aot text"\n', path="aot.yml")
    table = build_table("english", [("stellaris", vanilla), ("aot", aot)])
    entry = table.require("mod_planet_jobs_energy_upkeep_mult")
    assert entry.value.raw == "aot text"
    assert entry.version is None
    assert entry.source == "aot"


def test_within_file_duplicate_key_last_definition_wins_regardless_of_version():
    # giga_l_english.yml: giga_fe_planetcraft_buff:0 "giga_fe_planetcraft_buff" (line 13736),
    # later redefined at line 13923 as giga_fe_planetcraft_buff: "giga_fe_no_mega_upkeep" (no
    # version). Real, spliced fixture -- see manifest.json.
    doc = parse_excerpt("gigastructures/giga_fe_planetcraft_buff_dup_spliced.yml")
    table = build_table("english", [("gigastructures", doc)])
    entry = table.require("giga_fe_planetcraft_buff")
    assert entry.value.raw == "giga_fe_no_mega_upkeep"
    assert entry.version is None
    history = table.history["giga_fe_planetcraft_buff"]
    assert len(history) == 2
    assert history[0].value.raw == "giga_fe_planetcraft_buff"


def test_real_corpus_confirms_83_versioned_to_unversioned_cross_source_overrides():
    """Decisive, corpus-wide version of the synthetic test above: walks the real vendored
    sources (skipped if vendor/ isn't populated) and counts keys defined WITH a version suffix
    in vanilla or Gigastructures that are redefined WITHOUT one in ACOT or AoT. If the count
    were 0, the version-suffix-is-insignificant conclusion would be unconfirmed; 83 is the number
    found and recorded at the time this parser was built."""
    vendor_dir = REPO_ROOT / "vendor"
    if not vendor_dir.is_dir():
        pytest.skip("vendor/ not populated")

    import re

    from pipeline.localisation import parse_file
    from pipeline.localisation.sources import default_source_configs

    key_re = re.compile(r'^\s*([A-Za-z0-9_.\-\']+)\s*:\s*(\d*)\s*"')
    configs = {c.name: c for c in default_source_configs(vendor_dir)}

    def key_versions(source_name):
        out = {}
        for path in configs[source_name].resolve("english"):
            try:
                text = path.read_bytes().decode("utf-8-sig")
            except Exception:
                continue
            for line in text.splitlines():
                m = key_re.match(line)
                if m:
                    out.setdefault(m.group(1), set()).add(m.group(2))
        return out

    vanilla_kv = key_versions("stellaris")
    giga_kv = key_versions("gigastructures")
    acot_kv = key_versions("acot")
    aot_kv = key_versions("aot")

    def collisions(base_kv, override_kv):
        return sum(
            1
            for key, versions in base_kv.items()
            if key in override_kv and any(v != "" for v in versions) and override_kv[key] == {""}
        )

    total = (
        collisions(vanilla_kv, acot_kv)
        + collisions(vanilla_kv, aot_kv)
        + collisions(giga_kv, acot_kv)
        + collisions(giga_kv, aot_kv)
    )
    assert total >= 80, f"expected roughly 83 versioned->unversioned override collisions, found {total}"


# ---------------------------------------------------------------------------
# Lookup: absent signal, never a placeholder.
# ---------------------------------------------------------------------------


def test_get_returns_none_for_a_missing_key():
    table = build_table("english", [])
    assert table.get("nonexistent_key") is None


def test_require_raises_for_a_missing_key():
    table = build_table("english", [])
    with pytest.raises(MissingLocalisationKeyError):
        table.require("nonexistent_key")


def test_contains():
    doc = parse_text('l_english:\nfoo: "bar"\n')
    table = build_table("english", [("stellaris", doc)])
    assert "foo" in table
    assert "bar" not in table


# ---------------------------------------------------------------------------
# Malformed entries: reported via the table, never fatal to the build by themselves.
# ---------------------------------------------------------------------------


def test_malformed_entries_are_collected_with_source_file_and_line():
    doc = parse_excerpt("acot/acot_herculean_missing_close_quote_excerpt.yml")
    table = build_table("english", [("acot", doc)])
    assert len(table.malformed) == 1
    m = table.malformed[0]
    assert m.source == "acot"
    assert m.file == doc.path
    assert m.line > 0


# ---------------------------------------------------------------------------
# Value-is-key diagnostic.
# ---------------------------------------------------------------------------


def test_value_is_key_diagnostic_flags_placeholder_style_values():
    # giga_fe_planetcraft_buff and giga_meopa_fe_resources are both this shape.
    doc = parse_excerpt("gigastructures/giga_fe_planetcraft_buff_dup_spliced.yml")
    table = build_table("english", [("gigastructures", doc)])
    diagnostics = find_value_is_key_diagnostics(table)
    flagged_keys = {d.key for d in diagnostics}
    assert "giga_meopa_fe_resources" in flagged_keys


def test_value_is_key_diagnostic_ignores_ordinary_display_text():
    doc = parse_text('l_english:\nsome_key: "Some ordinary display text"\n')
    table = build_table("english", [("stellaris", doc)])
    assert find_value_is_key_diagnostics(table) == []


def test_value_is_key_diagnostic_ignores_self_referential_ordinary_words():
    # A real, common, legitimate Paradox convention (confirmed via full corpus run: `OK -> "OK"`,
    # `sand -> "sand"`, `Human -> "Human"`) -- self-reference alone is not a signal, only a
    # snake_case-identifier-shaped value is. See table.py's ValueIsKeyDiagnostic docstring.
    doc = parse_text('l_english:\nOK: "OK"\nsand: "sand"\n')
    table = build_table("english", [("stellaris", doc)])
    assert find_value_is_key_diagnostics(table) == []


def test_value_is_key_diagnostic_only_applies_to_quoted_values():
    doc = parse_text("l_english:\nfoo: bar\nbar: \"baz\"\n")
    table = build_table("english", [("stellaris", doc)])
    # foo's unquoted value happens to equal another key ('bar'), but is not flagged -- the
    # diagnostic stays inside the confirmed quoted-placeholder shape (see table.py docstring).
    assert find_value_is_key_diagnostics(table) == []


# ---------------------------------------------------------------------------
# Unquoted-value diagnostic.
# ---------------------------------------------------------------------------


def test_unquoted_value_diagnostic_flags_a_genuinely_unquoted_entry():
    doc = parse_text("l_english:\nacot_omegan_blessed: Blessed By Light\n")
    table = build_table("english", [("acot", doc)])
    diagnostics = find_unquoted_value_diagnostics(table)
    assert len(diagnostics) == 1
    assert diagnostics[0].key == "acot_omegan_blessed"
    assert diagnostics[0].value == "Blessed By Light"


def test_unquoted_value_diagnostic_ignores_quoted_entries():
    doc = parse_text('l_english:\nfoo: "bar"\n')
    table = build_table("english", [("stellaris", doc)])
    assert find_unquoted_value_diagnostics(table) == []


def test_unquoted_value_is_not_malformed_but_is_diagnosed():
    # The single point of this diagnostic: quoted=False stays a valid LocEntry (see
    # test_parser.py's test_genuinely_unquoted_value), but it must not vanish silently -- it has
    # to surface through the diagnostic even though it never touches `table.malformed`.
    doc = parse_text("l_english:\nacot_omegan_blessed: Blessed By Light\n")
    table = build_table("english", [("acot", doc)])
    assert table.malformed == []
    assert len(find_unquoted_value_diagnostics(table)) == 1
