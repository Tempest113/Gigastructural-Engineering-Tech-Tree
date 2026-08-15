"""P-14: full three-kind edge typing.

Three edge kinds, kept distinct end to end (`schema/common.schema.json`'s `EdgeKind`):

- **`prerequisite`** — a technology's `prerequisites` block, true (AND-required) members only.
  Extraction: `pipeline.overwrites.ordered_prerequisites`.
- **`alternative`** — a nested `OR` group inside `prerequisites` (P-08/CLAUDE.md's definition,
  not P-14's Requirement-section prose — see `spec/P-14-unconventional-prereqs.md`'s reworded
  Requirement section for why the two readings conflicted and which one won: `Edge.kind` is a
  fixed, profile-invariant base-dataset property, so a "relabelled per selected profile" reading
  is architecturally impossible). Extraction: `pipeline.overwrites.alternative_prerequisite_groups`,
  with a `groupId` assigned per group so members of the same `OR` are distinguishable from two
  separate groups (35 `OR` occurrences span 32 technologies; 3 carry two groups each).
- **`potential-gate`** — every `has_technology` check inside a technology's `potential` block,
  universally (P-14's acceptance criteria), extracted with the SAME scope discipline
  `pipeline.availability._evaluate_node` already uses: only descend into `AND`/`OR`/`NOT`/`NOR`
  wrappers; any other block-valued field (`count_country`, `weight_modifier`, `ai_weight`, ...)
  is an opaque leaf, never searched inside. This discipline is load-bearing, not a style choice —
  a naive unscoped recursive walk found a false self-loop on `tech_ehof_sentient_tier_7`, whose
  `potential` block nests `has_technology = tech_ehof_sentient_tier_7` inside
  `count_country = { limit = { OR = { has_tech_option = ... has_technology = ... } } } }` —
  checking OTHER empires in the galaxy for a scarcity mechanic, not the researching empire's own
  state. `tests/test_edges.py::test_count_country_nested_has_technology_does_not_produce_an_edge`
  is the permanent regression guard for this. `weight_modifier`/`ai_weight` contribute ZERO
  scope-disciplined `has_technology` occurrences on the real corpus (854 of 879 raw occurrences
  are inside opaque sub-scopes like this one) — `potential`-only is not a guess, it's what's left
  once opaque-scope occurrences are excluded from a legitimately universal `potential` extraction.
  `allow` never occurs on any rendered technology today (0/980) — P-3's "potential and allow"
  framing is aspirational; `check_has_technology_under_allow` is a standing diagnostic (never a
  build failure) so a future mod update that introduces one is surfaced, not silently ignored.

**Edge-kind membership is NOT mutually exclusive per `(from, to)` pair.** 4 real pairs are both a
formal `prerequisite` and a `potential-gate` (the same dependency redundantly encoded twice, e.g.
`tech_mega_engineering -> giga_tech_arkship_neutronium_harvester`). Both are emitted; P-3 already
establishes the parallel precedent (a dependency can be both an edge and a gate badge) and nothing
here collapses the two kinds into one record. Collapsing them for display, if ever wanted, is a
Stage 3 rendering decision over the emitted data, not something this module decides.

A negated `has_technology` (inside an odd number of `NOT`/`NOR`) is a NEGATIVE dependency — "must
NOT have researched X" — which has no representation in `EdgeKind` today and would be a wrong
graph if emitted as an ordinary positive dependency edge (P-14: "inverting it silently would
produce a wrong graph"). The real corpus has zero such occurrences under `potential` (confirmed,
not assumed), so this module excludes them from edge output and records them as a diagnostic
instead of guessing at a representation for a case that doesn't exist yet.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .clausewitz.nodes import Assignment, Block, Identifier, StringLiteral
from .overwrites import alternative_prerequisite_groups, ordered_prerequisites

BOOLEAN_WRAPPERS = {"AND", "OR", "NOT", "NOR"}


@dataclass(frozen=True)
class TypedEdge:
    """One P-14 edge. `from_key`/`to_key` follow P-08's fixed direction convention uniformly
    across all three kinds: `from` is the technology depended upon (tail), `to` is the technology
    declaring the dependency (head) -- see this module's docstring and P-08 for the per-kind
    detail of what "depended upon" means for `potential-gate` and `alternative`."""

    from_key: str
    to_key: str
    kind: str  # "prerequisite" | "potential-gate" | "alternative"
    group_id: str | None = None  # only set for kind == "alternative"


@dataclass(frozen=True)
class EdgeExtractionDiagnostics:
    """Standing diagnostics from edge extraction -- never a build failure, exist so a future
    corpus change surfaces a case this module deliberately doesn't guess at, rather than being
    silently dropped or silently mis-extracted."""

    has_technology_under_allow: list[str] = field(default_factory=list)
    negated_potential_gate: list[tuple[str, str]] = field(default_factory=list)  # (target, owner)


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


def _scoped_has_technology(node: Block, negated: bool) -> list[tuple[str | None, bool]]:
    """Mirrors `pipeline.availability._evaluate_node`'s scope discipline exactly: only descend
    into AND/OR/NOT/NOR. Any other block-valued assignment is an opaque leaf -- do not search
    inside it. See this module's docstring for why (the count_country false-self-loop case)."""
    results: list[tuple[str | None, bool]] = []
    for item in node.items:
        if not isinstance(item, Assignment):
            continue
        key_upper = item.key_name.upper()
        if item.key_name == "has_technology":
            results.append((_target_name(item.value), negated))
        elif key_upper in ("NOT", "NOR") and isinstance(item.value, Block):
            results.extend(_scoped_has_technology(item.value, not negated))
        elif key_upper in ("AND", "OR") and isinstance(item.value, Block):
            results.extend(_scoped_has_technology(item.value, negated))
        # else: opaque leaf (count_country, weight_modifier-shaped sub-scopes, has_global_flag,
        # ...) -- do not descend, per this module's docstring.
    return results


def extract_prerequisite_edges(technology_key: str, block: Block) -> list[TypedEdge]:
    return [
        TypedEdge(from_key=prereq, to_key=technology_key, kind="prerequisite")
        for prereq in ordered_prerequisites(block)
    ]


def extract_alternative_edges(technology_key: str, block: Block) -> list[TypedEdge]:
    """Each `OR` group gets its own `groupId`, `f"{technology_key}#alt{index}"` (0-based,
    declaration order) -- without it, two 2-member groups on the same technology would be
    indistinguishable from one 4-member group."""
    edges: list[TypedEdge] = []
    for index, members in enumerate(alternative_prerequisite_groups(block)):
        group_id = f"{technology_key}#alt{index}"
        for member in members:
            edges.append(TypedEdge(from_key=member, to_key=technology_key, kind="alternative", group_id=group_id))
    return edges


def extract_potential_gate_edges(
    technology_key: str, block: Block, diagnostics: EdgeExtractionDiagnostics
) -> list[TypedEdge]:
    """`potential`-only, universally, per P-14's acceptance criteria -- scope-disciplined per
    this module's docstring. Also runs the `allow`-block diagnostic (P-3's "potential and allow"
    framing; `allow` never occurs on a rendered technology today, but this exists to make a
    future appearance visible rather than silently out of scope)."""
    edges: list[TypedEdge] = []

    potential = _field(block, "potential")
    if potential is not None and isinstance(potential.value, Block):
        for target, negated in _scoped_has_technology(potential.value, False):
            if target is None:
                continue
            if negated:
                diagnostics.negated_potential_gate.append((target, technology_key))
                continue
            edges.append(TypedEdge(from_key=target, to_key=technology_key, kind="potential-gate"))

    allow = _field(block, "allow")
    if allow is not None and isinstance(allow.value, Block):
        for target, _negated in _scoped_has_technology(allow.value, False):
            if target is not None:
                diagnostics.has_technology_under_allow.append(technology_key)
                break

    return edges


def compute_typed_edges(
    rendered_blocks: dict[str, Block],
) -> tuple[list[TypedEdge], EdgeExtractionDiagnostics]:
    """Full P-14 edge set over `rendered_blocks` (P-16's rendered node set -- technology key ->
    its winning, `inline_script`-expanded block). Edges with either endpoint outside
    `rendered_blocks` are dropped defensively (measured: this never happens on the real corpus
    for `alternative`/`potential-gate` -- see CLAUDE.md's P-14 survey -- but nothing here assumes
    that holds forever)."""
    diagnostics = EdgeExtractionDiagnostics()
    edges: list[TypedEdge] = []

    for key, block in rendered_blocks.items():
        edges.extend(extract_prerequisite_edges(key, block))
        edges.extend(extract_alternative_edges(key, block))
        edges.extend(extract_potential_gate_edges(key, block, diagnostics))

    edges = [e for e in edges if e.from_key in rendered_blocks and e.to_key in rendered_blocks]
    return edges, diagnostics
