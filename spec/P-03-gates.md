# P-3 — Gate indicators

**Requirement.** Every technology gated behind a non-prerequisite unlock condition MUST display
a visually prominent gate indicator on its node, rendering the associated icon alongside the
gate's localised name — for example the Cosmogenesis perk icon paired with "Needs Cosmogenesis".

Gates include, at minimum: Cosmogenesis, Galactic Wonders and Gigastructural Constructs
ascension perks, and the Tetradimensional Engineering technology.

A gate is a condition on **empire state**. A dependency on another mod is not a gate — see
P-16.

Every `has_technology` check inside a `potential` block produces a typed `potential-gate` edge,
universally, per P-14. Gate detection (below) is a curated display allowlist layered on top of
that universal edge pass: a technology whose `potential-gate` edge matches a recognised pattern
in the gate registry is **both** an edge and a badge. This is not double-classification — the
edge is the complete, mechanical record of the dependency; the badge is an editorial decision
that this particular dependency is important enough to surface prominently on the card. See P-14
for the edge side.

## Acceptance criteria

- The gate indicator renders inside the node card and remains legible at default zoom.
- The gate icon renders as an image, never substituted with a glyph, emoji or text-only marker.
- Gate labels are localised strings sourced from the mod's localisation files, never hard-coded
  in application source.
- A technology with no gate renders no indicator and no empty placeholder row.
- A gate is displayed regardless of the selected empire profile. Selecting a profile never
  suppresses a gate indicator.

## Implied technical decisions

- **A technology may have more than one gate.** The model stores gates as an ordered list, the
  first element being the primary gate, surfaced in the popup per P-12.7. Node cards render the
  primary gate; where space permits, additional gates render as compact secondary badges.
- Ordering is by a checked-in priority table in the gate-pattern registry, with ascension perks
  outranking technology gates (D-3). Source declaration order is not used.
- Gate detection is a **classification pass** over trigger blocks, run after the universal
  `potential-gate` edge extraction of P-14: the build inspects each technology's `potential` and
  `allow` conditions for recognised gate patterns using a checked-in, extensible gate-pattern
  registry. Unrecognised conditions MUST NOT be silently dropped — the build reports them.
  Matching the registry never removes or alters the underlying edge; it only adds a badge.
- Gate icons MUST be extracted from mod and base-game assets during Stage 1 and packed into the
  atlases. Icon paths MUST NOT be manually maintained.
