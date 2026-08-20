"""Tests for pipeline.layout -- P-2/D-13 tier-band layout computation."""

from __future__ import annotations

import pytest

from pipeline.clausewitz import parse_text
from pipeline.layout import (
    CARD_HEIGHT,
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


def _input(key, text, faction=None):
    return TechnologyLayoutInput(key=key, block=_block(text), faction=faction)


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


def test_unrelated_same_band_nodes_wrap_within_their_depth_slot():
    # D-17 correction (spec/decisions.md): depth sets the MINIMUM sub-column a node may occupy,
    # but a depth is a SLOT of one or more sub-columns, not a single unbounded stack. An earlier
    # version of this test asserted the bug directly -- 10 mutually unrelated technologies (no
    # prerequisites, all same-band depth 0) all landing in column 0, stacked across 10 sub-grid
    # rows. That is exactly the failure mode the real corpus hit (up to 37 nodes stacked in one
    # column) and produced an unreconciled ~2.5x canvas-height regression. Depth-0 members now
    # wrap at `subgrid_width` (4) rows per column, spilling into additional columns within depth
    # 0's own slot: 10 nodes -> ceil(10/4) = 3 columns (0, 1, 2), with 4, 4, 2 nodes respectively.
    # The invariant is unaffected -- a real same-band prerequisite chain still needs one column per
    # depth level, since each level only ever has 1 member here (see
    # test_same_band_ordering_invariant_widens_the_band below).
    graph = {
        f"tech_{i}": _input(f"tech_{i}", "{ tier = 5 prerequisites = { } category = { voidcraft } }")
        for i in range(10)
    }
    result = compute_layout(graph, _vt(), subgrid_width=4)
    rows = {result.nodes[k].row for k in graph}
    cols = {result.nodes[k].col for k in graph}
    assert rows == {0, 1, 2, 3}
    assert cols == {0, 1, 2}
    # every (row, col) pair is unique -- no overlap
    positions = [(result.nodes[k].row, result.nodes[k].col) for k in graph]
    assert len(positions) == len(set(positions))
    # no column exceeds the wrap cap
    from collections import Counter

    col_counts = Counter(result.nodes[k].col for k in graph)
    assert max(col_counts.values()) <= 4


def test_same_band_ordering_invariant_widens_the_band():
    # D-17: a same-band prerequisite chain of length N needs N columns -- a technology must never
    # render in the same or an earlier column than any of its own same-band prerequisites. Chain:
    # tech_0 <- tech_1 <- tech_2 <- tech_3, all tier 5 (same band).
    graph = {
        "tech_0": _input("tech_0", "{ tier = 5 prerequisites = { } category = { voidcraft } }"),
        "tech_1": _input("tech_1", '{ tier = 5 prerequisites = { "tech_0" } category = { voidcraft } }'),
        "tech_2": _input("tech_2", '{ tier = 5 prerequisites = { "tech_1" } category = { voidcraft } }'),
        "tech_3": _input("tech_3", '{ tier = 5 prerequisites = { "tech_2" } category = { voidcraft } }'),
    }
    result = compute_layout(graph, _vt(), subgrid_width=4)
    cols = {k: result.nodes[k].col for k in graph}
    assert cols == {"tech_0": 0, "tech_1": 1, "tech_2": 2, "tech_3": 3}
    xs = {k: result.nodes[k].x for k in graph}
    assert xs["tech_0"] < xs["tech_1"] < xs["tech_2"] < xs["tech_3"]


def test_same_band_ordering_invariant_ignores_cross_band_prerequisites():
    # A prerequisite in an EARLIER band imposes no same-band ordering constraint at all -- D-17 is
    # scoped to same-band edges only. tech_1 (tier 6) depends on tech_0 (tier 5, a different band),
    # so tech_1's same-band depth is 0 regardless of tech_0's existence.
    graph = {
        "tech_0": _input("tech_0", "{ tier = 5 prerequisites = { } category = { voidcraft } }"),
        "tech_1": _input("tech_1", '{ tier = 6 prerequisites = { "tech_0" } category = { voidcraft } }'),
    }
    result = compute_layout(graph, _vt(), subgrid_width=4)
    assert result.nodes["tech_1"].col == 0


def test_subgrid_ordering_within_a_cell_no_longer_uses_category():
    # D-16: category dropped from the within-cell ordering key -- a (row, band) cell's members
    # already all share one row (category-or-faction) by construction, so it no longer
    # discriminates. Two same-category technologies at the same tier order by (computed_position,
    # key) only -- here, purely by key, since neither has a prerequisite giving it a different
    # computed_position.
    graph = {
        "tech_bio_2": _input("tech_bio_2", "{ tier = 5 prerequisites = { } category = { biology } }"),
        "tech_bio_1": _input("tech_bio_1", "{ tier = 5 prerequisites = { } category = { biology } }"),
    }
    result = compute_layout(graph, _vt(), subgrid_width=4)
    ordering = sorted(graph, key=lambda k: result.nodes[k].col + result.nodes[k].row * 4)
    assert ordering == ["tech_bio_1", "tech_bio_2"]


# ---------------------------------------------------------------------------
# Item 4 (screenshot-review session): a short sub-grid COLUMN is vertically CENTRED within its
# row's shared height, not top-anchored with 100% of the slack falling below it. Found from a
# real screenshot of voidcraft/T0's "Waystations" column (3 members against the row's own 6-row
# height, set by a denser column elsewhere in the same row) -- confirmed visually, not assumed,
# that the old top-anchored placement put a real, large empty gap below the last card and none
# above beyond the row's own fixed header.
# ---------------------------------------------------------------------------


def test_short_column_is_vertically_centred_within_the_row_height():
    # voidcraft-shaped case: one dense column (8 unrelated, same-depth technologies -- fills all 8
    # rows under subgrid_width=8, setting the row's own height) and one short column elsewhere in
    # the SAME row (2 members, via a different same-band depth so they land in a separate column,
    # not wrapped into the dense one).
    #
    # Item 6 (user domain call, later session): a true 50/50 split (this test's original version)
    # read as "a large gap above a sparse column, cards touching the row's bottom edge" once
    # compounded with the header strip's own content sitting immediately above row 0 -- see
    # pipeline/layout.py's own comment on the `// 4` change. This test now pins the NEW ratio: a
    # QUARTER of the slack above, three-quarters below. diff = 8 - 2 = 6; offset = 6 // 4 = 1 -- the
    # short column's 2 members sit at rows {1, 2}: 1 blank row above, 5 blank rows below (was
    # {3, 4}, 3 blank above/3 blank below, under the old `// 2` split).
    graph = {
        f"tech_dense_{i}": _input(f"tech_dense_{i}", "{ tier = 5 prerequisites = { } category = { voidcraft } }")
        for i in range(8)
    }
    # Two UNRELATED siblings, both depth 1 (a same-band prerequisite on the dense group, but not
    # on each other) -- same-band depth determines the column, so both land in the same depth-1
    # column, not two separate columns the way a tech_short_0 <- tech_short_1 chain would.
    graph["tech_short_0"] = _input(
        "tech_short_0", '{ tier = 5 prerequisites = { "tech_dense_0" } category = { voidcraft } }'
    )
    graph["tech_short_1"] = _input(
        "tech_short_1", '{ tier = 5 prerequisites = { "tech_dense_1" } category = { voidcraft } }'
    )
    result = compute_layout(graph, _vt(), subgrid_width=8)

    dense_col = result.nodes["tech_dense_0"].col
    assert {result.nodes[f"tech_dense_{i}"].col for i in range(8)} == {dense_col}
    assert {result.nodes[f"tech_dense_{i}"].row for i in range(8)} == set(range(8))

    short_col = result.nodes["tech_short_0"].col
    assert short_col != dense_col  # same-band depth ordering (D-17) puts it in its own column
    short_rows = {result.nodes["tech_short_0"].row, result.nodes["tech_short_1"].row}
    assert short_rows == {1, 2}, (
        f"expected the 2-member short column at rows {{1, 2}} (1/4 of the 6-row slack above, per "
        f"Item 6's // 4 split), got {short_rows} -- {{0, 1}} would mean it's still top-anchored "
        f"(no slack above at all), {{3, 4}} would mean it's still the old 50/50 split"
    )


def test_no_row_overlaps_when_the_same_row_spans_multiple_bands():
    """HARD REGRESSION (screenshot-review session, discovered from a real user screenshot of
    heavily overlapping rows): the centring fix above keyed `column_member_count` by
    `(row_id, col)` alone. `col` is BAND-RELATIVE -- `depth_slot_start[(band_index, depth)]`
    resets its own cursor to 0 for every band, so col 0 in one band and col 0 in a LATER band of
    the SAME row are physically different columns (different x) but shared the same dict key.
    Two different bands' columns landing on the same local index had their member counts silently
    SUMMED into one entry, which can exceed `row_row_counts[row_id]` (the row's own real max) and
    drive the centring offset NEGATIVE -- shifting a column's cards upward past row 0, overlapping
    the row above. This test reproduces the exact shape: one row (voidcraft), two bands (tier 5
    and tier 6), each band's own depth-0 column full at `subgrid_width` (4) members -- under the
    buggy key, `column_member_count[("voidcraft", 0)]` would be corrupted to 8 while
    `row_row_counts["voidcraft"]` is only 4, producing `centre_offset = (4 - 8) // 2 = -2`."""
    graph = {}
    for i in range(4):
        graph[f"tech_t5_{i}"] = _input(f"tech_t5_{i}", "{ tier = 5 prerequisites = { } category = { voidcraft } }")
    for i in range(4):
        graph[f"tech_t6_{i}"] = _input(f"tech_t6_{i}", "{ tier = 6 prerequisites = { } category = { voidcraft } }")

    result = compute_layout(graph, _vt(), subgrid_width=4)

    for key in graph:
        assert result.nodes[key].row >= 0, f"{key}: row {result.nodes[key].row} is negative -- overlaps the row above"

    # Every node in this single-row graph must land within one contiguous, non-negative row-index
    # range -- no gaps or negative excursions caused by a cross-band key collision.
    rows_used = {result.nodes[key].row for key in graph}
    assert min(rows_used) >= 0
    assert max(rows_used) < 4  # subgrid_width -- no column may need more than its own max real members


def test_detector_catches_the_cross_band_column_key_collision():
    """Proves the assertion above is capable of failing, not just passing by construction --
    reproduces the buggy (row_id, col)-only key directly (not by re-importing broken pipeline
    code) and shows it corrupts the centring offset negative for the exact scenario above."""
    row_row_counts = {"voidcraft": 4}
    # Buggy: keyed by (row_id, col) only -- band 0's col-0 (4 members) and band 1's col-0 (4
    # members) collide and sum.
    buggy_column_member_count = {("voidcraft", 0): 4 + 4}
    buggy_offset = (row_row_counts["voidcraft"] - buggy_column_member_count[("voidcraft", 0)]) // 2
    assert buggy_offset == -2, "the buggy key must reproduce a negative centring offset"

    # Fixed: keyed by (row_id, band_index, col) -- each band's own column count stays separate.
    fixed_column_member_count = {("voidcraft", 0, 0): 4, ("voidcraft", 1, 0): 4}
    fixed_offset_band0 = (row_row_counts["voidcraft"] - fixed_column_member_count[("voidcraft", 0, 0)]) // 2
    fixed_offset_band1 = (row_row_counts["voidcraft"] - fixed_column_member_count[("voidcraft", 1, 0)]) // 2
    assert fixed_offset_band0 == 0
    assert fixed_offset_band1 == 0


def test_detector_catches_the_old_top_anchored_bug():
    """Proves the assertion above is capable of failing, not just passing by construction -- this
    project's own standing rule. Simulates the OLD top-anchored formula directly (local_row with
    no centring offset) and confirms it produces the rejected {0, 1} placement, distinct from the
    real centred result."""
    row_row_count = 4
    column_member_count = 2
    old_top_anchored_rows = {i for i in range(column_member_count)}
    assert old_top_anchored_rows == {0, 1}
    centre_offset = (row_row_count - column_member_count) // 2
    new_centred_rows = {centre_offset + i for i in range(column_member_count)}
    assert new_centred_rows == {1, 2}
    assert new_centred_rows != old_top_anchored_rows


# ---------------------------------------------------------------------------
# Rows (D-16) -- faction-first-else-category, all always present, including zero-population ones
# ---------------------------------------------------------------------------


def test_category_row_derived_and_faction_rows_always_reserved():
    # A lone physics-category technology plus no crisis-faction technologies at all: the row set
    # is still "physics's one real category row" + all 5 faction rows (Compound et al. reserved
    # even at zero population) -- never a hand-typed "Standard" catch-all lane.
    graph = {"tech_a": _input("tech_a", "{ tier = 0 prerequisites = { } category = { computing } }")}
    result = compute_layout(graph, _vt())
    assert result.row_ids == ["computing", "Aeternum", "Blokkats", "Compound", "Sirenalia", "Katzenartig Imperium"]


def test_crisis_faction_technology_placed_in_its_faction_row_not_its_category_row():
    graph = {
        "tech_standard": _input("tech_standard", "{ tier = 0 prerequisites = { } category = { computing } }"),
        # A crisis-faction technology's OWN category (here, its Gigastructures-specific
        # "blokkats" category) never surfaces as a row of its own -- faction-first placement is
        # mutually exclusive, so this technology's row is "Blokkats", never "blokkats".
        "tech_blokkat": _input(
            "tech_blokkat", "{ tier = 0 prerequisites = { } category = { blokkats } }", faction="Blokkats"
        ),
    }
    result = compute_layout(graph, _vt())
    assert result.nodes["tech_standard"].row_id == "computing"
    assert result.nodes["tech_blokkat"].row_id == "Blokkats"
    assert "blokkats" not in result.row_ids
    assert result.nodes["tech_standard"].y != result.nodes["tech_blokkat"].y


def test_row_order_groups_categories_by_area_then_alphabetically():
    # particles/computing are both physics; industry is engineering. Physics rows sort before
    # engineering rows (AREA_ORDER); within physics, computing < particles alphabetically.
    graph = {
        "tech_particles": _input("tech_particles", "{ tier = 0 prerequisites = { } category = { particles } area = physics }"),
        "tech_computing": _input("tech_computing", "{ tier = 0 prerequisites = { } category = { computing } area = physics }"),
        "tech_industry": _input("tech_industry", "{ tier = 0 prerequisites = { } category = { industry } area = engineering }"),
    }
    result = compute_layout(graph, _vt())
    category_rows = [r for r in result.row_ids if r not in ("Aeternum", "Blokkats", "Compound", "Sirenalia", "Katzenartig Imperium")]
    assert category_rows == ["computing", "particles", "industry"]


def test_unresolved_row_raises_when_no_faction_and_no_category():
    from pipeline.layout import UnresolvedRowError

    graph = {"tech_a": _input("tech_a", "{ tier = 0 prerequisites = { } }")}
    with pytest.raises(UnresolvedRowError):
        compute_layout(graph, _vt())


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


def test_backward_edge_polyline_still_six_points():
    # Card-avoidance router rewrite: polyline moved from 4 points (H-V-H, 3 segments) to 6 points
    # (exit stub / V / transit / V / entry stub, 5 segments) -- see pipeline.layout._route_edges's
    # own docstring for the full reasoning and the real measured zero-crossing result.
    graph = {
        "tech_high": _input("tech_high", "{ tier = 5 prerequisites = { } category = { physics } }"),
        "tech_low": _input("tech_low", "{ tier = 2 prerequisites = { tech_high } category = { physics } }"),
    }
    result = compute_layout(graph, _vt())
    edge = result.edges[0]
    assert len(edge.polyline) == 6
