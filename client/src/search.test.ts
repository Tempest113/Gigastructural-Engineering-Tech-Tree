import { describe, expect, it } from "vitest";
import { rankSearchMatches, tokenizeQuery } from "./search";

describe("tokenizeQuery", () => {
  it("lower-cases and splits on non-alphanumeric runs", () => {
    expect(tokenizeQuery("Zero-Point Power!")).toEqual(["zero", "point", "power"]);
  });

  it("drops empty tokens from leading/trailing/duplicate separators", () => {
    expect(tokenizeQuery("  __zero__point__  ")).toEqual(["zero", "point"]);
  });

  it("returns an empty array for a query with no alphanumeric content", () => {
    expect(tokenizeQuery("   ---   ")).toEqual([]);
  });
});

describe("rankSearchMatches", () => {
  const entries = [
    { technologyId: "tech_zero_point_power", tokens: ["zero", "point", "power", "tech", "zero_point_power"] },
    { technologyId: "tech_zero_point_metabolism", tokens: ["zero", "point", "metabolism", "tech"] },
    { technologyId: "tech_dark_matter_power_core_ae", tokens: ["dark", "matter", "power", "core", "ae", "tech"] },
  ];
  const nameOf = (id: string): string =>
    ({
      tech_zero_point_power: "Zero Point Power",
      tech_zero_point_metabolism: "Zero Point Metabolism",
      tech_dark_matter_power_core_ae: "Dark Matter Power Core",
    })[id]!;

  it("ranks an exact name match first", () => {
    const matches = rankSearchMatches("Zero Point Power", entries, nameOf);
    expect(matches[0]).toEqual({ id: "tech_zero_point_power", rank: 0 });
  });

  it("ranks a name-starts-with match above a token-only match", () => {
    const matches = rankSearchMatches("Zero Point", entries, nameOf);
    const ranks = Object.fromEntries(matches.map((m) => [m.id, m.rank]));
    expect(ranks.tech_zero_point_power).toBe(1);
    expect(ranks.tech_zero_point_metabolism).toBe(1);
  });

  it("requires every query token to prefix-match some entry token (AND across words)", () => {
    const matches = rankSearchMatches("power core", entries, nameOf);
    expect(matches.map((m) => m.id)).toEqual(["tech_dark_matter_power_core_ae"]);
  });

  it("matches on a token prefix, not just a whole token", () => {
    const matches = rankSearchMatches("pow", entries, nameOf);
    expect(matches.map((m) => m.id).sort()).toEqual(
      ["tech_zero_point_power", "tech_dark_matter_power_core_ae"].sort()
    );
  });

  it("returns no matches for an empty/whitespace-only query", () => {
    expect(rankSearchMatches("   ", entries, nameOf)).toEqual([]);
  });

  it("breaks a rank tie by id, ascending", () => {
    const matches = rankSearchMatches("tech", entries, nameOf);
    expect(matches.map((m) => m.id)).toEqual([
      "tech_dark_matter_power_core_ae",
      "tech_zero_point_metabolism",
      "tech_zero_point_power",
    ]);
  });
});
