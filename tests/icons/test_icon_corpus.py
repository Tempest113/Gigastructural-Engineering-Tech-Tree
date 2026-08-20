"""Full icon-atlas build against the real vendored corpus (skipped when vendor/ isn't
populated locally, same posture as tests/clausewitz/test_roundtrip_full_corpus.py and
tests/localisation/test_corpus.py — vendor/ is gitignored, CI never has it).

Builds every sheet end to end (resolve -> decode -> pack -> encode) and reports resolution and
sheet-size numbers for a human to read locally. Per pipeline/icons/resolve.py's module docstring,
this test does NOT fail on unresolved icons — Stage 1 has no notion of rendering scope, so an
unresolved candidate is a diagnostic here, never a build failure (see the TODO(Stage 2) notes in
resolve.py for where that decision, and atlas content scope-filtering, actually belong).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import REPO_ROOT

from pipeline.icons.build import build_atlases, write_atlases
from pipeline.icons.overrides import load_overrides
from pipeline.icons.pack import MAX_SHEET_DIMENSION, MAX_TOTAL_ATLAS_BYTES, encode_webp

VENDOR_ROOT = REPO_ROOT / "vendor"
_vendor_populated = VENDOR_ROOT.is_dir()

pytestmark = pytest.mark.skipif(not _vendor_populated, reason="vendor/ not populated")


def _rendered_keys():
    from pipeline.clausewitz import parse_file
    from pipeline.inline_scripts import collect_scripts, expand_document
    from pipeline.overwrites import collect_technology_definitions
    from pipeline.rendering_scope import rendered_technology_keys

    sources = [
        ("Vanilla", VENDOR_ROOT / "stellaris"),
        ("Gigastructural Engineering", VENDOR_ROOT / "mods" / "gigastructures"),
        ("ACOT", VENDOR_ROOT / "mods" / "acot"),
        ("AoT", VENDOR_ROOT / "mods" / "aot"),
    ]
    script_entries = []
    for name, root in sources:
        base = root / "common" / "inline_scripts"
        if base.is_dir():
            for f in sorted(base.rglob("*.txt")):
                rel = f.relative_to(base).with_suffix("")
                script_entries.append((str(rel).replace("\\", "/"), str(f), f.read_text(encoding="utf-8")))
    scripts = collect_scripts(script_entries)

    tech_docs = []
    for name, root in sources:
        d = root / "common" / "technology"
        if d.is_dir():
            docs = [expand_document(parse_file(f), scripts)[0] for f in sorted(d.glob("*.txt"))]
            tech_docs.append((name, docs))

    history = collect_technology_definitions(tech_docs)
    return rendered_technology_keys(history)


def test_full_icon_corpus_build_report_unfiltered():
    """The UNFILTERED superset -- every resolvable icon across all four sources, before P-16
    scoping. Kept as a standing measurement for comparison (see
    test_filtered_technology_atlas_matches_p16_closure for the real build path this pipeline
    actually uses); deliberately does NOT assert against MAX_TOTAL_ATLAS_BYTES any more, since
    that constant is now calibrated to the filtered figure and the unfiltered superset is
    expected to exceed it (that's the whole point of filtering)."""
    overrides = load_overrides()
    assert overrides == {}, "no overrides expected yet -- see config/icon_overrides.txt"

    tech_sheets, tech_result = build_atlases("technology", VENDOR_ROOT)
    perk_sheets, perk_result = build_atlases("ascension_perk", VENDOR_ROOT)

    print(f"\ntechnologies: {len(tech_sheets)} sheet(s)")
    for sheet in tech_sheets:
        print(f"  {sheet.sheet_name}: {sheet.width}x{sheet.height}, {len(sheet.tiles)} tiles")
    print(f"  resolved: {len(tech_result.resolved)}  unresolved: {len(tech_result.unresolved)}")
    for c in tech_result.unresolved:
        print(f"    UNRESOLVED [{c.definition_source}] {c.key} -> {c.resolved_name} ({c.channel})")

    print(f"ascension_perks: {len(perk_sheets)} sheet(s)")
    for sheet in perk_sheets:
        print(f"  {sheet.sheet_name}: {sheet.width}x{sheet.height}, {len(sheet.tiles)} tiles")
    print(f"  resolved: {len(perk_result.resolved)}  unresolved: {len(perk_result.unresolved)}")
    for c in perk_result.unresolved:
        print(f"    UNRESOLVED [{c.definition_source}] {c.key} -> {c.resolved_name} ({c.channel})")

    from pipeline.icons.build import decode_resolved_icons

    tech_icons = decode_resolved_icons(tech_result)
    perk_icons = decode_resolved_icons(perk_result)
    fallback_tech = [n for n, i in tech_icons.items() if i.used_fallback]
    fallback_perk = [n for n, i in perk_icons.items() if i.used_fallback]
    print(f"ImageMagick fallback used: {len(fallback_tech) + len(fallback_perk)} icon(s)")
    for n in fallback_tech + fallback_perk:
        print(f"    FALLBACK: {n}")

    for sheet in tech_sheets + perk_sheets:
        assert sheet.width <= MAX_SHEET_DIMENSION and sheet.height <= MAX_SHEET_DIMENSION, (
            f"{sheet.sheet_name} is {sheet.width}x{sheet.height}, exceeds MAX_SHEET_DIMENSION "
            f"({MAX_SHEET_DIMENSION}) -- this would fail to upload as a WebGL texture on a "
            f"guaranteed-minimum device (P-9)"
        )

    assert len(tech_result.unresolved) == 19
    assert len(perk_result.unresolved) == 6

    total_atlas_bytes = sum(len(encode_webp(s)) for s in tech_sheets + perk_sheets)
    print(f"total UNFILTERED atlas bytes (WebP, all sheets): {total_atlas_bytes}")
    assert total_atlas_bytes == 8_650_292  # 4 tech sheets (8,387,616) + 1 perk sheet (262,676)
    assert len(fallback_tech) == 0 and len(fallback_perk) == 0, (
        "no icon in the current corpus should need the ImageMagick fallback -- if this fires, "
        "report it, don't silence it (see decode.py's module docstring)"
    )


def test_filtered_technology_atlas_matches_p16_closure():
    """The REAL build path (P-16 TODO(Stage 2) closed): technology icons filtered to the
    977-node rendered set (D-18: 980 -> 977); ascension-perk icons deliberately left unfiltered
    (see filter_result_to_rendered_scope's docstring for why). This is what MAX_TOTAL_ATLAS_BYTES
    is now calibrated against."""
    rendered_keys = _rendered_keys()
    assert len(rendered_keys) == 973  # D-18: 980 -> 977; Item 2c: 977 -> 973

    tech_sheets, tech_result = build_atlases("technology", VENDOR_ROOT, rendered_keys=rendered_keys)
    perk_sheets, perk_result = build_atlases("ascension_perk", VENDOR_ROOT)

    print(f"\nfiltered technologies: {len(tech_sheets)} sheet(s)")
    for sheet in tech_sheets:
        print(f"  {sheet.sheet_name}: {sheet.width}x{sheet.height}, {len(sheet.tiles)} tiles")
    print(f"  resolved: {len(tech_result.resolved)}  unresolved: {len(tech_result.unresolved)}")
    for c in tech_result.unresolved:
        print(f"    UNRESOLVED (survives P-16 filter) [{c.definition_source}] {c.key} -> {c.resolved_name} ({c.channel})")

    # D-18 (this session): 1192 -> 1189 -- the 3 depth-2+ technologies dropped from the P-16
    # closure carried resolvable icon candidates that are now correctly excluded by the filter.
    # Item 2c (user domain call, later session): 1189 -> 1185 -- the 4 permanently-disabled
    # technologies excluded from the rendered set each carried a resolvable icon candidate too.
    assert len(tech_result.resolved) == 1185
    # Of the 19 unfiltered unresolved candidates, only these 4 have an owning technology that
    # actually renders -- the other 15 (mostly ACOT bio-spore techs) are outside the P-16
    # closure and no longer matter. Do NOT resolve or guess at these 4 -- config/icon_overrides.txt
    # is human-decided by design (see resolve.py's module docstring). Unaffected by D-18: none of
    # the 3 dropped technologies was ever in this unresolved set.
    assert {c.key for c in tech_result.unresolved} == {
        "giga_tech_planetary_matter_dumping",
        "giga_tech_repeatable_observatory_cap",
        "giga_tech_repeatable_dyson_swarm_cap",
        "tech_ring_world/swap:giga_tech_ring_world_swap_no_habitables",
    }

    assert len(tech_sheets) == 2
    assert (tech_sheets[0].width, tech_sheets[0].height) == (1008, 2016)
    # D-18: second sheet shrinks from 1008x1468 to 1008x1406 -- 3 fewer tiles to pack.
    assert (tech_sheets[1].width, tech_sheets[1].height) == (1008, 1406)

    total_atlas_bytes = sum(len(encode_webp(s)) for s in tech_sheets + perk_sheets)
    print(f"total FILTERED atlas bytes (WebP, filtered tech + unfiltered perk): {total_atlas_bytes} "
          f"(tripwire: {MAX_TOTAL_ATLAS_BYTES})")
    # D-18: 4,826,990 -> 4,799,342 (4,536,666 filtered tech + 262,676 unfiltered perk).
    # Item 2c (user domain call, later session): 4,799,342 -> 4,783,554 -- 4 fewer icons packed
    # (the 4 permanently-disabled technologies' own icons, now excluded from the rendered set).
    assert total_atlas_bytes == 4_783_554
    assert total_atlas_bytes <= MAX_TOTAL_ATLAS_BYTES, (
        f"total atlas bytes {total_atlas_bytes} exceeds MAX_TOTAL_ATLAS_BYTES "
        f"({MAX_TOTAL_ATLAS_BYTES}) -- see pipeline/icons/pack.py's comment on this constant; "
        f"this is a tripwire against unintended sprite growth (including the P-16 filter "
        f"silently getting disabled), not a size budget, but tripping it is still worth a human "
        f"looking at, not silently raising the number"
    )


def test_atlas_write_round_trip(tmp_path):
    """Confirms the on-disk artefacts (webp, png, json metadata) actually get produced for every
    sheet and each metadata's tile map matches what was packed."""
    tech_sheets, _ = build_atlases("technology", VENDOR_ROOT)
    metadatas = write_atlases(tech_sheets, tmp_path)
    for sheet, metadata in zip(tech_sheets, metadatas):
        assert (tmp_path / f"{sheet.sheet_name}.webp").is_file()
        assert (tmp_path / f"{sheet.sheet_name}.png").is_file()
        assert (tmp_path / f"{sheet.sheet_name}.json").is_file()
        assert len(metadata["tiles"]) == len(sheet.tiles)
        assert metadata["encoder"]["pillow_version"]
