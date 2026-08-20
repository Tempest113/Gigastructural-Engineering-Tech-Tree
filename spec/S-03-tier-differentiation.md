# S-3 — Tier differentiation at low zoom

**Requirement.** Tiers MUST remain visually distinguishable when the user is zoomed out. The
recommended approach is to alternate the tier band background between the default tier colour and
a slightly desaturated variant. Alternative approaches achieving clear tier separation are
acceptable.

**The tier range is unbounded**, per P-2. ACOT-tier content pushes tiers to T9 and beyond, and
tier bands are enumerated from the dataset at build time. No fixed upper bound may be assumed
anywhere in this requirement — not in the alternating treatment, the band labelling, or the LOD
thresholds below.

## Acceptance criteria

- At the minimum supported zoom level, a user can identify tier boundaries without reading node
  text.
- ~~**Tier bands are labelled with a sticky header that renders once across the full lane
  stack**~~ **Superseded (Stage 3 visual-fidelity session, later than D-16's row re-axis) — this
  is the SECOND S-03 header criterion overridden by direct user review of the rendered result,
  after the row re-axis already replaced "lane" with "row"; note the pattern so a future session
  doesn't reintroduce either.** A first Stage 3 slice built a real viewport-pinned sticky header
  per this criterion's letter — one band label, one row label, each swapping contents as the
  camera moved. The user rejected it on sight: a banner floating in a fixed screen corner that
  changes what it names as you scroll doesn't visually belong to any of the objects on screen, no
  matter how correctly it tracks "current band"/"current row". The corrected requirement, per the
  same review, is the opposite of "renders once": **a small, subdued tier-band label repeats
  above every row's own populated band cell** (matching v1's treatment, which the user has
  separately confirmed he's happy with — see CLAUDE.md's "Stage 3 visual-fidelity pass" bullet),
  anchored in WORLD space like every other label so it scales and pans with the content instead of
  fighting the viewport for a fixed corner. This costs the "single unbroken vertical span" framing
  the old criterion argued for — a tier's identity is now read from many small repeated labels,
  not one authoritative header — but two independent user reviews (rejecting sticky headers,
  approving v1's repeated-label look) converge on the same answer, so the old framing is retired,
  not patched. Labels are still expected to become illegible at low/fit-to-viewport zoom — this is
  now the INTENDED behaviour, not a shortfall to fix: at overview zoom the user navigates by row
  shape and colour, not by reading text, and world-anchored labels shrinking with zoom is exactly
  what "scaling with the content like everything else" means.
- The alternating treatment does not conflict with, or reduce the contrast of, the node colour
  coding in S-1 or the locked-state treatment in P-13.

**Band header and card tier badge always agree — by construction, not by reconciliation.**
P-2 was corrected from an earlier draft that placed a node by *computed* position (graph depth
after promotion) rather than declared tier; under that superseded model the band header and a
card's own tier badge could diverge (measured at the time: 43% of rendered technologies). That
model is no longer in effect. **A band is a node's own declared `tier` field, full stop** — the
band header showing "Tier 5" and every card inside it carrying a "T5" tier badge is now a
tautology, not something requiring separate reconciliation logic. Computed position still exists
(P-2), but purely as internal geometry for horizontal ordering within a band and for routing
backwards edges — it is never displayed as a number anywhere in the UI, so there is nothing for a
band header to disagree with.

## Level-of-detail shedding table

A **level-of-detail (LOD) system** is implied: at low zoom, node cards progressively drop
indicators, then icons, then reduce to coloured blocks. This table is the single, shared
definition of that sequence — S-1's pattern degradation and every card indicator shed strictly
according to it; no indicator's threshold is decided ad hoc elsewhere.

| Stage | Zoom threshold | Sheds at this stage |
| --- | --- | --- |
| Full detail | ≥ 60% | Nothing. All six indicators, the tier badge, and crisis patterns (S-1) render in full. |
| Label shedding | < 60% | Gate label (icon remains); Repeatable indicator. |
| Secondary badges | < 35% | Rare badge; Mod requirement badge. |
| Tertiary badges | < 20% | Gate icon; Tier badge. |
| Minimal card | < 10% | Dangerous badge — kept longest of the badges, deliberately, since it is safety-critical information. |
| Pattern degradation | < 7% | Crisis-faction background pattern (S-1) — the hexagons, waves, lattices etc. switch to a solid fill of the same background colour. This is the threshold S-1's "below a defined threshold the renderer switches to a solid treatment" resolves to; it is deliberately its own stage, one step before the coloured-block stage below, because the fill colour is still classification-bearing at this zoom level (crisis lanes are still visually distinguishable by colour) even though the pattern detail no longer renders. |
| Coloured block | < 5% | Everything remaining: the node is a flat coloured block (lane/area or crisis-faction colour only, already flat since the stage above). |

**Below the coloured-block threshold, colour-only encoding is an explicit, acceptable exception
to S-1's "colour MUST NOT be the sole carrier" rule.** S-1's non-colour-channel requirement
exists so a user can distinguish classifications *of a node they are looking at*; below 5% zoom
no individual node is readable regardless of encoding, so the exception costs nothing in
practice and inventing a colour-independent treatment for unreadable pixels is not worth the
complexity.

## Implied technical decisions

- Band backgrounds are part of the static layout and SHOULD be drawn as a single background layer
  beneath nodes and connectors, so the cost is independent of node count.
- LOD thresholds are percentages of the tool's default (100%) zoom level, evaluated against the
  same zoom-threshold table S-1's pattern degradation uses — one shared table, not two
  independently tuned ones.
