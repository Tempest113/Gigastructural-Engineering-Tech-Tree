"""Tests for pipeline.overwrite_overrides — loader for config/overwrite_overrides.txt.
Mirrors tests/icons/test_overrides.py's structure for pipeline/icons/overrides.py."""

import pytest

from pipeline.overwrite_overrides import OverwriteOverrideConfigError, load_overrides


def _write(tmp_path, text):
    path = tmp_path / "overwrite_overrides.txt"
    path.write_text(text)
    return path


def test_missing_file_returns_empty_dict(tmp_path):
    assert load_overrides(tmp_path / "does_not_exist.txt") == {}


def test_blank_and_comment_lines_are_skipped(tmp_path):
    path = _write(tmp_path, "# header\n\n   \n# more\n")
    assert load_overrides(path) == {}


def test_valid_entry_parses(tmp_path):
    path = _write(tmp_path, "tech_a = ACOT  # ambiguous three-way chain, ACOT is the intended winner\n")
    overrides = load_overrides(path)
    assert overrides["tech_a"].winning_source == "ACOT"
    assert "ambiguous" in overrides["tech_a"].justification


def test_missing_equals_is_a_config_error(tmp_path):
    path = _write(tmp_path, "tech_a ACOT # no equals sign\n")
    with pytest.raises(OverwriteOverrideConfigError):
        load_overrides(path)


def test_missing_justification_is_a_config_error(tmp_path):
    path = _write(tmp_path, "tech_a = ACOT\n")
    with pytest.raises(OverwriteOverrideConfigError):
        load_overrides(path)


def test_invalid_source_name_is_a_config_error(tmp_path):
    path = _write(tmp_path, "tech_a = NotARealSource  # bogus\n")
    with pytest.raises(OverwriteOverrideConfigError):
        load_overrides(path)


def test_duplicate_key_is_a_config_error(tmp_path):
    path = _write(tmp_path, "tech_a = ACOT  # first\ntech_a = AoT  # second\n")
    with pytest.raises(OverwriteOverrideConfigError):
        load_overrides(path)


def test_checked_in_config_loads_empty():
    # config/overwrite_overrides.txt is checked in seeded empty (no case in the corpus survey
    # needed an override) -- confirm it actually loads as empty, not that it merely parses.
    from pipeline.overwrite_overrides import DEFAULT_PATH

    assert DEFAULT_PATH.is_file()
    assert load_overrides() == {}
