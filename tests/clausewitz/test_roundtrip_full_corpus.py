"""Round-trip check over the *real* scoped corpus (spec/00-overview.md's required directories:
`common/technology`, `common/scripted_variables`, `common/scripted_triggers`,
`common/ascension_perks`, `common/inline_scripts`, across all four vendored sources), as opposed
to `test_roundtrip.py`, which only covers the small, curated, git-committed fixture subset of it.

`vendor/` is gitignored (CLAUDE.md's "Source data" — base-game and Steam Workshop content is not
redistributable) and populated locally by `tools/collect_vanilla.py`. CI never has it, so every
test in this file is skipped when `vendor/` isn't present rather than failing — the same posture
`tools/regenerate_fixtures.py` takes, just applied to a test instead of a fixture-generation
script. Run this locally (with `vendor/` populated) for the authoritative "does the parser
round-trip the required directories" answer; `test_roundtrip.py` is the CI-safe proxy for it.

Corpus discovery: `common/technology`, `common/scripted_variables`, `common/scripted_triggers`
and `common/ascension_perks` are small enough (243 files total, verified) to include wholesale,
matching every other file in each of those four directories across all four sources being
in-scope per spec/00-overview.md with no filtering. Sites where source and serialised tokens
disagree only on inter-token separator presence are checked against
`roundtrip_allowlist.json` — see that file for what an entry means and the review rules before
adding one; anything not on it still fails.

`common/inline_scripts` is not included
wholesale — it holds 1,139 files across the four sources, the overwhelming majority unrelated to
anything the other four directories reference — so it's included via **dependency closure**
instead: every `inline_script = <path>` (bare or `{ script = <path> ... }` structured form)
reference found while walking the always-included 243 files (and transitively, references found
inside newly-reached inline_script files themselves) is resolved against each source's
`common/inline_scripts/<path>.txt` and added to the corpus. This reproduces the same 273-file
total this repo's fixture curation independently arrived at (see tests/fixtures/NOTES.md) — 243 +
30 reachable inline_scripts = 273 — which is corroborating evidence the closure logic here matches
the one used to select the fixtures, not just a coincidence of the final count.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.clausewitz.roundtrip_allowlist import is_allowlisted

from pipeline.clausewitz import ClausewitzError, parse_file
from pipeline.clausewitz.nodes import Assignment, Block, ConditionalBlock, Identifier, StringLiteral
from pipeline.clausewitz.roundtrip import all_token_divergences, is_adjacency_only_divergence
from pipeline.clausewitz.serializer import serialize_document

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
VENDOR_ROOT = REPO_ROOT / "vendor"

_SOURCES = {
    "stellaris": VENDOR_ROOT / "stellaris",
    "gigastructures": VENDOR_ROOT / "mods" / "gigastructures",
    "acot": VENDOR_ROOT / "mods" / "acot",
    "aot": VENDOR_ROOT / "mods" / "aot",
}
_ALWAYS_INCLUDE_DIRS = [
    "common/technology",
    "common/scripted_variables",
    "common/scripted_triggers",
    "common/ascension_perks",
]

_vendor_populated = VENDOR_ROOT.is_dir() and any(root.is_dir() for root in _SOURCES.values())


def _always_include_files() -> list[Path]:
    files: list[Path] = []
    for root in _SOURCES.values():
        for rel in _ALWAYS_INCLUDE_DIRS:
            base = root / rel
            if base.is_dir():
                files.extend(sorted(base.rglob("*.txt")))
    return files


def _walk_items(items):
    for item in items:
        if isinstance(item, Assignment):
            yield item
            if isinstance(item.value, Block):
                yield from _walk_items(item.value.items)
        elif isinstance(item, ConditionalBlock):
            yield from _walk_items(item.items)


def _extract_inline_script_paths(doc) -> list[str]:
    paths = []
    for a in _walk_items(doc.items):
        if a.key_name != "inline_script":
            continue
        if isinstance(a.value, Identifier):
            paths.append(a.value.name)
        elif isinstance(a.value, StringLiteral):
            paths.append(a.value.value)
        elif isinstance(a.value, Block):
            for sub in a.value.items:
                if isinstance(sub, Assignment) and sub.key_name == "script":
                    if isinstance(sub.value, Identifier):
                        paths.append(sub.value.name)
                    elif isinstance(sub.value, StringLiteral):
                        paths.append(sub.value.value)
    return paths


def _resolve_inline_script_path(path_str: str) -> list[Path]:
    found = []
    for root in _SOURCES.values():
        candidate = root / "common" / "inline_scripts" / f"{path_str}.txt"
        if candidate.is_file():
            found.append(candidate)
    return found


def _discover_scoped_corpus() -> list[Path]:
    always = _always_include_files()
    visited = set(always)
    queue = list(always)
    while queue:
        path = queue.pop()
        try:
            doc = parse_file(path)
        except ClausewitzError:
            continue
        for p in _extract_inline_script_paths(doc):
            for resolved in _resolve_inline_script_path(p):
                if resolved not in visited:
                    visited.add(resolved)
                    queue.append(resolved)
    return sorted(visited)


SCOPED_CORPUS = _discover_scoped_corpus() if _vendor_populated else []

pytestmark = pytest.mark.skipif(
    not _vendor_populated,
    reason="vendor/ not populated — run `python tools/collect_vanilla.py` first (see CLAUDE.md's Source data table)",
)


def test_scoped_corpus_size_matches_fixture_curation_count():
    # 243 always-included + 30 reachable inline_scripts = 273 — see tests/fixtures/NOTES.md.
    # A drift here (new files added upstream, a resolution-logic change) isn't necessarily wrong,
    # but it's exactly the kind of thing worth a human looking at before trusting the round-trip
    # numbers below, so this is a loud assertion, not a silent len() in a report.
    assert len(SCOPED_CORPUS) == 273, (
        f"scoped corpus is {len(SCOPED_CORPUS)} files, not the 273 tests/fixtures/NOTES.md "
        "documents — vendor/ content or the inline_script closure logic has drifted; "
        "re-derive the expected count before trusting round-trip results against it"
    )


@pytest.mark.parametrize(
    "path",
    SCOPED_CORPUS,
    ids=lambda p: str(p.relative_to(VENDOR_ROOT)) if _vendor_populated else "vendor-not-populated",
)
def test_scoped_corpus_file_round_trips_modulo_insignificant_whitespace(path: Path):
    source = path.read_bytes().decode("utf-8")
    doc = parse_file(path)
    serialized = serialize_document(doc)
    rel_file = str(path.relative_to(REPO_ROOT))

    unallowlisted = []
    for idx, s, t in all_token_divergences(source, serialized):
        if is_adjacency_only_divergence(s, t) and is_allowlisted(rel_file, idx, s, t):
            continue
        unallowlisted.append((idx, s, t))

    if unallowlisted:
        pytest.fail(
            f"{path}: serialised AST does not round-trip to the source (modulo insignificant "
            f"whitespace and reviewed roundtrip_allowlist.json entries) — "
            f"{len(unallowlisted)} unallowlisted divergence(s), first: {unallowlisted[0]}"
        )
