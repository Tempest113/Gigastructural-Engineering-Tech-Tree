"""P-2/D-13: tier-band layout computation.

Bands are a node's own **declared** `tier` field — never adjusted by graph depth (D-13,
`spec/decisions.md`, correcting an earlier promoted-position draft). Computed longest-path
position exists only as internal geometry: it orders nodes horizontally within a band's
category-grouped sub-grid, and (indirectly, via each node's own declared band) is what makes a
"backwards edge" — a prerequisite whose own band is later than its dependent's — identifiable.
Computed position is never emitted as a displayed value; see S-3's "Band header and card tier
badge always agree" note for why that distinction matters.

Two correctness gaps closed here, both found by the P-2 tier-source audit (CLAUDE.md's "Tiers"
section) and both exactly the "wrong tier placement" failure class v1 reported:

1. `resolve_declared_tier` is a **hard build failure** (`UnresolvedTierError`) for any rendered
   node whose `tier` cannot be resolved to a definite integer after `inline_script` expansion —
   never a silent default. 0 of the 980 real rendered nodes currently hit this, but the policy
   exists so a future one fails loudly instead of landing in a wrong or absent band.
2. `pipeline.overwrites.resolve_variable_overwrites` now checks `tier` (not just `cost`/`weight`)
   for cross-source `@variable` overwrites — see that module for the fix; this module just
   depends on it being correct, since 83/980 rendered nodes declare `tier` as a `@variable`.

**D-13's one deliberate exception**: a repeatable technology (`is_repeatable` — a `levels` field
present at all, see that function's docstring for a correction to what counts) always bands into
the terminal `REPEATABLES` band regardless of its own declared tier, and its card badges repeat
count instead of the tier badge. Declared tier is still resolved and still emitted for these nodes
(`resolve_declared_tier` applies to them unchanged, no exemption) — it stays meaningful for
internal ordering and the detail popup, it just isn't what the band or the card *displays*. This
is not a repeat of v1's bug: v1's band header made a FALSE claim about a card's own tier ("TIER 6"
over T5-badged cards); here the band header asserts repeatable-ness and the card asserts repeat
count, and both are true at once. See `spec/decisions.md`'s D-13 for the full reasoning.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from .clausewitz.nodes import Assignment, Block, Identifier, NumberLiteral, StringLiteral, VariableReference
from .edges import EdgeExtractionDiagnostics, TypedEdge, compute_typed_edges
from .overwrites import TechnologyDefinition, ordered_prerequisites
from .variables import UndefinedVariableError, VariableCycleError, VariableTable

REPEATABLES = "repeatables"  # sentinel band id, always the terminal band in every lane

# D-7's canonical lane order: standard progression first, then the five crisis factions in
# spec/decisions.md's D-7 spelling/order -- fixed so layout is deterministic and Compound (whose
# rendered population is currently zero, confirmed real -- see pipeline/crisis_faction.py) still
# gets a lane slot rather than being silently omitted.
LANE_ORDER = ("Standard", "Aeternum", "Blokkats", "Compound", "Sirenalia", "Katzenartig Imperium")

# Card dimensions (spec/P-02-layout.md's "Card dimensions" implied technical decision): sized to
# fit the p95 rendered-name length (39 chars) across up to two lines, AND the worst-case gate
# string (35 chars, "Needs " dropped in favour of the gate icon carrying that semantic) on one
# line, untruncated. Gate text is never truncated; names truncate at p95 with the full name
# available in the popup and hover title -- both are Stage 3 rendering decisions, not enforced
# here, but the dimensions below are sized for them.
CARD_WIDTH = 270
CARD_HEIGHT = 92

INTRA_GAP_X = 8  # between sibling cards within one band's sub-grid row
INTRA_GAP_Y = 10  # between sub-grid rows within one lane
INTER_BAND_GUTTER = 40  # between adjacent tier bands, reserved for P-8 routing channels
LANE_LABEL_MARGIN = 40  # per-lane header strip, present even for an empty lane (e.g. Compound)

DEFAULT_SUBGRID_WIDTH = 4  # N -- see module docstring / CLAUDE.md for why 4 over 3


class LayoutError(Exception):
    """Base class for layout-computation failures."""


class UnresolvedTierError(LayoutError):
    """A rendered technology's declared `tier` could not be resolved to a definite integer --
    absent even after `inline_script` expansion, or a `@variable` reference that doesn't
    resolve. Hard failure per P-2: never a silent default tier."""

    def __init__(self, technology_key: str, reason: str):
        self.technology_key = technology_key
        self.reason = reason
        super().__init__(f"{technology_key}: declared tier unresolved -- {reason}")


class LayoutCycleError(LayoutError):
    """The rendered prerequisite graph is not acyclic -- column assignment (even the internal,
    undisplayed kind) is ill-defined. P-2: a detected cycle fails the build loudly."""

    def __init__(self, remaining: set[str]):
        self.remaining = remaining
        super().__init__(
            f"prerequisite graph contains a cycle involving {len(remaining)} technolog"
            f"{'y' if len(remaining) == 1 else 'ies'}: {sorted(remaining)[:10]}"
        )


def _field(block: Block, name: str) -> Assignment | None:
    result = None
    for item in block.items:
        if isinstance(item, Assignment) and item.key_name == name:
            result = item
    return result


def resolve_declared_tier(technology_key: str, block: Block, variable_table: VariableTable) -> int:
    """The node's own declared tier -- its band, full stop (D-13). Raises `UnresolvedTierError`
    rather than defaulting. `block` MUST already be `inline_script`-expanded (P-2's tier-source
    audit: 50/980 real rendered nodes only carry a `tier` field after expansion)."""
    assignment = _field(block, "tier")
    if assignment is None:
        raise UnresolvedTierError(technology_key, "no 'tier' field present, even after inline_script expansion")

    value = assignment.value
    if isinstance(value, NumberLiteral):
        if isinstance(value.value, int) or value.value == int(value.value):
            return int(value.value)
        raise UnresolvedTierError(technology_key, f"tier value {value.raw!r} is not an integer")

    if isinstance(value, VariableReference):
        try:
            resolved = variable_table.resolve(value.name)
        except (UndefinedVariableError, VariableCycleError) as exc:
            raise UnresolvedTierError(technology_key, f"@{value.name} does not resolve: {exc}") from exc
        if isinstance(resolved, NumberLiteral) and (
            isinstance(resolved.value, int) or resolved.value == int(resolved.value)
        ):
            return int(resolved.value)
        raise UnresolvedTierError(technology_key, f"@{value.name} resolves to a non-integer value")

    raise UnresolvedTierError(technology_key, f"tier value is a {type(value).__name__}, not a number or @variable")


def is_repeatable(block: Block, variable_table: VariableTable) -> bool:
    """A `levels` field present at all is the real corpus signal for repeatable status --
    `repeatable = yes` does not occur anywhere in the vendored corpus. See CLAUDE.md's layout
    survey.

    **Correction (found against a user's v1 screenshot, not by any test)**: this predicate
    previously required `levels < 0`, on the assumption that repeatable technologies are always
    unbounded. That's wrong -- the corpus also uses `levels` as a positive **finite** cap on an
    otherwise identical repeatable-tech shape (same `cost_per_level` field, same
    `*_repeatable*.txt` source files as the `-1` cases). 12 real repeatable technologies (5 with
    `levels = 5`, 3 with `levels = 20`, 4 with `levels = 40`) were misclassified as ordinary
    tier-banded nodes under the old rule -- including `tech_repeatable_reduced_building_cost`
    ("Gravitational Analysis"), the exact node visible badged "T5 x5" in the screenshot that
    surfaced this. Field *presence*, not sign, is the signal: `variable_table` is accepted for
    call-site stability but this check never needs to resolve the value to decide repeatable
    status (unlike `resolve_declared_tier`, which does need the resolved value)."""
    return _field(block, "levels") is not None


def category_of(block: Block) -> str | None:
    assignment = _field(block, "category")
    if assignment is None or not isinstance(assignment.value, Block):
        return None
    for item in assignment.value.items:
        if isinstance(item, Identifier):
            return item.name
        if isinstance(item, StringLiteral):
            return item.value
    return None


@dataclass(frozen=True)
class TechnologyLayoutInput:
    key: str
    block: Block
    lane: str | None  # crisis faction name, or None for the standard lane


@dataclass(frozen=True)
class BandDescriptor:
    band_id: int | str  # declared tier (int), or REPEATABLES
    index: int  # ordinal position, ascending, REPEATABLES always last
    label: str


@dataclass(frozen=True)
class NodeLayout:
    technology_key: str
    lane_id: str
    band_id: int | str
    band_index: int
    row: int
    col: int
    x: float
    y: float


@dataclass(frozen=True)
class EdgeLayout:
    from_key: str
    to_key: str
    kind: str  # "prerequisite" | "potential-gate" | "alternative" -- P-14
    group_id: str | None  # only set for kind == "alternative" -- see pipeline.edges
    backward: bool
    band_span: int  # from_band_index - to_band_index; positive iff backward
    polyline: list[tuple[float, float]]


@dataclass(frozen=True)
class LayoutResult:
    nodes: dict[str, NodeLayout]
    edges: list[EdgeLayout]
    bands: list[BandDescriptor]
    lane_ids: list[str]
    subgrid_width: int
    canvas_width: float
    canvas_height: float
    edge_diagnostics: EdgeExtractionDiagnostics


def _topological_order(rendered_keys: set[str], prereqs_of: dict[str, list[str]]) -> list[str]:
    """Kahn's algorithm. Raises LayoutCycleError if the graph isn't a DAG -- P-2: a detected
    cycle fails the build loudly, checked rather than assumed."""
    indegree = {k: 0 for k in rendered_keys}
    dependents: dict[str, list[str]] = {k: [] for k in rendered_keys}
    for key in rendered_keys:
        for p in prereqs_of[key]:
            dependents[p].append(key)
            indegree[key] += 1

    queue = sorted(k for k, d in indegree.items() if d == 0)
    order: list[str] = []
    remaining_indegree = dict(indegree)
    i = 0
    while i < len(queue):
        node = queue[i]
        i += 1
        order.append(node)
        for dependent in sorted(dependents[node]):
            remaining_indegree[dependent] -= 1
            if remaining_indegree[dependent] == 0:
                queue.append(dependent)

    if len(order) != len(rendered_keys):
        raise LayoutCycleError(rendered_keys - set(order))
    return order


def _computed_position(rendered_keys: set[str], prereqs_of: dict[str, list[str]]) -> dict[str, int]:
    """Longest-path depth over the rendered prerequisite graph -- internal ordering signal only
    (D-13), never displayed. Computed over topological order so every prerequisite's position is
    final before a dependent's is computed."""
    order = _topological_order(rendered_keys, prereqs_of)
    position: dict[str, int] = {}
    for key in order:
        prereq_positions = [position[p] for p in prereqs_of[key] if p in position]
        position[key] = (max(prereq_positions) + 1) if prereq_positions else 0
    return position


def compute_layout(
    technologies: dict[str, TechnologyLayoutInput],
    variable_table: VariableTable,
    subgrid_width: int = DEFAULT_SUBGRID_WIDTH,
) -> LayoutResult:
    """Full P-2/D-13 layout over `technologies` (rendered set only -- P-16). Deterministic: the
    same input always produces the same node positions (P-2's acceptance criterion) -- every
    ordering step below breaks ties on `technology_key`, never dict/set iteration order."""
    rendered_keys = set(technologies.keys())

    tiers: dict[str, int] = {}
    repeatable: dict[str, bool] = {}
    categories: dict[str, str | None] = {}
    prereqs_of: dict[str, list[str]] = {}

    for key, tech in technologies.items():
        tiers[key] = resolve_declared_tier(key, tech.block, variable_table)
        repeatable[key] = is_repeatable(tech.block, variable_table)
        categories[key] = category_of(tech.block)
        prereqs_of[key] = [p for p in ordered_prerequisites(tech.block) if p in rendered_keys]

    computed_position = _computed_position(rendered_keys, prereqs_of)

    # Bands: every distinct declared tier actually present among non-repeatable nodes (P-2: "MUST
    # be enumerated from the dataset at build time", never a hardcoded range), ascending, plus the
    # terminal Repeatables band.
    distinct_tiers = sorted({tiers[k] for k in rendered_keys if not repeatable[k]})
    bands = [BandDescriptor(t, i, f"Tier {t}") for i, t in enumerate(distinct_tiers)]
    band_index_of_tier = {b.band_id: b.index for b in bands}
    repeatables_index = len(bands)
    bands.append(BandDescriptor(REPEATABLES, repeatables_index, "Repeatables"))

    def band_of(key: str) -> tuple[int | str, int]:
        if repeatable[key]:
            return REPEATABLES, repeatables_index
        t = tiers[key]
        return t, band_index_of_tier[t]

    # Lane ids: fixed D-7 order, present even at zero population (Compound).
    lane_id_of = {key: (tech.lane or "Standard") for key, tech in technologies.items()}

    # Group by (lane, band), order within the group by (category, computed position, key) --
    # category first so a dense band's sub-grid reads as labelled neighbourhoods (CLAUDE.md's
    # layout survey), computed position second so within-category chains still read left-to-right
    # where the sub-grid is wide enough to show it, key last purely to break remaining ties
    # deterministically.
    groups: dict[tuple[str, int | str], list[str]] = {}
    for key in rendered_keys:
        band_id, _ = band_of(key)
        groups.setdefault((lane_id_of[key], band_id), []).append(key)

    for members in groups.values():
        members.sort(key=lambda k: (categories[k] or "", computed_position[k], k))

    nodes: dict[str, NodeLayout] = {}
    lane_row_counts: dict[str, int] = {lane: 0 for lane in LANE_ORDER}

    for (lane_id, band_id), members in groups.items():
        band_index = band_index_of_tier[band_id] if band_id != REPEATABLES else repeatables_index
        rows_used = -(-len(members) // subgrid_width)  # ceil division
        lane_row_counts[lane_id] = max(lane_row_counts[lane_id], rows_used)
        for i, key in enumerate(members):
            row, col = divmod(i, subgrid_width)
            x = band_index * (subgrid_width * CARD_WIDTH + (subgrid_width - 1) * INTRA_GAP_X + INTER_BAND_GUTTER) \
                + col * (CARD_WIDTH + INTRA_GAP_X)
            nodes[key] = NodeLayout(
                technology_key=key, lane_id=lane_id, band_id=band_id, band_index=band_index,
                row=row, col=col, x=float(x), y=0.0,  # y finalised below, once lane heights are known
            )

    # Lane vertical offsets, in D-7's fixed lane order (so Compound always reserves its strip).
    lane_y_offset: dict[str, float] = {}
    y_cursor = 0.0
    for lane in LANE_ORDER:
        lane_y_offset[lane] = y_cursor
        rows = lane_row_counts.get(lane, 0)
        lane_height = LANE_LABEL_MARGIN + (rows * CARD_HEIGHT + max(0, rows - 1) * INTRA_GAP_Y if rows else 0)
        y_cursor += lane_height
    canvas_height = y_cursor

    nodes = {
        key: NodeLayout(
            technology_key=n.technology_key, lane_id=n.lane_id, band_id=n.band_id, band_index=n.band_index,
            row=n.row, col=n.col, x=n.x,
            y=lane_y_offset[n.lane_id] + LANE_LABEL_MARGIN + n.row * (CARD_HEIGHT + INTRA_GAP_Y),
        )
        for key, n in nodes.items()
    }

    canvas_width = len(bands) * (subgrid_width * CARD_WIDTH + (subgrid_width - 1) * INTRA_GAP_X) \
        + max(0, len(bands) - 1) * INTER_BAND_GUTTER

    # P-14: full three-kind edge set (prerequisite/alternative/potential-gate), NOT just
    # prereqs_of -- prereqs_of above is deliberately narrower (true prerequisites only) and feeds
    # ONLY the internal DAG position/backward-band computation, never the emitted edge list.
    typed_edges, edge_diagnostics = compute_typed_edges({key: tech.block for key, tech in technologies.items()})
    edges = _route_edges(typed_edges, nodes, band_of)

    return LayoutResult(
        nodes=nodes, edges=edges, bands=bands, lane_ids=list(LANE_ORDER),
        subgrid_width=subgrid_width, canvas_width=float(canvas_width), canvas_height=float(canvas_height),
        edge_diagnostics=edge_diagnostics,
    )


def _channel_offset(from_key: str, to_key: str, kind: str, spacing: float = 6.0, span: int = 5) -> float:
    """Deterministic per-edge offset within a shared gutter channel, so several traces through
    the same gutter don't draw exactly on top of one another (P-8: "consistent channel spacing").
    `kind` is part of the hash so the 4 real (from, to) pairs that are BOTH a `prerequisite` and a
    `potential-gate` edge (P-14: edge-kind membership is not mutually exclusive per pair) don't
    draw two identical overlapping polylines. Not a crossing-minimising router -- a fixed,
    reproducible hash-based offset, documented as a first pass; real obstacle-avoiding channel
    allocation is follow-on Stage 2 work."""
    digest = hashlib.sha256(f"{from_key}->{to_key}#{kind}".encode()).digest()
    return (digest[0] % span) * spacing


def _route_edges(typed_edges: list[TypedEdge], nodes: dict[str, NodeLayout], band_of) -> list[EdgeLayout]:
    """Routes P-14's full three-kind edge set. Every kind uses the SAME first-pass orthogonal
    H-V-H router and the SAME backward/band-span computation -- line-style differentiation
    (solid/dashed/dotted, P-8) is a Stage 3 rendering concern over this shared geometry, not
    something this module decides. `band_span` (from_band_index - to_band_index, positive iff
    backward) is emitted on every edge, not just backward ones, so a consumer never needs to
    recompute it from band indices it may not have handy.

    TODO(Stage 3): `potential-gate`'s backward population reaches up to 5 bands back (measured;
    P-8's "1-2 bands back, small and short-range" text describes `prerequisite`/`alternative`
    only -- see spec/P-08-connectors.md). This router does not special-case long-range
    `potential-gate` backward edges; `band_span` is emitted so a real routing decision can be made
    against an actual rendered canvas, deliberately deferred rather than designed blind here."""
    edges: list[EdgeLayout] = []
    for edge in sorted(typed_edges, key=lambda e: (e.to_key, e.kind, e.from_key)):
        a = nodes[edge.from_key]
        b = nodes[edge.to_key]
        _, from_band_index = band_of(edge.from_key)
        _, to_band_index = band_of(edge.to_key)
        band_span = from_band_index - to_band_index
        backward = band_span > 0

        a_exit = (a.x + CARD_WIDTH, a.y + CARD_HEIGHT / 2) if not backward else (a.x, a.y + CARD_HEIGHT / 2)
        b_entry = (b.x, b.y + CARD_HEIGHT / 2) if not backward else (b.x + CARD_WIDTH, b.y + CARD_HEIGHT / 2)
        offset = _channel_offset(edge.from_key, edge.to_key, edge.kind)
        channel_x = a_exit[0] + (offset if not backward else -offset)

        polyline = [a_exit, (channel_x, a_exit[1]), (channel_x, b_entry[1]), b_entry]
        edges.append(EdgeLayout(
            from_key=edge.from_key, to_key=edge.to_key, kind=edge.kind, group_id=edge.group_id,
            backward=backward, band_span=band_span, polyline=polyline,
        ))
    return edges
