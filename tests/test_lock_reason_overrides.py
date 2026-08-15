"""Tests for pipeline.lock_reason_overrides -- P-13's checked-in lock-reason override loader.
Mirrors tests/test_overwrite_overrides.py's structure for the parallel P-15 loader."""

from __future__ import annotations

import pytest

from pipeline.lock_reason_overrides import LockReasonOverrideConfigError, load_overrides


def _write(tmp_path, text):
    path = tmp_path / "lock_reason_overrides.txt"
    path.write_text(text, encoding="utf-8")
    return path


def test_missing_file_returns_empty_dict(tmp_path):
    assert load_overrides(tmp_path / "does_not_exist.txt") == {}


def test_blank_lines_and_comments_are_skipped(tmp_path):
    path = _write(tmp_path, "# header\n\n# more comment\n")
    assert load_overrides(path) == {}


def test_parses_a_valid_entry(tmp_path):
    path = _write(tmp_path, "tech_example = Unavailable: requires Example DLC  # confirmed by hand\n")
    overrides = load_overrides(path)
    assert set(overrides) == {"tech_example"}
    entry = overrides["tech_example"]
    assert entry.technology_key == "tech_example"
    assert entry.reason_text == "Unavailable: requires Example DLC"
    assert entry.justification == "confirmed by hand"
    assert entry.line == 1


def test_missing_equals_sign_is_a_config_error(tmp_path):
    path = _write(tmp_path, "tech_example  # no equals sign\n")
    with pytest.raises(LockReasonOverrideConfigError):
        load_overrides(path)


def test_missing_justification_is_a_config_error(tmp_path):
    path = _write(tmp_path, "tech_example = Unavailable: requires Example DLC\n")
    with pytest.raises(LockReasonOverrideConfigError):
        load_overrides(path)


def test_empty_reason_text_is_a_config_error(tmp_path):
    path = _write(tmp_path, "tech_example =   # justification only\n")
    with pytest.raises(LockReasonOverrideConfigError):
        load_overrides(path)


def test_duplicate_key_is_a_config_error(tmp_path):
    path = _write(
        tmp_path,
        "tech_example = Reason one  # first\ntech_example = Reason two  # second\n",
    )
    with pytest.raises(LockReasonOverrideConfigError):
        load_overrides(path)


def test_checked_in_file_loads_empty_and_parses_cleanly():
    # The real config/lock_reason_overrides.txt -- seeded empty (Task 3's survey found zero real
    # corpus cases needing one), but must still parse without error, same posture as
    # config/overwrite_overrides.txt.
    assert load_overrides() == {}
