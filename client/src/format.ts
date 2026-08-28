// Pure display-formatting helpers, extracted out of `main.ts`'s render/popup closures (which
// duplicated the same `Math.round(...).toLocaleString("en-US")` expression at each call site)
// so they can be unit tested directly (client test-infrastructure session) without a Pixi/DOM
// render pass.

/** P-12.2/S-1: research cost, rounded and thousands-grouped for display. `null` in, `null` out --
 * the caller decides whether a missing cost hides the whole cost panel (see `showCostPanel`
 * below); this function never invents a placeholder number for it. */
export function formatCost(cost: number | null): string | null {
  if (cost === null) return null;
  return Math.round(cost).toLocaleString("en-US");
}

/** CLAUDE.md's Repeatables rule: "a literal zero cost and an unresolvable (`null`) cost both
 * render NO cost panel, card and popup alike -- the distinction is meaningless to an end user."
 */
export function showCostPanel(cost: number | null): boolean {
  return cost !== null && cost !== 0;
}

/** CLAUDE.md's Repeatables rule: "shown as `Repeatable: ×N` or `×∞`." Faithfully extracted from
 * `main.ts`'s existing node-badge logic, unchanged -- that existing logic renders a bare `"∞"`
 * for an infinite repeatable (no `×` prefix), which does not match the spec's own `×∞` wording.
 * Kept as-is here (extraction, not a fix) since fixing card-badge display is out of this
 * session's scope; flagged for a follow-up. */
export function formatRepeatableBadgeLabel(levels: number | null): string {
  return levels === null ? "∞" : `×${levels}`;
}
