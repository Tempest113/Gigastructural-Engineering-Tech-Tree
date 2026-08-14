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

- **Deployment / GitHub Pages skeleton.** Discussed and postponed. Groundwork first; the user
  does not want a half-built site in the repo while the pipeline is still moving. Revisit once
  the dataset schema and a first emitted dataset exist.
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
output validated in CI.

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

Five packages, each self-contained and separately tested, none merged into a shared
"do everything" module:

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

Full pytest suite: **1,056 passed, 0 failed** (`pytest tests/`).

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
  3. **Whether atlases count toward the P-10 ≤2 MB initial-transfer budget is unresolved.**
     P-9 and `spec/implementation-notes.md` require icons to load lazily, which may put them
     outside that budget's accounting entirely. This is a dataset-schema decision. Lossless WebP
     is currently 8.5 MB across the technology sheets — lossy remains an available lever, but the
     decision should be made against a scope-filtered figure, not this superset.
- **`config/icon_overrides.txt`** is currently empty by design. Expect entries only after a
  *human* decides what's correct for each case — not a future agent session guessing.

---

## Ordered next steps

1. **Dataset schema** (`schema/`, not yet created). **This is the immediate next task** — the
   prompt for it is written and ready. A JSON Schema contract between Stage 2's Python output and
   the TypeScript client. Must settle the initial-payload vs lazy-payload split that the icon
   atlas byte-size question is blocked on, and must be sanity-checked against P-10's ≤2 MB
   initial-transfer budget with a real size estimate before Stage 2 is built on top of it.
2. **Overwrite resolution (P-15).** Whole-key, last-definition-wins across load order — the same
   rule already implemented in `pipeline.variables` and `pipeline.localisation.table` needs its
   canonical general form for technology definitions themselves. Also the blocker for the icon
   atlas's research-area split (rejected this session specifically because it needs this).
3. **Partial trigger evaluator (D-10).** The highest-risk component in the project and the one
   D-10's unknown rate depends on entirely. Unblocks both `TODO(Stage 2)` items in
   `pipeline/icons/resolve.py`, gate detection (P-3's pattern-matching layer, distinct from the
   universal `potential-gate` edge extraction), and rendering-scope computation generally.
   `common/scripted_triggers/` is the single biggest lever on the unknown rate.
4. **DAG build + P-16 ancestor closure**, which the icon atlas's real content scope depends on
   directly.
5. **Tier/column/edge computation, dataset emission** — the rest of Stage 2.
6. **Stage 3 (Render)** — nothing exists yet. Largest remaining body of work.
