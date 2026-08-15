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

from pipeline.clausewitz import ClausewitzError, parse_file
from pipeline.inline_scripts import collect_scripts, expand_document

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


def _inline_script_entries(vendor_root: Path):
    """Same discovery pattern every other Stage 2 consumer of technology data uses
    (pipeline.dataset_emit, the real-corpus test fixtures) -- kept local rather than shared,
    since this module has its own vendor-root-relative source layout already
    (technology_definition_files/ascension_perk_definition_files above), matching this file's
    existing "define your own dirs" convention rather than reaching into another module's."""
    entries = []
    for source_dir in ("stellaris", "mods/gigastructures", "mods/acot", "mods/aot"):
        base = vendor_root / source_dir / "common" / "inline_scripts"
        if not base.is_dir():
            continue
        for f in sorted(base.rglob("*.txt")):
            rel = f.relative_to(base).with_suffix("")
            entries.append((str(rel).replace("\\", "/"), str(f), f.read_text(encoding="utf-8")))
    return entries


def _expanded_documents(def_files: list[tuple[str, Path]], scripts) -> list[tuple[str, object]]:
    return [(source_name, expand_document(parse_file(path), scripts)[0]) for source_name, path in def_files]


def resolve_kind(kind: str, vendor_root: Path, overrides: dict[str, IconOverride]) -> IconResolutionResult:
    configs = default_source_configs(vendor_root)
    if kind == "technology":
        def_files = technology_definition_files(configs, vendor_root)
    elif kind == "ascension_perk":
        def_files = ascension_perk_definition_files(configs, vendor_root)
    else:
        raise ValueError(kind)

    # Expanded canonical records, not raw blocks -- closes the raw-block gap the defect-class
    # note in CLAUDE.md's "Availability evaluator" section flagged for this module specifically.
    scripts = collect_scripts(_inline_script_entries(vendor_root))
    documents = _expanded_documents(def_files, scripts)

    candidates = collect_candidates(documents, kind)
    icon_dir_kind = "technologies" if kind == "technology" else "ascension_perks"
    icon_files = resolve_icon_files(configs, icon_dir_kind)
    return resolve_all(candidates, icon_files, overrides)


def candidate_owner_key(candidate_key: str) -> str:
    """`IconCandidate.key` is either a bare technology key or `"<owner key>/swap:<swap name>"`
    (resolve.py's `collect_candidates`). The owning technology is what P-16's rendering-scope
    closure decides is rendered or not -- a swap alternate is never independently in or out of
    scope, it follows its owner."""
    return candidate_key.split("/swap:", 1)[0]


def filter_result_to_rendered_scope(result: IconResolutionResult, rendered_keys: set[str]) -> IconResolutionResult:
    """P-16 filter (TODO(Stage 2) closed): only technology/swap candidates whose OWNING
    technology survives the rendering-scope closure contribute to the atlas. Icons for the
    ~1,736 canonical technologies outside the 980-node closure (mostly ACOT/AoT content nothing
    rendered needs) are dropped before decode/pack, not packed and discarded after.

    **Ascension-perk icons are NOT filtered by this function and MUST NOT be** -- confirmed
    against spec, not assumed: P-16's rendering-scope closure is a technology-node concept (which
    ACOT/AoT technologies get their own canvas node); an ascension perk is never itself a canvas
    node, only a gate badge on a technology card (P-3). The question "which ascension perks does
    a rendered technology actually reference as a gate" is a DIFFERENT computation --  P-3's
    gate-pattern-registry/gate-detection pass, which classifies `potential`/`allow` trigger shapes
    against a curated pattern table -- and that pass is not built yet (HANDOFF.md's "Ordered next
    steps": gate detection is still open, distinct from the universal `potential-gate` edge
    extraction P-14 already does). Calling this function on ascension-perk candidates would filter
    against the wrong criterion entirely (technology rendering, not gate usage), so ascension-perk
    atlas building stays fully unfiltered until gate detection exists to filter it correctly."""
    resolved = [(c, path, channel) for c, path, channel in result.resolved if candidate_owner_key(c.key) in rendered_keys]
    unresolved = [c for c in result.unresolved if candidate_owner_key(c.key) in rendered_keys]
    overridden = [(c, ov) for c, ov in result.overridden if candidate_owner_key(c.key) in rendered_keys]
    candidates = [c for c in result.candidates if candidate_owner_key(c.key) in rendered_keys]
    return IconResolutionResult(
        candidates=candidates, icon_files=result.icon_files,
        resolved=resolved, unresolved=unresolved, overridden=overridden,
    )


def decode_resolved_icons(result: IconResolutionResult) -> dict[str, DecodedIcon]:
    """Deduplicates by resolved path (several candidates can point at the same file) and decodes
    each distinct file exactly once."""
    paths_by_name: dict[str, Path] = {}
    for candidate, path, _channel in result.resolved:
        paths_by_name[candidate.resolved_name] = path
    return {name: decode_level0(path) for name, path in sorted(paths_by_name.items())}


def build_atlases(
    kind: str, vendor_root: Path, overrides_path: Path | None = None, rendered_keys: set[str] | None = None,
) -> tuple[list[AtlasSheet], IconResolutionResult]:
    """Returns every sheet needed for this usage kind — always a list, even when only one sheet
    results, so callers never special-case "the" sheet (see pack.py's `pack_sheets` docstring on
    why sheet count is not fixed).

    `rendered_keys` (P-16's rendered technology-key set) filters technology-kind candidates to
    those whose owning technology is actually rendered — see `filter_result_to_rendered_scope`.
    Passed but ignored for `kind == "ascension_perk"` (that function's docstring explains why
    filtering perks by the technology closure would be wrong, not merely unfiltered by omission)."""
    overrides = load_overrides(overrides_path) if overrides_path else load_overrides()
    result = resolve_kind(kind, vendor_root, overrides)
    if rendered_keys is not None and kind == "technology":
        result = filter_result_to_rendered_scope(result, rendered_keys)
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
