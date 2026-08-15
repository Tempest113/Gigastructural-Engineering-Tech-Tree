"""Tests for pipeline.layout -- P-2/D-13 tier-band layout computation."""

from __future__ import annotations

import pytest

from pipeline.clausewitz import parse_text
from pipeline.layout import (
    REPEATABLES,
    LayoutCycleError,
    TechnologyLayoutInput,
    UnresolvedTierError,
    category_of,
    compute_layout,
    is_repeatable,
    resolve_declared_tier,
)
from pipeline.variables import build_variable_table


def _block(text: str):
    doc = parse_text(f"tech_x = {text}\n", path="x.txt")
    return doc.items[0].value


def _vt(*var_docs):
    return build_variable_table(var_docs)


def _input(key, text, lane=None):
    return TechnologyLayoutInput(key=key, block=_block(text), lane=lane)


# ---------------------------------------------------------------------------
# resolve_declared_tier -- hard fail, never a silent default
# ---------------------------------------------------------------------------


def test_literal_tier_resolves():
    vt = _vt()
    assert resolve_declared_tier("tech_x", _block("{ tier = 5 }"), vt) == 5


def test_missing_tier_field_raises():
    vt = _vt()
    with pytest.raises(UnresolvedTierError):
        resolve_declared_tier("tech_x", _block("{ cost = 100 }"), vt)


def test_variable_tier_resolves():
    var_doc = parse_text("@giga_tier5 = 5\n", path="vars.txt")
    vt = _vt(var_doc)
    assert resolve_declared_tier("tech_x", _block("{ tier = @giga_tier5 }"), vt) == 5


def test_undefined_variable_tier_raises():
    vt = _vt()
    with pytest.raises(UnresolvedTierError):
        resolve_declared_tier("tech_x", _block("{ tier = @nonexistent }"), vt)


def test_non_numeric_tier_raises():
    vt = _vt()
    with pytest.raises(UnresolvedTierError):
        resolve_declared_tier("tech_x", _block("{ tier = some_identifier }"), vt)


# ---------------------------------------------------------------------------
# is_repeatable / category_of
# ---------------------------------------------------------------------------


def test_negative_levels_is_repeatable():
    assert is_repeatable(_block("{ levels = -1 }"), _vt()) is True


def test_positive_levels_is_also_repeatable():
    # Correction: `levels` is used both as an unbounded marker (-1) and as a positive finite cap
    # (5/20/40 in the real corpus) on an otherwise identical repeatable-tech shape -- field
    # presence, not sign, is the real signal. See pipeline.layout.is_repeatable's docstring.
    assert is_repeatable(_block("{ levels = 5 }"), _vt()) is True
    assert is_repeatable(_block("{ levels = 40 }"), _vt()) is True


def test_no_levels_field_is_not_repeatable():
    assert is_repeatable(_block("{ cost = 100 }"), _vt()) is False


def test_category_of_reads_first_entry():
    assert category_of(_block("{ category = { voidcraft } }")) == "voidcraft"


def test_category_of_none_when_absent():
    assert category_of(_block("{ cost = 100 }")) is None


# ---------------------------------------------------------------------------
# compute_layout
# ---------------------------------------------------------------------------


def _simple_graph():
    return {
        "tech_a": _input("tech_a", "{ tier = 0 prerequisites = { } category = { physics } }"),
        "tech_b": _input("tech_b", "{ tier = 1 prerequisites = { tech_a } category = { physics } }"),
        "tech_c": _input("tech_c", "{ tier = 2 prerequisites = { tech_b } category = { physics } }"),
    }


def test_bands_are_enumerated_from_declared_tier_not_hardcoded():
    result = compute_layout(_simple_graph(), _vt())
    tiers = [b.band_id for b in result.bands if b.band_id != REPEATABLES]
    assert tiers == [0, 1, 2]
    assert result.bands[-1].band_id == REPEATABLES


def test_node_band_is_its_own_declared_tier_never_promoted():
    # tech_c's prerequisite (tech_b) has declared tier 1, tech_c has declared tier 2 -- no
    # promotion conflict here, but this confirms the band is read directly off the field.
    result = compute_layout(_simple_graph(), _vt())
    assert result.nodes["tech_a"].band_id == 0
    assert result.nodes["tech_b"].band_id == 1
    assert result.nodes["tech_c"].band_id == 2


def test_a_technology_declared_at_or_below_its_prerequisites_tier_is_NOT_promoted():
    # D-13's core correction: tech_b's declared tier (1) is at or below tech_a's declared tier
    # equal case doesn't apply here; use a genuine same-or-lower case instead.
    graph = {
        "tech_a": _input("tech_a", "{ tier = 5 prerequisites = { } category = { physics } }"),
        "tech_b": _input("tech_b", "{ tier = 3 prerequisites = { tech_a } category = { physics } }"),
    }
    result = compute_layout(graph, _vt())
    # Under the superseded model tech_b would have been promoted to column 6; under D-13 it
    # stays in its own declared band, 3.
    assert result.nodes["tech_b"].band_id == 3
    assert result.nodes["tech_b"].band_index < result.nodes["tech_a"].band_index


def test_repeatable_technology_placed_in_repeatables_band():
    graph = {
        "tech_a": _input("tech_a", "{ tier = 3 prerequisites = { } category = { physics } }"),
        "tech_a_repeat": _input(
            "tech_a_repeat", "{ tier = 5 levels = -1 prerequisites = { tech_a } category = { physics } }"
        ),
    }
    result = compute_layout(graph, _vt())
    assert result.nodes["tech_a_repeat"].band_id == REPEATABLES
    assert result.nodes["tech_a_repeat"].band_index == result.bands[-1].index


def test_finite_level_repeatable_also_placed_in_repeatables_band():
    # The corrected membership rule (field presence, not sign): a positive levels value is a
    # finite repeat cap, still repeatable, still bands into REPEATABLES -- not a tier-banded node.
    graph = {
        "tech_a": _input("tech_a", "{ tier = 3 prerequisites = { } category = { physics } }"),
        "tech_a_finite_repeat": _input(
            "tech_a_finite_repeat", "{ tier = 5 levels = 5 prerequisites = { tech_a } category = { physics } }"
        ),
    }
    result = compute_layout(graph, _vt())
    assert result.nodes["tech_a_finite_repeat"].band_id == REPEATABLES
    assert result.nodes["tech_a_finite_repeat"].band_index == result.bands[-1].index


def test_layout_is_deterministic():
    graph = _simple_graph()
    a = compute_layout(graph, _vt())
    b = compute_layout(graph, _vt())
    for key in graph:
        assert a.nodes[key] == b.nodes[key]
    assert [(e.from_key, e.to_key, e.polyline) for e in a.edges] == [(e.from_key, e.to_key, e.polyline) for e in b.edges]


def test_cycle_raises_layout_cycle_error():
    graph = {
        "tech_a": _input("tech_a", "{ tier = 0 prerequisites = { tech_b } category = { physics } }"),
        "tech_b": _input("tech_b", "{ tier = 1 prerequisites = { tech_a } category = { physics } }"),
    }
    with pytest.raises(LayoutCycleError):
        compute_layout(graph, _vt())


def test_unresolved_tier_propagates_as_hard_failure():
    graph = {"tech_a": _input("tech_a", "{ prerequisites = { } category = { physics } }")}
    with pytest.raises(UnresolvedTierError):
        compute_layout(graph, _vt())


# ---------------------------------------------------------------------------
# Sub-grid arrangement within a band
# ---------------------------------------------------------------------------


def test_dense_band_wraps_into_n_wide_subgrid():
    graph = {
        f"tech_{i}": _input(f"tech_{i}", "{ tier = 5 prerequisites = { } category = { voidcraft } }")
        for i in range(10)
    }
    result = compute_layout(graph, _vt(), subgrid_width=4)
    rows = {result.nodes[k].row for k in graph}
    cols = {result.nodes[k].col for k in graph}
    assert rows == {0, 1, 2}  # ceil(10/4) = 3 rows
    assert cols == {0, 1, 2, 3}
    # every (row, col) pair is unique -- no overlap
    positions = [(result.nodes[k].row, result.nodes[k].col) for k in graph]
    assert len(positions) == len(set(positions))


def test_subgrid_groups_by_category_before_computed_position():
    graph = {
        "tech_bio_1": _input("tech_bio_1", "{ tier = 5 prerequisites = { } category = { biology } }"),
        "tech_void_1": _input("tech_void_1", "{ tier = 5 prerequisites = { } category = { voidcraft } }"),
        "tech_bio_2": _input("tech_bio_2", "{ tier = 5 prerequisites = { } category = { biology } }"),
    }
    result = compute_layout(graph, _vt(), subgrid_width=4)
    # sorted by (category, computed_position, key): biology < voidcraft alphabetically
    ordering = sorted(graph, key=lambda k: result.nodes[k].col + result.nodes[k].row * 4)
    assert ordering == ["tech_bio_1", "tech_bio_2", "tech_void_1"]


# ---------------------------------------------------------------------------
# Lanes -- all six always present, including a zero-population one
# ---------------------------------------------------------------------------


def test_all_six_lanes_reserved_even_when_some_are_empty():
    graph = {"tech_a": _input("tech_a", "{ tier = 0 prerequisites = { } category = { physics } }")}
    result = compute_layout(graph, _vt())
    assert result.lane_ids == ["Standard", "Aeternum", "Blokkats", "Compound", "Sirenalia", "Katzenartig Imperium"]


def test_crisis_lane_technology_placed_in_its_own_lane():
    graph = {
        "tech_standard": _input("tech_standard", "{ tier = 0 prerequisites = { } category = { physics } }"),
        "tech_blokkat": _input(
            "tech_blokkat", "{ tier = 0 prerequisites = { } category = { blokkats } }", lane="Blokkats"
        ),
    }
    result = compute_layout(graph, _vt())
    assert result.nodes["tech_standard"].lane_id == "Standard"
    assert result.nodes["tech_blokkat"].lane_id == "Blokkats"
    assert result.nodes["tech_standard"].y != result.nodes["tech_blokkat"].y


# ---------------------------------------------------------------------------
# Backwards edges
# ---------------------------------------------------------------------------


def test_backward_edge_flagged_when_prerequisite_band_is_later():
    graph = {
        "tech_high": _input("tech_high", "{ tier = 5 prerequisites = { } category = { physics } }"),
        "tech_low": _input("tech_low", "{ tier = 2 prerequisites = { tech_high } category = { physics } }"),
    }
    result = compute_layout(graph, _vt())
    edge = next(e for e in result.edges if e.from_key == "tech_high" and e.to_key == "tech_low")
    assert edge.backward is True


def test_forward_edge_not_flagged_backward():
    result = compute_layout(_simple_graph(), _vt())
    for edge in result.edges:
        assert edge.backward is False


def test_band_span_sign_matches_backward_flag():
    graph = {
        "tech_high": _input("tech_high", "{ tier = 5 prerequisites = { } category = { physics } }"),
        "tech_low": _input("tech_low", "{ tier = 2 prerequisites = { tech_high } category = { physics } }"),
    }
    result = compute_layout(graph, _vt())
    edge = next(e for e in result.edges if e.from_key == "tech_high" and e.to_key == "tech_low")
    assert edge.band_span > 0
    assert edge.backward == (edge.band_span > 0)

    forward = next(e for e in compute_layout(_simple_graph(), _vt()).edges if e.from_key == "tech_a")
    assert forward.band_span <= 0
    assert forward.backward is False


# ---------------------------------------------------------------------------
# P-14: full three-kind edge typing
# ---------------------------------------------------------------------------


def test_prerequisite_edges_are_kind_tagged():
    result = compute_layout(_simple_graph(), _vt())
    assert all(e.kind == "prerequisite" for e in result.edges)
    assert all(e.group_id is None for e in result.edges)


def test_alternative_edges_carry_group_id():
    graph = {
        "tech_a": _input("tech_a", "{ tier = 0 prerequisites = { } category = { physics } }"),
        "tech_b": _input("tech_b", "{ tier = 0 prerequisites = { } category = { physics } }"),
        "tech_c": _input(
            "tech_c",
            "{ tier = 1 prerequisites = { OR = { tech_a tech_b } } category = { physics } }",
        ),
    }
    result = compute_layout(graph, _vt())
    alt_edges = [e for e in result.edges if e.kind == "alternative"]
    assert len(alt_edges) == 2
    assert {e.from_key for e in alt_edges} == {"tech_a", "tech_b"}
    assert all(e.to_key == "tech_c" for e in alt_edges)
    group_ids = {e.group_id for e in alt_edges}
    assert len(group_ids) == 1 and None not in group_ids


def test_potential_gate_edges_are_kind_tagged():
    graph = {
        "tech_a": _input("tech_a", "{ tier = 0 prerequisites = { } category = { physics } }"),
        "tech_b": _input(
            "tech_b",
            "{ tier = 1 prerequisites = { } potential = { has_technology = tech_a } category = { physics } }",
        ),
    }
    result = compute_layout(graph, _vt())
    pg_edges = [e for e in result.edges if e.kind == "potential-gate"]
    assert len(pg_edges) == 1
    assert pg_edges[0].from_key == "tech_a"
    assert pg_edges[0].to_key == "tech_b"
    assert pg_edges[0].group_id is None


def test_a_pair_can_be_both_prerequisite_and_potential_gate():
    graph = {
        "tech_a": _input("tech_a", "{ tier = 0 prerequisites = { } category = { physics } }"),
        "tech_b": _input(
            "tech_b",
            "{ tier = 1 prerequisites = { tech_a } potential = { has_technology = tech_a } category = { physics } }",
        ),
    }
    result = compute_layout(graph, _vt())
    kinds = sorted(e.kind for e in result.edges if e.from_key == "tech_a" and e.to_key == "tech_b")
    assert kinds == ["potential-gate", "prerequisite"]


def test_backward_edge_polyline_still_four_points():
    graph = {
        "tech_high": _input("tech_high", "{ tier = 5 prerequisites = { } category = { physics } }"),
        "tech_low": _input("tech_low", "{ tier = 2 prerequisites = { tech_high } category = { physics } }"),
    }
    result = compute_layout(graph, _vt())
    edge = result.edges[0]
    assert len(edge.polyline) == 4
