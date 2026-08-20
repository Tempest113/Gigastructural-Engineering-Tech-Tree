"""Tests for pipeline.crisis_faction -- D-7/P-5's three-step crisis-faction derivation."""

from __future__ import annotations

from pipeline.clausewitz import parse_text
from pipeline.crisis_faction import (
    CRISIS_FACTIONS,
    classify_by_flag,
    classify_by_prerequisite_inheritance,
    classify_by_tech_id,
    classify_crisis_factions,
)
from pipeline.crisis_faction_flags import CrisisFactionFlagOverride
from pipeline.crisis_faction_overrides import CrisisFactionOverride
from pipeline.overwrites import TechnologyDefinition


def _def(key: str, text: str, source="Gigastructural Engineering") -> TechnologyDefinition:
    doc = parse_text(f"{key} = {text}\n", path="x.txt")
    return TechnologyDefinition(key=key, source=source, document_path="x.txt", line=1, block=doc.items[0].value)


# ---------------------------------------------------------------------------
# Step 1: technology ID
# ---------------------------------------------------------------------------


def test_all_five_factions_recognised_by_id_fragment():
    assert classify_by_tech_id("giga_tech_aeternum_relay") == "Aeternum"
    assert classify_by_tech_id("tech_aeternite_armor") == "Aeternum"
    assert classify_by_tech_id("blokkat_laser_tech") == "Blokkats"
    assert classify_by_tech_id("tech_compound_shields") == "Compound"
    assert classify_by_tech_id("giga_tech_sirenalia_core") == "Sirenalia"
    assert classify_by_tech_id("tech_siren_song") == "Sirenalia"
    assert classify_by_tech_id("tech_katzenartig_gate") == "Katzenartig Imperium"
    assert classify_by_tech_id("tech_katzen_armor") == "Katzenartig Imperium"


def test_ordinary_technology_has_no_id_faction():
    assert classify_by_tech_id("tech_lasers_2") is None


# ---------------------------------------------------------------------------
# Step 2: prerequisite inheritance
# ---------------------------------------------------------------------------


def test_inherits_faction_when_every_prerequisite_agrees():
    known = {"tech_blokkat_a": "Blokkats", "tech_blokkat_b": "Blokkats"}
    result = classify_by_prerequisite_inheritance("tech_downstream", ["tech_blokkat_a", "tech_blokkat_b"], known)
    assert result == "Blokkats"


def test_does_not_inherit_when_prerequisites_disagree():
    known = {"tech_blokkat_a": "Blokkats", "tech_sirenalia_a": "Sirenalia"}
    result = classify_by_prerequisite_inheritance("tech_downstream", ["tech_blokkat_a", "tech_sirenalia_a"], known)
    assert result is None


def test_does_not_inherit_when_a_prerequisite_is_unclassified():
    known = {"tech_blokkat_a": "Blokkats", "tech_standard": None}
    result = classify_by_prerequisite_inheritance("tech_downstream", ["tech_blokkat_a", "tech_standard"], known)
    assert result is None


def test_no_prerequisites_means_no_inheritance():
    assert classify_by_prerequisite_inheritance("tech_downstream", [], {}) is None


# ---------------------------------------------------------------------------
# Full derivation: classify_crisis_factions
# ---------------------------------------------------------------------------


def test_full_derivation_combines_id_and_inheritance():
    technologies = {
        "tech_blokkat_root": _def("tech_blokkat_root", "{ prerequisites = { } }"),
        "tech_blokkat_child": _def("tech_blokkat_child", "{ prerequisites = { tech_blokkat_root } }"),
        "tech_downstream_no_id": _def("tech_downstream_no_id", "{ prerequisites = { tech_blokkat_child } }"),
        "tech_standard": _def("tech_standard", "{ prerequisites = { } }"),
    }
    result = classify_crisis_factions(technologies)
    assert result["tech_blokkat_root"] == "Blokkats"  # step 1
    assert result["tech_blokkat_child"] == "Blokkats"  # step 1 (ID also matches)
    assert result["tech_downstream_no_id"] == "Blokkats"  # step 2, transitively through child
    assert result["tech_standard"] is None


def test_inheritance_propagates_through_a_fixed_point_regardless_of_dict_order():
    # tech_c inherits from tech_b, which itself only becomes classified via step 2 inheriting
    # from tech_a -- single-pass processing in dict order would miss tech_c if tech_b hadn't
    # been resolved yet when tech_c was checked.
    technologies = {
        "tech_c_no_id": _def("tech_c_no_id", "{ prerequisites = { tech_b_no_id } }"),
        "tech_b_no_id": _def("tech_b_no_id", "{ prerequisites = { tech_blokkat_a } }"),
        "tech_blokkat_a": _def("tech_blokkat_a", "{ prerequisites = { } }"),
    }
    result = classify_crisis_factions(technologies)
    assert result["tech_blokkat_a"] == "Blokkats"
    assert result["tech_b_no_id"] == "Blokkats"
    assert result["tech_c_no_id"] == "Blokkats"


def test_override_wins_over_automatic_classification():
    technologies = {
        "tech_blokkat_root": _def("tech_blokkat_root", "{ prerequisites = { } }"),
    }
    override = CrisisFactionOverride(technology_key="tech_blokkat_root", faction=None, justification="test", line=1)
    result = classify_crisis_factions(technologies, {"tech_blokkat_root": override})
    assert result["tech_blokkat_root"] is None


def test_override_can_assign_a_faction_id_classification_missed():
    technologies = {"tech_mystery": _def("tech_mystery", "{ prerequisites = { } }")}
    override = CrisisFactionOverride(technology_key="tech_mystery", faction="Compound", justification="test", line=1)
    result = classify_crisis_factions(technologies, {"tech_mystery": override})
    assert result["tech_mystery"] == "Compound"


def test_all_five_faction_names_match_d7_spelling():
    assert CRISIS_FACTIONS == ("Aeternum", "Blokkats", "Compound", "Sirenalia", "Katzenartig Imperium")


# ---------------------------------------------------------------------------
# Step 1.5: flag map (config/crisis_faction_flag_overrides.txt)
# ---------------------------------------------------------------------------


def _flag_override(flag_name: str, faction: str) -> dict[str, CrisisFactionFlagOverride]:
    return {flag_name: CrisisFactionFlagOverride(flag_name=flag_name, faction=faction, justification="test", line=1)}


def test_classify_by_flag_matches_mapped_flag_in_potential():
    definition = _def("tech_gated", "{ potential = { has_country_flag = my_flag } }")
    assert classify_by_flag(definition, _flag_override("my_flag", "Compound")) == "Compound"


def test_classify_by_flag_ignores_unmapped_flag():
    definition = _def("tech_gated", "{ potential = { has_country_flag = other_flag } }")
    assert classify_by_flag(definition, _flag_override("my_flag", "Compound")) is None


def test_classify_by_flag_ignores_negated_flag():
    # A flag inside NOT/NOR means "must NOT have this flag" -- the opposite of membership
    # evidence, so it must never classify.
    definition = _def("tech_gated", "{ potential = { NOT = { has_country_flag = my_flag } } }")
    assert classify_by_flag(definition, _flag_override("my_flag", "Compound")) is None


def test_classify_by_flag_descends_into_and_or_only():
    definition = _def(
        "tech_gated",
        "{ potential = { OR = { AND = { has_country_flag = my_flag } } } }",
    )
    assert classify_by_flag(definition, _flag_override("my_flag", "Compound")) == "Compound"


def test_classify_by_flag_seeds_prerequisite_inheritance():
    # The flag-classified technology can itself seed step 2 for anything that depends on it
    # ALONE (a single, non-mixed prerequisite set) -- the same way a step-1 ID match already does.
    technologies = {
        "tech_flagged": _def("tech_flagged", "{ potential = { has_country_flag = my_flag } prerequisites = { } }"),
        "tech_dependent": _def("tech_dependent", "{ prerequisites = { tech_flagged } }"),
    }
    result = classify_crisis_factions(technologies, flag_overrides=_flag_override("my_flag", "Compound"))
    assert result["tech_flagged"] == "Compound"
    assert result["tech_dependent"] == "Compound"


def test_classify_by_flag_does_not_propagate_through_a_mixed_prerequisite_set():
    # Mirrors the real corpus finding (Part 0's reconciliation, tests/test_crisis_faction_corpus.py):
    # a dependent that ALSO requires an ordinary, unclassified prerequisite does not inherit,
    # because step 2 requires every rendered prerequisite to already share one faction.
    technologies = {
        "tech_flagged": _def("tech_flagged", "{ potential = { has_country_flag = my_flag } prerequisites = { } }"),
        "tech_baseline": _def("tech_baseline", "{ prerequisites = { } }"),
        "tech_dependent": _def("tech_dependent", "{ prerequisites = { tech_flagged tech_baseline } }"),
    }
    result = classify_crisis_factions(technologies, flag_overrides=_flag_override("my_flag", "Compound"))
    assert result["tech_flagged"] == "Compound"
    assert result["tech_dependent"] is None
