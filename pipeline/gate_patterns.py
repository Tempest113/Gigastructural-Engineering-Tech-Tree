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
GATE_KIND_ORIGIN = "origin"
GATE_KIND_ETHICS_OR_CIVIC = "ethics_or_civic"
GATE_KIND_TECHNOLOGY = "technology"

# D-3 (spec/P-03-gates.md): ascension-perk gates outrank technology gates. Origin/ethics-or-civic
# gates ("path to zero uncertain" follow-up, Item 3) are placed between the two -- like ascension
# perks, they name something about WHO you are (an empire-defining choice), closer in kind to a
# perk than to a mere prerequisite technology, but perks still outrank them since a perk-gated
# technology is typically the rarer, more deliberate case. Ties within the same kind keep
# declaration order (order_gates below uses a stable sort).
GATE_KIND_PRIORITY = {
    GATE_KIND_ASCENSION_PERK: 0,
    GATE_KIND_ORIGIN: 1,
    GATE_KIND_ETHICS_OR_CIVIC: 2,
    GATE_KIND_TECHNOLOGY: 3,
}

# **Considered redundant, kept deliberately, once `pipeline.scripted_triggers` existed to make
# the question answerable** ("path to zero uncertain" follow-up, Item 2). General expansion DOES
# resolve both names down to `has_ascension_perk` leaves for AVAILABILITY purposes (a confirmed
# no-op there, since `has_ascension_perk` was already excluded either way -- see
# `pipeline.scripted_triggers`' own docstring). But `classify_gates` below operates on a
# technology's RAW, unexpanded `potential` block (never scripted-trigger-expanded) by design, for
# two reasons expansion would not replicate:
# 1. `has_galactic_wonders`'s real body is an `OR` of FOUR ascension-perk ids (the base perk plus
#    three DLC-ownership variants unlocking the same thing) -- this table's hand curation collapses
#    all four to the ONE canonical, actually-vendored-and-localised id. General expansion would
#    surface all four as separate `GateMatch`es instead, a real regression in what gets displayed
#    (4 badge options where the corpus only supports showing 1).
# 2. Gate classification needs a stable trigger NAME to hang display metadata on
#    (`source_leaf` below); expanding away the name before classification would need a second,
#    parallel curation step to reconstruct which literal leaf a card's gate badge came from.
# Removing this table and expanding first, as this docstring's earlier draft asked, was tried and
# rejected for these reasons -- it is not an oversight that it still exists.
WRAPPER_TO_PERK = {
    "has_gigastructural_constructs": "ap_gigastructural_constructs",
    "has_galactic_wonders": "ap_galactic_wonders",
}

# "Path to zero uncertain" follow-up, Item 3: ethics/civic/origin display gates, the same
# treatment as ascension perks -- see `pipeline.availability.EXCLUDED_KEYS`'s own comment for the
# full corpus evidence behind every one of these 19 leaf keys. Two shapes:
#
# - DIRECT: the leaf already carries its own target value (`has_origin = origin_wilderness`),
#   exactly like `has_ascension_perk`/`has_technology` already do -- no curation needed.
# - WRAPPER: a 1:1 scripted-trigger wrapper around a single direct leaf, same shape as
#   `WRAPPER_TO_PERK` above (`is_wilderness_empire = { has_origin = origin_wilderness }`,
#   confirmed by direct inspection, not assumed from the name).
WRAPPER_TO_ORIGIN = {
    "is_wilderness_empire": "origin_wilderness",
    "giga_has_frameworld_origin": "origin_frameworld",
}
ORIGIN_DIRECT_KEYS = {"has_origin"}

WRAPPER_TO_ETHIC = {
    "is_fanatic_spiritualist": "ethic_fanatic_spiritualist",
    "is_fanatic_pacifist": "ethic_fanatic_pacifist",
}
# has_civic is a DISTINCT leaf from has_valid_civic (missed by the first survey pass, added once
# found) -- both direct, both civic-shaped.
ETHICS_OR_CIVIC_DIRECT_KEYS = {"has_ethic", "has_valid_civic", "has_civic"}

# can_research_technology: an engine-builtin alias of has_technology (P-14 prerequisite-graph
# reachability under a different literal name, not a scripted_trigger definition anywhere in the
# corpus, confirmed by direct search) -- same GATE_KIND_TECHNOLOGY treatment.
TECHNOLOGY_ALIAS_KEYS = {"can_research_technology"}

# **Deliberately excluded from availability (`pipeline.availability.EXCLUDED_KEYS`) but NOT
# gate-badge-classified here.** Each is a genuinely COMPOUND trigger -- an `OR` of multiple real
# sub-conditions -- confirmed by direct inspection, not assumed:
# - `is_void_dweller_empire` = OR(has_ascension_perk=ap_voidborn, has_void_dweller_origin=yes)
# - `has_void_dweller_origin` = OR(has_origin=origin_void_dwellers, has_origin=origin_void_machines)
# - `is_giga_one_planet_origin` = OR(has_country_flag=giga_one_planet_origin, giga_has_frameworld_origin=yes)
# - `is_spiritualist` = OR(has_ethic=ethic_spiritualist, is_fanatic_spiritualist=yes)
# - `is_natural_design_empire` = OR(has_valid_civic=civic_natural_design, its hive variant)
# - `is_beastmasters_empire` / `is_world_forger_empire` = OR of 4 civic variants each
# A single `GateMatch` needs one clean `refId`; picking one of several real alternatives would
# misrepresent the condition as narrower than it is, and this project's own no-guessing discipline
# rules that out without a documented reason to prefer one alternative -- none exists yet. Two more
# are excluded from availability for the same "empire-defining choice, not eligibility" reason but
# aren't even origin/civic/ethic-SHAPED, so a gate badge for them would need an entirely different
# concept this session doesn't build: `is_megacorp` (targets `has_authority`, a real 4th authority
# value outside this project's 3-axis model), `is_individual_machine` (species-archetype + gestalt
# check), `has_genetically_ascended` (tradition-path-completion check), `is_infernal_empire`
# (species-trait check). Left as availability-only exclusions -- a technology gated SOLELY on one
# of these renders AVAILABLE with no gate badge, same as before this session for any leaf outside
# the registry, just no longer UNCERTAIN either.
NOT_GATE_CLASSIFIED_EXCLUDED_KEYS = {
    "is_void_dweller_empire",
    "has_void_dweller_origin",
    "is_giga_one_planet_origin",
    "is_spiritualist",
    "is_natural_design_empire",
    "is_beastmasters_empire",
    "is_world_forger_empire",
    "is_megacorp",
    "is_individual_machine",
    "has_genetically_ascended",
    "is_infernal_empire",
}

GATE_LEAF_KEYS = {
    "has_ascension_perk", "has_technology", *WRAPPER_TO_PERK,
    *ORIGIN_DIRECT_KEYS, *WRAPPER_TO_ORIGIN,
    *ETHICS_OR_CIVIC_DIRECT_KEYS, *WRAPPER_TO_ETHIC,
    *TECHNOLOGY_ALIAS_KEYS,
}


@dataclass(frozen=True)
class GateMatch:
    kind: str  # GateKind ("ascension_perk" | "origin" | "ethics_or_civic" | "technology")
    ref_id: str  # perk id, origin/ethic/civic id, or technology key this gate names
    source_leaf: str  # the raw trigger key matched, e.g. "has_galactic_wonders"
    # Item 4 ("path to zero uncertain" follow-up): True iff this leaf sits inside an `OR` --
    # i.e. is one of SEVERAL independent ways to satisfy `potential`, not the sole/AND-required
    # condition. The survey that preceded this fix found `tech_torpedoes_1` displaying "Needs
    # Riddle Escort" as an unconditional requirement when it's really one of four independent OR
    # branches (non-bio-ship empires qualify via a completely different branch alone) -- the same
    # OR-flattening failure mode as v1's, in the display layer rather than traversal. 11 of 25
    # real `has_technology`-under-`potential` occurrences (44%) sit inside an OR; see
    # `pipeline.dataset_emit._build_gates` for how this changes the emitted label and
    # `appliesToEmpireTypes`. Edge extraction (`pipeline/edges.py`) is NOT the bug and is
    # untouched by this fix -- its scope discipline is deliberate and documented for edge
    # completeness, a different concern from gate DISPLAY.
    alternative: bool = False


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


def _scoped_gate_leaves(node: Block, negated: bool, in_or: bool = False) -> list[tuple[str, str | None, bool, bool]]:
    """Same AND/OR/NOT/NOR-only descent discipline as `pipeline.edges._scoped_has_technology`
    and `pipeline.availability._evaluate_node` -- an opaque block-valued field (`count_country`,
    `weight_modifier`, ...) is never searched inside. See `pipeline/edges.py`'s module docstring
    for the `count_country` false-positive this discipline specifically guards against.

    `in_or` (Item 4): True once any ancestor wrapper was `OR`/`NOR` -- a structural property
    (disjunction) independent of `negated`'s polarity, and once True it stays True for every
    descendant (an `OR` nested inside another `OR`'s branch is still "one of several ways",
    doesn't need re-detecting each level)."""
    results: list[tuple[str, str | None, bool, bool]] = []
    for item in node.items:
        if not isinstance(item, Assignment):
            continue
        key_upper = item.key_name.upper()
        if item.key_name in GATE_LEAF_KEYS:
            results.append((item.key_name, _target_name(item.value), negated, in_or))
        elif key_upper in ("NOT", "NOR") and isinstance(item.value, Block):
            results.extend(_scoped_gate_leaves(item.value, not negated, in_or or key_upper == "NOR"))
        elif key_upper in ("AND", "OR") and isinstance(item.value, Block):
            results.extend(_scoped_gate_leaves(item.value, negated, in_or or key_upper == "OR"))
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
    for leaf_key, target, negated, alternative in _scoped_gate_leaves(potential.value, False):
        if target is None or negated:
            continue
        if leaf_key == "has_ascension_perk":
            matches.append(GateMatch(GATE_KIND_ASCENSION_PERK, target, leaf_key, alternative))
        elif leaf_key == "has_technology" or leaf_key in TECHNOLOGY_ALIAS_KEYS:
            matches.append(GateMatch(GATE_KIND_TECHNOLOGY, target, leaf_key, alternative))
        elif leaf_key in WRAPPER_TO_PERK:
            matches.append(GateMatch(GATE_KIND_ASCENSION_PERK, WRAPPER_TO_PERK[leaf_key], leaf_key, alternative))
        elif leaf_key in ORIGIN_DIRECT_KEYS:
            matches.append(GateMatch(GATE_KIND_ORIGIN, target, leaf_key, alternative))
        elif leaf_key in WRAPPER_TO_ORIGIN:
            matches.append(GateMatch(GATE_KIND_ORIGIN, WRAPPER_TO_ORIGIN[leaf_key], leaf_key, alternative))
        elif leaf_key in ETHICS_OR_CIVIC_DIRECT_KEYS:
            matches.append(GateMatch(GATE_KIND_ETHICS_OR_CIVIC, target, leaf_key, alternative))
        elif leaf_key in WRAPPER_TO_ETHIC:
            matches.append(GateMatch(GATE_KIND_ETHICS_OR_CIVIC, WRAPPER_TO_ETHIC[leaf_key], leaf_key, alternative))
    return matches


def order_gates(matches: list[GateMatch]) -> list[GateMatch]:
    """D-3's priority ordering: ascension-perk gates before technology gates, declaration order
    preserved within the same kind (Python's sort is stable). Index 0 of the result is the
    primary gate (P-3/P-12.7)."""
    return sorted(matches, key=lambda m: GATE_KIND_PRIORITY[m.kind])
