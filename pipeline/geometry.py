"""00-overview.md: layout geometry lives in typed-array side-files; the JSON dataset carries only
`GeometryRef` pointers into them (`schema/common.schema.json`'s `GeometryRef`) — coordinate
arrays are never inlined in the JSON dataset. This module packs `pipeline.layout.LayoutResult`
into that shape: a single `float32` side-file per artefact, plus the `GeometryRef` dicts that
point into it.

Node positions and edge polylines are packed into **separate** side-files (matching
`base-dataset.schema.json`'s `geometry.nodePositions` / `geometry.edgePolylines`, two distinct
`GeometryRef`s) — a renderer that only needs node positions for the initial paint shouldn't have
to fetch edge geometry to get them, and vice versa.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from .layout import CARD_HEIGHT, EdgeLayout, LayoutResult, NodeLayout

# Every edge's polyline is exactly 6 (x, y) waypoints (pipeline.layout._route_edges: a
# card-avoidance route through the source row's own header/gutter strip -- exit stub, vertical
# run, horizontal transit, vertical run, entry stub -- 5 segments; moved from 4 points/3 segments
# in the session that closed the plain H-V-H router's card-crossing bug, see that function's own
# docstring) -- fixed-size records, so edge geometry packs as a flat float32 array with a uniform
# per-edge stride, no variable-length bookkeeping needed.
POINTS_PER_POLYLINE = 6
FLOATS_PER_NODE = 2  # x, y
FLOATS_PER_EDGE = POINTS_PER_POLYLINE * 2  # 6 points x (x, y)


@dataclass(frozen=True)
class GeometryRef:
    file: str
    byte_offset: int
    length: int  # element count, not byte count -- matches schema's GeometryRef.length
    dtype: str = "float32"

    def to_json(self) -> dict:
        return {"file": self.file, "byteOffset": self.byte_offset, "length": self.length, "dtype": self.dtype}


def pack_node_positions(layout: LayoutResult, key_order: list[str]) -> tuple[bytes, GeometryRef]:
    """Packs (x, y) for every key in `key_order` (the same order the JSON `technologies` array
    uses, so a node's index there is also its index into this typed array -- no separate id-to-
    offset lookup needed at runtime). `key_order` MUST cover exactly `layout.nodes`."""
    if set(key_order) != set(layout.nodes):
        missing = set(layout.nodes) - set(key_order)
        extra = set(key_order) - set(layout.nodes)
        raise ValueError(f"key_order must match layout.nodes exactly (missing={missing}, extra={extra})")

    floats: list[float] = []
    for key in key_order:
        node = layout.nodes[key]
        floats.append(node.x)
        floats.append(node.y)

    data = struct.pack(f"<{len(floats)}f", *floats)
    ref = GeometryRef(file="node-positions.f32", byte_offset=0, length=len(floats))
    return data, ref


def pack_edge_polylines(layout: LayoutResult) -> tuple[bytes, GeometryRef, list[dict]]:
    """Packs every edge's 4-point polyline back to back, in `layout.edges` order. Returns the
    packed bytes, the single `GeometryRef` covering the whole file, and a per-edge index list
    (`{"fromKey", "toKey", "kind", "groupId", "backward", "bandSpan", "offset", "length"}`) a
    caller merges into the JSON `edges` array -- `offset`/`length` are in float32 ELEMENTS
    (matching `GeometryRef.length`'s own units), so one edge's slice is
    `floats[offset:offset+length]`."""
    floats: list[float] = []
    index: list[dict] = []
    for edge in layout.edges:
        offset = len(floats)
        for x, y in edge.polyline:
            floats.append(x)
            floats.append(y)
        index.append({
            "fromKey": edge.from_key,
            "toKey": edge.to_key,
            "kind": edge.kind,
            "groupId": edge.group_id,
            "backward": edge.backward,
            "bandSpan": edge.band_span,
            "offset": offset,
            "length": FLOATS_PER_EDGE,
        })

    data = struct.pack(f"<{len(floats)}f", *floats) if floats else b""
    ref = GeometryRef(file="edge-polylines.f32", byte_offset=0, length=len(floats))
    return data, ref, index
