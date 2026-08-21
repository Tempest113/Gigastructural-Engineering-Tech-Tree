"""P-2/D-13: tier-band layout computation.

Bands are a node's own **declared** `tier` field — never adjusted by graph depth (D-13,
`spec/decisions.md`, correcting an earlier promoted-position draft). Computed longest-path
position exists only as internal geometry: it orders nodes horizontally within a band's
sub-grid, and (indirectly, via each node's own declared band) is what makes a "backwards edge" —
a prerequisite whose own band is later than its dependent's — identifiable. Computed position is
never emitted as a displayed value; see S-3's "Band header and card tier badge always agree" note
for why that distinction matters. **D-13 (the band/column axis) is UNCHANGED by the row re-axis
below** — only the OTHER axis (rows) changed.

**Row re-axis (later session, a design divergence found by showing the rendered output to the
user).** The row axis used to be D-7's crisis-faction LANE_ORDER (standard progression as one
lane, then one lane per faction, category used only as a sub-grid wrap key inside a lane×band
cell). The user confirmed from v1 screenshots this was never the intent, and it wastes enormous
vertical space: a faction lane reserves a full-height row for as few as 3 (Aeternum,
Katzenartig Imperium), 7 (Sirenalia) or even 0 (Compound) nodes, the same vertical weight as
Standard's 925.

**The row model now**: rows are the vanilla technology categories, one row each, followed by one
row per crisis faction (D-7's five, unified — NOT sub-split by category or research area the way
the old Standard lane's sub-grid used to group by category). Row assignment is **faction-first
and mutually exclusive**: a technology with a crisis faction (`pipeline.crisis_faction`,
UNCHANGED — see that module) goes in that faction's row; every other technology goes in its own
category's row. `pipeline/crisis_faction.py` and D-7's derivation itself did not change at all —
only what CONSUMES that classification changed, from "which lane" to "which row, when a faction
is present."

**Why "the 13 categories" needs to be derived, not hand-typed.** Gigastructures defines its own
technology category, `blokkats` (`common/technology/category/giga_category.txt`), used by
exactly the 42 rendered technologies the D-7 classifier already places in the Blokkats faction
row by technology-ID fragment (`pipeline.crisis_faction._ID_FRAGMENTS`) — 42/42, confirmed by
direct corpus survey, zero non-faction technology carries `category = { blokkats }`. Under
faction-first placement this category has **zero** remaining members once its Blokkats
technologies move to the Blokkats row, so it must never become its own (empty, spurious) category
row. Deriving the category-row set from the technologies that actually land in a category row
(rather than hand-typing "the 13 vanilla categories" as a fixed list) handles this for free, with
no special case for `blokkats` anywhere in this module — and is the same "enumerate from the
dataset, never hardcode" discipline `distinct_tiers`/bands already use below. Verified over the
real 980-node corpus: this derivation yields exactly the 13 real vanilla category ids
(`archaeostudies`, `biology`, `computing`, `field_manipulation`, `industry`,
`military_theory`, `materials`, `new_worlds`, `particles`, `propulsion`, `psionics`,
`statecraft`, `voidcraft`) with the largest of any faction's departure leaving its
donor category comfortably populated (psionics: 41 → 34 once Sirenalia's 7 leave) — no vanilla
category is left empty or near-empty.

**Row order**: the 13 (derived) categories, grouped by research area — `AREA_ORDER` below,
physics then society then engineering, matching this project's existing area-colour convention
(S-1/`client/src/tokens.ts`) — then alphabetically by category id within an area (simple,
reproducible, no additional corpus dependency; each real category maps to exactly one area
1:1 in the corpus, confirmed by direct survey, so there's no real ambiguity to break a tie on).
Then the 5 crisis-faction rows, in `pipeline.crisis_faction.CRISIS_FACTIONS`'s existing fixed
order — reused directly rather than re-declared, so the two can't drift apart. Every faction row
is always emitted, including Compound at its confirmed-real zero population (`pipeline.
crisis_faction`'s own module docstring) — unchanged behaviour from the old lane model, just now
true of a row instead of a lane.

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
from .crisis_faction import CRISIS_FACTIONS
from .edges import EdgeExtractionDiagnostics, TypedEdge, compute_typed_edges
from .overwrites import TechnologyDefinition, ordered_prerequisites
from .variables import UndefinedVariableError, VariableCycleError, VariableTable

REPEATABLES = "repeatables"  # sentinel band id, always the terminal band in every row

# Row-order grouping key for category rows -- physics, then society, then engineering, matching
# the existing area-colour convention (spec/S-01-colour.md, client/src/tokens.ts's AREA_COLORS
# key order). Faction rows don't participate in this grouping at all; they follow, in
# `pipeline.crisis_faction.CRISIS_FACTIONS`'s own fixed order, reused directly (see module
# docstring) rather than re-declared here.
AREA_ORDER = ("physics", "society", "engineering")

# Card dimensions (spec/P-02-layout.md's "Card dimensions" implied technical decision): sized to
# fit the p95 rendered-name length (39 chars) across up to two lines, AND the worst-case gate
# string (35 chars, "Needs " dropped in favour of the gate icon carrying that semantic) on one
# line, untruncated. Gate text is never truncated; names truncate at p95 with the full name
# available in the popup and hover title -- both are Stage 3 rendering decisions, not enforced
# here, but the dimensions below are sized for them.
CARD_WIDTH = 270
CARD_HEIGHT = 92

# Gutters (updated across two sessions of density complaints, both against real screenshots, not
# guessed at). Every gap below is collected here, the one named place, so a future density
# complaint has one place to look, not several.
#
# Session 1: the user flagged the original 8px/10px sibling-card gaps and the single 40px combined
# header+separator strip as reading like edge-to-edge touching cards -- doubled to 16px/16px/48px.
#
# Session 2 (this session, DEFECT 1): with the row re-axis's densest cell down to 47 nodes
# (voidcraft x T5, from the old lane model's 253), there is real room to spend and the user asked
# for it explicitly spent, with performance not a constraint (measured median 6.1ms/p95 12.1ms per
# frame on real hardware WebGL, well inside a 16.7ms/60fps budget, and viewport culling already
# measured and rejected as unnecessary at this node count). Chosen values, concrete and stated:
# INTRA_GAP_X/Y 16->24px (+50%, comfortable breathing room between sibling cards without the
# sub-grid reading as sparse); INTER_BAND_GUTTER 48->96px (doubled -- this gutter does double duty
# as both the visual tier-band separator AND the reserved P-8 edge-routing channel, so it benefits
# from headroom on both counts, and doubling reads as a clearly deliberate band boundary rather
# than an incremental nudge).
# DEFECT 2 (this session, third spacing pass): the user reported INTRA_GAP_X (session 2's 16->24)
# still read as too tight specifically on the horizontal axis; INTRA_GAP_Y at 24 was confirmed
# acceptable and left unchanged. Raised again, substantially, not incrementally: 24->40px (+67%).
# Canvas size remains not a constraint (same real-hardware performance headroom cited in session
# 2's own comment; nothing about horizontal card spacing changes the frame budget).
#
# EAWAF/v1-routing session (a fourth spacing pass): the user reported 40px STILL read as a packed
# grid, the third time this specific complaint has been raised -- each previous increase was too
# small. Raised substantially again, well past the previous increments: 40->120px (3x). Chosen so
# adjacent cards clearly read as separate objects with real breathing room, not incrementally
# nudged from the last complaint. Canvas size remains not a constraint (same measured real-hardware
# 6.1ms median/12.1ms p95 frame budget headroom cited above; nothing about horizontal card spacing
# changes it, and viewport culling was already measured and rejected as unneeded at this node count).
INTRA_GAP_X = 120  # between sibling cards within one row x band cell's sub-grid row -- was 16, then 24, then 40
INTRA_GAP_Y = 24  # between sub-grid rows within one row x band cell -- was 16, confirmed acceptable at 24, unchanged this session
INTER_BAND_GUTTER = 96  # between adjacent tier-band columns, reserved for P-8 routing channels -- was 48
# ROW_HEADER_HEIGHT (DEFECT 4, session 2): raised 40->52px to give the row header chip and the
# per-(row,band)-cell tier label (client/src/main.ts) independent, non-overlapping vertical bands
# to occupy within the header strip -- at 40px both occupied the same ~26px-tall region and
# visibly collided. 52px fit chip (26px, 4px top pad) then a 4px gap then the cell label (~16px)
# with only ~2px of clearance before the first row of cards -- too tight, per this session's Part-2
# spacing pass ("add vertical space between the label and the first row of cards"). Raised again,
# 52->68px, giving the label a real ~16px clearance before cards start; see main.ts's own
# header-layout comment for the exact sub-split and the numeric non-overlap check run against it.
ROW_HEADER_HEIGHT = 68  # per-row header-label strip, present even for a zero-population row (e.g. Compound) -- was 40, then 52
# ROW_GUTTER (DEFECT 2, this session): the user asked for MORE separation between rows so research
# categories visibly separate at fit-to-viewport zoom -- raised 24->48px (doubled, matching the
# same "clearly deliberate boundary, not an incremental nudge" reasoning INTER_BAND_GUTTER's own
# session-2 doubling used).
ROW_GUTTER = 48  # pure visual separation between one row's last sub-grid row and the next row's header,
# on top of ROW_HEADER_HEIGHT -- previously the header strip alone (LANE_LABEL_MARGIN) did double
# duty as both label space AND the only separation between rows, which is exactly what read as
# cramped. A zero-population row still reserves ROW_HEADER_HEIGHT + ROW_GUTTER -- the renderer
# collapses it to header height visually in a later Stage 3 slice; this pipeline emits the real,
# uncollapsed geometry, per this session's own "renderer changes are a separate slice" boundary.
# AREA_GROUP_GUTTER (new, this session, DEFECT 2): an ADDITIONAL gap, on top of ROW_GUTTER, before
# the first row of a new group -- the three research areas (physics/society/engineering) each form
# one group, and the 5 crisis-faction rows together form a fourth, so the row stack reads as four
# grouped blocks rather than 18 evenly-spaced strips, as requested. Applied once per group boundary
# (17 row-to-row gaps total, but only 3 of them are GROUP boundaries: computing->archaeostudies,
# statecraft->industry, voidcraft->Aeternum -- see `_row_order`'s `row_group_of` return).
#
# EAWAF/v1-routing session: reduced 96->64px. Root cause of the user's "no visible separation"
# report was NOT this constant -- it was a real rendering bug (see client/src/main.ts's
# `drawRowPanel` call site comment): every row's panel was drawn across its FULL reserved
# `rowHeight`, which already includes that row's own trailing `ROW_GUTTER` as computed below, so
# one row's panel visually bled into the gutter meant to separate it from the next row's panel,
# leaving same-group row boundaries (and every faction-to-faction boundary, since all five faction
# rows share one group) with an apparent 0px gap even though `ROW_GUTTER` was a real, nonzero
# number. Fixed at the render call site (panels now stop `ROW_GUTTER` short of their own bottom
# edge), which makes `ROW_GUTTER` itself finally visible as a real, if smaller, gap -- at which
# point AREA_GROUP_GUTTER's PREVIOUS 96px (already equal to INTER_BAND_GUTTER, and now nearly 2x
# a suddenly-visible ROW_GUTTER=48px) read as disproportionately large next to it. Reduced to 64px
# -- still clearly larger than ROW_GUTTER (48px), preserving three distinct, ordered separation
# levels (card < row < group), but no longer as large as the unrelated INTER_BAND_GUTTER.
AREA_GROUP_GUTTER = 64

MIN_STUB = 8  # minimum horizontal run at each end of an edge before any turn (P-2's
# card-avoidance router rewrite, this session). Combined with a channel offset capped at
# INTRA_GAP_X - MIN_STUB (16px headroom), the resulting turn point always stays inside the local
# column gap -- never spills into a sibling card's bounding box. See _route_edges's own
# docstring for the full 6-waypoint routing design and why a plain 4-point H-V-H shape can't
# reach zero card crossings no matter where MIN_STUB places the single bend.

DEFAULT_SUBGRID_WIDTH = 6  # N -- D-17's 4/6/8/12 trade-off survey; user picked 6. See D-17 in
# spec/decisions.md for the full reasoning: 6 is the only value that REDUCES canvas width
# relative to 4 (29,670 vs 30,840) while also fixing the aspect ratio (2.21:1 vs 3.17:1), and it
# cuts worst-case band width from 8,460 to 5,730px -- the figure that governs how far a user must
# pan to cross a single tier band. 8 buys negligible further aspect improvement for roughly double
# the canvas area; 12 is worse on aspect than 6 while quadrupling it.


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


def _scalar_text(node) -> str | None:
    if isinstance(node, Identifier):
        return node.name
    if isinstance(node, StringLiteral):
        return node.value
    return None


def area_of(block: Block) -> str:
    """A technology's `area` field, read the same permissive way `pipeline.dataset_emit`'s own
    `area` extraction does (mirrored here, not imported, to keep this module's only dependency on
    `pipeline.dataset_emit` at zero -- that module already depends on this one). Defaults to
    `"physics"` when the field is absent, matching `pipeline.dataset_emit`'s own default -- used
    here ONLY to group category rows by area for `ROW_ORDER`'s ordering (see module docstring),
    never emitted as this function's own displayed value."""
    assignment = _field(block, "area")
    return (_scalar_text(assignment.value) if assignment else None) or "physics"


@dataclass(frozen=True)
class TechnologyLayoutInput:
    key: str
    block: Block
    faction: str | None  # crisis faction name (D-7), or None -- row falls back to `category` (see `_row_id_of`)


@dataclass(frozen=True)
class BandDescriptor:
    band_id: int | str  # declared tier (int), or REPEATABLES
    index: int  # ordinal position, ascending, REPEATABLES always last
    label: str


@dataclass(frozen=True)
class NodeLayout:
    technology_key: str
    row_id: str  # row id: a category id, or a crisis-faction name -- see module docstring's row model
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
    row_ids: list[str]  # ROW_ORDER: derived category rows, then the 5 fixed faction rows -- see module docstring
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


def _same_band_depth(
    rendered_keys: set[str],
    prereqs_of: dict[str, list[str]],
    band_index_of: dict[str, int],
    extra_same_band_edges: dict[str, list[str]] | None = None,
) -> dict[str, int]:
    """D-17's same-band ordering invariant (`spec/decisions.md`): a technology's sub-column must
    exceed every SAME-BAND prerequisite's sub-column, so a same-band prerequisite chain renders
    strictly left-to-right instead of stacking in one column. Computed per band, across every row
    that shares it -- an edge's ROW membership is irrelevant to which BAND it's in, and the item-3
    survey measured this the same way (topological sort over the same-band-only edge subgraph,
    pooled across rows). Reuses `_topological_order` scoped to a same-band-only prereqs mapping,
    the same Kahn's-algorithm machinery `_computed_position` already uses for the full graph.

    The survey confirmed zero same-band cycles in the real corpus; a future one is a hard build
    failure (`LayoutCycleError`, from `_topological_order`), never silently ignored or broken by
    dropping an edge.

    **Extended (D-17 same-sub-column follow-up)**: `extra_same_band_edges` carries the SAME
    `from_key -> [to_key's prereqs]`-shaped mapping as `prereqs_of`, but sourced from
    `alternative`/`potential-gate` edges -- the survey found 6 real cases (2 in the Compound row)
    where one of THOSE edge kinds, not a formal `prerequisite`, put a dependent in the exact same
    sub-column as its counterpart. Merged into the same topological sort as an ADDITIONAL
    ordering constraint (not into `prereqs_of`/`computed_position`, which stay prerequisite-only,
    per CLAUDE.md D-17's own scope) so a dependent's sub-column strictly exceeds a same-band
    `alternative`/`potential-gate` source's too, closing the gap without touching
    `subgrid_width` or any other geometry the D-17 negotiation already settled."""
    same_band_prereqs = {
        key: [p for p in prereqs_of[key] if band_index_of[p] == band_index_of[key]] for key in rendered_keys
    }
    if extra_same_band_edges:
        for key in rendered_keys:
            extras = [p for p in extra_same_band_edges.get(key, []) if band_index_of.get(p) == band_index_of[key]]
            if extras:
                same_band_prereqs[key] = sorted({*same_band_prereqs[key], *extras})
    order = _topological_order(rendered_keys, same_band_prereqs)
    depth: dict[str, int] = {}
    for key in order:
        ps = same_band_prereqs[key]
        depth[key] = (max(depth[p] for p in ps) + 1) if ps else 0
    return depth


class UnresolvedRowError(LayoutError):
    """A rendered technology has no crisis faction AND no resolvable category -- row assignment
    is faction-first-else-category (module docstring); a technology matching neither has no row
    to go in. Hard failure, never a silent default row -- same discipline as
    `UnresolvedTierError`. Zero real rendered technologies hit this today (every one has a
    resolvable `category`, confirmed by direct corpus survey), but the policy exists so a future
    one fails loudly instead of landing in a wrong or invented row."""

    def __init__(self, technology_key: str):
        self.technology_key = technology_key
        super().__init__(f"{technology_key}: no crisis faction and no resolvable category -- cannot assign a row")


def _row_id_of(key: str, faction: str | None, category: str | None) -> str:
    """Faction-first, mutually exclusive (module docstring): a technology with a crisis faction
    goes in that faction's row; every other technology goes in its own category's row."""
    if faction is not None:
        return faction
    if category is not None:
        return category
    raise UnresolvedRowError(key)


def _row_order(rendered_keys: set[str], row_id_of: dict[str, str], categories: dict[str, str | None],
               areas: dict[str, str]) -> tuple[list[str], dict[str, int]]:
    """ROW_ORDER (module docstring): the categories actually present among non-faction
    technologies, grouped by `AREA_ORDER` then alphabetically by category id, followed by the 5
    crisis-faction rows in `CRISIS_FACTIONS`' own fixed order (always all 5, even at zero
    population -- Compound). Derived from `row_id_of`/`categories`, never hand-typed, so a
    category whose entire membership is faction-classified (Gigastructures' own `blokkats`
    category, 42/42 Blokkats-faction -- module docstring) never gets a spurious empty row of its
    own: it simply never appears as any technology's row id once faction-first assignment has
    run.

    Returns `(row_order, row_group_of)` -- the second dict maps every row id to its GROUP index
    (DEFECT 2, this session: 0/1/2 for the three research areas, `len(AREA_ORDER)` for every
    faction row), used by `compute_layout`'s row-height loop to add `AREA_GROUP_GUTTER` only at a
    group boundary, so the row stack reads as four grouped blocks rather than N evenly-spaced
    strips."""
    category_rows = {row_id_of[k] for k in rendered_keys if row_id_of[k] not in CRISIS_FACTIONS}

    def area_index_of_category(category: str) -> int:
        # Majority vote across that category's own (already faction-excluded) members -- in the
        # real corpus every category maps to exactly one area 1:1 (confirmed by direct survey),
        # so this only ever needs to break a hypothetical future tie, not a real one today.
        votes: dict[str, int] = {}
        for k in rendered_keys:
            if categories.get(k) == category:
                votes[areas[k]] = votes.get(areas[k], 0) + 1
        area = max(votes.items(), key=lambda kv: (kv[1], -AREA_ORDER.index(kv[0]) if kv[0] in AREA_ORDER else 0))[0] if votes else AREA_ORDER[0]
        return AREA_ORDER.index(area) if area in AREA_ORDER else len(AREA_ORDER)

    ordered_categories = sorted(category_rows, key=lambda c: (area_index_of_category(c), c))
    row_order = [*ordered_categories, *CRISIS_FACTIONS]

    # Row GROUP index, for the inter-group gap (DEFECT 2, this session): the 3 research areas
    # (physics/society/engineering, AREA_ORDER's own order) each get their own group index, and
    # every crisis-faction row shares ONE further group -- matching the requested "four grouped
    # blocks" reading (three area blocks, then the faction block), not a gap between every single
    # row. A category row's group is its own area's index; a faction row's group is
    # len(AREA_ORDER), always the last/highest group index so it sorts after every area.
    row_group_of: dict[str, int] = {}
    for category in ordered_categories:
        row_group_of[category] = area_index_of_category(category)
    for faction in CRISIS_FACTIONS:
        row_group_of[faction] = len(AREA_ORDER)

    return row_order, row_group_of


def compute_layout(
    technologies: dict[str, TechnologyLayoutInput],
    variable_table: VariableTable,
    subgrid_width: int = DEFAULT_SUBGRID_WIDTH,
) -> LayoutResult:
    """Full P-2/D-13 layout over `technologies` (rendered set only -- P-16). Deterministic: the
    same input always produces the same node positions (P-2's acceptance criterion) -- every
    ordering step below breaks ties on `technology_key`, never dict/set iteration order.

    Two independent axes, per the module docstring: bands (columns) are declared tier, UNCHANGED
    by the row re-axis; rows are faction-first-else-category, replacing the old lane axis."""
    rendered_keys = set(technologies.keys())

    tiers: dict[str, int] = {}
    repeatable: dict[str, bool] = {}
    categories: dict[str, str | None] = {}
    areas: dict[str, str] = {}
    prereqs_of: dict[str, list[str]] = {}

    for key, tech in technologies.items():
        tiers[key] = resolve_declared_tier(key, tech.block, variable_table)
        repeatable[key] = is_repeatable(tech.block, variable_table)
        categories[key] = category_of(tech.block)
        areas[key] = area_of(tech.block)
        prereqs_of[key] = [p for p in ordered_prerequisites(tech.block) if p in rendered_keys]

    computed_position = _computed_position(rendered_keys, prereqs_of)

    # Bands: every distinct declared tier actually present among non-repeatable nodes (P-2: "MUST
    # be enumerated from the dataset at build time", never a hardcoded range), ascending, plus the
    # terminal Repeatables band. UNCHANGED by the row re-axis.
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

    # Row ids: faction-first-else-category (module docstring). The field name stays `row_id`
    # throughout this module and in `pipeline.dataset_emit`'s JSON emission (`rowId`/`rows`) --
    # a deliberate choice this session, not an oversight: renaming the JSON contract is renderer
    # (Stage 3) work, explicitly out of this session's scope, and the shape doesn't change (still
    # a list of row-id-keyed groups), only its cardinality and the meaning of "which one" -- see
    # CLAUDE.md/HANDOFF.md for the rename tracked as the next slice's work.
    row_id_of = {key: _row_id_of(key, tech.faction, categories[key]) for key, tech in technologies.items()}
    row_order, row_group_of = _row_order(rendered_keys, row_id_of, categories, areas)

    # D-17: sub-column is no longer a plain wrap-at-N index -- it's each key's same-band
    # prerequisite-chain depth (`_same_band_depth`), so a same-band prerequisite chain always
    # renders strictly left-to-right, never stacked in one column. `band_index_of` builds once and
    # is reused for both the depth computation and the per-band width below.
    band_index_of = {key: band_of(key)[1] for key in rendered_keys}

    # P-14 full three-kind edge set, computed here (rather than just before `_route_edges` below,
    # where it used to live) so its `alternative`/`potential-gate` edges can ALSO feed the
    # same-sub-column extension below -- one computation, reused by both. `prereqs_of` above is
    # deliberately narrower (true prerequisites only) and stays the sole input to
    # `computed_position`/`_same_band_depth`'s own prerequisite-only argument; only the EXTRA
    # ordering constraint passed to `_same_band_depth` draws on the other two kinds.
    typed_edges, edge_diagnostics = compute_typed_edges({key: tech.block for key, tech in technologies.items()})
    extra_same_band_edges: dict[str, list[str]] = {}
    for edge in typed_edges:
        if edge.kind in ("alternative", "potential-gate"):
            extra_same_band_edges.setdefault(edge.to_key, []).append(edge.from_key)

    same_band_depth = _same_band_depth(rendered_keys, prereqs_of, band_index_of, extra_same_band_edges)

    # Group by (row, band); within a group, sort by (`same_band_depth`, `computed_position`, key)
    # so members at the same depth are ordered deterministically before being wrapped into
    # sub-columns below. `computed_position` (the full-graph longest-path depth) is only a
    # tie-breaker here -- `same_band_depth` (same-band-only) is what the D-17 invariant is stated
    # over.
    groups: dict[tuple[str, int], list[str]] = {}
    for key in rendered_keys:
        groups.setdefault((row_id_of[key], band_index_of[key]), []).append(key)

    for members in groups.values():
        members.sort(key=lambda k: (same_band_depth[k], computed_position[k], k))

    # D-17 correction: depth sets the MINIMUM sub-column a node may occupy, but a depth is a
    # SLOT of one or more sub-columns, not a single unbounded stack -- members sharing a depth
    # wrap at `subgrid_width` rows per sub-column, spilling into additional sub-columns within
    # their own depth's slot exactly like the pre-D-17 wrap-at-N behaviour did, rather than
    # stacking without limit (the bug: 37 unrelated depth-0 technologies in one band/row cell
    # previously rendered as one 37-row-tall column). A depth's slot width is the widest wrap any
    # ROW sharing that band needs at that depth, since `same_band_depth`/the column x-position are
    # shared across every row in the band; slot START is the cumulative sum of every shallower
    # depth's own slot width in that band, so a deeper depth's sub-columns never overlap a
    # shallower depth's -- the invariant (a dependent's column strictly exceeds its same-band
    # prerequisite's) still holds: a dependent's depth is strictly greater, so its slot start is
    # >= the shallower depth's slot start + its full width, i.e. strictly past every column the
    # shallower depth could ever use.
    depth_counts: dict[tuple[int, int], int] = {}
    for (row_id, band_index), members in groups.items():
        counts_by_depth: dict[int, int] = {}
        for key in members:
            counts_by_depth[same_band_depth[key]] = counts_by_depth.get(same_band_depth[key], 0) + 1
        for depth, count in counts_by_depth.items():
            depth_counts[(band_index, depth)] = max(depth_counts.get((band_index, depth), 0), count)

    depth_slot_width: dict[tuple[int, int], int] = {
        key: -(-count // subgrid_width) for key, count in depth_counts.items()  # ceil division
    }

    depth_slot_start: dict[tuple[int, int], int] = {}
    band_width: dict[int, int] = {}
    for band_index in {b for (b, _d) in depth_counts}:
        depths_in_band = sorted(d for (b, d) in depth_counts if b == band_index)
        cursor = 0
        for d in depths_in_band:
            depth_slot_start[(band_index, d)] = cursor
            cursor += depth_slot_width[(band_index, d)]
        band_width[band_index] = max(cursor, subgrid_width)

    # Cumulative per-band x-start: bands are no longer uniform width, so a band's x-origin is the
    # running sum of every earlier band's own (possibly wider) pitch, not `band_index * a
    # constant`. `bands` is already in ascending index order (enumerate() above).
    band_x_start: dict[int, float] = {}
    _cursor = 0.0
    for _b in bands:
        band_x_start[_b.index] = _cursor
        _width = band_width.get(_b.index, subgrid_width)
        _cursor += _width * CARD_WIDTH + (_width - 1) * INTRA_GAP_X
        if _b.index != bands[-1].index:
            _cursor += INTER_BAND_GUTTER
    canvas_width = _cursor

    band_id_of_index = {b.index: b.band_id for b in bands}
    nodes: dict[str, NodeLayout] = {}
    row_row_counts: dict[str, int] = {row: 0 for row in row_order}
    # Item 4 (screenshot-review session): a sub-grid COLUMN's own member count is very often
    # LESS than the row's shared height (set by that row's tallest column anywhere across every
    # band) -- e.g. voidcraft/T0's "Waystations" column has 3 members against the row's own
    # 6-row height. Under the old single-pass placement, every column was top-anchored at
    # `local_row = offset % subgrid_width`, so 100% of a short column's slack fell BELOW its last
    # card and none above (beyond the row header all columns already share) -- confirmed visually
    # in a real screenshot, not assumed. `column_member_count` records each column's own count so
    # a second pass (below, once `row_row_counts` is final) can centre it within the row's shared
    # height instead, splitting the slack roughly evenly above and below.
    # REGRESSION FIX (screenshot-review session, hard layout regression): `column_member_count`
    # was keyed by `(row_id, col)` alone. `col` is BAND-RELATIVE -- `depth_slot_start[(band_index,
    # depth)]` resets its own `cursor` to 0 for every `band_index` (see the `depth_slot_start`
    # construction above) -- so col 0 in band 2 and col 0 in band 5 of the SAME row are physically
    # different columns (different x, via `band_x_start[band_index] + col * ...`) but shared the
    # SAME dict key. Two different bands' columns landing on the same local index had their member
    # counts silently SUMMED into one entry, which could exceed `row_row_counts[row_id]` (the
    # row's own real max) and drive `centre_offset` NEGATIVE -- shifting a column's cards upward
    # past row=0, overlapping the row above. This is what actually produced the reported row-
    # overlap regression, not the centering concept itself. Fixed by keying on the full
    # `(row_id, band_index, col)` triple, which is unique by construction (band_x_start is
    # per-band, col is unique within a band). A new corpus test
    # (`test_no_row_overlaps_and_every_card_within_its_own_row_bounds`,
    # tests/test_layout_corpus.py) pins this as a standing invariant -- proven capable of failing
    # first, against the actual pre-fix code, before being trusted on the fix.
    column_member_count: dict[tuple[str, int, int], int] = {}
    placements: dict[str, tuple[int, int, int]] = {}  # key -> (band_index, col, local_row), local_row 0-based top-anchored within its OWN column

    for (row_id, band_index), members in groups.items():
        idx_in_depth: dict[int, int] = {}
        max_rows_used = 0
        for key in members:
            depth = same_band_depth[key]
            offset = idx_in_depth.get(depth, 0)
            idx_in_depth[depth] = offset + 1
            col = depth_slot_start[(band_index, depth)] + offset // subgrid_width
            local_row = offset % subgrid_width
            max_rows_used = max(max_rows_used, local_row + 1)
            x = band_x_start[band_index] + col * (CARD_WIDTH + INTRA_GAP_X)
            placements[key] = (band_index, col, local_row)
            column_key = (row_id, band_index, col)
            column_member_count[column_key] = column_member_count.get(column_key, 0) + 1
            nodes[key] = NodeLayout(
                technology_key=key, row_id=row_id, band_id=band_id_of_index[band_index], band_index=band_index,
                row=local_row, col=col, x=float(x), y=0.0,  # row/y finalised below, once row heights are known
            )
        row_row_counts[row_id] = max(row_row_counts[row_id], max_rows_used)

    # Second pass: re-express each node's `row` as its column-count-aware, row-height-centred
    # position -- `column_member_count` and `row_row_counts` are both only final once every
    # (row_id, band_index) group above has been visited, hence the separate pass rather than
    # computing this inline above.
    #
    # Item 6 (later session, user domain call): the original `// 2` (true 50/50 centring) read as
    # "a large gap at the top, cards touching the bottom" for a sparsely-populated column in a
    # tall row -- confirmed against a real screenshot, not assumed. This is NOT the D-17/
    # column-keying regression above (that one produced NEGATIVE offsets from a real dict-keying
    # bug; this is correctly-computed, genuinely symmetric slack that still reads as top-heavy
    # once compounded with ROW_HEADER_HEIGHT's own header-strip space sitting immediately above
    # row 0 -- the header's real content (chip + cell label) makes the already-symmetric slack
    # above a sparse column look larger than the equal slack below it, which has no comparable
    # content of its own to visually break up the gap). Fixed by putting a QUARTER of the slack
    # above and three-quarters below (`// 4` instead of `// 2`) -- directly halves the ABOVE-row-0
    # portion of the gap relative to the old formula, matching the user's explicit "roughly half
    # the current top gap" instruction, with the freed slack going below rather than being
    # discarded (removing it would just shrink the row, not rebalance it).
    for key, (band_index, col, local_row) in placements.items():
        row_id = nodes[key].row_id
        column_key = (row_id, band_index, col)
        centre_offset = (row_row_counts[row_id] - column_member_count[column_key]) // 4
        assert centre_offset >= 0, (
            f"{key}: centre_offset {centre_offset} < 0 -- column_member_count[{column_key}]="
            f"{column_member_count[column_key]} exceeds row_row_counts[{row_id!r}]="
            f"{row_row_counts[row_id]}, which is impossible for a correctly-scoped column key "
            f"and would push this node's row negative, overlapping the row above"
        )
        nodes[key] = NodeLayout(
            technology_key=nodes[key].technology_key, row_id=row_id, band_id=nodes[key].band_id,
            band_index=nodes[key].band_index, row=centre_offset + local_row, col=col,
            x=nodes[key].x, y=0.0,
        )

    # Row vertical offsets, in `row_order` (so every row -- including a zero-population one, e.g.
    # Compound -- always reserves its strip). Row height is VARIABLE, derived from the largest
    # (row, band) cell actually in that row under the N-wide sub-grid wrap -- never padded to a
    # global maximum across all rows (that was never true even under the old lane model, but is
    # restated here since it's now load-bearing: category rows and faction rows can have very
    # different natural heights, e.g. `voidcraft`'s 123 vs. Aeternum's 3).
    row_y_offset: dict[str, float] = {}
    y_cursor = 0.0
    previous_group: int | None = None
    for row_id in row_order:
        # DEFECT 2 (this session): an extra AREA_GROUP_GUTTER before the first row of a new group
        # (a new research area, or the faction block) -- never before the very first row overall,
        # so the canvas doesn't start with a leading gap.
        current_group = row_group_of[row_id]
        if previous_group is not None and current_group != previous_group:
            y_cursor += AREA_GROUP_GUTTER
        previous_group = current_group

        row_y_offset[row_id] = y_cursor
        rows = row_row_counts.get(row_id, 0)
        row_height = ROW_HEADER_HEIGHT + ROW_GUTTER + (rows * CARD_HEIGHT + max(0, rows - 1) * INTRA_GAP_Y if rows else 0)
        y_cursor += row_height
    canvas_height = y_cursor

    nodes = {
        key: NodeLayout(
            technology_key=n.technology_key, row_id=n.row_id, band_id=n.band_id, band_index=n.band_index,
            row=n.row, col=n.col, x=n.x,
            y=row_y_offset[n.row_id] + ROW_HEADER_HEIGHT + n.row * (CARD_HEIGHT + INTRA_GAP_Y),
        )
        for key, n in nodes.items()
    }

    # canvas_width was computed above (D-17: bands are no longer uniform width, so it has to be a
    # cumulative sum over each band's own possibly-widened pitch -- see `band_x_start`/`_cursor`).

    # P-14: full three-kind edge set (prerequisite/alternative/potential-gate), NOT just
    # prereqs_of -- prereqs_of above is deliberately narrower (true prerequisites only) and feeds
    # ONLY the internal DAG position/backward-band computation, never the emitted edge list.
    # UNCHANGED by the row re-axis: the router only ever reads node.x/node.y and band_of, and
    # doesn't care which axis produced them. `typed_edges`/`edge_diagnostics` were already computed
    # above (same-sub-column extension) -- reused here rather than recomputed.
    edges = _route_edges(typed_edges, nodes, band_of, row_y_offset)

    return LayoutResult(
        nodes=nodes, edges=edges, bands=bands, row_ids=list(row_order),
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


def _v1_style_waypoints(
    x1: float, y1: float, x2: float, y2: float, min_stub: float, offset: float = 0.0
) -> tuple[bool, list[tuple[float, float]]]:
    """Ports v1's `addEdge` trace geometry (github.com/Tempest113/Gigas-Tech-Tree, js/render.js)
    almost verbatim: leave the source card horizontally, turn in the gap near the target with a
    45-degree chamfer, arrive horizontally. v1's own formula:

        x1 = from.x + CARD_W, y1 = from.y + CARD_H/2
        x2 = to.x,             y2 = to.y + CARD_H/2
        reach  = clamp(24, 70, (x2-x1)*0.4)
        mid    = x2 - reach
        chamfer = min(14, |dy|/2, max(6, (mid-x1)/2))
        dir     = sign(dy)
        path: (x1,y1) -> (mid-chamfer,y1) -> (mid,y1+chamfer*dir) -> (mid,y2-chamfer*dir)
              -> (mid+chamfer,y2) -> (x2,y2)

    v1's own comment: "Because the vertical run happens in the channel, a trace never crosses a
    card" -- true in v1's simpler grid, NOT proven true here (v1 has no faction-row backing, no
    five-row-tall header strips, and no same-band or multi-band-backward edges the way P-14's
    `potential-gate` kind does, up to 5 bands back -- see P-2/P-08). Ported for its LOOK, not
    re-derived as a new safety proof; the caller measures the real crossing count and the project
    accepts it as a known, deliberate trade (CLAUDE.md/HANDOFF.md have the full writeup) rather
    than the previous router's proven zero.

    The one addition beyond a literal port: v1 has no minimum-stub guarantee at all (its own
    `reach` clamp of 24-70px happens to keep the ENTRY stub comfortably above any reasonable
    minimum, but the EXIT stub -- `dx - reach - chamfer` -- goes negative for a short or backward
    edge, which v1's own layout apparently never produced enough of to notice). This function
    clamps `mid` so both stubs respect `min_stub` whenever there is room to do so, and returns
    `False` (not just a bad polyline) when there is not enough horizontal room between the two
    cards for ANY placement of `mid` to satisfy both -- the caller falls back to the proven-safe
    gutter router for exactly those edges, rather than silently emitting a stub violation.

    A SECOND deliberate deviation from the literal port, found in a later reconciliation session:
    v1's real `addEdge` (confirmed by fetching `js/render.js` directly, not from memory) computes
    `mid` from x1/x2 ALONE -- no per-edge offset at all, so two edges sharing similar source/target
    x-distance draw the SAME `mid` and their vertical runs literally overlap. v1's own corpus and
    layout apparently never produced enough coincident geometry for this to read as a "trough";
    this project's much denser real corpus (989 edges, cells up to 47 nodes) does. `offset`
    (0 by default, so a direct v1 comparison is still exactly reproducible) nudges `mid` by a
    small deterministic per-edge amount, reusing the SAME `_channel_offset` hash the gutter router
    already used, so edges sharing a vertical run spread across a few pixels instead of drawing
    identical overlapping traces -- clamped inside the same `[lo, hi]` stub-respecting bounds as
    the base `mid`, so this never reintroduces a stub violation."""
    dy = y2 - y1
    dx = x2 - x1
    if abs(dy) < 1e-6:
        third = x1 + dx / 3.0
        two_third = x1 + dx * 2.0 / 3.0
        return True, [(x1, y1), (third, y1), (third, y1), (two_third, y1), (two_third, y1), (x2, y2)]

    reach = max(24.0, min(70.0, dx * 0.4)) if dx > 0 else 24.0
    mid = x2 - reach + offset
    chamfer = min(14.0, abs(dy) / 2.0, max(6.0, (mid - x1) / 2.0))
    direction = 1.0 if dy > 0 else -1.0

    lo = x1 + min_stub + chamfer
    hi = x2 - min_stub - chamfer
    if lo > hi:
        return False, []
    mid = min(max(mid, lo), hi)

    polyline = [
        (x1, y1),
        (mid - chamfer, y1),
        (mid, y1 + chamfer * direction),
        (mid, y2 - chamfer * direction),
        (mid + chamfer, y2),
        (x2, y2),
    ]
    return True, polyline


def _gutter_style_waypoints(
    a: NodeLayout, b: NodeLayout, backward: bool, offset_a: float, offset_b: float,
    transit_y: float,
) -> list[tuple[float, float]]:
    """The previous, proven-zero-crossings router (see CLAUDE.md's "edge router card-avoidance
    rewrite" bullet for the full measurement history) -- kept as the fallback for whatever edge
    `_v1_style_waypoints` cannot route without violating a minimum stub (a same-band or
    sufficiently-short/backward edge, where there is no horizontal room for v1's two-bend chamfer
    shape at all). See `_route_edges`'s own docstring for why this trade is deliberate and where
    the two routers now split responsibility."""
    a_mid_y = a.y + CARD_HEIGHT / 2
    b_mid_y = b.y + CARD_HEIGHT / 2
    if not backward:
        a_exit = (a.x + CARD_WIDTH, a_mid_y)
        b_entry = (b.x, b_mid_y)
        gap_x_a = a_exit[0] + MIN_STUB + offset_a
        gap_x_b = b_entry[0] - MIN_STUB - offset_b
    else:
        a_exit = (a.x, a_mid_y)
        b_entry = (b.x + CARD_WIDTH, b_mid_y)
        gap_x_a = a_exit[0] - MIN_STUB - offset_a
        gap_x_b = b_entry[0] + MIN_STUB + offset_b

    return [
        a_exit, (gap_x_a, a_exit[1]), (gap_x_a, transit_y),
        (gap_x_b, transit_y), (gap_x_b, b_entry[1]), b_entry,
    ]


def _route_edges(
    typed_edges: list[TypedEdge], nodes: dict[str, NodeLayout], band_of, row_y_offset: dict[str, float]
) -> list[EdgeLayout]:
    """Routes P-14's full three-kind edge set. Every kind uses the SAME router and the SAME
    backward/band-span computation -- line-style differentiation (solid/dashed/dotted, P-8) is a
    Stage 3 rendering concern over this shared geometry, not something this module decides.
    `band_span` (from_band_index - to_band_index, positive iff backward) is emitted on every
    edge, not just backward ones, so a consumer never needs to recompute it from band indices it
    may not have handy.

    **v1-style routing (this session, replacing the card-avoidance gutter-channel router below as
    the DEFAULT).** The gutter router (kept as `_gutter_style_waypoints`, see that function's
    docstring) measured a real, proven zero unrelated-card crossings across all 989 edges -- but
    the user reviewed the rendered result and rejected it: routing every vertical run through a
    shared inter-band/row-header channel produces dense parallel channel traffic that reads as
    MORE visually confusing than the occasional pass-under it eliminates. This is a deliberate,
    KNOWING trade of the measured zero-crossings property for legibility, made after seeing both,
    not a silent regression -- see CLAUDE.md's "edge router: v1-style trade" entry for the real
    before/after crossing counts. `_v1_style_waypoints` (this module) ports
    github.com/Tempest113/Gigas-Tech-Tree's own `addEdge` (js/render.js) chamfered two-bend
    "circuit trace" geometry; `_gutter_style_waypoints` is used ONLY as a fallback for the subset
    of edges (same-band, or otherwise too short/backward for v1's two-bend shape to keep both a
    minimum entry and exit stub) v1's own layout apparently never had to route, per that
    function's own docstring.

    Six waypoints, five segments per edge either way -- `POINTS_PER_POLYLINE`
    (`pipeline/geometry.py`) stays at 6 regardless of which router produced a given edge's
    polyline, so the schema/side-file shape this session inherited from the previous router's
    rewrite needs no further change.

    TODO(Stage 3): `potential-gate`'s backward population reaches up to 5 bands back (measured;
    P-8's "1-2 bands back, small and short-range" text describes `prerequisite`/`alternative`
    only -- see spec/P-08-connectors.md). Both routers route those like any other edge; a further
    VISUAL treatment for especially long spans (a different line style, hover-reveal, etc.) is
    still open, as before."""
    edges: list[EdgeLayout] = []
    for edge in sorted(typed_edges, key=lambda e: (e.to_key, e.kind, e.from_key)):
        a = nodes[edge.from_key]
        b = nodes[edge.to_key]
        _, from_band_index = band_of(edge.from_key)
        _, to_band_index = band_of(edge.to_key)
        band_span = from_band_index - to_band_index
        backward = band_span > 0

        a_mid_y = a.y + CARD_HEIGHT / 2
        b_mid_y = b.y + CARD_HEIGHT / 2
        offset_a = _channel_offset(edge.from_key, edge.to_key, edge.kind) % (INTRA_GAP_X - MIN_STUB)
        offset_b = _channel_offset(edge.to_key, edge.from_key, edge.kind) % (INTRA_GAP_X - MIN_STUB)

        x1, y1 = a.x + CARD_WIDTH, a_mid_y
        x2, y2 = b.x, b_mid_y
        # Trough fix (reconciliation session): a small, deterministic, roughly-zero-centred
        # per-edge nudge to `mid` -- see `_v1_style_waypoints`'s own docstring for why v1's literal
        # formula has no such offset and why this corpus needs one anyway.
        v1_offset = (_channel_offset(edge.from_key, edge.to_key, edge.kind, spacing=4.0, span=15) - 28.0) / 2.0
        ok, polyline = _v1_style_waypoints(x1, y1, x2, y2, MIN_STUB, offset=v1_offset)
        if not ok:
            transit_y = row_y_offset[a.row_id] + ROW_HEADER_HEIGHT / 2
            polyline = _gutter_style_waypoints(a, b, backward, offset_a, offset_b, transit_y)

        edges.append(EdgeLayout(
            from_key=edge.from_key, to_key=edge.to_key, kind=edge.kind, group_id=edge.group_id,
            backward=backward, band_span=band_span, polyline=polyline,
        ))
    return edges
