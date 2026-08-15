"""D-7's full three-step crisis-faction derivation, run against the real vendored corpus over
the exact 980-node P-16 rendered set -- the corrected counts Addition 2 asked for (layout
lane populations must come from the real derivation, not the provisional ID-only survey).

Skipped when vendor/ isn't populated, same posture as the other corpus tests.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from pipeline.clausewitz import parse_file
from pipeline.crisis_faction import classify_crisis_factions
from pipeline.crisis_faction_overrides import load_overrides
from pipeline.overwrites import collect_technology_definitions
from pipeline.rendering_scope import rendered_technology_keys

REPO_ROOT = Path(__file__).resolve().parent.parent
VENDOR_ROOT = REPO_ROOT / "vendor"

_SOURCES_IN_LOAD_ORDER = [
    ("Vanilla", VENDOR_ROOT / "stellaris"),
    ("Gigastructural Engineering", VENDOR_ROOT / "mods" / "gigastructures"),
    ("ACOT", VENDOR_ROOT / "mods" / "acot"),
    ("AoT", VENDOR_ROOT / "mods" / "aot"),
]

_vendor_populated = VENDOR_ROOT.is_dir() and any(root.is_dir() for _, root in _SOURCES_IN_LOAD_ORDER)

pytestmark = pytest.mark.skipif(not _vendor_populated, reason="vendor/ not populated locally")


@pytest.fixture(scope="module")
def rendered_history():
    tech_docs = [
        (name, [parse_file(f) for f in sorted((root / "common" / "technology").glob("*.txt"))])
        for name, root in _SOURCES_IN_LOAD_ORDER
        if (root / "common" / "technology").is_dir()
    ]
    history = collect_technology_definitions(tech_docs)
    rendered_keys = rendered_technology_keys(history)
    return {key: history[key][-1] for key in rendered_keys}


def test_corrected_faction_counts(rendered_history):
    overrides = load_overrides()
    result = classify_crisis_factions(rendered_history, overrides)

    counts = Counter(faction or "Standard" for faction in result.values())
    print("\n--- D-7 corrected crisis-faction populations (980 rendered nodes) ---")
    for faction, count in counts.most_common():
        print(f"  {faction}: {count}")

    assert sum(counts.values()) == 980
    # Regression anchor: step 1 (ID) is confirmed the whole derivable signal in this corpus --
    # step 2 (prerequisite inheritance) and step 3 (override table, seeded empty) both
    # contribute zero additional nodes beyond it. If a corpus refresh ever changes this, that's
    # real news (new crisis content shipped, or existing content restructured), not a silent
    # drift to wave through.
    assert counts["Standard"] == 925
    assert counts["Blokkats"] == 42
    assert counts["Sirenalia"] == 7
    assert counts["Aeternum"] == 3
    assert counts["Katzenartig Imperium"] == 3
    assert counts["Compound"] == 0


def test_confirmed_false_positive_candidates_resolve_to_standard_lane(rendered_history):
    # See pipeline/crisis_faction.py's module docstring: both were tried via potential-block
    # flag inspection and found to be false positives. Confirm the real derivation (ID +
    # prerequisite inheritance only) correctly leaves both in the standard lane.
    overrides = load_overrides()
    result = classify_crisis_factions(rendered_history, overrides)
    assert result["tech_sm_autocannons"] is None
    assert result["giga_tech_tetradimensional_engineering"] is None


def test_compound_technologies_are_commented_out_in_the_vendored_corpus():
    # Direct evidence for the "Compound is a real zero" claim: the seven tech_compound_* blocks
    # in giga_08_ehof_components.txt are present as raw text but never parse into technology
    # definitions, because every line is commented out.
    path = VENDOR_ROOT / "mods" / "gigastructures" / "common" / "technology" / "giga_08_ehof_components.txt"
    text = path.read_text(encoding="utf-8")
    compound_keys = [
        "tech_compound_armor", "tech_compound_computers", "tech_compound_drives",
        "tech_compound_reactors", "tech_compound_sensors", "tech_compound_shields",
        "tech_compound_thrusters",
    ]
    for key in compound_keys:
        assert f"# {key} = {{" in text or f"#{key} = {{" in text, f"{key} expected as commented-out source"
