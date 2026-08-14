from pathlib import Path

import pytest

from pipeline.icons.overrides import IconOverrideConfigError, load_overrides


def _write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "icon_overrides.txt"
    p.write_text(text, encoding="utf-8")
    return p


def test_checked_in_override_file_loads_with_no_entries():
    overrides = load_overrides()
    assert overrides == {}


def test_valid_entry_parses(tmp_path):
    path = _write(tmp_path, "some_key = some_icon  # a real justification\n")
    overrides = load_overrides(path)
    assert overrides["some_key"].icon_name == "some_icon"
    assert overrides["some_key"].justification == "a real justification"


def test_missing_justification_is_a_config_error(tmp_path):
    path = _write(tmp_path, "some_key = some_icon\n")
    with pytest.raises(IconOverrideConfigError):
        load_overrides(path)


def test_missing_equals_is_a_config_error(tmp_path):
    path = _write(tmp_path, "some_key some_icon # justification\n")
    with pytest.raises(IconOverrideConfigError):
        load_overrides(path)


def test_duplicate_key_is_a_config_error(tmp_path):
    path = _write(tmp_path, "k = a  # first\nk = b  # second\n")
    with pytest.raises(IconOverrideConfigError):
        load_overrides(path)


def test_comment_and_blank_lines_are_skipped(tmp_path):
    path = _write(tmp_path, "# header comment\n\nk = a  # justification\n")
    overrides = load_overrides(path)
    assert list(overrides.keys()) == ["k"]
