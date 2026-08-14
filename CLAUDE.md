# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Gigastructural Engineering Tech Tree

Interactive tech tree visualiser for the Stellaris mod *Gigastructural Engineering & More*.
Static client-side site, deployed to GitHub Pages. No backend, ever.

The normative requirements live in `spec/`. This file is a **summary** of `spec/`, kept here so
settled decisions aren't re-litigated. `spec/` is authoritative — if this file conflicts with
`spec/`, `spec/` wins; fix this file to match, don't amend the spec to match this file.

**Whenever a decision in `spec/` changes, re-check and update this file in the same session.**
A changed requirement, resolution, or renamed concept in `spec/` that has a summary here (empire
model, ACOT/AoT scope, prerequisites, trigger evaluation, tiers, colour and pattern, repeatables,
repository links, research weight/path, localisation, the rules below) is stale the moment
`spec/` changes, and stale project memory is worse than no memory — don't defer the sync to a
later session or a separate pass.

## Architecture

Three stages, and the boundary between them is load-bearing:

1. **Extract** (Python, CI) — parse Clausewitz script and localisation into a lossless AST.
2. **Compute** (Python, CI) — resolve overwrites, build the DAG, evaluate triggers per
   empire profile, assign tiers and columns, route edges, emit the dataset.
3. **Render** (TypeScript + PixiJS, browser) — load the dataset and draw it.

The browser never parses Clausewitz script and never computes layout. Both are build-time
concerns. Runtime does visibility masking over fixed geometry, nothing more.

The dataset schema is a cross-language contract. It lives as JSON Schema in `schema/`,
TypeScript types are generated from it, and the Python output is validated against it in CI.
Do not let the two sides drift by hand-editing either end.

## Stack

- Pipeline: Python
- Client: TypeScript, PixiJS (WebGL canvas) with a DOM overlay for popups and controls
- Dataset: JSON for structure, typed-array side-files for geometry
- Host: GitHub Pages, deployed from the default branch
- CI: GitHub Actions

## Source data

Not committed. Lives in gitignored `vendor/`, populated by `tools/collect_vanilla.py`.

| Source | Version | Update path |
| --- | --- | --- |
| Stellaris base game | 4.5 | manual, re-run the collector |
| Gigastructural Engineering | pinned commit | automated, scheduled CI check |
| Ancient Cache of Technologies (ACOT) | manual | manual, Steam Workshop only |
| Acquisition of Technology (AoT) | manual | manual, Steam Workshop only |

**ACOT and AoT are Steam Workshop only.** They cannot be fetched or pinned to a commit, so
the scheduled upstream sync covers Gigastructures alone. Their versions are recorded by hand
in dataset metadata. The collector hashes each vendored tree so CI can at least detect that a
local copy changed. AoT depends on ACOT.

Load order, lowest to highest: vanilla, Gigastructures, ACOT, AoT. Treat this as an ordered
list of sources. Do not special-case "vanilla" and "mod" in resolution logic. Overwrite
semantics are whole-key replacement, matching the engine — never a field-level merge.

Required directories, per source (spec/00-overview.md is authoritative — this is a pointer, not
a copy): `common/technology`, `common/scripted_variables`, `common/scripted_triggers`,
`common/ascension_perks`, `common/inline_scripts`, `localisation/english`,
`gfx/interface/icons/technologies`, `gfx/interface/icons/ascension_perks`. The two icon
directories are separate because ascension perk icons (P-3's gates) are not filed under
`technologies/` in any source — a directory list naming only `technologies/` cannot satisfy
P-3's "every gate renders its icon as an image, path never manually maintained" requirement.
Adding a gate kind outside ascension perks and technologies means adding its own directory here
the same way, not inferring a location from a pattern.

## Locked decisions

### Empire model

Three independent axes, composed at build time. Never a flat enumeration.

- Gestalt/authority: regular, hive mind, machine intelligence
- Shipset: mechanical, biological
- Nomadic: yes, no

Twelve profiles. Origins are not an axis for v1, but the fact registry is extensible — if
origin-gated techs turn up during extraction, add a fact, do not restructure.

**Ascension perks are gates, not profile facts.** A perk-gated tech always displays its gate.
The tree shows what you would need; it never assumes you have it.

### Scope of ACOT and AoT

The tree renders vanilla and Gigastructures technologies unconditionally. ACOT and AoT
technologies are rendered only where they fall in the **rendering-scope closure** of a rendered
technology — `prerequisite` edges only, pooled across all twelve profiles — so a rendered
technology's prerequisite chain is never broken by an invisible gap. An ACOT/AoT technology with
no rendered descendant is not emitted as a node. This is a build-time computation, not a
user-facing filter — there is no checkbox and no mod-set URL state. Mod requirement is a
`requiresMods: string[]` field rendered as a card badge (`ACOT`, `AoT`) — distinct from gates and
from prerequisites — that communicates the requirement without toggling visibility.

Rendering scope is a separate computation from **per-profile structural reachability**: because
the closure above is profile-invariant, a node reachable via only one profile's tech-swap chain
still renders for all twelve. For the other eleven, a second check — over *all three* edge kinds
(`prerequisite`, `potential-gate`, `alternative`), never just `prerequisite` — decides whether the
node is actually reachable for that profile; if not, it renders locked with a structure-derived
reason. Conflating the two checks is a correctness bug: it wrongly locks a node that a
`potential-gate` or `alternative` edge actually reaches for that profile. See P-16.

### Prerequisites

There is no "primary prerequisite". Multiple prerequisites are all equally required. The data
model carries a flat list, ordered deterministically by tier, then cost, then key.

Dependencies must also be extracted from `has_technology` checks inside `potential` and other
trigger blocks, not just `prerequisites` blocks. Preserve boolean structure — a `has_technology`
inside a `NOT` is a negative dependency and flattening it produces a wrong graph. Edges are
typed and conditional: `{ from, to, kind, appliesToEmpireTypes }`.

### Trigger evaluation

Partial evaluation against empire profile facts. Every condition resolves to `true`, `false`,
or `unknown`. `unknown` propagates. Never assume `unknown` means available or unavailable.

- Hard ceiling: 10% of techs may resolve to `unknown`. Above that, the build fails.
- Warn threshold: 3%.
- Ratchet: CI fails if the `unknown` count rises against the previous dataset, even under 10%.

`common/scripted_triggers/` is the single biggest lever on this number. Unresolvable scripted
trigger calls are the main source of spurious `unknown`.

### Tiers

Tier range is **not** bounded. ACOT pushes tiers to T9 and beyond. Enumerate tier bands from
the data. No fixed upper bound anywhere in layout, LOD, or band labelling.

Tier determines the band; longest-path depth determines ordering. If a tech's declared tier is
at or below a prerequisite's, promote it to `max(prereq columns) + 1` and warn.

### Colour and pattern

Background encodes research area. Outline encodes research area unless the tech is rare or
dangerous, in which case that takes priority. Dangerous outranks rare. A tech that is both gets
a 45° split outline, dangerous red on the top-left half.

Colour is never the sole carrier. Rare and dangerous each also get a card badge. The LOD shedding
sequence is one shared table (spec/S-03): gate label and repeatable shed first (<60% zoom), then
rare (<35%), then gate icon and tier badge (<20%), then dangerous last of the badges (<10%,
deliberately kept longest since it's safety-critical), then crisis patterns go solid (<7%), then
the node reduces to a flat coloured block (<5%). Rare and dangerous do **not** shed together, and
neither sheds "at the same threshold as the gate label" — see spec/S-03 for the authoritative
table rather than restating specific thresholds here.

Crisis factions: Aeternum, Blokkats, Compound, Sirenalia, Katzenartig Imperium. Faction
assignment is derived from tech ID, then from `potential`/prerequisites, then from a checked-in
manual override file for the remainder.

Exact hex values live in `tokens/` as the single source of truth, consumed by node rendering
and connector rendering alike. Do not hardcode colours in components.

Palette signed off: Aeternum `#823269`; Blokkats node fill `#2A6B2A` with pattern stroke
`#63A85C` (`#1C451C`, the authentic flag colour, reserved for tier-band/lane backing, not node
fill); Compound `#2F137F`; Sirenalia `#B0338C` with high-contrast sweeping bands; Katzenartig
`#2E3F98` with `#CC9429`.

### Repeatables

Shown on the card and in the popup as `Repeatable: ×40`, or `Repeatable: ∞` when unbounded.

### Repository links

Three branches, always populated, never dead. Gigastructures permalink pinned to the build
commit, targeting file and line range, where an override exists. ACOT/AoT-sourced technologies
link to that mod's Steam Workshop item page (no commit-pinned permalink is possible for a
Workshop item, and it isn't vanilla either). Otherwise a Stellaris wiki link. CI validates that
wiki anchors resolve and falls back to a wiki search URL where they do not.

### Research weight

Base weight prominently, expandable modifier list beneath. No evaluated weight — static analysis
cannot produce a number that is right often enough to present authoritatively.

### Research path

Complete ancestor set in tier order with cumulative cost, plus a "shortest chain" toggle.
Computed per empire profile at build time. Never substitute swaps in the browser: swaps change
the shape of the chain, not just its labels.

### Localisation

English only for v1. The pipeline is language-parameterised so more languages are a build flag.

## Rules

- Zero technology data is hand-authored. The only hand-maintained files are config: empire
  profiles, gate patterns, crisis classification overrides, overwrite overrides,
  `config/icon_overrides.txt` (a technology/swap referencing an icon its upstream source never
  shipped — never a silent fallback, always a reviewed, justified entry), the P-13 lock-reason
  override table (used when a locked technology's reason string can't be derived automatically
  from its trigger; the build warns when an override is missing), mod metadata.
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

## Commands

    python tools/collect_vanilla.py     # populate vendor/ from the local Steam install
    python tools/regenerate_fixtures.py # reproduce tests/fixtures/ from vendor/ (needs vendor/ populated)
    pip install -e ".[dev]"             # install the pipeline package + pytest
    pytest                              # run the pipeline test suite

*(Extract/Compute pipeline commands beyond the Clausewitz parser — dataset build, CI entry
points — to be filled in as they land.)*

## Open items

- Pattern tile for Blokkats needs tracing to clean SVG from the supplied flag image.
- **Stage 1 (Extract) is complete**, and the dataset schema — the cross-language contract Stage 2
  and Stage 3 both build against — is now written. See HANDOFF.md for the full picture.
  `pipeline/clausewitz/` (tokeniser + recursive-descent parser, lossless AST, plus a round-trip
  serialiser and corruption detector — see the Rules section) is built and green against every
  fixture in `tests/fixtures/`. `pipeline/variables.py` (`@variable` resolution),
  `pipeline/inline_scripts.py` (`inline_script` expansion), `pipeline/localisation/` (hand-written
  parser for the YAML-*like* localisation format — not YAML, see the Rules section), and
  `pipeline/icons/` (technology/ascension-perk icon resolution, DDS decode, deterministic,
  size-capped atlas packing — see the Rules section) are all built, each with its own test module
  (`tests/test_variables.py`, `tests/test_inline_scripts.py`, `tests/localisation/`,
  `tests/icons/`).
- **`schema/`** carries the JSON Schema for all five dataset artefacts (base dataset, empire
  overlay, detail payload, search index, diagnostics — see "Dataset structure" above and
  `spec/implementation-notes.md`'s Stage 2 section for the full field assignment).
  `schema/generated/dataset-types.ts` is generated from it by
  `tools/generate_typescript_types.py` (hand-written in Python — no Node/npm toolchain in this
  environment, and D-12 already commits the pipeline to Python end to end) and checked in;
  `tests/schema/test_typescript_drift.py` re-runs the generator and fails if the checked-in copy
  doesn't match, so the two sides of the contract can't drift by hand-editing either end.
  `pipeline/dataset_schema/` validates Python-side output against the schema (structural
  validation, then a separate `schemaVersion`-support check — see
  `UnsupportedSchemaVersionError`) and owns the canonical `EmpireProfileIndex` derivation
  (`pipeline/dataset_schema/empire_profile.py`, strides derived from axis cardinalities at import
  time, never hardcoded, with an import-time bijection assertion) plus the
  `availabilityMatrix`/overlay consistency check. `tests/schema/` covers a minimal valid document
  per artefact and the four required rejection shapes (unsupported version, missing required
  field, invalid edge kind, boolean-where-three-state).
  **TODO(Stage 3):** `schema/generated/dataset-types.ts` has never actually been typechecked —
  there is no Node/npm in this environment, so `tests/schema/test_typescript_drift.py` only
  proves the checked-in file matches a fresh generator run, not that the output compiles. Add a
  `tsc --noEmit` CI step over it when the Node toolchain lands with the PixiJS renderer (see
  `tools/generate_typescript_types.py`'s own `TODO(Stage 3)` for the same note).
- One remaining Stage 2 handoff, recorded as a `TODO(Stage 2)` in `pipeline/icons/resolve.py`:
  the atlas currently packs every resolvable icon across all four sources unconditionally,
  including ACOT/AoT content outside the prerequisite-edge closure that P-16 actually renders —
  so its current byte size is measured over a superset, not the real one. **Settled, not open:**
  icon atlas bytes are excluded from P-10's ≤2 MB base-dataset budget (P-9/`implementation-notes`
  require lazy icon loading; P-10's budget is defined as the base dataset's compressed transfer
  size specifically) — atlases instead have their own proposed 12 MB combined-bytes cap
  (`pipeline/icons/pack.py`'s `MAX_TOTAL_ATLAS_BYTES`, currently measuring ~8.65 MB unfiltered;
  revisit once the P-16 closure exists and the real, smaller figure is known). The other
  `TODO(Stage 2)` from the icon pipeline — 19 technology/swap and 6 ascension-perk candidates
  recorded as unresolved diagnostics, uninterpreted, deferring the diagnostic-vs-failure decision
  to the partial trigger evaluator — still stands. Not yet built: overwrite resolution, DAG
  build, trigger evaluation, tier/column/edge computation, dataset emission — the rest of
  Stage 2, now with a schema to emit into.
