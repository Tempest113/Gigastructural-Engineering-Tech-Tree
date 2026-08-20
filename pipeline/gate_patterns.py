"""P-3: gate classification -- the curated pattern registry `spec/P-03-gates.md` calls for,
layered on top of P-14's universal `potential-gate` edge extraction (`pipeline/edges.py`).

**Four registered patterns, all confirmed real in the corpus by the survey that preceded this
module** (gate-classification session): `has_ascension_perk` (22 rendered technologies),
`has_technology` (22 technologies, already producing the 25 `potential-gate` edges P-14
extracts), and two Gigastructures scripted-trigger wrappers, `has_gigastructural_constructs` (9
technologies) and `has_galactic_wonders` (14 technologies). 7 technologies carry two patterns at
once; none carry three or more.

**Curation is at the MECHANISM level, not the occurrence level** (decided at implementation --
see `spec/P-03-gates.md`'s "Curation is at the MECHANISM level" note for the full reasoning).
Once a pattern is registered here, every real occurrence of it produces a `GateMatch` -- there is
no further per-technology allowlist filtering individual occurrences out.

**This module never touches availability.** `has_ascension_perk`, `has_technology`,
`has_gigastructural_constructs` and `has_galactic_wonders` are already excluded from
`pipeline.availability`'s boolean combination (`EXCLUDED_KEYS`, an identity-element state
predating this module) -- gate classification adds display metadata on top of a graph P-14
already builds and an evaluator that already ignores these four leaf keys; it changes zero
availability-evaluation code paths and zero edge counts (`tests/test_gate_patterns.py::
test_building_gate_classification_does_not_change_potential_gate_edge_count` pins this).

**The two scripted-trigger wrappers are NOT literal `has_ascension_perk` checks in a technology's
own block** -- confirmed by direct inspection of `giga_scripted_triggers.txt` /
`zzz_overwrites.txt` (gate-classification survey session), not assumed from the trigger names
alone:

- `has_gigastructural_constructs` is a 1:1 wrapper for a single perk, `ap_gigastructural_
  constructs`.
- `has_galactic_wonders` is an `OR` of the base perk, `ap_galactic_wonders`, plus three
  DLC-ownership-variant perk IDs (`ap_galactic_wonders_utopia`, `_megacorp`,
  `_utopia_and_megacorp`) that unlock the exact same thing under different DLC combinations. The
  base id is used as the single canonical display target, since it is the one guaranteed
  vendored and localised regardless of which variant an actual save holds -- none of the three
  variant IDs has its own icon or loc entry in the vendored corpus (checked, not assumed), so
  they could not be displayed individually even if that were wanted.

**Both wrappers also carry an `is_ai = yes` AI-only override branch** (`OR = { AND = { is_ai =
yes, has_country_flag = ... } has_ascension_perk = ... }`) that this registry, like
`pipeline.availability`, deliberately does not model -- it is an AI-empire concession, never
relevant to a player-empire profile. Recorded here so a future session doesn't mistake the
missing AI branch for an oversight.

Zero negated (`NOT`/`NOR`-wrapped) occurrences of any of these four keys exist under any rendered
technology's `potential` block today (confirmed by survey) -- a negated match is silently
excluded rather than emitted wrong-polarity, matching `pipeline.edges`'s identical treatment of a
negated `has_technology` (P-14's "inverting it silently would produce a wrong graph"), but this
is a default for a case that does not currently occur, not a guess.
"""

from __future__ import annotations

from dataclasses import dataclass

from .clausewitz.nodes import Assignment, Block, Identifier, StringLiteral

GATE_KIND_ASCENSION_PERK = "ascension_perk"
GATE_KIND_TECHNOLOGY = "technology"

# D-3 (spec/P-03-gates.md): ascension-perk gates outrank technology gates. Ties within the same
# kind keep declaration order (order_gates below uses a stable sort).
GATE_KIND_PRIORITY = {GATE_KIND_ASCENSION_PERK: 0, GATE_KIND_TECHNOLOGY: 1}

WRAPPER_TO_PERK = {
    "has_gigastructural_constructs": "ap_gigastructural_constructs",
    "has_galactic_wonders": "ap_galactic_wonders",
}

GATE_LEAF_KEYS = {"has_ascension_perk", "has_technology", *WRAPPER_TO_PERK}


@dataclass(frozen=True)
class GateMatch:
    kind: str  # GateKind ("ascension_perk" | "technology")
    ref_id: str  # perk id or technology key this gate names
    source_leaf: str  # the raw trigger key matched, e.g. "has_galactic_wonders"


def _target_name(value) -> str | None:
    if isinstance(value, Identifier):
        return value.name
    if isinstance(value, StringLiteral):
        return value.value
    return None


def _field(block: Block, name: str) -> Assignment | None:
    result = None
    for item in block.items:
        if isinstance(item, Assignment) and item.key_name == name:
            result = item
    return result


def _scoped_gate_leaves(node: Block, negated: bool) -> list[tuple[str, str | None, bool]]:
    """Same AND/OR/NOT/NOR-only descent discipline as `pipeline.edges._scoped_has_technology`
    and `pipeline.availability._evaluate_node` -- an opaque block-valued field (`count_country`,
    `weight_modifier`, ...) is never searched inside. See `pipeline/edges.py`'s module docstring
    for the `count_country` false-positive this discipline specifically guards against."""
    results: list[tuple[str, str | None, bool]] = []
    for item in node.items:
        if not isinstance(item, Assignment):
            continue
        key_upper = item.key_name.upper()
        if item.key_name in GATE_LEAF_KEYS:
            results.append((item.key_name, _target_name(item.value), negated))
        elif key_upper in ("NOT", "NOR") and isinstance(item.value, Block):
            results.extend(_scoped_gate_leaves(item.value, not negated))
        elif key_upper in ("AND", "OR") and isinstance(item.value, Block):
            results.extend(_scoped_gate_leaves(item.value, negated))
        # else: opaque leaf -- do not descend.
    return results


def classify_gates(block: Block) -> list[GateMatch]:
    """Every gate-pattern-registry match in `block`'s `potential` sub-block, in declaration
    order (before `order_gates`' D-3 priority sort). Excludes a negated match (see module
    docstring) and a bare leaf with no resolvable target name."""
    potential = _field(block, "potential")
    if potential is None or not isinstance(potential.value, Block):
        return []

    matches: list[GateMatch] = []
    for leaf_key, target, negated in _scoped_gate_leaves(potential.value, False):
        if target is None or negated:
            continue
        if leaf_key == "has_ascension_perk":
            matches.append(GateMatch(GATE_KIND_ASCENSION_PERK, target, leaf_key))
        elif leaf_key == "has_technology":
            matches.append(GateMatch(GATE_KIND_TECHNOLOGY, target, leaf_key))
        elif leaf_key in WRAPPER_TO_PERK:
            matches.append(GateMatch(GATE_KIND_ASCENSION_PERK, WRAPPER_TO_PERK[leaf_key], leaf_key))
    return matches


def order_gates(matches: list[GateMatch]) -> list[GateMatch]:
    """D-3's priority ordering: ascension-perk gates before technology gates, declaration order
    preserved within the same kind (Python's sort is stable). Index 0 of the result is the
    primary gate (P-3/P-12.7)."""
    return sorted(matches, key=lambda m: GATE_KIND_PRIORITY[m.kind])
