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


def test_checked_in_config_has_exactly_the_one_known_real_gap():
    """`config/name_overrides.txt` should carry exactly the one reviewed entry this session found
    (giga_tech_aeternite_weaponry) -- a change here is either a new real gap (fine, but should be
    reviewed the same way) or an accidental edit (should be reverted)."""
    overrides = load_name_overrides()
    assert set(overrides) == {"giga_tech_aeternite_weaponry"}
