"""The cheap analogue of the Clausewitz AST round-trip check (pipeline/clausewitz/roundtrip.py),
applied to localisation values.

There is no separate serialiser here — the value grammar is simple enough (first-quote to
last-quote on one physical line) that the check is direct: for every `LocEntry` parsed from a
real fixture, the delimiters implied by `entry.value.quoted` must, when placed back around
`entry.value.raw`, reproduce the exact source bytes on that line. This makes "markup is
preserved, nothing was stripped or resolved" a standing, per-entry assertion rather than an
intention — the same "prove it, don't assert it" principle as the Clausewitz round-trip work,
scaled to this format's much simpler grammar.
"""

from pathlib import Path

import pytest

from tests.localisation.conftest import LOC_FIXTURES_ROOT

from pipeline.localisation import parse_text

FIXTURE_DIRS = ["stellaris", "gigastructures", "acot", "aot"]


def _discover_fixtures() -> list[Path]:
    paths = []
    for d in FIXTURE_DIRS:
        root = LOC_FIXTURES_ROOT / d
        if root.is_dir():
            paths.extend(sorted(root.rglob("*.yml")))
    return paths


FIXTURES = _discover_fixtures()


def _load_for_roundtrip(path: Path):
    """Several fixtures are body-only excerpts of a real file (no `l_english:` header — see
    conftest.parse_excerpt). Prepending a synthetic header when needed, and then parsing and
    line-indexing that *exact* text (rather than the raw file), keeps `entry.line` consistent
    with whichever text was actually fed to the parser — sidesteps an off-by-one that would
    otherwise appear for every headerless excerpt."""
    raw = path.read_bytes().decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    first_content = next((line for line in raw.split("\n") if line.strip() != ""), "")
    if not first_content.strip().startswith("l_"):
        raw = "l_english:\n" + raw
    doc = parse_text(raw, path=str(path))
    return raw.split("\n"), doc


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: str(p.relative_to(LOC_FIXTURES_ROOT)))
def test_every_quoted_value_reproduces_the_source_bytes_between_its_quotes(path: Path):
    source_lines, doc = _load_for_roundtrip(path)
    for entry in doc.entries:
        source_line = source_lines[entry.line - 1]
        if entry.value.quoted:
            reconstructed = f'"{entry.value.raw}"'
        else:
            reconstructed = entry.value.raw
        assert reconstructed in source_line, (
            f"{path}:{entry.line} key {entry.key!r}: stored value does not reproduce the "
            f"source bytes between its delimiters — got {reconstructed!r}, source line was "
            f"{source_line!r}"
        )


def test_round_trip_check_would_fail_if_markup_were_stripped():
    """Negative control: confirms the assertion above is actually load-bearing, not vacuous.
    A value with its `§`/`£`/`$` markup stripped (simulating a parser that "helpfully" resolved
    or discarded it before storing `raw`) must NOT reproduce the source bytes."""
    from pipeline.localisation import parse_text

    text = 'l_english:\nk:0 "§Yhello£energy£$world$§!"\n'
    doc = parse_text(text)
    entry = doc.entries[0]
    source_line = 'k:0 "§Yhello£energy£$world$§!"'
    correct = f'"{entry.value.raw}"'
    assert correct in source_line

    stripped_raw = "hello world"  # what a resolving/stripping parser would have kept instead
    assert f'"{stripped_raw}"' not in source_line
