from pathlib import Path

from tests.conftest import FIXTURES_ROOT

from pipeline.localisation import parse_text
from pipeline.localisation.nodes import LocFile

LOC_FIXTURES_ROOT = FIXTURES_ROOT / "localisation"


def parse_excerpt(relpath: str) -> LocFile:
    """Several localisation fixtures are body-only excerpts (a real file's raw byte range,
    starting partway through — see tests/fixtures/manifest.json), so they don't carry the
    source file's own `l_english:` header line. Synthesising one here (rather than committing a
    fixture that starts mid-language-declaration, which wouldn't be a faithful excerpt of the
    real source bytes) lets `parse_text` accept them without changing what's being tested."""
    path = LOC_FIXTURES_ROOT / relpath
    text = path.read_bytes().decode("utf-8-sig")
    return parse_text("l_english:\n" + text, path=str(path))
