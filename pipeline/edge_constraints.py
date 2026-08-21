"""P-14 follow-up: per-edge empire-type constraints for `potential-gate` edges (`Edge.
appliesToEmpireTypes`, `activeEdgeIds`) -- closes `dataset_emit.py`'s documented v1 scope
limitation ("`appliesToEmpireTypes` is emitted unconstrained on every edge").

**Scope: `potential-gate` only.** `prerequisite`/`alternative` edges are extracted from a
technology's `prerequisites` field, which is never evaluated as a trigger and contains only
technology references plus nested `OR` (0 `AND`/`NOT`/`NOR` occur there, corpus-confirmed) -- there
is no boolean context in which an axis fact could ever sit alongside one of those edges. Their
`appliesToEmpireTypes` stays `{}` (unconstrained) by construction, not by omission.

**The definition of "active", and why the obvious one (sensitivity) is wrong.** The naive approach
-- evaluate the owning technology's `potential` block with the edge's `has_technology` leaf forced
`TRUE` then `FALSE`, and call the edge "active for a profile" iff the two results differ -- looks
right but silently drops real structure. `giga_tech_disco_moon`'s `potential` has an AND-sibling
(`giga_can_use_habitables`) this evaluator cannot resolve (not an axis fact, not a DLC/ground fact,
not a mod-config-toggle flag). Kleene-`AND` needs an explicit `FALSE` to override an `UNKNOWN`
sibling, so the whole block evaluates `UNKNOWN` regardless of the tested leaf's value, for every
profile -- sensitivity reports both of Disco Moon's `has_technology` gate edges as "never active,"
which would make the pipeline stop emitting real dependency structure (Disco Moon genuinely does
require Autocurating Vault or Transcendent Faith) purely because an UNRELATED fact is undecidable.
**"We don't know" is not the same fact as "doesn't apply" -- conflating them was the actual defect
in the first survey pass of this feature, caught by a human review of the Disco Moon case before
this module was written, not by any test.** Only an axis fact (`pipeline.availability.AXIS_FACTS`)
may ever rule an edge inactive for a profile. A leaf this evaluator cannot resolve must never be
able to mask a `has_technology` leaf's real relevance -- if the pipeline cannot decide, the node's
own three-state availability (`UNCERTAIN`) is where that fact belongs, never a silently-dropped
edge. Do not "simplify" this back to raw sensitivity; that is a regression, not a cleanup -- see
CLAUDE.md's own record of this decision before changing it.

**The corrected algorithm**: identical Kleene evaluation to `pipeline.availability`, except every
leaf that evaluator resolves to `UNKNOWN` (genuinely unresolvable: an unmatched `has_global_flag`,
an unmodeled civic/tradition/origin/country-flag check, ...) is instead treated as `EXCLUDED` here
-- the same "doesn't count, filtered out of AND/OR combination" treatment `has_technology` leaves
for OTHER edges already get in the real evaluator. Axis facts, DLC checks, ground facts and
mod-config-toggle flags -- everything DETERMINATE -- evaluate identically to the real evaluator;
nothing here weakens an actual axis constraint, it only stops an irrelevant unresolvable leaf from
hiding one. This module never imports or modifies `pipeline.availability`'s real evaluation path
(`evaluate_technology_for_profiles`); D-10's uncertainty figures are computed by that function alone
and are unaffected by anything in this module (`tests/test_dataset_emit.py::
test_d10_uncertainty_unchanged_by_edge_constraints` pins this).

**Real corpus result (977-node/984-edge corpus, all 25 `potential-gate` edges, all decidable)**: 20
edges always active (12/12 profiles) -- including both Disco Moon edges, correctly, once the mask
is removed. 5 edges genuinely axis-constrained, each a clean per-axis rectangle (verified by
reconstruction, not assumed): `arkship_neutronium_harvester` (`nomadic=[yes]`),
`orbital_artificial_eco` (`nomadic=[no]`), `tech_missiles_1`/`tech_torpedoes_1`
(`shipset=[biological]`), and `giga_tech_planetary_seeder_nexus`'s `tech_gene_tailoring` edge
(`authority=[regular,hive_mind]` AND `shipset=[biological]` -- a genuine two-axis intersection,
still a rectangle in the product space `EmpireTypeConstraint`'s per-axis-array shape already
supports). 0 edges are ever "never active" under this criterion -- the earlier sensitivity pass's
0/12 Disco Moon result does not recur.
"""

from __future__ import annotations

from .availability import (
    AXIS_FACTS,
    DLC_NAME_CHECK_KEYS,
    GROUND_FACT_BOOL,
    EXCLUDED_KEYS,
    _State,
    _Eval,
    _bool_eval,
    _flag_value_name,
    _is_mod_config_toggle_flag,
    _yesno,
    evaluate_trigger_block,
)
from . import availability as _availability_module
from .clausewitz.nodes import Assignment, Block, Identifier, StringLiteral

AXES = ("authority", "shipset", "nomadic")


def _field(block: Block, name: str) -> Assignment | None:
    result = None
    for item in block.items:
        if isinstance(item, Assignment) and item.key_name == name:
            result = item
    return result


def _target_name(value) -> str | None:
    if isinstance(value, Identifier):
        return value.name
    if isinstance(value, StringLiteral):
        return value.value
    return None


def _relaxed_leaf(assignment: Assignment, profile: dict) -> _Eval:
    """`pipeline.availability._evaluate_leaf`, with every UNKNOWN-return branch changed to
    EXCLUDED -- see module docstring for why. Kept as a hand-mirrored copy (not a monkeypatch
    of the real evaluator) so this module can never accidentally change
    `evaluate_technology_for_profiles`'s behaviour."""
    key = assignment.key_name
    negate = assignment.operator == "!="

    if key in EXCLUDED_KEYS:
        return _Eval(_State.EXCLUDED, None)
    if key == "has_global_flag":
        flag_name = _flag_value_name(assignment.value)
        if flag_name is not None and _is_mod_config_toggle_flag(flag_name):
            return _bool_eval(False, negate, assignment)
        return _Eval(_State.EXCLUDED, None)
    if key in DLC_NAME_CHECK_KEYS:
        return _bool_eval(True, negate, assignment)
    if key in GROUND_FACT_BOOL:
        target = _yesno(assignment.value)
        if target is None:
            return _Eval(_State.EXCLUDED, None)
        return _bool_eval(GROUND_FACT_BOOL[key] == target, negate, assignment)
    if key in AXIS_FACTS:
        target = _yesno(assignment.value)
        if target is None:
            return _Eval(_State.EXCLUDED, None)
        actual = AXIS_FACTS[key](profile)
        return _bool_eval(actual == target, negate, assignment)
    return _Eval(_State.EXCLUDED, None)


def _legacy_combine_or(children: list[_Eval]) -> _Eval:
    """The `pipeline.availability._combine_or` behaviour AS IT WAS before Item 2 (later session)
    taught `has_ascension_perk`/`has_active_tradition` to sometimes return a real FALSE instead of
    always EXCLUDED. That change needed `_combine_or` itself to stop letting a lone real-FALSE
    sibling close off an OR that still has an EXCLUDED (gate-only, presumed-satisfiable) branch --
    correct for `evaluate_technology_for_profiles`'s real availability computation, but WRONG for
    this module's OWN, deliberately different `_relaxed_leaf` mechanism: `_relaxed_leaf` already
    turns every genuinely-UNKNOWN leaf into EXCLUDED specifically so an unrelated unresolvable
    condition can never mask a `has_technology` edge's real relevance (the Disco Moon bug this
    module exists to fix). Under the corrected `_combine_or`, that same EXCLUDED-conversion would
    now ALSO suppress the forced `has_technology` leaf's own real FALSE whenever a sibling is
    EXCLUDED -- reintroducing a masking bug of the same shape, just one step removed. Kept as an
    exact copy of the pre-Item-2 function (not a re-derivation) and swapped in for the duration of
    `_edge_active_per_profile`'s sensitivity check only -- `pipeline.availability`'s own
    `_combine_or` (used everywhere else, including this module's OTHER helpers) is untouched."""
    relevant = [c for c in children if c.state != _State.EXCLUDED]
    if not relevant:
        return _Eval(_State.EXCLUDED, None)
    if any(c.state == _State.TRUE for c in relevant):
        return _Eval(_State.TRUE, None)
    unknown_ones = [c for c in relevant if c.state == _State.UNKNOWN]
    if unknown_ones:
        return _Eval(_State.UNKNOWN, unknown_ones[0].leaf)
    return _Eval(_State.FALSE, relevant[0].leaf)


def _edge_active_per_profile(potential_value: Block | None, target_key: str, profiles: list[dict]) -> list[bool]:
    """For one `potential-gate` edge (`has_technology = target_key` inside `potential_value`),
    whether it's axis-relevant for each profile, in `profiles` order. Forces `target_key`'s
    `has_technology` leaf TRUE then FALSE (all other leaves via `_relaxed_leaf`) and compares the
    resulting AvailabilityResult.state; a difference means the leaf's value matters for that
    profile."""

    def make_patched(forced: bool):
        def patched(assignment: Assignment, profile: dict) -> _Eval:
            if assignment.key_name == "has_technology" and _target_name(assignment.value) == target_key:
                negate = assignment.operator == "!="
                state = _State.TRUE if (forced != negate) else _State.FALSE
                return _Eval(state, None if state == _State.TRUE else assignment)
            return _relaxed_leaf(assignment, profile)
        return patched

    orig_leaf = _availability_module._evaluate_leaf
    orig_combine_or = _availability_module._combine_or
    results = []
    try:
        _availability_module._combine_or = _legacy_combine_or
        for profile in profiles:
            _availability_module._evaluate_leaf = make_patched(True)
            r_true = evaluate_trigger_block(potential_value, profile)
            _availability_module._evaluate_leaf = make_patched(False)
            r_false = evaluate_trigger_block(potential_value, profile)
            results.append(r_true.state != r_false.state)
    finally:
        _availability_module._evaluate_leaf = orig_leaf
        _availability_module._combine_or = orig_combine_or
    return results


def _fit_rectangle(profiles: list[dict], active: list[bool]) -> dict[str, list[str]] | None:
    """Fits the boolean `active` array (parallel to `profiles`) to a per-axis-array rectangle, the
    exact shape `EmpireTypeConstraint` requires. Returns `None` if no such rectangle reproduces
    `active` exactly (would mean a genuine cross-axis union -- not expected, not seen in the real
    corpus, and never silently forced into a wrong shape)."""
    if all(active):
        return {}
    if not any(active):
        return None  # "matches zero profiles" isn't expressible -- see module docstring; caller must not call this for such an edge

    # Per-axis candidate: the set of values this axis takes on among ACTIVE profiles. An axis
    # irrelevant to the constraint (e.g. authority when only nomadic matters) legitimately has the
    # SAME full value set among both active and inactive profiles -- that's expected, not a
    # conflict, so unlike an earlier broken version of this function, there is no active/inactive
    # intersection check here. Correctness is verified once, below, by full reconstruction.
    constraint: dict[str, list[str]] = {}
    for axis in AXES:
        values = sorted({p[axis] for p in profiles})
        active_values = sorted({p[axis] for p, a in zip(profiles, active) if a})
        if len(active_values) < len(values):
            constraint[axis] = active_values

    def matches(p: dict) -> bool:
        return all(p[axis] in constraint[axis] for axis in constraint)

    if all(active[i] == matches(profiles[i]) for i in range(len(profiles))):
        return constraint
    return None


def compute_potential_gate_constraints(
    rendered_defs: dict, typed_edges: list, profiles: list[dict]
) -> dict[tuple[str, str, str], dict[str, list[str]]]:
    """`(from_key, to_key, kind) -> appliesToEmpireTypes` for every `potential-gate` edge whose
    axis relevance is NOT the same for all 12 profiles. `kind` is part of the key -- NOT optional --
    because `(from_key, to_key)` alone is not unique: 4 real pairs (CLAUDE.md's "Edge-kind
    membership is NOT mutually exclusive per (from, to) pair", e.g. `tech_mega_engineering ->
    giga_tech_arkship_neutronium_harvester`) are simultaneously a `prerequisite` edge AND a
    `potential-gate` edge, and the former must never inherit the latter's constraint. An edge
    absent from the returned dict is unconstrained (`{}`) -- either genuinely axis-invariant, or
    its active set couldn't be fit to a rectangle (never observed on the real corpus; if it ever
    occurs, the edge stays unconstrained rather than guessed at, so it degrades to over-inclusive,
    never to a silently dropped dependency)."""
    result: dict[tuple[str, str, str], dict[str, list[str]]] = {}
    for e in typed_edges:
        if e.kind != "potential-gate":
            continue
        owner_block = rendered_defs[e.to_key].block
        potential = _field(owner_block, "potential")
        pot_value = potential.value if potential else None
        active = _edge_active_per_profile(pot_value, e.from_key, profiles)
        if all(active):
            continue
        rect = _fit_rectangle(profiles, active)
        if rect:
            result[(e.from_key, e.to_key, e.kind)] = rect
        # rect is None (never-active or non-rectangular): leave unconstrained, never drop the edge.
    return result


def edge_active_for_profile(constraint: dict[str, list[str]] | None, profile: dict) -> bool:
    """Whether an edge carrying `constraint` (its `appliesToEmpireTypes`, possibly `{}`/`None` for
    unconstrained) is active for `profile`. Cheap per-axis membership check -- the expensive Kleene
    computation runs once per edge at base-dataset build time via
    `compute_potential_gate_constraints`, not once per (edge, profile) pair at overlay build time."""
    if not constraint:
        return True
    return all(profile[axis] in values for axis, values in constraint.items())
