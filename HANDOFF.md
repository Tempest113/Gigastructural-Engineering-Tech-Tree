# Handoff — Stage 1 (Extract) and Stage 2 (Compute) complete, Stage 3 (Render) in progress

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
   profile, assign layout, route edges, emit dataset. **Complete and real.**
   `pipeline/dataset_emit.py` emits all five schema-validated artefacts (base dataset, empire
   overlay, detail payload, search index, diagnostics) against the full vendored corpus. Not
   wired into a CI build command (deliberately — see D-15 in `spec/decisions.md` and CLAUDE.md's
   "Source data"/deploy notes: the dataset can never build in CI, it's built locally via
   `tools/build_dataset.py` and shipped through `tools/deploy_local.sh`).
3. **Render** (TypeScript + PixiJS, browser) — load dataset and draw it. **In progress.** Static
   render, camera/LOD, edges, row/band layout, badges, hover/selection/popup, search, empire-
   profile switching, and the research-path popup are all built — see CLAUDE.md's "What's built"
   pointer and `docs/BUILD-LOG.md`'s Stage 3 sections for the full slice-by-slice record. Not yet
   built: middle-click isolation (P-7) — see CLAUDE.md's Open Items.

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
  `availability.state` are redundant by design (see the schema field's own description) — wired
  into the real `pipeline/dataset_emit.py` build and checked on every run.

All of the above are gated behind `vendor/` being populated locally (gitignored, CI never has
it) — see each test file's `skipif`. CI-safe regression coverage over a small committed fixture
subset exists in parallel (`tests/fixtures/`, manifest-driven, `tools/regenerate_fixtures.py`).

## Current headline figures

Full detail, provenance and every historical correction live in `docs/BUILD-LOG.md`; this is
just the current, reconciled snapshot so a fresh session doesn't have to hunt for it.

- **Rendered nodes: 973** (Vanilla 673 + Gigastructures 300 + ACOT/AoT depth-1 closure, minus 4
  permanently-`always = no` technologies — D-18 then Item 2c in CLAUDE.md's "Scope of ACOT and
  AoT"). Edges: 977 (876 prerequisite + 76 alternative + 25 potential-gate).
- **D-10 uncertainty** (after Item 2b's zero-weight-gate fold-in): worst profile-dependent 58/973
  (5.96%, over the 3% warn threshold, under the 10% ceiling); unconditional 115/973 (11.8%); union
  (uncertain for ≥1 profile) 180/973. See CLAUDE.md's "Research weight" section for why.
- **Gates (P-3)**: DIRECT 107 instances (48 ascension_perk + 14 origin + 24 ethics_or_civic + 21
  technology) over 83 technologies. TOTAL (direct + inherited down `prerequisite` chains) 214
  instances over 147 technologies, 47 with more than one.
- **Canvas**: 30,060 × 13,448px at `subgrid_width=6` (D-17, settled).
- **Base dataset**: ~64 KB compressed. Largest empire overlay (with research paths): 63.5 KB
  gzip. Both comfortably inside the ≤2 MB budget.
- Full pytest suite, `tsc --noEmit`, `vite build`: clean as of the last session that touched
  pipeline or client code (see `docs/BUILD-LOG.md`'s most recent entry for the exact test count).

**Always rebuild before trusting any number above.** `client/public/dataset/` is gitignored
(D-15) — run `tools/build_dataset.py` (needs `vendor/` populated) before `npm run dev`/`build` in
`client/`, and re-derive figures from the fresh build rather than trusting this section, which is
a snapshot that goes stale the moment new pipeline code lands.

## Open items

See CLAUDE.md's own "Open items" section — kept there, not duplicated here, so there is exactly
one place a session needs to check for what's still genuinely open. `docs/BUILD-LOG.md` has the
full historical record of everything already closed.

## Where to look for what

- **`spec/`** — normative requirements, one file per concern (P-numbers) plus `decisions.md`
  (D-numbers) for settled trade-offs. Authoritative; nothing here or in CLAUDE.md should
  contradict it.
- **`CLAUDE.md`** — the running summary: architecture, stack, source data, locked decisions
  (empire model, scope, prerequisites, trigger evaluation, gates, tiers, colour, repeatables,
  research weight/path), the project's working rules, and current open items. Read this before
  making any design call.
- **`docs/BUILD-LOG.md`** — full historical build record: every session's findings, measured
  figures, and defects, organised by component/stage. Read this when you need to know *why* a
  number is what it is, or whether something was already tried and rejected.
- **This file (`HANDOFF.md`)** — a point-in-time status snapshot and the standing "how we work"
  instructions above. Not authoritative on anything `spec/`/`CLAUDE.md` also cover. Update or trim
  it rather than letting it accumulate a session log again — that drift has already happened once
  and been reversed; don't let it happen a third time.
