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
from pipeline.icons.pack import MAX_SHEET_DIMENSION

VENDOR_ROOT = REPO_ROOT / "vendor"
_vendor_populated = VENDOR_ROOT.is_dir()

pytestmark = pytest.mark.skipif(not _vendor_populated, reason="vendor/ not populated")


def test_full_icon_corpus_build_report():
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
    assert len(fallback_tech) == 0 and len(fallback_perk) == 0, (
        "no icon in the current corpus should need the ImageMagick fallback -- if this fires, "
        "report it, don't silence it (see decode.py's module docstring)"
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
