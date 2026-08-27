"""Tests for pipeline.weight_gate_suppressions -- Item 1's checked-in suppression config loader
and AST matcher. Mirrors tests/test_lock_reason_overrides.py's structure for the config-loading
half; the matching/pruning half has no direct precedent, so it's covered more thoroughly here."""

from __future__ import annotations

import pytest

from pipeline.clausewitz import parse_text
from pipeline.clausewitz.nodes import Assignment, Block
from pipeline.weight_gate_suppressions import (
    WeightGateSuppressionConfigError,
    apply_suppressions,
    find_suppressed_leaves,
    load_suppressions,
)


def _write(tmp_path, text):
    path = tmp_path / "weight_gate_suppressions.txt"
    path.write_text(text, encoding="utf-8")
    return path


def _block(text: str) -> Block:
    """Builds a condition Block the same shape `_weight_gate_condition_blocks` returns --
    `factor` already stripped -- so these tests exercise `find_suppressed_leaves`/`apply_
    suppressions` on exactly the input they receive in production."""
    doc = parse_text(f"tech_x = {{ weight_modifier = {{ modifier = {{ factor = 0 {text} }} }} }}\n", path="x.txt")
    assignment = doc.items[0]
    wm = next(item for item in assignment.value.items if item.key_name == "weight_modifier")
    modifier = next(item for item in wm.value.items if item.key_name == "modifier")
    cond_items = [it for it in modifier.value.items if not (isinstance(it, Assignment) and it.key_name == "factor")]
    return Block(items=cond_items, line=modifier.value.line, column=modifier.value.column)


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------


def test_missing_file_returns_empty_list(tmp_path):
    assert load_suppressions(tmp_path / "does_not_exist.txt") == []


def test_blank_lines_and_comments_are_skipped(tmp_path):
    path = _write(tmp_path, "# header\n\n# more comment\n")
    assert load_suppressions(path) == []


def test_parses_bare_key_entry(tmp_path):
    path = _write(tmp_path, "any_owned_nonprimary_starbase -> true  # trivially satisfied\n")
    [rule] = load_suppressions(path)
    assert rule.leaf_key == "any_owned_nonprimary_starbase"
    assert rule.shape == "any"
    assert rule.resolves_to is True
    assert rule.justification == "trivially satisfied"


def test_parses_numeric_entry(tmp_path):
    path = _write(tmp_path, "num_owned_planets < 2 -> false  # reached fast\n")
    [rule] = load_suppressions(path)
    assert rule.shape == "numeric_at_most"
    assert rule.operator == "<"
    assert rule.threshold == 2.0
    assert rule.resolves_to is False


def test_parses_suffix_entry(tmp_path):
    path = _write(tmp_path, "has_country_flag ~ _found -> true  # resource found\n")
    [rule] = load_suppressions(path)
    assert rule.shape == "suffix"
    assert rule.suffix == "_found"


def test_missing_arrow_is_a_config_error(tmp_path):
    path = _write(tmp_path, "num_owned_planets < 2  # no arrow\n")
    with pytest.raises(WeightGateSuppressionConfigError):
        load_suppressions(path)


def test_missing_justification_is_a_config_error(tmp_path):
    path = _write(tmp_path, "num_owned_planets < 2 -> false\n")
    with pytest.raises(WeightGateSuppressionConfigError):
        load_suppressions(path)


def test_invalid_bool_is_a_config_error(tmp_path):
    path = _write(tmp_path, "num_owned_planets < 2 -> maybe  # bad\n")
    with pytest.raises(WeightGateSuppressionConfigError):
        load_suppressions(path)


def test_unrecognised_shape_is_a_config_error(tmp_path):
    path = _write(tmp_path, "num_owned_planets between 1 2 -> false  # bad shape\n")
    with pytest.raises(WeightGateSuppressionConfigError):
        load_suppressions(path)


def test_duplicate_leaf_key_is_a_config_error(tmp_path):
    path = _write(
        tmp_path,
        "num_owned_planets < 2 -> false  # first\nnum_owned_planets < 3 -> false  # second\n",
    )
    with pytest.raises(WeightGateSuppressionConfigError):
        load_suppressions(path)


def test_checked_in_file_parses_cleanly_and_has_six_entries():
    suppressions = load_suppressions()
    assert len(suppressions) == 6
    assert {s.leaf_key for s in suppressions} == {
        "years_passed", "num_owned_planets", "any_owned_nonprimary_starbase",
        "num_communications", "any_planet_within_border", "has_country_flag",
    }


# ---------------------------------------------------------------------------
# Matching against real AST shapes
# ---------------------------------------------------------------------------


def test_numeric_matches_stricter_threshold_too(tmp_path):
    # config declares an upper bound (< 2); a corpus occurrence of `< 1` is stricter and still
    # trivially satisfied, so it must still match (real corpus: tech_galactic_markets uses `< 2`,
    # five other technologies use `< 1`).
    path = _write(tmp_path, "num_communications < 2 -> false  # first contact guaranteed\n")
    [rule] = load_suppressions(path)
    block = _block("num_communications < 1")
    hits = find_suppressed_leaves(block, [rule])
    assert len(hits) == 1


def test_numeric_does_not_match_a_looser_threshold(tmp_path):
    path = _write(tmp_path, "num_owned_planets < 2 -> false  # trivial\n")
    [rule] = load_suppressions(path)
    block = _block("num_owned_planets < 5")
    assert find_suppressed_leaves(block, [rule]) == []


def test_suffix_matches_only_the_configured_suffix(tmp_path):
    path = _write(tmp_path, "has_country_flag ~ _found -> true  # resource found\n")
    [rule] = load_suppressions(path)
    matching = _block("has_country_flag = sr_living_metal_found")
    non_matching = _block("has_country_flag = has_market_access")
    unrelated_found = _block("has_country_flag = found_presapients")
    assert len(find_suppressed_leaves(matching, [rule])) == 1
    assert find_suppressed_leaves(non_matching, [rule]) == []
    assert find_suppressed_leaves(unrelated_found, [rule]) == []


def test_bare_key_matches_regardless_of_nested_scope_content(tmp_path):
    path = _write(tmp_path, "any_planet_within_border -> true  # deposit found\n")
    [rule] = load_suppressions(path)
    block = _block(
        "any_planet_within_border = { OR = { has_deposit = d_rare_crystals_1 has_deposit = d_rare_crystals_2 } }"
    )
    assert len(find_suppressed_leaves(block, [rule])) == 1


def test_walk_descends_through_not_and_nor_wrappers(tmp_path):
    path = _write(tmp_path, "has_country_flag ~ _found -> true  # resource found\n")
    [rule] = load_suppressions(path)
    block = _block(
        "is_nomadic = yes NOT = { has_country_flag = rare_crystals_found }"
    )
    assert len(find_suppressed_leaves(block, [rule])) == 1


def test_apply_suppressions_produces_id_keyed_target_map(tmp_path):
    path = _write(tmp_path, "num_owned_planets < 2 -> false  # trivial\n")
    suppressions = load_suppressions(path)
    block = _block("num_owned_planets < 2")
    [leaf] = [item for item in block.items]
    targets, hits = apply_suppressions([block], suppressions)
    assert targets == {id(leaf): False}
    assert len(hits) == 1
