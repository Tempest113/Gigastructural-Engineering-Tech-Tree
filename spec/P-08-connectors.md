# P-8 — Circuit-trace connection lines

**Requirement.** Technologies MUST be connected by lines styled to resemble printed-circuit-board
traces: orthogonal (axis-aligned) routing with rounded corners or equivalent PCB-aesthetic
styling.

## Acceptance criteria

- Connectors run in horizontal and vertical segments only; corners are rounded at a consistent
  radius.
- Connectors do not pass through node cards.
- **Every connector runs from the technology depended upon to the technology declaring the
  dependency** — the same direction as a `prerequisite` edge, so all three edge kinds (P-14) read
  consistently left-to-right regardless of kind. This fixes the meaning of P-14's `{ from, to,
  kind }` edge schema: `from` is always the technology depended upon (the tail), `to` is always
  the technology declaring the dependency (the head), for every kind. For a `potential-gate` edge,
  "the technology depended upon" is the technology named in the `has_technology` check, not the
  technology whose `potential` block contains the check — the check's *target*, not its *owner*.
  For an `alternative` edge, likewise: the alternative prerequisite is the tail, the technology it
  unlocks is the head.
- **Connector colour follows the tail** — the technology depended upon, per S-1's classification
  — for every edge kind, not just `prerequisite`. For a `potential-gate` edge this again means the
  technology named in the `has_technology` check, matching the direction rule above: direction and
  colour attribution use the same endpoint, not two different ones. Connectors are visually
  associated with their endpoints when highlighted or isolated.
- **Edge kind (P-14) is a second, composed rendering dimension, independent of colour:**
  - `prerequisite` edges are **solid**, at full opacity — the most visually prominent, since they
    carry the graph's main structure.
  - `potential-gate` edges are **dashed**, at reduced opacity.
  - `alternative` edges are **dotted**, at further reduced opacity.

  Colour (the tail's classification) and line style (edge kind) compose independently: a
  `potential-gate` edge whose `has_technology` check targets a Physics technology is a dashed
  blue line, never a distinct colour of its own. This is the definition P-07 (isolation) and P-14
  (alternative-route display) both depend on.
- Overlapping parallel runs are separated by a consistent channel spacing so that individual
  traces remain traceable by eye.
- Edges crossing a lane boundary (P-5) route through a dedicated inter-lane gutter, never by
  passing through another lane's node-card region.

## Implied technical decisions

- Edge routes MUST be **computed at build time** and stored as polyline point lists in the
  dataset. Runtime orthogonal routing with obstacle avoidance across a graph of this size is not
  compatible with P-9/P-10.
- The router MUST reserve **inter-column channels** for vertical runs and assign each edge a
  channel index to prevent collinear overlap, so that several traces sharing a corridor remain
  separated at distinct offsets rather than drawing on top of one another.
- The router MUST additionally reserve **inter-lane gutters** — horizontal channel space between
  each pair of adjacent lanes — for any edge that crosses a lane boundary. Cross-lane edges take
  **priority in channel allocation over same-lane traffic**: they travel further and have fewer
  alternative routes available (a same-lane edge can often be re-ordered vertically within its
  lane to shorten its run; a cross-lane edge cannot avoid crossing the gutter). Channel
  assignment MUST resolve cross-lane edges first, then fit same-lane edges around them.
- Rounded corners SHOULD be produced by quadratic/arc segments at each vertex rather than by
  stroke-linejoin, so the radius is zoom-stable.
- The renderer MUST support drawing many thousands of polylines within frame budget; see
  `implementation-notes.md`.
