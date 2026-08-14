"""Round-trip corruption detector, wired in as a standing test (spec/00-overview.md's
lossless-AST requirement).

A green `test_fixtures.py` run proves every fixture *parses*; it proves nothing about whether it
parses correctly — a file can parse cleanly into the wrong AST (two real examples: a `flag@root`
scope suffix that used to split into a truncated flag plus a fabricated `@variable` reference, and
a `$PARAM$\n$PARAM$` pair that used to glue onto adjacent identifier text). This test instead
walks each fixture's AST back to text (`pipeline/clausewitz/serializer.py`, deliberately naive —
no whitespace-reproduction cleverness) and checks it against the original source modulo the small,
closed normalisation set documented in `pipeline/clausewitz/roundtrip.py` (BOM stripping, CRLF
normalisation, and insignificant inter-token whitespace, judged by re-tokenising both sides).
Anything else that differs is real data loss or misattachment, i.e. a parser bug — see that
module's docstring for the full justification of what is and isn't normalised.

Scope: **this is the committed fixture subset, not spec/00-overview.md's required directories**
(`common/technology`, `common/scripted_variables`, `common/scripted_triggers`,
`common/ascension_perks`, `common/inline_scripts`, across all four vendored sources — 273 files,
verified by walking `vendor/` directly). That full corpus lives outside git (`vendor/` is
gitignored per CLAUDE.md's "Source data"), so it can't be this file's parametrisation — CI has no
vendor/ to walk. `test_roundtrip_full_corpus.py` covers the real 273-file corpus instead, guarded
to skip when `vendor/` isn't populated locally; treat *that* file's result as authoritative for
"does the parser round-trip the required directories," and this file as a CI-safe regression net
over a curated slice of it (plus the BOM/CRLF encoding fixtures, which aren't part of the required
directories at all). This runs on the raw parse only — before `@variable` resolution and before
`inline_script` expansion, both later, separate passes (see nodes.py's module docstring) that this
parser doesn't perform. **Deliberately excluded**: expanded `inline_script` output. Once that pass
exists, its output has no single source file to diff against (it's assembled from an invocation
site plus a separately-parsed target file), so a byte-for-byte round-trip check against "the
source" doesn't have a well-defined "the source" to check against there — this test only ever
covers the pre-expansion AST this parser module actually produces.

`malformed/` and `windows-1252.txt` are excluded — they're expected to fail to parse at all, so
there's no AST to round-trip.

A handful of these fixtures have sites where the source and serialised token streams disagree
only on inter-token separator presence (never on token content) — see `roundtrip_allowlist.json`
for what that means, why it can't be normalised away, and the review rules for adding an entry.
Every such site here is individually allowlisted; anything not on that list still fails the test.
"""

from pathlib import Path

import pytest

from tests.conftest import FIXTURES_ROOT
from tests.clausewitz.roundtrip_allowlist import is_allowlisted

from pipeline.clausewitz import parse_file
from pipeline.clausewitz.roundtrip import all_token_divergences, is_adjacency_only_divergence
from pipeline.clausewitz.serializer import serialize_document

REPO_ROOT = FIXTURES_ROOT.parent.parent
_SCRIPT_DIRS = ["gigastructures", "stellaris", "acot", "aot"]


def _discover(*dirnames: str, pattern: str = "*.txt") -> list[Path]:
    paths: list[Path] = []
    for d in dirnames:
        root = FIXTURES_ROOT / d
        if root.is_dir():
            paths.extend(sorted(root.rglob(pattern)))
    return paths


ROUNDTRIP_FIXTURES = _discover(*_SCRIPT_DIRS) + [
    FIXTURES_ROOT / "encoding" / "utf8-bom.txt",
    FIXTURES_ROOT / "encoding" / "lf.txt",
    FIXTURES_ROOT / "encoding" / "crlf.txt",
]

if not ROUNDTRIP_FIXTURES:
    pytest.fail(
        "tests/fixtures/ appears empty. Run `python tools/regenerate_fixtures.py` "
        "first (with vendor/ populated) — see tests/fixtures/NOTES.md."
    )


@pytest.mark.parametrize("path", ROUNDTRIP_FIXTURES, ids=lambda p: str(p.relative_to(FIXTURES_ROOT)))
def test_fixture_round_trips_modulo_insignificant_whitespace(path: Path):
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
