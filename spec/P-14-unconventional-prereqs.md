# P-14 — Unconventional prerequisite handling

**Requirement.** The tool MUST correctly parse and represent unconventional prerequisite
definitions, including `has_technology = x` checks appearing inside a `potential` block rather
than a `prerequisites` block. This pattern is used so that one empire type can research a
technology through the normal prerequisite chain while a different empire type (e.g. nomads, for
whom the standard prerequisite is inaccessible) can access the same technology under different
conditions. **Both access paths MUST be represented accurately.**

## Acceptance criteria

- The parser extracts technology dependencies from `prerequisites` blocks **and** from
  `has_technology` checks located within `potential` and other trigger blocks.
- Each extracted dependency records: the technology it depends on, the block it came from
  (`prerequisites` vs. `potential` vs. other), and the empire-type conditions under which it
  applies.
- A technology reachable by two different routes for two different empire types renders **both**
  routes: the applicable route is shown as a `prerequisite` edge for the selected empire type,
  and the alternative route renders as an `alternative` edge, and is also listed in the detail
  popup as "Alternative access path".
- The detail popup's research path (P-12.9) uses the route valid for the selected empire type.
- Dependencies extracted from trigger blocks are visually distinguishable from formal
  prerequisites by edge kind, since they behave differently in game (they gate availability
  rather than forming the research chain). P-8 owns the concrete line style for each edge kind;
  this file only owns the classification.
- Every `has_technology` check inside a `potential` block produces a `potential-gate` edge,
  **universally** — this extraction is unconditional and has no allowlist. P-3 layers a second,
  curated pass on top: a subset of these edges additionally match a recognised pattern in the
  gate-pattern registry and get a card badge as well as the edge. A technology being both an edge
  and a badge is expected, not a classification conflict — see P-3.

## Implied technical decisions

- The edge model MUST support **typed, conditional edges**: `{ from, to, kind: "prerequisite" |
  "potential-gate" | "alternative", appliesToEmpireTypes: [...] }`. A plain unlabelled adjacency
  list cannot satisfy this requirement.
- Trigger blocks may contain arbitrary boolean structure (`OR`, `AND`, `NOT`, `NOR`). The
  extractor MUST preserve this structure rather than flattening it, because a `has_technology`
  inside a `NOT` is a *negative* dependency and inverting it silently would produce a wrong graph.
- Conditions the evaluator cannot resolve MUST be recorded as `unknown` and reported, never
  assumed true or false (`implementation-notes.md`).
