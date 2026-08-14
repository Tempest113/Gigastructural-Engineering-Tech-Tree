"""Orchestrates resolution → decode → pack → encode for the icon atlas build.

Split: **one sheet per usage kind** (`technologies`, `ascension_perks`), not per research area.
Research area was considered and rejected: an icon's "area" is a property of the *technology*
that references it, not of the icon file itself, and an icon can be referenced by technologies in
different areas across sources (the 31 cross-source icon-path collisions found in the survey are
exactly this — the same icon file serving as more than one definition), so an area-based split
would need technology-overwrite resolution (P-15, not built yet) to assign an icon to a sheet
unambiguously. Usage kind has no such ambiguity: every icon lives under either
`technologies/` or `ascension_perks/`, always exactly one, decided by directory alone. It also
matches how the renderer actually needs the data — a tech-tree card needs the technologies sheet,
a gate badge needs the ascension-perks sheet — so the split is along a real consumption boundary,
not an artificial one.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from pipeline.clausewitz import ClausewitzError

from .decode import DecodedIcon, decode_level0
from .overrides import IconOverride, load_overrides
from .pack import AtlasSheet, encode_png, encode_webp, encoder_metadata, pack_sheets, sheet_content_hash
from .resolve import IconResolutionResult, collect_candidates, resolve_all, resolve_icon_files
from .sources import IconSourceConfig, default_source_configs

TARGET_SHEET_WIDTH = {"technologies": 1024, "ascension_perks": 512}


def technology_definition_files(configs: list[IconSourceConfig], vendor_root: Path) -> list[tuple[str, Path]]:
    files = []
    dirs = {
        "stellaris": vendor_root / "stellaris" / "common" / "technology",
        "gigastructures": vendor_root / "mods" / "gigastructures" / "common" / "technology",
        "acot": vendor_root / "mods" / "acot" / "common" / "technology",
        "aot": vendor_root / "mods" / "aot" / "common" / "technology",
    }
    for config in configs:
        d = dirs[config.name]
        if d.is_dir():
            files.extend((config.name, p) for p in sorted(d.glob("*.txt")))
    return files


def ascension_perk_definition_files(configs: list[IconSourceConfig], vendor_root: Path) -> list[tuple[str, Path]]:
    files = []
    dirs = {
        "stellaris": vendor_root / "stellaris" / "common" / "ascension_perks",
        "gigastructures": vendor_root / "mods" / "gigastructures" / "common" / "ascension_perks",
        "acot": vendor_root / "mods" / "acot" / "common" / "ascension_perks",
        "aot": vendor_root / "mods" / "aot" / "common" / "ascension_perks",
    }
    for config in configs:
        d = dirs[config.name]
        if d.is_dir():
            files.extend((config.name, p) for p in sorted(d.glob("*.txt")))
    return files


def resolve_kind(kind: str, vendor_root: Path, overrides: dict[str, IconOverride]) -> IconResolutionResult:
    configs = default_source_configs(vendor_root)
    if kind == "technology":
        def_files = technology_definition_files(configs, vendor_root)
    elif kind == "ascension_perk":
        def_files = ascension_perk_definition_files(configs, vendor_root)
    else:
        raise ValueError(kind)

    candidates = collect_candidates(def_files, kind)
    icon_dir_kind = "technologies" if kind == "technology" else "ascension_perks"
    icon_files = resolve_icon_files(configs, icon_dir_kind)
    return resolve_all(candidates, icon_files, overrides)


def decode_resolved_icons(result: IconResolutionResult) -> dict[str, DecodedIcon]:
    """Deduplicates by resolved path (several candidates can point at the same file) and decodes
    each distinct file exactly once."""
    paths_by_name: dict[str, Path] = {}
    for candidate, path, _channel in result.resolved:
        paths_by_name[candidate.resolved_name] = path
    return {name: decode_level0(path) for name, path in sorted(paths_by_name.items())}


def build_atlases(kind: str, vendor_root: Path, overrides_path: Path | None = None) -> tuple[list[AtlasSheet], IconResolutionResult]:
    """Returns every sheet needed for this usage kind — always a list, even when only one sheet
    results, so callers never special-case "the" sheet (see pack.py's `pack_sheets` docstring on
    why sheet count is not fixed)."""
    overrides = load_overrides(overrides_path) if overrides_path else load_overrides()
    result = resolve_kind(kind, vendor_root, overrides)
    icons = decode_resolved_icons(result)
    sheet_base_name = "technologies" if kind == "technology" else "ascension_perks"
    sheets = pack_sheets(sheet_base_name, icons, TARGET_SHEET_WIDTH[sheet_base_name])
    return sheets, result


def write_atlas(sheet: AtlasSheet, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    webp_bytes = encode_webp(sheet)
    png_bytes = encode_png(sheet)
    (out_dir / f"{sheet.sheet_name}.webp").write_bytes(webp_bytes)
    (out_dir / f"{sheet.sheet_name}.png").write_bytes(png_bytes)

    metadata = {
        "sheet": sheet.sheet_name,
        "width": sheet.width,
        "height": sheet.height,
        "content_hash_sha256": sheet_content_hash(sheet),
        "encoder": encoder_metadata(),
        "tiles": {
            t.name: {"x": t.x, "y": t.y, "width": t.width, "height": t.height}
            for t in sorted(sheet.tiles, key=lambda t: t.name)
        },
    }
    (out_dir / f"{sheet.sheet_name}.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return metadata


def write_atlases(sheets: list[AtlasSheet], out_dir: Path) -> list[dict]:
    return [write_atlas(sheet, out_dir) for sheet in sheets]
