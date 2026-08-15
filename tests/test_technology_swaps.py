"""Tests for pipeline.technology_swaps -- D-14's axis-expressibility classification."""

from __future__ import annotations

from pipeline.clausewitz import parse_text
from pipeline.technology_swaps import collect_swaps


def _block(text: str):
    doc = parse_text(f"tech_x = {text}\n", path="x.txt")
    return doc.items[0].value


def test_no_swaps_returns_empty_list():
    block = _block("{ area = physics }")
    assert collect_swaps("tech_x", block) == []


def test_single_axis_expressible_swap():
    block = _block(
        "{ technology_swap = { name = tech_x_bio inherit_icon = no "
        "trigger = { country_uses_bio_ships = yes } } }"
    )
    swaps = collect_swaps("tech_x", block)
    assert len(swaps) == 1
    assert swaps[0].swap_key == "tech_x_bio"
    assert swaps[0].trigger_leaf_names == ("country_uses_bio_ships",)
    assert swaps[0].axis_expressible is True


def test_non_axis_swap_via_origin_leaf():
    block = _block(
        "{ technology_swap = { name = tech_x_wild trigger = { is_wilderness_empire = yes } } }"
    )
    swaps = collect_swaps("tech_x", block)
    assert swaps[0].axis_expressible is False


def test_compound_trigger_mixing_axis_and_non_axis_is_wholly_non_axis():
    """D-14's tech_ring_world case: an AND of one axis leaf and one non-axis leaf must not be
    treated as 'half expressible' -- substituting on the axis leg alone would assert a fact
    about the player's empire (giga_can_use_habitables) the model cannot verify."""
    block = _block(
        "{ technology_swap = { name = tech_x_variant trigger = { "
        "country_uses_bio_ships = yes giga_can_use_habitables = no } } }"
    )
    swaps = collect_swaps("tech_x", block)
    assert set(swaps[0].trigger_leaf_names) == {"country_uses_bio_ships", "giga_can_use_habitables"}
    assert swaps[0].axis_expressible is False


def test_axis_leaf_nested_inside_boolean_wrapper_still_collected():
    block = _block(
        "{ technology_swap = { name = tech_x_variant trigger = { "
        "OR = { is_nomadic = yes is_gestalt = yes } } } }"
    )
    swaps = collect_swaps("tech_x", block)
    assert set(swaps[0].trigger_leaf_names) == {"is_nomadic", "is_gestalt"}
    assert swaps[0].axis_expressible is True


def test_swap_with_no_trigger_block_is_not_axis_expressible():
    block = _block("{ technology_swap = { name = tech_x_variant inherit_icon = no } }")
    swaps = collect_swaps("tech_x", block)
    assert swaps[0].trigger_block is None
    assert swaps[0].trigger_leaf_names == ()
    assert swaps[0].axis_expressible is False


def test_multiple_swaps_preserve_declaration_order():
    block = _block(
        "{ technology_swap = { name = tech_x_a trigger = { is_nomadic = yes } } "
        "technology_swap = { name = tech_x_b trigger = { is_gestalt = yes } } }"
    )
    swaps = collect_swaps("tech_x", block)
    assert [s.swap_key for s in swaps] == ["tech_x_a", "tech_x_b"]


def test_swap_without_name_field_is_skipped():
    block = _block("{ technology_swap = { inherit_icon = no trigger = { is_nomadic = yes } } }")
    assert collect_swaps("tech_x", block) == []


def test_is_robot_empire_is_axis_expressible():
    """pipeline.availability.AXIS_FACTS already treats is_robot_empire as machine-intelligence
    authority (an established, already-audited approximation -- see that module's own comment).
    technology_swaps reuses AXIS_FACTS as its single source of truth, so this leaf must classify
    the same way here as it would inside a `potential` block."""
    block = _block(
        "{ technology_swap = { name = tech_x_robot trigger = { is_robot_empire = yes } } }"
    )
    swaps = collect_swaps("tech_x", block)
    assert swaps[0].axis_expressible is True
