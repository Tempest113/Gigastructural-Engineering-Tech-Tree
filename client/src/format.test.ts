import { describe, expect, it } from "vitest";
import { formatCost, formatRepeatableBadgeLabel, showCostPanel } from "./format";

describe("formatCost", () => {
  it("rounds and thousands-groups a positive cost", () => {
    expect(formatCost(123456.7)).toBe("123,457");
  });

  it("passes null through unchanged", () => {
    expect(formatCost(null)).toBeNull();
  });

  it("formats zero as the literal string, not null", () => {
    // showCostPanel is what decides whether zero is DISPLAYED at all -- formatCost itself just
    // formats whatever number it's given.
    expect(formatCost(0)).toBe("0");
  });
});

describe("showCostPanel", () => {
  it("hides the panel for a null (unresolvable) cost", () => {
    expect(showCostPanel(null)).toBe(false);
  });

  it("hides the panel for a literal zero cost", () => {
    expect(showCostPanel(0)).toBe(false);
  });

  it("shows the panel for any positive cost", () => {
    expect(showCostPanel(1)).toBe(true);
    expect(showCostPanel(2500)).toBe(true);
  });
});

describe("formatRepeatableBadgeLabel", () => {
  it("prefixes a finite level count with ×", () => {
    expect(formatRepeatableBadgeLabel(5)).toBe("×5");
  });

  it("renders an infinite repeatable as the bare infinity glyph", () => {
    // Faithfully extracted from main.ts's existing behaviour -- see format.ts's own docstring
    // for why this doesn't match CLAUDE.md's "×∞" wording (a known, unfixed pre-existing gap,
    // out of scope for this session).
    expect(formatRepeatableBadgeLabel(null)).toBe("∞");
  });
});
