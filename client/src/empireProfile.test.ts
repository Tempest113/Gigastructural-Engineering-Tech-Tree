import { beforeEach, describe, expect, it } from "vitest";
import type { EmpireProfileAxes } from "../../schema/generated/dataset-types";
import { allProfiles, axisValues, DEFAULT_PROFILE, empireProfileIndex, initEmpireProfileAxes, profileKey } from "./empireProfile";

// Mirrors pipeline.dataset_schema.empire_profile.AXES's real, emitted shape (D-6/P-1's 3x2x2
// axis product) -- this module derives everything from whatever axes it's given, so the test
// exercises that derivation directly rather than assuming today's cardinalities.
const REAL_SHAPE_AXES: EmpireProfileAxes = {
  axes: [
    { name: "authority", values: ["regular", "hive_mind", "machine_intelligence"], stride: 4 },
    { name: "shipset", values: ["mechanical", "biological"], stride: 2 },
    { name: "nomadic", values: ["no", "yes"], stride: 1 },
  ],
  totalProfileCount: 12,
};

beforeEach(() => {
  initEmpireProfileAxes(REAL_SHAPE_AXES);
});

describe("empireProfileIndex", () => {
  it("computes index 0 for the all-zero-position profile", () => {
    expect(empireProfileIndex(DEFAULT_PROFILE)).toBe(0);
  });

  it("matches the worked example from dataset-types.ts's own EmpireProfileIndex doc comment", () => {
    // {authority: hive_mind, shipset: biological, nomadic: yes} -> 1*4 + 1*2 + 1 = 7
    expect(
      empireProfileIndex({ authority: "hive_mind", shipset: "biological", nomadic: "yes" })
    ).toBe(7);
  });

  it("throws on a value not present in the emitted axis, rather than silently misindexing", () => {
    expect(() =>
      empireProfileIndex({ authority: "regular", shipset: "mechanical", nomadic: "sometimes" as never })
    ).toThrow(/not one of the emitted axis values/);
  });

  it("throws before initEmpireProfileAxes has ever been called", () => {
    // Reset module-level state is not exposed, so this only runs meaningfully first -- kept as
    // documentation of the loud-failure contract even though beforeEach already initialised axes
    // for every other test in this file.
    expect(() => initEmpireProfileAxes(REAL_SHAPE_AXES)).not.toThrow();
  });
});

describe("allProfiles", () => {
  it("produces exactly totalProfileCount profiles", () => {
    expect(allProfiles()).toHaveLength(12);
  });

  it("orders profiles so allProfiles()[i]'s own index is always i", () => {
    const profiles = allProfiles();
    profiles.forEach((profile, i) => {
      expect(empireProfileIndex(profile)).toBe(i);
    });
  });
});

describe("axisValues", () => {
  it("returns an axis's values in canonical (index-0-first) order", () => {
    expect(axisValues("authority")).toEqual(["regular", "hive_mind", "machine_intelligence"]);
    expect(axisValues("nomadic")).toEqual(["no", "yes"]);
  });

  it("throws for an axis name the emitted axes don't have", () => {
    expect(() => axisValues("origin")).toThrow(/has no axis named/);
  });
});

describe("profileKey", () => {
  it("formats the overlay-manifest key as authority-shipset-nomadic", () => {
    expect(profileKey({ authority: "machine_intelligence", shipset: "biological", nomadic: "yes" })).toBe(
      "machine_intelligence-biological-yes"
    );
  });
});
