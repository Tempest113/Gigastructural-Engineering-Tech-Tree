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

**D-18 (`spec/decisions.md`) — the closure is DEPTH-1, not a full transitive closure. This
supersedes this section's original justification below the line, kept only as historical
record of what was superseded and why.** The tree renders vanilla and Gigastructures technologies
unconditionally. An ACOT/AoT technology renders only when a rendered (vanilla/Gigastructures)
technology names it **directly** in its own `prerequisites` block — no recursion. An ACOT/AoT
technology reachable only through ANOTHER ACOT/AoT technology's own prerequisite chain does not
render, even if that intermediate technology does. This is a build-time computation, not a
user-facing filter — there is no checkbox and no mod-set URL state. Mod requirement is a
`requiresMods: string[]` field rendered as a card badge (`ACOT`, `AoT`) — distinct from gates and
from prerequisites — that communicates the requirement without toggling visibility.

**The accepted cost, real and named, not hypothetical**: exactly 3 off-tree prerequisite links in
the real corpus, all ACOT→ACOT — a rendered ACOT technology whose own card names a prerequisite
that itself has no node. `tech_dark_matter_power_core_ae` ("Alpha-class Enigmatic Power") →
`tech_precursor_design` ("Precursor Databank Analysis"); `tech_dark_matter_power_core_dm`
("Delta-class Enigmatic Power") → `tech_dark_matter_power_core_enig` and → `tech_mine_dark_energy`.
The user reviewed this exact set (surfaced by a reported over-inclusion complaint naming the first
pair) and chose depth-1 over both the original full-closure rule and a considered middle option
(rendering an out-of-closure prerequisite as a distinct stub/ghost node — rejected as
disproportionate to 3 links). `tests/test_rendering_scope.py::
test_depth_one_closure_off_tree_links_match_the_accepted_set` pins this exact 3-link set; a
corpus refresh that creates more fails it loudly rather than silently degrading chain completeness
further. Real measured effect: rendered node count 980 → 977, edges 989 → 984 (5 fewer
`prerequisite` edges; `alternative`/`potential-gate` unaffected). Canvas dimensions and densest
(row, band) cell were UNCHANGED by D-18 itself (30,840 × 9,736px at the `subgrid_width=4` in
effect when D-18 shipped, `voidcraft`×T5=47) — none of the 3 dropped technologies was in the
densest cell or its own band. (Canvas is now 29,670 × 13,448px under `subgrid_width=6`, the
user's later D-17 pick — see D-17's own record; the densest cell is still `voidcraft`×T5=47,
unaffected by either change.)

**Original justification, superseded by D-18 above, kept for history**: the tree used to render
ACOT and AoT technologies wherever they fell in the **rendering-scope closure** of a rendered
technology — `prerequisite` edges only, pooled across all twelve profiles, so a rendered
technology's prerequisite chain was never broken by an invisible gap — with an ACOT/AoT technology
having no rendered descendant excluded as a node. The user reported this over-included: an
ACOT/AoT technology reachable only through another ACOT/AoT technology, itself required by nothing
actually rendered, still appeared. D-18 replaced this with depth-1.

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
977 at last count, D-18's depth-1 ACOT/AoT closure, down from 980), not the full 1,879 canonical
technologies** — see `spec/decisions.md`'s D-10
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

The two denominators (all-1,879-canonical vs. rendered-977) give materially different, and
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

### Gates

**Built (gate-classification session).** `pipeline/gate_patterns.py` classifies four registered
trigger patterns into the schema's `Gate` shape, layered on top of P-14's universal
`potential-gate` edge extraction — never removing or altering an edge, only adding a badge.
Real corpus counts: `has_ascension_perk` (22 technologies), `has_technology` (22 technologies,
25 instances — one-to-one with the 25 `potential-gate` edges), `has_gigastructural_constructs`
(9), `has_galactic_wonders` (14) — 70 gate instances total over 60 technologies, 10 of which
carry more than one instance (7 crossing two distinct mechanism types, 3 more carrying two
`has_technology` targets each).

**Curation is at the MECHANISM level, not the occurrence level.** Once a pattern is registered,
every real occurrence badges — there is no further per-technology editorial filter. See
`spec/P-03-gates.md`'s "Curation is at the MECHANISM level" note for the full reasoning (the
alternative, a hand-curated per-occurrence subset, would be one more hand-maintained surface like
the crisis-faction/flag/name override files, for no evidenced benefit at this corpus size).

`has_gigastructural_constructs`/`has_galactic_wonders` are Gigastructures' own scripted-trigger
wrappers, not literal `has_ascension_perk` checks — confirmed by direct inspection, not assumed
from the names: `has_gigastructural_constructs` is a 1:1 wrapper for `ap_gigastructural_
constructs`; `has_galactic_wonders` is an `OR` of the base `ap_galactic_wonders` perk plus 3
DLC-ownership-variant perk IDs unlocking the same thing, displayed under the single canonical
base id (the only one of the four that's actually vendored/localised). Both wrappers carry an
`is_ai = yes` AI-only override branch the registry deliberately does not model, matching
`pipeline.availability`'s existing treatment.

**Zero interaction with availability evaluation.** All four registered keys were already in
`pipeline.availability.EXCLUDED_KEYS` (an identity-element state) before this module existed —
gate classification adds only display metadata.
`tests/test_gate_patterns.py::test_gate_leaf_keys_matches_availabilitys_excluded_keys_exactly`
pins the two lists staying in exact sync, so a future change to either without the other fails
loudly. D-10's worst-case profile-dependent uncertainty is unaffected: still 33/977 (3.37%),
asserted against the real corpus build
(`tests/test_dataset_emit.py::test_gate_classification_leaves_d10_uncertainty_unchanged`), not
assumed.

Ordering (D-3): ascension-perk gates outrank technology gates; index 0 is the primary gate,
the only one the node card renders (spec's "where space permits, additional gates render as
compact secondary badges" for a technology with more than one gate is not built — only 10/977
real technologies have a second gate instance). The popup shows every gate in the ordered list,
each with its resolved icon and localised "Needs `<name>`" label.

The spec's original "Tetradimensional Engineering" example of one technology gating another was
checked against the real corpus and found wrong — `giga_tech_tetradimensional_engineering`
gates several ascension perks, not any technology's `potential` block. Corrected in
`spec/P-03-gates.md` to a real example (`giga_tech_amb_supertensiles_acot_alpha` →
`tech_dark_matter_power_core_ae`), with the original example's refutation recorded rather than
silently dropped.

### Tiers

Tier range is **not** bounded. ACOT pushes tiers to T9 and beyond. Enumerate tier bands from
the data. No fixed upper bound anywhere in layout, LOD, or band labelling. Measured against the
real 977-node rendered corpus (D-18): 10 declared-tier bands (T0-T9) plus the terminal Repeatables band.

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
every rendered node's declared tier, not assumed correct; pre-D-18 figures, not re-verified
against the 977-node closure since none of the 3 dropped ACOT technologies belonged to the
inline_script/@variable-tier subsets this audit tracks): of 980 rendered nodes, 930 (94.9%)
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

**Superseded by D-16's row re-axis (`spec/decisions.md`) — "background encodes research area" is
no longer the per-card rule.** Colour and pattern now encode the ROW, not the card: an
area-coloured header chip on a category row, faction colour and pattern as row backing on a
faction row, cards themselves neutral dark. Rare/dangerous outline and badge remain the one
per-card exception below, unchanged by the re-axis. **Research area is deliberately NOT
colour-encoded inside a faction row** — a technology that is both crisis-sourced and, say,
`voidcraft` shows its faction's colour, not its area's, once it's in that faction's row. This is
an accepted loss, stated explicitly so it isn't rediscovered as a bug later: faction membership is
mutually exclusive with category under D-16's row model (a technology is in exactly one row), so
there is no second colour channel left to carry area once a technology is in a faction row — the
row itself only has one colour to give. (Client rendering itself is a later slice; this section
states the rule the renderer must follow, not that it's built yet.)

Outline encodes research area unless the tech is rare or dangerous, in which case that takes
priority. Dangerous outranks rare. A tech that is both gets a 45° split outline, dangerous red on
the top-left half. (This per-card outline rule is unaffected by the row re-axis — it's about the
CARD's own outline, not its background.)

Colour is never the sole carrier. Rare and dangerous each also get a card badge. The LOD shedding
sequence is one shared table (spec/S-03): gate label and repeatable shed first (<60% zoom), then
rare (<35%), then gate icon and tier badge (<20%), then dangerous last of the badges (<10%,
deliberately kept longest since it's safety-critical), then crisis patterns go solid (<7%), then
the node reduces to a flat coloured block (<5%). Rare and dangerous do **not** shed together, and
neither sheds "at the same threshold as the gate label" — see spec/S-03 for the authoritative
table rather than restating specific thresholds here.

Crisis factions: Aeternum, Blokkats, Compound, Sirenalia, Katzenartig Imperium. Faction
assignment is derived from tech ID, then from `potential`/prerequisites, then from a checked-in
manual override file for the remainder. **This derivation (`pipeline/crisis_faction.py`) is
completely unchanged by D-16** — D-16 only changed what CONSUMES the classification (row
selection instead of lane selection); see D-16 in `spec/decisions.md`.

**Connector colour (P-8) is a single neutral colour for every edge, not tail-classification
colour** — `spec/P-08-connectors.md` is corrected to match the shipped Stage 3 slice 3
implementation (`client/src/tokens.ts`'s `EDGE_COLOR`); see that spec file and CLAUDE.md's
"Slice 3 — edges" bullet for the original decision and reasoning.

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
truthfully) and the "Prerequisites"/schema sections for how a null `cost` (5/977 rendered nodes as
of D-18 — a later correctness pass resolved 10 of the originally-reported 15 via their `cost`
block's own `factor` sub-field, see `pipeline.dataset_emit._resolve_cost`'s docstring —
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
- **The pipeline owns all geometry; the renderer consumes emitted positions and never recomputes
  them from a parallel formula.** Any renderer-side value that is derivable from emitted geometry
  (row/band extents, a cell's populated width, anything of that shape) MUST be derived from the
  real emitted positions (`nodePositions`/`edgePolylines`, per `00-overview.md`), never
  reimplemented client-side from the same inputs `pipeline/layout.py` consumes. Found the hard
  way: `client/src/main.ts` once re-derived row/band geometry via its own copy of
  `pipeline/layout.py`'s wrap/width formulas, and D-17's same-band depth-slot fix silently
  desynced it — row panels, tier tints and cell labels drew nowhere near their actual cards, with
  no error, no failing test, no warning, caught only by a headless screenshot. Two independent
  implementations of the same geometry WILL drift the moment either one changes, and nothing
  forces them to change together. The permanent fix, and the rule going forward: derive from the
  real positions (min/max over the emitted `nodePositions`, grouped by row/band), so client and
  server geometry cannot drift apart again regardless of how the underlying layout formula changes
  in the future — not a periodic re-sync. **Audited for other instances of this pattern**: the
  severe form (recomputing a multi-step DERIVED formula that can produce a different value than
  the pipeline's own) is now eliminated for row/band geometry, the only place it existed. What
  remains is a milder, harder-to-avoid form: a set of mirrored SCALAR constants
  (`CARD_WIDTH`/`CARD_HEIGHT`, the gutter constants, `SUBGRID_WIDTH`, `AREA_ORDER`,
  `FLOATS_PER_EDGE_POLYLINE`, `MIN_STUB`) that must still be kept numerically in sync with
  `pipeline/layout.py`/`pipeline/geometry.py` by hand, since the dataset schema doesn't carry them
  as data. Their blast radius if they drift is smaller than the row/band bug was — most now feed
  only the degenerate zero-population-row/band fallback path or are diagnostic-only (`MIN_STUB`,
  used only by `checkMinStubLength`). `CARD_WIDTH`/`CARD_HEIGHT` are the one genuinely
  load-bearing pair, since they size the actual card draw call and the dataset carries corner
  positions, not card dimensions. Not fixed this session (would mean adding card dimensions to the
  schema) — flagged as a scoped follow-up rather than silently left looking fully closed.
- **A second, DIFFERENT defect class produced the same visible symptom (rows overlapping) a later
  session, and must not be confused with the parallel-formula bug above.** The screenshot-review
  session's Item 4 (short-sub-grid-column vertical centring, `pipeline/layout.py`) introduced a
  hard regression: `column_member_count`, a dict tracking each sub-grid column's own member
  count, was keyed by `(row_id, col)` alone. `col` is BAND-RELATIVE — `depth_slot_start[(band_
  index, depth)]` resets its own cursor to 0 for every band — so col 0 in one band and col 0 in a
  LATER band of the SAME row are physically different columns (different x) but shared the same
  dict key, silently SUMMING their member counts into one entry. That corrupted count could
  exceed the row's real max (`row_row_counts[row_id]`) and drive the centring offset NEGATIVE,
  shifting a column's cards upward past row 0 into the row above — real corpus example:
  `column_member_count[('voidcraft', 0)]` corrupted to 37 against a real `row_row_counts` of 6,
  producing `giga_tech_birch_world_1` at row **−16**. **This is a plain dict-keying bug (a missing
  discriminator field), not a parallel-geometry violation** — nothing client-side re-derived
  anything; `client/src/main.ts` correctly derived row panels from the (corrupted) emitted node
  positions exactly as the rule above requires, and faithfully reproduced the bug rather than
  masking or independently causing it. Confirmed directly (not assumed) that this rules out the
  parallel-geometry rule as a second cause here. Fixed by keying on the full `(row_id, band_index,
  col)` triple, which is unique by construction, plus a same-turn `assert centre_offset >= 0` in
  `pipeline/layout.py` itself as a second line of defence. **The real lesson, and why it reached
  the user**: the existing test suite stayed fully green through this regression — canvas
  dimensions were genuinely unaffected (row HEIGHT is computed from `row_row_counts`, set in the
  first pass and never touched by the buggy second pass; only individual cards' position WITHIN
  their row was corrupted), and nothing asserted the actual invariant that matters (no two rows'
  card-occupied extents may intersect, no node's row index is ever negative). A green suite proved
  self-consistency, not correctness — the same lesson D-17's unbounded-stacking bug already taught
  this project once, now recorded as a second occurrence.
  `tests/test_layout_corpus.py::test_no_row_overlaps_and_every_card_within_its_own_row_bounds`
  (real corpus) and `tests/test_layout.py::test_no_row_overlaps_when_the_same_row_spans_multiple_
  bands` (fast synthetic regression case) are the missing invariant, added after this regression,
  each proven capable of failing against the actual broken code before being trusted on the fix.

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

Full build history — every decision, measured figure, and defect found in past sessions — moved
to `docs/BUILD-LOG.md` in a reconciliation session (CLAUDE.md had become an append-only session
log rather than a list of open items; see that file's own header note). This section states only
what is genuinely still open, with a pointer to detail elsewhere. Locked, load-bearing decisions
live in this file's own body above and in `spec/decisions.md`, not here.

- **Gate classification (P-3) is now closed** — `pipeline/gate_patterns.py` classifies real gate
  data into `gates`; see this file's own "Gates" section above for the full account. Left here
  only so a future session's memory of "this was still open" gets corrected on sight.
- **P-12.9 (research path) is specced but not implemented, and is the next open work.** The
  feature v1 failed at: v1's implementation was profile-blind traversal (didn't vary by empire
  type) and flattened `OR`-group (`alternative`-edge) branches instead of choosing the cheapest
  one. `spec/P-12.9-research-path.md` is the normative spec — read it, then survey before
  implementing (see HANDOFF.md's next prompt). Note: the hover/selection slice's ancestry/
  dependent highlight is explicitly NOT this algorithm (it's a structural, profile-invariant
  closure over all edge kinds; P-12.9 is a per-profile cheapest-`OR`-branch resolution) — see
  `client/src/main.ts`'s `computeAncestryAndDependents` for the distinction stated in code. Gate
  classification (P-3, above) is now closed, so P-12.9's chain-completeness accounting can reason
  about gates as a distinct concept from prerequisites, per that section.
- **`subgrid_width` is settled at 6** — the user's pick from D-17's 4/6/8/12 trade-off survey
  (`spec/decisions.md`). Not open any more; left here only so a future session's memory of "this
  was still open" gets corrected on sight.
- **The `EmpireProfileIndex` parallel-formula gap (this file's own "pipeline owns all geometry"
  rule, generalised beyond geometry) is now closed** — the base dataset emits `empireProfileAxes`
  (axis order, values, strides, `totalProfileCount`; `schema/common.schema.json`'s
  `EmpireProfileAxes`, built by `pipeline.dataset_schema.empire_profile.
  build_empire_profile_axes`), and `client/src/empireProfile.ts` derives its index purely from
  that emitted data — no hardcoded stride or axis list survives client-side. Left here only so a
  future session's memory of "this was still open" gets corrected on sight.
- **The D-18 off-tree-prerequisite gap is now closed.** `pipeline.rendering_scope.
  compute_off_tree_prerequisites`'s 3 accepted links now surface in each affected technology's own
  detail payload (`offTreePrerequisiteNames`) and render in the popup under "Also requires," with
  a fixed client-side note that the name is outside the rendered scope — see
  `spec/P-16-mod-requirements.md`'s acceptance criteria, no longer flagged as a gap there.
- **`appliesToEmpireTypes` is unconstrained on every edge** — a real per-edge empire-type
  constraint extractor is new scope beyond what P-14 built; `activeEdgeIds` is therefore every
  edge index for every profile (confirmed directly against a real overlay, screenshot-review
  session: 984/984, `set(activeEdgeIds) == set(range(len(edges)))`, not just documented as a
  theoretical gap).
- **Tech-swap display substitution (`swapMappings`, D-14) is emitted but consumed nowhere in the
  client** (screenshot-review session finding, confirmed by grep — zero references in
  `client/src/`). A card, and the popup's Prerequisites/Dependents lists, always show a
  technology's BASE name/icon regardless of the selected profile — real example, confirmed in
  the corpus: `tech_zero_point_power` ("Zero Point Power") swaps to `tech_bio_zero_point_power`
  ("Zero Point Metabolism") for `country_uses_bio_ships = yes`, but a bio-shipset profile never
  sees the swapped name anywhere today. `swapMappings` only ever carries name/icon/area/category
  substitution — never prerequisites, never availability, both of which are already correctly
  profile-scoped elsewhere (`availabilityMatrix`/overlay `availability`); a swap NEVER changes
  which nodes are prerequisites, only what one node is called. 123 distinct rendered technologies
  carry at least one axis-expressible swap active for some profile (0 for the default
  regular/mechanical/non-nomadic profile, up to 123 for machine_intelligence/biological/yes —
  real per-profile counts, not estimated).
- **The popup's "Prerequisites"/"Dependents" lists pool all three edge kinds
  (`prerequisite`/`alternative`/`potential-gate`) unlabelled and unfiltered by profile**
  (screenshot-review session finding) — `client/src/main.ts`'s `prereqNames`/`dependentNames`
  filter `base.edges` by direct from/to adjacency with no `kind` check at all. Real corpus
  example: `tech_mega_engineering`'s "Prerequisites" list shows all 5 of its edges as one
  undifferentiated list — the one true `prerequisite` (Zero Point Power) alongside all 4
  `alternative` OR-group members (Arkship Mastery, Battleships, Citadel, Stingers) — with no
  indication only ONE of the four is actually needed, and no filtering by which one the selected
  profile can reach. This is the same OR-branch-flattening failure class HANDOFF.md's "Research
  path" section documents as v1's own reported bug, now confirmed present in the POPUP's
  prerequisite list too, not just a hypothetical research-path risk. **A per-branch fix is
  possible from data already emitted, without waiting on the `appliesToEmpireTypes` extractor
  above**: each alternative-branch member's own `availabilityMatrix` entry already correctly
  reflects per-profile reachability (confirmed directly: for `tech_mega_engineering`'s 4
  alternatives at regular/mechanical/non-nomadic, Battleships and Citadel read `available`,
  Arkship Mastery and Stingers read `locked` — matching expected nomadic/bio-shipset gating
  exactly) — filtering an `alternative` group's display to non-`locked` members for the selected
  profile does not require the edge-level constraint extractor, only a client-side change plus
  labelling edges by kind instead of pooling them.
- **`repositoryLink` isn't live-validated** (no network access at build time) and its `lineRange`
  uses the block's start line for both ends (the AST doesn't track an end-of-block line).
- **Middle-click isolation (P-7) is fully specced (`spec/P-07-isolation.md`) and entirely
  unbuilt** — confirmed on request, screenshot-review session (a user tried middle-click and got
  ordinary left-click selection behaviour instead, since no session has ever implemented it).
  Spec requirement, in full: middle-click (or long-press ≥400ms on touch, P-9) isolates a node
  together with its direct prerequisites/unlocks (user-adjustable depth, default 1 hop, with a
  full-closure option), traversing **all three edge kinds** distinctly styled per P-8 — this
  deliberately differs from the research path (P-12.9), which is prerequisite-edges-only.
  Dimming/hiding is a visibility mask over the static layout (never a re-layout, P-4's precedent),
  exitable via a labelled control and `Escape`, with persistent on-screen state naming the
  isolated technology. Adjacency lists (forward/reverse, per edge kind) must be precomputed in the
  dataset so traversal is O(1) per node, never a full edge-set scan, to stay inside P-10's 100ms
  interaction budget. Not started this session — left here as a real, scoped, ready-to-build
  feature, not a vague future idea.
- **No pipeline-test CI workflow exists** — `pytest` still runs manually/locally only.
- **`tools/collect_vanilla.py`'s GitHub-fetch-and-pin automation for Gigastructures, plus a
  scheduled CI staleness check, is still unbuilt** — see this file's "Source data" section above
  for the full context; the current manual pin is a deliberate stopgap, not a placeholder waiting
  passively to be replaced.
- **Pattern tile for Blokkats** needs tracing to clean SVG from the supplied flag image — the
  current herringbone motif is a procedural placeholder, not traced art.
- **Sirenalia's accent shade and Katzenartig Imperium's chevron pattern are both flagged
  provisional** in `client/src/tokens.ts`'s own comments — Sirenalia's real geometry (curved wave
  bands) was ported from v1, but its exact accent colour is still a placeholder; Katzenartig has no
  in-game reference at all and its pattern is Claude's own inference, not described art.
- **`potential-gate` edges' long-span (up to 5-band) backward routing** was left `TODO(Stage 3)`
  when P-8 was written, before a real rendered canvas existed to design against — re-check whether
  the v1-style router + gutter-router fallback (see `docs/BUILD-LOG.md`'s rendering section) has
  since made this moot before treating it as still open.
- **ΔE2000/WCAG mechanical colour checks are still unbuilt** — S-1's own CI-enforced acceptance
  criterion (pairwise contrast across the full token set, including the new `RARE_COLOR`/
  `DANGEROUS_COLOR` badges-slice additions). Every colour token is a first concrete pick, checked
  by eye only.
- **A real, previously-open gap, now closed**: the ACOT/AoT closure rule (depth vs. full
  transitive closure) was surveyed, decided (depth-1), and implemented as D-18
  (`spec/decisions.md`) — no longer open. Left here as a pointer only in case a future session's
  memory of "this was still open" needs correcting.
