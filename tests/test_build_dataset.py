"""tools/build_dataset.py, end to end against the real vendored corpus. Skipped when vendor/
isn't populated, same posture as the other corpus tests. Runs the real script as a subprocess
(not by importing its internals) so this actually exercises what a contributor running
`python tools/build_dataset.py` gets, including the content-hashed filename scheme
`client/src/dataset.ts` depends on.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from tests.conftest import REPO_ROOT

VENDOR_ROOT = REPO_ROOT / "vendor"
OUT_DIR = REPO_ROOT / "client" / "public" / "dataset"

pytestmark = pytest.mark.skipif(not VENDOR_ROOT.is_dir(), reason="vendor/ not populated")


@pytest.fixture(scope="module")
def built():
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "build_dataset.py")],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=300,
    )
    assert result.returncode == 0, f"build_dataset.py failed:\n{result.stdout}\n{result.stderr}"
    return json.loads((OUT_DIR / "manifest.json").read_text(encoding="utf-8"))


def test_manifest_references_files_that_actually_exist(built):
    for rel_path in [built["baseDataset"], built["searchIndex"], built["diagnostics"]]:
        assert (OUT_DIR / rel_path).is_file(), rel_path

    assert len(built["overlays"]) == 12
    for rel_path in built["overlays"].values():
        assert (OUT_DIR / rel_path).is_file(), rel_path

    assert len(built["details"]) == 973  # D-18: 980 -> 977; Item 2c: 977 -> 973
    for rel_path in built["details"].values():
        assert (OUT_DIR / rel_path).is_file(), rel_path


def test_manifest_filenames_are_content_hashed():
    """Every referenced filename (except manifest.json itself) carries a hash segment -- the
    cache-busting mechanism GitHub Pages' fixed cache headers require (tools/build_dataset.py's
    module docstring)."""
    manifest = json.loads((OUT_DIR / "manifest.json").read_text(encoding="utf-8"))
    all_paths = (
        [manifest["baseDataset"], manifest["searchIndex"], manifest["diagnostics"]]
        + list(manifest["overlays"].values())
        + list(manifest["details"].values())
    )
    for rel_path in all_paths:
        stem = rel_path.rsplit("/", 1)[-1]
        parts = stem.split(".")
        assert len(parts) >= 3, f"{rel_path} has no hash segment (expected name.hash.ext)"
        hash_segment = parts[-2]
        assert len(hash_segment) == 10 and all(c in "0123456789abcdef" for c in hash_segment), rel_path


def test_base_dataset_geometry_refs_point_at_hashed_sibling_files(built):
    base_doc = json.loads((OUT_DIR / built["baseDataset"]).read_text(encoding="utf-8"))
    node_ref = base_doc["geometry"]["nodePositions"]
    edge_ref = base_doc["geometry"]["edgePolylines"]

    node_path = OUT_DIR / node_ref["file"]
    edge_path = OUT_DIR / edge_ref["file"]
    assert node_path.is_file()
    assert edge_path.is_file()

    # 4 bytes per float32 element, matching pipeline/geometry.py's struct.pack("<Nf", ...).
    assert node_path.stat().st_size == node_ref["length"] * 4
    assert edge_path.stat().st_size == edge_ref["length"] * 4


def test_manifest_and_integrity_are_the_only_unhashed_dataset_files():
    top_level_files = [p for p in OUT_DIR.iterdir() if p.is_file()]
    unhashed = sorted(p.name for p in top_level_files if p.name.count(".") < 2)
    assert unhashed == ["integrity.json", "manifest.json"]


def test_icon_atlases_are_written_and_referenced_correctly(built):
    """tools/build_dataset.py previously never wrote atlas image files at all --
    base-dataset.json referenced technologies_0.webp/.png etc. and none of those files existed.
    Closed this session: real sheets, content-hashed, referenced by base-dataset.json's own
    iconAtlases entries (not just present in manifest.json's iconAtlases section)."""
    assert len(built["iconAtlases"]) == 3
    for sheet_name, paths in built["iconAtlases"].items():
        webp_path = OUT_DIR / paths["webp"]
        png_path = OUT_DIR / paths["png"]
        assert webp_path.is_file(), paths["webp"]
        assert png_path.is_file(), paths["png"]
        assert paths["webp"].startswith(f"{sheet_name}.") and paths["webp"].endswith(".webp")
        assert paths["png"].startswith(f"{sheet_name}.") and paths["png"].endswith(".png")

    base_doc = json.loads((OUT_DIR / built["baseDataset"]).read_text(encoding="utf-8"))
    assert len(base_doc["iconAtlases"]) == 3
    for entry in base_doc["iconAtlases"]:
        assert entry["webp"] == built["iconAtlases"][entry["name"]]["webp"]
        assert entry["png"] == built["iconAtlases"][entry["name"]]["png"]
        assert (OUT_DIR / entry["webp"]).is_file()
        assert (OUT_DIR / entry["png"]).is_file()

    # Real measured total (spec/decisions.md's vendoring-automation investigation): ~4.60 MB
    # WebP + ~5.72 MB PNG. Locked in loosely so a future change that materially grows the atlas
    # set (many more/larger icons) is visible here, not just discovered as a slow deploy.
    total_bytes = sum(
        (OUT_DIR / paths["webp"]).stat().st_size + (OUT_DIR / paths["png"]).stat().st_size
        for paths in built["iconAtlases"].values()
    )
    assert 9_000_000 < total_bytes < 13_000_000


def test_integrity_manifest_is_complete_and_honest(built):
    integrity = json.loads((OUT_DIR / "integrity.json").read_text(encoding="utf-8"))

    assert integrity["pipeline"]["commit"]  # a real SHA, not null -- this repo is a git checkout
    assert isinstance(integrity["pipeline"]["workingTreeDirty"], bool)

    assert integrity["vendor"]["available"] is True
    assert integrity["vendor"]["vanilla"]["gameVersion"]
    assert set(integrity["vendor"]["mods"]) == {"gigastructures", "acot", "aot"}
    for mod_info in integrity["vendor"]["mods"].values():
        assert mod_info.get("hash")  # every mod has a content hash; vanilla itself does not (no
        # equivalent field exists in vendor/manifest.json today -- an honest, pre-existing gap,
        # not something this integrity manifest invents an answer for)

    assert integrity["vendorSourcesLoaded"] == ["Vanilla", "Gigastructural Engineering", "ACOT", "AoT"]

    # Every artefact this script wrote (dataset JSON, geometry, atlases) has a checksum, and every
    # checksum corresponds to a real file with matching content -- not just present, but correct.
    all_manifest_paths = (
        [built["baseDataset"], built["searchIndex"], built["diagnostics"]]
        + list(built["overlays"].values())
        + list(built["details"].values())
        + [p for paths in built["iconAtlases"].values() for p in paths.values()]
    )
    for rel_path in all_manifest_paths:
        assert rel_path in integrity["artefactChecksums"], rel_path
        import hashlib

        actual = hashlib.sha256((OUT_DIR / rel_path).read_bytes()).hexdigest()
        assert integrity["artefactChecksums"][rel_path] == actual, rel_path

    # NOT part of artefactChecksums: manifest.json and integrity.json themselves (the manifest
    # can't checksum itself, and integrity.json is the checksum list -- checksumming itself would
    # need to exclude itself from itself, needless complexity for no real benefit here).
    assert "manifest.json" not in integrity["artefactChecksums"]
    assert "integrity.json" not in integrity["artefactChecksums"]

    assert "does NOT make the build CI-verifiable" in integrity["note"]
