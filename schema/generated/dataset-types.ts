// GENERATED FILE — DO NOT EDIT BY HAND.
// Produced by tools/generate_typescript_types.py from schema/*.json.
// Re-run that script after changing any schema/*.json file; the checked-in copy of
// this file and a fresh run must be byte-identical (see
// tests/schema/test_typescript_drift.py) — that identity is what stops the Python and
// TypeScript sides of the dataset contract from drifting apart by hand-editing either.

/** Semantic version of THIS artefact's own schema, independent of the other three/four artefacts' versions. Every artefact (base dataset, empire overlay, detail payload, search index, diagnostics) carries its own -- see spec/00-overview.md's Dataset structure section and spec/implementation-notes.md's Stage 2 section. The client validates each fetch against the version it declares and MUST refuse to render an unsupported version with a clear message rather than degrading silently. */
export type SchemaVersion = string;

/** The technology's internal Clausewitz key, e.g. tech_adaptive_bureaucracy. Stable identity used to cross-reference between artefacts and within edges/adjacency. */
export type TechnologyId = string;

/** P-13: availability MUST be a three-valued state, never a boolean. 'uncertain' means the partial trigger evaluator could not resolve the condition for this profile (D-10's 'unknown', propagated) -- it is not a variant of 'locked' and must never be presented as though it were either available or locked. */
export type ThreeState = "available" | "locked" | "uncertain";

/** P-1 axis 1 of 3. Canonical order for index derivation (see EmpireProfileIndex below): regular=0, hive_mind=1, machine_intelligence=2. */
export type GestaltAuthority = "regular" | "hive_mind" | "machine_intelligence";

/** P-1 axis 2 of 3. Canonical order: mechanical=0, biological=1. */
export type Shipset = "mechanical" | "biological";

/** P-1 axis 3 of 3. Canonical order: no=0, yes=1. */
export type Nomadic = "no" | "yes";

/** A single point in the composed 3-axis empire-type space (P-1, D-6). Twelve valid combinations -- NEVER modelled as a flat enumeration anywhere in this schema or its generated types. */
export interface EmpireProfile {
  authority: GestaltAuthority;
  shipset: Shipset;
  nomadic: Nomadic;
}

/** Derived 0-11 index of an EmpireProfile under the canonical ordering documented in this schema's $comment. Never authored by hand; always computed from the three axes. */
// STORAGE ENCODING ONLY -- the composed axes (EmpireProfile) are the identity model; this integer is a pure, documented function of them, used solely to index fixed-size 12-slot arrays (e.g. availabilityMatrix) compactly. Do not reintroduce this as if it were a sanctioned flat enumeration of profiles -- it isn't one; it's a derived array index. Canonical derivation, fixed and never to be changed without a schema version bump: index = authorityIndex*4 + shipsetIndex*2 + nomadicIndex, where authorityIndex/shipsetIndex/nomadicIndex are each axis value's position in the canonical order stated on GestaltAuthority/Shipset/Nomadic above (regular=0/hive_mind=1/machine_intelligence=2; mechanical=0/biological=1; no=0/yes=1). E.g. {authority: hive_mind, shipset: biological, nomadic: yes} -> 1*4 + 1*2 + 1 = 7.
export type EmpireProfileIndex = number;

/** P-14: {from, to, kind, appliesToEmpireTypes}. This is the appliesToEmpireTypes shape -- axis constraints, each an array of allowed values on that axis; an omitted axis is unconstrained (all its values allowed). Confirmed against the full corpus (see the icon/edge survey) that every real edge's empire-type applicability factors as a product of independent axis constraints -- no real edge needs an irregular (non-rectangular) subset of the twelve profiles, so this shape is sufficient. NEVER a flat 12-profile enumeration and NEVER a bitmask in this JSON -- if a bitmask is needed for fast membership testing at runtime, it is derived at build time into the typed-array side-files, never authored or shipped here. */
export interface EmpireTypeConstraint {
  authority?: (GestaltAuthority)[];
  shipset?: (Shipset)[];
  nomadic?: (Nomadic)[];
}

/** P-14. The three edge kinds, kept distinct end to end -- rendering (P-8: solid/dashed/dotted, decreasing opacity), traversal (P-7: isolation follows all three; P-12.9's research path follows prerequisite only), and rendering-scope computation (P-16: prerequisite only, pooled across profiles) all depend on this distinction never being collapsed. */
export type EdgeKind = "prerequisite" | "potential-gate" | "alternative";

/** P-14's typed, conditional edge. Direction is fixed and uniform across all three kinds -- see the 'from'/'to' property descriptions below, which are the single normative statement of this convention (P-8); nothing else in this schema or CLAUDE.md redefines it. */
export interface Edge {
  /** The technology DEPENDED UPON (the tail) -- for every edge kind uniformly. For a potential-gate edge, this is the technology named in the has_technology check, never the technology whose potential block contains the check. For an alternative edge, this is the alternative prerequisite. Connector colour follows this endpoint (P-8) -- the same endpoint used for direction, never a second attribution rule. */
  from: TechnologyId;
  /** The technology DECLARING the dependency (the head) -- for every edge kind uniformly. For a potential-gate edge, this is the technology whose potential block contains the has_technology check. Every connector renders from 'from' to 'to', the same direction a prerequisite edge reads, so all three kinds read consistently left-to-right regardless of kind (P-8). */
  to: TechnologyId;
  kind: EdgeKind;
  appliesToEmpireTypes: EmpireTypeConstraint;
}

/** A pointer into a packed atlas sheet -- never a raw path. Paths into atlases are build-generated, per P-3's 'icon paths MUST NOT be manually maintained.' */
export interface IconRef {
  /** Sheet name, e.g. technologies_0 (pipeline/icons/pack.py's pack_sheets sheet-naming convention). */
  sheet: string;
  x: number;
  y: number;
  width: number;
  height: number;
}

/** P-3: gate registry priority table ranks ascension-perk gates above technology gates (D-3) -- this field is what that priority table keys on. */
export type GateKind = "ascension_perk" | "technology";

/** P-3. A technology's gates are an ordered list; index 0 is the primary gate (P-12.7). */
export interface Gate {
  kind: GateKind;
  /** The ascension perk key or technology key this gate names. */
  refId: string;
  icon: IconRef;
  /** Localised gate label, e.g. 'Needs Cosmogenesis'. Sourced from the mod's own localisation, never hard-coded (P-3). */
  label: string;
}

/** 00-overview.md: geometry lives in typed-array side-files, JSON references them, never inlines coordinate arrays. */
export interface GeometryRef {
  /** Relative path/URL to the typed-array side-file. */
  file: string;
  byteOffset: number;
  /** Element count (not byte count) in the referenced typed-array span. */
  length: number;
  dtype: "float32" | "int32" | "uint32" | "uint16";
}

/** spec/00-overview.md's 'Dataset structure': technology records, layout coordinates, edge geometry, icon atlas references, the compact availabilityMatrix, labelPriority. Shared across all twelve empire profiles -- nothing in this artefact varies per profile. Search index, empire overlays and detail payloads are separate artefacts (their own schema files), fetched independently. */
export interface BaseDataset {
  schemaVersion: SchemaVersion;
  /** P-10: upstream sources MUST be pinned and recorded, displayed as a 'data as of' marker. */
  metadata: {
    gigastructuresCommit: string;
    vanillaVersion: string;
    acotVersion?: string;
    aotVersion?: string;
    buildTimestamp: string;
  };
  /** P-2/S-3: tier range is unbounded and MUST be enumerated from the dataset at build time, never assumed. Ascending order; the last entry is always the Repeatables terminal column. */
  tierBands: ({
    tier: number | "repeatables";
    column: number;
    label: string;
  })[];
  /** P-2/P-5: the standard-progression lane plus one per crisis faction, sharing one column axis. */
  lanes: ({
    id: string;
    label: string;
    crisisFaction: null | "Aeternum" | "Blokkats" | "Compound" | "Sirenalia" | "Katzenartig Imperium";
    technologyCount: number;
  })[];
  /** P-4: derived from the dataset at build time, never a hard-coded UI list. */
  categories: (string)[];
  /** Pointers to packed atlas sheets (pipeline/icons/pack.py). Atlas image bytes are fetched lazily and separately -- see pipeline/icons/resolve.py's Stage 2 note; this array carries references only, matching 00-overview.md's 'icon atlas references' base-dataset item. */
  iconAtlases: ({
    name: string;
    /** URL/path to the WebP sheet. */
    webp: string;
    /** URL/path to the PNG fallback sheet. */
    png: string;
    width: number;
    height: number;
  })[];
  technologies: ({
    id: TechnologyId;
    /** Localised name (P-6, node card). */
    name: string;
    icon: IconRef;
    /** Declared tier. P-2: unbounded, no fixed upper bound anywhere. */
    tier: number;
    /** Computed layout column. May exceed 'tier' after promotion (P-2: if declared tier is at or below a prerequisite's, promoted to max(prereq columns)+1). */
    column: number;
    /** References lanes[].id. */
    laneId: string;
    /** S-1: drives card background colour. */
    area: "physics" | "society" | "engineering";
    category: string;
    /** P-5: nullable. A technology that is both crisis-sourced and normally researchable is represented once, with this field set, never duplicated as two nodes. */
    crisisFaction: null | "Aeternum" | "Blokkats" | "Compound" | "Sirenalia" | "Katzenartig Imperium";
    /** P-12.11/S-1: badge, not a warning treatment. */
    rare: boolean;
    /** P-12.3/S-1: warning treatment, outranks rare in outline priority. */
    dangerous: boolean;
    /** P-12.2: boolean-plus-count on the card and in the popup. Full per-level cost progression is a detail-payload field, not here. */
    repeatable: {
      levels: number | null;
    };
    /** P-16. Empty for the overwhelming majority. A list, not a boolean, so a second dependency costs no schema change. */
    requiresMods: (string)[];
    /** P-3: ordered, primary gate first. Displayed regardless of the selected empire profile -- lives here in the base dataset, not in a per-profile overlay, precisely because it must never vary by profile. */
    gates: (Gate)[];
    /** P-13's twelve-profile expand-control matrix. Index i is this technology's ThreeState for EmpireProfileIndex i (see common.schema.json). Enum values only, no reason text -- the richer per-profile reason string lives in the empire-overlay artefact; this exists so the popup's matrix view doesn't require prefetching all twelve overlays just to render a summary widget. */
    availabilityMatrix: (ThreeState)[];
    /** S-3: far-zoom label-decluttering basis. Derived at build time from prerequisite out-degree (how many other technologies depend on this one) plus the rare and dangerous flags -- reproducible, never hand-maintained. Higher survives longer as zoom decreases. Exact derivation formula is Stage 2's to define at implementation time; this field's contract is only that it is build-time-derived and monotonic with 'importance', never authored. */
    labelPriority: number;
  })[];
  edges: (Edge)[];
  /** P-7: forward and reverse adjacency, per edge kind, precomputed -- O(1) lookup per node, never a full edge-set scan at interaction time. Values are indices into the 'edges' array. */
  adjacency: {
    /** technology id -> { edge kind -> [edge indices where this technology is "to"] } */
    forward: { [key: string]: { [key: string]: (number)[] } };
    /** technology id -> { edge kind -> [edge indices where this technology is "from"] } */
    reverse: { [key: string]: { [key: string]: (number)[] } };
  };
  /** 00-overview.md: typed-array side-files, JSON references them. */
  geometry: {
    nodePositions: GeometryRef;
    edgePolylines: GeometryRef;
  };
}

/** One artefact per empire profile, fetched on demand when the user selects that profile (spec/00-overview.md, spec/implementation-notes.md). Carries everything that varies by profile: availability with full reason text, active edge set, swap mappings, precomputed research path (P-12.9). */
export interface EmpireOverlay {
  schemaVersion: SchemaVersion;
  profile: EmpireProfile;
  /** P-13. Keyed by technology id. Full reason text lives here, not in the base dataset's compact availabilityMatrix. */
  availability: { [key: string]: {
    state: ThreeState;
    /** Required (non-null) when state is 'locked' or 'uncertain'; null when 'available'. Two valid origins for a locked reason (P-13): trigger-derived (the specific failed condition) or structure-derived (no edge of any kind reaches this technology for this profile -- P-16). Both are ordinary strings in this one field; a structure-derived reason MUST be phrased in terms of reachability, never as though a trigger failed. An uncertain reason always carries the unresolved trigger's source text. */
    reason: null | string;
  } };
  /** Indices into the base dataset's 'edges' array whose appliesToEmpireTypes constraint this profile satisfies. P-16: used by the per-profile structural-reachability check, which considers all three edge kinds -- never conflated with the profile-invariant rendering-scope closure (prerequisite edges only, computed once, lives in the base dataset's node set, not here). */
  activeEdgeIds: (number)[];
  /** P-14/technology_swap: which swap alternative applies for this profile. */
  swapMappings: ({
    baseTechnologyId: TechnologyId;
    activeVariantId: TechnologyId;
  })[];
  /** P-12.9: complete ancestor set in topological order by tier, with cumulative cost, computed per profile at build time -- never substituted from a canonical path in the browser, since swaps change the shape of the chain. Keyed by technology id. */
  researchPaths: { [key: string]: {
    ancestors: ({
      technologyId: TechnologyId;
      tier: number;
      cumulativeCost: number;
    })[];
    /** D-1's 'shortest chain' toggle: the cheapest single chain by cumulative cost, as an ordered list of technology ids. */
    shortestChain: (TechnologyId)[];
  } };
}

/** spec/00-overview.md: descriptions, weight modifier lists, repository links, chunked and lazily fetched when a popup opens. One artefact per technology (or a small batch); fetched on demand, never part of the initial base-dataset load. */
export interface DetailPayload {
  schemaVersion: SchemaVersion;
  technologyId: TechnologyId;
  /** P-12.1. Localised, with embedded formatting/variable tokens resolved or safely stripped (P-12.1). English only for v1 (D-9). */
  description: string;
  repeatableCostProgression: null | (number)[];
  /** P-12.5. */
  source: "Vanilla" | "Gigastructural Engineering" | "Vanilla (modified by Gigastructural Engineering)";
  /** P-15: for a modified vanilla technology, which fields differ from vanilla. Null when 'source' is not the modified-vanilla case. */
  overwriteDiff: null | {
    changedFields: ("cost" | "tier" | "prerequisites" | "weight" | "category" | "flags")[];
  };
  /** P-12.6/D-5: three branches. Never dead, never omitted. */
  repositoryLink: {
    kind: "gigastructures-permalink" | "steam-workshop" | "stellaris-wiki";
    url: string;
    /** Set only for the gigastructures-permalink branch. P-12.6: targets the technology's own declared file/line range as written -- never a post-inline_script-expansion reconstruction. */
    lineRange: null | {
      file: string;
      startLine: number;
      endLine: number;
    };
  };
  /** P-12.8. No evaluated weight (D-4) -- base weight plus conditions only, never a computed final number. */
  weight: {
    base: number;
    modifiers: ({
      factor: number;
      /** Human-readable rendering of the modifier's trigger condition. NOT YET BUILT as of this schema's authoring -- see HANDOFF.md's extraction-gap note on a trigger-to-text renderer; this field's presence in the schema does not imply the generator exists yet. */
      conditionText: string;
    })[];
  };
}

/** P-6. A fourth, separately-fetched artefact -- NOT part of the base dataset (see spec/implementation-notes.md's Stage 2 section for why). Fetched lazily on first search-box focus, not during initial load. Carries build-time-tokenised keywords derived from name, key and description text -- never raw description text, which stays in the lazy detail payload. If the fetch fails or hasn't completed, the client shows a loading state, then a failure state, without blocking any other part of the application (search degrades; nothing else does). */
export interface SearchIndex {
  schemaVersion: SchemaVersion;
  entries: ({
    technologyId: TechnologyId;
    /** Lower-cased, diacritic-stripped tokens (P-6: search MUST be diacritic- and case-insensitive) derived at build time from name, key and description. Partial/prefix matching is a client-side concern over these tokens; fuzzy (edit-distance) matching is optional per P-6 and, if implemented, MUST rank exact/prefix matches above it. */
    tokens: (string)[];
  })[];
}

/** S-2: the /?dev overlay's data. Outside the base/overlay/detail/search-index split entirely -- fetched only when ?dev is present, code-split, never affects the P-10 budgets when unused. */
export interface Diagnostics {
  schemaVersion: SchemaVersion;
  /** D-10: per-profile unknown rate, all twelve, plus each profile's delta against the previous build (the exact figure the ratchet fails on). */
  unknownRates: ({
    profile: EmpireProfile;
    unknownRate: number;
    previousUnknownRate: number;
  })[];
  missingInlineScriptParameterCount: {
    current: number;
    previous: number;
  };
  tierPromotions: ({
    technologyId: TechnologyId;
    declaredTier: number;
    promotedColumn: number;
  })[];
  unrecognisedGatePatterns: (string)[];
  missingLockReasonOverrides: (string)[];
  unresolvedTriggers: (string)[];
  unresolvedModDependencies: (string)[];
  overwriteReport: ({
    technologyId: TechnologyId;
    changedFields: (string)[];
  })[];
}
