"""Tests for pipeline.name_overrides — loader for config/name_overrides.txt.
Mirrors tests/test_overwrite_overrides.py's structure for pipeline/overwrite_overrides.py."""

import pytest

from pipeline.name_overrides import NameOverrideConfigError, load_name_overrides


def _write(tmp_path, text):
    path = tmp_path / "name_overrides.txt"
    path.write_text(text)
    return path


def test_missing_file_returns_empty_dict(tmp_path):
    assert load_name_overrides(tmp_path / "does_not_exist.txt") == {}


def test_blank_and_comment_lines_are_skipped(tmp_path):
    path = _write(tmp_path, "# header\n\n   \n# more\n")
    assert load_name_overrides(path) == {}


def test_valid_entry_parses(tmp_path):
    path = _write(tmp_path, "tech_a = Real Display Name  # the mod never localised this key\n")
    overrides = load_name_overrides(path)
    assert overrides["tech_a"].name == "Real Display Name"
    assert "never localised" in overrides["tech_a"].justification


def test_missing_equals_is_a_config_error(tmp_path):
    path = _write(tmp_path, "tech_a Real Name # no equals sign\n")
    with pytest.raises(NameOverrideConfigError):
        load_name_overrides(path)


def test_missing_justification_is_a_config_error(tmp_path):
    path = _write(tmp_path, "tech_a = Real Name\n")
    with pytest.raises(NameOverrideConfigError):
        load_name_overrides(path)


def test_duplicate_key_is_a_config_error(tmp_path):
    path = _write(tmp_path, "tech_a = Name One # justified\ntech_a = Name Two # justified again\n")
    with pytest.raises(NameOverrideConfigError):
        load_name_overrides(path)


def test_checked_in_config_is_seeded_empty_again():
    """`config/name_overrides.txt` carried exactly one reviewed entry (giga_tech_aeternite_
    weaponry) until Item 2c (later session) excluded that technology from the rendered tree
    entirely (`potential = { always = no }`, disabled content) -- the override can never fire for
    an unrendered technology, so it was removed rather than left dead. Seeded empty again; a
    change here is either a new real gap (fine, but should be reviewed the same way) or an
    accidental edit (should be reverted)."""
    overrides = load_name_overrides()
    assert set(overrides) == set()
