// Empire-profile switching slice (reconciliation session 4). Mirrors
// pipeline/dataset_schema/empire_profile.py's canonical EmpireProfileIndex derivation EXACTLY --
// see that module's own docstring for the full normative statement (schema/common.schema.json's
// EmpireProfileIndex $comment is the ultimate source of truth; this and the Python module are
// both derived from it, deliberately kept in sync by hand since there is no cross-language code
// generation for pure logic in this project, only for the data schema itself).
//
// This is a STORAGE ENCODING, not an identity model: the three composed axes remain the
// identity (P-1, D-6); this integer exists only to index the base dataset's fixed-size 12-slot
// `availabilityMatrix` arrays compactly. Never treat it as a sanctioned flat enumeration of
// profiles in UI code -- the profile SELECTOR exposes the three axes independently (this
// session's own instruction), never a flat list of 12.

export type Authority = "regular" | "hive_mind" | "machine_intelligence";
export type Shipset = "mechanical" | "biological";
export type Nomadic = "no" | "yes";

export interface EmpireProfile {
  authority: Authority;
  shipset: Shipset;
  nomadic: Nomadic;
}

// Canonical axis order -- changing this changes what every EmpireProfileIndex means (a schema
// version bump, per the Python module's own docstring), never a casual edit.
export const AUTHORITY_ORDER: Authority[] = ["regular", "hive_mind", "machine_intelligence"];
export const SHIPSET_ORDER: Shipset[] = ["mechanical", "biological"];
export const NOMADIC_ORDER: Nomadic[] = ["no", "yes"];

// Strides: authority=4 (2 shipset values * 2 nomadic values), shipset=2, nomadic=1 -- mixed-radix
// positional encoding, standard odometer style. Hardcoded here (unlike the Python module, which
// derives strides from axis cardinalities at import time to survive a future axis change) since
// this file has no import-time assertion mechanism to fail loudly the way Python's does; if the
// axis shape ever changes, this file MUST change in lockstep with empire_profile.py, and the
// round-trip test (window.__tt.checkEmpireProfileIndexRoundTrip) would catch a mismatch against
// the real emitted overlay files' own `profile` field.
const AUTHORITY_STRIDE = SHIPSET_ORDER.length * NOMADIC_ORDER.length; // 4
const SHIPSET_STRIDE = NOMADIC_ORDER.length; // 2

export function empireProfileIndex(profile: EmpireProfile): number {
  return (
    AUTHORITY_ORDER.indexOf(profile.authority) * AUTHORITY_STRIDE +
    SHIPSET_ORDER.indexOf(profile.shipset) * SHIPSET_STRIDE +
    NOMADIC_ORDER.indexOf(profile.nomadic)
  );
}

/** The overlay manifest's own key format (`pipeline.dataset_emit`'s `<authority>-<shipset>-
 * <nomadic>`), used to look up `manifest.overlays[...]` -- distinct from EmpireProfileIndex,
 * which indexes the base dataset's compact `availabilityMatrix`, not the overlay manifest. */
export function profileKey(profile: EmpireProfile): string {
  return `${profile.authority}-${profile.shipset}-${profile.nomadic}`;
}

/** All 12 profiles, in the canonical odometer order (authority outermost, nomadic innermost) --
 * `ALL_PROFILES[i]` is the profile whose `empireProfileIndex` is `i`, for every i in [0, 12). */
export const ALL_PROFILES: EmpireProfile[] = AUTHORITY_ORDER.flatMap((authority) =>
  SHIPSET_ORDER.flatMap((shipset) => NOMADIC_ORDER.map((nomadic) => ({ authority, shipset, nomadic })))
);

export const DEFAULT_PROFILE: EmpireProfile = { authority: "regular", shipset: "mechanical", nomadic: "no" };
