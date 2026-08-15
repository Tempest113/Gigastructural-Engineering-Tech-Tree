"""Tests for pipeline.rendering_scope -- P-16 rendering-scope closure.

Synthetic mechanism test plus a real-corpus regression asserting the exact figures HANDOFF.md's
manual P-16 measurement recorded, so a future corpus refresh that silently changes them fails a
test instead of going unnoticed (same posture as tests/test_overwrites_corpus.py's 25-overlap
assertion).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.clausewitz import parse_file, parse_text
from pipeline.overwrites import collect_technology_definitions
from pipeline.rendering_scope import compute_alternative_only_gaps, compute_rendering_scope, rendered_technology_keys

REPO_ROOT = Path(__file__).resolve().parent.parent
VENDOR_ROOT = REPO_ROOT / "vendor"
_vendor_populated = (VENDOR_ROOT / "stellaris" / "common" / "technology").is_dir()


def _doc(text, path):
    return parse_text(text, path=path)


def test_synthetic_closure_is_transitive_and_stops_at_rendered_sources():
    vanilla = _doc(
        "tech_vanilla_a = { prerequisites = { tech_vanilla_b } }\n"
        "tech_vanilla_b = { prerequisites = { } }\n",
        "vanilla.txt",
    )
    giga = _doc("tech_giga_a = { prerequisites = { tech_acot_a } }\n", "giga.txt")
    acot = _doc(
        "tech_acot_a = { prerequisites = { tech_acot_b tech_vanilla_b } }\n"
        "tech_acot_b = { prerequisites = { tech_acot_c } }\n"
        "tech_acot_c = { prerequisites = { } }\n"
        "tech_acot_unreferenced = { prerequisites = { } }\n",
        "acot.txt",
    )
    history = collect_technology_definitions(
        [("Vanilla", [vanilla]), ("Gigastructural Engineering", [giga]), ("ACOT", [acot])]
    )
    closure = compute_rendering_scope(history)
    assert closure == {"tech_acot_a", "tech_acot_b", "tech_acot_c"}
    assert "tech_acot_unreferenced" not in closure  # no rendered descendant -> not in closure

    rendered = rendered_technology_keys(history)
    assert rendered == {
        "tech_vanilla_a", "tech_vanilla_b", "tech_giga_a",
        "tech_acot_a", "tech_acot_b", "tech_acot_c",
    }


def test_closure_ignores_a_reference_back_into_a_rendered_source():
    # tech_acot_a references a vanilla technology -- already rendered unconditionally, must not
    # be double-counted or cause an error.
    vanilla = _doc("tech_vanilla_a = { prerequisites = { } }\n", "vanilla.txt")
    giga = _doc("tech_giga_a = { prerequisites = { tech_acot_a } }\n", "giga.txt")
    acot = _doc("tech_acot_a = { prerequisites = { tech_vanilla_a } }\n", "acot.txt")
    history = collect_technology_definitions(
        [("Vanilla", [vanilla]), ("Gigastructural Engineering", [giga]), ("ACOT", [acot])]
    )
    assert compute_rendering_scope(history) == {"tech_acot_a"}


# ---------------------------------------------------------------------------
# compute_alternative_only_gaps -- P-16 tripwire diagnostic (decision e)
# ---------------------------------------------------------------------------


def test_alternative_only_gap_is_detected_when_the_only_path_is_an_or_branch():
    vanilla = _doc("tech_vanilla_a = { prerequisites = { } }\n", "vanilla.txt")
    giga = _doc(
        "tech_giga_a = { prerequisites = { OR = { tech_acot_a tech_vanilla_a } } }\n", "giga.txt"
    )
    acot = _doc("tech_acot_a = { prerequisites = { } }\n", "acot.txt")
    history = collect_technology_definitions(
        [("Vanilla", [vanilla]), ("Gigastructural Engineering", [giga]), ("ACOT", [acot])]
    )
    # tech_acot_a is referenced ONLY via the OR group -- the prerequisite-only closure excludes
    # it, so it must show up as a gap.
    assert compute_rendering_scope(history) == set()
    assert compute_alternative_only_gaps(history) == {"tech_acot_a"}


def test_no_gap_when_the_same_technology_also_has_a_true_prerequisite_path():
    vanilla = _doc("tech_vanilla_a = { prerequisites = { } }\n", "vanilla.txt")
    giga = _doc(
        "tech_giga_a = { prerequisites = { tech_acot_a OR = { tech_acot_a tech_vanilla_a } } }\n",
        "giga.txt",
    )
    acot = _doc("tech_acot_a = { prerequisites = { } }\n", "acot.txt")
    history = collect_technology_definitions(
        [("Vanilla", [vanilla]), ("Gigastructural Engineering", [giga]), ("ACOT", [acot])]
    )
    # tech_acot_a is ALSO a true prerequisite here -- already in the real closure, not a gap.
    assert compute_rendering_scope(history) == {"tech_acot_a"}
    assert compute_alternative_only_gaps(history) == set()


@pytest.mark.skipif(not _vendor_populated, reason="vendor/ not populated locally")
def test_real_corpus_has_no_alternative_only_gaps(corpus_history):
    # Verified, not assumed: the closure is identical whether OR-branch members are treated as
    # traversable or not, on the real corpus. Fails loudly if a future re-vendor ever changes
    # this, per decision (e)'s "surfaced, not silently dropped" tripwire.
    assert compute_alternative_only_gaps(corpus_history) == set()


# ---------------------------------------------------------------------------
# Real corpus
# ---------------------------------------------------------------------------

_SOURCES_IN_LOAD_ORDER = [
    ("Vanilla", VENDOR_ROOT / "stellaris"),
    ("Gigastructural Engineering", VENDOR_ROOT / "mods" / "gigastructures"),
    ("ACOT", VENDOR_ROOT / "mods" / "acot"),
    ("AoT", VENDOR_ROOT / "mods" / "aot"),
]

pytestmark_corpus = pytest.mark.skipif(not _vendor_populated, reason="vendor/ not populated locally")


@pytest.fixture(scope="module")
def corpus_history():
    tech_docs = [
        (name, [parse_file(f) for f in sorted((root / "common" / "technology").glob("*.txt"))])
        for name, root in _SOURCES_IN_LOAD_ORDER
        if (root / "common" / "technology").is_dir()
    ]
    return collect_technology_definitions(tech_docs)


@pytest.mark.skipif(not _vendor_populated, reason="vendor/ not populated locally")
def test_real_corpus_closure_matches_handoff_measurement(corpus_history):
    closure = compute_rendering_scope(corpus_history)
    assert closure == {
        "tech_dark_matter_power_core_dm",
        "tech_dark_matter_power_core_ae",
        "tech_dark_matter_power_core_se",
        "tech_civil_phanon_application",
        "tech_mine_dark_energy",
        "tech_dark_matter_power_core_enig",
        "tech_precursor_design",
    }


@pytest.mark.skipif(not _vendor_populated, reason="vendor/ not populated locally")
def test_real_corpus_rendered_total_is_980(corpus_history):
    assert len(rendered_technology_keys(corpus_history)) == 980
