// Level-of-detail tiers, driven by zoom percentage. spec/S-03-tier-differentiation.md's
// "Level-of-detail shedding table" is the single, shared definition of what sheds at what zoom
// threshold. Badges slice (reconciliation session): replaces the previous 3-tier simplification
// (which existed only because rare/dangerous/gate/repeatable/mod-requirement badges didn't exist
// yet to hang the real table on -- see git history of this file) with S-03's real 7-stage table,
// verbatim:
//
//   | Stage              | Threshold | Sheds |
//   | Full detail        | >= 60%    | nothing |
//   | Label shedding      | < 60%    | gate label (icon remains); repeatable indicator |
//   | Secondary badges    | < 35%    | rare badge; mod requirement badge |
//   | Tertiary badges     | < 20%    | gate icon; tier badge |
//   | Minimal card        | < 10%    | dangerous badge (kept longest, safety-critical) |
//   | Pattern degradation | < 7%     | crisis-faction pattern -> solid fill |
//   | Coloured block      | < 5%     | everything remaining: icon, name, cost -> flat block |
//
// Real correction from the old simplification: the previous ladder shed the ICON (and reduced to
// a flat block) at < 10%, documented at the time as "a conservative simplification... nothing
// left to shed between 10% and 5%" since no real badges existed to occupy that gap. Under the
// REAL table, the icon/name/cost are NOT named at any stage before "Coloured block" -- they are
// exactly the "everything remaining" that stage sheds at < 5%, one stage later than the old
// simplification had it. The dangerous badge (< 10%) is the only thing between the tertiary-badge
// stage and the coloured-block stage now that real badges fill that gap.

export type LodTier = "full" | "reduced" | "minimal";

// Card CONTENT (icon, name, cost) sheds only at the final "Coloured block" stage -- see the
// correction note above.
export const CONTENT_SHED_THRESHOLD = 0.05;
export const NAME_SHED_THRESHOLD = CONTENT_SHED_THRESHOLD;
export const COST_SHED_THRESHOLD = CONTENT_SHED_THRESHOLD;
export const ICON_SHED_THRESHOLD = CONTENT_SHED_THRESHOLD;

// Per-indicator thresholds, named exactly after S-03's own stage names.
export const GATE_LABEL_SHED_THRESHOLD = 0.60; // "Label shedding" -- gate icon remains
export const REPEATABLE_SHED_THRESHOLD = 0.60; // "Label shedding"
export const RARE_BADGE_SHED_THRESHOLD = 0.35; // "Secondary badges"
export const MOD_REQUIREMENT_BADGE_SHED_THRESHOLD = 0.35; // "Secondary badges"
export const GATE_ICON_SHED_THRESHOLD = 0.20; // "Tertiary badges"
export const TIER_BADGE_SHED_THRESHOLD = 0.20; // "Tertiary badges"
export const DANGEROUS_BADGE_SHED_THRESHOLD = 0.10; // "Minimal card" -- kept longest

// S-03's pattern-degradation row: faction row-backing patterns go solid (accent motif dropped,
// flat base colour only) below 7% zoom.
export const PATTERN_SOLID_THRESHOLD = 0.07;

// `LodTier`/`tierForScale` remain as a coarse three-bucket status-line summary (used only by
// `updateStatusLine`'s human-readable report), NOT as what actually drives per-indicator
// visibility any more -- each indicator now checks its own named threshold above directly. "full"
// now means "content + at least the longest-surviving badge visible" (>= 10%, since that's the
// last badge threshold), "reduced" the pattern-degradation band, "minimal" the flat-block stage.
export function tierForScale(scale: number): LodTier {
  if (scale >= DANGEROUS_BADGE_SHED_THRESHOLD) return "full";
  if (scale >= CONTENT_SHED_THRESHOLD) return "reduced";
  return "minimal";
}

export function tierLabel(tier: LodTier): string {
  switch (tier) {
    case "full":
      return "full (content + surviving badges)";
    case "reduced":
      return "reduced (rect+icon+name, badges shed)";
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
