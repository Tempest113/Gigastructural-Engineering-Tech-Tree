#!/usr/bin/env python3
"""
Reproduces tests/fixtures/ from vendor/, driven by tests/fixtures/manifest.json.

tests/fixtures/ contains verbatim excerpts of Stellaris and Steam Workshop mod source, which
cannot be committed to a public repository (the same redistribution constraint that keeps
vendor/ itself out of git — see CLAUDE.md). What IS committed is manifest.json: for every
fixture, its source path relative to vendor/, whether it's a whole file or an excerpt (and if
so, which lines), and a sha256 of the fixture's exact bytes. This script is the only thing that
turns that manifest back into real files, and it refuses to produce a fixture whose extracted
content doesn't match the recorded hash — that mismatch means the vendored source has drifted
since the fixture was captured, and silently regenerating a different file than the one the
tests and NOTES.md describe would be worse than failing loudly.

tests/fixtures/malformed/ and tests/fixtures/encoding/ are hand-authored, not vendor-derived,
and are committed directly — this script does not touch them.

Usage:
    python tools/regenerate_fixtures.py              # regenerate + verify from vendor/
    python tools/regenerate_fixtures.py --update      # re-capture hashes after an intentional
                                                       # fixture change (edit manifest.json's
                                                       # source/lines first, then run this)
    python tools/regenerate_fixtures.py --check       # verify only, write nothing
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VENDOR_ROOT = REPO_ROOT / "vendor"
FIXTURES_ROOT = REPO_ROOT / "tests" / "fixtures"
MANIFEST_PATH = FIXTURES_ROOT / "manifest.json"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def extract_whole(source_path: Path) -> bytes:
    return source_path.read_bytes()


def extract_excerpt(source_path: Path, lines: list[int]) -> bytes:
    """lines is [start, end], 1-indexed, inclusive, matching the source file's own line numbers."""
    start, end = lines
    raw = source_path.read_bytes()
    # Split keeping line endings so CRLF sources stay CRLF, LF sources stay LF.
    all_lines = raw.splitlines(keepends=True)
    if start < 1 or end > len(all_lines) or start > end:
        raise ValueError(
            f"line range {lines} is out of bounds for {source_path} ({len(all_lines)} lines)"
        )
    return b"".join(all_lines[start - 1 : end])


def extract_spliced_excerpt(source_path: Path, segments: list[list[int]], separator: str) -> bytes:
    """Non-contiguous excerpt: several line ranges from one source, joined by `separator`
    (a literal string, e.g. "\\r\\n" for a blank CRLF-terminated line) between each pair of
    segments. Each segment is extracted exactly like extract_excerpt."""
    # JSON already decoded the "\r\n" escape into real CR/LF characters; encode as-is.
    sep_bytes = separator.encode("utf-8")
    parts = [extract_excerpt(source_path, seg) for seg in segments]
    return sep_bytes.join(parts)


def build_fixture(entry: dict) -> bytes:
    source_path = VENDOR_ROOT / entry["source"]
    if not source_path.is_file():
        raise FileNotFoundError(str(source_path))

    kind = entry["type"]
    if kind == "whole":
        return extract_whole(source_path)
    elif kind == "excerpt":
        return extract_excerpt(source_path, entry["lines"])
    elif kind == "spliced-excerpt":
        return extract_spliced_excerpt(source_path, entry["segments"], entry["separator"])
    else:
        raise ValueError(f"unknown fixture type {kind!r} for {entry['dest']}")


def load_manifest() -> dict:
    if not MANIFEST_PATH.is_file():
        sys.exit(f"FATAL: manifest not found at {MANIFEST_PATH}")
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--update", action="store_true",
        help="recompute and rewrite hashes in manifest.json from vendor/, instead of verifying against them",
    )
    parser.add_argument(
        "--check", action="store_true",
        help="verify hashes only; do not write fixture files",
    )
    args = parser.parse_args()

    if not VENDOR_ROOT.is_dir():
        sys.exit(
            "FATAL: vendor/ is absent.\n"
            "tests/fixtures/ is reproduced from local Stellaris and Steam Workshop mod source,\n"
            "which this repository never commits (see CLAUDE.md, 'Source data').\n"
            "Populate it first:\n"
            "  - Stellaris base game:        python tools/collect_vanilla.py\n"
            "  - Gigastructural Engineering: automated collector (CI) or manual clone into\n"
            "                                vendor/mods/gigastructures/\n"
            "  - ACOT / AoT:                 Steam Workshop only — subscribe and copy the\n"
            "                                installed mod folders into vendor/mods/acot/ and\n"
            "                                vendor/mods/aot/ by hand."
        )

    manifest = load_manifest()
    entries = manifest["fixtures"]

    failures: list[str] = []
    missing_sources: list[str] = []
    mismatches: list[str] = []
    written = 0
    verified = 0

    for entry in entries:
        dest = entry["dest"]
        try:
            content = build_fixture(entry)
        except FileNotFoundError as e:
            missing_sources.append(f"{dest}: source not in vendor/ ({e})")
            continue
        except ValueError as e:
            failures.append(f"{dest}: {e}")
            continue

        actual_hash = sha256_bytes(content)
        expected_hash = entry["sha256"]

        if args.update:
            entry["sha256"] = actual_hash
        elif actual_hash != expected_hash:
            mismatches.append(
                f"{dest}: hash mismatch\n"
                f"    source:   {entry['source']}\n"
                f"    expected: {expected_hash}\n"
                f"    actual:   {actual_hash}\n"
                f"    vendor/{entry['source']} has changed since this fixture was captured."
            )
            continue

        verified += 1
        if not args.check:
            dest_path = FIXTURES_ROOT / dest
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            dest_path.write_bytes(content)
            written += 1

    if args.update:
        MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        print(f"Updated hashes for {len(entries)} entries in {MANIFEST_PATH}.")
        return 0

    if missing_sources:
        print("FATAL: some fixtures reference vendor/ files that don't exist:", file=sys.stderr)
        for line in missing_sources:
            print(f"  - {line}", file=sys.stderr)
        failures.append("missing sources")

    if mismatches:
        print("FATAL: some fixtures no longer match their recorded hash:", file=sys.stderr)
        for line in mismatches:
            print(f"  - {line}", file=sys.stderr)
        failures.append("hash mismatches")

    if failures:
        print(
            f"\n{verified}/{len(entries)} fixtures verified OK; {len(missing_sources)} missing "
            f"source(s), {len(mismatches)} hash mismatch(es). Nothing was silently regenerated "
            f"from drifted content.",
            file=sys.stderr,
        )
        return 1

    action = "verified" if args.check else f"verified and wrote {written} file(s)"
    print(f"OK: {action}, {verified}/{len(entries)} fixtures.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
