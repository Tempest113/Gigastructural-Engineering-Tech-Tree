"""Full localisation/english/ corpus run across all four vendored sources (spec/00-overview.md's
required directories), mirroring tests/clausewitz/test_roundtrip_full_corpus.py's posture:
`vendor/` is gitignored (CLAUDE.md's "Source data"), so this is skipped whenever it isn't
populated locally rather than failing CI, which never has it. Run this locally for the
authoritative "does the parser handle the real corpus" answer.

Reports parse failures by category — mirroring the Clausewitz corpus report's format — rather
than a single flat count, since a file-level failure (bad header, bad encoding) and a per-entry
malformed diagnostic are different kinds of finding with different implications.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import REPO_ROOT

from pipeline.localisation import LocalisationError, parse_file
from pipeline.localisation.sources import default_source_configs
from pipeline.localisation.table import build_table, find_unquoted_value_diagnostics, find_value_is_key_diagnostics

VENDOR_ROOT = REPO_ROOT / "vendor"
_vendor_populated = VENDOR_ROOT.is_dir()

pytestmark = pytest.mark.skipif(
    not _vendor_populated,
    reason="vendor/ not populated — run `python tools/collect_vanilla.py` first (see CLAUDE.md's Source data)",
)


def _discover_all_files():
    if not _vendor_populated:
        return []
    files = []
    for config in default_source_configs(VENDOR_ROOT):
        for path in config.resolve("english"):
            files.append((config.name, path))
    return files


ALL_FILES = _discover_all_files()


def test_corpus_size_matches_survey_count():
    # 353 English .yml files across all four sources, verified by filename-suffix glob during
    # the Step 1/2 survey (46 acot + 25 aot + 50 gigastructures + 232 stellaris).
    assert len(ALL_FILES) == 353, (
        f"corpus is {len(ALL_FILES)} files, not the 353 the survey found — vendor/ content or "
        f"source config has drifted; re-derive the expected count before trusting the report below"
    )


@pytest.mark.parametrize("source_name,path", ALL_FILES, ids=lambda v: str(v) if isinstance(v, Path) else v)
def test_every_localisation_file_parses(source_name, path):
    # A file-level failure here (bad header, bad encoding) is a hard stop for that one file —
    # unlike a per-entry MalformedEntry, which parse_file already handles by not raising.
    parse_file(path)


def test_full_corpus_report():
    """Not a pass/fail assertion by itself (the per-file parametrised test above already is) —
    builds the full resolved table and prints a category breakdown, matching the Clausewitz
    corpus report's format, for a human to read when running this locally."""
    files_in_load_order = []
    file_level_failures = []
    for config in default_source_configs(VENDOR_ROOT):
        for path in config.resolve("english"):
            try:
                doc = parse_file(path)
            except LocalisationError as exc:
                file_level_failures.append((config.name, path, exc))
                continue
            files_in_load_order.append((config.name, doc))

    table = build_table("english", files_in_load_order)
    value_is_key = find_value_is_key_diagnostics(table)
    unquoted = find_unquoted_value_diagnostics(table)

    malformed_by_reason: dict[str, int] = {}
    for m in table.malformed:
        malformed_by_reason[m.reason] = malformed_by_reason.get(m.reason, 0) + 1

    print(f"\nfiles parsed: {len(files_in_load_order)} / {len(ALL_FILES)}")
    print(f"file-level failures: {len(file_level_failures)}")
    for source_name, path, exc in file_level_failures:
        print(f"  FILE FAILURE [{source_name}] {path}: {exc}")
    print(f"resolved keys: {len(table.entries)}")
    print(f"malformed entries: {len(table.malformed)}")
    for reason, count in sorted(malformed_by_reason.items()):
        print(f"  {count:4d}  {reason}")
    for m in table.malformed:
        print(f"    [{m.source}] {m.file}:{m.line}: {m.reason} -- {m.raw_line.strip()[:100]!r}")
    print(f"value-is-key diagnostics: {len(value_is_key)}")
    for d in value_is_key[:20]:
        print(f"  [{d.source}] {d.file}:{d.line}: {d.key!r} -> {d.value!r}")
    print(f"unquoted-value diagnostics: {len(unquoted)} (single-occurrence evidence base; see table.py)")
    for d in unquoted:
        print(f"  [{d.source}] {d.file}:{d.line}: {d.key!r} -> {d.value!r}")

    assert not file_level_failures, f"{len(file_level_failures)} file(s) failed to parse at all"
