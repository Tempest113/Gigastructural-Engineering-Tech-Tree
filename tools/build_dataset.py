#!/usr/bin/env python3
"""Builds the real dataset (all five artefacts + typed-array side-files + icon atlases) from
`vendor/` and writes them into `client/public/dataset/`, where Vite serves them verbatim in dev
and copies them verbatim into `client/dist/dataset/` on build (Vite's `public/` convention).

**Requires `vendor/` populated** (gitignored -- Stellaris/Steam Workshop content, not
redistributed; see CLAUDE.md's "Source data").

**Deploy model: local build, manual deploy -- a permanent constraint, not a gap to close later.**
The real dataset build cannot run in GitHub Actions. Vanilla Stellaris is the blocker: its game
files require a Steam account that owns the game, so CI-side building would mean either storing
real Steam credentials as a CI secret (a security and ToS exposure) or redistributing extracted
game files (foreclosed outright by this project's standing never-redistribute-vendor-content
rule). See spec/decisions.md's vendoring-automation decision for the full reasoning, including why
options A (a private artefact store) and C (CI builds without ACOT/AoT) were considered and
rejected as the PRIMARY deploy model. Consequently:

- This script runs LOCALLY, where `vendor/` already exists.
- `client/public/dataset/` output is **NOT committed to the repo** -- see `.gitignore`. It is
  derived from vendored third-party content; git would retain every version permanently; and a
  committed artefact can silently disagree with the pipeline that claims to produce it, which is
  exactly the staleness problem content-hashed filenames exist to prevent, just moved to a
  different layer.
- Deployment is via `.github/workflows/deploy.yml`'s `workflow_dispatch` trigger, which takes a
  pre-built artefact (uploaded as a workflow input/attached to a release -- see that workflow's
  own comments) and publishes it to Pages. It does not build anything.

**Integrity manifest.** Every run of this script writes `client/public/dataset/integrity.json`
(unhashed, stable name -- the audit trail itself needs to be findable), recording: the pipeline
commit this build ran from (and whether the working tree was dirty), `vendor/manifest.json`'s
per-source identifying info (game_version for Vanilla, content hash for each mod), which sources
were actually loaded, and a sha256 checksum of every other artefact this script writes. **This
does NOT make the build CI-verifiable -- nothing can, given the constraint above.** What it does
provide: every deployed build states exactly what produced it, so a mismatch between deployed
bytes and claimed provenance is DETECTABLE (recompute the checksums, compare) rather than
invisible. Record this limitation honestly wherever this manifest is described -- it is not
CI-grade auditability, and must never be presented as though it were.

**Content-hashed filenames.** GitHub Pages' cache headers are not configurable (no way to set a
short/no-cache TTL on a specific path), so a same-named artefact that changes content between
deploys risks being served stale from an intermediate cache. Every artefact below (including, as
of this session, the icon atlas image files) is written as `<name>.<content-hash>.<ext>` and
referenced only through `dataset/manifest.json` -- the ONE unhashed, stable entry point the
client fetches first (same pattern Vite's own `index.html` -> hashed-asset-references already
uses for the JS bundle, applied here to the dataset side of the site). `base-dataset.json`'s own
`geometry.nodePositions`/`edgePolylines`/`iconAtlases[].webp`/`.png` fields are set to their
referenced files' final hashed names, computed BEFORE base-dataset.json itself is serialised and
hashed, so every reference is always correct.

**ACOT/AoT-absent builds are a real, supported mode, not an error** -- see
`pipeline.dataset_emit.build_diagnostics`'s `vendorSourcesLoaded`/`placeholderTechnologiesAbsent`/
`vanillaTechnologiesRevertedFromAcotOverwrite` fields (spec/decisions.md's vendoring-automation
investigation: 977 rendered nodes, not 980, if either is absent -- and NOT a simple 980-7=973
subtraction either). This script prints a loud console warning when it detects either missing, so
a contributor without an ACOT/AoT Workshop subscription can't miss what they're building.

Usage: `python tools/build_dataset.py`
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pipeline.dataset_emit import (  # noqa: E402
    build_base_dataset,
    build_context,
    build_detail_payload,
    build_diagnostics,
    build_empire_overlay,
    build_search_index,
)
from pipeline.dataset_schema import (  # noqa: E402
    validate_base_dataset,
    validate_detail_payload,
    validate_diagnostics,
    validate_empire_overlay,
    validate_search_index,
)
from pipeline.dataset_schema.empire_profile import all_profiles_in_canonical_order  # noqa: E402
from pipeline.icons.pack import encode_png, encode_webp  # noqa: E402

OUT_DIR = REPO_ROOT / "client" / "public" / "dataset"
HASH_LENGTH = 10


def _hashed_name(base_name: str, suffix: str, data: bytes) -> str:
    digest = hashlib.sha256(data).hexdigest()[:HASH_LENGTH]
    return f"{base_name}.{digest}{suffix}"


def _write_bytes_hashed(rel_dir: str, base_name: str, suffix: str, data: bytes) -> str:
    """Writes `data` under a content-hashed filename, returns the path RELATIVE to `dataset/`
    (e.g. `overlays/regular-mechanical-no.9f3a1b2c4d.json`) for the manifest to record."""
    filename = _hashed_name(base_name, suffix, data)
    directory = OUT_DIR / rel_dir if rel_dir else OUT_DIR
    directory.mkdir(parents=True, exist_ok=True)
    (directory / filename).write_bytes(data)
    return f"{rel_dir}/{filename}" if rel_dir else filename


def _write_json_hashed(rel_dir: str, base_name: str, doc: dict) -> str:
    data = json.dumps(doc, separators=(",", ":")).encode("utf-8")
    return _write_bytes_hashed(rel_dir, base_name, ".json", data)


def _clean(out_dir: Path) -> None:
    """Removes previously-written hashed files so a rename/removed technology doesn't leave a
    stale, unreferenced file behind indefinitely."""
    if out_dir.exists():
        import shutil

        shutil.rmtree(out_dir)


def _git_provenance() -> dict:
    def _run(args: list[str]) -> str | None:
        try:
            return subprocess.run(
                ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True, timeout=10,
            ).stdout.strip()
        except Exception:
            return None

    sha = _run(["rev-parse", "HEAD"])
    status = _run(["status", "--porcelain"])
    return {"commit": sha, "workingTreeDirty": bool(status)}


def _vendor_provenance() -> dict:
    manifest_path = REPO_ROOT / "vendor" / "manifest.json"
    if not manifest_path.is_file():
        return {"available": False}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    mods = manifest.get("mods", {})
    return {
        "available": True,
        "collectedAt": manifest.get("collected_at"),
        "vanilla": {"gameVersion": manifest.get("game_version")},
        "mods": {
            name: {k: v for k, v in info.items() if k in ("commit", "tag", "workshop_id", "hash")}
            for name, info in mods.items()
        },
    }


def main() -> None:
    vendor_root = REPO_ROOT / "vendor"
    if not vendor_root.is_dir():
        raise SystemExit(
            "vendor/ is not populated -- this script needs the real vendored corpus. "
            "See CLAUDE.md's 'Source data' section (tools/collect_vanilla.py)."
        )

    _clean(OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Building context (parsing + expanding the full corpus)...")
    ctx = build_context(vendor_root)

    missing = [s for s in ("ACOT", "AoT") if s not in ctx.sources_present]
    if missing:
        print()
        print("=" * 78)
        print(f"WARNING: building WITHOUT {' and '.join(missing)} -- this is a reduced-corpus build.")
        print("Real node count will be 977, not 980 (7 fewer for the missing placeholder")
        print("technologies, but 4 MORE for vanilla technologies ACOT normally overwrites --")
        print("980 - 7 + 4 = 977, not a naive 980 - 7 = 973). See diagnostics.json's")
        print("placeholderTechnologiesAbsent / vanillaTechnologiesRevertedFromAcotOverwrite")
        print("for exactly which technologies are affected and how.")
        print("=" * 78)
        print()

    manifest: dict = {"overlays": {}, "details": {}, "iconAtlases": {}}
    checksums: dict[str, str] = {}

    def _record_checksum(rel_path: str) -> None:
        checksums[rel_path] = hashlib.sha256((OUT_DIR / rel_path).read_bytes()).hexdigest()

    print("Building icon atlases...")
    atlas_path_by_sheet_name: dict[str, tuple[str, str]] = {}
    for sheet in ctx.tech_sheets + ctx.perk_sheets:
        webp_bytes = encode_webp(sheet)
        png_bytes = encode_png(sheet)
        webp_path = _write_bytes_hashed("", sheet.sheet_name, ".webp", webp_bytes)
        png_path = _write_bytes_hashed("", sheet.sheet_name, ".png", png_bytes)
        atlas_path_by_sheet_name[sheet.sheet_name] = (webp_path, png_path)
        manifest["iconAtlases"][sheet.sheet_name] = {"webp": webp_path, "png": png_path}
        _record_checksum(webp_path)
        _record_checksum(png_path)
    total_atlas_bytes = sum((OUT_DIR / p).stat().st_size for pair in atlas_path_by_sheet_name.values() for p in pair)
    print(f"  {len(atlas_path_by_sheet_name)} sheets, {total_atlas_bytes:,} bytes (webp+png)")

    print("Building base dataset...")
    base_doc, node_bytes, edge_bytes = build_base_dataset(ctx)
    # Geometry + atlas files hashed and written FIRST (atlases above), so their final names can
    # be embedded into base_doc before base_doc itself is serialised and hashed.
    node_positions_path = _write_bytes_hashed("", "node-positions", ".f32", node_bytes)
    edge_polylines_path = _write_bytes_hashed("", "edge-polylines", ".f32", edge_bytes)
    base_doc["geometry"]["nodePositions"]["file"] = node_positions_path
    base_doc["geometry"]["edgePolylines"]["file"] = edge_polylines_path
    for atlas_entry in base_doc["iconAtlases"]:
        webp_path, png_path = atlas_path_by_sheet_name[atlas_entry["name"]]
        atlas_entry["webp"] = webp_path
        atlas_entry["png"] = png_path
    validate_base_dataset(base_doc)  # after the file-path rewrite, so the validated doc is the emitted one
    manifest["baseDataset"] = _write_json_hashed("", "base-dataset", base_doc)
    print(f"  {len(base_doc['technologies'])} technologies, {len(base_doc['edges'])} edges")
    _record_checksum(node_positions_path)
    _record_checksum(edge_polylines_path)
    _record_checksum(manifest["baseDataset"])

    print("Building empire overlays (12 profiles)...")
    for profile in all_profiles_in_canonical_order():
        overlay = build_empire_overlay(ctx, profile)
        validate_empire_overlay(overlay)
        key = f"{profile['authority']}-{profile['shipset']}-{profile['nomadic']}"
        rel_path = _write_json_hashed("overlays", key, overlay)
        manifest["overlays"][key] = rel_path
        _record_checksum(rel_path)
    print(f"  wrote {len(manifest['overlays'])} overlay files")

    print("Building detail payloads...")
    detail_payloads = {}
    for key in sorted(ctx.rendered_keys):
        payload = build_detail_payload(ctx, key)
        validate_detail_payload(payload)
        detail_payloads[key] = payload
        rel_path = _write_json_hashed("details", key, payload)
        manifest["details"][key] = rel_path
        _record_checksum(rel_path)
    print(f"  wrote {len(detail_payloads)} detail payload files ({len(ctx.rendered_keys)} technologies)")

    print("Building search index...")
    search_index = build_search_index(ctx, base_doc, detail_payloads)
    validate_search_index(search_index)
    manifest["searchIndex"] = _write_json_hashed("", "search-index", search_index)
    _record_checksum(manifest["searchIndex"])

    print("Building diagnostics...")
    diagnostics = build_diagnostics(ctx)
    validate_diagnostics(diagnostics)
    manifest["diagnostics"] = _write_json_hashed("", "diagnostics", diagnostics)
    _record_checksum(manifest["diagnostics"])

    # The one unhashed, stable entry point -- everything else is reached only through it.
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, separators=(",", ":")), encoding="utf-8")

    integrity = {
        "pipeline": _git_provenance(),
        "vendor": _vendor_provenance(),
        "vendorSourcesLoaded": ctx.sources_present,
        "artefactChecksums": checksums,  # sha256, keyed by path relative to dataset/
        "note": (
            "This manifest states what produced this build; it does NOT make the build "
            "CI-verifiable -- see tools/build_dataset.py's module docstring for why that's a "
            "permanent constraint, not a gap. A mismatch between these checksums and the actual "
            "files is detectable; a mismatch between this commit/vendor info and reality is not, "
            "beyond trusting whoever ran this script."
        ),
    }
    (OUT_DIR / "integrity.json").write_text(json.dumps(integrity, indent=2), encoding="utf-8")

    print(f"\nDone. Artefacts written to {OUT_DIR}")
    print(f"Pipeline commit: {integrity['pipeline']['commit']}" + (
        " (WORKING TREE DIRTY)" if integrity["pipeline"]["workingTreeDirty"] else ""
    ))


if __name__ == "__main__":
    main()
