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

from .overwrites import TechnologyDefinition, alternative_prerequisite_groups, ordered_prerequisites

RENDERED_UNCONDITIONALLY = ("Vanilla", "Gigastructural Engineering")


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
    definition, plus this corpus's P-16 closure over ACOT/AoT."""
    winners = {key: occurrences[-1] for key, occurrences in technology_history.items()}
    base = {key for key, winner in winners.items() if winner.source in RENDERED_UNCONDITIONALLY}
    return base | compute_rendering_scope(technology_history)


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
