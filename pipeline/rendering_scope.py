"""P-16: rendering-scope closure.

**D-18 (`spec/decisions.md`): the closure is DEPTH-1, not a full transitive closure -- corrects
this module's original design.** CLAUDE.md's "Scope of ACOT and AoT" originally pulled in an
ACOT/AoT technology whenever it fell anywhere in the recursive prerequisite chain of a rendered
technology, "so a rendered technology's prerequisite chain is never broken by an invisible gap."
The user reported a concrete case this over-included -- an ACOT/AoT technology two hops deep,
required only by ANOTHER ACOT/AoT technology, not by anything actually rendered -- and, after a
survey quantified the real cost (see D-18), chose depth-1 instead: an ACOT/AoT technology renders
only when a rendered (Vanilla/Gigastructures) technology names it DIRECTLY in its own
`prerequisites` block. No recursion. This deliberately accepts a small number of off-tree
prerequisites -- a rendered ACOT/AoT technology may itself require a technology that is no longer
rendered -- see D-18's exact, named 3-link list and the corpus test pinning it
(`tests/test_rendering_scope.py::test_depth_one_closure_off_tree_links_match_the_accepted_set`).

This is the pipeline implementation of D-18's chosen rule (superseding the depth-N version this
module originally shipped, itself the first real implementation of HANDOFF.md's hand-computed
7-technology/max-depth-2 measurement).
"""

from __future__ import annotations

from .clausewitz.nodes import Assignment, Identifier
from .overwrites import TechnologyDefinition, alternative_prerequisite_groups, ordered_prerequisites

RENDERED_UNCONDITIONALLY = ("Vanilla", "Gigastructural Engineering")


def _is_permanently_disabled(block) -> bool:
    """Item 2c (user domain call): a technology whose `potential` block contains a TOP-LEVEL
    (direct-child, not nested inside NOT/OR/AND or an opaque sub-scope) literal leaf `always = no`
    is disabled content, not uncertain content -- the mod author left it in the files but made it
    permanently unreachable by any empire, ever, regardless of axis facts. `potential`'s top level
    is an implicit AND, so one unconditional-FALSE direct child makes the whole block FALSE no
    matter what other (now-moot) siblings remain -- confirmed real: `giga_tech_orbital_elysium`
    keeps `giga_can_use_habitables = yes` and more as dead siblings alongside its own top-level
    `always = no #disabled since 4.0`, not a clean singleton the way
    `giga_tech_aeternite_weaponry` is. Deliberately does NOT descend into nested NOT/OR/AND or
    opaque sub-scopes (count_country, weight_modifier, ...) looking for a deeper `always = no` --
    same scope discipline `pipeline.edges`/`pipeline.availability` already use, and the real corpus
    has no such nested case among rendered technologies (verified: the survey behind this
    implementation ran the full evaluator over every rendered technology and found exactly the
    same 4 unconditionally-uncertain-via-`always`-leaf technologies this function excludes;
    `giga_09_ehof_other.txt`'s own `always = no` occurrence sits inside a nested sub-scope this
    function correctly leaves untouched, matching the evaluator's own established opaque-scope
    treatment). Never a `potential` block absent entirely (`None` means unconditionally available,
    not disabled). Real corpus, confirmed by direct inspection, not a naming-pattern guess: exactly
    4 technologies match -- `giga_tech_aeternite_weaponry`/`giga_tech_interstellar_ringworld`/
    `giga_tech_orbital_elysium`/`giga_tech_stellar_ring_habitat`."""
    for item in block.items:
        if not isinstance(item, Assignment) or item.key_name != "potential":
            continue
        potential_value = item.value
        if not hasattr(potential_value, "items"):
            return False
        for leaf in potential_value.items:
            if not isinstance(leaf, Assignment):
                continue
            if leaf.key_name == "always" and isinstance(leaf.value, Identifier) and leaf.value.name == "no":
                return True
        return False
    return False


def compute_rendering_scope(technology_history: dict[str, list[TechnologyDefinition]]) -> set[str]:
    """Returns the set of ACOT/AoT technology keys in the rendering-scope closure -- i.e. the
    ADDITIONAL technologies beyond the unconditionally-rendered Vanilla/Gigastructures set.
    `technology_history` is P-15's full occurrence history (`collect_technology_definitions`'s
    output); only each key's winning (last) definition is consulted, matching P-15 resolution.

    D-18: DEPTH-1 ONLY -- a single pass over every unconditionally-rendered technology's own
    `prerequisites` block, no further expansion from the technologies that pass reaches. An
    ACOT/AoT technology reachable only via ANOTHER ACOT/AoT technology's prerequisite chain is
    deliberately not included."""
    winners = {key: occurrences[-1] for key, occurrences in technology_history.items()}

    def prerequisite_keys(key: str) -> list[str]:
        winner = winners.get(key)
        if winner is None:
            return []
        return ordered_prerequisites(winner.block)

    closure: set[str] = set()

    for key, winner in winners.items():
        if winner.source not in RENDERED_UNCONDITIONALLY:
            continue
        for prereq_key in prerequisite_keys(key):
            prereq_winner = winners.get(prereq_key)
            if prereq_winner is not None and prereq_winner.source not in RENDERED_UNCONDITIONALLY:
                closure.add(prereq_key)

    return closure


def compute_off_tree_prerequisites(
    technology_history: dict[str, list[TechnologyDefinition]],
) -> list[tuple[str, str]]:
    """D-18: the accepted cost of depth-1. Returns every `(technology_key, prerequisite_key)` pair
    where `technology_key` IS rendered (unconditionally, or as a depth-1 closure member) but
    `prerequisite_key` is an ACOT/AoT technology that is NOT rendered -- i.e. a prerequisite that
    would have been reachable under the old full-transitive-closure rule but is deliberately
    dropped under depth-1. Every entry here is a real, accepted gap: the rendered technology's own
    card will name a prerequisite that has no node to point to. Used both for diagnostics
    (`pipeline.dataset_emit`) and for the corpus regression test pinning the exact accepted set."""
    winners = {key: occurrences[-1] for key, occurrences in technology_history.items()}
    rendered = rendered_technology_keys(technology_history)

    off_tree: list[tuple[str, str]] = []
    for key in sorted(rendered):
        winner = winners.get(key)
        if winner is None:
            continue
        for prereq_key in ordered_prerequisites(winner.block):
            prereq_winner = winners.get(prereq_key)
            if (
                prereq_winner is not None
                and prereq_winner.source not in RENDERED_UNCONDITIONALLY
                and prereq_key not in rendered
            ):
                off_tree.append((key, prereq_key))
    return off_tree


def rendered_technology_keys(technology_history: dict[str, list[TechnologyDefinition]]) -> set[str]:
    """The full rendered-node key set: every Vanilla/Gigastructural Engineering winning
    definition, plus this corpus's P-16 closure over ACOT/AoT, MINUS Item 2c's permanently-
    disabled technologies (`_is_permanently_disabled` -- `potential = { always = no }`), excluded
    entirely rather than rendered as a locked/uncertain node. Applied to the full unioned set, not
    just the unconditional half, since a disabled technology could in principle appear in either
    (none of the real 4 are ACOT/AoT today, but the rule doesn't assume that)."""
    winners = {key: occurrences[-1] for key, occurrences in technology_history.items()}
    base = {key for key, winner in winners.items() if winner.source in RENDERED_UNCONDITIONALLY}
    full = base | compute_rendering_scope(technology_history)
    return {key for key in full if not _is_permanently_disabled(winners[key].block)}


def compute_alternative_only_gaps(technology_history: dict[str, list[TechnologyDefinition]]) -> set[str]:
    """Diagnostic tripwire, decided on evidence rather than left to guess: P-16's closure stays
    **prerequisite-only** (the requirement is keeping a research *chain* unbroken, and an
    `alternative`/OR-branch member is definitionally not a required link in that chain -- see
    `spec/P-16-mod-requirements.md`). Verified on the real corpus: recomputing the closure with
    `alternative` edges included as reachable makes ZERO difference to depth-1 membership, and all
    4 of the user's named trigger technologies (`tech_dark_matter_power_core_dm/ae/se`,
    `tech_civil_phanon_application`) are reached via a true prerequisite chain, never an OR branch
    (see CLAUDE.md's P-14 survey). This is not a reason to assume it will always be true, though --
    a future corpus refresh could add an ACOT/AoT technology a rendered technology reaches ONLY
    through an `alternative` branch, which depth-1's prerequisite-only rule would then silently
    exclude, risking exactly the "invisible gap" CLAUDE.md's rendering scope section warns against.

    **Rescoped to depth-1, D-18**: this diagnostic now checks the SAME single pass
    `compute_rendering_scope` does (every unconditionally-rendered technology's own block), just
    with `alternative`-group members ALSO treated as traversable at that one depth -- not a
    multi-hop recursive closure the way this function's original (pre-D-18) version was, since
    that would no longer be checking against a like-for-like rule. Returns the ACOT/AoT
    technologies a rendered technology's own `alternative` groups reach that the real depth-1
    prerequisite-only closure doesn't. Never a build failure and never changes what P-16 actually
    renders; a non-empty result here is a signal for a human to look at. Empty on the real corpus
    today (verified, not assumed)."""
    winners = {key: occurrences[-1] for key, occurrences in technology_history.items()}

    def alt_inclusive_prerequisite_keys(key: str) -> list[str]:
        winner = winners.get(key)
        if winner is None:
            return []
        keys = list(ordered_prerequisites(winner.block))
        for group in alternative_prerequisite_groups(winner.block):
            keys.extend(group)
        return keys

    closure: set[str] = set()
    for key, winner in winners.items():
        if winner.source not in RENDERED_UNCONDITIONALLY:
            continue
        for prereq_key in alt_inclusive_prerequisite_keys(key):
            prereq_winner = winners.get(prereq_key)
            if prereq_winner is not None and prereq_winner.source not in RENDERED_UNCONDITIONALLY:
                closure.add(prereq_key)

    return closure - compute_rendering_scope(technology_history)
