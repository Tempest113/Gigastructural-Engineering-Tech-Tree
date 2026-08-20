"""Tests for pipeline.crisis_faction_overrides -- D-7's checked-in override loader. Mirrors
tests/test_overwrite_overrides.py and tests/test_lock_reason_overrides.py."""

from __future__ import annotations

import pytest

from pipeline.crisis_faction_overrides import CrisisFactionOverrideConfigError, load_overrides


def _write(tmp_path, text):
    path = tmp_path / "crisis_faction_overrides.txt"
    path.write_text(text, encoding="utf-8")
    return path


def test_missing_file_returns_empty_dict(tmp_path):
    assert load_overrides(tmp_path / "does_not_exist.txt") == {}


def test_parses_a_faction_entry(tmp_path):
    path = _write(tmp_path, "tech_example = Compound  # confirmed by hand\n")
    overrides = load_overrides(path)
    assert overrides["tech_example"].faction == "Compound"
    assert overrides["tech_example"].justification == "confirmed by hand"


def test_parses_a_none_entry(tmp_path):
    path = _write(tmp_path, "tech_example = None  # overriding a wrong ID match\n")
    overrides = load_overrides(path)
    assert overrides["tech_example"].faction is None


def test_invalid_faction_token_is_a_config_error(tmp_path):
    path = _write(tmp_path, "tech_example = Blorkats  # typo\n")
    with pytest.raises(CrisisFactionOverrideConfigError):
        load_overrides(path)


def test_missing_justification_is_a_config_error(tmp_path):
    path = _write(tmp_path, "tech_example = Compound\n")
    with pytest.raises(CrisisFactionOverrideConfigError):
        load_overrides(path)


def test_duplicate_key_is_a_config_error(tmp_path):
    path = _write(tmp_path, "tech_example = Compound  # first\ntech_example = Blokkats  # second\n")
    with pytest.raises(CrisisFactionOverrideConfigError):
        load_overrides(path)


def test_checked_in_file_parses_cleanly_and_has_the_fifteen_real_entries():
    # config/crisis_faction_overrides.txt started with 2 real entries (the has_country_flag
    # bypass case), gained 12 more in the Part-0 reconciliation session (HANDOFF.md) --
    # tech_qnm_utilities' 12 direct prerequisite dependents, each individually reachability-
    # justified -- then 1 more in the EAWAF/Sirenalia correction session (giga_tech_eawaf_psifusion,
    # the one EAWAF technology with no `potential` block to classify it via the flag map). See that
    # file's header comment and pipeline/crisis_faction.py's module docstring for the full
    # reasoning. The 14 Compound entries are unchanged; the 15th is Sirenalia.
    overrides = load_overrides()
    compound_expected = {
        "tech_sm_autocannons", "tech_qnm_disruptors",
        "tech_sm_flak_batteries", "tech_sm_mass_drivers", "tech_sm_kinetic_artillery",
        "tech_sm_mass_accelerator", "tech_sm_titanic", "tech_qnm_pd_tracking",
        "tech_qnm_lasers", "tech_qnm_plasma", "tech_qnm_energy_torpedoes",
        "tech_qnm_energy_lance", "tech_qnm_arc_emitter", "tech_qnm_titanic",
    }
    sirenalia_expected = {"giga_tech_eawaf_psifusion"}
    expected = compound_expected | sirenalia_expected
    assert set(overrides) == expected
    assert len(expected) == 15
    for key in compound_expected:
        assert overrides[key].faction == "Compound"
    for key in sirenalia_expected:
        assert overrides[key].faction == "Sirenalia"
