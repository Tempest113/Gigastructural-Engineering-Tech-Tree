"""Asserts schema/generated/dataset-types.ts is exactly what tools/generate_typescript_types.py
would produce right now from schema/*.json.

This is the enforcement mechanism for "TypeScript types generated from it" (spec/00-overview.md)
actually meaning something: without this test, nothing stops a future change from editing the
JSON Schema and forgetting to regenerate, or editing the generated .ts file by hand to patch
around a generator gap — either one lets the two sides of the cross-language contract drift
apart silently, which is the exact failure mode this file exists to catch.
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GENERATED_PATH = REPO_ROOT / "schema" / "generated" / "dataset-types.ts"


def test_generated_typescript_matches_a_fresh_run():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "generate_typescript_types", REPO_ROOT / "tools" / "generate_typescript_types.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    fresh = module.generate()
    checked_in = GENERATED_PATH.read_text(encoding="utf-8")
    assert fresh == checked_in, (
        "schema/generated/dataset-types.ts does not match a fresh generation from schema/*.json "
        "-- run `python tools/generate_typescript_types.py` and commit the result"
    )


def test_generator_check_mode_agrees():
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "generate_typescript_types.py"), "--check"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
