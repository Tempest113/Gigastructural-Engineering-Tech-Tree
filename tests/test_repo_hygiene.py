"""Guards against the exact defect a reconciliation session found and fixed: ten real,
load-bearing files (client/src/{tokens,camera,lod}.ts among them) sat untracked across many
sessions with no .gitignore pattern excluding them and no signal ever raised. `client/src/` and
`pipeline/` are this project's two source trees where an untracked file is never intentional (a
build artefact or generated output belongs under an already-ignored directory, per .gitignore's
own comments) -- an untracked file under either one is either forgotten work or a real bug.

Guard extended (Item 1a, gate-classification survey session) to `tests/`, `spec/`, `config/` and
`docs/` after this very file -- the check whose purpose is to catch untracked source -- was
itself found untracked, having shipped in a tree (`tests/`) its own guard list didn't cover.
Same reasoning applies to `spec/` (normative requirements), `config/` (hand-maintained overrides
CLAUDE.md's Rules names as the only legitimate hand-authored files) and `docs/` (the build log):
none of these trees ever legitimately contains a derived/disposable file, so untracked always
means forgotten work or a bug, never noise to ignore.

This check is LOCAL-ONLY by construction: CI checks out a fresh clone from committed history, so
it can never observe an untracked file in someone's working tree -- the failure mode this guards
against is invisible to CI by definition. It has value precisely because `pytest` is run
manually/locally every session (CLAUDE.md's Commands section), which is the actual point an
untracked file under one of these trees would get caught."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
GUARDED_PREFIXES = ("client/src/", "pipeline/", "tests/", "spec/", "config/", "docs/")


def _git_available() -> bool:
    return shutil.which("git") is not None and (REPO_ROOT / ".git").exists()


def _offending(untracked_paths: list[str]) -> list[str]:
    return [path for path in untracked_paths if path.startswith(GUARDED_PREFIXES)]


def test_detector_flags_a_synthetic_untracked_guarded_file():
    """Proves the detector is capable of failing before trusting a clean real-repo run --
    this project's own standing rule (CLAUDE.md: "a clean run proves nothing until the detector
    is shown capable of a dirty one"). Exercises `_offending` directly against a synthetic
    untracked-file list, not the real repo, so it can never mutate real working-tree state."""
    assert _offending(["client/src/rogue.ts", "docs/rogue.md", "vendor/manifest.json"]) == [
        "client/src/rogue.ts", "docs/rogue.md"
    ]
    assert _offending(["pipeline/rogue.py"]) == ["pipeline/rogue.py"]
    assert _offending(["tests/rogue.py", "spec/rogue.md", "config/rogue.txt"]) == [
        "tests/rogue.py", "spec/rogue.md", "config/rogue.txt"
    ]
    assert _offending(["schema/generated/dataset-types.ts", "vendor/manifest.json"]) == []


@pytest.mark.skipif(not _git_available(), reason="not running inside a git working tree")
def test_no_untracked_files_under_guarded_source_trees():
    result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    )
    untracked = [line[3:] for line in result.stdout.splitlines() if line.startswith("??")]
    offending = _offending(untracked)
    assert not offending, (
        f"Untracked file(s) under a guarded source tree ({', '.join(GUARDED_PREFIXES)}): "
        f"{offending}. Either `git add` them (if real work) or add a .gitignore pattern (if "
        "genuinely derived/disposable) -- never leave a guarded-tree file untracked silently."
    )
