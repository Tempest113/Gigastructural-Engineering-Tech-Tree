// Empire-profile switching slice (reconciliation session 4), corrected (Item 1b, gate-
// classification survey session): this module used to restate pipeline/dataset_schema/
// empire_profile.py's EmpireProfileIndex formula as a second, hand-synced implementation --
// exactly the shape CLAUDE.md's Rules forbid ("the pipeline owns all geometry [or, here, indexing
// scheme]; the renderer consumes emitted [data] and never recomputes them from a parallel
// formula"), the same defect class D-17's row-geometry desync was found under. Fixed the same
// way: the base dataset now emits `empireProfileAxes` (schema/common.schema.json's
// `EmpireProfileAxes`, built by `pipeline.dataset_schema.empire_profile.build_empire_profile_axes`)
// -- axis order, cardinalities, canonical value order and derived stride -- and every function
// below derives its answer from that emitted data. Nothing here hardcodes a stride, an axis order,
// or an axis's value list; a one-sided axis-cardinality change (pipeline gains a value, this file
// doesn't know) now produces a wrong INDEX (still derived, still detectable by the cross-check
// against the emitted availabilityMatrix) rather than a silent divergence between two formulas
// that happened to agree.
//
// This is a STORAGE ENCODING, not an identity model: the three composed axes remain the identity
// (P-1, D-6); the index exists only to look up the base dataset's fixed-size N-slot
// `availabilityMatrix` arrays compactly. Never treat it as a sanctioned flat enumeration of
// profiles in UI code -- the profile SELECTOR exposes the axes independently, never a flat list.

import type { EmpireProfile, EmpireProfileAxes } from "../../schema/generated/dataset-types";

export type { EmpireProfile };

let currentAxes: EmpireProfileAxes | null = null;

/** Must be called once, with the base dataset's own `empireProfileAxes`, before any other
 * function in this module is used. There is deliberately no hardcoded fallback -- a caller that
 * forgets this gets a loud error, not a silently wrong index. */
export function initEmpireProfileAxes(axes: EmpireProfileAxes): void {
  currentAxes = axes;
}

function requireAxes(): EmpireProfileAxes {
  if (!currentAxes) {
    throw new Error(
      "empireProfile: initEmpireProfileAxes() must be called with the base dataset's emitted " +
        "empireProfileAxes before this module is used -- there is no hardcoded fallback formula."
    );
  }
  return currentAxes;
}

/** This axis's values in the emitted canonical order (index 0 = value 0), e.g. `axisValues
 * ("authority")` -> `["regular", "hive_mind", "machine_intelligence"]`. Used to populate the
 * profile-selector's `<select>` options without hardcoding the value list here. */
export function axisValues(axisName: string): string[] {
  const axis = requireAxes().axes.find((a) => a.name === axisName);
  if (!axis) {
    throw new Error(`empireProfile: emitted empireProfileAxes has no axis named "${axisName}"`);
  }
  return axis.values;
}

/** The canonical EmpireProfileIndex, computed purely from the emitted axis list/strides --
 * see this module's header comment. Throws if `profile` names a value not present in the
 * emitted axis (a real divergence, surfaced loudly rather than producing a wrong index). */
export function empireProfileIndex(profile: EmpireProfile): number {
  const axes = requireAxes();
  const bag = profile as unknown as Record<string, string>;
  let index = 0;
  for (const axis of axes.axes) {
    const value = bag[axis.name];
    const position = axis.values.indexOf(value ?? "");
    if (position < 0) {
      throw new Error(
        `empireProfileIndex: profile.${axis.name}=${String(value)} is not one of the emitted ` +
          `axis values [${axis.values.join(", ")}]`
      );
    }
    index += position * axis.stride;
  }
  return index;
}

/** The overlay manifest's own key format (`pipeline.dataset_emit`'s `<authority>-<shipset>-
 * <nomadic>`), used to look up `manifest.overlays[...]` -- distinct from EmpireProfileIndex,
 * which indexes the base dataset's compact `availabilityMatrix`, not the overlay manifest. Axis
 * order for this key is fixed by the overlay manifest's own convention, independent of
 * EmpireProfileIndex's derivation, so it is spelled out explicitly rather than derived from
 * `axes` (whose order is about stride significance, not this string format). */
export function profileKey(profile: EmpireProfile): string {
  return `${profile.authority}-${profile.shipset}-${profile.nomadic}`;
}

/** All profiles in the full axis product, in the exact order `empireProfileIndex` assigns
 * 0..totalProfileCount-1 -- `allProfiles()[i]` always has `empireProfileIndex(...) === i`.
 * Built as a cartesian product over the emitted `axes` list in its own order (most-significant
 * stride first), which is what makes that invariant hold without hardcoding axis count or
 * shape. */
export function allProfiles(): EmpireProfile[] {
  const axes = requireAxes();
  let combos: Record<string, string>[] = [{}];
  for (const axis of axes.axes) {
    combos = combos.flatMap((combo) => axis.values.map((value) => ({ ...combo, [axis.name]: value })));
  }
  return combos as unknown as EmpireProfile[];
}

export const DEFAULT_PROFILE: EmpireProfile = { authority: "regular", shipset: "mechanical", nomadic: "no" };
