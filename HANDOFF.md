# Handoff — Stage 1 (Extract) complete, Stage 2 (Compute) starting

Paste this at the start of a new conversation to carry context over.

This tells you what exists, what's guaranteed about it, what's been deliberately left undecided
and why, how this project is worked on, and where to start.

`spec/` is authoritative; `CLAUDE.md` is the running summary. This file is neither — it's a
point-in-time status report. If it goes stale, trust `spec/` and `CLAUDE.md` over this file, and
update or delete this file rather than letting it drift.

---

## What this is

An interactive web tech tree visualiser for the Stellaris mod *Gigastructural Engineering &
More*. Static site, no backend, deployed to GitHub Pages at
`github.com/Tempest113/Gigastructural-Engineering-Tech-Tree`. This is v2 — v1 existed and is
being rebuilt properly.

## How we work

The build happens in **Claude Code** (IntelliJ plugin). This chat is for design decisions,
visual review, reasoning through a problem before committing to it, and writing prompts to
paste into Claude Code. Keeping implementation out of chat is deliberate — v1 became
prohibitively expensive because the whole transcript was resent every turn.

**Standing instructions for Claude in this chat:**

- End every message with a short numbered list of actions the user needs to take, after
  explaining them in more detail above. Where an action is a question, include a simplified
  version of it plus any relevant suggestions.
- Never act without confirmation of intent. Don't produce files or run work speculatively.
- Draft every Claude Code prompt explicitly and in full, ready to paste without further
  composition.

The user defers technical and visual judgement calls to Claude, and contributes the
mod-specific domain knowledge. Claude is expected to make the call and justify it, not to
present a menu of options.

## Methodology that has worked — keep doing this

- **Evidence before design.** Every time a corpus assumption was checked rather than carried, it
  either broke or revealed something better. The localisation value-scanning rule, the
  `inherit_icon` resolution channel, the version-suffix identity question and three separate
  Clausewitz grammar rules all came from surveys, not reasoning. Ask Claude Code to survey with
  raw text and **report before implementing**, then review the findings before it proceeds.
- **Raw inspection only.** Never conclude anything about source syntax from output that passed
  through `repr()`, `pprint` or any formatter. A single misread `repr()` once produced a false
  "single-quoted strings exist" finding that drove real but baseless tokeniser changes. This is
  a rule in `CLAUDE.md`.
- **Iterative critical review.** Three rounds on the spec, each finding real structural problems.
  When asking for review, say explicitly not to manufacture findings if nothing is left —
  otherwise later rounds pad.
- **Prove a negative result before believing it.** A clean run means nothing until the detector
  is shown capable of a non-clean one. The round-trip mutation harness exists for exactly this
  reason and caught a comparator that would have passed both historical bugs.
- **Counts don't move silently.** When a reported number changes between sessions (352 vs 353
  files; 3 vs 2 malformed entries), reconcile it before proceeding. Both instances turned out to
  be real — one a discovery bug, one a deliberate reclassification.

## Deliberately deferred

- **Deployment / GitHub Pages skeleton** for the real app is still postponed — groundwork first,
  no half-built site while the pipeline is still moving. **But the delivery path itself is now
  proven, separately**: `deploy-spike/` is a throwaway static page (no framework, no build step)
  deployed by `.github/workflows/deploy-spike-pages.yml`, proving base-path resolution under
  this repo's real GitHub Pages project subpath, the MIME type a typed-array side-file is
  actually served with, and that the lazy-fetch pattern works against real static hosting rather
  than a local dev server — the four things that are silent until they fail, verified now rather
  than discovered while debugging the real renderer. See `deploy-spike/README.md`. **Manual
  one-time setup needed in the GitHub UI** — Settings → Pages → Build and deployment → Source →
  "GitHub Actions" (not "Deploy from a branch") — the workflow cannot enable Pages for the repo
  by itself; until that's set, the workflow's `actions/deploy-pages` step fails with a clear
  "Pages not enabled" error rather than silently no-opping. Delete `deploy-spike/` and its
  workflow once Stage 3 has a real deploy pipeline of its own.
- **Blokkats SVG pattern tile.** Needs tracing from the supplied flag image. Unrelated to
  pipeline work, not blocking anything.

---

## Architecture

Three stages, boundaries load-bearing:

1. **Extract** (Python, CI) — parse Clausewitz script and localisation, decode icons, pack
   atlases. **Complete.**
2. **Compute** (Python, CI) — resolve overwrites, build DAG, evaluate triggers per empire
   profile, assign layout, route edges, emit dataset. **Starting.**
3. **Render** (TypeScript + PixiJS, browser) — load dataset and draw it. **Not started.**

The browser never parses Clausewitz and never computes layout. The dataset schema is a
cross-language contract: JSON Schema in `schema/`, TypeScript types generated from it, Python
output validated in CI. **This contract is now written** — five artefacts (base dataset, empire
overlay, detail payload, search index, diagnostics), each independently `schemaVersion`'d — see
"What's built" below.

## Sources and load order

Ordered, lowest first: vanilla Stellaris 4.5 → Gigastructures (pinned commit, GitHub) → ACOT →
AoT. ACOT and AoT are Steam Workshop only, cannot be pinned, vendored manually. AoT requires
ACOT. Overwrite resolution is whole-key replacement, never field-level merge.

Source files live in gitignored `vendor/`, populated by `tools/collect_vanilla.py`. Nothing
third-party is ever committed.

## Locked decisions

Full detail in `spec/` (23 files) and `CLAUDE.md`. Read `CLAUDE.md` before making any design
call — the headlines below are a pointer, not a substitute:

- **Empire model**: three independent axes — gestalt/authority (regular, hive, machine),
  shipset (mechanical, biological), nomadic (yes/no). Twelve profiles. Origins not an axis.
- **Ascension perks are gates, not profile facts.** The tree shows what you'd need, never
  assumes you have it.
- **Mod scope**: renders vanilla + Gigastructures, plus ACOT/AoT technologies only where they
  fall in the rendering-scope closure (prerequisite edges only) of a rendered technology. Node
  set is profile-invariant. Separately, a per-profile structural-reachability check over all
  three edge kinds drives lock state — these two computations are deliberately distinct and
  named so they don't drift back together. Conflating them is a correctness bug.
- **No primary prerequisite.** Multiple prerequisites are all equally required.
- **Layout**: crisis factions are horizontal lanes, tiers are vertical columns, orthogonal.
  Single global column grid, lanes never compress. Tier range unbounded (ACOT reaches T9+).
- **Colour**: background = research area or crisis faction; outline = area unless rare or
  dangerous, dangerous outranks rare, both = 45° split. Colour never the sole carrier. Exact
  hexes in `CLAUDE.md`; `tokens/` is the intended single source of truth and does not exist yet.
- **Unknown tolerance (D-10)**: 10% ceiling per empire profile (worst profile, not pooled), 3%
  warn, plus a no-regression ratchet.
- English only for v1, pipeline language-parameterised.

---

## What's built

Five extraction packages plus the dataset schema contract, each self-contained and separately
tested, none merged into a shared "do everything" module:

- **`pipeline/clausewitz/`** — hand-written tokeniser + recursive-descent parser for Clausewitz
  script (not a general-purpose parser; grammar derived entirely from real corpus evidence, see
  `tests/fixtures/NOTES.md`). Produces a lossless AST: duplicate keys survive as ordered lists,
  comments are preserved with position, comparison operators other than `=` are kept verbatim.
  Also owns `serializer.py` and `roundtrip.py` — see "Standing invariants" below.
- **`pipeline/variables.py`** — `@scripted_variable` resolution. Memoised recursive lookup (not a
  sequential pass), whole-key last-definition-wins across load order, hard-fails on an undefined
  reference or a reference cycle (naming the full cycle chain).
- **`pipeline/inline_scripts.py`** — `inline_script` expansion. Text substitution on raw source
  before tokenising (required — ~46% of real `$PARAM$` usage is embedded mid-token, which no AST
  node shape can represent), then parsed with the ordinary Clausewitz parser. Runs before
  `@variable` resolution.
- **`pipeline/localisation/`** — hand-written parser for Paradox's localisation format. **Not
  YAML** — `§` colour codes, `£icon£` tokens, embedded colons, doubled/escaped quotes, and
  version-suffixed keys all fall outside the YAML spec; a YAML library would variously reject,
  coerce, or silently mangle real content. Preserves all markup verbatim, resolves nothing.
  **Value scanning is first-quote-to-last-quote-on-the-line — the inverse of the Clausewitz
  string rule.** 970 lines carry literal internal quotes; scanning to the next unescaped quote
  truncates them into plausible-looking short strings with no error. Do not reuse the Clausewitz
  scanner here.
- **`pipeline/icons/`** — technology/ascension-perk → icon-file resolution, DDS decoding
  (level 0 only), and deterministic, size-capped atlas packing to WebP (lossless) with PNG
  fallback. Sheets capped at 2048×2048 because WebGL's guaranteed `MAX_TEXTURE_SIZE` floor is
  2048 and mid-range mobile GPUs commonly report 4096 — an uncapped sheet fails to upload and
  every icon disappears, breaking P-9.
- **`schema/`** — the dataset schema itself: `common.schema.json` (shared `$defs` — `ThreeState`,
  `EdgeKind`, the composed `EmpireProfile`/`EmpireTypeConstraint` axis types, `Edge` with its
  `from`/`to` direction convention stated once as the property descriptions, `Gate`, `IconRef`,
  `GeometryRef`) plus one schema per artefact (`base-dataset`, `empire-overlay`,
  `detail-payload`, `search-index`, `diagnostics`). `schema/generated/dataset-types.ts` is
  generated from it by `tools/generate_typescript_types.py` — hand-written in Python, not an
  off-the-shelf `json-schema-to-typescript` run, because this environment has no Node/npm and
  D-12 already commits the pipeline to Python end to end. **Unverified as TypeScript** — the
  drift test proves the checked-in file matches a fresh generator run, which is not the same as
  proving it compiles; no `tsc` exists in this environment. `TODO(Stage 3)` recorded at the top
  of the generator and in CLAUDE.md's Open Items: add a `tsc --noEmit` CI step once the Node
  toolchain lands with the PixiJS renderer. `pipeline/dataset_schema/` is the Python-side
  validator (`jsonschema` + a `referencing.Registry` wiring the local `$ref`s together) plus the
  canonical `EmpireProfileIndex` derivation (`pipeline/dataset_schema/empire_profile.py` —
  composed axes are the identity model, this integer is a documented, storage-only encoding of
  them for indexing the 12-slot `availabilityMatrix`; strides are *derived* from axis
  cardinalities at import time, not hardcoded, with an import-time bijection assertion —
  hardcoding was the original bug: correct for today's 3×2×2 shape but silently
  collision-prone if any axis ever grows) and the `availabilityMatrix`/overlay consistency check.

## Standing invariants — tests that exist to keep something from regressing silently

These aren't "just tests" — each closes a specific class of bug this project already hit once. Do
not weaken or delete them without understanding what they guard against; read the module
docstring named before touching the logic.

- **Round-trip adjacency check** (`pipeline/clausewitz/roundtrip.py`,
  `tests/clausewitz/test_roundtrip*.py`). A file parsing without raising proves nothing about
  whether it parsed into the *right* AST — two real bugs (`flag@root` silently split; a `$PARAM$`
  silently glued onto adjacent identifier text) parsed cleanly into wrong ASTs. The detector
  serialises the AST back to text and compares token streams against the source, and critically
  compares `preceded_by_whitespace` (whether *any* separator existed between two tokens) —
  **never** reconstructed by asking the tokeniser "could this pair lex differently," because that
  consults the same tool under test and would silently pass the exact corruption it exists to
  catch.
  - **Allowlist**: `tests/clausewitz/roundtrip_allowlist.json`, 433 entries across 48 files —
    every one a same-token, presence-only whitespace divergence, never a content mismatch. Read
    the file's own `_rationale` field before adding an entry; an entry only applies while the
    exact recorded token pair still matches.
- **Mutation harness, permanent** (`tests/clausewitz/test_roundtrip_detects_mutations.py`).
  Reintroduces the two historical tokeniser bugs via monkeypatching, so the *same* mutated
  tokeniser is used for both AST construction and comparison — the actual adversarial scenario —
  and asserts the round-trip check still fails on each. Also asserts a weaker comparator (no
  `preceded_by_whitespace`) would have silently passed both. Keep this file; it exists to stop
  the comparator being "simplified" back into blindness.
- **Determinism tests** (`tests/icons/test_pack.py`). Packing the same input twice is
  byte-identical (RGBA buffer, WebP bytes, PNG bytes, independently checked). Changing one source
  icon's pixels changes only its own sheet's content hash and leaves every other icon's
  sheet/position assignment untouched.
- **Corpus-size drift guards.** 273 Clausewitz files; 353 localisation files; the icon
  unresolved-candidate counts (19 technology/swap, 6 ascension perk) and zero ImageMagick
  fallbacks. A failure means vendored content or discovery logic has drifted — **re-derive the
  expected number before trusting anything measured against it, don't just bump the assertion.**
- **TypeScript drift test** (`tests/schema/test_typescript_drift.py`). Re-runs
  `tools/generate_typescript_types.py` and diffs against the checked-in
  `schema/generated/dataset-types.ts`. Without this, nothing stops the JSON Schema and the
  TypeScript types from being hand-edited independently until they silently disagree — exactly
  the failure mode the generated-file approach exists to prevent.
- **`availabilityMatrix`/overlay consistency check**
  (`pipeline/dataset_schema/empire_profile.py`'s `check_availability_matrix_matches_overlays`).
  The base dataset's compact 12-slot matrix and each empire overlay's richer per-profile
  `availability.state` are redundant by design (see the schema field's own description) — nothing
  currently wires this into a real build (Stage 2 doesn't emit datasets yet), but the check
  exists and is tested now so Stage 2 has no excuse to skip it later.

All of the above are gated behind `vendor/` being populated locally (gitignored, CI never has
it) — see each test file's `skipif`. CI-safe regression coverage over a small committed fixture
subset exists in parallel (`tests/fixtures/`, manifest-driven, `tools/regenerate_fixtures.py`).

## Vendor-backed corpus counts

| | Count |
| --- | --- |
| Clausewitz scoped corpus (`common/{technology,scripted_variables,scripted_triggers,ascension_perks}` + reachable `inline_scripts`, 4 sources) | 273 files, 0 parse errors |
| Localisation (`localisation/english`, 4 sources, filename-suffix discovery) | 353 files, 0 file-level failures, 193,496 resolved keys |
| Technology icon candidates (technologies + `technology_swap` alternates) | 2,121 candidates, 2,102 resolved, 19 unresolved |
| Ascension-perk icon candidates (perks + `tradition_swap` alternates, 3 sources — AoT has none) | 69 candidates, 63 resolved, 6 unresolved |
| Cross-source icon-file collisions (same relative path, >1 source) | 31 |
| Technology atlas sheets (2048×2048 cap, WebP lossless) | 4 sheets: 1008×2016 ×3, 1008×118 |
| Ascension-perk atlas sheets | 1 sheet: 504×384 |

Full pytest suite: **1,077 passed, 0 failed** (`pytest tests/`).

**Empire-type edge shape, confirmed against the corpus:** every real `prerequisite`/
`potential-gate`/`alternative` edge's empire-type applicability factors as a product of
independent axis constraints (25 `has_technology`-plus-axis-fact sites inspected raw; each is
either unconstrained or a single-axis rectangle — never an irregular union spanning multiple
axes). This is what licenses `schema/common.schema.json`'s `EmpireTypeConstraint` shape
(per-axis arrays, no flat 12-enum, no bitmask in JSON) — it isn't an assumption, it's a checked
finding.

**The "17 parse failures in `scripted_triggers/`" open item: resolved, not lost.**
`tests/fixtures/NOTES.md`'s "Scripted-triggers grammar gaps" section documents 17 real parse
failures found rescoping the Clausewitz corpus run to the four required directories, confined to
`scripted_triggers/` plus one `inline_scripts/` file, across six grammar constructs (conditional
`[[GUARD] ... ]` blocks, pipe-delimited `value:name|K|V|` calls, `$NAME|default$`, `$SCOPE$?`,
bare mid-token `$PARAM$` substitution, inline arithmetic `@[ ... ]`). All six were fixed earlier
in this project's history — before the round-trip/localisation/icon/schema work in this
document, not during it. **Verified fresh this session**, not just inferred from history: a
direct re-parse of the full 273-file scoped corpus, including every `scripted_triggers/` file,
right now, produces **0 parse failures**. The item dropped out of this file's rewrite because it
was resolved, not because it was forgotten — recorded here explicitly now specifically so that
ambiguity can't recur. If this count is ever non-zero again, that's a real regression in the
tokeniser/parser grammar, not a residual item finally being noticed.

## Recorded diagnostic sets — what exists, what's still undecided

Every one is a *diagnostic*, not a build failure, by deliberate design. Deciding whether any
should fail the build is explicitly left to Stage 2, not guessed at in Stage 1.

- **`roundtrip_allowlist.json`, 433 entries.** Reviewed, closed, all adjacency-only. A maintained
  list, not an open question.
- **`ValueIsKeyDiagnostic`, 134 hits.** A key's winning value is verbatim another key that exists
  in the resolved table — almost certainly an unfinished translation. Narrowed to values
  containing `_`; an unrestricted check returned 3,370 hits of which 2,854 were ordinary
  self-referential English words (`OK` → `"OK"`), a legitimate Paradox convention. **Do not
  re-widen this check blind** — the false-positive count is in the diagnostic's docstring.
  **Undecided**: whether Stage 2/3 treats any as build-blocking.
- **`UnquotedValueDiagnostic`, 1 hit** (`acot_omegan_blessed`). Parsed as valid, not malformed,
  but flagged because one occurrence in ~194,000 lines isn't enough to call the shape reliable.
  **Undecided**: nothing actionable; exists so a future rise is visible rather than absorbed.
- **`LocalisationTable.malformed`, 2 hits**, both ACOT, both real upstream typos. No local fix.
  These become failures only if the affected key is looked up via `.require()` for a displayed
  string; `.get()` returning `None` is the harness. This is the intended terminal state.
- **`IconResolutionResult.unresolved`, 19 technology/swap + 6 ascension perk.** See the two
  `TODO(Stage 2)` blocks in `pipeline/icons/resolve.py` in full. Summarised:
  1. **Scope-conditional failure.** Recorded uninterpreted; Stage 1 does not know which are
     permanently-unreachable technologies (needs trigger evaluation) versus real gaps. The one
     unambiguous real gap (`giga_tech_ring_world_swap_no_habitables`, explicit `inherit_icon = no`
     with no shipped icon) is deliberately left unresolved rather than guessed at. The 6
     ascension-perk cases (`ap_colossus`, `ap_eternal_vigilance_nomads`,
     `ap_organo_machine_interfacing_assimilator`, three `ap_galactic_wonders_*` DLC variants)
     have not been individually investigated — likely DLC-conditional perks resolved through a
     mechanism this model doesn't cover, but that's a guess, not a finding.
  2. **Atlas content scope.** The atlas packs every resolvable icon across all four sources
     unconditionally, including all of ACOT's and AoT's. Rendering scope admits ACOT/AoT
     technologies only within the prerequisite-edge closure of a rendered technology. **The
     measured sheet sizes are an upper bound, not the real number.** Filtering by that closure is
     Stage 2 work.
  3. **SETTLED: atlases are excluded from P-10's ≤2 MB budget.** That budget is defined as the
     base dataset's compressed transfer size specifically (`spec/P-10-performance-automation.md`,
     amended this session); atlas image bytes are lazy (P-9/`implementation-notes.md`) and were
     never part of it. Atlases instead get `pipeline/icons/pack.py`'s `MAX_TOTAL_ATLAS_BYTES`
     (12 MB combined WebP bytes) — **a tripwire, not a budget**: it sits ~1.4x above today's
     measured ~8.65 MB *unfiltered* ceiling, so it exists to catch a pipeline bug pulling in far
     more sprites than intended, not to express a size target. `TODO(Stage 2)`, recorded next to
     the constant: a real budget can only be set once icon resolution runs against the P-16
     closure and the true, filtered figure is known.
- **`config/icon_overrides.txt`** is currently empty by design. Expect entries only after a
  *human* decides what's correct for each case — not a future agent session guessing.
- **P-13's lock-reason override table** is a newly-identified hand-maintained config file, not
  yet created (added to `CLAUDE.md`'s and `spec/P-10`'s config enumeration this session, but the
  file itself doesn't exist — Stage 2 needs it, and the build must warn when an override is
  missing per P-13).
- **No trigger-condition → human-readable-text renderer exists yet.** Needed for two schema
  fields that already exist (`detail-payload.schema.json`'s `weight.modifiers[].conditionText`,
  and the empire-overlay's trigger-derived lock `reason` string) but have nothing populating
  them. The raw material (preserved boolean trigger structure) is already in the Clausewitz AST
  — this is a missing *component*, not missing data. Easy to mistake for "just wire up existing
  data" when it's actually new logic; don't underestimate it when scoping Stage 2.

**Base dataset size, estimated against the real split:** ~275–305 KB compressed against the
≤2 MB budget (~6–7x headroom), computed from 1,878 real technology-shaped definitions, real
localisation string-length samples (name median 22 chars, description median 154/mean 180 —
description itself stays out of the base dataset), and the search index moved to its own lazy
artefact. Not measured against a real Stage 2 build (doesn't exist yet) — re-derive once one
does, the same way every other estimate in this document should be re-checked before being
trusted blind.

---

## Ordered next steps

The dataset schema (`schema/`) is done — see "What's built" above. Stage 2 now has a contract to
emit into.

1. **Overwrite resolution (P-15).** Whole-key, last-definition-wins across load order — the same
   rule already implemented in `pipeline.variables` and `pipeline.localisation.table` needs its
   canonical general form for technology definitions themselves. **This is the immediate next
   task.** Also the blocker for the icon atlas's research-area split (rejected this session
   specifically because it needs this) and for the trigger-condition-text renderer (needs a
   resolved technology record to render conditions against).
   **This ordering was checked, not just carried over** — see the analysis below.

**Sequencing check: P-15 vs. localisation, verified with evidence.** `pipeline.localisation` is
already Stage-1-complete and has zero remaining work — it isn't actually competing with P-15 for
"next task," so the real question was whether P-15 has a hidden dependency on it, or vice versa.
Checked both directions: (1) P-15's own outputs — the `Vanilla`/`Gigastructural Engineering`/
`Vanilla (modified...)` source enum (P-12.5) and the field-level diff list (cost/tier/
prerequisites/weight/category/flags, `schema/detail-payload.schema.json`'s `overwriteDiff`) —
are fixed enums and internal field names, never localised text; P-15 needs no resolved
localisation table to do its work. (2) `pipeline/localisation/table.py`'s own docstring states
the independence directly ("*never merged with... P-15's technology-overwrite table*") — its
last-wins resolution runs entirely over the loc corpus, keyed by loc key string, with no
reference anywhere to which source wins a technology-block overwrite. Neither blocks the other.
What *does* make P-15 come first is `spec/00-overview.md`'s own Stage 2 ordering — "Resolve
overwrites... Build the DAG... Evaluate triggers... Assign tiers... Route edges... Emit the
dataset" — every one of those needs the canonical (post-overwrite) technology record first,
including "attach a localised name to it." P-15 is the one genuine blocker on the critical path;
localisation is a leaf, consumed only at final dataset-emission time, zero schedule risk. The
current ordering is correct for the right reason, not by default.
2. **Partial trigger evaluator (D-10).** The highest-risk component in the project and the one
   D-10's unknown rate depends on entirely. Unblocks both `TODO(Stage 2)` items in
   `pipeline/icons/resolve.py`, gate detection (P-3's pattern-matching layer, distinct from the
   universal `potential-gate` edge extraction), rendering-scope computation generally, and the
   trigger-condition-text renderer noted above as a genuine gap.
3. **DAG build + P-16 ancestor closure**, which the icon atlas's real content scope depends on
   directly.
4. **Tier/column/edge computation, dataset emission** — the rest of Stage 2, now with a schema
   to validate output against (`pipeline/dataset_schema/`) on every build.
5. **Stage 3 (Render)** — nothing exists yet. Largest remaining body of work. The generated
   `schema/generated/dataset-types.ts` is what it builds against.
