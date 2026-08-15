"""Tests for pipeline.geometry -- packing pipeline.layout.LayoutResult into typed-array
side-files plus GeometryRef pointers, per 00-overview.md's "geometry lives in typed-array
side-files, JSON references them, never inlines coordinate arrays"."""

from __future__ import annotations

import struct

import pytest

from pipeline.clausewitz import parse_text
from pipeline.geometry import FLOATS_PER_EDGE, pack_edge_polylines, pack_node_positions
from pipeline.layout import TechnologyLayoutInput, compute_layout
from pipeline.variables import build_variable_table


def _input(key, text, lane=None):
    doc = parse_text(f"tech_x = {text}\n", path="x.txt")
    return TechnologyLayoutInput(key=key, block=doc.items[0].value, lane=lane)


def _graph():
    return {
        "tech_a": _input("tech_a", "{ tier = 0 prerequisites = { } category = { physics } }"),
        "tech_b": _input("tech_b", "{ tier = 1 prerequisites = { tech_a } category = { physics } }"),
    }


def test_pack_node_positions_round_trips():
    layout = compute_layout(_graph(), build_variable_table([]))
    key_order = ["tech_a", "tech_b"]
    data, ref = pack_node_positions(layout, key_order)

    assert ref.length == 4  # 2 nodes x (x, y)
    assert ref.dtype == "float32"
    floats = struct.unpack(f"<{ref.length}f", data)
    assert floats[0] == pytest.approx(layout.nodes["tech_a"].x)
    assert floats[1] == pytest.approx(layout.nodes["tech_a"].y)
    assert floats[2] == pytest.approx(layout.nodes["tech_b"].x)
    assert floats[3] == pytest.approx(layout.nodes["tech_b"].y)


def test_pack_node_positions_rejects_mismatched_key_order():
    layout = compute_layout(_graph(), build_variable_table([]))
    with pytest.raises(ValueError):
        pack_node_positions(layout, ["tech_a"])  # missing tech_b


def test_pack_edge_polylines_round_trips_and_indexes_correctly():
    layout = compute_layout(_graph(), build_variable_table([]))
    data, ref, index = pack_edge_polylines(layout)

    assert len(index) == len(layout.edges) == 1
    entry = index[0]
    assert entry["fromKey"] == "tech_a"
    assert entry["toKey"] == "tech_b"
    assert entry["kind"] == "prerequisite"
    assert entry["groupId"] is None
    assert entry["backward"] is False
    assert entry["bandSpan"] <= 0
    assert entry["length"] == FLOATS_PER_EDGE == 8

    floats = struct.unpack(f"<{ref.length}f", data)
    edge_floats = floats[entry["offset"]:entry["offset"] + entry["length"]]
    expected = [coord for point in layout.edges[0].polyline for coord in point]
    for got, want in zip(edge_floats, expected):
        assert got == pytest.approx(want)


def test_pack_edge_polylines_empty_graph_produces_empty_bytes():
    layout = compute_layout({"tech_a": _input("tech_a", "{ tier = 0 prerequisites = { } category = { physics } }")}, build_variable_table([]))
    data, ref, index = pack_edge_polylines(layout)
    assert data == b""
    assert ref.length == 0
    assert index == []
