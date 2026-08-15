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
| Gigastructural Engineering | pinned commit | GitHub, `Live-Branch`, currently unautomated (see below) |
| Ancient Cache of Technologies (ACOT) | manual | manual, Steam Workshop only |
| Acquisition of Technology (AoT) | manual | manual, Steam Workshop only |

**Gigastructures target and mechanism are two separate questions — don't conflate them.**
The *target* is the released mod (what players run), not unreleased dev work. The
*mechanism* is a pinned commit on GitHub's `Live-Branch`
(`Pouchkinn-s-Gigastructures/Gigastructures`), confirmed to match the Steam Workshop upload
in content relevant to this tool — a commit hash is precise, fetchable, and reproducible in
a way a locally-mounted Workshop directory's provenance is not. If `Live-Branch` ever
diverges from the Workshop release, follow the release and re-pin the commit; do not track
HEAD unconditionally. Currently vendored: commit `0f1f2b024f43249dc7dfe132fe7c0e4201398ef5`
(tag `v3.39.3`), recorded in `vendor/manifest.json` alongside the existing content hash.
**ACOT and AoT remain Steam Workshop only, asymmetrically — and the reason is repo
reliability, not repo absence.** Both have source repos; neither is pinned against, because
ACOT's is not well maintained and AoT's carries the same risk (its repo tracks ACOT's, so an
unreliable ACOT repo makes AoT's no more trustworthy to pin against). Gigastructures gets the
stronger mechanism because its `Live-Branch` is confirmed to track the Workshop release
reliably — not because it's the only one of the three that happens to publish a repo at all.
**Do not "fix" this asymmetry by pinning ACOT or AoT to their repos** without first
re-establishing that those repos are reliable enough to track — the current manual Workshop
mechanism is the deliberate choice, not a placeholder waiting to be replaced. Their versions
are recorded by hand in dataset metadata. AoT depends on ACOT.

**Open item, not yet built**: `tools/collect_vanilla.py` does not implement any of this —
it currently collects all three mods identically, from local Steam Workshop directories
keyed by `workshop_id`, with no GitHub fetch and no commit pinning. The commit above was
pinned manually (`git clone` + `rsync` into `vendor/mods/gigastructures/`, hash and commit
recorded in `vendor/manifest.json`) to make the gap visible and the snapshot reproducible in
the meantime. Building an actual GitHub-fetch-and-pin path (plus the scheduled CI check that
reports how far behind the vendored snapshot is, as a warning not a blocker) is still open.

Load order, lowest to highest: vanilla, Gigastructures, ACOT, AoT. Treat this as an ordered
list of sources. Do not special-case "vanilla" and "mod" in resolution logic. Overwrite
semantics are whole-key replacement, matching the engine — never a field-level merge.

Surveyed, not assumed: Gigastructures redefines exactly **two** vanilla `common/technology`
blocks (`tech_ring_world`, `tech_mega_engineering`, both in `zz_giga_tech_overwrites.txt`),
and nothing else — checked and ruled out for Gigastructures-over-vanilla specifically: no
`@scripted_variable` indirect override of a vanilla-referenced variable, no `technology_swap`
appropriating a vanilla key. Overwriting between mods is a much bigger surface: 19
`acot`↔`aot` and 4 `acot`↔`stellaris` technology-block overlaps, with `aot` redefining `acot`
technologies as its dominant pattern (`aot` depends on and loads after `acot`). No 3+-source
overwrite chains exist anywhere in `common/technology`. `acot`↔`aot` scripted-variable
overwrite is real, though (14 cross-source keys, mostly component-cost variables) — a
technology's effective cost/weight can change without its own block being touched, so any
overwrite diff must resolve `@variable` references before comparing cost/weight fields.

**Canonical technology count: 1,879.** Three technology counts have been used interchangeably in
this project's notes and must not be — each counts something different, and only one is correct
for "how many technologies exist / will become nodes":

- **1,879 — distinct technology keys, canonical.** Every unique top-level `key = { ... }` name
  across `common/technology` in all four sources, after whole-key overwrite resolution collapses
  each redefined key to its one winning definition. This is the right number for "how many
  technology identities exist" and today's best available upper bound on the final rendered node
  count — it can only shrink further once P-16's rendering-scope closure exists (some ACOT/AoT
  keys outside that closure won't be emitted as nodes at all). **Use this for size estimates,
  node-count estimates, and any fixture meant to be shaped like the real dataset.**
- **1,904 — raw technology-block occurrences, pre-resolution.** Every `key = { ... }` block
  parsed, counting an overwritten key once per source that defines it (25 keys are defined twice,
  matching the 25 confirmed technology-block overwrites — see below — so 1,879 + 25 = 1,904). Not
  a node count: an overwritten-away definition merges into its winner's single node, it doesn't
  become a second one. Useful only for overwrite-resolution bookkeeping, never for size/count
  estimates.
- **2,122 — technology icon *candidates*, a different concept entirely.** `pipeline/icons/`'s
  candidate count: the 1,904 raw occurrences above, plus 218 `technology_swap` sub-block
  alternates (1,904 + 218 = 2,122). A swap alternate is per-empire-profile display data on an
  *existing* node's card, never a separate node. Correct for icon-atlas sizing; wrong for
  anything answering "how many technologies."
- **1,878 — retired.** Appeared in earlier size estimates and the deploy-spike fixture; its exact
  derivation was never preserved and could not be reconstructed, but it does not match any of the
  three real quantities above — treat any figure still citing 1,878 as stale and correct it to
  1,879 (or whichever of the three above is actually meant) on sight.

If a fourth technology count ever shows up, work out which of these three concepts it actually
is before recording it anywhere — do not add a fourth number to the set without first mapping it
onto raw-occurrences, icon-candidates, or canonical.

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

Corpus confirmation, not a to-do: vanilla's `tech_mega_engineering` (also overwritten by
Gigastructures — see `### Prerequisites`) carries `is_nomadic = yes`-gated weight modifiers
mirroring its non-nomadic starhold/citadel starbase-count modifiers 1:1 (waystation tiers 2
and 3 in place of starhold/citadel). Direct evidence the nomadic axis affects research
weight, and therefore research path — relevant to `EmpireTypeConstraint` and P-12.9.

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

Dependencies must also be extracted from `has_technology` checks inside a `potential` block,
universally (`potential`-only — checked against the real corpus, not "and other trigger blocks"
as an earlier draft assumed; `allow` never occurs on a rendered technology, and
`weight_modifier`/`ai_weight` contribute zero occurrences once scoped correctly — see P-14's
"Implied technical decisions" for the full corpus finding). Preserve boolean structure — a
`has_technology` inside a `NOT` is a negative dependency; the real corpus has zero such
occurrences under `potential` today, and one is excluded from edge output and diagnosed rather
than emitted as a wrong-polarity edge, since flattening/inverting it silently would produce a
wrong graph. Edges are typed and conditional:
`{ from, to, kind, groupId, appliesToEmpireTypes, backward, bandSpan }`.

**Nested `OR` inside a `prerequisites` block (the `alternative` edge kind) is real and common in
the corpus — 35 confirmed `OR`-group instances (21 vanilla, 14 Gigastructures) across 32 distinct
technologies (18 vanilla, 14 Gigastructures — 3 vanilla technologies carry two independent groups
each), including vanilla's own `tech_mega_engineering`.** Corrected from an earlier, broader
claim: the real corpus contains only `OR` nested inside `prerequisites` — checked directly, not
assumed — 0 `AND`/`NOR`/`NOT` occur there. It is a distributional fact, not yet a gap, that ACOT
and AoT contain zero such instances — alternative-edge rendering is exercised only by vanilla and
Gigastructures nodes; keep that in mind when building fixtures or coverage around this edge kind.
Each `OR` group carries its own `groupId` (`Edge.groupId`, `schema/common.schema.json`) so two
independent 2-member groups on the same technology aren't indistinguishable from one 4-member
group.

**Edge-kind membership is NOT mutually exclusive per `(from, to)` pair.** 4 real corpus pairs are
both a formal `prerequisite` and a `potential-gate` (the same dependency redundantly encoded
twice, e.g. `tech_mega_engineering -> giga_tech_arkship_neutronium_harvester`). Both are emitted;
dropping either would corrupt one of the two traversals that consume that kind. Collapsing them
into one visual line for display, if ever wanted, is a Stage 3 rendering decision over the
emitted data, not a data-model decision — see `spec/P-14-unconventional-prereqs.md`.

### Trigger evaluation

Partial evaluation against empire profile facts (`pipeline/availability.py`). Every condition
resolves to `true`, `false`, or `unknown` (three-valued, Kleene-style short-circuiting through
`AND`/`OR`/`NOT`/`NOR`). `unknown` propagates. Never assume `unknown` means available or
unavailable. Output is always `(technology, empire profile) -> {state, reason}` with `state` in
`{available, locked, uncertain}` — never a boolean (D-10/P-13).

**D-10 splits into two distinct metrics, both computed over RENDERED nodes (P-16's closure —
980 at last count), not the full 1,879 canonical technologies** — see `spec/decisions.md`'s D-10
for the full reasoning; summarised:

- **Profile-dependent uncertainty** — a technology whose state varies by profile (some profiles
  short-circuit to a definite answer, others stay stuck). This is what the thresholds below
  govern, per profile, worst-case:
  - Hard ceiling: 10% for any single profile. Above that, the build fails.
  - Warn threshold: 3%, per profile.
  - Ratchet: CI fails if any individual profile's rate rises against that same profile's figure
    in the previous dataset, even under 10%.
- **Unconditional uncertainty** — a technology `uncertain` under all twelve profiles identically
  (no axis check anywhere in its trigger structure). Never misleads a user about their specific
  empire — it's the same honest "unknown" for everyone, reporting a fact outside the axis model
  (crisis-chain/story progression, mid-game player state). Published as its own
  data-completeness figure with its own regression ratchet, but **NOT subject to the 10%
  ceiling** — a different quality signal, not a weaker version of the same one.

The two denominators (all-1,879-canonical vs. rendered-980) give materially different, and
oppositely-signed, answers: rendered-only uncertainty (26.84%) is *higher* than all-canonical
(22.67%), because Gigastructures' own content — not unrendered ACOT/AoT bulk — is the
concentration point (39.00% at-risk). Narrowing ACOT/AoT rendering scope does not fix a ceiling
breach. Always state which denominator a reported rate uses.

**Documented evaluator assumptions**, applied before anything counts as uncertain (each
individually verified against the vendored corpus, not a blanket "assume everything works" —
see `pipeline/availability.py`'s module docstring and `spec/decisions.md`'s D-10 for the full
detail and the specific names each covers):

1. Mod-config content-toggle global flags (`has_global_flag` names ending `_forbidden`,
   `_disabled`, or `_OFF`) resolve to their unset default — content not forbidden. Flags outside
   that pattern (`compound_invasion_happened`, `l_cluster_opened`, `has_aot_mod`, ...) are real
   undecidable state and stay unresolved.
2. All official DLC assumed owned — covers a literal `has_dlc`/`host_has_dlc` leaf and a dozen
   named per-DLC scripted-trigger wrappers individually confirmed to be pure `host_has_dlc`
   calls. Two similarly-named triggers (`has_gigastructural_constructs`, `has_galactic_wonders`)
   were checked and found to be ascension-perk-gate checks in disguise, not DLC checks, and are
   deliberately left unresolved.
3. Not-a-fallen-empire is a ground fact of all twelve profiles (`is_fallen_empire`,
   `merg_is_fallen_empire` always resolve `no`).

`has_technology` (P-14 prerequisite-graph reachability), `has_ascension_perk` (a P-3 gate,
D-6/P-1), and `has_gigastructural_constructs`/`has_galactic_wonders` (Gigastructures' own custom
scripted_triggers, individually inspected and confirmed to be pure `OR`-of-`has_ascension_perk`
chains — ascension-perk gates wearing a different name) are excluded from boolean combination
entirely — an identity element, not resolved either way — because all four are a different
mechanism's job; folding any into `uncertain` would be a category error. `has_nemesis` and
`has_infernals` were added to the DLC-owned assumption's named-wrapper list after the same kind
of individual verification (both are bare `host_has_dlc` calls).

`common/scripted_triggers/` is the single biggest lever on the unconditional figure: this
evaluator does not inline arbitrary custom scripted-trigger call bodies (a materially larger
feature than what's built), so any technology gated behind one falls to `uncertain` regardless of
what that trigger actually checks. `has_country_flag` (131 corpus occurrences, 82 distinct names)
is confirmed to have no single resolvable pattern and is left fully unresolved.

### Tiers

Tier range is **not** bounded. ACOT pushes tiers to T9 and beyond. Enumerate tier bands from
the data. No fixed upper bound anywhere in layout, LOD, or band labelling. Measured against the
real 980-node rendered corpus: 10 declared-tier bands (T0-T9) plus the terminal Repeatables band.

**A node's band is its own declared `tier` field — never adjusted by graph depth (D-13,
corrected from an earlier draft that promoted a node's displayed position) — with one declared
exception: repeatable technologies band into the terminal Repeatables band regardless of their
own tier, and badge repeat count instead of tier on the card. See "Repeatables" below and D-13 in
`spec/decisions.md` for the full reasoning, including why this exception is not a return of v1's
band-header bug.** Tier is vanilla's and Gigastructures' own vocabulary; a band labelled "Tier 5"
contains exactly what the mod calls tier 5. Computed longest-path position still exists, but
purely as internal geometry — it orders technologies horizontally within a band's sub-grid and
gives the router a consistent signal for backwards edges, and is never displayed as a number.
**Backwards edges are consequently real and expected**: an edge in a later band than its
dependent, whenever the tail's own declared tier is higher. **Record this as a per-kind
decomposition, never a single number — it has moved three times purely through re-scoping.**
Measured over the full P-14 three-kind edge set (989 edges: 888 `prerequisite` + 76
`alternative` + 25 `potential-gate`): **34 backward total = 25 `prerequisite` + 2 `alternative` +
7 `potential-gate`.** `prerequisite`/`alternative` both stay within 1-2 bands back — P-8 routes
these through the inter-band gutter, a build MUST NOT warn or fail merely because one exists.
`potential-gate` does NOT fit that characterization: its 7 backward edges reach up to **5 bands
back** (a `has_technology` gate can reference any technology anywhere, unlike a formal
prerequisite chain) — its routing treatment is `TODO(Stage 3)`, deliberately deferred to a real
rendered canvas rather than designed blind; see `spec/P-08-connectors.md`. (History: originally
27/891 — `prerequisite`-only, under the initial `levels < 0`-only repeatable rule; then 27/881
once repeatable membership was corrected to 88 nodes; the 27 always decomposed into 25
`prerequisite` + 2 `alternative` once `alternative`-branch members stopped being flattened into
the same list — the `potential-gate` figure was never counted at all before this session.) See
D-13 in `spec/decisions.md` for the full reasoning, the reconciliation, and worst cases.

**Tier-source audit** (prompted by v1's reported wrong-placement failures — checked the source of
every rendered node's declared tier, not assumed correct): of 980 rendered nodes, 930 (94.9%)
have `tier` literal on the raw, unexpanded technology block; **50 (5.1%) — all
`giga_tech_repeatable_*_cap` technologies — only get a `tier` field via `inline_script`
expansion** (`giga_mega_repeatable.txt`'s template), exactly the bug class that produces wrong
placement if expansion is skipped. 0 rendered nodes lack a resolvable declared tier after
expansion — but the correct policy going forward is a **hard build failure** for any that ever
do (CLAUDE.md/P-2: "the build fails rather than emitting a partial dataset"), never a silent
default tier. 83 nodes (8.5%) declare `tier` as a `@variable` reference (4 distinct variables,
all currently resolve, none currently subject to a cross-source scripted-variable overwrite) —
but **`pipeline.overwrites.resolve_variable_overwrites` only checks `cost`/`weight` for
cross-source variable overwrites, not `tier`** — a currently-latent blind spot (zero real impact
today) worth closing before Stage 2's real dataset build, not urgent now. 2 nodes
(`tech_adaptive_combat_algorithms`, `tech_biomechanics`) have their declared tier changed by a
P-15 technology-block overwrite (Vanilla → ACOT) — already correctly handled by existing P-15
machinery, since it's a literal field difference, not a variable-indirection issue.

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
**Cost display**: base `cost` (first-level, primary) plus `costPerLevel` (scaling rate,
secondary) — never `costPerLevel` alone, never omitted for a repeatable card. See
`spec/P-02-layout.md`'s "Cost display" section for the full rationale (in-game cost is
approximate regardless of empire state; the scaling rate is the one figure the card can state
truthfully) and the "Prerequisites"/schema sections for how a null `cost` (15/980 rendered nodes,
unresolvable, never guessed at) is represented.

**This is D-13's one declared exception to "bands are declared tier, full stop"**: a repeatable
technology bands into the terminal Repeatables band regardless of its own declared `tier`, and its
card badges repeat count instead of the tier badge. `tier` is still resolved, still validated
(`UnresolvedTierError` applies unchanged, no exemption), and still emitted — it stays meaningful
for internal sub-grid ordering and the detail popup, it just isn't what the band header or card
display. This is not v1's bug repeated: v1's failure was a band header making a FALSE claim about
the cards under it ("TIER 6" over T5-badged cards); here the band header asserts repeatable-ness
and the card asserts repeat count, and both are true at once. See D-13 in `spec/decisions.md` for
the full argument — read it before "fixing" this as an inconsistency.

**Membership is "source declares a `levels` field at all," not "`levels` is negative."** Corrected
against a user's v1 screenshot (a card badged "T5 x5"), not caught by any test: the original
`pipeline.layout.is_repeatable` only tested `levels < 0`, which is real for 76 of the corpus's
repeatable technologies but misses 12 more that declare `levels` as a positive **finite** cap (5,
20, or 40) on an otherwise identical `cost_per_level` shape — including
`tech_repeatable_reduced_building_cost` ("Gravitational Analysis"), the exact node visible in the
screenshot. Corrected membership is **88 nodes**, not 76. This set is deliberately distinct from
the 50 `giga_tech_repeatable_*_cap` inline_script-tier-only nodes (CLAUDE.md's "Tiers" section) —
every `_cap` node happens to be repeatable (a proper subset of the 88), but 38 of the 88 are
repeatable without ever going through inline_script tier expansion. Conflating the two sets is a
distinct bug from either finding alone.

**Sink property, verified over the corrected 88-node set**: every prerequisite edge touching a
repeatable node is non-repeatable → repeatable; zero run the other way or repeatable → repeatable.
A repeatable node therefore never sources an edge at all, so it can never source a backward edge
and the Repeatables band needs no intra-band edge routing.

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
  profiles, gate patterns, `config/crisis_faction_overrides.txt` (D-7's step-3 fallback, seeded
  empty — see `pipeline/crisis_faction.py`), `config/overwrite_overrides.txt`,
  `config/icon_overrides.txt` (a technology/swap referencing an icon its upstream source never
  shipped — never a silent fallback, always a reviewed, justified entry), `config/
  lock_reason_overrides.txt` (P-13's lock-reason override table — used when a locked technology's
  reason string can't be derived automatically from its trigger; `pipeline/availability.py`'s
  `needs_lock_reason_override`/`build_missing_lock_reason_overrides` warn when an override is
  missing; seeded empty — the real corpus currently has no case that needs one), mod metadata.
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
    python tools/build_dataset.py       # build the real dataset into client/public/dataset/ (needs vendor/ populated)
    pip install -e ".[dev]"             # install the pipeline package + pytest
    pytest                              # run the pipeline test suite

    cd client && npm install            # install the Stage 3 client toolchain (Node pinned via client/.nvmrc)
    npm run dev                         # Vite dev server
    npm run typecheck                   # tsc --noEmit
    npm run build                       # tsc --noEmit && vite build -> client/dist/ (needs client/public/dataset/ built first)

    bash tools/deploy_local.sh          # D-15: build dataset + client, publish dist.zip as a GitHub Release (needs `gh` auth'd, vendor/ populated)

CI: `.github/workflows/typecheck.yml` (`tsc --noEmit` on every `client/**`/dataset-types.ts
change). `.github/workflows/deploy.yml` is `workflow_dispatch`-only (D-15, spec/decisions.md) —
it does NOT build anything; it downloads a pre-built `dist.zip` from a GitHub Release (published
by `tools/deploy_local.sh`) and deploys that. `tools/build_dataset.py` never runs in CI and
never will, permanently — see D-15's vanilla-blocker reasoning. No pipeline-test CI workflow
exists yet (`pytest` is still run manually/locally only) — a real gap, not filled by any Stage 3
session so far.

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
  ~~**TODO(Stage 3):** `schema/generated/dataset-types.ts` has never actually been typechecked~~
  **Closed, later session — see "Stage 3 toolchain foundation is built" below.** Zero `tsc`
  errors, verified three ways, not just by the drift test's self-consistency check.
- ~~One remaining Stage 2 handoff, recorded as a `TODO(Stage 2)` in `pipeline/icons/resolve.py`:
  the atlas currently packs every resolvable icon across all four sources unconditionally.~~
  **Done** (later session): `pipeline/icons/build.py`'s `filter_result_to_rendered_scope` filters
  technology icon candidates to the P-16 980-node rendered set (ascension-perk icons deliberately
  stay unfiltered — see HANDOFF.md's "Atlas content scope" note for why filtering them by the
  technology closure would be the wrong criterion entirely). Real filtered figures: technology
  atlas 4 sheets/8,387,616 bytes (unfiltered) → **2 sheets/4,564,314 bytes** (filtered); combined
  with the unchanged 262,676-byte perk sheet, **total ~4.83 MB, down from ~8.65 MB unfiltered**.
  `MAX_TOTAL_ATLAS_BYTES` re-calibrated from 12 MB to **6 MB** — deliberately kept below the old
  unfiltered ceiling, unlike 12 MB, so a regression that silently disables filtering is now
  actually caught by the tripwire. Icon atlas bytes remain excluded from P-10's ≤2 MB base-dataset
  budget (P-9/`implementation-notes` require lazy icon loading; P-10's budget is defined as the
  base dataset's compressed transfer size specifically). The other `TODO(Stage 2)` from the icon
  pipeline — 19 technology/swap and 6 ascension-perk candidates recorded as unresolved diagnostics
  — is now partially resolved by the filter: only 4 of the 19 technology candidates survive it
  (their owning technology is actually rendered); the 6 ascension-perk candidates are unaffected
  (perks aren't filtered) and still stand uninterpreted, same as before.
- **D-10/P-13 availability evaluator is built**: `pipeline/availability.py` — the partial trigger
  evaluator described above (three-valued short-circuit boolean evaluation, the 3 documented
  ground-fact assumptions, `has_technology`/`has_ascension_perk`/`has_gigastructural_constructs`/
  `has_galactic_wonders` exclusion — the latter two added after direct inspection showed they're
  ascension-perk gates wearing a different name, not a new kind of undecidable leaf). Boolean
  wrapper keys (`AND`/`OR`/`NOT`/`NOR`) are matched case-insensitively — the corpus genuinely uses
  both `NOT = { ... }` and `not = { ... }` for the same semantics (found while building Task 3's
  category survey; missing this silently treated real lowercase wrappers as unrecognised leaves).
  Output is `AvailabilityResult(state, reason, description, category)` per `(technology, profile)`
  pair. `pipeline/rendering_scope.py` implements P-16's closure as real code (BFS over resolved
  `prerequisites`, matching HANDOFF.md's hand-computed 7-technology/980-rendered-node measurement
  exactly) so both D-10 metrics are computed over the EXACT rendered set, not an approximation.
  `pipeline/trigger_text.py` is the shared trigger-condition -> text/category component HANDOFF.md
  flagged as missing — `describe_condition()` (best-effort human-readable phrasing, also usable
  for P-12.8's weight-modifier condition text) and `categorize_leaf()` (classifies an undecidable
  leaf into a `ReasonCategory`, corpus-derived, not designed up front — see that module).
  `pipeline/lock_reason_overrides.py` loads `config/lock_reason_overrides.txt` (same format/review
  bar as `config/overwrite_overrides.txt`, seeded empty — the real corpus currently has zero
  LOCKED results that fall back to unphrased raw trigger text) and
  `needs_lock_reason_override()`/`resolve_lock_reason()`/`build_missing_lock_reason_overrides()`
  wire P-13's "warn when an override is missing" requirement. `survey_uncertainty()` computes the
  D-10 metric split; `classify_d10_status()`/`build_d10_diagnostics_section()` apply the
  3%/10%/ratchet thresholds and produce the `schema/diagnostics.schema.json`-shaped
  `profileDependentUncertainty`/`unconditionalUncertainty` sections (that schema was updated in
  the same session — see below). Tests: `tests/test_availability.py`,
  `tests/test_trigger_text.py`, `tests/test_lock_reason_overrides.py`,
  `tests/test_rendering_scope.py` (all synthetic, mechanism coverage), plus
  `tests/test_availability_corpus.py`/`tests/test_rendering_scope.py`'s real-corpus tests (skipped
  when `vendor/` isn't populated).

  **Real measured rates, over the EXACT 980-rendered-node P-16 closure (both metrics share this
  denominator, per this file's D-10 section)**: **3.37% worst-case profile-dependent uncertain**
  (below HANDOFF.md's 5.3% upper-bound projection, as expected — the projection counted "could
  vary by profile", the real short-circuit logic pins it lower; **confirmed to actually cross the
  3% warn threshold** — `classify_d10_status(0.0337) == "warn"`, asserted directly in
  `tests/test_availability_corpus.py`, not just eyeballed from a printed rate) and **21.33%
  unconditional uncertain (209/980)**.

  **This figure moved twice** (209 → 259 → 209) **before settling here — see the "`giga_tech_
  repeatable_*_cap` correctly categorized — CONFIG_GATED" bullet further down this section for
  the full history, both corrections, the re-derived category-distribution table, and why 209
  landing back where it started is a coincidence of arithmetic, not evidence nothing changed.**
  In short: the original 209 was wrong (raw-block parsing skipped 50 real technologies' gating
  conditions entirely); 259 was also wrong, differently (those 50, once evaluated correctly,
  were classified `uncertain` when their `potential` actually resolves determinately); 209 is
  now right, because those 50 correctly resolve to `config-gated` — a fourth `AvailabilityState`,
  not `uncertain` and not `locked` — and so belong in neither this metric nor its `locked`
  counterpart. The category distribution over this final 209-set is byte-identical to the
  original pre-correction table (89/41/34/34/7/4 — crisis/story, origin, opaque-country-state,
  ethics/civic, unclassified, mod-content) — restated below rather than in this paragraph, since
  it's identical to what was already documented before any of this session's or the previous
  session's corrections began. `has_country_flag`'s crisis/story sub-split is still a
  name-pattern heuristic, not individually verified per flag (see `_looks_like_story_progress`).

  **Defect class, not three unrelated bugs (Stage 2 cleanup session).** Three components have now
  independently produced a plausible-but-wrong answer, with no error raised, by reading
  `giga_tech_repeatable_*`-family technology data by a route other than the full expanded
  canonical record: (1) tier resolution — 50 `_cap` nodes have no `tier` field pre-expansion (P-2's
  tier-source audit); (2) `pipeline.layout.is_repeatable` — a related but mechanistically distinct
  bug (a sign-only `levels < 0` predicate missing 12 finite-level repeatables in the SAME family,
  not itself a raw-vs-expanded input problem, since layout's real-corpus path was already
  expansion-fed — see the "Repeatables" section); (3) this section's `unconditionalUncertainty` —
  50 `_cap` nodes have no `potential` field pre-expansion. (1) and (3) are the same mechanism
  (expansion-only field) applied to two different fields; (2) shares the same *family* and the
  same *symptom* (a plausible wrong answer, zero errors, discovered only by independently checking
  against real evidence — a screenshot for (2), a hand-recomputation for (3)) without sharing the
  exact cause. **The actionable generalisation**: any component that acquires technology data by a
  route other than the full expanded canonical record is at risk of this failure mode, and the
  `giga_tech_repeatable_*` family is the reliable canary for it, because enough of that family's
  own data (tier, potential, and — via `giga_mega_repeatable.txt`'s shared template — probably
  other fields too) exists ONLY post-expansion that a raw-block consumer fails silently rather
  than loudly. See the audit below for which of this pipeline's other components read technology
  blocks, and by which route.

  **Audit: every component that reads a technology block, and its input route** (Stage 2 cleanup
  session, reported not fixed — see HANDOFF.md for the one gap found and its scoped follow-up):

  | Component | Reads technology blocks via | Expanded? |
  | --- | --- | --- |
  | `pipeline/overwrites.py` (`collect_technology_definitions`, diffing, `ordered_prerequisites`, `alternative_prerequisite_groups`) | `Document`s passed in by the caller | Caller-dependent — never expands itself |
  | `pipeline/rendering_scope.py` | `TechnologyDefinition.block` from `overwrites`' history | Caller-dependent, same as above |
  | `pipeline/crisis_faction.py` | Same | Caller-dependent, same as above |
  | `pipeline/layout.py` (`compute_layout`, `resolve_declared_tier`, `is_repeatable`, `category_of`) | `TechnologyLayoutInput.block`, supplied by the caller | Caller-dependent; every real corpus test/emission call site feeds it expanded blocks (verified) |
  | `pipeline/edges.py` (`compute_typed_edges`) | `dict[str, Block]` passed in by the caller | Caller-dependent, same as above |
  | `pipeline/availability.py` (`evaluate_trigger_block` and friends) | A `Block` passed in by the caller | Caller-dependent — **this is exactly where the bug lived**: the evaluator itself was always correct, its caller (the old test fixture) fed it the wrong input |
  | `pipeline/dataset_emit.py` | Loads and expands technology documents itself, once, in `build_context` | Always expanded — verified, this is the one component with its own loading path rather than depending on a caller |
  | `pipeline/icons/resolve.py`/`build.py` (`collect_candidates`) | Parses technology/ascension-perk files directly via `parse_file`, no caller-supplied option at all | **NOT expanded — reads raw, unexpanded blocks unconditionally, no way to pass expanded documents in.** |

  **Every pipeline module above that takes a block as a parameter is correct-by-construction and
  depends entirely on its caller** — none of them expands internally, and none of them is wrong on
  its own terms. The failure mode lives at the CALL SITE, not in these modules, which is exactly
  why the bug was invisible: `pipeline/layout.py`'s and `pipeline/dataset_emit.py`'s real call
  sites already expand correctly (verified, not assumed), so the same shared functions are
  correct when called from there and were wrong only when called from
  `tests/test_availability_corpus.py`'s own fixture.

  **One real, not-yet-audited-away gap found**: `pipeline/icons/resolve.py`'s `collect_candidates`
  parses `common/technology`/`common/ascension_perks` files directly with `parse_file`, with no
  `inline_script`-expansion step anywhere in the icon pipeline, and no parameter to accept
  pre-expanded documents even if a caller wanted to supply them. Every one of the 50
  `giga_tech_repeatable_*_cap` technologies' icon resolution consequently runs off a raw block —
  **unaffected in practice today** (their `icon` field, if any, and their filename-convention
  fallback don't come from anything the `giga_mega_repeatable.txt` template splices in — checked:
  none of the 50 candidates is unresolved for a reason traceable to a missing expansion), but this
  is exactly the shape of gap that produced all three defects above, just not yet triggered for
  icons. **Not fixed in this session** (audit only, per this session's scope) — a follow-up should
  scope whether icon candidate collection needs the same `inline_script` expansion pass every
  other Stage 2 consumer already gets, or whether icon resolution's specific field set (`icon`,
  `technology_swap`/`tradition_swap`, `inherit_icon`) is safely never inline_script-templated in
  the real corpus (unverified either way — this audit checked today's zero-impact outcome, not the
  general question).

  **Leaf-matcher case-sensitivity audit** (prompted by the boolean-wrapper case bug above):
  checked every known leaf key (`is_nomadic`, `is_gestalt`, `country_uses_bio_ships`,
  `has_country_flag`, `has_global_flag`, `has_dlc`/`host_has_dlc`, `has_technology`,
  `has_ascension_perk`, `is_fallen_empire`, `has_ethic`, `has_origin`, `has_valid_civic`, ...) for
  case variants and found none in the real corpus; `= yes`/`= no` values are always lowercase
  (1,824 / 667 occurrences, zero `Yes`/`YES`/`No`/`NO` variants); every mod-config toggle suffix
  match (`_forbidden`/`_disabled`/`_OFF`) has no lowercase counterpart being missed; and every
  axis-fact leaf in the corpus uses `=` exclusively, never `!=`/`<>`. No further case- or
  syntax-variant bug found — the boolean-wrapper case bug was real but isolated, not a symptom of
  a broader pattern in leaf matching.
- **D-7/P-5 crisis-faction derivation is built**: `pipeline/crisis_faction.py` implements the
  three-step rule D-7 only stated before now — technology ID (`classify_by_tech_id`), then
  prerequisite-chain inheritance (`classify_by_prerequisite_inheritance`, iterated to a fixed
  point so a chain of inherited classifications propagates fully regardless of processing order),
  then `config/crisis_faction_overrides.txt` (loaded by `pipeline/crisis_faction_overrides.py`,
  same format/review bar as the other override tables — seeded empty, and uniquely among this
  project's override tables explicitly allowed to CORRECT an automatic result, not just fill a
  gap, since faction membership is closer to an editorial call). **Deliberately does NOT
  implement `potential`-block flag inspection** as part of step 2, despite D-7's "potential and
  prerequisite inspection" wording — tried against the real corpus and found to produce two
  confirmed false positives (`tech_sm_autocannons` is EHOF/Urmazin-trader content referencing a
  Compound weapon-compatibility bypass flag, not Compound membership; `giga_tech_
  tetradimensional_engineering` is a standard physics tech with an alternate Blokkat-crisis
  unlock path, not a Blokkats-lane technology) — both confirmed by reading the actual block, not
  guessed from the flag name. **Real derived counts, over the 980-node P-16 rendered set**:
  Standard 925, Blokkats 42, Sirenalia 7, Aeternum 3, Katzenartig Imperium 3, **Compound 0**.
  Compound's zero is a confirmed real zero, not a classifier gap: `giga_08_ehof_components.txt`
  contains seven `tech_compound_*` technology blocks, every one commented out in the vendored
  source — Compound's technology content doesn't exist as live, parseable data in this corpus
  snapshot. **Do not rebuild or extend the classifier chasing Compound content on this basis** —
  there is nothing in the current corpus for a smarter derivation to find; re-check only after a
  Gigastructures version bump that could plausibly have uncommented the content (re-run
  `tests/test_crisis_faction_corpus.py::test_compound_technologies_are_commented_out_in_the_vendored_corpus`,
  which fails loudly the moment that's no longer true). **The Compound lane MUST still be
  supported end-to-end in the schema and renderer despite its current zero population** — D-7
  names five factions unconditionally, `pipeline/crisis_faction.py`'s `CRISIS_FACTIONS` already
  enumerates all five regardless of live content, and the content may be uncommented in a later
  mod release without any pipeline change being needed if the lane was never special-cased down
  to "four factions" anywhere. Step 2 and step 3 both contribute zero additional nodes beyond
  step 1 for the current corpus — step 1 (technology ID) is confirmed to be the entire
  currently-derivable signal, a finding, not an assumption. Tests: `tests/test_crisis_faction.py`,
  `tests/test_crisis_faction_overrides.py` (synthetic), `tests/test_crisis_faction_corpus.py`
  (real corpus, skipped when `vendor/` isn't populated — asserts the corrected per-faction counts
  above so a future corpus refresh that changes them fails a test instead of drifting silently,
  and directly asserts both false-positive candidates resolve to the standard lane).
- **P-2/D-13 layout is built**: `pipeline/layout.py` (band/lane/sub-grid position computation)
  and `pipeline/geometry.py` (packs it into `float32` typed-array side-files + `GeometryRef`
  pointers, per `00-overview.md`). Two correctness gaps the tier-source audit found were closed
  first, both tested: `pipeline.overwrites.resolve_variable_overwrites` now checks `tier` for
  cross-source `@variable` overwrites (not just `cost`/`weight`); `pipeline.layout.
  resolve_declared_tier` hard-fails (`UnresolvedTierError`) on any rendered node whose declared
  tier can't be resolved after `inline_script` expansion, never a silent default. Bands are a
  node's own declared `tier` — D-13's model, not the superseded computed-column one. Computed
  longest-path position is internal only: it orders nodes within a band's category-grouped
  N=4-wide sub-grid (`(category, computed_position, key)`, deterministic) and gives backward-edge
  routing a consistent signal. Lanes are the fixed D-7 order (`LANE_ORDER`, standard + 5 crisis
  factions), always all six, including Compound at its confirmed-real zero population. Edges are
  routed as simple 4-point orthogonal polylines (H-V-H) with a deterministic hash-based channel
  offset (the hash now includes `kind`, not just `from`/`to`, so the 4 pairs that are both a
  `prerequisite` and a `potential-gate` edge don't draw identical overlapping polylines) — a
  first-pass router, not a full crossing-minimising/obstacle-avoiding one; that remains open
  follow-on work, noted in P-2 rather than silently claimed done. `edges[].backward`
  (`schema/common.schema.json`) flags a backward edge for distinct rendering treatment;
  `edges[].bandSpan` (added for P-14 edge typing, see below) carries the signed band distance on
  every edge, not just backward ones.

  **Real run over the exact 980-node P-16 rendered set** (`tests/test_layout_corpus.py`): all 980
  resolve — 0 `UnresolvedTierError`, 0 `LayoutCycleError` (the rendered prerequisite graph is
  confirmed acyclic). 34 of 989 rendered edges are backward (25 `prerequisite` + 2 `alternative` +
  7 `potential-gate` — see the P-14 edge-typing bullet below for the full breakdown; this figure
  superseded the original 27/964 `prerequisite`-only measurement in the same session it was made).
  Tests: `tests/test_layout.py`, `tests/test_geometry.py` (synthetic, mechanism coverage),
  `tests/test_layout_corpus.py` (real corpus, skipped when `vendor/` isn't populated — asserts the
  real canvas dimensions, densest cell, and backward-edge count so a corpus refresh that silently
  changes any of them fails a test). Schema updated to match (`schema/base-dataset.schema.json`'s
  stale per-technology `column` field — described as "may exceed tier after promotion", the
  superseded model — removed entirely; `tierBands[].column` renamed `bandIndex` with a description
  matching D-13; `schema/common.schema.json`'s `Edge` gained the required `backward` field); TS
  types regenerated; fixtures updated; schema tests green.

  **Repeatable-membership correction (later session, found against a user's v1 screenshot, not by
  any test)**: `is_repeatable` widened from "`levels < 0`" to "`levels` field present at all" —
  see "Repeatables" above for the corpus finding (12 additional finite-level repeatables) and D-13
  in `spec/decisions.md` for the exception this membership rule feeds. Real figures shift
  accordingly: **canvas 12,544 × 8,146px** (was 8,350px — the 12 newly-recognised repeatables
  shrink their old declared-tier band rows and grow the Repeatables band), densest actual band
  cell **Standard × T5 = 253 nodes** (was 261 — 8 of the 12 were Standard-lane, declared-T5
  nodes that moved into Repeatables). Sink property re-verified over the corrected 88-node set:
  881 non-repeatable-to-non-repeatable prerequisite edges + 83 non-repeatable→repeatable edges =
  964 total (cross-checks the earlier 891-vs-964 reconciliation); 0 repeatable→non-repeatable, 0
  repeatable→repeatable, so a repeatable node can never source an edge, let alone a backward one.
  The 27 backward edges are the same 27 by key under both the old and corrected membership — none
  touches a repeatable node either way. `schema/base-dataset.schema.json`'s `repeatable` field
  changed shape from an always-present object to `null | { levels }` (`null` = not repeatable;
  object = repeatable, `levels` finite int or `null` for unbounded) — the old always-object shape
  had no way to represent "not repeatable" without also (incorrectly) claiming "unbounded
  repeatable" via `{"levels": null}`, which is what the four base-dataset fixtures were doing for
  their non-repeatable example technology before this session corrected them. TS types
  regenerated; `tests/schema/test_validation.py` gained explicit coverage of all three shapes
  (null / finite / unbounded) plus the zero-level rejection.

- **P-14 full edge typing is built** (later session): `pipeline/edges.py` — the last structural
  gap in Stage 2 before dataset emission. Layout previously built `prerequisite` edges only
  (`pipeline.overwrites.ordered_prerequisites`, called from `pipeline.layout._route_edges`); all
  three P-14 kinds are now real, extracted and typed:
  - **`prerequisite`** — `pipeline.overwrites.ordered_prerequisites`, corrected to exclude nested
    `OR`-branch members (see "Prerequisites" above) — 888 edges.
  - **`alternative`** — `pipeline.overwrites.alternative_prerequisite_groups`, the OR-branch
    members `ordered_prerequisites` used to wrongly flatten in — 76 edges across 35 groups (32
    technologies), each group carrying a `groupId` (`f"{owner}#alt{index}"`,
    `pipeline.edges.extract_alternative_edges`).
  - **`potential-gate`** — `pipeline.edges.extract_potential_gate_edges`, `potential`-only,
    scope-disciplined to match `pipeline.availability._evaluate_node` exactly (only descend into
    `AND`/`OR`/`NOT`/`NOR`; any other block-valued field is an opaque leaf) — 25 edges. This
    discipline is load-bearing, not style: an earlier, unscoped draft of the extraction found a
    false self-loop on `tech_ehof_sentient_tier_7`, whose `potential` nests
    `has_technology = tech_ehof_sentient_tier_7` inside `count_country = { limit = { OR = {...}
    } } }` — checking OTHER empires in the galaxy for a scarcity mechanic, not the researching
    empire's own state.
    `tests/test_edges.py::test_count_country_nested_has_technology_does_not_produce_an_edge` and
    `tests/test_layout_corpus.py::test_tech_ehof_sentient_tier_7_has_no_self_loop_edge` are the
    permanent regression guards.

  **Two standing diagnostics** (`pipeline.edges.EdgeExtractionDiagnostics`, never a build
  failure): `has_technology_under_allow` (P-3's "potential and allow" framing is aspirational —
  `allow` never occurs on a rendered technology today, 0/980, verified; fires if a future mod
  update introduces one) and `negated_potential_gate` (a `has_technology` inside an odd `NOT`/
  `NOR` nesting is a negative dependency with no `EdgeKind` representation today — 0 real
  occurrences; excluded from edge output and diagnosed rather than emitted as a wrong-polarity
  edge). Both confirmed empty on the real corpus
  (`tests/test_layout_corpus.py::test_no_has_technology_under_allow_on_real_corpus`,
  `::test_no_negated_potential_gate_on_real_corpus`).

  **Edge-kind membership is NOT mutually exclusive per `(from, to)` pair** — 4 real pairs are both
  a `prerequisite` and a `potential-gate` (e.g.
  `tech_mega_engineering -> giga_tech_arkship_neutronium_harvester`); both are emitted as distinct
  `TypedEdge` records. Collapsing them for display, if ever wanted, is a Stage 3 rendering
  decision over the emitted data, not a data-model one (`spec/P-14-unconventional-prereqs.md`).

  **P-16's rendering-scope closure stays `prerequisite`-only**, decided on evidence
  (`spec/P-16-mod-requirements.md`): recomputing it with `alternative` treated as traversable
  changes nothing on the real corpus (identical 7-technology closure, identical 980 rendered
  nodes, all four "supertensile" trigger technologies reach ACOT/AoT via a true prerequisite
  chain). The forward-looking risk is mitigated by a standing diagnostic, not a closure change:
  `pipeline.rendering_scope.compute_alternative_only_gaps`, empty on the real corpus
  (`tests/test_rendering_scope.py::test_real_corpus_has_no_alternative_only_gaps`).

  **`pipeline/rendering_scope.py` and `pipeline/crisis_faction.py` needed zero code changes** —
  both already consumed `ordered_prerequisites()`, so correcting that function to exclude
  `OR`-branch members fixed both automatically. Measured effect of the fix (Task 1's audit, before
  implementing): `crisis_faction.py`'s D-7 step-2 inheritance — a real 0-technology change (no
  real-corpus classification ever actually depended on an OR member); `pipeline.layout`'s internal
  `computed_position` (never displayed, D-13) — 142 nodes shift by 1-3 internally, with **canvas
  dimensions and densest band cell confirmed unchanged** (12,544×8,146px, Standard×T5=253) since
  bands are declared tier and `computed_position` only orders within a band — asserted explicitly
  in `tests/test_layout_corpus.py::test_densest_actual_band_cell_and_canvas_dimensions`'s own
  docstring, not just carried as an assumption. `pipeline/availability.py` was confirmed to never
  consume `prerequisites` at all (P-16's per-profile structural-reachability check — the consumer
  that WOULD have turned OR-conflation into a false `locked` result — is specified but still not
  built; fixing the flattening now, before that check exists, is exactly the point: the bug was
  free to fix today and becomes a reachability bug the moment that check is written against the
  conflated list).

  **Final real figures, over the 980-node rendered set** (`tests/test_layout_corpus.py`,
  `tests/test_edges.py`, `tests/test_rendering_scope.py`): **989 total edges = 888 prerequisite +
  76 alternative + 25 potential-gate.** Sink property holds over the full set: 906
  non-repeatable-to-non-repeatable + 83 non-repeatable→repeatable = 989, 0 repeatable→non-
  repeatable, 0 repeatable→repeatable. Backward: 34 = 25 + 2 + 7 (see the "Tiers" section above
  for the full reconciliation against the earlier 27/891 and 27/881 figures). `schema/
  common.schema.json`'s `Edge` gained `groupId` (nullable, `alternative`-only) and `bandSpan`
  (signed, every edge); TS types regenerated; the one Edge-bearing schema fixture updated;
  `pipeline/geometry.py`'s `pack_edge_polylines` index dicts gained the same two fields.
  `spec/P-14-unconventional-prereqs.md`'s Requirement section reworded: an earlier draft described
  `alternative` as a profile-relative relabeling of whichever kind is "active" for the selected
  empire profile, which is architecturally impossible (`Edge.kind` lives in the profile-invariant
  base dataset; only the *active edge set* varies per profile, in the empire-overlay artefact) —
  `alternative` is, and operationally always was, the nested-`OR`-inside-`prerequisites`
  construct P-08 already defined edge direction for. `spec/P-08-connectors.md`'s backward-edge
  characterization ("1-2 bands back, small and short-range") is now explicitly rescoped to
  `prerequisite`/`alternative`; `potential-gate`'s real distribution (up to 5 bands back) is
  recorded separately with its own `TODO(Stage 3)` routing decision, deliberately not designed
  here. Tests: `tests/test_edges.py` (synthetic, mechanism coverage — scope discipline, group IDs,
  the count_country regression, the two diagnostics, dual-kind pairs),
  `tests/test_overwrites.py`/`tests/test_overwrites_corpus.py` (updated for
  `ordered_prerequisites`'s corrected contract and the new `alternative_prerequisite_groups`),
  `tests/test_rendering_scope.py` (the new tripwire diagnostic), `tests/test_layout.py`/
  `tests/test_layout_corpus.py` (the full three-kind edge set wired through real layout output).
- **Stage 2 dataset emission is built** (later session): `pipeline/dataset_emit.py` assembles all
  five schema'd artefacts from every already-built Stage 2 component (P-15 overwrites, P-13
  availability, P-16 rendering scope, D-7 crisis faction, P-2/P-14 layout+edges, filtered icon
  atlases) and validates every one against its schema as part of the build
  (`pipeline.dataset_schema.validate_*`) — an invalid artefact raises during assembly, never a
  separate optional check. `tests/test_dataset_emit.py` runs the real build end to end against the
  vendored corpus: all 980 technologies, all 989 edges, all 12 empire overlays, all 980 detail
  payloads, the search index, and diagnostics — every one schema-valid, plus a direct
  `availabilityMatrix`/overlay consistency cross-check
  (`pipeline.dataset_schema.empire_profile.check_availability_matrix_matches_overlays`).

  **Real measured base-dataset transfer size: ~64 KB compressed** (65,585 bytes: 54,264 JSON +
  2,911 node side-file + 8,410 edge side-file, gzip level 9) — comfortably under P-10's 2 MB
  budget, but a real finding worth its own writeup rather than a quiet update: the pre-build
  projection was ~275-305 KB, and the **real measured compression ratio is 14.29x**, well above
  the 6-9x range the projection assumed (itself drawn from the deploy-spike's 9.34x synthetic
  ratio, with an explicit caveat that real content should compress *worse* than synthetic, not
  better). The projection held directionally (comfortably under budget) but its specific method
  was wrong, not just imprecise: the deploy-spike's synthetic ~1,878-record blob was dominated by
  free-text name/description-shaped content, while the real base dataset's size is dominated by
  small, highly-repetitive structured JSON — 980 near-identically-shaped technology records, each
  carrying a 12-slot enum array (`availabilityMatrix`), mostly-empty arrays (`gates`, `requiresMods`
  for 95%+ of nodes), and `null` (`crisisFaction` for 925/980) — exactly the shape gzip compresses
  far better than prose. Free-text content (descriptions) isn't even in the base dataset; it's in
  the lazy detail payloads. The lesson: a synthetic-content compression estimate is not a reliable
  stand-in for real structured-JSON compression, in either direction — re-measure against the real
  shape once it exists, don't extrapolate from a differently-shaped proxy.

  **Other four artefacts, measured for the first time** (never part of P-10's budget, but Stage 3's
  loading design needs real numbers): empire overlays ~486 KB raw / ~43 KB gz each (12 total: 5.8 MB
  raw / 512 KB gz); detail payloads 630 KB raw combined, 384 KB gz fetched individually per
  technology vs. 90 KB gz if batched into one file (batching wins substantially — worth deciding
  before Stage 3 commits to a fetch granularity); search index 297 KB raw / 64 KB gz; diagnostics
  48 KB raw / 4.4 KB gz.

  **Real finding, not a bug in this emission code**: `unconditionalUncertainty.count` is **259**
  (26.4%), not the previously-published **209** (21.33%) — CLAUDE.md's "Availability evaluator"
  section below is corrected to match. Same evaluator, same 980-node closure; the difference is
  that `pipeline/dataset_emit.py` evaluates `potential` blocks from `inline_script`-EXPANDED
  technology definitions throughout, while `tests/test_availability_corpus.py` (the source of the
  209 figure) parses raw, unexpanded blocks. All 50 `giga_tech_repeatable_*_cap` technologies —
  the exact same group P-2's tier-source audit already found only gets a `tier` field via
  `inline_script` expansion — likewise only get their real `potential` field via expansion; on the
  raw block they have no `potential` at all, so the unexpanded survey silently treats all 50 as
  unconditionally AVAILABLE regardless of their actual (real, inline_script-supplied) gating
  condition. 259 − 209 = 50, exactly the cap-group size — confirmed directly, not inferred from
  the arithmetic coincidence alone (`tests/test_dataset_emit.py::
  test_diagnostics_validates_and_reports_the_unconditional_uncertain_finding` asserts every one of
  the 50 has a real `potential` block post-expansion). ~~`tests/test_availability_corpus.py` itself
  is not fixed in this session.~~ **Fixed in the following Stage 2 cleanup session** — see this
  file's "Availability evaluator" section for the full writeup, the re-seeded ratchet, the moved
  category-distribution proportions, and the defect-class note this joined. The profile-dependent
  worst-case figure (3.37%) is UNCHANGED and matches exactly — expansion only affects technologies
  whose `potential` itself is inline_script-templated, and none of those 50 happens to be the
  profile-dependent worst case.

  **Known v1 scope limitations** (each schema-valid, none silently fabricated — see the module
  docstring for the full list): `appliesToEmpireTypes` is unconstrained on every edge (a real
  per-edge empire-type constraint extractor is new scope beyond what P-14 built); `activeEdgeIds`
  is therefore every edge index for every profile; `gates` is always `[]`
  (P-3's gate-pattern-registry classification pass isn't built — already tracked as open before
  this session); `repositoryLink`'s wiki URLs aren't live-validated (no network access) and its
  `lineRange` uses the block's start line for both ends (no end-of-block line is tracked in the
  AST). ~~`swapMappings` is always `[]`~~ **Closed in a later session — see D-14 below.**
- **Small targeted correctness pass, prompted by a manual review of `giga_mega_repeatable.txt`**
  (later session, three independent items):

  1. **Boolean-operator case-sensitivity — audited, not a bug.** The template's `potential` block
     uses lowercase `not = { has_global_flag = $name$_disabled }`. Both walkers that descend only
     into `AND`/`OR`/`NOT`/`NOR` (`pipeline/availability.py`'s `_evaluate_node`,
     `pipeline/edges.py`'s `_scoped_has_technology`) already normalise to uppercase before
     comparing (`key.upper()`) — confirmed by reading the code, not assumed from the earlier
     "case-insensitive" claim. **Real corpus case survey, scoped to `potential` blocks across all
     1,879 canonical technologies**: `NOT`=111/`not`=50, `OR`=62/`or`=5, `AND`=29 (0 lowercase in
     this scope), `NOR`=17 (0 lowercase in this scope). **54 distinct rendered technologies carry
     a lowercase operator in `potential`** — 50 are the `giga_tech_repeatable_*_cap` family (all
     `not`), but **4 are outside it** (`giga_tech_birch_world_1` — 2×`or`,
     `giga_tech_planetary_seeder_nexus`, `tech_qnm_disruptors`, `tech_sm_autocannons` — 1×`or`
     each), confirming lowercase isn't confined to the repeatable-cap family, as expected. No fix
     needed; added a case-insensitivity regression test to `pipeline/edges.py`'s test suite
     (`tests/test_edges.py::test_extract_potential_gate_edges_boolean_wrappers_are_case_insensitive`
     — this walker had none before) and extended `pipeline/availability.py`'s existing one to
     cover lowercase `and`/`nor` too (it only covered `not`/`or`).

  2. **`cost`/`costPerLevel` added to the base dataset.** Neither was carried in
     `schema/base-dataset.schema.json` before this session — `cost` wasn't in the schema at all
     despite `00-overview.md`'s glossary naming "research cost" as a card field, and repeatables'
     `cost_per_level` (the real v1 gap: a repeatable card showing only the bare first-level cost
     misrepresents the commitment) existed nowhere in any artefact. Added: a top-level `cost`
     field (`number | null` — null when unresolvable, never guessed/defaulted to 0, matching D-4's
     "no evaluated weight" discipline) and `repeatable.costPerLevel` (`number | null`, required
     alongside `levels` whenever `repeatable` is non-null). **Decision, recorded in
     `spec/P-02-layout.md`'s new "Cost display" section**: base `cost` is the primary displayed
     figure, `costPerLevel` a secondary indicator — in-game cost shifts heavily with empire size
     and other live modifiers, so any absolute number is approximate regardless of which is shown;
     the scaling RATE is the one thing the card can state truthfully for a repeatable technology.
     Exact visual treatment is Stage 3's; this session emits semantic data only. **Real corpus,
     verified**: exactly the 88-node repeatable set carries a resolvable `costPerLevel` (0
     non-repeatable technologies do). Separately (found while wiring `cost` itself, not part of
     the original ask): **15 of 980 rendered technologies have an unresolvable `cost`** — 5 with
     no `cost` field at all (apparently-free starting technologies:
     `tech_missiles_1`/`tech_flak_batteries_1`/`tech_solar_panel_network`/others) and 10 vanilla
     "cosmic storm" technologies whose `cost` is a dynamic modifier block
     (`cost = { factor = @var inline_script = {...} }`, a previously-unseen shape in this
     codebase's cost handling) rather than a scalar — both emit `cost: null`, never a guessed
     value. TS types regenerated; all four base-dataset fixtures updated; `tests/schema/
     test_validation.py` and `tests/test_dataset_emit.py` gained coverage for both fields.

  3. **`pipeline/icons/resolve.py`'s raw-block gap — closed.** The previous session's audit found
     `collect_candidates` read raw, unexpanded technology/ascension-perk blocks unconditionally,
     with no way to supply expanded documents — the same shape as the defect class above (tier
     resolution, `unconditionalUncertainty`), just not yet triggered for icons.
     `collect_candidates`'s signature changed from `(source_name, Path)` to
     `(source_name, Document)` pairs; `pipeline/icons/build.py::resolve_kind` now parses AND
     `inline_script`-expands every technology/ascension-perk document itself (mirroring
     `pipeline/dataset_emit.py`'s own loading pattern) before handing it to `collect_candidates`.
     **Verified zero-impact on the real corpus, as predicted**: every existing exact-count
     assertion (2,103/19 unfiltered, 1,192/4 filtered technology candidates; 63/6 ascension-perk
     candidates) passed unchanged after the fix, including the SPECIFIC unresolved-candidate key
     lists — strong enough evidence of byte-identical results that no separate diff was needed.
     Added `tests/icons/test_resolve.py::
     test_collect_candidates_sees_an_inline_script_supplied_icon_field`, a synthetic template that
     DOES define an `icon =` field, proving the expanded-vs-raw distinction actually matters (raw
     input falls back to filename convention; expanded input picks up the template's icon) rather
     than merely proving the plumbing compiles.
- **`giga_tech_repeatable_*_cap` correctly categorized — CONFIG_GATED, a fourth availability
  state** (later session). Follow-up to the "Small targeted correctness pass" bullet above: the
  50-node family's `unclassified` jump (7→57, "Availability evaluator" section) turned out to be
  a real classification GAP, not just missing corpus coverage. The template's `potential` —
  `NOT{has_global_flag=$name$_disabled} AND has_global_flag=$name$_capped_r` — is two
  mod-configuration toggles; the user confirmed `_capped_r` specifically (no core Gigastructures
  preset sets a cap to the "1+r" mode it names, so it's unset by default) is the SAME "assume
  documented default" shape as the already-recognised `_forbidden`/`_disabled`/`_OFF` suffixes,
  just not yet taught to the evaluator.

  **`pipeline.trigger_text.MOD_CONFIG_TOGGLE_SUFFIXES`** is now the single source of truth for
  this pattern (`_forbidden`/`_disabled`/`_OFF`/`_capped_r`) — moved out of
  `pipeline/availability.py`'s own private copy so the evaluator's resolution logic and
  `categorize_leaf`'s classification can't drift apart. **Corpus survey, scoped to `potential`
  blocks across all 1,879 canonical technologies** (not assumed confined to the known 50): every
  rendered technology using a `_capped_*`-shaped flag uses exactly `_capped_r`, and exactly the
  50 `giga_tech_repeatable_*_cap` technologies do so — `_capped_1`/`_capped_2`/`_capped_3`/
  `_capped_u`/`_capped_s` exist in the corpus (menu/button-effect files) but never in a rendered
  technology's `potential`, so nothing beyond the known 50 was in scope.

  **A new `AvailabilityState` (`schema/common.schema.json`, renamed from `ThreeState`) value:
  `config-gated`.** Elsewhere, `locked` means "your empire cannot obtain this" — an empire-state
  property, which is why D-10's states are keyed to the twelve-profile axis model at all. That
  framing is false for this family: their `potential` resolves definitively FALSE for every
  profile identically, but nothing about authority/shipset/nomadic status is the cause — a game
  OPTION is. Rendering them `locked` would misrepresent a one-toggle-away technology as
  empire-gated. `pipeline/availability.py`'s `evaluate_trigger_block` now checks whether the
  FALSE-causing leaf categorizes as `ReasonCategory.MOD_CONFIGURATION`
  (`pipeline.trigger_text`, new category) and emits `CONFIG_GATED` instead of `LOCKED` when it
  does — a mechanism that applies to any mod-config-toggle-caused FALSE result generally, not
  hardcoded to `_capped_r`; **verified against the real corpus that this generality costs
  nothing**: `config-gated` fires for exactly the 50 cap-family technologies and no others (every
  other real `_forbidden`/`_disabled`/`_OFF` occurrence is wrapped in `NOT{}`, contributing to
  AVAILABLE, never a bare FALSE). `$defs`/type renamed `ThreeState` → `AvailabilityState`
  deliberately (a value-count-independent name, so a fifth value later doesn't leave a stale name
  behind again) — TS types regenerated; both `$ref` sites (base-dataset's `availabilityMatrix`,
  empire-overlay's `availability[].state`) updated; empire-overlay's `reason`-required-when-
  non-available prose extended to cover `config-gated` too (this requirement was already
  documentation-only, not schema-enforced, for `locked`/`uncertain` — a pre-existing gap, found
  and reported, not fixed, since fixing it is unrelated new scope).

  **Real corrected figures, over the same 980-node rendered set (recomputed, not assumed)**:
  profile-dependent worst-case uncertainty **unchanged**, 3.37% (same profile, same rate to 5
  decimal places — none of the 50 was ever profile-dependent, since their `potential` has no axis
  check). Unconditional uncertainty **209/980 (21.33%), down from 259/980 (26.4%)** — the 50 that
  the earlier `_capped_r`-recognition fix had moved into `unconditionalUncertainty` now leave for
  `config-gated` instead. **209 is the same number the ORIGINAL raw-block-survey code reported,
  by coincidence, not by the same reasoning** — that number was wrong for skipping these 50 nodes
  entirely; this number is right for evaluating all 980 correctly and finding the 50 belong in a
  fourth state neither `uncertain` nor `locked` capture.

  **Category distribution over the final, corrected 209-node unconditional-uncertain set** —
  byte-identical to the table this project had before either correction began:

  | Category | Count | % of unconditional |
  | --- | ---: | ---: |
  | Crisis/story-chain progression | 89 | 42.6% |
  | Origin requirement | 41 | 19.6% |
  | Opaque mid-game country state | 34 | 16.3% |
  | Ethics/civic requirement | 34 | 16.3% |
  | Unclassified (honest fallback) | 7 | 3.3% |
  | Mod-content requirement (ACOT) | 4 | 1.9% |

  **~80% of unconditional uncertainty is explainable** (crisis/story + origin + ethics/civic + mod
  content), ~20% genuinely opaque or unclassified — restored exactly, since the intermediate
  259-node table's only difference (an `unclassified` count of 57, all 50 cap-family nodes
  landing there because `categorize_leaf` had no category for `_capped_r` yet) is now moot: those
  50 never reach `categorize_leaf` for the unconditional-uncertain path at all, because they
  resolve to `config-gated` before that classification would run. See `pipeline/trigger_text.py`'s
  own comments for the individual per-leaf verifications behind each row (`has_ancrel`,
  `is_world_forger_empire`, `giga_can_use_habitables`, etc.). See `spec/decisions.md`'s new D-10
  "CONFIG_GATED" subsection for the full
  evidence, the "first real application of the mod-config assumption to a bare flag" framing, and
  the explicit caveat that a non-core/custom Gigastructures preset may set a cap differently (a
  Stage 3 presentation concern, not a data one). Tests: `tests/test_availability.py`/
  `tests/test_trigger_text.py` (synthetic mechanism coverage, including that the suffix pattern
  applies only to `has_global_flag`, never `has_country_flag`), `tests/test_availability_corpus.py`
  (real-corpus figures, the corrected category-distribution table, and a two-layer regression
  guard — expansion AND correct-state — for all 50 cap technologies),
  `tests/schema/test_validation.py` (the new state's shape, plus the found-not-fixed
  reason-requirement gap recorded honestly), `tests/test_dataset_emit.py` (the real base dataset
  emits `config-gated` in all 12 `availabilityMatrix` slots for exactly the 50 cap technologies,
  never elsewhere).

  **The 209 → 259 → 209 sequence, recorded explicitly so it cannot be misread**: the two 209s
  above are not a no-op round trip — they exclude the same 50 nodes from
  `unconditionalUncertainty` for opposite reasons. Step 1 (original raw-block survey): 209,
  because a raw/unexpanded read never saw these 50 nodes' `potential` block at all — excluded by a
  defect, and (wrongly) counted `AVAILABLE`. Step 2 (after `inline_script` expansion, before
  `_capped_r`/`config-gated` existed): 259 = 209 + 50, because the now-visible `potential` made
  all 50 genuinely `uncertain`. Step 3 (current, after `_capped_r` joins
  `MOD_CONFIG_TOGGLE_SUFFIXES` and `config-gated` is introduced): 209 again, because those same 50
  now evaluate correctly to a fourth state, `config-gated`, that didn't exist at step 1 — same
  count, same 50 members, different (correct) reasoning. See `spec/decisions.md`'s D-10 section
  ("The 209 -> 259 -> 209 sequence...") for the full table.

  **The real change is visible in the AVAILABLE-state count, not the uncertainty count**: all 50
  moved from `AVAILABLE` (step 1's wrong reading) to `CONFIG_GATED` (step 3's correct one) — an
  **available-count delta of exactly -50**, confirmed directly
  (`tests/test_dataset_emit.py::test_repeatable_cap_family_available_count_delta_is_exactly_minus_50`):
  evaluating with no `potential` visible (the step-1 counterfactual) is unconditionally AVAILABLE
  for all 50; the real expanded evaluation is AVAILABLE for 0 of them. **Ratchet status**: having
  gone 209 → 259 → 209 across two sessions, the D-10 unconditional-uncertainty ratchet is back at
  its original seed value — no regression, no ratchet action needed.

  **Config-gated reason wording (P-13)**: display text is user-supplied, matching Gigastructures'
  own in-game option label — `Requires <Megastructure Name> cap: 1 + Repeatables`, e.g. "Requires
  Alderson Disk cap: 1 + Repeatables". Emitted as semantic data only, never a pre-composed
  sentence: the empire overlay's `availability[key].configGatedSubject`
  (`schema/empire-overlay.schema.json`) carries just the megastructure name; Stage 3 substitutes
  it into the fixed template, which lives in `spec/P-13-empire-locking.md`, not in the dataset.
  The name is sourced from the technology's own resolved localised name
  (`<Name> Management Protocols`, suffix stripped).

  **Corrected in a later session: all 50/50 resolve, not 42/50.** The suffix-stripped name is
  frequently itself a `$token$` (e.g. `giga_tech_repeatable_alderson_cap` -> `$name_alderson$`).
  An earlier pass assumed such a token was an unresolvable Stellaris runtime name-pool reference
  and returned `null` for all 8 real occurrences — including the flagship Alderson Disk example
  the reason wording was designed around. **That assumption was wrong**, found by re-inspecting
  raw localisation source (CLAUDE.md's own "inspect raw bytes, never conclude from a formatted
  read" rule, applied here to the previous session's own unverified claim): every `$token$` is
  ordinary Stellaris `$key$` loc-variable substitution — `token` is itself a plain,
  statically-resolvable loc key one hop away (`name_alderson: "Alderson Disk"`, Gigastructures'
  own localisation). Two of the 8 (`dyson_swarm_3`, `orbital_arc_furnace_4`) are **vanilla**
  megastructures Gigastructures extends with a repeatable cap, and their name lives in vanilla's
  own localisation — confirming the fix (`pipeline/dataset_emit.py`'s `_resolve_loc_tokens`) must
  search the full cross-source `ctx.loc_table` (vanilla, Gigastructures, ACOT, AoT, in load
  order), bounded to a small hop count (some tokens chain through a second token, e.g. vanilla's
  `dyson_swarm_1: "$dyson_swarm_3$: Array"`) so an unexpected cycle fails cleanly to `null` rather
  than looping. `configGatedSubject` stays nullable in the schema and the resolver still returns
  `None`, never a guess, if a technology has no loc entry at all or a token can't be resolved
  within the hop limit — no case in the current corpus hits either path.

  **Real corpus, corrected: 50/50 resolve** to a literal megastructure name — the 8 previously-null
  cases: `giga_tech_repeatable_alderson_cap` -> "Alderson Disk" (the user's own flagship example),
  `_asteroid_manufactory_cap` -> "Asteroid Industrial Site", `_dyson_swarm_cap` -> "Dyson Swarm",
  `_furnace_cap` -> "Arc Furnace", `_observatory_cap` -> "Atmospheric Storm Observatory",
  `_orbital_naval_logistics_cap` -> "Orbital Naval Logistics Office", `_warmoon_cap` -> "Attack
  Moon", `_warplanet_cap` -> "Behemoth Planetcraft". Implementation:
  `pipeline/dataset_emit.py`'s `_config_gated_subject`/`_resolve_loc_tokens`. Test:
  `tests/test_dataset_emit.py::test_config_gated_subject_resolves_all_50_megastructure_names`
  (supersedes the retired `..._resolves_42_of_50_...` test of the same name pattern).
- **P-15 overwrite resolution is built**: `pipeline/overwrites.py` (technology-block whole-key
  resolution, field-level diff against the immediately-preceding definition in load order —
  never hardcoded to vanilla — cost/weight compared through `@variable` resolution with the raw
  pre-resolution form retained alongside, prerequisites/category diffed as sets, flags diffed as
  a single composite field, declaration-order prerequisite display list kept separate from the
  diff) plus `pipeline/overwrite_overrides.py` (loader for `config/overwrite_overrides.txt`,
  seeded empty — no case in the corpus needs one; format and required-warning mirror
  `pipeline/icons/overrides.py`). `pipeline.overwrites.resolve_variable_overwrites` is the
  distinct scripted-variable overwrite layer (Finding 5: a technology's effective cost/weight can
  change without its own block being touched). Tests: `tests/test_overwrites.py` (synthetic,
  mechanism coverage), `tests/test_overwrite_overrides.py` (loader), `tests/test_overwrites_corpus.py`
  (real vendored corpus, skipped when `vendor/` isn't populated — asserts the corrected 25-overlap
  survey counts so a future corpus refresh that silently changes them fails a test). `schema/`
  (`common.schema.json`'s new `SourceMod` def, `detail-payload.schema.json`'s `source`/
  `overwriteDiff`, `diagnostics.schema.json`'s two-section `overwriteReport`) and
  `spec/P-15-overwrites.md` were updated to match — overwriting is not vanilla-only, and most of
  the corpus's overwrites (19 of 25) have no vanilla baseline at all. (Status at the time this
  bullet was written: trigger evaluation, tier/layout/edge computation and dataset emission were
  still open — all but dataset emission are built now; see the later bullets in this section and
  HANDOFF.md's "Ordered next steps" for current status.)
- **D-14: `technology_swap` per-profile name/icon substitution is built** (later session,
  prompted by a report that a bio-shipset player's card would show "Fission Power," a name that
  doesn't exist in their game). `pipeline/technology_swaps.py` (new module) parses every
  `technology_swap` sub-block and classifies its trigger against `pipeline.availability.AXIS_FACTS`
  (the SAME dict the evaluator uses for `potential` blocks — reused directly rather than a second,
  competing axis-leaf definition). **Real corpus: 214 swaps across 185/980 rendered
  technologies — 128 axis-expressible, 86 non-axis** (corrected from a pre-implementation
  ad-hoc survey's 126/88: `AXIS_FACTS` also resolves `is_mechanical_empire`/`is_robot_empire`/
  `is_regular_empire`, which that survey's own classification omitted).

  **Two treatments, never a third.** Axis-expressible swaps (128 swaps / 123 technologies)
  substitute per profile — `schema/empire-overlay.schema.json`'s `swapMappings` is redesigned
  (the old `{baseTechnologyId, activeVariantId}` shape assumed a variant had its own node id,
  which D-1's "a swap never becomes its own node" rules out) to carry
  `{technologyId, name, icon, area, category}` directly, `area`/`category` null meaning
  "unchanged from base." Non-axis swaps (86 swaps / 72 technologies — origin/civic/species-trait/
  ascension-perk/galaxy-situation leaves the 3-axis model can't express) NEVER substitute — listed
  instead in the detail payload's new `variants` field (`{name, icon, conditionText}`,
  `conditionText` via `pipeline.trigger_text.describe_condition`/new `describe_trigger_block`),
  popup-only, same precedent as ascension-perk gates. 10 technologies carry both (one swap
  substitutes, a different swap on the same technology lists as a variant). **The rendered node
  count stays exactly 980 regardless — asserted directly, not left as an unstated consequence.**

  **`tech_ring_world` exception, decided explicitly in chat, no special-casing**: its 2 swaps mix
  one axis leaf (`country_uses_bio_ships`) with one non-axis leaf
  (`giga_can_use_habitables`) in a single compound trigger — treated as WHOLLY non-axis (matches
  the evaluator's own Kleene "no partial credit on a compound condition" discipline). Cost is
  named: `tech_ring_world` keeps its base `society`/`voidcraft` presentation for every profile,
  with all 3 of its non-axis swaps listed as popup variants instead. Of the real corpus's 8
  area/category-changing swaps, all 8 fall out of this same classification for free — 6
  axis-expressible bio-shipset ones substitute automatically, `tech_ring_world`'s 2 non-axis ones
  never do — no separate area/category mechanism was needed.

  **Icon inheritance, item 6**: one real swap, `giga_tech_ring_world_swap_no_habitables`, declares
  `inherit_icon = no` with no icon file of its own. `pipeline/icons/resolve.py` still correctly
  leaves it an unresolved atlas candidate (unchanged — redirecting AT THAT LAYER would override an
  explicit authorial refusal, per that module's own docstring). A SEPARATE, presentation-layer
  fallback in `pipeline.dataset_emit`'s `_swap_icon_ref_map` shows the owning technology's icon for
  display instead, tracked via the new `diagnostics.swapsRenderingOnInheritedIcon`
  (`{technologyId, swapKey}[]`) — today exactly this one entry, confirmed to never fire for the 87
  swaps that legitimately keep the base icon via `inherit_icon` defaulting to `yes` (those resolve
  through the ordinary channel and are never `unresolved` candidates). No `config/
  icon_overrides.txt` entry was used deliberately — that would need a human to notice and remove it
  once upstream ships a real icon, and would silently shadow it until they did; the fallback
  instead yields automatically the moment a real icon resolves.

  **Trigger-text coverage gap reported, not invented**: 9 non-axis leaf names have no dedicated
  `describe_condition` phrasing and fall back to raw trigger text —
  `is_wilderness_empire` (41, by far the largest), `is_beastmasters_empire` (16),
  `giga_can_use_habitables` (3), `is_tankbound_empire`/`is_reanimator`/`is_eager_explorer_empire`
  (2 each), `has_void_dweller_origin`/`is_cloning_authority`/`is_situation_type` (1 each) — an open
  item for `pipeline/trigger_text.py`'s phrase table, not silently accepted or papered over.

  **`weight` (94/214 swaps) and `prereqfor_desc` (39/214) remain deliberately unsurfaced**,
  consistent with D-4's no-evaluated-weight precedent — seen during this decision's own survey,
  recorded so a future session knows it wasn't missed.

  **Real payload delta, measured**: the base dataset itself (P-10's budget) is unchanged —
  `swapMappings`/`variants` live in the lazy empire-overlay/detail-payload artefacts.
  `swapMappings` across all 12 overlays adds **~17.5 KB gzip** (~141 KB raw, 745 entries);
  `variants` across all 980 detail payloads adds **~2.8 KB gzip** (~15 KB raw, 86 entries) —
  both small next to the ~64-67 KB base-dataset reference point, well above the
  pre-implementation ~9.7 KB gz worst-case guess (icon-ref objects are heavier than bare
  strings) but nowhere near a concern either way. See `spec/decisions.md`'s D-14 for the full
  writeup. Tests: `tests/test_technology_swaps.py` (synthetic classification, including the
  compound-trigger and `is_robot_empire` cases), `tests/test_dataset_emit.py`'s D-14 section
  (real-corpus substitution/variant/icon-inheritance/payload-delta assertions).
- ~~**Deploy spike confirms P-10's compressed-transfer assumption.**~~ **Superseded, later
  session — `deploy-spike/` is deleted, replaced by the real pipeline below**, which re-confirms
  the same findings (relative-path base resolution, real hosting round-trip) against the ACTUAL
  toolchain and dataset rather than a throwaway synthetic stand-in. Historical record of what the
  spike proved before deletion: GitHub Pages serves both a JSON artefact and a binary typed-array
  side-file gzip'd (9.34x measured on a ~982 KB synthetic dataset), confirming P-10's ≤2 MB
  compressed-transfer budget assumption wasn't speculative.

- **P-12.9 (research path) is fully specced, not yet implemented** — `spec/P-12.9-research-path.md`
  (new file; the old P-12-detail-popup.md row is now a summary pointing to it). Fixes v1's second
  reported failure (profile-blind path, unexpanded `OR` branches, e.g. "or Arkship Mastery" never
  showing its own prerequisites). Per-profile traversal over true `prerequisite` edges + resolved
  `OR`-group selection (cheapest total cost among viable available/uncertain candidates — real
  corpus: 0 disagreements with fewest-steps across 72 genuine multi-candidate choices). `uncertain`
  steps stay in the path with the total marked an estimate; `config-gated` steps are excluded from
  the total and — confirmed structurally, not assumed — can ONLY ever be the path's own target,
  never a mid-path step (config-gated technologies are edge sinks, D-13's Repeatables finding
  extended to `alternative` edges too). **Pinned figure, corrected in a follow-up session**: the
  uncertain-path count is per SELECTED PROFILE (matching the path itself), not a single number —
  the original "163-182" was an unlabelled per-profile min/max range; canonical headline is
  **182/980 (18.6%), the worst profile** (machine_intelligence/biological/non-nomadic), with the
  full 12-profile table and the separately-labelled across-any-profile (191/980) and intersection
  (156/980) figures recorded in the spec. Also recorded: the path is selection-triggered, exactly
  as v1 (pinning a goal technology for persistent display is a deferred QOL feature, explicitly
  out of scope for the first renderer); a tripwire diagnostic
  (`diagnostics.unresolvableResearchPaths`) for the "target looks researchable but has no route"
  case that has zero real occurrences today. Real worked-example validation against the user's own
  v1 bug report: `tech_mega_engineering` for regular/mechanical/non-nomadic recomputes to exactly
  **74,750** (v1's reported figure); nomadic correctly routes through Arkship Mastery instead of
  the `is_nomadic = no`-gated Starbase line (**99,750**, higher — correctness, not flattery);
  bio-shipset correctly routes through Stingers with Battleships excluded as locked (**73,750**).
- **Stage 3 toolchain foundation is built** (later session): `client/` — TypeScript + PixiJS +
  Vite, no rendering logic yet (explicitly out of scope for this session; see spec/00-overview.md
  for what Stage 3 actually renders). **Node/npm now exist in this environment**, installed
  user-level via Homebrew/linuxbrew (`/home/linuxbrew/.linuxbrew`, owned by the working user, no
  root at any point) — CLAUDE.md's and `tools/generate_typescript_types.py`'s prior "no Node/npm
  toolchain in this environment" notes are now historical, not current. **A first attempt to set
  up headless-browser verification via `npx playwright install --with-deps chromium` tried to
  shell out to `apt-get` as root and was abandoned mid-session** (per-user instruction — it failed
  harmlessly here since this host has no `apt-get`, but the attempt itself was wrong regardless of
  whether it succeeded); the corrected, fully user-level equivalent (`npx playwright install
  chromium`, no `--with-deps`, browser binary in `~/.cache/ms-playwright/`) was used transiently
  for verification only and was never added to `client/package.json` — confirmed by a full
  `rm -rf node_modules && npm install` reproducing the working toolchain from the committed
  lockfile alone with zero trace of it.

  **Reproducibility, pinned properly**: `client/.nvmrc` (`26.7.0`, the exact version everything
  was verified against) for `nvm`/`fnm`/`actions/setup-node`'s `node-version-file`;
  `client/package.json`'s `engines.node` (`>=22`) as a looser compatibility floor. No
  `npm install -g` anywhere — every tool (`typescript`, `vite`) is a `devDependency`, run via
  `npm run <script>` or `npx`.

  **`tsc --noEmit` against `schema/generated/dataset-types.ts`: zero errors**, verified three ways
  — as part of the client project's full compile (confirmed via `tsc --listFiles` that the file is
  actually type-checked, not silently excluded), standalone in isolation under
  `--strict --exactOptionalPropertyTypes --noImplicitOverride --noPropertyAccessFromIndexSignature`
  (stricter than the project's own baseline `tsconfig.json`), and by importing/using several of
  the generated types (`BaseDataset`, `GeometryRef`, `EmpireOverlay`) in real, working client code.
  `tools/generate_typescript_types.py`'s hand-written generator produces valid, well-typed
  TypeScript — a genuine negative result (the module's own docstring expected possible real
  problems; there weren't any), not a gap in the check. `.github/workflows/typecheck.yml` runs
  this on every change to `client/**` or `schema/generated/dataset-types.ts`.

  **Real dataset wired in, content-hashed, and verified against a real browser.**
  `tools/build_dataset.py` runs the full Stage 2 pipeline against `vendor/` and writes all five
  artefacts + geometry side-files into `client/public/dataset/`, every filename content-hashed
  (`<name>.<sha256[:10]>.<ext>`) except two stable, unhashed entry points: `manifest.json` — the
  cache-busting mechanism GitHub Pages needs, since its cache headers aren't configurable (same
  pattern Vite's own `index.html` → hashed-JS-bundle already uses) — and `integrity.json` (see
  D-15, below). `client/src/dataset.ts` fetches `manifest.json` first, then every other artefact
  only through the path it names — `base-dataset.json`'s own `geometry.nodePositions`/
  `edgePolylines`/`iconAtlases[].webp`/`.png` fields are set to their files' final hashed names
  BEFORE `base-dataset.json` itself is serialised and hashed, so every reference is always
  correct. **Real corpus, not synthetic**: 980 technologies, 989 edges, 12 empire overlays, 980
  detail payloads, search index, diagnostics.

  **Verified against a REAL headless browser** (Chromium via a transiently-installed
  `playwright-core`, never added to `client/package.json` — confirmed by a full
  `rm -rf node_modules && npm install` reproducing the working toolchain with zero trace of it):
  fetched `manifest.json` → `base-dataset.json` → both geometry side-files → a sample empire
  overlay → a real WebP icon atlas texture, decoded and drawn as a PixiJS `Sprite`, all through
  the real Vite dev/preview server AND a manually-simulated GitHub Pages project-subpath layout
  (`http://localhost/Gigastructural-Engineering-Tech-Tree/`, matching deploy-spike's own base-path
  finding) — 980 technologies, 989 edges, 1,960 float32 node-position values (980 × 2, exactly as
  expected, all finite/non-NaN — the little-endian `struct.pack("<Nf", ...)` packing round-trips
  against a real browser's `Float32Array`, not just Python's own encoder). One harmless console
  message (`favicon.ico` 404 — no favicon was added; cosmetic) was the only anomaly found.

  **D-15 (spec/decisions.md, later session): deploy model is local build, manual deploy — a
  PERMANENT constraint, not an interim gap.** The dataset cannot be built in GitHub Actions at
  all: vanilla Stellaris requires a Steam account that owns the game, so CI-side building would
  mean storing real Steam credentials as a secret (security/ToS exposure) or redistributing
  extracted game files (foreclosed outright by this project's own never-redistribute-vendor-
  content rule). No automation closes this — investigated and confirmed directly (a prior
  session's vendoring-automation investigation), not assumed. Consequently:
  - `client/public/dataset/` is **gitignored**, reversed from this session's own earlier
    decision to commit it. It's derived from vendored third-party content (a real, if lesser,
    redistribution question than `vendor/` itself); git would retain every ~7–18 MB version
    permanently; and a committed artefact can silently disagree with the pipeline commit that
    claims to produce it — exactly the staleness problem content-hashed filenames exist to
    prevent, reintroduced one layer up. Confirmed nothing from the prior session was ever
    actually staged/committed (`client/` was entirely untracked the whole time).
  - `tools/deploy_local.sh` (new) orchestrates the local side: build dataset, build client, zip
    `client/dist/`, publish it as a GitHub Release asset via the `gh` CLI, print the exact
    `gh workflow run` command. **Not executed for real this session** — creating a live Release
    is a "visible to others" action, left for the user to run themselves.
  - `.github/workflows/deploy.yml` is now `workflow_dispatch`-only, takes a `release_tag` input,
    downloads that release's `dist.zip`, sanity-checks it, and deploys it via the ordinary
    `actions/upload-pages-artifact`/`deploy-pages` steps — it builds nothing itself. Confirms
    Pages CAN deploy a build that happened elsewhere; the trade is a weaker integrity story than
    a full CI build (see below), stated honestly rather than glossed over.
  - `client/public/dataset/integrity.json` (unhashed, stable name): the pipeline commit SHA
    (+ dirty-tree flag), `vendor/manifest.json`'s per-source provenance (Vanilla's
    `game_version`; each mod's pinned commit/Workshop ID/content hash), which sources were
    loaded, and a sha256 checksum of every other artefact. **States provenance, does not verify
    it** — a mismatch between deployed bytes and claimed provenance is detectable (recompute,
    compare); a mismatch between the claimed commit and what a human actually ran is not, beyond
    trusting whoever ran `tools/build_dataset.py`. Never presented as CI-grade auditability.
  - Options considered and rejected as the PRIMARY model: (A) a private artefact store the CI
    workflow fetches from — still needs a human to build+publish, so it's just the chosen model
    plus an extra hop and, usually, another credential; (C) CI builds without ACOT/AoT — doesn't
    solve vanilla either way, and would make the CANONICAL deployed site quietly different
    (977 nodes, not 980) by default, the wrong default for real users. Kept as a genuinely useful
    LOCAL option instead (below).

  **Icon atlases now actually written — closed a real, previously-unnoticed gap.**
  `tools/build_dataset.py` never wrote atlas image bytes at all before this session:
  `base-dataset.json` referenced `technologies_0.webp` etc. and none of those files existed
  anywhere — the site could not render a single icon. Fixed: every sheet (`ctx.tech_sheets` +
  `ctx.perk_sheets`) is now encoded to both WebP and PNG (`pipeline.icons.pack.encode_webp`/
  `encode_png`), content-hashed, and `base-dataset.json`'s `iconAtlases[].webp`/`.png` fields are
  rewritten to the real hashed paths before that document is itself hashed. **Real measured
  total: 4,826,990 bytes WebP (4.60 MB) + 5,994,998 bytes PNG (5.72 MB) = 10,821,988 bytes
  combined** across 3 sheets (`technologies_0` 1008×2016, `technologies_1` 1008×1468,
  `ascension_perks_0` 504×384) — matches the figure a prior session's vendoring-automation
  investigation had already measured directly, confirming consistency. Verified end to end in
  the real headless-browser check above, not just "file exists on disk": a real `Assets.load()`
  fetch of the hashed WebP, a real `Texture`/`Rectangle` tile crop, a real `Sprite` drawn to the
  PixiJS canvas.

  **ACOT/AoT-absent builds: loud, specific diagnostic, not a generic warning.** A prior session's
  vendoring-automation investigation found building without ACOT/AoT yields **977 rendered nodes,
  not 980 − 7 = 973** — the 7 real ACOT/AoT-`requiresMods` technologies correctly disappear, but 4
  vanilla technologies ACOT overwrites (`tech_adaptive_combat_algorithms`, `tech_biomechanics`,
  `tech_titan_hull_1`, `tech_titan_hull_2`) are, perhaps surprisingly, **not themselves rendered
  in the FULL build at all** (their ACOT-overwritten form falls outside the P-16 closure,
  confirmed directly) — without ACOT they revert to vanilla content, which IS unconditionally
  rendered, and reappear. `pipeline.dataset_emit.build_diagnostics` now reports this specifically:
  `vendorSourcesLoaded`, `placeholderTechnologiesAbsent` (the exact 7, each naming which source
  they need), `vanillaTechnologiesRevertedFromAcotOverwrite` (the exact 4, each flagging whether
  the reversion is a real content difference — see the user-supplied domain note below).
  `tools/build_dataset.py` also prints a loud console banner when ACOT/AoT is missing. Both lists
  are maintained constants (`PLACEHOLDER_TECHNOLOGIES_REQUIRING_ACOT_AOT`,
  `VANILLA_TECHNOLOGIES_ACOT_OVERWRITES`), deliberately NOT dynamically derived — 3 of the 7
  placeholders are reached only through ACOT's own internal prerequisite chains, invisible
  without ACOT loaded, so nothing present in a reduced corpus could ever discover them — each
  re-verified against the real, full corpus by its own regression test
  (`tests/test_dataset_emit.py`), so a future re-vendor that changes one of these 11 keys fails a
  test rather than silently going stale. **User-supplied domain context**: most of ACOT's
  overwrites of vanilla technologies only add modifiers, invisible to this tool's display either
  way (`tech_adaptive_combat_algorithms`/`tech_biomechanics`,
  `contentDiffersFromOverwrite: false`) — the titan hull technologies are the documented
  exception, where ACOT's content materially differs (`contentDiffersFromOverwrite: true`).

  **Base-path resolution re-verified, not just inherited from the spike's old finding**: built
  `client/dist/`, served it under a locally-simulated `/Gigastructural-Engineering-Tech-Tree/`
  path prefix (not domain root), and confirmed the real headless-browser check above still passes
  identically — `vite.config.ts`'s `base: "./"` (relative, matching the spike's own lesson) plus
  every hand-written `fetch()` call using a relative path (`./dataset/...`) is what makes this
  work; an absolute leading-slash path would have passed locally at a domain root and silently
  broken here, exactly the failure mode the spike existed to catch before Stage 3 built on it.
