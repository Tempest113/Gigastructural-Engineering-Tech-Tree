# Handoff — Stage 1 (Extract) complete, Stage 2 (Compute) emits real artefacts, Stage 3 (Render) next

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
present a menu of options. **This is a standing instruction, restated explicitly by the user
mid-project**: "We'll proceed with your recommendation for these sorts of things here on out."
Do not hand technical decisions back to him — make the call, state the reasoning, and flag
separately when something is genuinely a *game or mod* question rather than a technical one.

**The user's domain knowledge and screenshots have repeatedly caught bugs no test could.** This
is not a courtesy — it is the single most productive input channel in the project, and it works
because he is asked specific, answerable questions:
- A v1 screenshot showing a card badged "T5 ×5" exposed `is_repeatable`'s `levels < 0` bug (12
  misplaced technologies, full green suite).
- Pasting the `giga_mega_repeatable` inline_script template surfaced both the `cost_per_level`
  display gap and the lowercase-`not` operator question.
- Clarifying that `$name$_capped_r` is a **mod-configuration** flag, not a progress flag —
  correcting Claude's stated assumption — reclassified 50 nodes and produced the `config-gated`
  state.
- Clarifying that no core preset sets a cap to "1 + Repeatables" turned those 50 from *uncertain*
  into *determinate*.
- Correcting Claude's reading of v1's second failure (see the Layout model section) prevented an
  entire wasted design effort on untruncatable card text.
When a corpus finding is ambiguous, **ask him a specific game question** rather than inferring.

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
- **A green test suite doesn't mean the classification is right — it means the classification is
  self-consistent.** `pipeline.layout.is_repeatable` shipped with `levels < 0` as the repeatable
  test, every test for it passed, and the corrected 980-node corpus run reported "0 unresolved
  tiers" — nothing in the suite could have flagged that 12 real repeatable technologies (positive
  finite `levels`, same shape otherwise) were being silently placed in ordinary tier bands
  instead of the Repeatables band, because no test encoded "the real corpus's repeatable
  population is 88, not 76" as an expectation — that number wasn't known to be wrong yet. It was
  found by checking a user's v1 screenshot (a card badged "T5 x5", which cannot exist under
  `levels = -1`) against the real corpus, the same "evidence before design" habit as the
  `repr()` bug above, applied to a screenshot instead of raw text. **What would have caught it
  without the screenshot**: a test asserting the repeatable count against an independently
  re-derived corpus figure (the same "counts don't move silently" discipline above, applied
  pre-emptively rather than after a number happens to be reported twice) — or naming the
  predicate's assumption explicitly enough in a docstring/comment ("assumes unbounded" without
  ever checking the corpus for finite repeatables) that a later reviewer would think to challenge
  it. Neither existed; the mechanism-level unit tests (`levels = -1` → True, `levels = 5` → False)
  tested the rule faithfully, which is exactly why they couldn't catch that the rule itself was
  wrong.
- **A defect class, found by pattern-matching across sessions rather than treating each fix as
  isolated.** Three separate components — tier resolution (P-2's tier-source audit), `pipeline.
  layout.is_repeatable` (above), and `unconditionalUncertainty` (Stage 2 cleanup session) — each
  independently produced a plausible, error-free wrong answer for technologies in the
  `giga_tech_repeatable_*` family. Two of the three (tier, `unconditionalUncertainty`) share an
  exact mechanism: the field in question only exists on the technology block AFTER
  `inline_script` expansion, and a component reading the raw block sees no field at all rather
  than an error — silently wrong, not loudly broken. The general form: **any component that
  acquires technology data by a route other than the full expanded canonical record is at risk of
  this failure mode, and `giga_tech_repeatable_*` is the reliable canary**, because enough of its
  data exists only post-expansion that a raw-block consumer fails silently. See CLAUDE.md's
  "Availability evaluator" section for the full write-up and the audit of every component's input
  route this prompted — one real, not-yet-triggered gap found (`pipeline/icons/resolve.py` reads
  raw blocks unconditionally, currently zero-impact but the same shape of risk), reported, not
  fixed, pending a scoped follow-up. ~~Follow-up~~ **Done, next session**: `collect_candidates`
  now takes expanded documents (`pipeline/icons/build.py::resolve_kind` parses+expands before
  calling it); verified zero-impact on the real corpus as predicted (every existing exact-count
  assertion held unchanged), plus a synthetic regression test proving the expanded-vs-raw
  distinction actually matters when a template DOES define an `icon=` field. See CLAUDE.md's
  "Small targeted correctness pass" bullet.
- **The defect-class hypothesis paid off directly, not just as a warning.** The same "Small
  targeted correctness pass" session's `unclassified` jump (7→57 unconditional-uncertain nodes,
  all 50 `giga_tech_repeatable_*_cap`) was initially read as expected fallout of fixing the
  raw-vs-expanded bug — a real fix revealing real, previously-invisible undecidable content. A
  follow-up review of the actual template found it wasn't undecidable at all: both leaves in its
  `potential` are mod-configuration toggles, one already resolvable, one (`_capped_r`) not yet
  taught to the evaluator. Recognising it turned an "opaque, unclassifiable" bucket into a
  fully-explained, DETERMINATE result — and revealed that `locked`/`uncertain` were both the
  wrong label for it, prompting a fourth `AvailabilityState` (`config-gated`). The number this
  produced (209) is numerically identical to the ORIGINAL, pre-any-correction figure — a good
  reminder that "the number went back to what it used to be" is not evidence nothing needed
  fixing; two real, unrelated corrections can net to zero by coincidence. See CLAUDE.md's
  "`giga_tech_repeatable_*_cap` correctly categorized — CONFIG_GATED" bullet for the full
  writeup.

## Deliberately deferred

- ~~**Deployment / GitHub Pages skeleton** for the real app is still postponed~~ **Done across
  two sessions — `deploy-spike/` deleted, replaced by a real pipeline with a deliberately
  PERMANENT (not interim) deploy model.** `client/` (TypeScript + PixiJS + Vite, foundation only,
  still no rendering logic) exists, typechecks cleanly, and builds. `.github/workflows/
  typecheck.yml` runs `tsc --noEmit` on every `client/**`/`dataset-types.ts` change — closed the
  `schema/generated/dataset-types.ts` "never actually typechecked" TODO from below: **zero
  errors**, verified three ways (see CLAUDE.md's "Stage 3 toolchain foundation is built" bullet).

  **Deploy model, decided in the second of these two sessions (D-15, spec/decisions.md) — read
  this before assuming CI can build anything**: the dataset cannot be built in GitHub Actions,
  ever, not as a temporary gap. Vanilla Stellaris requires a Steam account that owns the game;
  CI-side building would mean storing real Steam credentials as a secret (a security/ToS
  exposure) or redistributing extracted game files (foreclosed by this project's own
  never-redistribute-vendor-content rule). No automation closes this. Consequently:
  - The dataset is built LOCALLY (`tools/build_dataset.py`, where `vendor/` already exists) —
    **NOT committed to the repo** (`client/public/dataset/` is gitignored — an earlier session's
    opposite decision was reversed once the redistribution/git-bloat/staleness costs were
    weighed against the small deploy-cadence convenience of committing it).
  - `tools/deploy_local.sh` (new) builds the dataset, builds the client, zips `client/dist/`, and
    publishes it as a GitHub Release asset via the `gh` CLI — **not run for real this session**
    (creating a live Release is a "visible to others" action, left for a human to trigger).
  - `.github/workflows/deploy.yml` is `workflow_dispatch`-only: it downloads a named release's
    `dist.zip` and deploys it via the ordinary `actions/upload-pages-artifact`/`deploy-pages`
    steps. It builds nothing. Confirms Pages CAN deploy a build that happened elsewhere.
  - `client/public/dataset/integrity.json` (built into every local run, travels inside
    `dist.zip`): pipeline commit SHA + dirty-tree flag, `vendor/manifest.json`'s per-source
    provenance, which sources loaded, sha256 of every other artefact. **States provenance, does
    NOT verify it** — nothing can, given the constraint above. A byte mismatch is detectable; a
    false provenance claim is not, beyond trusting whoever ran the local build. Never describe
    this as CI-grade auditability in any future write-up.
  - Two alternatives were seriously considered and rejected as the PRIMARY model — a private
    artefact store (still needs a human to build+publish, just adds a hop) and CI building
    without ACOT/AoT (doesn't solve vanilla either way, and would make the canonical deployed
    site quietly different — 977 nodes, not 980 — by default). See D-15 for the full costing.

  **Icon atlases are now actually written** — closed a real gap the first of the two sessions
  left behind: `tools/build_dataset.py` built `base-dataset.json` referencing
  `technologies_0.webp` etc. but never wrote any atlas image file at all; the site could not
  render a single icon. Fixed: every sheet is encoded to WebP+PNG, content-hashed, referenced
  correctly. **Real measured total: 4,826,990 bytes WebP (4.60 MB) + 5,994,998 bytes PNG
  (5.72 MB) = 10,821,988 bytes combined**, verified loadable end to end (a real `Assets.load()`
  fetch, a real `Texture` tile crop, a real PixiJS `Sprite` drawn to canvas — not just "file
  exists on disk").

  **ACOT/AoT-absent builds get a loud, specific diagnostic.** Building without ACOT/AoT yields
  **977 rendered nodes, not 980 − 7 = 973** — see CLAUDE.md's "Stage 3 toolchain foundation is
  built" bullet or D-15 in spec/decisions.md for the full mechanism (4 vanilla technologies ACOT
  overwrites turn out not to be rendered at all in the FULL build, and reappear once ACOT is
  absent). `pipeline.dataset_emit.build_diagnostics` now reports this by name
  (`vendorSourcesLoaded`/`placeholderTechnologiesAbsent`/
  `vanillaTechnologiesRevertedFromAcotOverwrite`), and `tools/build_dataset.py` prints a loud
  console warning too. Both affected-technology lists are maintained constants with their own
  regression tests against the full corpus (not dynamically derivable — 3 of the 7 placeholders
  are reachable only through ACOT's own internal prerequisite chains).

  Historical record of what `deploy-spike/` (deleted) originally proved, kept for context since
  its four findings were re-confirmed against real data and a real hosting-layout simulation,
  not just inherited on faith:
  - Relative paths resolve correctly under the project subpath
    (`tempest113.github.io/Gigastructural-Engineering-Tech-Tree/`), not the domain root.
  - `.f32` side-file served as `application/octet-stream` — unrecognised extension falls back
    correctly, not mangled or refused.
  - Float32Array decoded to clean 0.5-increments (0.0, 0.5, 1.0, 1.5 …), confirming
    little-endian round-trips end to end. A byte-order mismatch would have produced garbage.
  - GitHub Pages serves gzip on BOTH `application/json` and `application/octet-stream` — measured
    9.34x on a ~982 KB synthetic JSON artefact against the 6x assumed in the P-10 estimate.
- ~~**GitHub Pages cache headers are not configurable — a Stage 3 decision, not something to act
  on now.**~~ **Decided.** `tools/build_dataset.py` content-hashes every artefact filename
  (`<name>.<sha256[:10]>.<ext>`, including icon atlases as of the second Stage 3 session) except
  two stable, unhashed entry points: `dataset/manifest.json` (the client fetches this first and
  reaches every other artefact only through it) and `dataset/integrity.json` (the provenance
  record, needs a stable name to be findable).
- **Blokkats SVG pattern tile.** Needs tracing from the supplied flag image. Unrelated to
  pipeline work, not blocking anything.

---

## Architecture

Three stages, boundaries load-bearing:

1. **Extract** (Python, CI) — parse Clausewitz script and localisation, decode icons, pack
   atlases. **Complete.**
2. **Compute** (Python, CI) — resolve overwrites, build DAG, evaluate triggers per empire
   profile, assign layout, route edges, emit dataset. **Emits real, schema-validated artefacts**
   (`pipeline/dataset_emit.py`) against the full vendored corpus — see "Ordered next steps" point
   4b and CLAUDE.md's "Stage 2 dataset emission is built" bullet. Not wired into an actual CI build
   command yet (`tools/`-level orchestration, `npm run build:data`-equivalent) — that plus real
   traffic through Stage 3 remain the gap to a shippable pipeline.
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
- **Layout (corrected — see D-13/D-16 and the "Layout model" section below)**: rows are the 13
  derived vanilla technology categories plus the 5 crisis-faction rows, faction-first-else-
  category and mutually exclusive (D-16, corrects an earlier draft where the crisis-faction lane
  was the row axis and category was only a sub-grid wrap key); **bands are DECLARED tier, never
  computed column** (D-13, unaffected by D-16). A node declared T5 sits in the T5 band regardless
  of promotion. Band headers show the declared tier and nothing else. Computed column is internal
  geometry governing horizontal ordering *within* a (row, band) cell, and is never displayed.
  ~10 declared-tier bands plus a terminal Repeatables band. Tier range unbounded in principle
  (ACOT reaches T9+), but the rendered set tops out around T8.
- **Colour**: superseded by D-16 — colour/pattern now encode the ROW (an area-coloured header
  chip on a category row, faction colour/pattern as row backing on a faction row), cards
  themselves neutral dark; research area is deliberately NOT colour-encoded inside a faction row
  (an accepted loss). Outline = area unless rare or dangerous, dangerous outranks rare, both = 45°
  split (unaffected by D-16 — this is about the card's own outline, not its background). Colour
  never the sole carrier. Exact hexes in `CLAUDE.md`; `tokens/`/`client/src/tokens.ts` is the
  single source of truth for node colours (edge colours were added there too, Stage 3 slice 3).
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
  off-the-shelf `json-schema-to-typescript` run — D-12 already commits the pipeline to Python end
  to end, and (as of a later session) there's no longer a "no Node/npm" reason either; the
  generator's own `tsc`-verified correctness (below) means swapping it for a Node dependency has
  no problem left to solve. ~~**Unverified as TypeScript**~~ **Verified, later session: zero
  errors.** `.github/workflows/typecheck.yml` runs `tsc --noEmit` over the whole `client/`
  project (which includes this file via `client/tsconfig.json`), closing the `TODO(Stage 3)` that
  used to sit at the top of the generator and in CLAUDE.md's Open Items — see CLAUDE.md's "Stage 3
  toolchain foundation is built" bullet for the three ways this was checked.
  `pipeline/dataset_schema/` is the Python-side
  validator (`jsonschema` + a `referencing.Registry` wiring the local `$ref`s together) plus the
  canonical `EmpireProfileIndex` derivation (`pipeline/dataset_schema/empire_profile.py` —
  composed axes are the identity model, this integer is a documented, storage-only encoding of
  them for indexing the 12-slot `availabilityMatrix`; strides are *derived* from axis
  cardinalities at import time, not hardcoded, with an import-time bijection assertion —
  hardcoding was the original bug: correct for today's 3×2×2 shape but silently
  collision-prone if any axis ever grows) and the `availabilityMatrix`/overlay consistency check.
- **`pipeline/overwrites.py`** — P-15 technology overwrite resolution. Whole-key,
  last-source-wins across load order (`Vanilla` < `Gigastructural Engineering` < `ACOT` < `AoT`),
  refusing to guess (raising `OverwriteOverrideRequiredError`) on the two shapes the corpus survey
  never validated a rule for — a 3-or-deeper source chain, or two definitions from the *same*
  source — unless `config/overwrite_overrides.txt` names the winner. Per-technology output: a
  `definedBy`/`overwrites`/`label` triple (generalising the old single vanilla-only case — most
  of the corpus's overwrites have no vanilla baseline: 19 of 25 are `ACOT`→`AoT`), and a
  field-level diff (cost/tier/prerequisites/weight/category/flags) against whatever the winner
  actually replaced, never hardcoded to vanilla. `cost`/`weight` are compared through
  `@variable` resolution (via `pipeline.variables`) so an indirect scripted-variable overwrite is
  visible even when the technology's own block is untouched, but the raw pre-resolution form
  (literal vs. `@name` reference) is retained alongside the resolved value — a mechanism change
  and a value change are tracked separately, never collapsed. `prerequisites`/`category` are
  diffed as sets (reordering alone is not a change — confirmed against the corpus with no
  counter-example, treated as an inference not a proven invariant); the *displayed* prerequisite
  order is a separate, declaration-order, depth-first list from the winning definition, kept
  deterministic across builds. `resolve_variable_overwrites` is the distinct scripted-variable
  overwrite layer: a `@name` redefined by a later source, changing every technology that
  references it in `cost`/`weight` without their own blocks being touched — a different cause
  from a technology-block overwrite, reported in its own section of `build_overwrite_report`'s
  S-2 diagnostics output (`technologyBlockOverwrites` / `scriptedVariableOverwrites`), never
  collapsed into one list. `pipeline/overwrite_overrides.py` loads
  `config/overwrite_overrides.txt` (same format and required-`#`-justification bar as
  `pipeline/icons/overrides.py`'s `config/icon_overrides.txt`) — checked in seeded empty, since
  the corpus survey found no case needing one. Tests: `tests/test_overwrites.py` (synthetic,
  mechanism coverage — presence-vs-absence, set-vs-order, mechanism-vs-value, the ambiguity
  guard), `tests/test_overwrite_overrides.py` (loader), `tests/test_overwrites_corpus.py` (real
  vendored corpus end-to-end, skipped when `vendor/` isn't populated, asserting the corrected
  25-overlap counts so a corpus refresh that silently changes them fails a test instead of going
  unnoticed).

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
  - **Allowlist**: `tests/clausewitz/roundtrip_allowlist.json`, 434 entries across 48 files —
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

| | Count | Δ vs. pre-re-vendor |
| --- | --- | --- |
| Clausewitz scoped corpus (`common/{technology,scripted_variables,scripted_triggers,ascension_perks}` + reachable `inline_scripts`, 4 sources) | 273 files, 0 parse errors | unchanged |
| Total technology-shaped definitions (`common/technology`, all occurrences across 4 sources, pre-overwrite-resolution) | 1,904 | new figure, not previously tracked as its own row |
| Distinct technology keys | 1,879 | unchanged (`tech_mega_engineering`'s key already existed in vanilla; the re-vendor added an *occurrence*, not a new key) |
| Round-trip allowlist entries | 434 | +1 (one new adjacency-only divergence in refreshed `giga_frameworld_triggers.txt`, reviewed) |
| Localisation (`localisation/english`, 4 sources, filename-suffix discovery) | 353 files, 0 file-level failures, **193,548** resolved keys | resolved keys **+52** (Gigastructures localisation content advanced along with the technology content when re-vendored to the pinned commit — same root cause, not a new one) |
| Localisation malformed entries / value-is-key diagnostics / unquoted-value diagnostics | 2 / 134 / 1 | unchanged (same files and lines) |
| Technology icon candidates (technologies + `technology_swap` alternates) | **2,122** candidates, **2,103** resolved, 19 unresolved | candidates/resolved **+1/+1** (the new `tech_mega_engineering` occurrence in Gigastructures is one more pre-resolution candidate, and it resolves cleanly against vanilla's existing icon); unresolved list unchanged, same 19 keys |
| Ascension-perk icon candidates (perks + `tradition_swap` alternates, 3 sources — AoT has none) | 69 candidates, 63 resolved, 6 unresolved | unchanged |
| Cross-source icon-file collisions (same relative path, >1 source) | 31 | unchanged |
| Technology atlas sheets (2048×2048 cap, WebP lossless), UNFILTERED | 4 sheets: 1008×2016 ×3, 1008×118; 8,387,616 bytes | corrected: this row's byte figure was previously mislabeled as 8,650,292 (that was tech+perk combined, see below) |
| Technology atlas sheets, FILTERED to P-16's 980-node rendered set (later session) | 2 sheets: 1008×2016, 1008×1468; 4,564,314 bytes | new row — the real build path now uses this, not the unfiltered row above |
| Ascension-perk atlas sheets (never filtered — see rendering-scope note below) | 1 sheet: 504×384; 262,676 bytes | byte figure added this session |
| Technology-block overwrites (P-15, corrected corpus) | 25: 2 `Gigastructural Engineering`×`Vanilla`, 4 `ACOT`×`Vanilla`, 19 `ACOT`×`AoT`, 0 chains of 3+ | n/a — this row only exists post-re-vendor |
| Scripted-variable overwrites feeding a technology's cost/weight (P-15) | 4 (`acot_tier6cost2/7cost2/8cost2/9cost2` — Gigastructures' compat-fallback stubs, overwritten by ACOT's real definitions when ACOT is present) | n/a — this row only exists post-re-vendor |

Full pytest suite: **1,114 passed, 0 failed** (`pytest tests/`).

**Verification pass, run explicitly after the re-vendor** (not assumed from "the icon test suite
stayed green"): every figure above was recomputed against the refreshed corpus and compared
against the numbers recorded before the re-vendor (`tests/localisation/test_corpus.py::test_full_corpus_report`,
`tests/icons/test_icon_corpus.py`, a direct parse/glob over `common/technology`, and the
round-trip suite). Every moved figure has an identified, single-cause explanation (Gigastructures'
own content growing between the stale Workshop snapshot and the pinned `Live-Branch` commit) —
nothing moved for an unexplained reason, and nothing that should have been stable (parse failure
counts, malformed-entry counts, diagnostic counts, other three sources' figures, atlas byte
total) actually moved.

**Gigastructures vendored snapshot was corrected mid-session.** The original snapshot (Steam
Workshop download, hash `0b60eb7186bba531`) was stale relative to GitHub's `Live-Branch` — it was
missing a real overwrite (`tech_mega_engineering`, added to `zz_giga_tech_overwrites.txt`), which
the P-15 survey's first pass correctly reported as absent because it genuinely was absent from
that snapshot, not because of a scan defect. Re-vendored to commit
`0f1f2b024f43249dc7dfe132fe7c0e4201398ef5` (tag `v3.39.3`, `Live-Branch`, confirmed by the user to
match the Steam Workshop release in content relevant to this tool) — see `vendor/manifest.json`
and CLAUDE.md's "Source data" section for the full provenance and the still-open collector gap
(GitHub fetch + commit pin + scheduled CI for Gigastructures is specified but not yet
implemented; this snapshot was pinned manually). One new round-trip allowlist entry was added
for content only present in the refreshed snapshot
(`vendor/mods/gigastructures/common/scripted_triggers/giga_frameworld_triggers.txt:1045` — a
missing space before `=`, reviewed as adjacency-only per the usual bar) — full suite re-ran green
after the refresh.

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

- **`roundtrip_allowlist.json`, 434 entries.** Reviewed, closed, all adjacency-only. A maintained
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
  2. ~~**Atlas content scope.**~~ **Done** (later session): `pipeline/icons/build.py`'s
     `filter_result_to_rendered_scope` filters technology icon candidates to those whose owning
     technology is in P-16's 980-node rendered set, before decode/pack, wired through
     `build_atlases(..., rendered_keys=...)`. **Ascension-perk icons are deliberately NOT
     filtered** — checked against spec, not assumed: P-16's closure is a technology-node concept
     (which ACOT/AoT technologies get their own canvas node); an ascension perk is never a canvas
     node, only a gate badge (P-3), and "which perks does a rendered technology actually reference
     as a gate" is a different computation — P-3's gate-pattern-registry/gate-detection pass,
     which still isn't built (see below) — so there is no correct filter to apply to perks yet.
     **Real filtered figures**: technology atlas drops from 4 sheets / 8,387,616 bytes (unfiltered)
     to **2 sheets (1008×2016, 1008×1468) / 4,564,314 bytes** — resolved candidates 2103→1192,
     unresolved 19→4 (the other 15 unfiltered-unresolved candidates' owning technologies are
     outside the rendered set and no longer matter; do NOT guess at the surviving 4 —
     `config/icon_overrides.txt` stays human-decided by design). Combined with the unchanged
     262,676-byte perk sheet: **total atlas bytes ~4.83 MB (4,826,990), down from ~8.65 MB
     unfiltered — a 44% reduction.**
  3. **SETTLED: atlases are excluded from P-10's ≤2 MB budget** — same reasoning as before,
     unchanged. `MAX_TOTAL_ATLAS_BYTES` re-calibrated to the filtered figure this session: **6 MB**
     (was 12 MB), ~1.24x above the real ~4.83 MB total, and deliberately kept BELOW the ~8.65 MB
     unfiltered ceiling — unlike the old 12 MB setting, which sat above the unfiltered figure too
     and so could never have caught a regression that silently disabled filtering. This one can.
  4. **Documentation correction found while re-measuring**: the "8,650,292 bytes total" figure
     previously recorded against "Technology atlas sheets" in this file's corpus-counts table
     (below) was actually **technology + ascension-perk sheets summed together**
     (8,387,616 + 262,676 = 8,650,292, confirmed by direct recomputation) — the two rows in that
     table were correct individually (4 sheets / 1 sheet) but the byte figure was mislabeled as
     belonging to the technology row alone. Corrected in that table now.
- **`config/icon_overrides.txt`** is currently empty by design. Expect entries only after a
  *human* decides what's correct for each case — not a future agent session guessing.
- ~~**P-13's lock-reason override table** is a newly-identified hand-maintained config file, not
  yet created.~~ **Done**: `config/lock_reason_overrides.txt` + `pipeline/lock_reason_overrides.py`
  (loader) + `pipeline/availability.py`'s `needs_lock_reason_override`/
  `build_missing_lock_reason_overrides` (the warn-when-missing wiring). Seeded empty — the real
  corpus currently has zero LOCKED results needing an entry (verified, not assumed — see
  `tests/test_availability_corpus.py::test_no_locked_reasons_currently_need_a_lock_reason_override`).
- ~~**No trigger-condition → human-readable-text renderer exists yet.**~~ **Done**:
  `pipeline/trigger_text.py`, built as a shared component (not private to availability) so it also
  serves `detail-payload.schema.json`'s `weight.modifiers[].conditionText` via
  `describe_condition()`, not just the empire-overlay's lock `reason` string. `categorize_leaf()`
  additionally classifies undecidable leaves into a `ReasonCategory` — see CLAUDE.md's
  "Availability evaluator" section for the measured category distribution.

**Base dataset size — REAL, MEASURED (later session), not the estimate below.** Stage 2 dataset
emission is built (`pipeline/dataset_emit.py`) and the real base-dataset compressed transfer size
is **~64 KB (65,585 bytes)** against the ≤2 MB budget — ~31x headroom, comfortably more than the
projection below assumed, but for a reason worth recording rather than absorbing: the **real
measured compression ratio is 14.29x**, well above the 6-9x range the projection used (drawn from
the deploy-spike's 9.34x *synthetic* ratio, which itself carried an explicit caveat that real
content should compress *worse* than synthetic). The projection's method turns out to have been
wrong, not just imprecise — the deploy-spike's synthetic blob was dominated by free-text
name/description-shaped content, but the real base dataset's size is dominated by small,
highly-repetitive structured JSON (980 near-identical technology record shapes, 12-slot enum
arrays, mostly-empty arrays, frequent `null`s) that gzips far better than prose; real description
text isn't even in the base dataset, it's in the lazy detail payloads. **`spec/P-10-performance-automation.md` now records this formally** (Stage 2 cleanup session): size
is no longer a binding constraint on Stage 3's loading design at ~30x headroom, the lazy-artefact
split's justification is restated as responsiveness/memory/cache-granularity rather than "must fit
the budget," and the 14.29x-vs-6-9x compression divergence and its cause are recorded there too —
read that file, not just this paragraph, before making a Stage 3 loading-design decision that
assumes size is still scarce. See CLAUDE.md's "Stage 2 dataset emission is built" bullet for the
full writeup, including the other four artefacts' real sizes (never measured before this session)
and a real, non-arithmetic-coincidence finding this
build surfaced: `unconditionalUncertainty` moved from a stale 209/980 (21.33%, computed from
unexpanded blocks that silently skip 50 real `giga_tech_repeatable_*_cap` availability
conditions — the same bug class the tier-source audit already found for `tier`) to 259/980
(26.4%) once expansion was fixed, then — a later session, once those 50 were correctly
categorized as mod-configuration-gated rather than undecidable — back to **209/980 (21.33%)**,
the same number as the ORIGINAL figure by coincidence of arithmetic only. See CLAUDE.md's
"`giga_tech_repeatable_*_cap` correctly categorized — CONFIG_GATED" bullet for the full history
and why this is the correct, final figure, not a reversion.

**The two 209s are not a no-op, even though the number is identical — record this explicitly so a
future read doesn't conclude nothing changed.** Both exclude the same 50 `giga_tech_repeatable_*_cap`
nodes from `unconditionalUncertainty`, but for opposite reasons: the original 209 excludes them by
never seeing their `potential` block at all (a raw-block parsing defect, and they were wrongly
counted `AVAILABLE` as a result); the current 209 excludes them by evaluating them correctly and
finding they belong in a fourth state, `config-gated`, that didn't exist at the time of the
original figure. **The real change is visible in the AVAILABLE-state count, not this one**: those
50 moved from `AVAILABLE` to `CONFIG_GATED`, an **available-count delta of exactly -50**, confirmed
by `tests/test_dataset_emit.py::test_repeatable_cap_family_available_count_delta_is_exactly_minus_50`
(evaluating with no `potential` visible — the original defect's exact counterfactual — is
AVAILABLE for all 50; the real expanded evaluation is AVAILABLE for 0 of them). The D-10
unconditional-uncertainty ratchet, having gone 209 → 259 → 209 across two sessions, is back at its
original seed value — no regression, no ratchet action needed. Full table:
`spec/decisions.md`'s D-10 "The 209 -> 259 -> 209 sequence..." subsection.

**Config-gated display wording (P-13, a separate follow-up item in the same session)**: the
reason text for these 50 nodes is user-supplied, matching Gigastructures' own in-game option label
— `Requires <Megastructure Name> cap: 1 + Repeatables`. Stage 2 emits only the semantic subject
(the empire overlay's `availability[key].configGatedSubject`, sourced from the technology's own
resolved name) — Stage 3 composes the final sentence from the fixed template recorded in
`spec/P-13-empire-locking.md`.

**Corrected in a following session: real corpus is 50/50 resolved, not 42/50.** The original pass
found 8/50 (including the flagship `giga_tech_repeatable_alderson_cap` example) fell back to
`configGatedSubject: null` because the technology's own name embeds a `$...$` token, and assumed
that token was an unresolvable Stellaris runtime name-pool reference. **That assumption was never
verified against raw source and turned out to be wrong**: every one of those tokens is ordinary
Stellaris `$key$` loc-variable substitution, resolvable one hop away as its own plain loc key
(`name_alderson: "Alderson Disk"`) — two of the 8 (`dyson_swarm_3`, `orbital_arc_furnace_4`) are
vanilla megastructures Gigastructures extends, with the name defined in vanilla's own
localisation, which is why the fix (`pipeline/dataset_emit.py`'s `_resolve_loc_tokens`) resolves
against the full cross-source `ctx.loc_table`, not Gigastructures' loc files alone. All 50/50 now
resolve: `alderson` -> "Alderson Disk", `asteroid_manufactory` -> "Asteroid Industrial Site",
`dyson_swarm` -> "Dyson Swarm", `furnace` -> "Arc Furnace", `observatory` -> "Atmospheric Storm
Observatory", `orbital_naval_logistics` -> "Orbital Naval Logistics Office", `warmoon` -> "Attack
Moon", `warplanet` -> "Behemoth Planetcraft". `configGatedSubject` remains nullable and the
resolver still reports `None` rather than guessing when a technology has no loc entry or a token
chain exceeds the hop limit — no case in the current corpus hits either path. See CLAUDE.md's
"Config-gated reason wording" bullet for the full writeup and
`tests/test_dataset_emit.py::test_config_gated_subject_resolves_all_50_megastructure_names`.

**Original projection, kept for the record of what was assumed before a real build existed:**
~275–305 KB compressed against the ≤2 MB budget (~6–7x headroom), computed from **1,879** — the
canonical technology count (see "Canonical technology count" below; previously recorded as 1,878,
an uncorrected off-by-one from an earlier ad-hoc count whose exact method wasn't preserved — the
1-record difference doesn't move the KB range at any meaningful precision, but the count itself is
now the reviewed, traceable figure, not a stale one) — real localisation string-length samples
(name median 22 chars, description median 154/mean 180 — description itself stays out of the base
dataset), and the search index moved to its own lazy artefact. This projection has now been
superseded by a real measurement (above) — kept here only as the historical record of the
estimate, not as a figure to still trust.

**Canonical technology count: 1,879 — see CLAUDE.md's "Canonical technology count" section for
the full reconciliation.** Three counts were in circulation and used interchangeably before this
was pinned down: 1,878 (a stale, unrecoverable-provenance earlier count, now corrected), 1,879
(distinct technology keys after whole-key overwrite resolution — the correct figure for "how many
technologies exist as identities," and today's best available upper bound on final node count
pending P-16's rendering-scope closure), and 2,122 (icon *candidates* — 1,904 raw pre-resolution
technology-block occurrences across all 4 sources, plus 218 `technology_swap` sub-block
alternates; neither term belongs in a node-count estimate, since an overwritten-away occurrence
never becomes its own node and a swap alternate is per-profile display data on an existing node,
not a separate one).

---

## P-16 rendering-scope closure — measured by hand, since implemented as real code

**Update (Task 3 session): implemented as `pipeline/rendering_scope.py`.** The measurement below
was originally a one-off manual computation; it is now reproducible pipeline code
(`compute_rendering_scope`/`rendered_technology_keys`), verified against the exact figures below
in `tests/test_rendering_scope.py` (both synthetic mechanism tests and a real-corpus regression).
The rest of this section is kept as the original measurement record — the numbers didn't change,
only their provenance (hand-computed -> code-computed-and-tested).

CLAUDE.md's "Scope of ACOT and AoT" section specifies the rule (prerequisite-edge closure from a
rendered vanilla/Gigastructures technology); this is the first time it was actually computed.
Script: BFS over the canonical (post-P-15) `prerequisites` field only, seeded from every
Vanilla/Gigastructures technology's direct references into ACOT/AoT, then transitively expanded
through ACOT/AoT's own `prerequisites`.

**Trigger**: the user's real requirement is 4 specific ACOT/AoT technologies Gigastructures uses
as placeholders for its "supertensile" building alternates — `tech_dark_matter_power_core_dm`,
`tech_dark_matter_power_core_ae`, `tech_dark_matter_power_core_se`, `tech_civil_phanon_application`.
All 4 confirmed present, un-renamed: `dm` in `acot_01_delta_components_tech.txt:30`, `ae` in
`acot_02_alpha_components_tech.txt:9`, `se` in `acot_03_stellarite_components_tech.txt:693`, AoT's
`tech_civil_phanon_application` in `z_aot_phanon_building_tech.txt:1`. All 4 referenced only by
`vendor/mods/gigastructures/common/technology/giga_17_alternative_mega_build.txt` (lines 201, 225,
250, 276), each as a `prerequisites` entry for one of Gigastructures' 4 "supertensile" techs.

**Closure result**: **7 ACOT/AoT technologies total** (6 ACOT + 1 AoT), max depth 2.
- Direct references from Vanilla/Gigastructures: **exactly 4** — the four named above. No other
  vanilla or Gigastructures technology references any ACOT/AoT technology as a prerequisite,
  anywhere in the corpus.
- Transitive-only additions (3): `tech_mine_dark_energy` (ACOT), `tech_dark_matter_power_core_enig`
  (ACOT), `tech_precursor_design` (ACOT). All bottom into ordinary vanilla technologies
  (`tech_mine_dark_matter`, `tech_zero_point_power`, `tech_sensors_4`, …) already rendered
  unconditionally.
- `tech_dark_matter_power_core_se` has **zero** ACOT/AoT ancestors — no `prerequisites` field at
  all (gated purely through `potential`).
- Inclusion-rule comparison: (a) direct-only = 4, (b) depth≤1 = 4 / depth≤2 = 7 / depth≤3 = 7
  (closure exhausted at depth 2), (c) current unbounded closure (the spec'd rule) = 7.

**Conclusion: no rule change needed.** The closure was feared to be large (CLAUDE.md's own text:
"ACOT reaches T9+ with deep chains") but measures small and shallow for this reference set — the
unbounded closure (rule c, already spec'd) adds only 3 extra nodes beyond the 4 wanted, all
needed to avoid an invisible prerequisite-chain gap for `tech_dark_matter_power_core_ae`
specifically. Rule (a) (direct-only) would hit exactly 4 with zero extra but breaks CLAUDE.md's
own "never broken by an invisible gap" invariant — not recommended. **When P-16 is actually
implemented, use the existing unbounded-closure rule as spec'd; this measurement is the
confirmation, not a proposed change.**

**Rendered node total (Vanilla + Gigastructures + this 7-technology ACOT/AoT closure): 980.**
Canonical technology counts by winning source (post-P-15 resolution, all 1,879): Vanilla 673,
ACOT 742, Gigastructural Engineering 300, AoT 164. Rendered-by-source: Vanilla 673,
Gigastructural Engineering 300, ACOT 6, AoT 1 — i.e. 742-6=736 ACOT and 164-1=163 AoT canonical
technologies never render at all under this closure.

## D-10 availability projection — corrected figures and three review checks

**Correction to the previous survey turn's numbers**: 428/353/80 (previously reported) had a
methodology bug — trigger-construct classification was accumulated across *every* historical
occurrence of a technology key, including definitions a key's canonical winner overwrote away,
not just the winning (post-P-15) block. Recomputed against canonical winning blocks only. **The
numbers below (426/350/76 etc.) are the corrected, authoritative ones — supersede the previous
turn's figures wherever they were cited.**

**Baseline (1,879 canonical technologies)**: 437 (23.3%) have no `potential` block at all —
unconditionally available, confirmed not assumed. Of the remainder, applying the 2 design
decisions the survey recommended (assume default/off mod-config `has_global_flag`s; assume all
official DLC owned) plus a `not-fallen-empire` ground fact (none of the 12 profiles is a fallen
empire, so `is_fallen_empire`/`merg_is_fallen_empire` resolve to a constant `no`):

| Scenario | At-risk technologies | % of 1,879 |
|---|---:|---:|
| No design decisions applied (naive) | 1,235 | 65.73% |
| **With the 3 resolutions applied** | **426** | **22.67%** |

**CHECK 1 — profile-dependent vs. unconditional split** (of the 426 at-risk technologies):

| | Count | % of 1,879 |
|---|---:|---:|
| (a) Profile-dependent (an axis check coexists with the undecidable leaf — some profiles can short-circuit via `AND` to a definite `locked`) | 76 | **4.04%** |
| (b) Unconditional (no axis check anywhere — all 12 profiles resolve identically to `uncertain`) | 350 | **18.63%** |

(a) is above the 3% warn threshold, below the 10% hard ceiling. (a)'s 4.04% is an *upper bound
per profile* (counts "could vary," not "does vary for profile X") — the exact per-profile number
needed the real evaluator's short-circuit logic, since built (see "Ordered next steps" below).
**Adopted** (a later session's Task 1, now in `spec/decisions.md`'s D-10 and CLAUDE.md's "Trigger
evaluation" section): D-10's threshold applies to (a) only; (b) is tracked as a separate published
data-completeness figure, since a node reading identically under all 12 profiles never misleads a
user about their specific empire type — it's honestly reporting a fact outside the axis model, a
different quality signal than "the tool got your empire's availability wrong."

**CHECK 2 — `has_country_flag` breakdown (131 occurrences, 82 distinct names)**: unlike
`has_global_flag` (dominated by one resolvable "assume default mod settings" pattern), no single
resolvable pattern was found here. Two largest confirmed by direct evidence, not pattern-guess:
- `herculean_built` (27, all ACOT) — confirmed mid-game: `set_country_flag = herculean_built`
  fires from `vendor/mods/acot/events/acot_herculean_events.txt:1316`, a player-triggered event
  effect. Genuinely undecidable.
- `colossus_project` (16, all vanilla) — traced to `ap_colossus` ascension perk
  (`vendor/stellaris/common/ascension_perks/00_ascension_perks.txt:1076`), whose `on_enabled`
  fires `country_event = { id = apoc.100 }`. That event lives in `common/events/`, outside
  vanilla's vendored scope — **could not confirm** whether this is fully redundant with
  `has_ascension_perk = ap_colossus` (plausible but unverified). Left classified undecidable.
- Remaining 80 distinct names (88 occurrences): read as crisis-chain/story-progression flags by
  name pattern (`blokkat_*_possible` ×20, `ehof_code_2..7_complete` ×6,
  `encountered_first_lgate`, `completed_lcluster_chain`, `synth_queen_knowledge`,
  `cosmogenesis_aborted`, `starfire_cannon_unlocked`, etc.), consistent with the 2 confirmed
  examples' pattern but individually unverified (82 names, mostly singleton occurrences).
- **Net effect: none of the 131 occurrences move out of the undecidable bucket.** The 426/350/76
  figures above already reflect this — no further reduction available here.

**CHECK 3 — rate over the 980 rendered nodes (Part 1's closure), by source:**

| Source | Rendered | At-risk | At-risk % | Unconditional (no axis) |
|---|---:|---:|---:|---:|
| Vanilla | 673 | 144 | 21.40% | 103 |
| Gigastructural Engineering | 300 | 117 | **39.00%** | 106 |
| ACOT | 6 | 2 | 33.33% | 2 |
| AoT | 1 | 0 | 0.00% | 0 |
| **Total** | **980** | **263** | **26.84%** | **211** |

**This inverts the "restrict ACOT/AoT scope to fix the rate" premise.** The rendered-only rate
(26.84%) is *higher* than the all-1,879-canonical rate (22.67%) — the ~1,780 non-rendered
ACOT/AoT technologies excluded by the closure have a *lower* undecidable-leaf rate than what's
kept. **Gigastructures' own content is the concentration point** (39.00% at-risk, its own
crisis-faction/endgame-chain story-progression flags — the same pattern found in Check 2), not
vendored-but-unrendered ACOT/AoT bulk content. Narrowing ACOT/AoT rendering scope per the P-16
section above does not address the ceiling breach; the two problems are orthogonal.

**This section's numbers predate the real evaluator and the (a)/(b) split's adoption — kept as the
original projection record, not the current authoritative figures.** See CLAUDE.md's "Availability
evaluator" section for the real, evaluator-measured rates over the exact 980-rendered-node closure
— **3.37% worst-case profile-dependent, 21.33% unconditional (209/980), final figures after two
corrections that happened to cancel numerically** (209 → 259 → 209; see CLAUDE.md's "`giga_tech_
repeatable_*_cap` correctly categorized — CONFIG_GATED" bullet for the full history and why 209
is the genuinely correct final answer, not the original uncorrected one). The category
distribution behind the unconditional figure is likewise back to its original table, for the
same reason. The (a)/(b) split was adopted, not left as an open proposal, and the ceiling was not
breached once the real short-circuit logic replaced this section's upper-bound projection.

---

## Layout model — settled from v1 evidence (D-13)

**v1's actual failure, diagnosed from a screenshot.** The user reported that v1's visual design
was close to right, but two things were wrong behaviourally: **incorrect tier placement** (worst
in tier 6, and "likely not the only one") and **inadequate labelling of locks and
prerequisites**.

**IMPORTANT correction to the second failure's diagnosis (later session, from the user
directly).** For many sessions this document read "inadequate labelling of locks and
prerequisites" as a *card text* problem — truncated gate strings, missing badges — and
`spec/P-02-layout.md` still carries design constraints derived from that reading. **That reading
was wrong.** Shown his own v1 screenshots and asked directly, the user's answer was:

> "the issue isn't the gate or tech names being cut off, while it isn't ideal, players will know
> what they're looking for, and in the event of them being confused, they can select the tech for
> more info"

**Truncated card text is acceptable.** The real second failure is the **research path** — see the
"Research path" section below. Do not spend design effort making card text untruncatable; that
constraint was inferred, never reported. The popup is the escape hatch for full text and the user
considers it sufficient.

The screenshot diagnoses the first precisely: the band headed **TIER 6 contained cards almost
all badged T5**. v1 was assigning nodes to bands by *computed column* (post-promotion position)
while badging them with *declared tier*. A T5 technology promoted to column 6 landed under a
"TIER 6" header. Tier 6 was the worst offender because it is the first band that exists almost
entirely from promotion rather than declaration — vanilla and Gigastructures barely declare T6+
at all.

**This is why D-13 matters and is not a cosmetic preference.** Bands are declared tier. The mod
does not define tiers beyond vanilla (only ACOT and friends do); most Gigastructures technologies
are declared T5, and the community expresses progression depth through **ascension-perk gates**
("Galactic Wonders tier", "Gigastructural Constructs tier"), not through tier numbers. Players
saying "tier" mean the declared vanilla tier. So: **tier organises, gates annotate.** The computed
column number appears nowhere in the game, the mod, or player vocabulary and must never be
surfaced.

A design direction that made gates the *band-organising* axis was proposed in chat and
**rejected** on the user's evidence — do not revive it. Gates are a prominent card element, not a
layout axis.

### Measured layout facts

- **Tier source audit** (v1's placement bug class): 930/980 take tier from a literal on the raw
  block; **50/980 only have a tier after `inline_script` expansion** (`giga_mega_repeatable.txt`'s
  template, all `giga_tech_repeatable_*_cap`) — a pipeline reading raw blocks places these with
  no tier at all. 0/980 unresolvable after expansion. **Policy: hard build failure on a missing
  tier, never a silent default.** 83/980 declare tier as an `@variable` (4 distinct, all resolve,
  none currently overwritten cross-source) — **known blind spot:
  `pipeline.overwrites.resolve_variable_overwrites` checks cost/weight for cross-source variable
  overwrites but NOT tier.** Zero impact today, must close before Stage 2's real build. 2/980 have
  declared tier changed by a P-15 block overwrite (`tech_adaptive_combat_algorithms`,
  `tech_biomechanics`, Vanilla→ACOT), already handled correctly.
- **Backwards edges**: 27 of 891 non-repeatable prerequisite edges (3.0%) point from a later
  declared-tier band to an earlier one — 24 by one band, 3 by two, max 2. Worst cases:
  `tech_antimatter_power`(T3)→`tech_reactor_boosters_3`(T1);
  `tech_mega_engineering`(T5)→`giga_tech_penrose_sphere_1`(T3);
  `tech_stingers`(T4)→`tech_swarmer_missiles_1`(T2). Small and short-range; P-8 updated to route
  them explicitly in a gutter rather than assume forward-only. The old
  `column(B) > column(A)` invariant is **false under D-13 and has been removed from the spec.**
  **Correction (later session)**: the 891 denominator used a repeatable-membership rule
  (`levels < 0` only) that undercounted repeatable technologies by 12 — see the correction note
  below. Corrected denominator is **881**. The 27 backward edges are the same 27 by key either
  way; only the denominator moved.
  **Correction (P-14 edge-typing session)**: this was always `prerequisite`-only figure, and 2 of
  the 27 (`tech_stingers`→`tech_swarmer_missiles_1` at T4→T2, plus one other) turn out to be
  `alternative` edges (OR-branch members), not `prerequisite` — they were flattened into the same
  list by the pre-fix `ordered_prerequisites()`. The real, final decomposition, over the full
  three-kind P-14 edge set: **34 backward = 25 `prerequisite` + 2 `alternative` + 7
  `potential-gate`** (`potential-gate` wasn't extracted as an edge kind at all before this
  session). `potential-gate`'s 7 backward edges reach up to **5 bands back**
  (`tech_cosmogenesis_escort`(T5)→`tech_missiles_1`(T0)) — well outside the "1-2 bands back" this
  bullet describes for `prerequisite`/`alternative`; see CLAUDE.md's P-14 bullet and
  `spec/P-08-connectors.md` for the full breakdown and the deliberately-deferred `TODO(Stage 3)`
  routing decision. Record this figure as a per-kind decomposition from now on — it has moved
  three times purely through re-scoping.
- **Density** (declared-tier denominator, the relevant one again): Standard × T5 = **261**, the
  layout-forcing cell. Broad midsection, not one anomaly. Category is the natural sub-grid wrap
  key — T5's 261 split 13 ways (voidcraft 49, particles 39, field_manipulation 30, biology 26,
  computing 25 … archaeostudies 1), and there are **zero multi-category nodes**.
  **Correction (later session)**: recomputed at **253** under the corrected repeatable-membership
  rule (8 of the 12 newly-recognised finite-level repeatables were Standard-lane, declared-T5
  nodes that moved into the Repeatables band) — see below.
- **Repeatable membership, corrected (later session, not part of the original hand survey)**: the
  original layout implementation's `is_repeatable` tested `levels < 0` only (76/980 nodes). Found
  wrong against a user's v1 screenshot: the corpus also uses `levels` as a positive **finite** cap
  (5, 20, or 40) on an otherwise identical repeatable-tech shape (`cost_per_level` field,
  `*_repeatable*.txt` source files) — 12 more nodes, for a corrected total of **88**. The
  screenshot's "T5 x5" card is `tech_repeatable_reduced_building_cost` ("Gravitational Analysis"),
  exactly one of the 12. Corrected membership is deliberately distinct from the 50
  `giga_tech_repeatable_*_cap` inline_script-tier-only nodes above — every `_cap` node is
  repeatable (a proper subset of the 88), but 38 of the 88 never went through inline_script tier
  expansion at all; conflating the two is a separate bug from either finding alone. Sink property
  re-verified over the corrected set: 881 non-repeatable-to-non-repeatable edges + 83
  non-repeatable→repeatable edges = 964 total, 0 edges run the other two directions. See CLAUDE.md's
  "Repeatables" section and `spec/decisions.md`'s D-13 for the full writeup, including why the
  5 non-T5 repeatables (mostly Blokkat-scrap/L-Cluster/Cosmogenesis crisis-chain nodes) are
  evidence *for* the repeat-count badge, not just a stray fact.
- **N-card-wide bands**: settled in principle (v1 clearly did this). Recommended **N = 3–4**. At
  270px cards: N=3 → 9,486 × 10,900px; N=4 → 12,544 × 8,350px. Canvas size itself is *not* the
  constraint — 980 nodes/964 edges is small for WebGL, S-3's LOD thresholds are zoom percentages
  not absolute pixels, and no dimension approaches float32 precision limits. What bites at N=1 is
  **wayfinding**: 161+ single-file stacked cards give a panning user nothing to chunk against.
  Any N≥2 fixes that; category grouping fixes it properly.
- **Card dimensions** (proposed, not yet locked in spec): **270×92px**. Name lengths over the 980
  rendered nodes: p50=21, p90=35, p95=39, p99=46, **max=54** ("Blokkilian Equations - Planckscale
  Particle Generation"; the `giga_tech_repeatable_*_cap` → "… Management Protocols" convention
  sits at 43–53). 17% of names carry `§` markup. Designed to p95 with ellipsis truncation, full
  name in popup and hover title — though 270px in practice fits even the 54-char max across two
  lines. ~~**Gate text is never truncated** — that was v1's literal reported failure.~~
  **CORRECTED (later session, from the user directly): this premise was false.** Gate text
  truncation was never the reported failure — see the correction note at the top of this section.
  The user explicitly accepts truncated gate and name text on the card, with the popup as the
  escape hatch. The 270×92px dimension and the p95 design target still stand on their own
  measurement merits; only the "never truncate gate text" *rationale* was wrong. Dropping the
  "Needs " prefix (the icon already carries the semantic per P-3) cuts the worst gate string from
  41 to 35 chars, which is still worth doing — but as a legibility improvement, not to satisfy a
  hard constraint that does not exist.
- **Gate population**: 46/980 nodes (4.7%) carry ≥1 gate, 9 carry 2 (max observed) — covered by
  P-3's existing primary+secondary rule, no design gap. Only 28 possible gate strings exist
  total, shared across many nodes — a small bounded set, unlike per-node names.
- **Reason-category surfacing**: same inline treatment as gates, not a corner badge — e.g.
  "Locked: Nomadic empires", "Uncertain: Blokkat crisis progress", falling back to "Uncertain:
  reason unknown". Full raw trigger text, category and 12-profile matrix in the popup. This
  directly targets v1's second reported failure: uncertain/locked states reading as missing data
  rather than as information.

---

## Research path — v1's real second failure, diagnosed from a screenshot (spec: P-12.9)

This is the other half of what the user reported about v1, and it is **not** a card-labelling
problem (see the correction at the top of the Layout model section). It is a correctness problem
in the research path, diagnosed from a v1 screenshot of the path to `tech_mega_engineering` —
a flat numbered list of steps with a running cost total, ending at Σ 74,750.

**What was wrong with it**, per the user, all four the same root cause — the path was computed
once, profile-blind, with OR branches flattened to inline annotations rather than traversed:

- "*or Arkship Mastery*" named an alternative but never expanded **its own prerequisites** — the
  path was incomplete for anyone who would actually take that branch.
- "*or Stingers*" was shown as optional when for a **bio-shipset** empire it is the only route
  (Maulers → Stingers), and belonged in the path proper.
- **Starbase techs were included for every empire**, though a **nomadic** empire does not need
  them.
- Consequently **the Σ total was wrong for most of the 12 profiles** — 74,750 is the
  regular-shipset non-nomadic figure presented as if universal. This is the worst of the four: a
  cost total reads as authoritative in a way an inline annotation does not.

**The data to fix this now exists and did not when v1 was built** — P-14 separated `alternative`
edges from true `prerequisite`s with group IDs, the empire overlay carries per-profile
availability across all 12 profiles, and D-14 added per-profile swap name substitution. The P-14
edge-typing work turned out to be the prerequisite for fixing this, not just a data-model tidy-up.

**Design decisions, all settled with the user in chat and written into
`spec/P-12.9-research-path.md`** (spec only — nothing is implemented):

- **Per selected profile.** Technologies not on that profile's route simply do not appear. This is
  correctness, not filtering. The user considered "show multiple paths, one per empire type" and
  rejected it once it was clear per-profile computation makes it unnecessary.
- **Shape stays as v1 had it** — one flat ordered list with a running cost total. Explicitly
  confirmed by the user; do not redesign it into a graph overlay without asking.
- **OR-branch selection: cheapest total cost**, including that branch's own prerequisite chain,
  with the alternative noted at that step. **Measured 0/72 disagreement with fewest-steps on the
  real corpus** — the rule is currently a distinction without a difference and is explicitly
  revisitable.
- **Uncertain steps stay in the path; the total is marked an estimate** (a lower bound). Excluding
  them understates cost; presenting an exact number over an unknown is a false claim. Worst
  profile is 182/980 paths carrying ≥1 uncertain step, so this must read as an ordinary annotated
  state, not an error.
- **Config-gated steps are excluded from the total and explained separately.** Structurally
  confirmed: config-gated technologies are sinks, so a config-gated step can only ever be the path
  **target**, never mid-path — no path total is ever mixed.
- **Triggered by selecting a technology**, as in v1. Pinning a goal technology for always-on
  display is a **deferred QOL feature**, explicitly out of scope for the first renderer. The
  user's framing: "main focus is getting the tree working, extra QOL features come after."

**The design was validated against the user's own bug report before being accepted**, which is
the strongest evidence in the project that it is right: recomputing `tech_mega_engineering`'s path
for regular/mechanical/non-nomadic reproduces **74,750 exactly** — v1's own reported figure — while
nomadic correctly routes through Arkship Mastery (**99,750**, a *higher* number, not a flattering
one) and bio-shipset correctly routes through Stingers (**73,750**) with Battleships excluded as
locked rather than shown as a false option.

---

## Ordered next steps

The dataset schema (`schema/`) is done — see "What's built" above. Stage 2 now has a contract to
emit into.

1. ~~**Overwrite resolution (P-15).**~~ **Done.** `pipeline/overwrites.py` +
   `pipeline/overwrite_overrides.py` — see "What's built" below for the full description. Not
   plain last-definition-wins alone: the resolution rule was corrected mid-implementation after
   a survey miss surfaced (see "Vendor-backed corpus counts" below) — Gigastructures' vendored
   snapshot was stale relative to its own GitHub `Live-Branch`, missing a real overwrite
   (`tech_mega_engineering`) the survey's first pass correctly reported as absent from the (then
   stale) corpus. The corpus was re-vendored to the pinned commit before resolution was built, so
   the counts and behaviour below reflect the corrected corpus, not the original survey's numbers.
   **This ordering was checked, not just carried over** — see the analysis below.

**Sequencing check: P-15 vs. localisation, verified with evidence.** `pipeline.localisation` is
already Stage-1-complete and has zero remaining work — it isn't actually competing with P-15 for
"next task," so the real question was whether P-15 has a hidden dependency on it, or vice versa.
Checked both directions: (1) P-15's own outputs — the `SourceMod`-based `definedBy`/`overwrites`/
`label` shape (P-12.5) and the field-level diff list (cost/tier/prerequisites/weight/category/
flags, `schema/detail-payload.schema.json`'s `overwriteDiff`) — are fixed enums and internal
field names, never localised text; P-15 needs no resolved localisation table to do its work.
(2) `pipeline/localisation/table.py`'s own docstring states the independence directly ("*never
merged with... P-15's technology-overwrite table*") — its last-wins resolution runs entirely
over the loc corpus, keyed by loc key string, with no reference anywhere to which source wins a
technology-block overwrite. Neither blocks the other. What *does* make P-15 come first is
`spec/00-overview.md`'s own Stage 2 ordering — "Resolve overwrites... Build the DAG... Evaluate
triggers... Assign tiers... Route edges... Emit the dataset" — every one of those needs the
canonical (post-overwrite) technology record first, including "attach a localised name to it."
P-15 is the one genuine blocker on the critical path; localisation is a leaf, consumed only at
final dataset-emission time, zero schedule risk. The current ordering is correct for the right
reason, not by default.
2. ~~**Partial trigger evaluator (D-10).**~~ **Done, including the P-13 reason-text/category
   layer.** `pipeline/availability.py` — see CLAUDE.md's "Availability evaluator" bullet under
   "What's built" for the full description. D-10 was split into two metrics (profile-dependent,
   ceiling-governed; unconditional, ceiling-exempt) — see `spec/decisions.md`'s D-10. **Real
   measured rates, over the EXACT 980-rendered-node P-16 closure** (`pipeline/rendering_scope.py`,
   built alongside — see point 3 below): 3.37% worst-case profile-dependent (below the 5.3%
   projected upper bound; confirmed to actually cross the 3% warn threshold, not just look close
   to it), **21.33% unconditional (209/980)**. Neither breaches the 10% ceiling. This figure moved
   twice across later sessions (209 → 259 → 209): first a real measurement bug (raw, unexpanded
   technology blocks in `tests/test_availability_corpus.py`'s fixture silently missed the real
   `potential`-gating condition on all 50 `giga_tech_repeatable_*_cap` technologies, undercounting
   at 209; fixed, giving 259), then a real classification gap (those 50, once visible, were being
   counted as `uncertain` when their `potential` actually resolves DEFINITIVELY to unavailable for
   a mod-configuration reason -- introduced as `config-gated`, a fourth `AvailabilityState`
   distinct from `locked`/`uncertain`/`available`; fixed, giving 209 again). **209 is the final,
   correct figure -- the same number as the original by coincidence of arithmetic, not because
   nothing needed fixing.** See CLAUDE.md's "`giga_tech_repeatable_*_cap` correctly categorized —
   CONFIG_GATED" bullet for the full writeup, including why the fix generalises to any
   mod-config-toggle-caused unavailability (verified to affect only these 50 on the real corpus).
   `pipeline/trigger_text.py` is the shared trigger-condition -> text/category renderer this
   section previously flagged as missing — `describe_condition()` (also usable for P-12.8) and
   `categorize_leaf()` (a corpus-derived `ReasonCategory` taxonomy: crisis/story-chain, origin,
   ethics/civic, mod-content, mod-configuration, opaque country state, unclassified — the
   `mod_configuration` category added alongside `config-gated`). **Category distribution over the
   final, corrected 209 unconditional-uncertain nodes is exactly the original table**: ~80%
   explainable (crisis/story 42.6%, origin 19.6%, ethics/civic 16.3%, mod-content 1.9%), ~20%
   opaque/unclassified (16.3% + 3.3%) — read as primarily a presentation problem Stage 3 can
   mostly solve with honest, category-specific reason text.
   `pipeline/lock_reason_overrides.py` + `config/lock_reason_overrides.txt` implement P-13's
   override table (seeded empty — zero real-corpus LOCKED results currently fall back to
   unphrased text). Still open, not done here: general scripted-trigger call inlining (the single
   biggest lever still left on the unconditional figure — `has_gigastructural_constructs` and
   similar custom triggers are individually special-cased, not generically resolved), and
   `has_country_flag` resolution beyond the name-pattern heuristic behind the crisis/story split
   (individually unverified per flag, same caveat the original survey carried). These unblock
   gate detection (P-3's pattern-matching layer, distinct from the universal `potential-gate` edge
   extraction) and both `TODO(Stage 2)` items in `pipeline/icons/resolve.py`.
3. ~~**P-16 ancestor closure.**~~ **Done** as real code, not just measured by hand:
   `pipeline/rendering_scope.py` (BFS over P-15-resolved `prerequisites`), verified against this
   file's earlier hand-computed measurement (7 ACOT/AoT technologies, 980 rendered nodes total) —
   see `tests/test_rendering_scope.py`. Closure stays `prerequisite`-only, decided on evidence in
   a later session (see point 4a below), not left as a placeholder.
4. ~~**Tier/column/edge computation.**~~ **Done, per D-13's corrected model** (`spec/decisions.md`
   — bands are declared tier, not computed position; see CLAUDE.md's "P-2/D-13 layout is built"
   bullet for the full description). `pipeline/layout.py` + `pipeline/geometry.py`. Real numbers
   over the 980-node rendered set: canvas 12,544×8,146px (corrected from an initially-reported
   8,350px — see the repeatable-membership correction below), densest band cell Standard×T5=253
   nodes (corrected from 261). Edge routing is a first-pass orthogonal H-V-H router with a
   deterministic channel offset, not a full crossing-minimising/obstacle-avoiding one — that
   refinement is still open, tracked in `spec/P-02-layout.md` rather than silently assumed done.
4a. ~~**P-14 full edge typing (DAG build).**~~ **Done** (later session): `pipeline/edges.py` — the
   last structural gap in Stage 2 before dataset emission. Layout previously built `prerequisite`
   edges only; all three P-14 kinds (`prerequisite`, `alternative`, `potential-gate`) are real now
   — see CLAUDE.md's "P-14 full edge typing is built" bullet for the full description (extraction
   mechanism per kind, the two standing diagnostics, the count_country self-loop regression guard,
   the P-16 `prerequisite`-only decision and its `compute_alternative_only_gaps` tripwire
   mitigation, and why edge-kind membership isn't mutually exclusive per pair). **Final real
   figures**: 989 total edges = 888 prerequisite + 76 alternative + 25 potential-gate; 34 backward
   = 25 + 2 + 7 (was reported 27/964 `prerequisite`-only before this session — see the "Backwards
   edges" correction note above for the full reconciliation). `schema/common.schema.json`'s `Edge`
   gained `groupId` and `bandSpan`; TS types regenerated; the icon atlas's real content scope
   still depends on P-16's closure the same way it always did (unaffected by this work — the
   closure itself didn't change, only the edges built alongside it).
   **Repeatable-band correction (later session)**: `pipeline.layout.is_repeatable` widened from
   "`levels < 0`" to "`levels` field present at all" — found by checking a user's v1 screenshot
   (a card badged "T5 x5") against the corpus, not by any test. See "Measured layout facts"'
   correction note below and CLAUDE.md's "Repeatables" section for the full finding and the
   corrected 88-node membership, the 881/83/964 edge-count reconciliation, and the schema change
   (`repeatable` is now `null | {levels}` rather than an always-present object) this drove.
4b. ~~**Dataset emission**~~ (assembling every Stage 2 component into the actual
   `base-dataset.schema.json`-shaped JSON + side-files, plus the other four artefacts). **Done**
   (later session): `pipeline/dataset_emit.py` — see CLAUDE.md's "Stage 2 dataset emission is
   built" bullet for the full writeup. All five artefacts build and schema-validate against the
   real corpus (`tests/test_dataset_emit.py`): 980 technologies, 989 edges, 12 empire overlays, 980
   detail payloads, the search index, diagnostics. Real base-dataset compressed transfer: **~64 KB**
   against the 2 MB budget (see the "Base dataset size" section above for the full reconciliation
   against the ~275-305 KB projection, including why the projection's *method*, not just its
   number, turned out to be wrong). A real bug surfaced along the way, not introduced by this work
   (later corrected again, in a following session, to a different final answer — 209/980, via a
   new `config-gated` state, not a reversion to the original bug): see the "Availability
   evaluator" correction in CLAUDE.md. Also closed in the same session: icon-atlas
   P-16 filtering (`pipeline/icons/build.py`'s `filter_result_to_rendered_scope`, technology atlas
   ~8.65 MB unfiltered → ~4.83 MB filtered including the unchanged perk sheet;
   `MAX_TOTAL_ATLAS_BYTES` re-calibrated 12 MB → 6 MB) — see "Vendor-backed corpus counts" above.
   Known v1 scope limitations (all schema-valid, none fabricated): `appliesToEmpireTypes`
   unconstrained on every edge, `gates` always `[]`, `repositoryLink`
   wiki URLs unvalidated — see the module's own docstring for the full list and why each is
   deferred rather than guessed at. ~~`swapMappings` always `[]`~~ **Closed in a later session —
   see CLAUDE.md's "D-14: `technology_swap` per-profile name/icon substitution is built" bullet**:
   real corpus is 214 swaps across 185/980 rendered technologies, 128 axis-expressible (substitute
   per profile via `swapMappings`) / 86 non-axis (listed as popup-only `variants` in the detail
   payload, never substituted — origin/civic/species-trait/ascension-perk/galaxy-situation
   conditions the 3-axis model can't express). **`cost`/`repeatable.costPerLevel` added next session** (they
   didn't exist in the base dataset at all before — `cost` wasn't in the schema despite
   `00-overview.md`'s glossary naming "research cost" as a card field): see CLAUDE.md's "Small
   targeted correctness pass" bullet for the real figures (15/980 rendered nodes have an
   unresolvable `cost`, 88/88 repeatables resolve `costPerLevel`) and `spec/P-02-layout.md`'s
   "Cost display" section for the primary/secondary display decision.
5. **Stage 3 (Render)** — real rendering, six passes in
   (`client/src/main.ts`/`camera.ts`/`lod.ts`/`tokens.ts`): slice 1 (static render), slice 2
   (camera + a first 3-tier LOD), slice 3 (edges), slice 4 (row rendering, D-16's re-axis), a
   **visual-fidelity pass** that fixed four appearance defects the user found reviewing slice 4's
   screenshots, and now a **second visual-fidelity pass** that fixed five more. See CLAUDE.md's
   "Stage 3 visual-fidelity pass" and "Stage 3 visual-fidelity pass 2" bullets for the full
   writeups. Pass 1 summary: the viewport-pinned sticky headers slice 4 built are REMOVED entirely
   (the user rejected them outright) and replaced with world-anchored row header chips plus a
   v1-style tier-band label repeated above every row's own populated band cell — this superseded
   S-03's "renders once across the full lane stack" criterion for a SECOND time (the first was
   D-16's lane→row rename), both supersessions now recorded explicitly in `spec/S-03-tier-
   differentiation.md` itself; every one of the 18 rows (not just the 5 faction rows) now gets a
   real tinted-panel/border/rounded-corner treatment, so category rows read as labelled containers
   instead of empty space; the faction row-backing patterns are rescaled for row (not card) scale,
   with a real unbounded-line bug found and fixed along the way (a faction row's diagonal pattern
   was bleeding across the entire canvas height, striping category rows too) and Sirenalia's
   pattern changed from flat rects to real curved "sweeping bands" via PixiJS's `quadraticCurveTo`;
   card name text is now hard-clamped to 2 lines with an ellipsis (matching the card's own original
   p95-name sizing intent), verified numerically over all 980 nodes that no name's bounding box
   exceeds its card. **Pass 2 summary**: card/band spacing widened again (real rebuilt canvas
   13,632×11,608px, up from 12,888×10,800px); tier bands now get an alternating background tint;
   edges get rounded corners (closing `spec/P-08-connectors.md`'s previously-skipped requirement)
   and a brighter light blue-cyan trace colour; the row-chip/per-cell-tier-label overlap Pass 1
   introduced is fixed (verified numerically, 0 violations across all 18 rows); the five faction
   row patterns are now real user-supplied artwork (Katzenartig's flagged provisional), which also
   surfaced and fixed two real bugs — the row panel was reading the chip's flag-identity colour
   instead of its own row-backing tone, and the pattern accent's clipping mask was never a
   scene-graph child so it silently clipped every faction pattern to nothing regardless of zoom.
   Still real gaps, next slice's scope: rare/dangerous/repeatable/gate/mod-requirement badges, the
   rare/dangerous outline override, hover/click/selection/popup, search, empire-profile switching,
   plus two still-open art items (real traced Blokkats flag SVG, a signed-off Sirenalia contrast
   colour). See CLAUDE.md's Stage 3 bullets for exactly what does and doesn't exist.
   `spec/P-12.9-research-path.md` is spec-only too — a design for one popup field, not yet
   implemented either.

---

## Next prompt to paste into Claude Code

**Most recent session ("commit + close the loop" follow-up): committed the previously-staged
has_ancrel/scripted-trigger-expansion/gate-extension work (Item 0, five logical commits); pinned
the corpus-wide uncertain count as a structural test invariant, proven capable of failing
(Item 1); resolved the crisis/story-progression flag naming pattern as a class, same treatment as
the user-approved `colossus_project` precedent — 73 technologies move unconditionally uncertain →
available, unconditional 107 → 34/973, union uncertain 127 → 54/973, worst profile-dependent rate
UNCHANGED at 1.54% (Item 2); confirmed `founder_species`/`has_authority` are already fully closed
by an earlier session's ethics/civic/origin gate work, no code change needed (Item 3); investigated
and reported (not applied) the `@giga_amb_flag` config-toggle candidate, pending user confirmation
of its default state (Item 4); catalogued the remaining 54-technology residue by classification,
with a domain question flagged for the user (`is_country_type = acot_phanon_base` on
`tech_dark_matter_power_core_se`) (Item 5). **Both flagged questions were answered by the user in
the same session, as a follow-up**: `acot_phanon_base` is confirmed AI/event-only, and the
technology IS reachable by a player who has progressed far into ACOT (not a permanent-
impossibility case) — `pipeline.availability.COUNTRY_TYPE_NEVER_PLAYER` now resolves that leaf as
a ground fact, correcting the technology's UNCERTAIN reason to the real one
(`has_country_flag = stellarite_tech_enable`, still genuinely unresolved). `giga_buildcap_j` was
DELIBERATELY left unresolved (not applied) — the user confirmed the reference-balance preset has
it ON by default but real players mostly change it and Gigastructures' own default may drift,
the opposite evidence shape from the already-approved `_capped_r` toggle; resolving to either
constant would misrepresent genuinely unstable state. See `docs/BUILD-LOG.md`'s "commit + close
the loop" section for the full writeup, real numbers, and the residue table. **Open follow-ups
from this session, not yet resolved:** `giga_rings_beh`/`_gar`/`_tit` (5 technologies, already on
CLAUDE.md's older unconfirmed candidate list) still need per-flag user confirmation; a scoped
evaluator-thoroughness relaxation for `if = { limit = {...} }` blocks (4 technologies) the user
already pre-approved in
principle but this session didn't implement; `exists`/`has_dna`/`always` leaf constructs not yet
individually surveyed.

**Stale as of an earlier session — kept for history.** Current as of the session that: built the
`?dev` uncertainty health monitor (Item 1); resolved four classes of
user-confirmed uncertainty (Item 2a-d — DLC/mod-presence/progression-flag resolution rules plus
the `always = no` exclusion, 977 → 973 rendered nodes); surveyed (not implemented)
ascension-perk `add_research_option` grants (Item 3); fixed gate-label collisions and enlarged
the gate icon (Item 4); stopped the ACOT/AoT tensile technologies from showing a redundant
prerequisite as gate text (Item 5); rebalanced sub-grid centring to fix top-heavy row padding
(Item 6); and clarified (without changing) hover-vs-selection scope (Item 7). All of Items 1-6 are
implemented, tested, and headless-verified; Item 3 and Item 7 are surveys only, per instruction.
See `docs/BUILD-LOG.md` for the full session writeup (real numbers, screenshots, every reasoning
step) and the immediately-prior session's writeup for the `activeEdgeIds`/tech-swap/prerequisite-
popup-list work this one built on top of.

**Next prompt should point at the research path (P-12.9) implementation.** The design was surveyed
against the real corpus in a still-earlier session and **approved by the user** — do not
re-litigate the design (per-profile, cheapest-total-cost `OR`-branch resolution, `uncertain`-
stays-in-estimate with the total marked an ESTIMATE, config-gated-target-only, unavailable-as-
one-state) — but three of the spec's own recorded validation figures are now stale against how far
the corpus has moved since they were measured, and **correcting them is part of the same
implementation pass, not a separate follow-up**:
- The "2 of 980 impossible" headline count is now **203 technologies / 1,270 (key, profile)
  pairs** — real, expected content growth (many more technologies are directly axis-gated than
  when this was last measured), not a bug. Re-verify the "dangerous" sub-case the spec's entire
  `status: "unavailable"` simplification rests on — an ancestor chain broken while the target
  itself stays `available`/`uncertain` — is still exactly zero before trusting the simplification;
  it was as of this session's survey, but re-check against whatever corpus state exists when you
  implement, don't assume it's still true.
- `tech_mega_engineering`'s nomadic total is now **76,250** (was 99,750 in the spec) — the
  regular/mechanical (**74,750**) and regular/biological (**73,750**) totals still reproduce
  exactly, so this is a real, narrow content-length change in the Arkship Mastery chain
  specifically, not an algorithm problem.
- The `OR`-group tie-break's "0 disagreements between cheapest-total-cost and fewest-steps" is now
  **12 disagreements** (out of 72 genuine 2+-viable-candidate choices, unchanged count) — cheapest-
  total-cost is genuinely load-bearing now, not a distinction without a difference the way the spec
  currently frames it.

Re-run the survey's own reproduction script (or equivalent) against whatever corpus state exists
at implementation time before trusting these three numbers verbatim — they were measured once,
this session, and the corpus does keep moving.

**Also still open, not part of the P-12.9 work but real and scoped:**
- ~~Item 3's `add_research_option` finding...~~ **DONE, a later session ("Ring Segment /
  ascension-perk locking / gate-propagation" session, Item 4a)**: `tech_ring_world`/
  `tech_dyson_sphere`/`tech_matter_decompressor` now carry a real `ap_galactic_wonders` gate via
  `pipeline.dataset_emit.ADD_RESEARCH_OPTION_PERK_GRANTS`. Left here only so a future session's
  memory of "this was still open" gets corrected on sight — see CLAUDE.md's "Gates" section.
- Middle-click isolation (P-7, fully specced, confirmed entirely unbuilt across every session
  asked about it).
- No `pytest` CI workflow exists yet (only `tsc --noEmit` runs in CI).
- Hover/selection discoverability (Item 7) — the right behaviour already exists, nothing surfaces
  it to the user; a cheap, optional follow-up, not asked for yet.
- **New this session**: gate propagation down `potential-gate` edges (as opposed to
  `prerequisite` edges, which now DO propagate) is a deliberately deferred scope boundary — see
  CLAUDE.md's Open Items.
- **New this session**: same-sub-column `alternative`/`potential-gate` edges (6 real cases, 2 in
  the Compound row) are a real, narrow gap in D-17's guarantee — surveyed, not implemented, per
  explicit instruction; see CLAUDE.md's Open Items for the recommended fix and why it's cheap
  (per-cell, not a global `subgrid_width` renegotiation).

**Prerequisite, same as every session**: `client/public/dataset/` is gitignored (D-15) and won't
exist in a fresh checkout — run `tools/build_dataset.py` locally (needs `vendor/` populated)
before `npm run dev`/`build` in `client/`. Re-run it fresh rather than assume any on-disk build is
current; the real node/edge counts are **973/977** (D-18 then Item 2c). **Gate instance count is
now stale here — see CLAUDE.md's "Gates" section for the current, real figure (TOTAL 267 instances
over 196 technologies, direct-only 139 over 112 technologies, as of the "Ring Segment /
ascension-perk locking / gate-propagation" session) rather than the 136/109 recorded in this
paragraph historically.**

---

## "Ring Segment / ascension-perk locking / gate-propagation" session (this session)

Nine items from a single prompt: (1) `always = yes` never handled as a leaf — fixed, 1 technology
(`tech_ring_world`) moved from unconditionally uncertain to available. (2) Ascension perks
CAN be a real profile fact when the perk's own `potential` carries a genuine axis constraint —
CLAUDE.md's locked decision corrected (not reversed) to this distinction; automated via
`pipeline.availability.set_perk_potentials` + a real `_combine_or` correction (see CLAUDE.md's
"Ascension perks are gates" section for the full survey: 21 perks cleanly axis-restricted, 20
left gate-only with residual undecidable conditions, one real cross-perk cycle broken by a
recursion guard). (3) Gates now propagate down `prerequisite` chains, tagged
`inherited`/`sourceTechnologyId` (schema + client updated) — fixes the user-reported QSO family
and "Management Protocols" repeatable gap; scoped to `prerequisite` edges only, `potential-gate`
propagation deliberately deferred. (4a) `on_enabled -> add_research_option` perk grants
(`tech_ring_world`/`tech_dyson_sphere`/`tech_matter_decompressor`) are now a gate source — closes
a previously-surveyed-but-unimplemented item. (4b) Cosmogenesis-locked technologies: surveyed,
found real (2 technologies, `giga_tech_fe_megaworkshop_1` and vanilla's own `tech_cosmogenesis_
thesis`) but `weight_modifier`-based, not gate/availability-based — each carries `modifier =
{ factor = 0 NOT = { has_crisis_level = crisis_cosmogenesis_level_4/5 } }`, a research-WEIGHT
mechanism (CLAUDE.md's own "weight is a separate concern from availability" rule), not a
`potential` condition. The "tensile buildings" (`giga_tech_amb_supertensiles*`) the user also
named do NOT share this shape — their only real gate is the already-known `@giga_amb_flag`
mod-config toggle (CLAUDE.md's Item 4, "deliberately unresolved" section). Deliberately NOT
treated as a gate — implementing it as one would conflate weight and availability, a category
error this project's own rules already warn against. Not implemented (correctly, per the survey's
own conclusion) — reported, not guessed at. (5) `has_active_tradition` resolves
TRUE by default except the user-confirmed `tr_genetics*` (unavailable to machine-intelligence) —
1 real corpus occurrence, `giga_tech_the_vat`. (6) Localisation/icon precedence: vanilla-won
technologies now use vanilla's own name/description/icon even when ACOT redefines the same loc
key/filename — exactly 3 real cases (`tech_dark_matter_power_core`/`_propulsion`/`_deflector`),
surveyed before implementing, confirmed independent of the ACOT-absent reduced-build diagnostic.
(7a) Dangling "or:" gates (sole alternative gate in a technology's list) downgraded to a plain
requirement — 20 real cases, Riddle Escort/Missiles/Torpedoes and the_vat's genuine 2-gate case
both confirmed unaffected. (7b) OR-set popup grouping: not implemented — the existing `groupId`
mechanism only covers `Edge`, not `Gate`; a genuine "need one of" grouped presentation for gates
would need new plumbing, reported here as a real gap rather than attempted under this session's
time budget. (8) Small fixes: enlarged the repeatable-infinity badge glyph (a dedicated 20px font
size for "∞" only); rewrote the off-tree-prerequisite popup note for an end user, full detail kept
under `?dev`; confirmed the 5 null-cost technologies still render no cost line. (9) Surveyed
same-sub-column edges (6 real cases, all `alternative`/`potential-gate`, none `prerequisite`; 2 in
the Compound row matching the user's report) and reported a recommended fix — a real, narrow gap
in D-17's guarantee, not implemented per explicit instruction.

Full pytest suite (1496 tests), `tsc --noEmit`, and `vite build` all clean after every change,
including a real, deliberately-updated set of pinned D-10/gate-count regression tests (each
updated with the reasoning for why the number moved, never silenced). Playwright/browser
screenshot verification was attempted (`npx playwright install chromium --with-deps`) but timed
out before completing in this environment — visual verification of the client changes (inherited
gate rendering, the enlarged infinity glyph, the rewritten off-tree note) was NOT done this
session; say so explicitly rather than claiming it, and do it early in the next session if visual
confirmation matters before shipping.

---

## Part-0 reconciliation session (stopped here per explicit instruction)

A fresh session opened with a 4-part prompt whose Part 0 was blocking: reconcile a disagreement
between two writeups over Compound's population (2 vs. a described "15, post-reclassification").
Confirmed by direct repo inspection: no flag→faction map existed anywhere before this session —
the queued "13 = tech_qnm_utilities + 12 dependents, via a flag map seeded with
`qnm_utilities_possible`" plan was genuinely dropped, not implemented, exactly as suspected.

Implemented as asked: `config/crisis_faction_flag_overrides.txt` + `pipeline/crisis_faction_flags.py`
+ `pipeline.crisis_faction.classify_by_flag` (D-7 "step 1.5"), seeded with the one entry
(`qnm_utilities_possible = Compound`), verified against the raw event/localisation source (not the
flag's name alone — see CLAUDE.md's new Part-0 bullet for the full evidence chain), wired into
`classify_crisis_factions` and `pipeline/dataset_emit.py`.

**Real measured result: Compound = 3, Standard = 922 — not the expected 15/910.**
`tech_qnm_utilities` itself correctly picks up Compound via the flag map; its 12 direct dependents
do not inherit, because the existing step-2 rule (`classify_by_prerequisite_inheritance`) requires
EVERY rendered prerequisite to already share one faction, and each of the 12 also requires an
ordinary Standard-lane baseline weapon technology as a co-prerequisite — a mixed set, by design
never propagated. This is not a bug; it's step 2 doing exactly what its own docstring says. The
queued "15" plan implicitly needed a weaker inheritance rule that was never specified or built.
**Per the prompt's own explicit instruction ("if it differs, stop and report before continuing"),
this session stopped here and did not attempt Parts 1-3** (edge routing/card-avoidance, spacing,
or the v1-sourced Sirenalia pattern port) — those remain fully open, unstarted.

Full pytest green (1,369 passed, up from 1,368 — synthetic `classify_by_flag`/loader coverage plus
the real-corpus regression tests were added alongside the fix). Client dataset not rebuilt, no
screenshots taken — this session's diff is pipeline-only.

**Resolved same session**: the user confirmed the 12 dependents should be Compound, via 12
individually-reviewed `config/crisis_faction_overrides.txt` entries (not a step-2 semantics
change) — implemented exactly as proposed. **Final real figure: Compound = 15, Standard = 910,
matching the originally-expected number exactly.** `config/crisis_faction_overrides.txt` now
carries 14 real entries. Row membership: `particles` 104→96 (7 dependents), `propulsion` 51→45 (5
dependents). Canvas returns to 13,632×11,608px (same as before the flag map, coincidentally — see
CLAUDE.md's Part-0 bullet for why that's not evidence nothing changed). Full pytest green (1,381
passed). Client dataset still not rebuilt as of the reconciliation itself — folded into the
verification pass for Parts 1-3, which this same session continued into per the user's
instruction. See CLAUDE.md's Part-0 bullet for the full final writeup.

## Parts 1-3: edge router card-avoidance rewrite, spacing, real Sirenalia geometry (same session)

**Part 1 — edge router.** Measured (not eyeballed) the real defect first: a script counting edge
polyline segments intersecting an unrelated card's bbox found **2,586 real crossings across 722 of
989 edges** on the pre-existing 4-point H-V-H router. Root cause, confirmed by direct geometric
analysis: the router's vertical run always landed in a genuinely card-free x (any inter-column gap
is empty across every row sharing a band, since column x only depends on band+column, never row),
but the LONG final horizontal segment connecting that x to the actual target position necessarily
crossed whatever unrelated cards sat in between at that fixed y — exactly the reported
false-connection shape. Several 4-point variants were tried and MEASURED (source-adjacent vs.
target-adjacent gutter, with/without forcing a true band edge) — **none reduced the crossing count
below the original baseline**, because a single-bend H-V-H shape always has one long,
unconstrained horizontal segment somewhere.

The fix that actually works needs a second bend: `pipeline/layout.py`'s `_route_edges` now emits a
**6-waypoint, 5-segment** polyline (exit stub → V → horizontal transit through the edge's own
SOURCE ROW's header/gutter strip, which is card-free for the FULL canvas width → V → entry stub).
Both vertical runs sit in a column gap (safe for their full height, regardless of row); the middle
horizontal run sits in a row header strip (safe for its full width, regardless of column) — a
provably-safe combination, not tuned empirically. **Measured real result: 0 crossings across all
989 edges** (down from 2,586). `MIN_STUB` (8px) added at both ends. This is a real schema/side-file
change: `pipeline/geometry.py`'s `POINTS_PER_POLYLINE` moved 4→6; `client/src/main.ts`'s
`FLOATS_PER_EDGE_POLYLINE` moved 8→12. `roundPolylineCorners`/`tracePolyline`/`addArrowhead` were
already generic over point count and needed no logic changes, only stale comments fixed.

The user's exact named technologies (`tech_improved_deflectors`, `tech_basic_cloaking_fields`)
don't exist under those literal keys in the vendored corpus — but the real corpus DOES contain
"Improved Deflectors" (T1) directly above "Storm Manipulation" (T2) and "Basic Cloaking Field"
(T2) to its right, in the same neighbourhood the user described — screenshotted directly (see
below) and confirmed clean: no trace runs under "Storm Manipulation."

**Part 2 — spacing.** `INTRA_GAP_X` 24→40px (was flagged still-too-tight; `INTRA_GAP_Y` confirmed
acceptable, unchanged). `ROW_GUTTER` 24→48px (more separation between every row). New
`AREA_GROUP_GUTTER` (96px), applied only at the 3 real group boundaries (the 3 research areas
each form one group, the 5 faction rows form a 4th) via a new `row_group_of` map `_row_order`
returns alongside `row_order` — client-side, derived from the SAME `tech.area` lookup already used
for row chip colouring (`rowArea`), no schema change needed for this half. `ROW_HEADER_HEIGHT`
52→68px, and the per-cell tier label's x moved from a hardcoded `+4` to `+CHIP_MARGIN` (shared
left edge with the chip) — both closing the reported label/chip misalignment and tight vertical
clearance before the first card row. **Real measured canvas: 14,160 × 12,616px** (was
13,632 × 11,608px).

**Part 3 — Sirenalia geometry, ported from v1 directly.** v1's actual pattern lives in
`js/render.js`'s `drawWaves` (NOT CSS — v1 draws it on a canvas 2D context; the CSS only holds a
`--siren` colour variable used elsewhere). Ported verbatim: 4 layers, each a FILLED region bounded
above by a sine curve (`y = rowTop + rowHeight*(base + sin(t)*amp)`) and below by the row's own
bottom edge — not a stroked ribbon, which is what the three earlier rejected attempts drew. v1's
own per-layer `{amp, phase, base, alpha, period}` values and 60px sampling step were copied
directly. **Correction to this project's own prior assumption**: v1 uses ONE accent colour across
all 4 layers with only ALPHA varying (0.05→0.09) — not "several distinct pink/purple shades" as an
earlier session's placeholder both stated and implemented; `tokens.ts`'s Sirenalia entry and
comment were corrected to match. The signed-off `#B0338C` hex is kept as that one colour (v1's own
`--siren` CSS value is a different palette, out of this session's styling-port scope per the
signed-off-hex rule). No PixiJS-vs-canvas-2D gap was hit — `Graphics.fill()` after building each
layer's path handles v1's per-layer fill directly.

**Aeternum lightening**: signed-off hexes (`#591227` backing, `#823269` flag pink) unchanged;
`tokens.ts`'s Aeternum pattern spec now uses a LOCAL, rendering-only lightened variant (`#823269`
blended 35% toward white → `#AE7A9E`) as the hexagon stroke colour, plus `accentAlpha` 0.30→0.42.

**Verify**: full pytest (1,381 passed), `tsc --noEmit`, `vite build` all clean. Real dataset
rebuilt (`tools/build_dataset.py`) and served via `vite preview`; a real headless-Chromium
(`playwright-core`, transient, not added to `package.json`) run: zero console errors, zero failed
requests, `stageChildCount === 1`, `rowPanelCount === 18`, `checkNameBounds`/
`checkChipLabelOverlap`/`checkEdgeEndpointsInCards` all 0 violations, and a new
`checkMinStubLength` (added this session, checks the RAW pre-rounding polyline's exit/entry
segment lengths against `MIN_STUB`) — **0 violations across all 989 edges**. Five screenshots
reviewed: fit-to-viewport (area/faction grouping visibly reads as 4 blocks), the
Improved-Deflectors/Storm-Manipulation/Basic-Cloaking-Field neighbourhood at 100% (clean routing,
directly refuting the reported false connection), the Sirenalia row at 100% (real layered wave
fill, not the old stroked-ribbon placeholder), the Aeternum row at 100% (visibly lighter hexagon
stroke against the burgundy backing), and the voidcraft→Aeternum row-group boundary at 25% (the
larger inter-group gap reads clearly against the ordinary Aeternum→Blokkats row gap directly below
it).

**Next up**: badges (rare/dangerous/repeatable/gate/tier), pattern fills as real traced art (the
Blokkats flag SVG trace is still the one open procedural-placeholder item), hover/click/selection,
popups, search, empire-profile switching — same exclusions as every prior slice, still open.

## EAWAF/Sirenalia correction, v1-style edge router, edge LOD, and spacing session

Six numbered items from the user. Items 1, 4, 5, 6 implemented; items 2 and 3 surveyed and
STOPPED ON, per explicit instruction — see CLAUDE.md's bullet of the same name for the full
per-item writeup, exact figures, and reasoning. Summary here, for a fast catch-up:

**Item 1 (implemented)**: re-derived Sirenalia/EAWAF membership without relying on
`has_star_flag = giga_eawaf_siren_faust` (confirmed unsound — Faust isn't Siren-exclusive). All 7
of the family's flag-gated technologies are confirmed set exclusively inside the Sirens' own event
chain (`giga_034_eawaf_events.txt`, which creates a country literally named "Sirenalia"). Sirenalia
7 → 14 via 6 new `config/crisis_faction_flag_overrides.txt` entries + 1 new
`config/crisis_faction_overrides.txt` entry. This is the FOURTH instance of the project's recurring
defect class (a survey dismissed a whole family on the wrong distinguishing signal) — see
CLAUDE.md's defect-class paragraph. A DNF-based reachability rule (test-scope only, NOT promoted to
the live classifier) still converges exactly with the hand-built derivation after this change.

**Item 2 (surveyed, no code changed)**: no rendering-scope bug found. The user's two named
"over-inclusion" examples turn out to be a Gigastructures technology (unconditionally rendered by
design) and a legitimate ACOT closure member — likely Item 3's stacking defect misread as an
over-inclusion case. Re-open only with a new, specific example.

**Item 3 (this session: surveyed, no code changed — SUPERSEDED, see reconciliation note above)**:
the "never render left of/in line with a prerequisite" invariant is real, violated (182/315
same-band prerequisite edges, 57.8%), always satisfiable (no same-band cycles). This was
subsequently IMPLEMENTED as D-17 by a concurrently-running session, and its width cost landed
close to this survey's own +11.6% prediction — but a follow-up reconciliation session found and
fixed an unbounded-stacking bug in that implementation. See D-17 in `spec/decisions.md` for the
full history and the corrected canvas figure.

**Item 4 (implemented)**: replaced the previous, PROVEN-zero-crossings gutter-channel router with a
port of v1's own chamfered two-bend "circuit trace" edge geometry (`js/render.js`'s `addEdge`),
per the user's explicit rejection of the gutter router's dense-parallel-channel look after seeing
it rendered. This is a knowing, recorded trade — new measured unrelated-card-crossing count is
2,828 across 606/989 edges (nonzero, accepted). A minimum-stub guarantee was added on top of v1's
own formula (which has none), with a fallback to the previous gutter router for the subset of edges
(same-band/short/backward) v1's two-bend shape can't route without violating it — endpoint
containment and minimum stub length both stayed 100% clean (0/989 violations) throughout. Also
corrected: `EDGE_COLOR` was wrongly brightened to blue-cyan in an earlier session on a mistaken
belief about v1's own colour — checked against v1's real source this session, v1's actual default
is a dark grey (`#38363c`); the blue-cyan is now `HOVER_COLOR`, reserved (with a comment) for a
hover/selection state that doesn't exist yet.

**Item 5 (implemented)**: edge LOD reappearance threshold lowered so edges come back at 16.6% zoom
(status-strip-reported), one step further out than the previously observed 21.5%.

**Item 6 (implemented)**: `INTRA_GAP_X` 40→120px (a fourth pass at the same recurring complaint).
Found and fixed a REAL rendering bug while investigating why `ROW_GUTTER` read as invisible: row
panels were drawn across their FULL reserved height, including their own trailing gutter, so
adjacent panels visually touched with zero apparent separation even though `ROW_GUTTER` was a real,
correct, nonzero number. Fixed at the render call site (panels now stop `ROW_GUTTER` short of their
own bottom); `AREA_GROUP_GUTTER` reduced 96→64px now that it's no longer competing with an invisible
`ROW_GUTTER` for "which gap reads as bigger." Real measured canvas: 16,800 × 12,520px.

**Verified**: full pytest (1,382 passed), `tsc --noEmit`, `vite build` all clean; real dataset
rebuilt and a real headless-Chromium run confirmed zero console errors/failed requests, 0/989
endpoint-containment and minimum-stub violations (new detectors proven capable of failing on
synthetic bad inputs before trusting the clean pass), and the 2,828/606 crossing count. Five
screenshots reviewed and matched expectations — see CLAUDE.md for the full list.

**Not done, tracked above in "Next prompt"**: the badges slice is still the next open, unstarted
work (Item 3's fix landed via the concurrently-running D-17 session, then a follow-up
reconciliation session — see above — not via this session).

## Reconciliation session — D-17 stacking fix, docs split, edge-router offset fix, row/band geometry desync fix

Opened after a report that a concurrent session had stood down mid-work, leaving the repo in an
unreconciled state. Ran single-threaded throughout, no sub-agents, per explicit instruction.

**D-17 unbounded-stacking bug found and fixed.** `pipeline.layout.compute_layout` used
`same_band_depth` directly as sub-column, stacking every member sharing a depth in ONE column via
an unbounded counter — the real corpus's worst cell stacked 37 unrelated technologies 37 rows
tall. `tests/test_layout.py` had a test asserting this as intended behaviour (a THIRD instance of
this project's "green suite proves self-consistency, not correctness" pattern, and the first one
that didn't just have narrow fixture coverage — it actively enshrined the bug as spec). Fixed:
depth now sets a MINIMUM sub-column; each depth is a slot of one or more sub-columns, wrapped at
`subgrid_width`. Canvas moved 18,750×30,152 → 30,840×9,736. Full writeup, including the
`subgrid_width` 4/6/8/12 trade-off survey the new width cost prompted (not changed, left for the
user to pick from), is D-17 in `spec/decisions.md` — read that before touching sub-column
assignment again.

**CLAUDE.md split.** It had grown to 210,756 chars (past the CLI's 150k warning), 83% of it an
append-only "Open items" session log. Moved verbatim (byte-identical, checked) to
`docs/BUILD-LOG.md` (179,453 chars now), reorganised by component rather than chronology.
CLAUDE.md is now 38,605 chars with a short, genuinely-open "Open items" list. HANDOFF.md
(112,951 chars) was judged NOT to have the same problem — it's a working document with a real
"Next prompt" section, not an append-only log — and was left structurally intact.

**Two count discrepancies from a prior session, reconciled:**
- Sirenalia's 14th member (`giga_tech_eawaf_psifusion`) is classified via a technology-key
  override on genuinely weaker evidence than the other 13 (no `potential` block at all to key
  on — pure file/event-chain co-location). The other 13 all have a direct flag/ID signal. This is
  why v2 shows 14 against v1's 13 — not a miscount, a deliberate (documented) extra inclusion.
- The "2,828 crossings / 606 edges" figure was never a different denominator from 989 — 606 is
  `affectedEdgeCount` (edges with ≥1 crossing), always checked against all 989. Re-measured after
  this session's own changes: 2,992 crossings / 725 of 989 edges affected.
- `client/src/{tokens,camera,lod}.ts` were never git-tracked (zero commit history) so "edited vs.
  recreated" can't be answered from git — but every documented justification (camera clamps, LOD
  thresholds, `EDGE_COLOR`/`HOVER_COLOR`) is present and matches the narrative; nothing lost.

**ACOT/AoT closure depth (Item 5): surveyed, not implemented, per instruction.** Depth-1-only
would break exactly 3 links, all ACOT→ACOT, confirmed to include the user's own named case
(`tech_dark_matter_power_core_ae`, "Alpha-class Enigmatic Power" → `tech_precursor_design`,
"Precursor Databank Analysis", both verified against real vendored localisation). A middle option
(render an out-of-closure prerequisite as a distinct stub/ghost node) is feasible but unbuilt.
User needs to pick between depth-1, the current full-transitive-closure rule, or a stub option.

**Edge router: two real fixes, not just verification.**
1. Fetched v1's real `js/render.js` directly — confirmed `_v1_style_waypoints` is a byte-for-byte
   port of v1's own `addEdge` (the "chamfer" IS what v1 itself calls "corners chamfered at 45°";
   there is no separate longer-diagonal path in v1's real source to port instead).
2. Found the real trough cause: v1's own formula has no per-edge offset at all, so edges sharing
   similar geometry drew literally overlapping traces (worst cluster: 54 edges sharing one exact
   `mid` x-value). Added a small deterministic offset (reusing the existing `_channel_offset`
   hash) — worst cluster drops to 10, total overlapping-edge count 868 → 685. Crossing count
   against unrelated cards is materially unaffected by this specific change (~2,992 either way) —
   it addresses visual overlap, not card-crossing, which are different concerns.

**A second, serious desync bug found and fixed while re-verifying: `client/src/main.ts` computed
row/band geometry (panel/tint/header positions) via its OWN reimplementation of
`pipeline/layout.py`'s formulas, which silently went stale the moment D-17's wrap-within-depth fix
changed those formulas server-side.** Row panels, tier tints, and cell labels were drawing at
completely wrong positions relative to where cards actually rendered (found via a headless
screenshot: a faction row's pattern nowhere near its own cards). Permanent fix, not a re-sync:
row/band geometry is now DERIVED from the real min/max node positions in the geometry side-file,
so client and server geometry can never drift apart again regardless of future formula changes.
Verified: `rowGeometry.y` for every row now matches its real card positions exactly (header-offset
apart); confirmed visually across all four required screenshot cases.

**Item 7 verification, real numbers, current dataset:**
- Tier badge vs. band: 0/892 non-repeatable nodes disagree (checked directly, not assumed).
- 88 repeatable technologies, all in the terminal band; none render a repeat-count badge yet
  (badges slice, still unbuilt).
- 28/980 cards render `Cost: 0` — real corpus zero-cost starting technologies, not a fallback
  (5 more have `cost: null` and render no cost line at all, per existing policy).
- 107/980 names render with an ellipsis; 6 distinct visible-text collisions (different
  technologies whose wrapped/clamped display text happens to coincide — not itself a bug, since
  full names differ and are available on hover/popup, but worth knowing).
- 0/980 cards fall back to a missing icon.
- The 7 long-span backward `potential-gate` edges are now locatable and traceable (confirmed by
  screenshot) — `tech_cosmogenesis_escort → tech_missiles_1` (bandSpan 5) is the longest.

**Verified**: full pytest (1,384 passed), `tsc --noEmit`, `vite build` all clean throughout. Real
dataset rebuilt twice (once after the D-17/offset fix, once after the row/band geometry fix); a
real headless-Chromium run against the final rebuild: zero console errors, zero failed requests,
all existing invariant checks (name bounds, chip/label overlap, edge endpoints, min stub) still
0 violations. Four required screenshots taken and reviewed: fit-to-viewport (row panels now
correctly span their full real extent), the D-17 in-line case (`tech_dark_matter_power_core_ae`
isolated, no overlap), the Sirenalia row (patterns now aligned with real cards, all 14 members
visible including the reclassified EAWAF technologies), and a multi-elbow/long-span-edge region.

**Not done this session, by explicit instruction**: Items 3 and 5 (`subgrid_width` value itself,
ACOT/AoT closure rule) are surveyed only, awaiting the user's decision. `docs/BUILD-LOG.md`'s
reorganisation moved content but did not rewrite or re-verify any individual historical claim
inside it beyond the byte-identical-move check.

**Next prompt should point at the badges slice** (guidance above, in the "Next prompt to paste
into Claude Code" section, is otherwise still accurate) — but MUST run `tools/build_dataset.py`
fresh first (D-15, gitignored dataset) and should re-run the headless verification script rather
than trust any number in this section as still current once new code lands.

## Reconciliation + D-17 extension + P-12.9 implementation session

Four numbered items plus P-12.9, run single-threaded, no sub-agents, per explicit instruction.

**Item 1 (reconcile the uncertain count)**: not a regression. Full pytest went 1495 → 1496 across
the prior session's six-change commit (`a36722b`), and its own pinned-test update
(`c45448e`) documents each figure's move with a named reason (three real fixes: `always` leaf
evaluation, ascension-perk axis-locking's `_combine_or` correction, `has_active_tradition`) — no
process failure. Rebuilt dataset confirms the pin exactly: unconditional uncertainty 31/973
(3.19%), union 53, worst profile-dependent 16/973 (1.64%, `status: "ok"`), D-10 ratchet holds
(`previousRate == rate` on every profile).

**Item 2 (perk-perk cycle)**: already correctly handled, not a gap. `ap_defender_of_the_galaxy`
<-> `ap_defender_of_the_galaxy_nomads` is a real mutual-exclusion pair in the mod's own source
(each excludes the other via a `NOR = { has_ascension_perk = <the other> }` superseded-perk
guard); `pipeline.availability`'s eager (non-short-circuiting) block evaluation means both
directions genuinely get walked, and `_perk_eval_in_progress`'s recursion guard breaks the cycle
correctly. `ap_defender_of_the_galaxy` resolves LOCKED (its own `potential` starts
`has_nomads_dlc = no`, false under the all-DLC-owned assumption); `ap_defender_of_the_galaxy_
nomads` stays gate-only (its own NOR references two unregistered game-state leaves,
`is_player_crisis`/`is_unfriendly`, so it can't fully resolve either way). Zero rendered
technologies reference either perk id directly — the cycle has zero downstream effect on gates or
availability.

**Item 3 (visual verification)**: Playwright's browser installed cleanly this session
(`npx playwright install chromium`, cached in `~/.cache/ms-playwright`) — no install blocker this
time. All nine required cases verified by real headless-Chromium screenshot against the rebuilt
dataset, zero console errors throughout: an inherited gate's "(via <source>)" note
(`giga_tech_quasi_stellar_2`), the QSO/Management-Protocols families' new inherited perk gates,
`tech_dyson_sphere`'s new direct perk-grant gate, a nomadic-vs-non-nomadic lock behind Galactic
Wonders (`giga_tech_ringworld_titanic_1` — non-nomadic shows the gate as "available", nomadic
shows "locked — Requires the ap_galactic_wonders ascension perk"), Birch World's dangling "or:"
now plain "Needs Vast Expanses", a genuine two-gate OR set (`giga_tech_the_vat`: "Needs Galactic
Wonders" + "or: Mechromancy"), the repeatable infinity glyph (clearly "∞", not a hyphen, at both
mid-zoom and close-up), the off-tree-prerequisite end-user note, and a 4-gate card
(`tech_cloning`) with no overflow. One pre-existing, already-documented gap observed, not new:
origin/ethics-or-civic gates render no icon (blank) in the popup — CLAUDE.md's "Icons — reported,
not vendored" note already covers this.

**Item 4 (D-17 same-sub-column extension): implemented.** `pipeline.layout._same_band_depth`
gained an `extra_same_band_edges` parameter fed from `alternative`/`potential-gate` edges
(`compute_typed_edges`, moved earlier in `compute_layout` so both consumers share one call).
Canvas 29,670 × 13,448px → 30,060 × 13,448px (+390px, +1.3%, well under the ~10%
stop-and-report threshold), densest cell/row population unaffected. New corpus test
(`test_zero_same_sub_column_pairs_across_all_edge_kinds`) proven to fail first (24 violations
against the pre-extension code) before trusted on the fix. See `spec/decisions.md`'s D-17 section
for the full record.

**P-12.9 (research path): implemented.** `researchPaths[technologyId]` per profile now carries
`{status, steps, totalCost, totalCostIsEstimate, estimateReasons, configGatedTarget}`
(`pipeline.dataset_emit._build_research_paths_for_profile`), replacing the old placeholder
`{ancestors, shortestChain}` shape. `alternative` groups resolve to the cheapest-full-closure-cost
viable candidate, never just the branch's own declared cost (the fix for v1's "Arkship Mastery
never expanded its own prerequisites" bug); the chosen step's `alternatives` names the other
viable siblings, never flattened. A real, load-bearing correction found while implementing: the
spec's own worked example (`tech_mega_engineering` = 74,750 for regular/mechanical/non-nomadic)
only reproduces when `totalCost` for `status == "path"` INCLUDES the target's own declared cost —
the schema's literal "sum of stepCost" text was imprecise; confirmed against three independent
figures (74,750, 73,750, and the corrected nomadic 76,250) before trusting the fix.

Three stale spec figures re-measured against the current corpus: the OR tie-break
(cheapest-total-cost vs. fewest-steps) now disagrees on 12 of 72 genuine 2+-viable choices (was
"0 disagreements"); the nomadic `tech_mega_engineering` total is 76,250 (was 99,750, content
drift). A FOURTH figure — inherited in this session's own prompt as "confirmed still zero" — was
found to be wrong on direct measurement and corrected rather than forced to match: the "dangerous"
sub-case (ancestor chain broken while the target's own state stays available/uncertain) is real
and substantial on the current corpus (78 technologies / 472 pairs), confirmed against raw source
(`tech_ehof_spinal` unconditionally requires `tech_arkship_tier_3`, itself `is_nomadic = yes`-
locked). Reported honestly per CLAUDE.md's "raw inspection only, a documented claim is not
self-verifying" rule, not suppressed to match the inherited assumption. New diagnostics field
`unresolvableResearchPaths` surfaces every `{technologyId, profile}` pair.

Client: `main.ts`'s `openPopup` now fetches the profile overlay unconditionally (previously only
for a non-`available` technology) and renders a "Research path" popup section via a new
`renderResearchPath` function — ordered steps with per-step cost and an `uncertain` badge, running
total with its estimate note, inline `alternatives` on a chosen OR-step, and the config-gated
target's subject/template note. Verified with 5 real screenshots (an OR-choice path reproducing
74,750 exactly, the nomadic Arkship-branch substitution reproducing 76,250 exactly, an
uncertain-step estimate, an `unavailable` dangerous-case target, and a config-gated target
excluding its own cost from the total) — zero console errors.

**Global verify**: full pytest 1507 passed (was 1496 at session start), `tsc --noEmit` and
`vite build` both clean. Largest empire
overlay (research paths added): 1.25MB raw / 63.5KB gzip — comfortably inside the ≤2MB compressed
budget. Existing layout/geometry invariant tests (row-overlap, card-within-row, name-bounds,
D-17 including the new per-cell extension, edge-containment) all still pass unmodified.

## Gate-polarity/nested-OR/wilderness-icon fix session

Six numbered items from a domain-authority user report, run single-threaded. Full detail in
CLAUDE.md's own "Gates"/"Open items" sections; terse record here.

**Item 1 (gate-polarity bug, real class bug, fixed).** `pipeline.gate_patterns` tracked negation
only via a `NOT`/`NOR` wrapper ancestor, never a leaf's own literal boolean-false VALUE
(`is_wilderness_empire = no`) — Clausewitz's OTHER way to write a negative condition, no wrapper
at all. `_leaf_negated` now XORs three channels (wrapper, `!=` operator, literal `= no`); safe to
apply unscoped (checked: `= no` occurs ONLY on `is_wilderness_empire` in the real corpus, 31
technologies). A real bug was found and fixed WHILE fixing this: the first implementation used
Python's `a != b != c` CHAINED comparison, not a real 3-way XOR — caught by direct testing before
it shipped. `can_research_technology` (meaning "eligibility", not `has_technology`'s "already
completed") is removed from gate classification entirely — one real occurrence, but gate
propagation had inherited the mis-badge onto 15 descendants (16 technologies), matching the
user's "many technologies" report. The "bioship technologies not locked" half of the report was
surveyed and found NOT the same bug (87/88 real `country_uses_bio_ships` references already
resolve correctly). Gate counts: DIRECT 139 → 107 (48 ascension_perk + 14 origin + 24
ethics_or_civic + 21 technology) over 83 technologies; TOTAL 267 → 214 over 147 technologies.

**Item 2a (Nano-Assembler/Polyatomic Crucible): surveyed, NOT a bug.** Raw source confirms
neither has an ascension-perk requirement in `potential` — the prior session's "weight-based, not
gate-based" conclusion for the Cosmogenesis family stands. Reported to the user, not fabricated.

**Item 2b (nested AND-of-OR gates, real structural bug, fixed).** `GateMatch` gained `group_id`
(mirrors `Edge.groupId`'s per-owner, per-block-index identity), naming the specific `OR`/`NOR`
block a gate is a direct child of. Real corpus: exactly 1 technology (`giga_tech_the_vat`) mixes
unconditional and grouped matches; the client now nests same-`groupId` gates under their own
"Need one of:" cluster instead of showing them as flat peers.

**Item 3a (wilderness/origin/ethics icon fallback, real bug, fixed).** The degenerate 1x1-pixel
stretched fallback (`_default_icon_ref`) read as a rendering error (a "teal square") for
origin/ethics-or-civic gates — not a rare edge case, it fired 100% of the time (no icon source
vendored for any of these). `Gate.icon` is now nullable; the client renders label-only when null.

**Item 3b (wilderness as a fourth axis): surveyed, NOT implemented, real decision needed.**
Simulated wilderness=true/false against the real evaluator for all 4 hive-authority profiles: 41
of 973 technologies (4.2%) / 148 (technology, profile) pairs show a REAL availability difference
between a wilderness and non-wilderness hive empire — not small. Reported to the user with the
cost (24 profiles, every per-profile array doubles) for a decision.

**Item 4 (two "Confluence of Thought" technologies): confirmed already-known, not new.**
`tech_hive_confluence`/`tech_wilderness_confluence` are two deliberately-parallel vanilla
technology lines (confirmed via raw source's own "# Wilderness" section header) — already one of
the reconciliation session's 5 documented genuine same-name pairs.

**Item 5 (looping edges): surveyed, NONE FOUND.** Three independent geometric checks (X-reversal,
Y-hook shape, polyline self-intersection) against the rebuilt dataset found zero matching edges
across all 977. Recommended asking the user for a screenshot or specific technology name.

**Item 6 (dangerous ancestor-broken case): surveyed, STOPPED per instruction, not implemented.**
Re-measured after Item 1 landed: still exactly 78/472 — UNCHANGED, confirming it's not an
artefact of the polarity bug. Categorised by cause (44 nomadic-locked ancestor, 25 axis-locked
perk ancestor, 4 hive/shipset-locked, 2 zero-viable OR-group, 3 unresolved) — every traced case is
a real, non-alternative dead end, none found to be a modelling artefact. Recommended a distinct
status value (naming the blocking ancestor) rather than `status: "unavailable"` for both causes —
not implemented, since this changes a spec decision (P-12.9 section 6) the user should review
first.

**Verification**: full pytest (1514 passed, up from 1507), `tsc --noEmit` and `vite build` both
clean. Real dataset rebuilt and headless-Chromium-verified: zero console errors across all
screenshots (habitat technology with corrected polarity, Gargantuan Cloning Facilities' nested
AND-of-OR, Nano-Assembler with no fabricated gate, Gene Banks with no icon-fallback square),
`checkNameBounds`/`checkIndicatorBounds`/`checkEdgeEndpointsInCards`/`checkTierBadgeMatchesBand`/
`checkGateLabelFontAndCollision` all 0 violations. D-10 figures unchanged (31/973 unconditional,
53 union, worst 16/973 = 1.64%) — confirmed directly, not assumed, since the gate-display fixes
never touch `pipeline.availability`. Canvas dimensions unaffected (gates are display metadata,
computed after layout).
