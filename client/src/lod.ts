// Level-of-detail tiers, driven by zoom percentage. spec/S-03-tier-differentiation.md's
// "Level-of-detail shedding table" is the single, shared definition of what sheds at what zoom
// threshold. This slice's card carries icon, name, cost and a tier badge (rare/dangerous/gate/
// repeatable/mod-requirement badges are still the NEXT slice's work, per this slice's own scope
// note) -- folded into this one shared ladder rather than a parallel one:
//   - Name text AND cost text shed together at S-03's "Tertiary badges" boundary (< 20%) -- at
//     that screen size both are already illegible, and it's the same boundary S-03 sheds its own
//     tertiary badges at.
//   - The tier badge sheds at the same < 20% boundary, per S-03's table (tier badge is one of the
//     badges shed at the "Tertiary badges" stage).
//   - The icon sheds (and the card becomes a flat coloured block) at S-03's "Minimal card" stage
//     (< 10%), not the literal "Coloured block" row's 5% -- with rare/dangerous/gate/repeatable/
//     mod-requirement badges not yet built, there is nothing left to shed between 10% and 5% for
//     this card, so flattening at 10% is a conservative simplification, not a new threshold.
// Replace this file's ladder with the real 7-stage table once the remaining badges are built.

export type LodTier = "full" | "reduced" | "minimal";

export const NAME_SHED_THRESHOLD = 0.20; // reuses S-03's "Tertiary badges" boundary
export const COST_SHED_THRESHOLD = NAME_SHED_THRESHOLD; // sheds with the name, per this file's own table
export const TIER_BADGE_SHED_THRESHOLD = NAME_SHED_THRESHOLD; // S-03: tier badge is a tertiary badge
export const ICON_SHED_THRESHOLD = 0.10; // reuses S-03's "Minimal card" boundary

// S-03's pattern-degradation row: faction row-backing patterns go solid (accent motif dropped,
// flat base colour only) below 7% zoom -- unrelated to the node-card ladder above, but the same
// shared-table discipline: reuse S-03's own named boundary rather than inventing one.
export const PATTERN_SOLID_THRESHOLD = 0.07;

export function tierForScale(scale: number): LodTier {
  if (scale >= NAME_SHED_THRESHOLD) return "full";
  if (scale >= ICON_SHED_THRESHOLD) return "reduced";
  return "minimal";
}

export function tierLabel(tier: LodTier): string {
  switch (tier) {
    case "full":
      return "full (rect+icon+name)";
    case "reduced":
      return "reduced (rect+icon)";
    case "minimal":
      return "minimal (flat block)";
  }
}

// Edge LOD (Stage 3 slice 3). S-03's shedding table doesn't cover edges at all -- it only names
// thresholds for card badges and the crisis pattern (see the node-LOD comment above). These two
// thresholds are chosen to ALIGN with S-03's existing 35%/20% boundaries (S-03's "Secondary
// badges: <35%" and "Tertiary badges: <20%" rows) purely so this project keeps one small family
// of zoom breakpoints instead of a second, arbitrary set -- they are not derived from any spec
// row about edges, because no such row exists.
//   - < 35%: shed `alternative` and `potential-gate` edges entirely (the two lower-priority kinds
//     per P-08's own opacity ordering), and shed ALL arrowheads, including on the `prerequisite`
//     edges that remain -- at this zoom an arrowhead is a few screen px and reads as noise, while
//     the solid prerequisite trunk lines still carry real structure.
//   - < 20%: shed every edge, including `prerequisite` -- matches node LOD's own "Tertiary
//     badges"/name-text boundary, so cards and edges thin out together rather than edges lingering
//     after names have already gone illegible.
export type EdgeLodTier = "full" | "reduced" | "none";

export const EDGE_PARTIAL_SHED_THRESHOLD = 0.35;
// EAWAF/v1-routing session: lowered 0.20 -> 0.166, per the user's explicit request that edges
// reappear "one step further zoomed out" than the previously observed 21.5% (the status strip's
// own `Zoom: N%` figure, i.e. `camera.getScale() * 100` -- the same `scale` value this function
// receives directly, so this threshold and the status strip always agree by construction). The
// new value is stated exactly as the user wants it reported: edges reappear at 16.6% zoom.
export const EDGE_FULL_SHED_THRESHOLD = 0.166;

export function edgeTierForScale(scale: number): EdgeLodTier {
  if (scale >= EDGE_PARTIAL_SHED_THRESHOLD) return "full";
  if (scale >= EDGE_FULL_SHED_THRESHOLD) return "reduced";
  return "none";
}

export function edgeTierLabel(tier: EdgeLodTier): string {
  switch (tier) {
    case "full":
      return "full (all kinds + arrows)";
    case "reduced":
      return "reduced (prerequisite only, no arrows)";
    case "none":
      return "none (all edges hidden)";
  }
}
