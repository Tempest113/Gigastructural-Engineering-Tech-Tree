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

**This module never touches `potential`-based availability.** `has_ascension_perk`,
`has_technology`, `has_gigastructural_constructs` and `has_galactic_wonders` are already excluded
from `pipeline.availability`'s boolean combination (`EXCLUDED_KEYS`, an identity-element state
predating this module) -- gate classification adds display metadata on top of a graph P-14
already builds and an evaluator that already ignores these four leaf keys; it changes zero
availability-evaluation code paths and zero edge counts (`tests/test_gate_patterns.py::
test_building_gate_classification_does_not_change_potential_gate_edge_count` pins this).

**A later session's addition, `classify_weight_gate_condition`, is the one exception.** A
zero-factor `weight_modifier` condition that classifies to a registered gate pattern is excluded
from `pipeline.availability._apply_weight_gate`'s evaluation entirely (see
`pipeline.dataset_emit.build_context`'s `weight_gate_conditions`/`weight_gate_gate_matches`
split) -- it badges the card as a `Gate` instead of contributing a `weight-gated` verdict for that
condition. This is a deliberate, documented exception to the "never touches availability" rule
above, not a violation of it: the condition still resolves the SAME question ("is this currently
offered"), just through the gate-display channel instead of the `AvailabilityState` channel.

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

**A later session's additions (`is_wilderness_empire`, origin/ethics/civic gates) DO have real
negated occurrences, and a real polarity bug shipped before it was caught.** `_leaf_negated`
(below) tracks THREE independent negation channels -- `NOT`/`NOR` wrapping (the only one this
paragraph's "zero negated occurrences" scoped itself to), the `!=` operator, and a literal
boolean-false VALUE (`is_wilderness_empire = no`, Clausewitz's other way to write a negative
condition with no wrapper at all). The bug: only the first channel was ever checked. 31 real
technologies (`tech_habitat_1`/`_2`, `tech_gene_banks`, ...) write `is_wilderness_empire = no`
("needs a NON-wilderness empire") and were rendered as a positive "Needs Wilderness" gate --
exactly backwards, user-reported. Fixed by `_leaf_negated`; see that function's own docstring for
the full corpus scoping (the value-level channel is safe to check unscoped across every
`GATE_LEAF_KEYS` member -- `= no` occurs ONLY on `is_wilderness_empire` in the real corpus today).
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

# **`can_research_technology` was REMOVED from gate classification (a later session, user-
# reported).** Previously treated as an alias for `has_technology` (same `GATE_KIND_TECHNOLOGY`
# badge, "Needs <target>") on the theory that both are P-14 prerequisite-graph reachability under
# different literal names. That conflated two genuinely different engine semantics:
# `has_technology` means "you have ALREADY COMPLETED this technology" -- a real, satisfiable
# prerequisite a player advances toward, exactly what "Needs X" communicates. `can_research_
# technology` means "this OTHER technology is not currently LOCKED OUT for your empire" -- a
# structural eligibility fact about your build, not something researched or "gotten". Badging it
# "Needs Genome Mapping" told the player to go complete a technology that may have nothing to do
# with their actual empire-type restriction. Real corpus: exactly ONE literal occurrence
# (`tech_alien_cloning`'s `OR = { is_beastmasters_empire = yes, can_research_technology =
# tech_genome_mapping }`), but D-3's gate-propagation-down-prerequisite-chains feature (a prior
# session) inherited this single mis-badge onto 15 further descendants (16 technologies total,
# `tech_controlled_mutations`/`tech_improved_incubators` and everything below them) -- matching
# the user's "many technologies" report exactly. `can_research_technology` stays excluded from
# `pipeline.availability`'s boolean combination (an identity element there, unaffected by this
# change) -- only the gate BADGE is removed; the technology still resolves availability the same
# way it always did.
TECHNOLOGY_ALIAS_KEYS: set[str] = set()

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
    # can_research_technology (a later session, user-reported -- see TECHNOLOGY_ALIAS_KEYS's own
    # docstring for the full reasoning): a DIFFERENT exclusion reason from every entry above --
    # not compound, not an empire-defining-choice-shaped concept with no single clean refId. It's
    # a genuinely different ENGINE SEMANTIC from has_technology ("can research" vs. "has already
    # researched"), and badging it identically to has_technology misrepresented an eligibility
    # fact as a completable requirement. Stays excluded from availability (an identity element,
    # unaffected) but is no longer gate-classified.
    "can_research_technology",
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
    # Nested AND-of-OR fix (a later session, user-reported: Gargantuan Cloning Facilities showed
    # "Needs Galactic Wonders" + "or: Mechromancy" as if they were two peers in one choice, when
    # the real structure is `AND(has_galactic_wonders, OR(has_genetically_ascended, has_active_
    # tradition, ap_mechromancy))` -- Galactic Wonders is unconditionally required, and the OR is
    # a SEPARATE branch beneath it, not beside it). `group_id` names the specific `OR`/`NOR` block
    # this leaf is a DIRECT child of (mirroring `Edge.groupId`'s per-owner, per-block-index
    # identity), so two independent OR groups on the same technology are distinguishable and an
    # unconditional (non-`alternative`) leaf is never confused with a member of either. `None` for
    # a non-`alternative` match, or one whose nearest enclosing wrapper was `AND`/`NOT` rather than
    # `OR`/`NOR` (impossible in practice -- `alternative` is only ever True when a group_id was
    # assigned -- but kept nullable to mirror `Edge.groupId`'s own contract exactly). Real corpus:
    # exactly 1 technology (`giga_tech_the_vat`) has a mix of unconditional and grouped gate
    # matches today; every other multi-gate technology's matches are either all-unconditional or
    # all-members-of-the-SAME-group, where this field changes nothing observable.
    group_id: str | None = None


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


def _leaf_negated(item: Assignment, ancestor_negated: bool) -> bool:
    """A leaf's EFFECTIVE polarity has THREE independent channels, each of which can flip it, and
    the polarity bug this function fixes was tracking only the first: `ancestor_negated` (the
    leaf sits under a `NOT`/`NOR` wrapper -- already tracked before this fix), `item.operator ==
    "!="` (zero real corpus occurrences on a gate leaf key today, checked directly -- kept for
    correctness/symmetry with `pipeline.availability._evaluate_leaf`'s own `negate = assignment.
    operator == "!="`, not because a real case exists yet), and a literal boolean-false VALUE
    (`is_wilderness_empire = no` -- Clausewitz's OTHER way to write a negative condition, with no
    `NOT`/`NOR` wrapper at all). The third channel was the real, corpus-confirmed bug: 31 real
    technologies (`tech_habitat_1`/`_2`, `tech_gene_banks`, ...) write `is_wilderness_empire = no`
    ("this technology needs a NON-wilderness empire") and it was rendered as a positive "Needs
    Wilderness" gate -- backwards. Checked against the full GATE_LEAF_KEYS corpus: `= no` occurs
    ONLY on `is_wilderness_empire` today (31 technologies, all boolean-shaped leaves) -- no
    VALUE-shaped key (`has_origin`, `has_technology`, `has_ascension_perk`, ...) ever legitimately
    takes the literal string "no" as a real id, so this check is safe unscoped rather than needing
    a separate boolean-shaped-keys allowlist."""
    operator_negated = item.operator == "!="
    value_negated = _target_name(item.value) == "no"
    # NOTE: `a != b != c` is a Python CHAINED comparison (`(a != b) and (b != c)`), not XOR-chaining
    # -- deliberately NOT used here; explicit parenthesization is required for a real 3-way XOR.
    return (ancestor_negated != operator_negated) != value_negated


def _scoped_gate_leaves(
    node: Block, negated: bool, in_or: bool = False, group_index: int | None = None, counter: list[int] | None = None,
) -> list[tuple[str, str | None, bool, bool, int | None]]:
    """Same AND/OR/NOT/NOR-only descent discipline as `pipeline.edges._scoped_has_technology`
    and `pipeline.availability._evaluate_node` -- an opaque block-valued field (`count_country`,
    `weight_modifier`, ...) is never searched inside. See `pipeline/edges.py`'s module docstring
    for the `count_country` false-positive this discipline specifically guards against.

    `in_or` (Item 4): True once any ancestor wrapper was `OR`/`NOR` -- a structural property
    (disjunction) independent of `negated`'s polarity, and once True it stays True for every
    descendant (an `OR` nested inside another `OR`'s branch is still "one of several ways",
    doesn't need re-detecting each level).

    `group_index` (nested AND-of-OR fix, a later session): the INNERMOST enclosing `OR`/`NOR`
    block's own index (declaration order, 0-based, counted via the shared `counter` list), or
    `None` outside any `OR`/`NOR`. A fresh index is allocated every time a NEW `OR`/`NOR` block is
    entered (even nested inside another one -- a leaf's group is the block it's a DIRECT child of,
    not any outer ancestor); `AND`/`NOT` never allocate one and pass the current `group_index`
    through unchanged, since neither introduces a new choice of alternatives."""
    if counter is None:
        counter = [0]
    results: list[tuple[str, str | None, bool, bool, int | None]] = []
    for item in node.items:
        if not isinstance(item, Assignment):
            continue
        key_upper = item.key_name.upper()
        if item.key_name in GATE_LEAF_KEYS:
            results.append((item.key_name, _target_name(item.value), _leaf_negated(item, negated), in_or, group_index))
        elif key_upper == "NOT" and isinstance(item.value, Block):
            results.extend(_scoped_gate_leaves(item.value, not negated, in_or, group_index, counter))
        elif key_upper == "NOR" and isinstance(item.value, Block):
            this_group = counter[0]
            counter[0] += 1
            results.extend(_scoped_gate_leaves(item.value, not negated, True, this_group, counter))
        elif key_upper == "AND" and isinstance(item.value, Block):
            results.extend(_scoped_gate_leaves(item.value, negated, in_or, group_index, counter))
        elif key_upper == "OR" and isinstance(item.value, Block):
            this_group = counter[0]
            counter[0] += 1
            results.extend(_scoped_gate_leaves(item.value, negated, True, this_group, counter))
        # else: opaque leaf -- do not descend.
    return results


def _classify_leaves_in_block(
    technology_key: str, root: Block, group_label: str, filter_negated: bool = True,
) -> list[GateMatch]:
    """Shared dispatch for both `classify_gates` (a technology's own `potential` sub-block) and
    `classify_weight_gate_condition` (a zero-factor `weight_modifier` condition block -- see that
    function's docstring). `group_label` namespaces `GateMatch.group_id` so the two callers never
    collide on the same id for the same technology.

    `filter_negated` (weight-condition gate extraction): `classify_gates` (default, `True`) keeps
    dropping a negated leaf -- a `potential` block's own polarity already IS the requirement, and
    "must NOT have perk X" is not a positive "Needs X" gate. `classify_weight_gate_condition`
    passes `False`: a zero-factor `weight_modifier` condition names the same perk/origin/civic/
    technology either way a `weight_modifier` names it AT ALL is the informative fact worth
    badging (real corpus: `tech_lathe_*`'s condition wraps `has_ascension_perk = ap_cosmogenesis`
    in a `NOT`, `tech_housing_2`'s names `civic_agrarian_idyll` completely unwrapped -- both name
    the same real requirement/exclusion pair a player cares about, and both badge identically to
    their own swap-pair sibling, `tech_housing_agrarian_idyll`, which names the same civic from
    the opposite polarity). Gate badges are already an approximate, best-effort display layer
    elsewhere (an `alternative`'s "or:" wording, a dangling-alternative downgrade) -- this is a
    deliberate continuation of that, not a new precision bar."""
    matches: list[GateMatch] = []
    for leaf_key, target, negated, alternative, group_index in _scoped_gate_leaves(root, False):
        if target is None or (filter_negated and negated):
            continue
        group_id = f"{technology_key}#{group_label}{group_index}" if alternative and group_index is not None else None
        if leaf_key == "has_ascension_perk":
            matches.append(GateMatch(GATE_KIND_ASCENSION_PERK, target, leaf_key, alternative, group_id))
        elif leaf_key == "has_technology" or leaf_key in TECHNOLOGY_ALIAS_KEYS:
            matches.append(GateMatch(GATE_KIND_TECHNOLOGY, target, leaf_key, alternative, group_id))
        elif leaf_key in WRAPPER_TO_PERK:
            matches.append(GateMatch(GATE_KIND_ASCENSION_PERK, WRAPPER_TO_PERK[leaf_key], leaf_key, alternative, group_id))
        elif leaf_key in ORIGIN_DIRECT_KEYS:
            matches.append(GateMatch(GATE_KIND_ORIGIN, target, leaf_key, alternative, group_id))
        elif leaf_key in WRAPPER_TO_ORIGIN:
            matches.append(GateMatch(GATE_KIND_ORIGIN, WRAPPER_TO_ORIGIN[leaf_key], leaf_key, alternative, group_id))
        elif leaf_key in ETHICS_OR_CIVIC_DIRECT_KEYS:
            matches.append(GateMatch(GATE_KIND_ETHICS_OR_CIVIC, target, leaf_key, alternative, group_id))
        elif leaf_key in WRAPPER_TO_ETHIC:
            matches.append(GateMatch(GATE_KIND_ETHICS_OR_CIVIC, WRAPPER_TO_ETHIC[leaf_key], leaf_key, alternative, group_id))
    return matches


def classify_gates(technology_key: str, block: Block) -> list[GateMatch]:
    """Every gate-pattern-registry match in `block`'s `potential` sub-block, in declaration
    order (before `order_gates`' D-3 priority sort). Excludes a negated match (see module
    docstring) and a bare leaf with no resolvable target name. `technology_key` is used ONLY to
    compose a stable, globally-unique `GateMatch.group_id` (`f"{technology_key}#gate-alt{index}"`,
    mirroring `Edge.groupId`'s own `f"{technology_key}#alt{index}"` convention) -- it plays no role
    in which leaves match."""
    potential = _field(block, "potential")
    if potential is None or not isinstance(potential.value, Block):
        return []
    return _classify_leaves_in_block(technology_key, potential.value, "gate-alt")


def classify_weight_gate_condition(technology_key: str, condition_block: Block, index: int) -> list[GateMatch]:
    """Extends gate extraction (a later session, "weight-condition gate extraction") to a single
    zero-factor `weight_modifier` condition block -- already `factor`-stripped and scripted-
    trigger-expanded by `pipeline.dataset_emit._weight_gate_condition_blocks`, the same input
    `pipeline.availability._apply_weight_gate` consumes. Classified with the exact same registry
    and `_scoped_gate_leaves` descent discipline `classify_gates` uses on a `potential` block --
    this is a new INPUT to gate extraction, not a new gate mechanism (CLAUDE.md's "curation is at
    the MECHANISM level").

    `index` disambiguates the `group_id` namespace across a technology's own multiple
    `weight_modifier` entries (a real corpus shape: `giga_tech_amb_supertensiles` has two), and
    from `classify_gates`' own `#gate-alt` namespace, so two independent OR-groups -- one from
    `potential`, one from a weight condition -- never collide on the same `groupId` even when both
    belong to the same technology. See `_classify_leaves_in_block`'s `filter_negated` for why this
    call passes `filter_negated=False`, unlike `classify_gates`."""
    return _classify_leaves_in_block(technology_key, condition_block, f"weight-gate{index}-alt", filter_negated=False)


def order_gates(matches: list[GateMatch]) -> list[GateMatch]:
    """D-3's priority ordering: ascension-perk gates before technology gates, declaration order
    preserved within the same kind (Python's sort is stable). Index 0 of the result is the
    primary gate (P-3/P-12.7)."""
    return sorted(matches, key=lambda m: GATE_KIND_PRIORITY[m.kind])
