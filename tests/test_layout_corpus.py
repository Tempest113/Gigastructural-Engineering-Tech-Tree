"""P-2/D-13 layout computed against the real vendored corpus, over the exact 980-node P-16
rendered set -- the real canvas dimensions and densest band cell this session's report is based
on. Skipped when vendor/ isn't populated, same posture as the other corpus tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.clausewitz import parse_file
from pipeline.clausewitz.nodes import Assignment
from pipeline.crisis_faction import classify_crisis_factions
from pipeline.crisis_faction_flags import load_flag_overrides as load_crisis_flag_overrides
from pipeline.crisis_faction_overrides import load_overrides as load_crisis_overrides
from pipeline.geometry import pack_edge_polylines, pack_node_positions
from pipeline.inline_scripts import collect_scripts, expand_document
from pipeline.layout import (
    DEFAULT_SUBGRID_WIDTH,
    TechnologyLayoutInput,
    UnresolvedTierError,
    compute_layout,
    is_repeatable,
    resolve_declared_tier,
)
from pipeline.overwrites import collect_technology_definitions
from pipeline.rendering_scope import rendered_technology_keys
from pipeline.variables import build_variable_table

REPO_ROOT = Path(__file__).resolve().parent.parent
VENDOR_ROOT = REPO_ROOT / "vendor"

_SOURCES_IN_LOAD_ORDER = [
    ("Vanilla", VENDOR_ROOT / "stellaris"),
    ("Gigastructural Engineering", VENDOR_ROOT / "mods" / "gigastructures"),
    ("ACOT", VENDOR_ROOT / "mods" / "acot"),
    ("AoT", VENDOR_ROOT / "mods" / "aot"),
]

_vendor_populated = VENDOR_ROOT.is_dir() and any(root.is_dir() for _, root in _SOURCES_IN_LOAD_ORDER)

pytestmark = pytest.mark.skipif(not _vendor_populated, reason="vendor/ not populated locally")


def _script_entries():
    entries = []
    for name, root in _SOURCES_IN_LOAD_ORDER:
        base = root / "common" / "inline_scripts"
        if not base.is_dir():
            continue
        for f in sorted(base.rglob("*.txt")):
            rel = f.relative_to(base).with_suffix("")
            entries.append((str(rel).replace("\\", "/"), str(f), f.read_text(encoding="utf-8")))
    return entries


def _load_expanded(sub, scripts):
    result = []
    for name, root in _SOURCES_IN_LOAD_ORDER:
        d = root / "common" / sub
        if not d.is_dir():
            continue
        docs = []
        for f in sorted(d.glob("*.txt")):
            expanded, _report = expand_document(parse_file(f), scripts)
            docs.append(expanded)
        result.append((name, docs))
    return result


def _load_raw(sub):
    result = []
    for name, root in _SOURCES_IN_LOAD_ORDER:
        d = root / "common" / sub
        if not d.is_dir():
            continue
        docs = [parse_file(f) for f in sorted(d.glob("*.txt"))]
        result.append((name, docs))
    return result


def _has_tier_field(block) -> bool:
    return any(isinstance(item, Assignment) and item.key_name == "tier" for item in block.items)


@pytest.fixture(scope="module")
def real_layout_context():
    scripts = collect_scripts(_script_entries())
    tech_docs = _load_expanded("technology", scripts)
    tech_docs_raw = _load_raw("technology")
    var_docs = _load_expanded("scripted_variables", scripts)
    all_docs = [d for _, ds in tech_docs for d in ds] + [d for _, ds in var_docs for d in ds]
    variable_table = build_variable_table(all_docs)

    history = collect_technology_definitions(tech_docs)
    history_raw = collect_technology_definitions(tech_docs_raw)
    rendered_keys = rendered_technology_keys(history)
    rendered_defs = {k: history[k][-1] for k in rendered_keys}
    rendered_defs_raw = {k: history_raw[k][-1] for k in rendered_keys if k in history_raw}

    crisis = classify_crisis_factions(rendered_defs, load_crisis_overrides(), load_crisis_flag_overrides())

    technologies = {
        key: TechnologyLayoutInput(key=key, block=defn.block, faction=crisis[key])
        for key, defn in rendered_defs.items()
    }

    layout = compute_layout(technologies, variable_table, subgrid_width=DEFAULT_SUBGRID_WIDTH)
    return layout, rendered_defs, rendered_defs_raw, variable_table


@pytest.fixture(scope="module")
def real_layout(real_layout_context):
    return real_layout_context[0]


def test_every_rendered_node_gets_a_resolvable_tier_no_hard_failure(real_layout):
    # D-18 (spec/decisions.md): 980 -> 977, the depth-1 ACOT/AoT closure adopted this session --
    # 3 depth-2+ closure members (tech_dark_matter_power_core_enig, tech_mine_dark_energy,
    # tech_precursor_design) no longer render. See pipeline/rendering_scope.py and D-18 for the
    # full reasoning and the accepted 3-link off-tree-prerequisite cost.
    assert len(real_layout.nodes) == 977


def test_band_count_matches_survey(real_layout):
    # 10 declared-tier bands (T0-T9) + Repeatables, per CLAUDE.md's layout survey.
    assert len(real_layout.bands) == 11
    assert [b.band_id for b in real_layout.bands[:-1]] == list(range(10))
    assert real_layout.bands[-1].label == "Repeatables"


def test_all_eighteen_rows_present(real_layout):
    """D-16's row re-axis (spec/decisions.md): 13 derived category rows (grouped by AREA_ORDER,
    alphabetical within an area), then the 5 fixed crisis-faction rows in
    pipeline.crisis_faction.CRISIS_FACTIONS's own order. `row_ids` is the JSON contract's field
    name, unchanged -- see D-16 for why the rename to `rows`/`rowId` is deliberately NOT done this
    session."""
    assert real_layout.row_ids == [
        "computing", "field_manipulation", "particles",
        "archaeostudies", "biology", "military_theory", "new_worlds", "psionics", "statecraft",
        "industry", "materials", "propulsion", "voidcraft",
        "Aeternum", "Blokkats", "Compound", "Sirenalia", "Katzenartig Imperium",
    ]
    assert len(real_layout.row_ids) == 18


def test_densest_actual_row_band_cell_and_canvas_dimensions(real_layout):
    from collections import Counter

    cell_counts = Counter((n.row_id, n.band_id) for n in real_layout.nodes.values())
    densest_cell, densest_count = max(cell_counts.items(), key=lambda kv: kv[1])

    print(f"\n--- P-2/D-13/D-16 real layout ({DEFAULT_SUBGRID_WIDTH}-wide sub-grid) ---")
    print(f"canvas: {real_layout.canvas_width:,.0f}px wide x {real_layout.canvas_height:,.0f}px tall")
    print(f"densest (row, band) cell: {densest_cell} = {densest_count} nodes")

    # D-16's row re-axis (spec/decisions.md): Standard x T5 (253) no longer exists as a single
    # cell once the old Standard lane splits into 13 category rows -- the new densest cell is
    # voidcraft x T5 (47), since categories are inherently smaller buckets than "everyone who
    # isn't crisis content." Canvas grows from 12,544 x 8,146px to 12,888 x 10,800px: width grows
    # slightly from the widened INTER_BAND_GUTTER/INTRA_GAP_X gutter constants (D-16), height
    # grows substantially because rows are now individually sized to their own content instead of
    # one 925-technology Standard lane dominating. Height moved again, later session (10,708 ->
    # 10,800px): config/crisis_faction_overrides.txt's two new Compound entries
    # (tech_sm_autocannons, tech_qnm_disruptors) pull those two nodes out of the
    # particles/propulsion category rows into the Compound row, growing Compound's own row height
    # by more than it shrinks the two category rows it left -- densest cell and canvas width are
    # both unaffected, since neither node was ever in the densest voidcraft x T5 cell.
    #
    # Canvas grows again, this session (12,888 x 10,800 -> 13,632 x 11,608): a deliberate DEFECT-1
    # spacing increase, not a side effect -- INTRA_GAP_X/Y 16->24px and INTER_BAND_GUTTER 48->96px
    # (pipeline/layout.py's own comment), plus ROW_HEADER_HEIGHT 40->52px (DEFECT-4's chip/label
    # non-overlap fix, which also shifts every row's height since header height is part of it).
    # Densest cell is unaffected -- neither the sub-grid membership nor the row/band assignment
    # changed, only the pixel spacing between and around them.
    # Canvas height moved twice more in the Part-0 reconciliation session: first 11,608 ->
    # 11,492px (config/crisis_faction_flag_overrides.txt classifies tech_qnm_utilities Compound,
    # pulling it out of propulsion), then back up to 11,608px (12 more technology-key overrides in
    # config/crisis_faction_overrides.txt pull tech_qnm_utilities' 12 direct dependents out of
    # particles/propulsion into the now-much-larger Compound row -- Compound's row height grows by
    # more than particles/propulsion together shrink). Landing back at the pre-flag-map figure
    # (11,608px) is a coincidence of the specific pixel arithmetic, not evidence nothing changed --
    # per-row membership differs substantially (Compound 3 -> 15, particles 103 -> 96, propulsion
    # 50 -> 45). Densest cell/width unaffected throughout -- none of these 13 nodes was ever in the
    # voidcraft x T5 cell.
    assert densest_cell == ("voidcraft", 5)
    assert densest_count == 47
    # Canvas grows again, this session's Part-2 spacing pass (13,632 x 11,608 -> 14,160 x
    # 12,328): INTRA_GAP_X 24->40px (width, +16px per of the 3 intra-cell gaps per band =
    # 4 bands wide subgrid... measured directly, not hand-derived), ROW_GUTTER 24->48px, and the
    # new AREA_GROUP_GUTTER (96px, applied at exactly 3 group boundaries: computing->
    # archaeostudies, statecraft->industry, voidcraft->Aeternum) both add height. Densest cell is
    # unaffected -- pure spacing, no membership change.
    # Canvas height moved once more (12,328 -> 12,616): ROW_HEADER_HEIGHT 52->68px (Part-2's own
    # "add vertical space between the label and the first row of cards" fix), +16px x 18 rows.
    #
    # Canvas moved again, EAWAF/v1-routing session (14,160 x 12,616 -> 16,800 x 12,520): a
    # deliberate DEFECT-6 spacing increase, the fourth pass at this specific complaint --
    # INTRA_GAP_X 40->120px (width, +80px per of the 3 intra-cell gaps per band x 10 tier bands,
    # matches directly). AREA_GROUP_GUTTER 96->64px REDUCES height slightly (3 group boundaries x
    # -32px = -96px total), more than offsetting a few px of unrelated height drift elsewhere, so
    # canvas_height moves DOWN this session (12,616 -> 12,520) even though every other change this
    # session only adds height. Densest cell is unaffected -- pure spacing, no membership change.
    #
    # Canvas changed again, D-17 same-band-ordering session (16,800 x 12,520 -> 18,750 x 30,152):
    # `pipeline.layout._same_band_depth` + the column-is-depth change in `compute_layout` (see
    # `spec/decisions.md` D-17) enforce that a dependent's sub-column strictly exceeds its own
    # same-band prerequisite's sub-column. Width moved to 18,750px, matching the item-3 survey's
    # prediction (+11.6%) closely. Height's move to 30,152px (+141%) was NOT predicted by that
    # survey and was left unreconciled by that session -- a real defect, not an accepted cost:
    # `compute_layout`'s first implementation used `col = same_band_depth[key]` directly as the
    # sub-column, with same-depth members stacked in ONE column via an unbounded per-column
    # counter (no wrap at `subgrid_width` at all). The real corpus's worst cell (Blokkats x band 5
    # x depth 0) stacked 37 unrelated technologies in a single column, 37 sub-grid rows tall --
    # `tests/test_layout.py`'s own `test_unrelated_same_band_nodes_stack_in_one_column` (renamed
    # below) asserted this directly as intended behaviour, which is why no test caught it.
    #
    # Fixed in the following reconciliation session: depth still sets the MINIMUM sub-column a
    # node may occupy (the D-17 invariant is unaffected), but a depth is now a SLOT of one or more
    # sub-columns -- members sharing a depth wrap at `subgrid_width` (4) rows per column, spilling
    # into additional columns within their own depth's slot, exactly like the pre-D-17 wrap-at-N
    # behaviour did for an ordinary (row, band) cell. A deeper depth's slot starts strictly after
    # every shallower depth's own slot (cumulative sum of per-depth slot widths, each slot's width
    # being the widest wrap any ROW sharing that band needs at that depth -- columns are shared
    # across every row in a band since `same_band_depth` pools prerequisites across rows), so the
    # invariant still holds: a dependent's depth is strictly greater, so its slot start is past
    # every column its same-band prerequisite could ever use.
    #
    # Real measured result of the fix: canvas moves to **30,840 x 9,736** -- height drops far
    # below even the pre-D-17 figure (12,520px), confirming the stacking bug, not D-17 itself, was
    # the height driver; width grows well past the item-3 survey's 15,806-18,750px prediction,
    # because that survey assumed one column per depth LEVEL (chain length only) and did not
    # anticipate a depth level's own POPULATION also needing width once vertical stacking is
    # capped -- aligning columns across every row sharing a band means a population-heavy depth in
    # one row (e.g. Blokkats' 37-strong depth 0) reserves wrap-driven width that every other row
    # sharing the band inherits too, even though most other rows don't need it. This tradeoff
    # (bounded height, population-driven width) is the direct, examined consequence of the
    # wrap-within-depth rule chosen to fix the stacking bug -- not a rule chosen to hit any
    # particular width or height target.
    #
    # `subgrid_width` decision, D-17 (spec/decisions.md): the user picked 6 from the 4/6/8/12
    # trade-off survey the wrap-within-depth fix above prompted -- the only value that reduces
    # canvas width relative to 4 (29,670 vs 30,840) while ALSO fixing the aspect ratio (2.21:1 vs
    # 3.17:1). Canvas moves to **29,670 x 13,448** -- matches the survey's own projection exactly.
    # Densest cell/row population are unaffected (subgrid_width never changes membership, only
    # geometry).
    assert real_layout.canvas_width == 29670.0
    assert real_layout.canvas_height == 13448.0


def test_row_population_matches_survey(real_layout):
    """D-16: real per-row counts, over the 980-node rendered set. `blokkats` (Gigastructures' own
    technology category, 42/42 already Blokkats-faction by ID fragment) never appears as its own
    row -- confirming the derived-row-set mechanism excludes it without any special case.

    Compound is 15, not 0: config/crisis_faction_overrides.txt's 14 technology-key override
    entries (the original 2 bypass-flag entries plus 12 for tech_qnm_utilities' direct
    prerequisite dependents) move particles 104->96 and propulsion 52->45, and
    config/crisis_faction_flag_overrides.txt's flag-map entry (qnm_utilities_possible) classifies
    tech_qnm_utilities itself (one more node out of propulsion, on top of the override table's
    own 12).

    Sirenalia is 14, not 7, as of the EAWAF/Sirenalia correction session (see CLAUDE.md's
    defect-class entry and pipeline/crisis_faction.py's module docstring): 6 giga_tech_eawaf_*
    technologies join via config/crisis_faction_flag_overrides.txt's six new EAWAF entries
    (giga_tech_thaumaturgic_weaponry moves out of `particles`, 96->95; giga_tech_eawaf_
    disenchanter_1/2/3/4 and giga_tech_eawaf_weapons_repeatable move out of `psionics`, 34->28 for
    those five plus the sixth below), and 1 more (giga_tech_eawaf_psifusion, also `psionics`) joins
    via config/crisis_faction_overrides.txt's new technology-key entry -- 6 out of psionics total,
    34->28, plus 1 out of particles, 96->95."""
    from collections import Counter

    # D-18 (spec/decisions.md, this session): the depth-1 ACOT/AoT closure drops 3 previously-
    # rendered technologies (tech_dark_matter_power_core_enig, tech_mine_dark_energy,
    # tech_precursor_design), one each from `computing`, `field_manipulation` and `particles`
    # (83->82, 82->81, 95->94) -- confirmed directly, not assumed, by diffing the row-count table
    # against the pre-D-18 one. No other row is affected; total drops 980 -> 977.
    row_counts = Counter(n.row_id for n in real_layout.nodes.values())
    counts_by_row = {row_id: row_counts.get(row_id, 0) for row_id in real_layout.row_ids}
    assert counts_by_row == {
        "computing": 82, "field_manipulation": 81, "particles": 94,
        "archaeostudies": 24, "biology": 130, "military_theory": 43, "new_worlds": 49,
        "psionics": 28, "statecraft": 82,
        "industry": 70, "materials": 49, "propulsion": 45, "voidcraft": 123,
        "Aeternum": 3, "Blokkats": 42, "Compound": 15, "Sirenalia": 14, "Katzenartig Imperium": 3,
    }
    assert "blokkats" not in row_counts
    assert sum(row_counts.values()) == 977


def test_no_row_overlaps_and_every_card_within_its_own_row_bounds(real_layout):
    """Standing invariant, added after a real hard regression (screenshot-review session): the
    Item 4 vertical-centring fix (`pipeline/layout.py`'s `column_member_count`) originally keyed
    a per-column member count by `(row_id, col)` alone, and `col` is BAND-RELATIVE -- two
    different bands' columns landing on the same local index silently summed their counts into
    one dict entry, which could exceed the row's real max and drive the centring offset negative,
    shifting cards up into the row above. A green suite proved SELF-consistency at the time (every
    existing test still passed), not correctness against the actual geometric invariant that
    matters -- the same lesson D-17's unbounded-stacking bug already taught this project once.
    This test is the invariant that was missing: no two rows' card-occupied vertical extents may
    intersect, and (implied, but asserted directly rather than left implicit) no node's row index
    is ever negative. Real corpus, not a synthetic case -- `tests/test_layout.py`'s
    `test_no_row_overlaps_when_the_same_row_spans_multiple_bands` is the fast synthetic
    regression test for CI; this is the same invariant checked against the real vendored corpus's
    actual row/band shape, which is what actually caught the user-reported defect in the first
    place."""
    from pipeline.layout import CARD_HEIGHT

    for key, n in real_layout.nodes.items():
        assert n.row >= 0, f"{key}: row {n.row} is negative -- would overlap the row above"

    row_extent: dict[str, list[float]] = {}
    for n in real_layout.nodes.values():
        top, bottom = n.y, n.y + CARD_HEIGHT
        if n.row_id not in row_extent:
            row_extent[n.row_id] = [top, bottom]
        else:
            row_extent[n.row_id][0] = min(row_extent[n.row_id][0], top)
            row_extent[n.row_id][1] = max(row_extent[n.row_id][1], bottom)

    # Sorted-by-start with a running max-end, not merely pairwise-adjacent comparison -- a row
    # whose extent fully ENCLOSES a later, shorter row's extent would be missed by an
    # adjacent-only check (the enclosing row's own end is still the binding constraint for
    # everything after it, not just its immediate successor in sort order).
    items = sorted(row_extent.items(), key=lambda kv: kv[1][0])
    violations = []
    running_max_end = -float("inf")
    running_max_end_row = None
    for row_id, (start, end) in items:
        if start < running_max_end:
            violations.append((running_max_end_row, row_id, running_max_end, start))
        if end > running_max_end:
            running_max_end = end
            running_max_end_row = row_id
    assert not violations, f"row card-extent overlaps found: {violations}"


def test_edge_kind_breakdown_matches_survey(real_layout):
    """P-14: the full three-kind edge set, never a single 'edge count' number. 984 total =
    883 prerequisite + 76 alternative + 25 potential-gate (35 OR groups across 32 technologies).
    D-18 (this session): dropped from 989 = 888 + 76 + 25 -- the depth-1 ACOT/AoT closure change
    removes 5 prerequisite edges (each of the 3 dropped closure members' own inbound/outbound
    prerequisite edges to/from other rendered technologies), all from the `prerequisite` kind;
    `alternative`/`potential-gate` counts are unaffected since none of the 3 dropped technologies
    participated in an OR-group or a `potential`-gate relationship."""
    from collections import Counter

    kind_counts = Counter(e.kind for e in real_layout.edges)
    print(f"\nedge kind breakdown: {dict(kind_counts)}")
    assert dict(kind_counts) == {"prerequisite": 883, "alternative": 76, "potential-gate": 25}
    assert len(real_layout.edges) == 984

    alt_edges = [e for e in real_layout.edges if e.kind == "alternative"]
    assert len({e.group_id for e in alt_edges}) == 35
    assert len({e.to_key for e in alt_edges}) == 32
    assert all(e.group_id is not None for e in alt_edges)
    assert all(e.group_id is None for e in real_layout.edges if e.kind != "alternative")


def test_backward_edges_decomposed_by_kind_never_a_single_number(real_layout):
    """This figure has moved three times purely through re-scoping (27/891 -> 27/881 ->
    25 prerequisite + 2 alternative + 7 potential-gate = 34) -- recording it as one number is
    exactly what let it drift unnoticed each time. Recording the kind alongside the count is the
    fix: each kind's count is stable once its OWN scope is fixed, only the sum moved."""
    from collections import Counter

    backward = [e for e in real_layout.edges if e.backward]
    by_kind = Counter(e.kind for e in backward)
    print(f"\nbackward edges by kind: {dict(by_kind)} = {len(backward)} total")
    assert dict(by_kind) == {"prerequisite": 25, "alternative": 2, "potential-gate": 7}
    assert len(backward) == 34


def test_backward_span_per_kind_matches_survey(real_layout):
    """P-8's 'always 1-2 bands back' text describes prerequisite/alternative only (spec, reworded
    this session). potential-gate reaches up to 5 bands back -- a has_technology gate can
    reference any technology anywhere in the tree with no reason to sit near its owner's declared
    tier, unlike a formal prerequisite chain. band_span is emitted on every backward edge so a
    real Stage 3 routing decision can be made against this distribution, deliberately deferred
    rather than designed here (TODO(Stage 3), see pipeline.layout._route_edges)."""
    from collections import Counter

    backward = [e for e in real_layout.edges if e.backward]
    span_by_kind: dict[str, list[int]] = {}
    for e in backward:
        span_by_kind.setdefault(e.kind, []).append(e.band_span)

    assert dict(Counter(span_by_kind["prerequisite"])) == {1: 23, 2: 2}
    assert max(span_by_kind["prerequisite"]) == 2

    assert dict(Counter(span_by_kind["alternative"])) == {1: 1, 2: 1}
    assert max(span_by_kind["alternative"]) == 2

    assert dict(Counter(span_by_kind["potential-gate"])) == {1: 1, 2: 2, 3: 1, 4: 2, 5: 1}
    assert max(span_by_kind["potential-gate"]) == 5


def test_repeatable_membership_is_88_nodes_by_field_presence(real_layout_context):
    """Corrected membership rule (found against a user's v1 screenshot, not by any prior test):
    `levels` field PRESENT at all -- not `levels < 0` -- is what makes a technology repeatable.
    76 nodes declare `levels = -1` (unbounded); a further 12 declare a positive finite cap (5, 20,
    or 40) on the same `cost_per_level` shape. The old sign-only rule misclassified those 12,
    including `tech_repeatable_reduced_building_cost` ("Gravitational Analysis", the screenshot's
    "T5 x5" card) as an ordinary tier-banded node."""
    from collections import Counter

    _layout, rendered_defs, _rendered_defs_raw, variable_table = real_layout_context

    repeatable_keys = {k for k, defn in rendered_defs.items() if is_repeatable(defn.block, variable_table)}
    assert len(repeatable_keys) == 88

    def _levels_value(key):
        for item in rendered_defs[key].block.items:
            if isinstance(item, Assignment) and item.key_name == "levels":
                return item.value.value
        return None

    dist = Counter(_levels_value(k) for k in repeatable_keys)
    print(f"\nlevels distribution over the 88-node repeatable set: {dict(dist)}")
    assert dist == {-1: 76, 5: 5, 40: 4, 20: 3}

    assert "tech_repeatable_reduced_building_cost" in repeatable_keys


def test_inline_script_tier_group_is_proper_subset_of_repeatable_group(real_layout_context):
    """Guards against a future session conflating these two related-but-distinct sets: the 50
    `giga_tech_repeatable_*_cap` nodes (P-2's tier-source audit -- the ones whose `tier` field only
    exists after inline_script expansion) and the 88-node repeatable-membership set (this session's
    corrected `is_repeatable` rule). Every _cap node IS repeatable (they all declare `levels = -1`
    after expansion), so cap_keys is a PROPER SUBSET of repeatable_keys, not a disjoint-overlapping
    pair -- assert the subset relationship directly, not "neither is a subset of the other" (which
    fails against the real corpus: it IS a subset)."""
    _layout, rendered_defs, _rendered_defs_raw, variable_table = real_layout_context

    cap_keys = {k for k in rendered_defs if k.startswith("giga_tech_repeatable_") and k.endswith("_cap")}
    repeatable_keys = {k for k, defn in rendered_defs.items() if is_repeatable(defn.block, variable_table)}

    assert len(cap_keys) == 50
    assert len(repeatable_keys) == 88
    assert cap_keys.issubset(repeatable_keys)
    assert cap_keys != repeatable_keys


def test_repeatable_band_never_sources_an_edge(real_layout_context):
    """The sink property this session's routing simplifications depend on: every edge (of ANY of
    the three P-14 kinds) touching a repeatable node is non-repeatable -> repeatable, never the
    reverse and never repeatable -> repeatable. Verified directly over the full 984-edge P-14 set,
    not just prerequisite. 901 + 83 == 984 == 883 prerequisite + 76 alternative + 25
    potential-gate (the P-14 edge-kind breakdown -- see test_edge_kind_breakdown_matches_survey).
    D-18 (this session): dropped from 906 (pre-depth-1-closure) -- the 5 edges the depth-1 closure
    change removed (see test_edge_kind_breakdown_matches_survey) were all non-repeatable ->
    non-repeatable (none of the 3 dropped ACOT technologies is repeatable), so all 5 come off this
    bucket; the non-repeatable -> repeatable bucket (83) is unaffected."""
    layout, rendered_defs, _rendered_defs_raw, variable_table = real_layout_context

    repeatable_keys = {k for k, defn in rendered_defs.items() if is_repeatable(defn.block, variable_table)}

    both_nonrepeatable = [e for e in layout.edges if e.from_key not in repeatable_keys and e.to_key not in repeatable_keys]
    nonrep_to_rep = [e for e in layout.edges if e.from_key not in repeatable_keys and e.to_key in repeatable_keys]
    rep_to_nonrep = [e for e in layout.edges if e.from_key in repeatable_keys and e.to_key not in repeatable_keys]
    rep_to_rep = [e for e in layout.edges if e.from_key in repeatable_keys and e.to_key in repeatable_keys]

    assert len(rep_to_nonrep) == 0
    assert len(rep_to_rep) == 0
    assert len(both_nonrepeatable) == 901
    assert len(nonrep_to_rep) == 83
    assert len(both_nonrepeatable) + len(nonrep_to_rep) == len(layout.edges) == 984

    # A repeatable node can never source an edge at all (sink property), so it can never source a
    # backward edge either -- assert this directly rather than relying on it falling out of the
    # backward-edge count.
    assert all(not e.backward for e in layout.edges if e.from_key in repeatable_keys)
    backward_touching_repeatable = [e for e in layout.edges if e.backward and (e.from_key in repeatable_keys or e.to_key in repeatable_keys)]
    assert backward_touching_repeatable == []


def test_inline_script_only_tier_group_resolves_through_expansion(real_layout_context):
    """P-2 tier-source audit (CLAUDE.md's 'Tiers' section, HANDOFF.md's 'Measured layout facts'):
    50 of the 980 rendered nodes -- all `giga_tech_repeatable_*_cap`, from
    `giga_mega_repeatable.txt`'s inline_script template -- carry NO `tier` field on their raw,
    unexpanded block at all; they only gain one via inline_script expansion. These are exactly the
    nodes an expansion-ordering regression would silently strip a tier from, tripping
    UnresolvedTierError (or worse, resolving to nothing) -- a global '0 unresolved' count alone
    does not prove *these specific* nodes are the ones passing through expansion rather than being
    excluded, defaulted, or counted elsewhere. This test isolates the group directly."""
    _layout, rendered_defs, rendered_defs_raw, variable_table = real_layout_context

    only_via_expansion = [
        key
        for key in rendered_defs
        if _has_tier_field(rendered_defs[key].block)
        and (key not in rendered_defs_raw or not _has_tier_field(rendered_defs_raw[key].block))
    ]

    print(f"\nnodes with a tier ONLY after inline_script expansion: {len(only_via_expansion)}")

    # Membership: exactly the giga_tech_repeatable_*_cap family (P-2's tier-source audit), not an
    # approximation -- a size match alone wouldn't catch the group silently shifting to a
    # different set of nodes.
    assert set(only_via_expansion) == {
        key for key in rendered_defs if key.startswith("giga_tech_repeatable_") and key.endswith("_cap")
    }
    assert len(only_via_expansion) == 50

    # Every one resolves to a concrete integer tier post-expansion, and none raises
    # UnresolvedTierError -- the exact failure mode a regression in expansion ordering would hit.
    for key in only_via_expansion:
        tier = resolve_declared_tier(key, rendered_defs[key].block, variable_table)
        assert isinstance(tier, int)


def test_no_has_technology_under_allow_on_real_corpus(real_layout):
    """P-3's 'potential and allow' framing is aspirational -- `allow` never occurs on any
    rendered technology today (0/980, verified). This diagnostic exists so a future mod update
    that introduces one is surfaced, never silently out of scope."""
    assert real_layout.edge_diagnostics.has_technology_under_allow == []


def test_no_negated_potential_gate_on_real_corpus(real_layout):
    """Zero real has_technology-inside-NOT/NOR occurrences under `potential` today (verified).
    A future one would need a real representation (EdgeKind has none for a negative dependency);
    until then it's excluded from edge output and diagnosed rather than guessed at."""
    assert real_layout.edge_diagnostics.negated_potential_gate == []


def test_tech_ehof_sentient_tier_7_has_no_self_loop_edge(real_layout):
    """Regression guard for the real corpus case that found the scope-discipline requirement:
    tech_ehof_sentient_tier_7's own `potential` block nests
    `has_technology = tech_ehof_sentient_tier_7` inside `count_country = { limit = { OR = {...} }
    } }` -- checking OTHER empires in the galaxy for a scarcity mechanic, not the researching
    empire's own state. A naive unscoped recursive walk (an earlier draft of this survey) found a
    false self-loop here; pipeline.edges's scope discipline (matching
    pipeline.availability._evaluate_node's) must never descend into count_country looking for
    has_technology. Checked corpus-wide, not just for this one key: zero self-loop edges of any
    kind should exist anywhere in the real rendered graph."""
    self_loops = [e for e in real_layout.edges if e.from_key == e.to_key]
    assert self_loops == []

    tier_7_edges = [e for e in real_layout.edges if "tech_ehof_sentient_tier_7" in (e.from_key, e.to_key)]
    assert all(e.from_key != e.to_key for e in tier_7_edges)


def test_geometry_packs_without_error(real_layout):
    key_order = sorted(real_layout.nodes)
    node_bytes, node_ref = pack_node_positions(real_layout, key_order)
    edge_bytes, edge_ref, edge_index = pack_edge_polylines(real_layout)

    assert node_ref.length == len(key_order) * 2
    assert len(node_bytes) == node_ref.length * 4  # float32 = 4 bytes
    assert edge_ref.length == len(real_layout.edges) * 12
    assert len(edge_index) == len(real_layout.edges)
