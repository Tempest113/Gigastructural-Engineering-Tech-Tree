"""P-16: rendering-scope closure.

CLAUDE.md's "Scope of ACOT and AoT": the tree renders Vanilla and Gigastructural Engineering
technologies unconditionally, plus ACOT/AoT technologies only where they fall in the
**rendering-scope closure** of a rendered technology -- `prerequisites` edges only, pooled
across all twelve profiles, so a rendered technology's prerequisite chain is never broken by an
invisible gap. An ACOT/AoT technology with no rendered descendant is not emitted as a node.

This is the first actual pipeline implementation of the rule HANDOFF.md's "P-16 rendering-scope
closure -- measured, not yet implemented" section computed by hand: 7 ACOT/AoT technologies (6
ACOT + 1 AoT), max depth 2, seeded from exactly 4 direct Vanilla/Gigastructures references. This
module reproduces that measurement as code so it can be re-run after any corpus refresh instead
of trusted as a one-off manual result.
"""

from __future__ import annotations

from .overwrites import TechnologyDefinition, alternative_prerequisite_groups, ordered_prerequisites

RENDERED_UNCONDITIONALLY = ("Vanilla", "Gigastructural Engineering")


def compute_rendering_scope(technology_history: dict[str, list[TechnologyDefinition]]) -> set[str]:
    """Returns the set of ACOT/AoT technology keys in the rendering-scope closure -- i.e. the
    ADDITIONAL technologies beyond the unconditionally-rendered Vanilla/Gigastructures set.
    `technology_history` is P-15's full occurrence history (`collect_technology_definitions`'s
    output); only each key's winning (last) definition is consulted, matching P-15 resolution.
    """
    winners = {key: occurrences[-1] for key, occurrences in technology_history.items()}

    def prerequisite_keys(key: str) -> list[str]:
        winner = winners.get(key)
        if winner is None:
            return []
        return ordered_prerequisites(winner.block)

    closure: set[str] = set()
    frontier: list[str] = []

    for key, winner in winners.items():
        if winner.source not in RENDERED_UNCONDITIONALLY:
            continue
        for prereq_key in prerequisite_keys(key):
            prereq_winner = winners.get(prereq_key)
            if prereq_winner is not None and prereq_winner.source not in RENDERED_UNCONDITIONALLY:
                if prereq_key not in closure:
                    closure.add(prereq_key)
                    frontier.append(prereq_key)

    while frontier:
        key = frontier.pop()
        for prereq_key in prerequisite_keys(key):
            prereq_winner = winners.get(prereq_key)
            if prereq_winner is not None and prereq_winner.source not in RENDERED_UNCONDITIONALLY:
                if prereq_key not in closure:
                    closure.add(prereq_key)
                    frontier.append(prereq_key)

    return closure


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
    `alternative` edges included as reachable makes ZERO difference -- same 7-technology closure,
    same 980 rendered nodes, and all 4 of the user's named trigger technologies
    (`tech_dark_matter_power_core_dm/ae/se`, `tech_civil_phanon_application`) are reached via a
    true prerequisite chain, never an OR branch (see CLAUDE.md's P-14 survey). This is not a
    reason to assume it will always be true, though -- a future corpus refresh could add an
    ACOT/AoT technology reachable ONLY through an alternative branch, which the prerequisite-only
    rule would then silently exclude, risking exactly the "invisible gap" CLAUDE.md's rendering
    scope section warns against.

    This function is the mitigation: it computes the SAME closure but with `alternative`-group
    members also treated as traversable, and returns the technologies that closure reaches but
    the real (prerequisite-only) closure doesn't -- i.e. the ACOT/AoT technologies that would be
    silently dropped if a rendered technology ever gains an alternative-only route to one. Never
    a build failure and never changes what P-16 actually renders; a non-empty result here is a
    signal for a human to look at, not something this function decides on its own. Empty on the
    real corpus today (verified, not assumed)."""
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
    frontier: list[str] = []

    for key, winner in winners.items():
        if winner.source not in RENDERED_UNCONDITIONALLY:
            continue
        for prereq_key in alt_inclusive_prerequisite_keys(key):
            prereq_winner = winners.get(prereq_key)
            if prereq_winner is not None and prereq_winner.source not in RENDERED_UNCONDITIONALLY:
                if prereq_key not in closure:
                    closure.add(prereq_key)
                    frontier.append(prereq_key)

    while frontier:
        key = frontier.pop()
        for prereq_key in alt_inclusive_prerequisite_keys(key):
            prereq_winner = winners.get(prereq_key)
            if prereq_winner is not None and prereq_winner.source not in RENDERED_UNCONDITIONALLY:
                if prereq_key not in closure:
                    closure.add(prereq_key)
                    frontier.append(prereq_key)

    return closure - compute_rendering_scope(technology_history)
