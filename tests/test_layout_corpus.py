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

    crisis = classify_crisis_factions(rendered_defs, load_crisis_overrides())

    technologies = {
        key: TechnologyLayoutInput(key=key, block=defn.block, lane=crisis[key])
        for key, defn in rendered_defs.items()
    }

    layout = compute_layout(technologies, variable_table, subgrid_width=DEFAULT_SUBGRID_WIDTH)
    return layout, rendered_defs, rendered_defs_raw, variable_table


@pytest.fixture(scope="module")
def real_layout(real_layout_context):
    return real_layout_context[0]


def test_every_rendered_node_gets_a_resolvable_tier_no_hard_failure(real_layout):
    assert len(real_layout.nodes) == 980


def test_band_count_matches_survey(real_layout):
    # 10 declared-tier bands (T0-T9) + Repeatables, per CLAUDE.md's layout survey.
    assert len(real_layout.bands) == 11
    assert [b.band_id for b in real_layout.bands[:-1]] == list(range(10))
    assert real_layout.bands[-1].label == "Repeatables"


def test_all_six_lanes_present(real_layout):
    assert real_layout.lane_ids == [
        "Standard", "Aeternum", "Blokkats", "Compound", "Sirenalia", "Katzenartig Imperium",
    ]


def test_densest_actual_band_cell_and_canvas_dimensions(real_layout):
    from collections import Counter

    cell_counts = Counter((n.lane_id, n.band_id) for n in real_layout.nodes.values())
    densest_cell, densest_count = max(cell_counts.items(), key=lambda kv: kv[1])

    print(f"\n--- P-2/D-13 real layout ({DEFAULT_SUBGRID_WIDTH}-wide sub-grid) ---")
    print(f"canvas: {real_layout.canvas_width:,.0f}px wide x {real_layout.canvas_height:,.0f}px tall")
    print(f"densest (lane, band) cell: {densest_cell} = {densest_count} nodes")

    # Standard x T5 = 253 under the corrected repeatable-membership rule (was 261 under the old
    # levels<0-only rule -- some of the 12 newly-recognised finite-level repeatables were in the
    # Standard lane at declared T5 and moved out of this cell into the Repeatables band).
    #
    # This test doubles as the P-14 OR-vs-AND fix's explicit invariant check (decision 5):
    # excluding alternative-branch members from ordered_prerequisites() shifts internal
    # computed_position for ~142 nodes, but bands are declared tier and computed_position only
    # orders WITHIN a band -- so this densest-cell count and the canvas dimensions below MUST be
    # unchanged by that fix. Verified: both are identical to the pre-fix figures. If either had
    # moved, that would mean band assignment secretly depended on computed position -- v1's bug
    # class -- and this test would have caught it.
    assert densest_cell == ("Standard", 5)
    assert densest_count == 253


def test_edge_kind_breakdown_matches_survey(real_layout):
    """P-14: the full three-kind edge set, never a single 'edge count' number. 989 total =
    888 prerequisite + 76 alternative + 25 potential-gate (35 OR groups across 32 technologies).
    This is the reconciliation against the previous session's 964 = 888 (true prerequisite) + 76
    (alternative, previously flattened into the same 'prerequisite' figure) -- nothing drifted,
    the count decomposed. 964 + 25 potential-gate (not counted at all before this session) = 989."""
    from collections import Counter

    kind_counts = Counter(e.kind for e in real_layout.edges)
    print(f"\nedge kind breakdown: {dict(kind_counts)}")
    assert dict(kind_counts) == {"prerequisite": 888, "alternative": 76, "potential-gate": 25}
    assert len(real_layout.edges) == 989

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
    reverse and never repeatable -> repeatable. Verified directly over the full 989-edge P-14 set,
    not just prerequisite. 906 + 83 == 989 == 888 prerequisite + 76 alternative + 25
    potential-gate (the P-14 edge-kind breakdown -- see test_edge_kind_breakdown_matches_survey).
    (Historical note: the prerequisite-only figure from the previous session, 881, undercounts
    here because 906 sums each kind's own non-repeatable-to-non-repeatable count including the 4
    pairs that are both a prerequisite and a potential-gate edge -- two distinct TypedEdge records
    for the same (from, to) pair, per P-14's 'kind membership is not mutually exclusive' rule.)"""
    layout, rendered_defs, _rendered_defs_raw, variable_table = real_layout_context

    repeatable_keys = {k for k, defn in rendered_defs.items() if is_repeatable(defn.block, variable_table)}

    both_nonrepeatable = [e for e in layout.edges if e.from_key not in repeatable_keys and e.to_key not in repeatable_keys]
    nonrep_to_rep = [e for e in layout.edges if e.from_key not in repeatable_keys and e.to_key in repeatable_keys]
    rep_to_nonrep = [e for e in layout.edges if e.from_key in repeatable_keys and e.to_key not in repeatable_keys]
    rep_to_rep = [e for e in layout.edges if e.from_key in repeatable_keys and e.to_key in repeatable_keys]

    assert len(rep_to_nonrep) == 0
    assert len(rep_to_rep) == 0
    assert len(both_nonrepeatable) == 906
    assert len(nonrep_to_rep) == 83
    assert len(both_nonrepeatable) + len(nonrep_to_rep) == len(layout.edges) == 989

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
    assert edge_ref.length == len(real_layout.edges) * 8
    assert len(edge_index) == len(real_layout.edges)
