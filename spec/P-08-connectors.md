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
- **Connector colour is a single neutral, low-contrast colour for every edge, regardless of kind
  or endpoint classification** (`client/src/tokens.ts`'s `EDGE_COLOR`) — corrected from an earlier
  draft of this requirement, which specified colour following the tail's (the technology depended
  upon's) S-1 classification. Implemented and shipped differently, with a stated reason, in Stage
  3 slice 3 (edges): at real corpus density (989 edges, many crossing row/area boundaries — and,
  after D-16's row re-axis, ALSO crossing row boundaries constantly, since rows are now
  categories/factions rather than one broad standard-progression lane), a per-edge tail colour
  would be ambiguous for any edge whose tail and head differ in classification, and would compete
  visually with the cards it runs beneath rather than reading as a distinct rendering layer. This
  spec is corrected to match the shipped implementation rather than left contradicting it — see
  CLAUDE.md's "Slice 3 — edges" bullet for the original decision record.
  **Research area is NOT colour-encoded by connectors at all under this corrected rule** — a
  deliberate, accepted loss (D-16 already accepts the analogous loss for row backgrounds inside
  faction rows; this is the same trade applied to edges), not an oversight. Connectors are still
  visually associated with their endpoints when highlighted or isolated (P-7) — that association
  is structural (which nodes light up), not colour-based.
- **Edge kind (P-14) is the SOLE composed rendering dimension now** (opacity plus line style,
  since colour no longer varies):
  - `prerequisite` edges are **solid**, at full opacity — the most visually prominent, since they
    carry the graph's main structure.
  - `potential-gate` edges are **dashed**, at reduced opacity.
  - `alternative` edges are **dotted**, at further reduced opacity.

  This is the definition P-07 (isolation) and P-14 (alternative-route display) both depend on.
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
- **Backwards edges — an edge whose own declared-tier band is later than its dependent's — are
  real graph structure the router MUST handle, not an edge case to assume away.** D-13
  (`spec/decisions.md`) settles that band placement follows declared tier, not computed depth, so
  these are not rare. **This "1-2 bands back, small and short-range" characterization is scoped
  to `prerequisite` and `alternative` only** — measured at 3.0% of non-repeatable
  `prerequisite`/`alternative` edges, max 2 bands back for both kinds. Route a backwards edge of
  either kind back through the inter-column channel it would otherwise use going forward — same
  channel-reservation mechanism, opposite horizontal direction — so it reads as a deliberate
  right-to-left trace rather than an artefact.
- **`potential-gate` backward edges are a separate population and do NOT fit the characterization
  above.** Measured over the real corpus: 7 backward `potential-gate` edges, span distribution
  `{1 band: 1, 2: 2, 3: 1, 4: 2, 5: 1}`, max **5 bands back** — materially longer-range than
  `prerequisite`/`alternative`. The structural reason: a `has_technology` gate can reference any
  technology anywhere in the tree as an alternative unlock condition, with no reason to sit near
  its owner's declared tier the way a formal prerequisite chain does (e.g. a late-game
  crisis-chain technology gating access to an early-tier vanilla weapon technology). **This spec
  deliberately does NOT prescribe a routing treatment for these here** — designing long-range
  routing without a real rendered canvas to check it against risks guessing wrong. `Edge.bandSpan`
  is emitted on every edge (not just backward ones) specifically so this decision can be made
  against real data. **Card-avoidance closed, later session (`pipeline.layout._route_edges`'s
  card-avoidance rewrite) — the specific TODO below is superseded, not by prescribing a distinct
  long-range treatment, but because the router now routes EVERY edge (any span, any direction)
  through the same card-avoidance mechanism unconditionally, measured to reach 0 real
  card-crossings across all 989 edges including the 7 long-range `potential-gate` backward
  edges.** A distinct VISUAL treatment for especially long spans (a different line style,
  hover-reveal, etc., as opposed to correctness/avoidance) remains open, genuinely undesigned —
  see CLAUDE.md's own bullet for the full router rewrite. ~~**TODO(Stage 3)**: decide whether
  `potential-gate` backward edges reuse the same inter-column channel mechanism (likely fine for
  the 4 edges at span ≤2) or need a distinct treatment for the ones spanning 3+ bands (crossing
  multiple inter-band gutters, not just one) — against an actual rendered canvas, not designed
  blind in this document.~~
- The router MUST additionally reserve **inter-lane gutters** — horizontal channel space between
  each pair of adjacent lanes — for any edge that crosses a lane boundary. Cross-lane edges take
  **priority in channel allocation over same-lane traffic**: they travel further and have fewer
  alternative routes available (a same-lane edge can often be re-ordered vertically within its
  lane to shorten its run; a cross-lane edge cannot avoid crossing the gutter). Channel
  assignment MUST resolve cross-lane edges first, then fit same-lane edges around them.
- Rounded corners SHOULD be produced by quadratic/arc segments at each vertex rather than by
  stroke-linejoin, so the radius is zoom-stable. **Done** (Stage 3 visual-fidelity pass 2, later
  session — this requirement was originally skipped as a scoped simplification in the edge slice,
  sharp H-V-H joins): `client/src/main.ts`'s `roundPolylineCorners` takes the exact server-computed
  polyline (unchanged, no client-side re-routing -- 6 points/4 interior corners since the later
  card-avoidance router rewrite, but the function was already generic over point count) and
  replaces each interior corner with a quadratic-bezier arc, sampled into straight segments, exactly matching this
  guidance's own "quadratic/arc segments... not stroke-linejoin" wording. Radius is
  `tokens.ts`'s `EDGE_CORNER_RADIUS` (12px), clamped per-corner to half of each adjacent segment's
  length so a short segment can't overshoot. Endpoints are always preserved exactly, verified
  numerically for all 989 edges (`window.__tt.checkEdgeEndpointsInCards`).
  ~~Connector colour was also brightened toward v1's light blue-cyan PCB-trace look in the same
  pass (`EDGE_COLOR` `0x5b6472` slate → `0x5cc9e6` cyan, stroke width `2` → `1.4`)~~ **Corrected, a
  later session (EAWAF/Sirenalia correction session)**: that brightening was based on a MISTAKEN
  belief about what v1's own colour actually was, checked against v1's real source
  (`github.com/Tempest113/Gigas-Tech-Tree`, `css/*.css:11`'s `--line: #38363c`, consumed at
  `js/render.js:618`) and found wrong -- v1's real default edge colour is a dark, low-contrast
  GREY, not blue-cyan. `EDGE_COLOR` is now `0x38363c` (v1's real value); the previous `0x5cc9e6`
  is kept as `HOVER_COLOR` (it turns out to be v1's own highlighted-lineage stroke colour,
  `C.accent`, an exactly hover/selection-shaped use), reserved for a hover/selection state this
  client doesn't implement yet. Stroke width stays `1.4`. The single-neutral-colour-for-every-kind
  rule above is UNCHANGED throughout both sessions -- only the shared colour's identity moved, from
  a wrong guess to v1's real value.
  **Router geometry itself also replaced, same session**: the gutter-channel router described
  earlier in this file (the "card-avoidance rewrite," proven zero unrelated-card crossings) was
  REPLACED as the default with a direct port of v1's own chamfered two-bend trace geometry
  (`js/render.js`'s `addEdge`), per the user's explicit rejection of the gutter router's dense-
  parallel-channel look after seeing it rendered -- a deliberate, recorded trade of the proven zero
  crossings for legibility (new measured count: 2,828 crossings across 606/989 edges, nonzero,
  accepted). The gutter router is KEPT as `pipeline.layout._gutter_style_waypoints`, used as a
  fallback for same-band/short/backward edges v1's two-bend shape cannot route without violating a
  minimum stub -- see `pipeline/layout.py`'s `_route_edges` docstring and CLAUDE.md's "EAWAF/
  Sirenalia correction..." bullet for the full writeup.
- The renderer MUST support drawing many thousands of polylines within frame budget; see
  `implementation-notes.md`.
