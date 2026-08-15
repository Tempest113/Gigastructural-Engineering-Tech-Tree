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


def test_checked_in_file_loads_empty_and_parses_cleanly():
    assert load_overrides() == {}
