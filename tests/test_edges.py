"""Tests for pipeline.edges -- P-14 full three-kind edge typing."""

from __future__ import annotations

from pipeline.clausewitz import parse_text
from pipeline.edges import (
    EdgeExtractionDiagnostics,
    compute_typed_edges,
    extract_alternative_edges,
    extract_potential_gate_edges,
    extract_prerequisite_edges,
)
def _block(text: str):
    doc = parse_text(f"tech_x = {text}\n", path="x.txt")
    return doc.items[0].value


# ---------------------------------------------------------------------------
# prerequisite / alternative extraction
# ---------------------------------------------------------------------------


def test_extract_prerequisite_edges_true_prerequisites_only():
    block = _block("{ prerequisites = { tech_a tech_b } }")
    edges = extract_prerequisite_edges("tech_x", block)
    assert {(e.from_key, e.to_key, e.kind) for e in edges} == {
        ("tech_a", "tech_x", "prerequisite"),
        ("tech_b", "tech_x", "prerequisite"),
    }


def test_extract_prerequisite_edges_excludes_or_members():
    block = _block("{ prerequisites = { tech_a OR = { tech_b tech_c } } }")
    edges = extract_prerequisite_edges("tech_x", block)
    assert {(e.from_key, e.to_key) for e in edges} == {("tech_a", "tech_x")}


def test_extract_alternative_edges_assigns_group_id():
    block = _block("{ prerequisites = { OR = { tech_b tech_c } } }")
    edges = extract_alternative_edges("tech_x", block)
    assert len(edges) == 2
    assert all(e.kind == "alternative" for e in edges)
    assert all(e.to_key == "tech_x" for e in edges)
    assert {e.from_key for e in edges} == {"tech_b", "tech_c"}
    group_ids = {e.group_id for e in edges}
    assert group_ids == {"tech_x#alt0"}


def test_extract_alternative_edges_two_groups_get_distinct_ids():
    block = _block("{ prerequisites = { OR = { tech_a tech_b } OR = { tech_c tech_d } } }")
    edges = extract_alternative_edges("tech_x", block)
    by_group: dict[str, set[str]] = {}
    for e in edges:
        by_group.setdefault(e.group_id, set()).add(e.from_key)
    assert by_group == {"tech_x#alt0": {"tech_a", "tech_b"}, "tech_x#alt1": {"tech_c", "tech_d"}}


# ---------------------------------------------------------------------------
# potential-gate extraction -- scope discipline
# ---------------------------------------------------------------------------


def test_extract_potential_gate_edges_direct_has_technology():
    block = _block("{ potential = { has_technology = tech_a } }")
    diagnostics = EdgeExtractionDiagnostics()
    edges = extract_potential_gate_edges("tech_x", block, diagnostics)
    assert [(e.from_key, e.to_key, e.kind) for e in edges] == [("tech_a", "tech_x", "potential-gate")]


def test_extract_potential_gate_edges_descends_into_or_and_and():
    block = _block("{ potential = { OR = { has_technology = tech_a AND = { has_technology = tech_b } } } }")
    diagnostics = EdgeExtractionDiagnostics()
    edges = extract_potential_gate_edges("tech_x", block, diagnostics)
    assert {e.from_key for e in edges} == {"tech_a", "tech_b"}


def test_extract_potential_gate_edges_boolean_wrappers_are_case_insensitive():
    # Real corpus shape (giga_mega_repeatable.txt's inline_script template, 50 rendered nodes):
    # `not = { has_global_flag = ... }` lowercase, alongside a bare has_global_flag leaf. Matching
    # only uppercase would silently treat the lowercase wrapper as an opaque leaf -- exactly the
    # same failure mode this module's scope discipline exists to avoid for count_country, just
    # from the other direction (an unrecognised wrapper, not an over-eager descent).
    block = _block("{ potential = { not = { has_technology = tech_a } or = { has_technology = tech_b } } }")
    diagnostics = EdgeExtractionDiagnostics()
    edges = extract_potential_gate_edges("tech_x", block, diagnostics)
    # tech_a is inside `not`, so it's a negated dependency -- excluded from edges, diagnosed.
    assert [(e.from_key, e.kind) for e in edges] == [("tech_b", "potential-gate")]
    assert diagnostics.negated_potential_gate == [("tech_a", "tech_x")]


def test_extract_potential_gate_edges_negated_is_excluded_and_diagnosed():
    block = _block("{ potential = { NOT = { has_technology = tech_a } } }")
    diagnostics = EdgeExtractionDiagnostics()
    edges = extract_potential_gate_edges("tech_x", block, diagnostics)
    assert edges == []
    assert diagnostics.negated_potential_gate == [("tech_a", "tech_x")]


def _naive_unscoped_has_technology_walk(node) -> list[str]:
    """Reproduces the earlier, WRONG draft's extraction: recurse into every block-valued
    assignment unconditionally, not just AND/OR/NOT/NOR wrappers. Used only here, as a mutation-
    style proof that the count_country regression guard is a real detector and not a vacuous
    "no edge happened to appear" assertion -- HANDOFF.md's standing rule: a clean run means
    nothing until the detector is shown capable of a non-clean one. Mirrors the round-trip
    mutation harness's pattern (tests/clausewitz/test_roundtrip_detects_mutations.py)."""
    from pipeline.clausewitz.nodes import Assignment as _Assignment
    from pipeline.clausewitz.nodes import Block as _Block

    found = []
    if isinstance(node, _Block):
        for item in node.items:
            if isinstance(item, _Assignment):
                if item.key_name == "has_technology":
                    target = item.value.name if hasattr(item.value, "name") else item.value.value
                    found.append(target)
                found.extend(_naive_unscoped_has_technology_walk(item.value))
    return found


def test_naive_unscoped_walk_would_have_produced_the_false_self_loop():
    """Proves the count_country regression guard is a real detector, not vacuous: the naive
    unscoped walker (reproduced above, matching the earlier wrong draft) DOES find
    has_technology=tech_x inside count_country's limit scope on this fixture and would emit a
    false self-loop edge if used -- exactly the failure mode
    test_count_country_nested_has_technology_does_not_produce_an_edge guards against. If this
    assertion ever started failing, the guard test below would no longer be testing anything."""
    block = _block(
        "{ potential = { "
        "count_country = { limit = { OR = { has_technology = tech_x } } } "
        "} }"
    )
    potential = block.items[0].value
    naive_hits = _naive_unscoped_has_technology_walk(potential)
    assert naive_hits == ["tech_x"]  # the false self-loop the scoped walker must NOT produce


def test_count_country_nested_has_technology_does_not_produce_an_edge():
    """Regression guard for the real corpus case (tech_ehof_sentient_tier_7): a has_technology
    check nested inside count_country's limit scope is checking OTHER empires in the galaxy for a
    scarcity mechanic, not the researching empire's own state. A naive unscoped recursive walk
    (an earlier draft of this survey) found a false self-loop here. The scope-disciplined walker
    must never descend into count_country -- or any other non-boolean-wrapper block -- looking for
    has_technology."""
    block = _block(
        "{ potential = { "
        "count_country = { limit = { OR = { has_technology = tech_x } } } "
        "} }"
    )
    diagnostics = EdgeExtractionDiagnostics()
    edges = extract_potential_gate_edges("tech_x", block, diagnostics)
    assert edges == []  # in particular, no self-loop (tech_x -> tech_x)
    assert diagnostics.negated_potential_gate == []


def test_weight_modifier_has_technology_is_not_a_potential_gate_edge():
    # has_technology inside weight_modifier affects research priority weighting, not
    # availability -- it must never produce a potential-gate edge.
    block = _block("{ weight_modifier = { factor = 2 has_technology = tech_a } potential = { } }")
    diagnostics = EdgeExtractionDiagnostics()
    edges = extract_potential_gate_edges("tech_x", block, diagnostics)
    assert edges == []


def test_has_technology_under_allow_is_diagnosed_not_extracted_as_an_edge():
    block = _block("{ potential = { } allow = { has_technology = tech_a } }")
    diagnostics = EdgeExtractionDiagnostics()
    edges = extract_potential_gate_edges("tech_x", block, diagnostics)
    assert edges == []
    assert diagnostics.has_technology_under_allow == ["tech_x"]


def test_no_allow_field_produces_no_diagnostic():
    block = _block("{ potential = { has_technology = tech_a } }")
    diagnostics = EdgeExtractionDiagnostics()
    extract_potential_gate_edges("tech_x", block, diagnostics)
    assert diagnostics.has_technology_under_allow == []


# ---------------------------------------------------------------------------
# compute_typed_edges -- full assembly
# ---------------------------------------------------------------------------


def test_compute_typed_edges_assembles_all_three_kinds():
    defs = {
        "tech_a": _block("{ prerequisites = { } }"),
        "tech_b": _block(
            "{ prerequisites = { tech_a OR = { tech_c tech_d } } potential = { has_technology = tech_a } }",
        ),
        "tech_c": _block("{ prerequisites = { } }"),
        "tech_d": _block("{ prerequisites = { } }"),
    }
    edges, diagnostics = compute_typed_edges(defs)
    kinds = {e.kind for e in edges}
    assert kinds == {"prerequisite", "alternative", "potential-gate"}
    assert ("tech_a", "tech_b", "prerequisite") in {(e.from_key, e.to_key, e.kind) for e in edges}
    assert ("tech_a", "tech_b", "potential-gate") in {(e.from_key, e.to_key, e.kind) for e in edges}
    assert diagnostics.has_technology_under_allow == []
    assert diagnostics.negated_potential_gate == []


def test_compute_typed_edges_drops_edges_with_endpoint_outside_rendered_set():
    defs = {
        "tech_a": _block("{ prerequisites = { tech_outside } }"),
    }
    edges, _diagnostics = compute_typed_edges(defs)
    assert edges == []


def test_compute_typed_edges_a_pair_can_be_both_prerequisite_and_potential_gate():
    # Edge-kind membership is NOT mutually exclusive per (from, to) pair -- both must be emitted.
    defs = {
        "tech_a": _block("{ prerequisites = { } }"),
        "tech_b": _block(
            "{ prerequisites = { tech_a } potential = { has_technology = tech_a } }"
        ),
    }
    edges, _diagnostics = compute_typed_edges(defs)
    pairs_by_kind = {(e.from_key, e.to_key): [] for e in edges}
    for e in edges:
        pairs_by_kind[(e.from_key, e.to_key)].append(e.kind)
    assert sorted(pairs_by_kind[("tech_a", "tech_b")]) == ["potential-gate", "prerequisite"]
