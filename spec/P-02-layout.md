# P-2 — Tier-based column layout

**Requirement.** Technologies MUST be laid out left-to-right as a directed acyclic graph and
MUST be visually separated into columns by tier. No technology may be rendered to the left of,
or in the same column as, any of its prerequisites.

**The tier range is unbounded.** ACOT-tier content pushes tiers to T9 and beyond. Tier bands
MUST be enumerated from the dataset at build time. No fixed upper bound may appear anywhere in
layout, level-of-detail thresholds, band labelling, or the colour token set.

Repeatable technologies occupy a dedicated terminal column labelled "Repeatables", positioned
after the highest numeric tier.

Tier columns and crisis lanes (P-5) are **orthogonal**: columns run vertically and are assigned
identically regardless of lane; lanes run horizontally and partition the standard-progression
technologies from each crisis faction's. Every technology has exactly one column and one lane. A
crisis-faction technology that is also repeatable occupies the Repeatables column within its own
faction's lane — the two axes compose, neither one overrides the other.

**The column grid is global and single.** Every lane spans the full grid, from T0 (or the lowest
enumerated tier) through the Repeatables column, regardless of what that lane's own technologies
actually use. A lane whose technologies stop at T5 still has T6-through-Repeatables columns; they
render empty. This is required so the shared coordinate space (P-5) stays valid for cross-lane
edge routing (P-8) — a column index means the same tier in every lane, with no per-lane
renumbering — and it is also the honest representation: an empty column is a visible statement
that the faction has no content at that tier, not a gap papered over by compression. Lanes are
fitted **vertically** to their content only (a lane with five technologies is short; one with
fifty is tall); they are never fitted or compressed horizontally.

## Acceptance criteria

- For every edge `(A → B)` where A is a prerequisite of B, `column(B) > column(A)`.
- Every node's column corresponds to its tier band; bands are contiguous and ordered ascending
  left to right, with the repeatables band last.
- Layout is deterministic: the same input dataset produces the same node positions every build.
- The graph contains no cycles. A detected cycle fails the build loudly.
- Adding a technology at a tier higher than any previously seen requires no code change.

## Implied technical decisions

- Declared `tier` and graph depth can disagree. **Tier determines the band; longest-path depth
  determines ordering within and across bands.** If a technology's declared tier is at or below
  that of one of its prerequisites, the build MUST promote it to `max(prereq columns) + 1` and
  MUST emit a warning listing the affected technologies, visible in the `?dev` build (S-2).
- Vertical ordering within a column MUST be computed by a crossing-reduction pass — a
  Sugiyama-style barycentre or median heuristic. Grouping by category or connected component is
  an acceptable additional constraint.
- Layout MUST be computed at build time and stored as coordinates in the dataset. Runtime
  layout of a graph this size is incompatible with P-9 and P-10.
- The layout engine MUST support **multiple horizontal lanes** (the standard-progression lane
  plus one per crisis faction, P-5) sharing one column axis and one coordinate space, with
  independent vertical ordering within each lane, so cross-lane edges still route (P-8). The
  repeatables column is not a separate zone — it is an ordinary terminal column, present within
  every lane that has repeatable technologies.
