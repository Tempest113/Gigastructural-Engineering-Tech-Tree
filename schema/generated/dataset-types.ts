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

/** P-15/P-16: the four sources in load order (vanilla, Gigastructural Engineering, ACOT, AoT). Load order is lowest to highest -- a later source's technology-block definition replaces an earlier one's wholesale, matching engine overwrite semantics. */
export type SourceMod = "Vanilla" | "Gigastructural Engineering" | "ACOT" | "AoT";

/** P-13: availability MUST be an enumerated state, never a boolean. 'uncertain' means the partial trigger evaluator could not resolve the condition for this profile (D-10's 'unknown', propagated) -- it is not a variant of 'locked' and must never be presented as though it were either available or locked. 'config-gated' (added by D-10's giga_tech_repeatable_*_cap application, spec/decisions.md) means the technology's potential resolved DEFINITIVELY to false because of a mod-configuration toggle (a has_global_flag matching pipeline.trigger_text.MOD_CONFIG_TOGGLE_SUFFIXES), not because of anything about the empire being played -- distinct from 'locked', which elsewhere always means an empire-state property is what's blocking the technology. This $defs key was named 'ThreeState' before 'config-gated' was added; renamed to a value-count-independent name deliberately, so a fifth state added later doesn't leave a stale 'ThreeState'/'FourState' name behind again. */
export type AvailabilityState = "available" | "locked" | "uncertain" | "config-gated";

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

/** Emitted mirror of pipeline/dataset_schema/empire_profile.py's AXES -- the axis order, each axis's cardinality and canonical value order, and derived stride, exactly as EmpireProfileIndex's $comment states it. Exists so the client derives EmpireProfileIndex from this emitted data instead of restating the formula as a second implementation (CLAUDE.md's Rules: 'the pipeline owns all geometry [or here, indexing scheme]; the renderer consumes emitted [data] and never recomputes them from a parallel formula') -- the exact defect class D-17's row-geometry desync was found under. A one-sided axis-cardinality change (pipeline gains a value, client doesn't know) must fail loudly, not silently drift; deriving from this field is what makes that structurally impossible rather than merely tested-for. */
export interface EmpireProfileAxes {
  /** In canonical order (authority, shipset, nomadic today) -- index 0 is the most significant (largest stride). */
  axes: ({
    name: "authority" | "shipset" | "nomadic";
    /** This axis's values in canonical order -- values[i]'s position i is its index for stride multiplication. */
    values: (string)[];
    /** Multiplier applied to this axis's value-index when composing EmpireProfileIndex. Product of the cardinalities of every axis after this one; the last axis always has stride 1. */
    stride: number;
  })[];
  /** Product of every axis's cardinality -- 12 today. The valid range for EmpireProfileIndex is 0..totalProfileCount-1. */
  totalProfileCount: number;
}

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
  /** P-14: only set (non-null) for kind == 'alternative'. Identifies which nested OR group inside the 'to' technology's prerequisites this edge's member belongs to -- without it, two independent 2-member OR groups on the same technology are indistinguishable from one 4-member group (the real corpus has 35 OR groups across 32 technologies; 3 technologies carry two groups each, e.g. tech_mega_engineering). Null for 'prerequisite' and 'potential-gate' edges, which have no group structure. */
  groupId: null | string;
  appliesToEmpireTypes: EmpireTypeConstraint;
  /** D-13 (spec/decisions.md): true when 'from' (the prerequisite) sits in a later declared-tier band than 'to' (the dependent) -- a real, expected consequence of bands reflecting declared tier rather than computed depth. Measured over the full P-14 three-kind edge set (989 real rendered edges): 34 backward, decomposed as 25 prerequisite + 2 alternative + 7 potential-gate -- record this as a per-kind breakdown, never a single number; it has moved three times purely through re-scoping (see CLAUDE.md's P-14 edge-typing section). P-8 MUST render these visually distinguishably from forward edges rather than as if the graph were acyclic in band order. prerequisite/alternative stay within 1-2 bands back; potential-gate reaches up to 5 (a has_technology gate can reference any technology anywhere, with no reason to sit near its owner's declared tier) -- P-8's long-range routing treatment for potential-gate is TODO(Stage 3), deliberately deferred to a real rendered canvas rather than designed blind. */
  backward: boolean;
  /** P-8/TODO(Stage 3): from_bandIndex - to_bandIndex. Positive iff backward is true; emitted on every edge (not just backward ones) so a consumer never needs to recompute it from band indices it may not have handy. Exists specifically so potential-gate's long-range backward routing (up to 5 bands, vs. 1-2 for prerequisite/alternative) can be decided against real data at Stage 3 rather than guessed at now. */
  bandSpan: number;
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

/** P-3: gate registry priority table ranks ascension-perk gates above origin/ethics-or-civic gates above technology gates (D-3, extended by the "path to zero uncertain" follow-up's Item 3) -- this field is what that priority table keys on. */
export type GateKind = "ascension_perk" | "origin" | "ethics_or_civic" | "technology";

/** P-3. A technology's gates are an ordered list; index 0 is the primary gate (P-12.7). */
export interface Gate {
  kind: GateKind;
  /** The ascension perk key or technology key this gate names. */
  refId: string;
  /** Null for an origin/ethics-or-civic gate (a later session, user-reported): no civic/origin/ethic icon is vendored for ANY source (a 100%-of-the-time gap, not a rare edge case), so this used to fall back to a degenerate 1x1-pixel stretched IconRef -- a solid colour block (a 'teal square') that reads as a rendering error, not a placeholder. Null tells the client to render the gate's label alone, no icon element at all, until real icons are vendored. An ascension_perk/technology gate still carries a real resolved IconRef (the same rare-fallback IconRef as before for the vanishingly rare case its own icon never resolved -- unaffected, out of scope for this fix). */
  icon: null | IconRef;
  /** Localised gate label, e.g. 'Needs Cosmogenesis'. Sourced from the mod's own localisation, never hard-coded (P-3). */
  label: string;
  /** "path to zero uncertain" follow-up, Item 4: true iff this leaf sits inside an OR in the technology's own potential block -- one of SEVERAL independent ways to satisfy it, not the sole/AND-required condition (e.g. tech_torpedoes_1's 'Needs Riddle Escort' is one of four independent OR branches, not an unconditional requirement). The client MUST render an alternative gate distinctly from an unconditional one -- never as a bare 'Needs X' requirement. */
  alternative: boolean;
  /** Nested AND-of-OR fix (a later session, user-reported: Gargantuan Cloning Facilities showed 'Needs Galactic Wonders' + 'or: Mechromancy' as if they were two peers in one choice, when the real structure is AND(has_galactic_wonders, OR(has_genetically_ascended, has_active_tradition, ap_mechromancy)) -- Galactic Wonders is unconditionally required, and the OR is a SEPARATE branch beneath it, not beside it). Names the specific OR/NOR block this gate is a direct child of (mirroring Edge.groupId's per-owner, per-block-index identity, `f"{technologyId}#gate-alt{index}"`) -- two gates sharing the same groupId are alternatives WITHIN that one choice; a gate with a different groupId (or none) is a separate, independently-required condition even if it is also `alternative: true` (rare -- only when a technology has two distinct OR groups). Null when `alternative` is false. */
  groupId: null | string;
  /** Item 4: for a "technology"-kind alternative gate backed by a real potential-gate edge with a genuine per-axis constraint (pipeline.edge_constraints), the same constraint reused here -- e.g. tech_torpedoes_1's Riddle Escort gate only ever matters for shipset=[biological] profiles; for every other profile the gate should not present as a requirement at all. Null when the gate is unconstrained (applies to every profile) or not backed by an edge-constraint entry. */
  appliesToEmpireTypes: unknown;
  /** Item 3 (later session): true iff this gate was NOT declared on this technology's own potential/perk-grant, but propagated from a `prerequisite`-edge ancestor that declares it directly (e.g. the QSO family inherits `ap_qso` from `giga_tech_quasi_stellar_1`; a Management Protocols repeatable inherits `ap_galactic_wonders` from its megastructure prerequisite). The client must render an inherited gate distinctly from a directly-declared one (e.g. naming the source technology) so a user can tell where the requirement originates. */
  inherited: boolean;
  /** Null for a directly-declared gate (`inherited: false`). For an inherited gate, the technology key whose OWN potential/perk-grant declares this gate directly -- the original source, not an intermediate hop in a longer prerequisite chain. */
  sourceTechnologyId: null | string;
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
  empireProfileAxes: EmpireProfileAxes;
  /** P-10: upstream sources MUST be pinned and recorded, displayed as a 'data as of' marker. */
  metadata: {
    gigastructuresCommit: string;
    vanillaVersion: string;
    acotVersion?: string;
    aotVersion?: string;
    buildTimestamp: string;
  };
  /** P-2/S-3/D-13: tier range is unbounded and MUST be enumerated from the dataset at build time, never assumed. A band is a distinct DECLARED tier value actually present among rendered technologies -- never adjusted by graph depth (D-13, spec/decisions.md). Ascending order by declared tier; the last entry is always the Repeatables terminal band. */
  tierBands: ({
    tier: number | "repeatables";
    /** This band's ordinal position (0-based, ascending by declared tier, Repeatables always last). Internal layout geometry only -- never rendered as a number; the band header shows 'tier' (or 'Repeatables'). */
    bandIndex: number;
    label: string;
  })[];
  /** P-2/D-16 (spec/decisions.md): a ROW, sharing one band axis with every other row. The field name is unchanged from an earlier model (the standard-progression lane plus one per crisis faction) for JSON-contract/client-typecheck stability -- see D-16 -- but the CONTENT changed: 18 entries, the derived vanilla-category rows (grouped by research area, alphabetical within an area) followed by the 5 crisis-faction rows, faction-first-else-category, mutually exclusive. All 18 always present, including a faction at zero population (e.g. Compound -- confirmed real in the current corpus, not a classifier gap; see pipeline/crisis_faction.py) -- a row is never omitted for being empty. */
  rows: ({
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
    /** Declared tier. P-2: unbounded, no fixed upper bound anywhere. D-13: this IS the technology's band -- never adjusted by graph depth or promoted. Its exact pixel position (including horizontal placement within the band's sub-grid) lives in geometry.nodePositions, not as a separate displayed field here. */
    tier: number;
    /** P-12.2/S-1 card field: research cost, first-level/base figure. Per D-4's 'no evaluated weight' precedent, this is a stated field value, not a computed-final number -- in-game costs shift with empire size and other live modifiers the static build can't see, so this is the base/declared cost, approximate by nature, not a promise of what research will actually cost. */
    cost: null | number;
    /** References rows[].id -- this technology's ROW (D-16): its own crisis faction if it has one, else its own category id. Field name unchanged from an earlier lane model for JSON-contract stability; see D-16 in spec/decisions.md. */
    rowId: string;
    /** S-1: drives card background colour. */
    area: "physics" | "society" | "engineering";
    category: string;
    /** P-5: nullable. A technology that is both crisis-sourced and normally researchable is represented once, with this field set, never duplicated as two nodes. */
    crisisFaction: null | "Aeternum" | "Blokkats" | "Compound" | "Sirenalia" | "Katzenartig Imperium";
    /** P-12.11/S-1: badge, not a warning treatment. */
    rare: boolean;
    /** P-12.3/S-1: warning treatment, outranks rare in outline priority. */
    dangerous: boolean;
    /** P-12.2/D-13: boolean-plus-count on the card and in the popup. Full per-level cost progression (the detail popup's fuller breakdown) is a detail-payload field (`repeatableCostProgression`), not here -- `costPerLevel` here is the single scaling-rate number, not the expanded series. Membership is 'source declares a levels field at all' -- both the unbounded (-1) and positive-finite-cap shapes in the corpus are repeatable; sign alone is not the signal (see pipeline.layout.is_repeatable's docstring for the corpus finding behind this). */
    repeatable: null | {
      levels: number | null;
      /** The per-level cost increment (source's own `cost_per_level` field) -- a SECONDARY card indicator alongside the primary `cost` field above, not a replacement for it. Decision (spec/P-02-layout.md): `cost` (this technology's base/first-level cost, from the top-level `cost` field) is the primary displayed figure; `costPerLevel` is secondary. Rationale: in-game research cost shifts heavily with empire size and other live modifiers, so any absolute number is approximate regardless of which one is shown -- the scaling RATE (`costPerLevel`) is the one thing the card can state truthfully about a repeatable technology's cost trajectory, where the absolute total at level N cannot be. Exact visual treatment (badge text, iconography) is a Stage 3 rendering decision; this field is the semantic data only. Real corpus: exactly the 88-node repeatable set carries this field (0 non-repeatable technologies do -- confirmed, not assumed). */
      costPerLevel: null | number;
    };
    /** P-16. Empty for the overwhelming majority. A list, not a boolean, so a second dependency costs no schema change. */
    requiresMods: (string)[];
    /** P-3: ordered, primary gate first. Displayed regardless of the selected empire profile -- lives here in the base dataset, not in a per-profile overlay, precisely because it must never vary by profile. */
    gates: (Gate)[];
    /** P-13's twelve-profile expand-control matrix. Index i is this technology's AvailabilityState for EmpireProfileIndex i (see common.schema.json). Enum values only, no reason text -- the richer per-profile reason string lives in the empire-overlay artefact; this exists so the popup's matrix view doesn't require prefetching all twelve overlays just to render a summary widget. */
    availabilityMatrix: (AvailabilityState)[];
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
    state: AvailabilityState;
    /** Required (non-null) when state is 'locked', 'uncertain' or 'config-gated'; null when 'available'. Two valid origins for a locked reason (P-13): trigger-derived (the specific failed condition) or structure-derived (no edge of any kind reaches this technology for this profile -- P-16). Both are ordinary strings in this one field; a structure-derived reason MUST be phrased in terms of reachability, never as though a trigger failed. An uncertain reason always carries the unresolved trigger's source text. A config-gated reason carries the mod-configuration flag's trigger text (e.g. 'has_global_flag = giga_tech_repeatable_dyson_swarm_capped_r') -- phrased around the game OPTION responsible, never as though the empire itself were the obstacle. */
    reason: null | string;
    /** P-13's config-gated reason template (spec/P-13-empire-locking.md): the semantic subject only -- e.g. 'Alderson Disk' -- for Stage 3 to substitute into the user-supplied, fixed template 'Requires {subject} cap: 1 + Repeatables'. Deliberately NOT a pre-composed display string: Stage 2 emits the semantic part, Stage 3 composes the final text (the template itself is not data and is never emitted here). Present (non-null) only when 'state' is 'config-gated' AND the subject's own localised name is statically resolvable -- sourced from the technology's own display name, never the raw '$name$' runtime token, which Stellaris resolves per-playthrough from a name pool this static pipeline cannot see. Null both when 'state' isn't 'config-gated' and when it is but the name embeds an unresolved '$...$' token (8/50 in the real giga_tech_repeatable_*_cap corpus, including 'Alderson Disk' itself) -- an honest gap, not a guess. */
    configGatedSubject?: null | string;
  } };
  /** Indices into the base dataset's 'edges' array whose appliesToEmpireTypes constraint this profile satisfies. P-16: used by the per-profile structural-reachability check, which considers all three edge kinds -- never conflated with the profile-invariant rendering-scope closure (prerequisite edges only, computed once, lives in the base dataset's node set, not here). */
  activeEdgeIds: (number)[];
  /** D-14 (spec/decisions.md): per-profile display substitution for the subset of a technology's `technology_swap` alternates whose trigger is fully expressible on the 3-axis empire model (authority/shipset/nomadic -- `pipeline.availability.AXIS_FACTS`). One entry per rendered technology that has an axis-expressible swap ACTIVE for this profile; a technology with no matching swap (no swaps at all, or none of its swaps' triggers hold for this profile) has no entry here at all, and a renderer falls back to the base dataset's own name/icon/area/category. Swap alternates NEVER become separate rendered nodes (D-1) -- this is presentation substitution on the one node, never a second node reference, which is why this shape carries the substituted fields directly rather than an id pointing at something else. */
  swapMappings: ({
    technologyId: TechnologyId;
    /** The swap's own localised display name, replacing the base technology's name for this profile. */
    name: string;
    icon: IconRef;
    area: null | "physics" | "society" | "engineering";
    category: null | string;
  })[];
  /** P-12.9 (spec/P-12.9-research-path.md): the complete `prerequisite`-edge ancestor set, `alternative` (OR-group) branches resolved to the cheapest-total-cost viable candidate, computed per profile at build time -- never substituted or recomputed from a canonical path in the browser (a v1 failure this spec's own 'The failure being fixed' section documents: profile-blind traversal and flattened OR branches). Keyed by technology id; one entry per rendered technology. */
  researchPaths: { [key: string]: {
    status: "path" | "config-gated" | "unavailable";
    /** status == 'path' or 'config-gated' only. Ordered ancestor set (topological, by tier), D-14-substituted per this profile. */
    steps?: ({
      technologyId: TechnologyId;
      name: string;
      icon: IconRef;
      tier: number;
      /** Null when this step's own cost is unresolvable (contributes 0 to totalCost; see totalCostIsEstimate/estimateReasons). */
      stepCost: null | number;
      /** Never locked/config-gated -- a step whose own state resolves to either is excluded upstream (a plain locked prerequisite makes the whole path unavailable; a config-gated technology can only ever be the path's own target, per the sink property). */
      availabilityState: "available" | "uncertain";
      /** Set when this step was the chosen member of an alternative (OR-group) edge (P-14's Edge.groupId); null for an ordinary prerequisite step. */
      groupId: null | string;
      /** Other VIABLE (not locked/config-gated) siblings at this step's own groupId, not chosen. Empty when groupId is null. */
      alternatives: ({
        technologyId: TechnologyId;
        name: string;
      })[];
    })[];
    /** status == 'path' or 'config-gated' only (otherwise null). Sum of every step's stepCost, null-cost steps contributing 0, PLUS the target's own declared cost when status == 'path' -- a v1-compatible 'total cost to research this technology' figure (confirmed against the spec's own worked example: tech_mega_engineering's 15-ancestor sum, 50,750 for regular/mechanical/non-nomadic, plus its own 24,000 declared cost, reproduces the spec's reported 74,750 total exactly; the ancestor sum alone does not). Excludes the target's own cost when status == 'config-gated' (section 5: 'The target's own cost is excluded from totalCost entirely' -- the ancestor chain up to, not including, the cap technology itself). */
    totalCost?: null | number;
    /** True whenever any step is uncertain and/or any step's cost is unresolved -- see estimateReasons. False (and estimateReasons empty) only when every step is a determinate, cost-resolved available technology. */
    totalCostIsEstimate?: boolean;
    /** Empty when totalCostIsEstimate is false. Can carry both reasons at once. */
    estimateReasons?: ("uncertain-availability" | "unresolved-cost")[];
    /** Non-null only when status == 'config-gated' -- the target itself, excluded from steps/totalCost above (P-13's fourth AvailabilityState: a settings-toggle, determinate-unavailable fact, not an uncertain one). */
    configGatedTarget?: null | {
      technologyId: TechnologyId;
      name: string;
      icon: IconRef;
      /** Same semantics as availability.*.configGatedSubject -- null when the megastructure name itself doesn't resolve. */
      subject: null | string;
    };
  } };
}

/** spec/00-overview.md: descriptions, weight modifier lists, repository links, chunked and lazily fetched when a popup opens. One artefact per technology (or a small batch); fetched on demand, never part of the initial base-dataset load. */
export interface DetailPayload {
  schemaVersion: SchemaVersion;
  technologyId: TechnologyId;
  /** P-12.1. Localised, with embedded formatting/variable tokens resolved or safely stripped (P-12.1). English only for v1 (D-9). */
  description: string;
  repeatableCostProgression: null | (number)[];
  /** P-12.5/P-15. Overwriting is not vanilla-only -- ACOT redefines vanilla technologies directly, and AoT redefines ACOT technologies, so a vanilla baseline does not exist for most overwrites in the corpus. 'definedBy' is who defined the winning block; 'overwrites' is the source of the block it replaced (null if this technology was never redefined -- distinct from 'was redefined but the winner IS vanilla', which cannot happen since vanilla loads first). 'label' is the precomputed presentation string for the popup (P-12.5), e.g. 'Vanilla', 'ACOT', 'Vanilla (modified by ACOT)', 'ACOT (modified by AoT)' -- computed at build time per Stage 3's 'no runtime derivation of presentation logic from raw fields' rule. */
  source: {
    definedBy: SourceMod;
    overwrites: null | SourceMod;
    label: string;
  };
  /** P-15: for a redefined technology, which fields differ from the source it replaced (the immediately-preceding definition in load order, whatever its source -- NOT always vanilla; see 'source' above). Null when 'source.overwrites' is null. */
  overwriteDiff: null | {
    /** A field absent after overwrite but present before is a change, distinguishable in the underlying resolution report from a field that was never present on either side -- this list carries only the field name, so consult the S-2 overwrite report for which direction a field was added/removed/changed. 'prerequisites' is diffed as a set (reordering alone is not a change); the technology's own prerequisites list elsewhere in this payload preserves declaration order from the winning definition for display. */
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
  /** D-14 (spec/decisions.md): `technology_swap` alternates whose trigger is NOT fully expressible on the 3-axis empire model (origin, civic, species-trait, ascension-perk, or galaxy-situation leaves -- anything outside `pipeline.availability.AXIS_FACTS`). Never substituted onto the card face or into the empire overlay (that would assert an empire fact this tool cannot verify) -- listed here instead, in the popup only, same precedent as ascension-perk gates: the tree shows what exists and what you would need, never assumes it. A technology with only axis-expressible swaps (or no swaps at all) has an empty array here, not an omitted field. */
  variants: ({
    name: string;
    icon: IconRef;
    /** Human-readable rendering of the swap's trigger (pipeline.trigger_text.describe_condition), same renderer as weight.modifiers[].conditionText below. Falls back to raw trigger source text when no dedicated phrasing exists for a leaf -- never fabricated prose. */
    conditionText: string;
  })[];
  /** P-12.8. No evaluated weight (D-4) -- base weight plus conditions only, never a computed final number. */
  weight: {
    base: number;
    modifiers: ({
      factor: number;
      /** Human-readable rendering of the modifier's trigger condition. NOT YET BUILT as of this schema's authoring -- see HANDOFF.md's extraction-gap note on a trigger-to-text renderer; this field's presence in the schema does not imply the generator exists yet. */
      conditionText: string;
    })[];
  };
  /** D-18 (spec/decisions.md): the exact, accepted cost of the depth-1 ACOT/AoT rendering-scope closure -- a prerequisite this technology names in its own source that is NOT rendered as a node (reachable only via ANOTHER ACOT/AoT technology, not directly from anything rendered). Localised names, best-effort resolved (falls back to the raw technology key if genuinely unresolvable -- never blocks the build, since this is a supplementary note about a technology OTHER than the one this payload describes). Empty for the overwhelming majority (974/977) -- real corpus: exactly 3 technologies carry 1-2 entries each. Never a card badge (three affected nodes doesn't justify a new indicator) -- popup-only, alongside a fixed client-side note that the name is outside the rendered scope. */
  offTreePrerequisiteNames: (string)[];
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
  /** D-10's profile-dependent metric only (spec/decisions.md's D-10, amended when the metric split landed): a technology whose resolved state varies by profile. Per-profile rate, all twelve, plus each profile's delta against the previous build -- the exact figure the 3% warn / 10% ceiling / ratchet are evaluated against. Deliberately excludes unconditional uncertainty (see `unconditionalUncertainty` below) -- pooling the two into one rate would let the ceiling fire on, or hide behind, a figure it was never meant to govern. */
  profileDependentUncertainty: ({
    profile: EmpireProfile;
    rate: number;
    previousRate: number;
    status: "ok" | "warn" | "fail";
  })[];
  /** D-10's unconditional metric (spec/decisions.md's D-10): technologies uncertain under all twelve profiles identically. A data-completeness figure with its own regression ratchet -- NOT subject to the 10% ceiling or 3% warn threshold that govern profileDependentUncertainty, because it measures a different thing (see D-10's reasoning). categoryDistribution classifies every unconditionally-uncertain rendered node by the reason category its undecidable leaf falls into (pipeline/trigger_text.py's ReasonCategory) -- the deliverable that determines whether this is a presentation problem (most nodes explainable) or a data problem (most nodes opaque). */
  unconditionalUncertainty: {
    count: number;
    previousCount: number;
    rate: number;
    previousRate: number;
    categoryDistribution: ({
      category: string;
      count: number;
    })[];
  };
  missingInlineScriptParameterCount: {
    current: number;
    previous: number;
  };
  /** Item 1 (later session): the dev health monitor's data -- every rendered technology with at least one UNCERTAIN profile, with the human-readable trigger text (pipeline.trigger_text.describe_condition, never raw AST) and ReasonCategory that caused it, so the user can review remaining uncertainty and decide what's a fixable data gap versus what's genuinely undecidable game state. `unconditional` is true when all twelve profiles are UNCERTAIN identically (in which case `perProfile` still lists all twelve, for uniformity -- the client doesn't need a second code path to render the unconditional case). Sorted by technologyId for a stable, diffable order across builds. */
  uncertainTechnologies: ({
    technologyId: TechnologyId;
    name: string;
    unconditional: boolean;
    perProfile: ({
      profile: EmpireProfile;
      category: string;
      description: string;
    })[];
  })[];
  tierPromotions: ({
    technologyId: TechnologyId;
    declaredTier: number;
    promotedColumn: number;
  })[];
  /** D-14 (spec/decisions.md): technology_swap alternates with `inherit_icon = no` (an explicit request for their own icon) whose own icon file does not exist in the vendored corpus -- `pipeline/icons/resolve.py` correctly and deliberately leaves these as an unresolved icon-atlas candidate (never silently redirected there, per that module's own docstring: redirecting would override an explicit authorial refusal). This is a SEPARATE, presentation-layer diagnostic: when EMITTING the dataset, `pipeline.dataset_emit` falls back to the owning technology's own icon for display purposes only, so the card shows something rather than nothing -- this list makes that fallback visible rather than silent. Never fires for a swap that simply never asked for its own icon (inherit_icon omitted or 'yes', the default/legitimate base-icon-reuse case) -- only for the `inherit_icon = no`-and-nothing-found case. If this list shrinks on a future re-vendor, upstream shipped a real icon and the fallback is no longer needed for that entry; if it grows, a swap lost icon coverage. */
  swapsRenderingOnInheritedIcon: ({
    technologyId: TechnologyId;
    swapKey: string;
  })[];
  unrecognisedGatePatterns: (string)[];
  missingLockReasonOverrides: (string)[];
  unresolvedTriggers: (string)[];
  unresolvedModDependencies: (string)[];
  /** P-12.9 section 6's tripwire (spec/P-12.9-research-path.md): a technology whose OWN availability state is available/uncertain for the paired profile, but whose ancestor closure still contains a dead end (a plain, non-alternative prerequisite that's itself locked, or an alternative OR-group with zero viable candidates) -- the 'looks researchable but has no route' case the real corpus never produces today. Empty is the expected, healthy state; a non-empty entry here is the signal to investigate, not a normal, ignorable occurrence. */
  unresolvableResearchPaths: ({
    technologyId: TechnologyId;
    profile: EmpireProfile;
  })[];
  /** Vendoring-automation investigation (spec/decisions.md): which of the four sources (in load order) this build actually had `vendor/` content for. Vanilla and Gigastructural Engineering are always present in a valid build (their absence is a hard build failure elsewhere, not something this array softly reports); ACOT and/or AoT absent is a real, SUPPORTED reduced-corpus build mode -- Stellaris (Vanilla) cannot be fetched in CI at all (requires a Steam account that owns the game), which is why the dataset is built locally and deployed via workflow_dispatch rather than built in CI. `placeholderTechnologiesAbsent`/`vanillaTechnologiesRevertedFromAcotOverwrite` below are the loud, specific consequences of ACOT/AoT specifically being missing from this list. */
  vendorSourcesLoaded: (SourceMod)[];
  /** Empty unless ACOT and/or AoT is missing from `vendorSourcesLoaded`. The real technologies whose `requiresMods` names the missing source in a full build -- Gigastructures' own 'supertensile alternate' content (`giga_17_alternative_mega_build.txt`), the actual reason ACOT/AoT are vendored at all: they show the TRUE prerequisites of those alternates. A build missing these is plausible and self-consistent (no dangling edges, no alternative-only gaps) precisely because nothing else looks broken -- this field exists so the gap is stated, not discovered. */
  placeholderTechnologiesAbsent: ({
    technologyId: TechnologyId;
    requiresMod: SourceMod;
  })[];
  /** Empty unless ACOT is missing from `vendorSourcesLoaded`. Vanilla technology keys ACOT redefines (P-15) in a full build -- without ACOT, these revert to their vanilla content and REAPPEAR in the rendered set, having been excluded from the rendering-scope closure in their ACOT-overwritten form. This is exactly why the reduced-corpus node count is NOT a simple subtraction (980 - 7 = 973 is wrong; the real figure is 977 -- 7 fewer for the missing placeholders, 4 more for these reversions). `contentDiffersFromOverwrite` distinguishes the two real cases so the diagnostic doesn't imply all entries differ equally: most of ACOT's overwrites here only add modifiers, invisible to this tool's display regardless of which version renders -- `false`. The titan hull technologies are the documented exception, where ACOT's content materially differs from vanilla's -- `true`. */
  vanillaTechnologiesRevertedFromAcotOverwrite: ({
    technologyId: TechnologyId;
    contentDiffersFromOverwrite: boolean;
  })[];
  /** P-15/spec/P-15-overwrites.md. Two distinct sections -- different causes, different repairs, never collapsed into one list. See pipeline/overwrites.py's build_overwrite_report. */
  overwriteReport: {
    /** A technology key redefined outright by a later source. The diff baseline is the immediately-preceding definition in load order, whatever its source -- NOT always vanilla; most of the corpus's overwrites have no vanilla baseline at all (see spec/P-15-overwrites.md). */
    technologyBlockOverwrites: ({
      technology: TechnologyId;
      definedBy: SourceMod;
      overwrites: SourceMod;
      label: string;
      changedFields: (string)[];
      /** Full per-field diagnostic detail: presence before/after (distinguishing a field that was removed from one that was never present), and both the raw pre-resolution form and the @variable-resolved value -- a literal-to-variable-reference change is a mechanism change, not just a value change. */
      fieldChanges: ({
        field: string;
        beforePresent: boolean;
        afterPresent: boolean;
        beforeRaw: unknown;
        afterRaw: unknown;
        beforeResolved?: unknown;
        afterResolved?: unknown;
      })[];
    })[];
    /** A `@name` scripted variable redefined by a later source, changing the effective cost/weight of every technology that references it without touching those technologies' own blocks -- a distinct overwrite mechanism from a technology-block redefinition. */
    scriptedVariableOverwrites: ({
      variable: string;
      definedBy: SourceMod;
      overwrites: SourceMod;
      affectedTechnologies: (TechnologyId)[];
    })[];
  };
}
