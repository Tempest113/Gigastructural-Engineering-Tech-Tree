# P-2 — Tier-based column layout

**Requirement.** Technologies MUST be laid out left-to-right as a directed acyclic graph and
MUST be visually separated into columns by tier. No technology may be rendered to the left of,
or in the same column as, any of its prerequisites.

**The tier range is unbounded.** ACOT-tier content pushes tiers to T9 and beyond. Tier bands
MUST be enumerated from the dataset at build time. No fixed upper bound may appear anywhere in
layout, level-of-detail thresholds, band labelling, or the colour token set.

Repeatable technologies occupy a dedicated terminal band labelled "Repeatables", positioned
after the highest numeric tier.

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
- The layout engine MUST support **multiple layout zones** with independent internal ordering
  but a shared coordinate space, so crisis regions (P-5) and the repeatables band can be
  positioned separately while cross-zone edges still route (P-8).
