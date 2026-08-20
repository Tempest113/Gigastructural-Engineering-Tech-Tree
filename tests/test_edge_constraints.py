"""Synthetic mechanism tests for pipeline.edge_constraints -- see that module's own docstring for
the algorithm and the corrected axis-fact-only definition of "active" (sensitivity was rejected;
these tests exist specifically to prove the rejected approach WOULD have failed the Disco Moon
case, and that the shipped approach doesn't)."""

from __future__ import annotations

from dataclasses import dataclass

from pipeline.clausewitz import parse_text
from pipeline.dataset_schema.empire_profile import all_profiles_in_canonical_order
from pipeline.edge_constraints import (
    _edge_active_per_profile,
    _field,
    _fit_rectangle,
    compute_potential_gate_constraints,
    edge_active_for_profile,
)

PROFILES = all_profiles_in_canonical_order()


def _potential_block(text: str):
    doc = parse_text(f"tech_x = {{ potential = {text} }}\n", path="x.txt")
    block = doc.items[0].value
    return _field(block, "potential").value


@dataclass(frozen=True)
class _FakeDef:
    block: object


@dataclass(frozen=True)
class _FakeEdge:
    from_key: str
    to_key: str
    kind: str
    group_id: str | None = None


def test_unconstrained_edge_is_active_for_all_twelve_profiles():
    pot = _potential_block("{ has_technology = tech_a }")
    active = _edge_active_per_profile(pot, "tech_a", PROFILES)
    assert active == [True] * 12


def test_or_sibling_axis_fact_masks_the_edge_for_matching_profiles():
    """nomadic=yes already satisfies the OR for nomadic profiles -- the has_technology leaf's
    value never matters there."""
    pot = _potential_block("{ OR = { is_nomadic = yes has_technology = tech_a } }")
    active = _edge_active_per_profile(pot, "tech_a", PROFILES)
    for p, a in zip(PROFILES, active):
        assert a == (p["nomadic"] == "no"), p


def test_unresolvable_and_sibling_does_not_mask_the_edge():
    """The corrected criterion's whole point, isolated to a minimal synthetic case: an AND-sibling
    this evaluator cannot resolve (not an axis fact, not DLC/ground/mod-config) must NOT suppress
    a real has_technology dependency -- only an axis fact may do that."""
    pot = _potential_block("{ some_unmodeled_civic_check = yes has_technology = tech_a }")
    active = _edge_active_per_profile(pot, "tech_a", PROFILES)
    assert active == [True] * 12  # never masked, unlike the rejected sensitivity approach


def test_sensitivity_would_have_wrongly_reported_this_case_as_never_active():
    """Proves the REJECTED approach really would fail here -- i.e. this test file's corrected
    behaviour above is a real fix, not a no-op. Mirrors the exact Disco Moon shape: an AND of an
    unresolvable leaf with an OR containing the has_technology leaf."""
    from pipeline.availability import evaluate_trigger_block, _State

    pot = _potential_block(
        "{ some_unmodeled_civic_check = yes OR = { has_technology = tech_a has_valid_civic = whatever } }"
    )

    def naive_sensitivity(target, profiles):
        import pipeline.availability as av

        orig = av._evaluate_leaf

        def make(forced):
            def patched(assignment, profile):
                if assignment.key_name == "has_technology" and assignment.value.name == target:
                    return av._Eval(_State.TRUE if forced else _State.FALSE, None)
                return orig(assignment, profile)
            return patched

        out = []
        for profile in profiles:
            av._evaluate_leaf = make(True)
            r_true = evaluate_trigger_block(pot, profile)
            av._evaluate_leaf = make(False)
            r_false = evaluate_trigger_block(pot, profile)
            av._evaluate_leaf = orig
            out.append(r_true.state != r_false.state)
        return out

    naive_result = naive_sensitivity("tech_a", PROFILES)
    assert naive_result == [False] * 12  # the rejected approach: wrongly "never active"

    corrected_result = _edge_active_per_profile(pot, "tech_a", PROFILES)
    assert corrected_result == [True] * 12  # the shipped approach: correctly always active


def test_fit_rectangle_single_axis():
    active = [p["nomadic"] == "yes" for p in PROFILES]
    assert _fit_rectangle(PROFILES, active) == {"nomadic": ["yes"]}


def test_fit_rectangle_two_axis_intersection():
    active = [(p["authority"] != "machine_intelligence" and p["shipset"] == "biological") for p in PROFILES]
    assert _fit_rectangle(PROFILES, active) == {"authority": ["hive_mind", "regular"], "shipset": ["biological"]}


def test_fit_rectangle_all_active_returns_empty_constraint():
    assert _fit_rectangle(PROFILES, [True] * 12) == {}


def test_fit_rectangle_detects_a_non_rectangular_active_set():
    """Proves the detector can fail before trusting that every real corpus case fits a rectangle
    (this project's own standing rule) -- a synthetic active set that is NOT a product of
    per-axis subsets (an irregular diagonal-shaped selection) must not be silently forced into a
    wrong rectangle."""
    active = [(i % 5 == 0) for i in range(12)]  # arbitrary, not axis-aligned
    assert _fit_rectangle(PROFILES, active) is None


def test_edge_active_for_profile_matches_constraint():
    profile = {"authority": "regular", "shipset": "biological", "nomadic": "no"}
    assert edge_active_for_profile({}, profile) is True
    assert edge_active_for_profile(None, profile) is True
    assert edge_active_for_profile({"nomadic": ["yes"]}, profile) is False
    assert edge_active_for_profile({"shipset": ["biological"]}, profile) is True


def test_compute_potential_gate_constraints_keys_by_kind_not_just_from_to():
    """The real corpus regression this guards against: a (from_key, to_key) pair that is BOTH a
    prerequisite and a potential-gate edge must only carry the constraint on the gate edge."""
    owner_doc = parse_text("tech_y = { potential = { OR = { is_nomadic = yes has_technology = tech_a } } } \n")
    rendered_defs = {"tech_y": _FakeDef(block=owner_doc.items[0].value)}
    typed_edges = [
        _FakeEdge(from_key="tech_a", to_key="tech_y", kind="potential-gate"),
        _FakeEdge(from_key="tech_a", to_key="tech_y", kind="prerequisite"),
    ]
    result = compute_potential_gate_constraints(rendered_defs, typed_edges, PROFILES)
    assert result == {("tech_a", "tech_y", "potential-gate"): {"nomadic": ["no"]}}
    assert ("tech_a", "tech_y", "prerequisite") not in result
