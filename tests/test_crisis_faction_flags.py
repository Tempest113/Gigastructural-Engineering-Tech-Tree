"""Tests for pipeline.crisis_faction_flags -- D-7/P-5's flag-to-faction map loader. Mirrors
tests/test_crisis_faction_overrides.py's format/coverage, keyed by flag name instead of
technology key."""

from __future__ import annotations

import pytest

from pipeline.crisis_faction_flags import CrisisFactionFlagOverrideConfigError, load_flag_overrides


def _write(tmp_path, text):
    path = tmp_path / "crisis_faction_flag_overrides.txt"
    path.write_text(text, encoding="utf-8")
    return path


def test_missing_file_returns_empty_dict(tmp_path):
    assert load_flag_overrides(tmp_path / "does_not_exist.txt") == {}


def test_parses_a_flag_entry(tmp_path):
    path = _write(tmp_path, "my_flag = Compound  # confirmed by hand\n")
    overrides = load_flag_overrides(path)
    assert overrides["my_flag"].faction == "Compound"
    assert overrides["my_flag"].justification == "confirmed by hand"


def test_invalid_faction_token_is_a_config_error(tmp_path):
    path = _write(tmp_path, "my_flag = Blorkats  # typo\n")
    with pytest.raises(CrisisFactionFlagOverrideConfigError):
        load_flag_overrides(path)


def test_missing_justification_is_a_config_error(tmp_path):
    path = _write(tmp_path, "my_flag = Compound\n")
    with pytest.raises(CrisisFactionFlagOverrideConfigError):
        load_flag_overrides(path)


def test_duplicate_key_is_a_config_error(tmp_path):
    path = _write(tmp_path, "my_flag = Compound  # first\nmy_flag = Blokkats  # second\n")
    with pytest.raises(CrisisFactionFlagOverrideConfigError):
        load_flag_overrides(path)


def test_checked_in_file_parses_cleanly_and_has_the_seven_real_entries():
    # config/crisis_faction_flag_overrides.txt gained its first real entry in the Part-0
    # reconciliation session (HANDOFF.md), then six more in the EAWAF/Sirenalia correction
    # session -- see that file's header comment and pipeline/crisis_faction.py's module
    # docstring for the full reasoning.
    overrides = load_flag_overrides()
    assert set(overrides) == {
        "qnm_utilities_possible",
        "giga_faust_weaponry_possible",
        "giga_tech_eawaf_disenchanter_1_possible",
        "giga_tech_eawaf_disenchanter_2_possible",
        "giga_tech_eawaf_disenchanter_3_possible",
        "giga_tech_eawaf_disenchanter_4_possible",
        "giga_tech_eawaf_weapons_repeatable_possible",
    }
    assert overrides["qnm_utilities_possible"].faction == "Compound"
    assert overrides["giga_faust_weaponry_possible"].faction == "Sirenalia"
    assert overrides["giga_tech_eawaf_disenchanter_1_possible"].faction == "Sirenalia"
    assert overrides["giga_tech_eawaf_disenchanter_2_possible"].faction == "Sirenalia"
    assert overrides["giga_tech_eawaf_disenchanter_3_possible"].faction == "Sirenalia"
    assert overrides["giga_tech_eawaf_disenchanter_4_possible"].faction == "Sirenalia"
    assert overrides["giga_tech_eawaf_weapons_repeatable_possible"].faction == "Sirenalia"
