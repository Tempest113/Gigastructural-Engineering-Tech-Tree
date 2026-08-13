# P-4 — Category filtering

**Requirement.** Users MUST be able to filter the visible tech tree by technology category (e.g.
Computing, Voidcraft, Psionics, Materials, Field Manipulation, Biology, Statecraft, Industry,
Military Theory, New Worlds, Propulsion, Particles).

## Acceptance criteria

- The category list is derived from the dataset at build time; it is never a hard-coded UI list.
- Multiple categories can be selected simultaneously; the filter is additive (union of selected
  categories).
- Filtering is non-destructive: clearing the filter restores the full view without a page reload.
- Filter state is encoded in the URL.
- Filtering MUST NOT reflow the layout. Filtered-out nodes are hidden or dimmed in place, so that
  node positions remain stable and the user's spatial memory is preserved.

## Implied technical decisions

- Because layout is static (P-2), filtering is a *visibility* operation over a fixed coordinate
  space, not a re-layout. Edges with at least one hidden endpoint MUST be hidden or dimmed
  consistently with their endpoints.
- Category filters MUST compose with crisis filters (P-5), search (P-6) and isolation (P-7).
  Composition semantics are specified in `implementation-notes.md`.
