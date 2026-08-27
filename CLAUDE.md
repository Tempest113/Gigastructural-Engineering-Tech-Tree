# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Gigastructural Engineering Tech Tree

Interactive tech tree visualiser for the Stellaris mod *Gigastructural Engineering & More*.
Static client-side site, deployed to GitHub Pages. No backend, ever.

The normative requirements live in `spec/`; `spec/` is authoritative. This file answers only
"what must I know before I touch anything, that I cannot get by reading the code": standing
rules (in full), locked decisions (one line, pointing to their spec/ home), and a current-state
index (what's built, what's open). Full reasoning, measured figures, and session history live in
`docs/BUILD-LOG.md`; recurring bug shapes live in `docs/DEFECTS.md`. If this file conflicts with
`spec/`, `spec/` wins — fix this file to match. **When a decision changes, update this file's
one-liner in the same session; don't defer it.**

## Architecture

Three stages, boundary load-bearing: **Extract** (Python, CI) parses Clausewitz script and
localisation into a lossless AST. **Compute** (Python, CI) resolves overwrites, builds the DAG,
evaluates triggers per empire profile, assigns tiers/columns, routes edges, emits the dataset.
**Render** (TypeScript + PixiJS, browser) loads the dataset and draws it. The browser never
parses Clausewitz and never computes layout — both are build-time only; runtime does visibility
masking over fixed geometry, nothing more. The dataset schema (`schema/`) is a cross-language
contract — JSON Schema, with TypeScript types generated from it and the Python output validated
against it in CI. Never hand-edit either side independently.

## Stack

Pipeline: Python. Client: TypeScript, PixiJS (WebGL) + DOM overlay for popups/controls. Dataset:
JSON + typed-array side-files. Host: GitHub Pages. CI: GitHub Actions.

## Source data

Not committed — gitignored `vendor/`, populated by `tools/collect_vanilla.py`.

| Source | Version | Update path |
| --- | --- | --- |
| Stellaris base game | 4.5 | manual, re-run the collector |
| Gigastructural Engineering | pinned commit (currently `0f1f2b0`, tag `v3.39.3`) | GitHub `Live-Branch`, currently unautomated |
| ACOT | manual | Steam Workshop only |
| AoT | manual | Steam Workshop only, depends on ACOT |

Load order lowest→highest: vanilla, Gigastructures, ACOT, AoT — an ordered list, never
special-cased "vanilla vs mod." Overwrite semantics are whole-key replacement, matching the
engine, never a field-level merge. Gigastructures gets a commit-pinned mechanism because its
`Live-Branch` is confirmed to track the Workshop release reliably; ACOT/AoT stay manual-Workshop
because their repos are not confirmed reliable — don't "fix" that asymmetry by pinning them
without first re-establishing reliability. `tools/collect_vanilla.py` doesn't yet implement any
GitHub fetch/pin — see Open items.

Required directories per source: `common/technology`, `common/scripted_variables`,
`common/scripted_triggers`, `common/ascension_perks`, `common/inline_scripts`,
`localisation/english`, `gfx/interface/icons/technologies`, `gfx/interface/icons/ascension_perks`
(the two icon directories are separate — ascension-perk icons aren't filed under `technologies/`
in any source). Adding a gate kind outside these two means adding its own directory the same way.

**Canonical technology count: use 1,879** (distinct technology keys after overwrite resolution)
for any size/node-count estimate — never 1,904 (raw pre-resolution occurrences), 2,122 (icon
candidates), or 1,878 (a retired, unrecoverable-provenance figure). Full reconciliation:
`docs/BUILD-LOG.md`.

## Locked decisions

Full reasoning and every measured figure for all of the below: `docs/BUILD-LOG.md`. Spec pointers
that are themselves stale or thin are flagged inline — do not assume the spec file is current
just because it's named here.

- **Empire model**: three independent axes (gestalt/authority: regular/hive/machine; shipset:
  mechanical/biological; nomadic: yes/no) = 12 profiles, composed at build time, never a flat
  enumeration. Origins are not an axis. — D-6, `spec/P-01-empire-types.md`. **D-6's staleness is
  now fixed** (a later session): `spec/decisions.md`'s own D-6 entry previously still stated the
  pre-correction "ascension perks are gates, not profile facts" rule with no axis-lock exception;
  it now states the correction below directly, so this flag no longer applies.
- **Ascension perks are gates, not profile facts — with a correction.** WHICH perk a player
  chooses is always a free choice, never a profile fact — a perk-gated technology always displays
  its gate. WHETHER a perk is obtainable at all for an empire type IS a real fact when the perk's
  own `potential` carries a genuine axis constraint (21 of the corpus's perks are cleanly
  axis-restricted) — that technology is genuinely LOCKED for an axis-excluded profile, not merely
  gated. Automated via `pipeline.availability.set_perk_potentials`; a real cross-perk cycle
  (`ap_defender_of_the_galaxy` ↔ `_nomads`) is broken by a recursion guard.
- **Scope of ACOT/AoT: depth-1 closure, not full transitive closure.** Vanilla/Gigastructures
  render unconditionally; an ACOT/AoT technology renders only when a rendered technology names it
  *directly* in `prerequisites` — no recursion. Build-time only, no user-facing toggle. — D-18.
  A technology whose `potential` is a top-level literal `always = no` is excluded from rendering
  entirely (4 real cases) — same section, D-18.
  Rendering scope (profile-invariant) is a **separate computation** from per-profile structural
  reachability (checked over all three edge kinds) — conflating them wrongly locks a node a
  `potential-gate`/`alternative` edge actually reaches. — P-16.
- **Prerequisites**: no "primary prerequisite" — a flat list, all equally required, ordered
  deterministically by tier/cost/key. Also extracted from `has_technology` inside `potential`
  (universal, `potential`-only). Nested `OR` inside `prerequisites` is the `alternative` edge kind,
  each group carrying its own `groupId`. Edge-kind membership is NOT mutually exclusive per
  `(from, to)` pair (4 real corpus pairs are both `prerequisite` and `potential-gate`). — D-2,
  `spec/P-14-unconventional-prereqs.md`.
- **Trigger evaluation**: three-valued Kleene evaluation (`true`/`false`/`unknown`) over empire
  profile facts (`pipeline/availability.py`); `unknown` always propagates, never assumed either
  way. Output is always `(technology, profile) → {state, reason}`, `state ∈
  {available, locked, uncertain, config-gated, weight-gated}` — never a boolean. — D-10, P-13.
  D-10 splits into **profile-dependent uncertainty** (10% hard ceiling per profile, 3% warn,
  ratchet against the prior dataset) and **unconditional uncertainty** (uncertain identically
  under all 12 profiles — its own ratchet, NOT subject to the 10% ceiling). A zero-factor
  `weight_modifier` condition is folded into this evaluation too, not treated as a pure weight
  concern — see "Research weight" below, and note `weight-gated` (unlike `uncertain`) is NOT
  subject to either half of this ceiling. Current corpus figures and the full leaf-resolution
  table (which flag names/leaf keys resolve and why): `docs/BUILD-LOG.md`.
- **Gates** (`pipeline/gate_patterns.py`): classifies registered trigger patterns
  (`ascension_perk`, `origin`, `ethics_or_civic`, `technology`) into the schema's `Gate` shape,
  layered on P-14's universal `potential-gate` edge extraction — curation is at the MECHANISM
  level (once a pattern is registered, every occurrence badges), never per-technology. D-3
  priority order: ascension perk > origin > ethics-or-civic > technology (index 0 is the card's
  primary gate). Gates propagate down `prerequisite` chains (not `potential-gate` — see Open
  items), tagged `inherited`/`sourceTechnologyId`. A dangling `alternative` gate (no other visible
  gate badge in its own OR-group, checked per-`groupId` not just whole-list) downgrades to a
  plain "Needs X". **A zero-factor `weight_modifier` condition (see Research weight below) that
  classifies to a registered pattern is a SECOND gate source** (`classify_weight_gate_condition`,
  polarity NOT filtered — unlike `potential`, a condition and its negation name the same fact from
  opposite sides), deduped by `(kind, refId)` against a `potential`-derived match, merged before
  D-3 sorting. — **`spec/P-03-gates.md` now documents the weight-condition addition; the REST of
  the mechanism is still undocumented there — flagged, see report.** Full detail and current
  totals (274 direct / 643 total gate instances): `docs/BUILD-LOG.md`.
- **Tiers**: unbounded range (ACOT reaches T9+) — enumerate bands from the data, no fixed upper
  bound anywhere. A node's band is its own declared `tier` field, never adjusted by graph depth,
  with one exception: repeatables band into the terminal Repeatables band regardless of tier.
  Computed longest-path position is internal geometry only (horizontal ordering, backward-edge
  routing signal), never displayed. Within a shared depth slot, zero-cost technologies sort left
  of costed ones. Backward edges are real and expected (34 of 977: 25 prerequisite + 2
  alternative + 7 potential-gate); `potential-gate` backward routing past 1-2 bands is
  `TODO(Stage 3)`. — D-13, `spec/P-08-connectors.md`.
- **Colour and pattern**: colour/pattern encode the ROW (area-coloured chip on a category row,
  faction colour/pattern as row backing on a faction row), cards themselves neutral dark — area is
  deliberately NOT colour-encoded inside a faction row (an accepted loss). Card outline encodes
  area unless rare/dangerous (dangerous outranks rare; both = 45° split outline), unaffected by
  the row re-axis. Colour is never the sole carrier — rare/dangerous also get a badge. LOD
  shedding sequence and exact hex values: `spec/S-03-tier-differentiation.md`, `tokens/`. — D-16.
- **Repeatables**: shown as `Repeatable: ×N` or `×∞`. Cost display is base `cost` (primary) +
  `costPerLevel` (secondary), never `costPerLevel` alone. A literal zero cost and an unresolvable
  (`null`) cost both render NO cost panel, card and popup alike — the distinction is meaningless
  to an end user. Membership is "source declares a `levels` field at all" (88 nodes), not
  "`levels` is negative" (which misses 12 finite-level repeatables). Sink property: every
  prerequisite edge touching a repeatable node runs non-repeatable → repeatable, never the other
  direction. — D-13, `spec/P-02-layout.md`.
- **Repository links**: three branches, always populated, never dead. Gigastructures gets a
  commit-pinned permalink; ACOT/AoT link to the mod's Workshop page; otherwise a Stellaris wiki
  link, CI-validated with a search-URL fallback. — D-5.
- **Research weight**: base weight prominently, expandable modifier list beneath, no evaluated
  weight (static analysis can't produce a trustworthy number). **Extension, corrected (a later
  session)**: a `weight_modifier` entry whose own `factor` is a literal `0` IS an availability
  fact, not a pure weight concern — Stellaris's own idiom for "cannot currently be drawn as a
  research option at all." Folded into the same evaluator as `potential`
  (`pipeline.availability._apply_weight_gate`), but LOCKED is now narrower than a bare firing
  condition: only a genuine empire-TYPE fact (an axis leaf, or an axis-restricted ascension perk)
  may produce LOCKED, since a static evaluator can't see `give_technology`/event/special-project/
  archaeology/relic routes that bypass the weighted draw entirely (confirmed real:
  `tech_akx_worm_1`'s permanent `always = yes` is granted through a guaranteed event chain
  regardless). Everything else that fires or can't be resolved (circumstantial state, opaque
  leaves, `always`, an unrestricted perk) downgrades to the fifth `AvailabilityState`,
  `weight-gated` — "not currently offered in the draw," never `locked`, and NOT subject to D-10's
  uncertainty ceiling. **Weight-condition gate extraction (a later session)**: a zero-factor
  condition that classifies to a registered gate pattern (see Gates above) is EXCLUDED from
  producing `weight-gated` for that condition — it badges the card as a `Gate` instead — but its
  axis-pure-LOCKED branch is unaffected, still a real `locked` when the gate's own target is
  axis-unobtainable. `weight-gated` population: 1,636 pairs/163 technologies → 850/85; freed pairs
  move to `available`. **Suppression (Item 1, a later session)**: six reviewed, mechanism-level
  entries in `config/weight_gate_suppressions.txt` resolve a trivially-satisfied leaf (`years_
  passed`/`num_owned_planets`/`num_communications` below a small threshold; `any_owned_nonprimary_
  starbase`, `any_planet_within_border`, and `has_country_flag` `_found`-suffix resource-discovery
  flags) to a fixed constant — never the `EXCLUDED` identity element, which is unsound once such a
  leaf sits AND-combined with a real axis fact (`docs/DEFECTS.md`'s "EXCLUDED-as-vacuously-
  satisfied" class). `weight-gated`: 1,090/106 → 900/89 (−190 pairs, all ex-UNKNOWN, all move to
  `available`). **Copy split (Item 2)**: `weight-gated`'s description now varies by resolution —
  a condition resolving definitely TRUE states the modifier IS firing; UNKNOWN gets softer "MAY
  not be offered" phrasing; the unconditional bare-`factor=0` case keeps its original neutral
  wording. Of the 900 remaining pairs: 120 TRUE, 516 UNKNOWN, 240 unconditional, 24 `always=yes`.
  — D-4, D-10's Extension in `spec/decisions.md`.
- **Research path** (P-12.9, `spec/P-12.9-research-path.md`): `researchPaths[technologyId]` per
  profile, precomputed at build time — never recomputed in the browser. `status` is `"path"`,
  `"config-gated"` (target is one of the 50 `giga_tech_repeatable_*_cap` technologies, own cost
  excluded from `totalCost`), `"unavailable"` (target itself is `locked`), or `"blocked"` (target
  is fine, but a real ancestor in its chain is `locked`/`config-gated` — `blockedBy` names it).
  `"unavailable"` and `"blocked"` are deliberately different statuses. An `alternative` group
  resolves to the cheapest FULL recursive closure cost, never just its own declared cost.
  `totalCost` for `"path"` includes the target's own cost; `"config-gated"` excludes it.
- **Localisation**: English only for v1; the pipeline is language-parameterised, more languages
  are a build flag.

## Rules

- Work is committed at the end of every session, in logical groups (pipeline, client,
  spec/docs, tests kept as separate commits where the diff supports it), never left staged.
  Bisectability is this project's only defence against a regression whose cause spans
  sessions — it has already been lost once to accumulated uncommitted work across many
  sessions, and drifted back into the same state after a prior fix. Do not defer this to "a
  later cleanup session."
- Zero technology data is hand-authored. The only hand-maintained files are config: empire
  profiles, gate patterns, `config/crisis_faction_overrides.txt` (D-7's step-3 fallback, seeded
  empty — see `pipeline/crisis_faction.py`), `config/overwrite_overrides.txt`,
  `config/icon_overrides.txt` (a technology/swap referencing an icon its upstream source never
  shipped — never a silent fallback, always a reviewed, justified entry), `config/
  lock_reason_overrides.txt` (P-13's lock-reason override table — used when a locked technology's
  reason string can't be derived automatically from its trigger; `pipeline/availability.py`'s
  `needs_lock_reason_override`/`build_missing_lock_reason_overrides` warn when an override is
  missing; seeded empty — the real corpus currently has no case that needs one),
  `config/weight_gate_suppressions.txt` (Item 1 — mechanism-level, reviewed suppression of
  trivially-satisfied zero-factor `weight_modifier` conditions; see "Research weight" below), mod
  metadata.
- The build fails rather than emitting a partial dataset. Fail on parse errors, graph cycles,
  dangling references, missing localisation for displayed strings, missing icons, schema
  violations, dead repository links.
- All shareable state goes in the URL: empire type, filters, search, open popup.
- No runtime re-layout. Filtering, search and isolation are visibility masks.
- Every hover behaviour needs a tap or press equivalent. Pointer Events only — no separate
  mouse and touch code paths.
- Icon atlases must pack deterministically. Unchanged icons produce byte-identical output.
- When surveying corpus content (vendor/, fixtures) to verify a syntax claim, inspect raw bytes
  or raw text — `grep`/`sed`/`xxd`/direct file reads. Never conclude anything about source
  syntax from output that passed through `repr()`, `pprint`, or any formatter that can add,
  strip or transform delimiters (Python's `repr()` wraps plain strings in quotes; that is the
  formatter's choice, not evidence the source had quotes). A single misread `repr()` output
  once produced a false "single-quoted strings exist in scripted_variables/" finding that led
  to a tokeniser change with zero actual evidentiary basis — caught only because the fixture
  built to test it was checked against the raw file.
- The Clausewitz AST has a standing round-trip check (`pipeline/clausewitz/roundtrip.py`,
  wired in by `tests/clausewitz/test_roundtrip*.py`): a naive serialiser walks the AST back to
  text and the result is compared against the source, catching parses that succeed but build the
  wrong AST — a strictly stronger claim than "every fixture parses without raising." Inter-token
  adjacency (whether any whitespace separated two tokens, not its quantity or kind) is
  deliberately significant in that comparison, not normalised away — it is the one signal that
  can catch a tokeniser silently merging or splitting a token, which is exactly the bug class two
  real, previously-shipped corruptions belonged to. A comparator that reconstructs adjacency by
  asking the tokeniser itself whether a pair could lex differently does not work, because it
  consults the same tool that's under test. Round-trip mismatches are never silently normalised
  away to make a build green: each is reviewed, and only a reviewed, adjacency-only,
  cannot-lex-differently mismatch is added to the checked-in `tests/clausewitz/
  roundtrip_allowlist.json` — read that file before touching it.
- **The pipeline owns all geometry; the renderer consumes emitted positions and never recomputes
  them from a parallel formula.** Two independent implementations of the same geometry will drift
  the moment either one changes — found the hard way once (a headless-screenshot-only bug, no
  failing test). Full account: `docs/DEFECTS.md`'s "Parallel geometry" section.
- **A dict key missing a discriminator field can silently sum unrelated data across a
  band-relative index** — a second, different defect class than the one above that produced the
  same visible symptom (rows overlapping); don't conflate them. Full account: `docs/DEFECTS.md`'s
  "Dict-keying" section.
- **A passing test suite proves self-consistency, not correctness** — this project has hit that
  lesson from three independent root causes. Full account: `docs/DEFECTS.md`'s "green-suite"
  section.
- **An identity element sound for one caller is not sound for a different question asked of the
  same evaluator** — `EXCLUDED`'s "presume open" default is correct for `potential` (a player
  CHOICE question) and unsound for a `weight_modifier` zero-factor condition (an "is this
  currently drawn" question); reusing it there silently laundered an unresolvable condition into a
  false definite LOCKED. Full account: `docs/DEFECTS.md`'s "EXCLUDED-as-vacuously-satisfied"
  section.

## Commands

    python tools/collect_vanilla.py     # populate vendor/ from the local Steam install
    python tools/regenerate_fixtures.py # reproduce tests/fixtures/ from vendor/ (needs vendor/ populated)
    python tools/build_dataset.py       # build the real dataset into client/public/dataset/ (needs vendor/ populated)
    pip install -e ".[dev]"             # install the pipeline package + pytest
    pytest                              # run the pipeline test suite

    cd client && npm install            # install the Stage 3 client toolchain (Node pinned via client/.nvmrc)
    npm run dev                         # Vite dev server
    npm run typecheck                   # tsc --noEmit
    npm run build                       # tsc --noEmit && vite build -> client/dist/ (needs client/public/dataset/ built first)

    bash tools/deploy_local.sh          # D-15: build dataset + client, publish dist.zip as a GitHub Release (needs `gh` auth'd, vendor/ populated)

CI: `.github/workflows/typecheck.yml` (`tsc --noEmit` on every `client/**`/dataset-types.ts
change). `.github/workflows/deploy.yml` is `workflow_dispatch`-only — downloads a pre-built
`dist.zip` from a GitHub Release and deploys it; builds nothing. `tools/build_dataset.py` never
runs in CI (D-15: vanilla is a permanent CI blocker). No pipeline-test CI workflow exists yet.

## Open items

Full reasoning/figures for every item below: `docs/BUILD-LOG.md`. Remove an item entirely when
resolved — never leave a struck-through placeholder.

- **Wilderness/Frameworld as toggles over the 12 profiles**: surveyed, not implemented — real
  decision needed. Recommendation given (implement): scale is real (54/8 technologies), payload
  cost is negligible (+4.8 KB gzip), `EmpireProfileIndex` extends cleanly to a 3-state axis,
  neither has a vendored icon.
- **Middle-click isolation (P-7)** is fully specced and entirely unbuilt.
- **No pipeline-test CI workflow exists** — `pytest` runs manually/locally only.
- **`tools/collect_vanilla.py`'s GitHub-fetch-and-pin automation for Gigastructures** is still
  unbuilt — the current manual pin is a deliberate stopgap.
- **Blokkats pattern tile** needs tracing to clean SVG from the supplied flag image.
- **Sirenalia's accent shade and Katzenartig's chevron pattern** are both flagged provisional in
  `client/src/tokens.ts`.
- **`potential-gate` edges' long-span backward routing (up to 5 bands)** was left `TODO(Stage 3)`
  — re-check whether the v1-style router has since made this moot.
- **ΔE2000/WCAG mechanical colour checks** are still unbuilt.
- **`repositoryLink` isn't live-validated** (no network access at build time).
- **Gate propagation down `potential-gate` edges** is a deliberately deferred scope boundary
  (propagation currently covers `prerequisite` edges only).
- **Looping edges**: surveyed twice, none found geometrically — if reported again, ask for a
  screenshot or a specific technology name.
- **Hover vs. selection scope discoverability**: the split (hover = neighbours, selection = full
  closure) is correct but undiscoverable in the UI — a cheap, optional follow-up.
- **Two technologies named "Confluence of Thought"** are a known, genuine same-name pair (a
  hive/wilderness parallel content pair), not a bug.
