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

**Ascension perks are gates, not profile facts — CORRECTED (a later session, "Ring Segment /
ascension-perk locking" session).** The original wording above was refuted by real corpus content
(Galactic Wonders is genuinely unobtainable for nomadic empires) and by the user's domain
knowledge, and is kept struck through only as the historical record of what was superseded:
~~A perk-gated tech always displays its gate. The tree shows what you would need; it never assumes
you have it.~~

**The corrected rule is a distinction, not a reversal:**
- **WHICH perk a player chooses remains a free choice, never a profile fact.** A perk-gated
  technology still always displays its gate rather than assuming the player has or hasn't picked
  it — this half of the original rule stands unchanged.
- **WHETHER a perk is obtainable AT ALL for an empire type is a real fact, when the perk's own
  `potential` carries a genuine axis constraint.** A technology gated behind a perk that is
  structurally impossible for a profile is genuinely LOCKED for that profile, not merely gated —
  the same as any other axis-impossible technology.

Implemented automatically (a full corpus survey, not a hand-curated table):
`pipeline.availability.set_perk_potentials` registers every ascension perk's own winning
`potential` block; `_evaluate_leaf`'s `has_ascension_perk` branch evaluates the referenced perk's
potential against the current profile through the SAME evaluator, and only turns the leaf into a
real `FALSE` when that sub-evaluation is a definite `LOCKED` (never for `UNCERTAIN` — a perk with
residual undecidable conditions stays gate-only, exactly as before). **Real corpus: 21 perks are
cleanly axis-restricted** (`ap_wanderlust`/`ap_hydrocentric`/`ap_eternal_vigilance(_nomads)` on
`is_nomadic`; `ap_synthetic_age`/`ap_machine_worlds`/`ap_mechromancy`/`ap_one_vision` on
`is_machine_empire`; `ap_organo_machine_interfacing`/`ap_hive_worlds` on `is_hive_empire`;
`ap_lord_of_war`/`ap_xeno_compatibility`/`ap_arcology_project` on `is_regular_empire`;
`ap_gigastructural_constructs`/`ap_qso`/`ap_vast_expanses`/`ap_celestial_printing`/
`ap_supermassive_ehof`/`ap_master_builders`/`ap_galactic_wonders` on `is_nomadic`; plus 3 perks —
`ap_defender_of_the_galaxy` and the `ap_galactic_wonders_utopia`/`_megacorp`/
`_utopia_and_megacorp` DLC-variant duplicates — found universally unobtainable, either a legacy
pre-Nomads-DLC fallback (`has_nomads_dlc = no`, impossible under this project's all-DLC-owned
assumption) or a superseded perk carrying a literal `potential = { always = no }`, resolved
correctly by the SAME session's `always` leaf fix below). **20 more perks carry a residual
undecidable condition** (compound triggers, mid-game player state) and are deliberately left
gate-only, never guessed at — see `pipeline.availability`'s module docstring for the full list.
A genuine cross-perk cycle exists in the real corpus (`ap_defender_of_the_galaxy` <->
`ap_defender_of_the_galaxy_nomads`, each excluding the other via a `NOR = { has_ascension_perk =
<the other> }` superseded-perk guard) — broken by a recursion guard
(`_perk_eval_in_progress`), not assumed absent.

**A real, necessary correction to `_combine_or` fell out of this fix.** Before a perk-gated leaf
could ever be a real `FALSE`, an `OR` mixing an EXCLUDED (gate-only, presumed-achievable) sibling
with a real FALSE sibling never arose; `_combine_or`'s original rule (ignore EXCLUDED siblings,
decide purely from the rest) then wrongly closed off the whole OR whenever the achievable sibling
was filtered away, leaving only the FALSE one. Real corpus case this fixes:
`giga_tech_ringworld_titanic_1`'s `OR = { has_ascension_perk = ap_galactic_wonders,
has_ascension_perk = ap_galactic_wonders_utopia }` — for a non-nomadic profile the first branch is
open (achievable) while the second is a real FALSE (permanently disabled); the whole OR must read
as still-gated (AVAILABLE), not LOCKED, since the open branch remains live. Fixed: an `OR` whose
non-EXCLUDED children are all FALSE, but at least one child WAS EXCLUDED, now resolves EXCLUDED
(open) rather than FALSE. `pipeline.edge_constraints`'s own, deliberately different sensitivity
mechanism (Disco Moon's masking-avoidance fix) needed the PRE-correction behaviour preserved
exactly, so it now swaps in its own `_legacy_combine_or` copy for the duration of its check —
these are two different questions ("is this technology available" vs. "does this specific
has_technology leaf's value change the outcome") that happen to share underlying code, not one
mechanism that regressed.

See CLAUDE.md's "Gates" section below for the propagation and `add_research_option`-grant
extensions this same finding led to, and the "Trigger evaluation" section for the moved D-10
figures.

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

**977 → 973, a later session, Item 2c (user domain call): a technology whose `potential` block
contains a top-level literal `always = no` leaf is disabled content, not uncertain content, and is
now excluded from the rendered tree entirely** (`pipeline.rendering_scope._is_permanently_
disabled`), rather than rendered locked/uncertain. Real corpus: exactly 4 technologies —
`giga_tech_aeternite_weaponry`, `giga_tech_interstellar_ringworld`, `giga_tech_orbital_elysium`,
`giga_tech_stellar_ring_habitat` (the last two carry `always = no` alongside now-moot dead
siblings, not as a clean singleton the way the first two do — the detector checks any top-level
child, not just a singleton block). Nothing else references any of the 4 as a prerequisite
(confirmed by direct search), so no dangling-edge/off-tree-prerequisite consequence. Real measured
effect: 977 → 973 nodes, 984 → 977 edges (876 prerequisite + 76 alternative + 25 potential-gate;
7 fewer prerequisite edges, the 4 excluded technologies' own outgoing references — alternative/
potential-gate unaffected). Densest (row, band) cell moves 47 → 46 (`giga_tech_interstellar_
ringworld` was a real member of `voidcraft`×T5); canvas 29,670 × 13,448px → 29,670 × 13,332px.
`config/name_overrides.txt`'s `giga_tech_aeternite_weaponry` entry (see "Rules" below) was removed
as dead once its technology stopped rendering, rather than left in place unused.

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

**D-10 splits into two distinct metrics, both computed over RENDERED nodes (973, P-16's closure)**
— see `spec/decisions.md`'s D-10 for the full reasoning; summarised:

- **Profile-dependent uncertainty** — a technology whose state varies by profile. Governed by:
  hard ceiling 10% for any single profile (build fails above it); warn threshold 3% per profile;
  a ratchet (CI fails if any profile's rate rises against its own prior-dataset figure, even
  under 10%).
- **Unconditional uncertainty** — a technology `uncertain` under all twelve profiles identically
  (no axis check anywhere in its trigger structure). Never misleads a user about their specific
  empire — an honest "unknown" reporting a fact outside the axis model. Its own
  data-completeness figure with its own regression ratchet, but **NOT subject to the 10%
  ceiling** — a different quality signal, not a weaker version of the same one.

Always state which of the two denominators (all-1,879-canonical vs. rendered-973) a reported rate
uses — rendered-only uncertainty is *higher* than all-canonical, because Gigastructures' own
content, not unrendered ACOT/AoT bulk, is the concentration point; narrowing ACOT/AoT rendering
scope does not fix a ceiling breach.

**Current real corpus figures (reconciled, latest session, after Item 2b's zero-weight-gate fold-in
below): unconditional 115/973 (11.8%); worst profile-dependent 58/973 (5.96%, over the 3% warn
threshold, under the 10% ceiling); union (uncertain for ≥1 profile) 180/973.** (Pre-Item-2b:
unconditional 31/973 (3.19%), worst profile-dependent 16/973 (1.64%), union 53/973 — see the
"Research weight" section below for the full accounting of what moved and why.) Full move-by-move
history — every intermediate figure and which fix moved it — lives in `docs/BUILD-LOG.md`'s
availability/trigger-evaluation sections; do not re-derive it
from memory, re-run the corpus survey if a figure here looks stale.

**Leaf types the evaluator resolves**, beyond the axis facts (gestalt/authority, shipset,
nomadic) and DLC-ownership ground facts:
- `always` (both `yes` and `no`).
- `has_active_tradition` — TRUE by default except the user-confirmed `tr_genetics*` category
  (unavailable to machine-intelligence empires; the only real corpus occurrence is
  `giga_tech_the_vat`).
- `has_ascension_perk` — resolves through the perk's own registered `potential` (see "Ascension
  perks are gates" above); only ever contributes a real `FALSE` on a definite perk LOCKED result,
  never on UNCERTAIN.
- `has_ancrel` — a literal `host_has_dlc = "Ancient Relics Story Pack"` check (real definition at
  `vendor/stellaris/common/scripted_triggers/00_scripted_triggers.txt:2678`), treated as an
  ordinary DLC-ownership ground fact.
- **Recursive scripted-trigger expansion** (`pipeline/scripted_triggers.py`) — a bare-identifier
  scripted-trigger reference in `potential` (e.g. `giga_can_use_habitables = yes`) is substituted
  with the trigger's real body, recursively, before evaluation — never a second evaluator, never
  new boolean semantics. Any leaf already in `AXIS_FACTS`/`GROUND_FACT_BOOL`/`DLC_NAME_CHECK_KEYS`
  is skipped by expansion unconditionally, so the axis-fact/ground-fact shortcuts for things like
  `country_uses_bio_ships` (also a real scripted-trigger name) are never destroyed by blind
  substitution. `is_ai = yes` branches are stripped (not modelled) during expansion, including
  through a `hidden_trigger` wrapper whose direct children are ALL is_ai-gated. Real corpus: 3,463
  distinct trigger names post-overwrite, zero reference cycles, max reference-chain depth 8
  (`MAX_EXPANSION_DEPTH = 12`, a hard-failure sanity ceiling). One file
  (`zzz_overwrites.txt`'s `has_research_building`) can't be fully expanded (a dynamic `@[...]`
  file-path computation) — zero real-corpus effect, since no rendered technology references it.
- `PROGRESSION_FLAGS_TRUE` (`pipeline.availability`) — `has_country_flag`/`has_global_flag` names
  matching a crisis-faction/story-progression naming pattern
  (`_possible`/`_solved`/`_unlocked`/`_happened`/`_complete`/`_aborted`/`_knowledge`/`_opened`
  suffixes, `encountered_`/`completed_` prefixes) resolve TRUE as a class — every sampled real
  setting site is a genuine `is_triggered_only` country event with no empire-type restriction.
  Real corpus: 64 distinct flag names. Two vanilla L-Gate storyline flags (`l_cluster_opened`,
  `encountered_first_lgate`) are deliberately EXCLUDED from the pattern — their setting sites live
  in vanilla's `events`/`decisions`, which this project doesn't vendor, so resolving them would
  rest on outside-corpus knowledge. `docs/BUILD-LOG.md` has the full outlier list.

**Documented evaluator assumptions**, applied before anything counts as uncertain (each
individually verified against the vendored corpus, never a blanket "assume everything works" —
see `pipeline/availability.py`'s module docstring and `spec/decisions.md`'s D-10 for full detail):

1. Mod-config content-toggle global flags (`has_global_flag` names ending `_forbidden`,
   `_disabled`, or `_OFF`) resolve to their unset default. Flags outside that pattern
   (`compound_invasion_happened`, `l_cluster_opened`, ...) stay genuinely unresolved.
2. All official DLC assumed owned — a literal `has_dlc`/`host_has_dlc` leaf plus a dozen named
   per-DLC scripted-trigger wrappers individually confirmed pure `host_has_dlc` calls
   (including `has_nemesis`/`has_infernals`), plus `has_megacorp` (the DLC-ownership check, NOT
   `is_megacorp`, a real empire-type/civic choice fact outside the 3-axis model, deliberately
   left unresolved). `has_gigastructural_constructs`/`has_galactic_wonders` were checked and
   found to be ascension-perk-gate checks in disguise, not DLC checks — left unresolved here.
3. Not-a-fallen-empire is a ground fact of all twelve profiles.
4. **Mod-content-presence flags** — `has_acot` and `has_global_flag = has_aot_mod` both resolve
   `true` (this deployed tree already assumes ACOT/AoT content is present). Distinct from the
   `requiresMods` card badge (`pipeline.dataset_emit._potential_mod_requirements`), which is a
   separate display mechanism keyed off the same leaf. Real corpus: 4 technologies
   (`giga_tech_amb_supertensiles_acot_alpha/sigma/delta/phanon`).
5. **User-confirmed progression-state flags, one at a time, never a blanket pattern-resolve** —
   `has_country_flag`/`has_global_flag` names gating Gigastructures-internal PROGRESSION state,
   distinct from a genuine per-empire-type ELIGIBILITY gate. Only `colossus_project` is confirmed
   (6 technologies, `tech_pk_cracker`/`_godray`/`_nanobots`/`_neutron`/`_shielder`/`_smelter`). A
   larger candidate list (`giga_rings_beh`/`_gar`/`_tit`, `has_arcane_generator`,
   `has_finished_psionic_tradition`, `has_quantum_catapult_insight`, others) is surveyed but not
   resolved — see `docs/BUILD-LOG.md`. This is the one evaluator category that is inherently
   per-flag, never a pattern rule — see `PROGRESSION_FLAGS_TRUE`'s own comment before adding one.

`has_technology` (P-14 prerequisite-graph reachability), `has_ascension_perk` (a P-3 gate), and
`has_gigastructural_constructs`/`has_galactic_wonders` are excluded from boolean combination
entirely — an identity element, not resolved either way, because each is a different mechanism's
job; folding any into `uncertain` would be a category error.

`common/scripted_triggers/` custom calls the evaluator can't expand (a materially larger feature
than what's built beyond the recursive expansion above) and `has_country_flag` (131 occurrences,
82 distinct names, no single resolvable pattern) remain the two biggest levers still left on the
unconditional figure. Leaf shapes deliberately left unresolved, no invented handling: `has_authority`,
`founder_species`, `has_civic` (distinct from `has_valid_civic`), `if = { limit = {...} }`
conditional-effect blocks — real residue, not bugs, see `docs/BUILD-LOG.md` for which are further
resolvable.

### Gates

`pipeline/gate_patterns.py` classifies registered trigger patterns into the schema's `Gate`
shape, layered on top of P-14's universal `potential-gate` edge extraction — never removing or
altering an edge, only adding a badge. **Curation is at the MECHANISM level, not the occurrence
level**: once a pattern is registered, every real occurrence badges — there is no further
per-technology editorial filter (`spec/P-03-gates.md`'s own note has the full reasoning).

**Registered gate kinds and their patterns** (D-3 priority order: ascension perk > origin >
ethics-or-civic > technology — index 0 is the primary gate, the only one the node card renders;
the popup shows every gate in the ordered list):
- `ascension_perk` — `has_ascension_perk` direct, plus two Gigastructures scripted-trigger
  wrappers confirmed by direct inspection, not assumed from naming: `has_gigastructural_
  constructs` (a 1:1 wrapper for `ap_gigastructural_constructs`) and `has_galactic_wonders` (an
  `OR` of the base `ap_galactic_wonders` perk plus 3 DLC-variant perk IDs, displayed under the
  single canonical base id). Both wrappers carry an `is_ai = yes` AI-only override branch,
  deliberately not modelled, matching `pipeline.availability`'s treatment.
- `origin` — `has_origin` direct, plus two 1:1 wrappers (`is_wilderness_empire`,
  `giga_has_frameworld_origin`).
- `ethics_or_civic` — `has_ethic`/`has_valid_civic`/`has_civic` direct, plus two 1:1 wrappers
  (`is_fanatic_spiritualist`, `is_fanatic_pacifist`).
- `technology` — `has_technology` (an engine-builtin alias, `can_research_technology`, was tried
  and then REMOVED — see "Gate-polarity/nested-OR fixes" below, it means something different).

**Zero interaction with availability evaluation** — every registered leaf key is also in
`pipeline.availability.EXCLUDED_KEYS` (an identity-element state), so gate classification adds
only display metadata, never changes an availability result.
`tests/test_gate_patterns.py::test_gate_leaf_keys_plus_not_classified_matches_availabilitys_
excluded_keys_exactly` pins the two lists staying in exact sync.

**11 further `EXCLUDED_KEYS` entries are deliberately NOT gate-classified**
(`pipeline.gate_patterns.NOT_GATE_CLASSIFIED_EXCLUDED_KEYS`) — genuinely compound triggers with
no single clean `refId` (`is_void_dweller_empire`, `has_void_dweller_origin`,
`is_giga_one_planet_origin`, `is_spiritualist`, `is_natural_design_empire`,
`is_beastmasters_empire`, `is_world_forger_empire`), or not origin/civic/ethic-shaped despite the
same "empire-defining choice" character (`is_megacorp` — targets a real 4th authority value
outside the 3-axis model; `is_individual_machine`, `has_genetically_ascended`,
`is_infernal_empire`). These resolve AVAILABLE with no gate badge — see the module's own comment
for the full per-key reasoning. Every new `EXCLUDED_KEYS`/`NOT_GATE_CLASSIFIED_EXCLUDED_KEYS`
entry that is ALSO a real scripted-trigger catalog name must be added to `pipeline.
scripted_triggers._ALREADY_RESOLVED_KEYS` too, or the general trigger expander (see "Trigger
evaluation" above) will blindly substitute its real body and silently undo the exclusion — the
same defect class the `country_uses_bio_ships` regression already taught this project once.

**Icons — reported, not vendored, for origin/ethics_or_civic.** `common/civics`/`common/origins`/
`common/ethics` aren't vendored for any source, so there's no icon file for these two gate kinds.
`Gate.icon` is nullable; the client renders the label alone when null (see "Gate-polarity/nested-
OR fixes" below for why this replaced an earlier, worse fallback).

**OR-context (`alternative`) gates.** A `has_technology`/perk/origin/civic leaf sitting inside a
real source `OR` is marked `alternative: boolean` (`GateMatch`/`Edge.groupId`-style tracking, OR
ancestry independent of negation polarity) — label wording is `"or: <name>"` for an alternative
gate, `"Needs <name>"` only for a genuinely unconditional one. Real corpus: 11/25 (44%) of real
`has_technology`-under-`potential` occurrences sit inside an `OR` (e.g. `tech_torpedoes_1`/
`tech_missiles_1`'s Riddle Escort requirement, non-bio-ship empires already qualify a different
way). A second field, `appliesToEmpireTypes` (nullable `EmpireTypeConstraint`), reuses
`pipeline.edge_constraints`' existing per-edge axis constraint for a `"technology"`-kind
alternative gate backed by a real `potential-gate` edge — the client filters the badge out
entirely for a profile the edge doesn't apply to, rather than showing a misleading requirement.
**Dangling "or:" downgrade**: when a technology's emitted `gates` list ends up with exactly ONE
entry and it's the alternative one (its real OR-sibling isn't itself gate-shaped, e.g. a district
check), it's downgraded to a plain "Needs X" (`pipeline.dataset_emit._downgrade_dangling_
alternative`) — deliberately NOT when `appliesToEmpireTypes` is non-null, where "or:" is correct.
Real corpus: 20 technologies.

**Nested AND-of-OR gates.** `GateMatch.group_id` (mirrors `Edge.groupId`) names the specific
`OR`/`NOR` block a gate is a direct child of, so an unconditional requirement (e.g. "Needs
Galactic Wonders") never reads as a flat peer of a choice beneath it (e.g. "or: Mechromancy" /
"or: a tradition"). The client nests same-`groupId` gates under their own "Need one of:" cluster.
Real corpus: 1 technology mixes unconditional and grouped matches (`giga_tech_the_vat`).

**Gate-polarity fix.** `_leaf_negated` XORs three independent negation channels: a `NOT`/`NOR`
wrapper ancestor, the `!=` operator, and a leaf's own literal `= no` VALUE (Clausewitz's other way
to write negation, no wrapper at all — the original bug: only the wrapper channel was checked).
Safe to apply unscoped — `= no` occurs only on `is_wilderness_empire` in the real corpus (31
technologies, all boolean-shaped). `can_research_technology` was removed from gate classification
entirely — it means "this OTHER technology isn't currently locked out" (an eligibility fact), not
`has_technology`'s "you have already completed this" — 1 real literal occurrence, but gate
propagation had inherited the mis-badge onto 15 descendants.

**Gates PROPAGATE down `prerequisite` chains.** A technology whose only real requirement is "my
prerequisite needs the gate" previously showed no gate at all. `pipeline.dataset_emit.
build_base_dataset` computes, for every rendered technology, the union of its own DIRECT gates
plus every `prerequisite`-ancestor's gates (transitively, via topological order), deduplicated by
`(kind, refId)` — direct declarations always win the dedup. Two new `Gate` schema fields carry
this: `inherited: boolean`, `sourceTechnologyId: string | null` (the original declaring
technology). Deliberately scoped to `prerequisite` edges only, NOT `potential-gate` — see Open
Items.

**`on_enabled → add_research_option` ascension-perk grants are a gate source too.**
`ap_galactic_wonders`'s (Gigastructures-overwritten) `on_enabled` unconditionally grants
`tech_ring_world`/`tech_dyson_sphere`/`tech_matter_decompressor` — all three structurally
unreachable any other way (`weight_modifier = { factor = 0 }` unconditionally). These 3 get a
direct `ascension_perk` gate (`pipeline.dataset_emit.ADD_RESEARCH_OPTION_PERK_GRANTS`),
deliberately NOT `tech_mega_engineering` (also granted this way, but remains reachable normally
too, so a gate would overstate a real requirement). DISPLAY-only — does not make these three
LOCKED for axis-excluded profiles, since their own `potential` never references the perk.
**Cosmogenesis-locked technologies (Nano-Assembler, Polyatomic Crucible, and the "tensile
buildings") are `weight_modifier`-based, not `potential`/gate-based** (`factor = 0` unless a
crisis-level condition, or the already-known `@giga_amb_flag` mod-config toggle) — surveyed twice
(the second time specifically to check Nano-Assembler/Polyatomic Crucible for a missed perk
requirement — none found in raw source), correctly NOT gate-classified, since that would conflate
weight and availability (a category error this project's rules already warn against).

**Current real corpus totals: DIRECT gates 107 instances (48 ascension_perk + 14 origin + 24
ethics_or_civic + 21 technology) over 83 directly-gated technologies. TOTAL (direct + inherited)
214 instances (104 ascension_perk + 16 origin + 61 ethics_or_civic + 33 technology) over 147
gated technologies, 47 of which carry more than one gate instance.** Full move-by-move history —
every intermediate count and which fix moved it — lives in `docs/BUILD-LOG.md`.

The spec's original "Tetradimensional Engineering" gate example was checked against the real
corpus and found wrong (it gates ascension perks, not a technology) — corrected once in
`spec/P-03-gates.md`, then found stale again since that replacement pair is one of the redundant-
prerequisite-plus-gate pairs excluded from display. A real still-valid example: any
`tech_lathe_*` → `tech_cosmogenesis_world` pair.

**Dangling "or:" downgrade extended to a single group nested inside a longer list — real bug fix
(Item 3b, a later session, user-reported).** The existing downgrade (above) only checked the
WHOLE `gates` list's length; it missed a `groupId` with exactly ONE member sitting alongside other
gates/groups — real corpus example: `tech_cloning`'s own direct gate ("Driven Assimilator") formed
a 1-member group next to a genuine 2-member INHERITED group (`tech_genome_mapping`'s "Rogue
Servitor"/"Genesis Architects"), so the card showed a dangling "or: Driven Assimilator" primary
badge and the popup rendered a "Need one of:" cluster containing a single, non-choice entry.
`pipeline.dataset_emit._downgrade_dangling_alternative` now also checks per-`groupId` size after
the whole-list check, downgrading any lone-member group the same way (`alternative: false`,
`groupId: null`, `"or: X"` → `"Needs X"`), regardless of how many other gates/groups the technology
carries. `#detail-popup`'s CSS also gained explicit `overflow-x: hidden` and `overflow-wrap`
safety on gate rows as defence-in-depth against a long localised name bleeding past the fixed-width
panel.

### Tiers

Tier range is **not** bounded. ACOT pushes tiers to T9 and beyond. Enumerate tier bands from
the data. No fixed upper bound anywhere in layout, LOD, or band labelling. Measured against the
real 973-node rendered corpus (D-18, then Item 2c): 10 declared-tier bands (T0-T9) plus the terminal Repeatables band.

**A node's band is its own declared `tier` field — never adjusted by graph depth (D-13,
corrected from an earlier draft that promoted a node's displayed position) — with one declared
exception: repeatable technologies band into the terminal Repeatables band regardless of their
own tier, and badge repeat count instead of tier on the card. See "Repeatables" below and D-13 in
`spec/decisions.md` for the full reasoning, including why this exception is not a return of v1's
band-header bug.** Tier is vanilla's and Gigastructures' own vocabulary; a band labelled "Tier 5"
contains exactly what the mod calls tier 5. Computed longest-path position still exists, but
purely as internal geometry — it orders technologies horizontally within a band's sub-grid and
gives the router a consistent signal for backwards edges, and is never displayed as a number.
**Within a shared depth slot, zero-cost technologies sort left of costed ones (Item 3a, a later
session, user-reported: zero-cost technologies appearing right of costed ones read as backwards
progression).** `pipeline.layout.compute_layout`'s sort key gained a zero-cost tie-break
(`same_band_depth`, then zero-cost-first, then `computed_position`, then key) — this only ever
reorders members that ALREADY share a `same_band_depth` value, exactly where D-17 permits free
reordering; it never changes which depth slot a node occupies, so it cannot violate D-17's own
invariant (a node never rendering left of/in line with its own prerequisite). No real case was
found where D-17 forbids the preferred order — the two constraints operate at different levels
(depth slot vs. position within a slot) and never conflict.
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
truthfully) and the "Prerequisites"/schema sections for how a null `cost` (5/973 rendered nodes as
of D-18 — a later correctness pass resolved 10 of the originally-reported 15 via their `cost`
block's own `factor` sub-field, see `pipeline.dataset_emit._resolve_cost`'s docstring —
unresolvable, never guessed at) is represented.

**A literal zero cost and an unresolvable (`null`) cost both render NO cost panel — user decision
(a later session, Item 2a).** Distinguishing "this costs nothing" from "we couldn't work out what
this costs" is meaningless to an end user; both collapse to the same "no panel" treatment on the
card and in the popup (`client/src/main.ts`'s card cost line and the popup's `field-value`
block). Previously a zero cost rendered `Cost: 0` and a null cost rendered nothing (card) or
`Cost: unresolvable` (popup) — three different signals for what the user experiences as two
states worth distinguishing (has a real cost / doesn't). This is purely a client display decision
— the pipeline still emits the real resolved `cost` value (`0`, a positive number, or `null`)
unchanged; nothing about `_resolve_cost` or the schema changed.

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

**Zero weight IS an availability fact — user decision (Item 2b, a later session), a carve-out on
top of the rule above.** "Weight is a separate concern from availability" stands for weight as a
gradient — a modifier that boosts or reduces a nonzero weight stays purely a weight concern, never
folded into `state`. But a `weight_modifier` entry whose own `factor` is a literal `0` is
Stellaris's own idiom for "this technology cannot currently be drawn as a research option at all"
— functionally a gate, not a gradient. The motivating case: Cosmogenesis-locked technologies
(Nano-Assembler, Polyatomic Crucible, the "tensile" buildings) — a prior session correctly found
these `weight_modifier`-based, then wrongly concluded that meant no user-facing treatment at all.

**Implemented**: `pipeline.dataset_emit._weight_gate_condition_blocks` extracts every zero-factor
`weight_modifier` `modifier` entry's own condition (siblings of `factor`, `factor` itself
stripped) per rendered technology — deliberately `weight_modifier` only, never `ai_weight` (which
governs AI empires' own choices, not what the player is offered). Each condition is
scripted-trigger-expanded exactly like a `potential` block, then evaluated through the SAME
unchanged Kleene evaluator (`pipeline.availability._apply_weight_gate`) as an additional check
layered onto the technology's `potential`-based result, only when that result is AVAILABLE: if
the zero-factor condition resolves definitely TRUE for a profile (the modifier fires, weight is
currently zero), the technology downgrades to LOCKED with a reason naming the raw condition; if it
resolves UNKNOWN, it downgrades to UNCERTAIN the same honest way any other undecidable leaf does.
A technology already LOCKED/UNCERTAIN/CONFIG_GATED for a real `potential`-block reason is
unaffected — the more specific existing reason wins.

**Real corpus: 248 rendered technologies (301 zero-factor `modifier` entries — some carry more
than one) carry a `weight_modifier` factor=0 branch.** This is materially broader than the
motivating Cosmogenesis example — the same idiom is Stellaris's standard mechanism for excluding a
tech from the weighted draw under ANY condition, used throughout vanilla for ordinary things like
"don't offer this terraforming variant when the empire has no matching planets"
(`tech_mountain_range`/`tech_volcano`/`tech_toxic_kelp`/... via `num_owned_planets`), policy/civic
toggles (`has_policy_flag`), and FE/crisis-chain content, not just mod-configuration or
crisis-progression gates. Effect, measured directly (not estimated): **unconditional uncertainty
31/973 → 115/973 (11.8%); worst profile-dependent rate 16/973 (1.64%) → 58/973 (5.96%) — crosses
the 3% warn threshold but stays well under the 10% hard ceiling; union 53 → 180.** 39 technologies
gain a real LOCKED verdict for at least one profile that was previously AVAILABLE (mostly Fallen
Empire/crisis-chain content genuinely never offered through the normal weighted draw); 124 more
gain an UNCERTAIN verdict for at least one profile that was previously AVAILABLE (dynamic in-game
state the evaluator correctly can't resolve — planet counts, policies, crisis levels). This is a
considered, reported tradeoff per this project's own "report honestly, don't smooth over a worse
number" discipline (the same posture the scripted-trigger expansion session took) — the ceiling is
not breached, and the new signal is real and more informative than silence, even though it moves
the warn-threshold figure. The pinned corpus test
(`tests/test_availability_corpus.py::test_uncertain_count_and_per_profile_breakdown_pinned`) was
updated deliberately for this move, not silenced.

### Research path

**Implemented (P-12.9, a later session — `spec/P-12.9-research-path.md`).** The old placeholder
`{ancestors, shortestChain}` shape (a plain profile-blind `prerequisite`-edge BFS, `alternative`
edges never resolved — v1's own two documented failures: profile-blind traversal and flattened
`OR`-branch choices) is replaced by `researchPaths[technologyId]` = `{status, steps, totalCost,
totalCostIsEstimate, estimateReasons, configGatedTarget}`, precomputed per (technology, profile)
at build time in the empire overlay (`pipeline.dataset_emit._build_research_paths_for_profile`,
memoised once per profile across all 973 targets sharing it). `status` is `"path"` (ordinary),
`"config-gated"` (the target is one of the 50 `giga_tech_repeatable_*_cap` technologies — its own
cost is excluded from `totalCost` entirely, per D-13's sink property: a config-gated technology
can only ever be a path's own target, never an interior step), `"unavailable"` (no `steps` array
at all — the target ITSELF is `locked`), or **`"blocked"`** (Item 2d, a later session — no `steps`
array either, but the target's own state is `available`/`uncertain`; a plain, non-`alternative`
prerequisite somewhere in its ancestor chain is `locked`/`config-gated`, or an `alternative` group
has zero viable candidates). `"unavailable"` and `"blocked"` are deliberately DIFFERENT statuses,
not one shared state — see "When there is no route at all" below for why. An `alternative`
(`OR`-group) is resolved to whichever VIABLE
(`available`/`uncertain`, never `locked`/`config-gated`) candidate has the cheapest FULL recursive
closure cost — never just its own declared cost, which is what fixes v1's "chose a branch without
expanding its own prerequisites" bug — and the chosen step's own `alternatives` list names the
other viable siblings, never flattened away. `totalCost` for `status == "path"` includes the
TARGET's own declared cost (confirmed the only reading that reproduces the spec's own worked
example: `tech_mega_engineering` regular/mechanical/non-nomadic = 74,750 exactly, the 15-ancestor
sum plus the target's own 24,000 — the ancestor-sum-only reading does not); for `"config-gated"`
it excludes the target's cost, per section 5. An `uncertain` step or a `null`-cost step both stay
in the path (never excluded, matching D-10's "unknown ≠ excluded" discipline) and set
`totalCostIsEstimate`/`estimateReasons` (`"uncertain-availability"`/`"unresolved-cost"`,
composable). Every step's `name`/`icon` is D-14-substituted for the selected profile.

**Real corpus, current (re-measured this session — the original spec's 3 headline figures had
gone stale, per its own worked examples): OR tie-break (cheapest-total-cost vs. fewest-steps)
disagrees on 12 of 72 genuine 2+-viable-candidate group×profile choices** (of 420 total
group×profile evaluations over the corpus's 35 real `alternative` groups, 408 have ≥1 viable
candidate) — cheapest-total-cost is genuinely load-bearing now, not a defensible-either-way
footnote the original survey's "0 disagreements" figure implied.

**A real, previously-unmeasured finding, corrected against an earlier session's own inherited
assumption, not suppressed to match it: the "dangerous" sub-case (an ancestor chain broken while
the target's own state stays available/uncertain) is NOT zero on the current corpus.** Confirmed
directly against raw source, not assumed: `tech_ehof_spinal`'s `prerequisites` block
unconditionally (never inside an `OR`) requires `tech_arkship_tier_3`
(`giga_09_ehof_other.txt:260`), whose own `potential` is `is_nomadic = yes`
(`00_nomads_dlc_tech.txt`) — locked for every non-nomadic profile; `tech_ehof_spinal`'s own state
resolves `uncertain` (an unrelated `has_arcane_generator` flag), never `locked`. Real corpus: 78
distinct technologies / 472 (key, profile) pairs hit this.

**When there is no route at all — CORRECTED (Item 2d, a later session): `spec/P-12.9-research-
path.md` section 6 originally folded "target itself locked" and "ancestor chain broken while the
target is fine" into ONE status (`"unavailable"`), on the strength of a stale claim that the two
always coincide (2 of 980 technologies, both cases). That claim was never true of the real, current
corpus (78/472, above) — a documented figure trusted across sessions without being re-verified,
the same failure mode as the `has_ancrel` defect (see "Trigger evaluation" above). Fixed: a new,
distinct status, `"blocked"`, carries `blockedBy: {technologyId, name, reason}` naming the specific
ancestor whose own locked/config-gated state broke the route (one representative non-viable member
for a broken `alternative` group, not every one) — `pipeline.dataset_emit._UnreachablePath` now
carries the blocking key from its origin raise site up to the target-level catch, unchanged, so the
FIRST (deepest) real cause survives, not a synthesized one. `"unavailable"` now means ONLY "the
target's own state is locked" — 0 conflation with the ancestor-chain case going forward.
`pipeline.dataset_emit.build_diagnostics`'s `unresolvableResearchPaths` field
(`spec/P-12.9-research-path.md` section 6's tripwire) now tracks every `blocked` pair directly,
same 78/472 figure at the time this status was introduced.**

**The 78/472 figure moved again, same session, purely as a consequence of Item 2b (above) landing
alongside Item 2d — reported together honestly, not chased back down to the smaller pre-Item-2b
number.** Item 2b's weight-gate LOCKED downgrades add real new ancestor dead ends throughout the
prerequisite graph, and every downstream descendant of a newly-LOCKED technology now legitimately
hits the `"blocked"` case too. Real corpus, both fixes together: **958 (technology, profile) pairs
/ 116 distinct technologies are `"blocked"`.** This is not a bug in Item 2d's own mechanism — the
mechanism is proven correct against the smaller pre-Item-2b corpus and against direct raw-source
tracing (`tech_ehof_spinal`, above) — it is downstream fallout of Item 2b correctly surfacing more
real dead ends. Do not "fix" this by reverting Item 2b's weight-gate fold-in to make the smaller
number reappear.

**Nano-Assembler display bug fixed, same session, independent of the status split.**
`giga_tech_fe_megaworkshop_1` ("Nano-Assembler") has NO `prerequisites` at all — a legitimate
zero-step path (research it directly, `totalCost` = its own declared cost) — but the client
rendered "Research path (0) / none / Total: 70,000 (estimate: uncertain-availability)", which
reads as contradictory (a zero-step list next to a nonzero total). Fixed in `client/src/main.ts`'s
`renderResearchPath`: a zero-step `"path"`/`"config-gated"` status now renders "No prerequisites —
this is the direct cost of researching it" instead of the bare word "none", regardless of which
status it ends up with.

CLIENT: selection-triggered (matches v1's own trigger — no persistent "goal technology" pin, an
explicitly deferred feature). `client/src/main.ts`'s `openPopup` fetches the current profile's
overlay unconditionally (previously only for a non-`available` technology) and renders a
`renderResearchPath` section: ordered steps with per-step cost and an `uncertain` badge, the
running total with its estimate note where set, `alternatives` shown inline per OR-chosen step,
the `config-gated` target's own subject/template note, and (Item 2d) a distinct `"blocked"`
explanatory line naming `blockedBy`. Verified with real screenshots (an `OR`-choice path, the
nomadic Arkship-branch substitution, an `uncertain`-step estimate, an `unavailable` target, a
`config-gated` target, a `blocked` target naming its blocking ancestor, and Nano-Assembler's
corrected zero-step display) — zero console errors, all figures matching the pinned corpus tests.

### Localisation

English only for v1. The pipeline is language-parameterised so more languages are a build flag.

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
  them from a parallel formula.** Any renderer-side value derivable from emitted geometry
  (row/band extents, a cell's populated width) MUST be derived from the real emitted positions
  (`nodePositions`/`edgePolylines`), never reimplemented client-side from the same inputs
  `pipeline/layout.py` consumes. Found the hard way: `client/src/main.ts` once re-derived row/band
  geometry via its own copy of `pipeline/layout.py`'s formulas, and D-17's same-band depth-slot fix
  silently desynced it — row panels, tier tints and cell labels drew nowhere near their actual
  cards, no error, no failing test, caught only by a headless screenshot. Fixed permanently by
  deriving from real positions (min/max over emitted `nodePositions`, grouped by row/band), not a
  periodic re-sync — client and server geometry can't drift apart again regardless of future
  formula changes. A milder residual form remains: mirrored SCALAR constants (`CARD_WIDTH`/
  `CARD_HEIGHT`, gutter constants, `SUBGRID_WIDTH`, `AREA_ORDER`, `FLOATS_PER_EDGE_POLYLINE`,
  `MIN_STUB`) still kept in sync by hand since the dataset schema doesn't carry them as data —
  `CARD_WIDTH`/`CARD_HEIGHT` are the one genuinely load-bearing pair (they size the actual card
  draw call); flagged as a scoped follow-up, not fixed. See `docs/BUILD-LOG.md` for the full
  audit of what else was checked and ruled out.
- **A second, DIFFERENT defect class produced the same visible symptom (rows overlapping) a later
  session — do not confuse it with the parallel-formula bug above.** A sub-grid centring fix
  (`pipeline/layout.py`) keyed `column_member_count` by `(row_id, col)` alone, but `col` is
  BAND-RELATIVE (its cursor resets every band) — two physically different columns in different
  bands of the same row shared a dict key, silently summing member counts and driving the centring
  offset negative (real corpus: one node placed at row −16). A plain dict-keying bug, not a
  parallel-geometry violation — confirmed directly, not assumed. Fixed by keying on the full
  `(row_id, band_index, col)` triple, plus an `assert centre_offset >= 0` as a second line of
  defence. The existing test suite stayed green through this regression because nothing asserted
  the actual invariant (no two rows' card extents may intersect, no row index is ever negative) —
  the same "green suite proves self-consistency, not correctness" lesson D-17's unbounded-stacking
  bug already taught once. `tests/test_layout_corpus.py::
  test_no_row_overlaps_and_every_card_within_its_own_row_bounds` and `tests/test_layout.py::
  test_no_row_overlaps_when_the_same_row_spans_multiple_bands` are the missing invariant, each
  proven capable of failing against the broken code before being trusted on the fix.

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

Full build history — every decision, measured figure, and defect found in past sessions,
including every item that used to be listed here as "now closed" — lives in `docs/BUILD-LOG.md`.
This section states only what is genuinely still open. Locked, load-bearing decisions live in
this file's own body above and in `spec/decisions.md`, not here. When an item below is resolved,
remove it entirely — do not leave a struck-through "now closed" placeholder; `docs/BUILD-LOG.md`
already has the closure on record.

- **Wilderness/Frameworld as TOGGLES layered over the 12 profiles (not new axes): surveyed (Item
  2c, a later session), NOT implemented — real decision needed, user explicitly wants a
  recommendation.** The user's framing: two origins with the same shape (substantial exclusive
  content, `has_origin`-gated) is a pattern, not a special case — a toggle composes ("show me this
  as a frameworld empire") where a flat axis multiplies, and the two origins are MUTUALLY
  EXCLUSIVE, which bounds it to a 3-state dimension (neither / wilderness / frameworld), not two
  independent booleans.
  - **Scale, re-measured this session (methodology differs slightly from the original wilderness
    survey — see caveat below, not silently reconciled to the old number): wilderness affects 54
    technologies / 200 (technology, profile) pairs across the 4 hive-authority profiles; frameworld
    affects 8 technologies / 96 pairs across all 12 profiles** (frameworld's authority-restriction,
    if any, is UNCONFIRMED — `common/origins/` isn't vendored for any source, so its own `possible`
    block can't be inspected; simulated as unrestricted across all 12). Caveat: the wilderness
    figure was previously recorded as 41/973 (4.2%) / 148 pairs, hive-only; this session's
    re-measurement (54/200) used a direct true-vs-false leaf simulation rather than replicating the
    exact prior methodology bit-for-bit — flagged as an unreconciled discrepancy, not silently
    overwritten, since re-deriving the exact original method wasn't done. Either figure supports
    the same conclusion (both origins show a real, non-trivial availability difference).
  - **No other origin comes close in scale** — a full corpus survey of direct `has_origin = X`
    leaves found the next-largest at 2 technologies (`origin_shroudwalker_apprentice`,
    `origin_endbringers`, `origin_shroud_forged`, `origin_red_giant`), an order of magnitude below
    wilderness/frameworld — and `pipeline.gate_patterns.WRAPPER_TO_ORIGIN` confirms these two are
    the only origin-shaped scripted-trigger WRAPPERS registered at all. **Three states (neither /
    wilderness / frameworld) is enough** — nothing else in the real corpus argues for a fourth.
  - **Real emitted payload cost, MEASURED not estimated**: widening `availabilityMatrix` from
    12 to 36 slots (simulated directly against the real base dataset) moves the base dataset's
    compressed size **60,885 → 65,704 bytes gzip (+4.8 KB, +7.9%)** — negligible against the ≤2 MB
    base-dataset budget (spec/P-10), still ~30x headroom. A real built empire overlay for a
    simulated wilderness/frameworld profile is **54.2 KB / 54.5 KB gzip respectively**, essentially
    identical to an ordinary profile's overlay (currently ~56–64 KB) — overlays are explicitly
    OUTSIDE the ≤2 MB base-dataset budget (P-10's own scope statement) and are fetched one profile
    at a time (lazy, per-selection), so tripling the profile COUNT (12 → 36 files) does not
    multiply what any single session actually downloads; it multiplies the total artefact COUNT on
    disk/in a full prefetch, which was never the design's cost model anyway.
  - **`EmpireProfileIndex` (`pipeline/dataset_schema/empire_profile.py`) extends cleanly, no
    rework needed.** `AXES` is a plain list of `(name, ordered_values)` pairs with strides derived
    at import time from cardinalities, plus an import-time bijection assertion — adding a single
    3-valued axis (`("originToggle", ["neither", "wilderness", "frameworld"])`) is a one-line
    change that correctly yields `TOTAL_PROFILE_COUNT = 36` with zero special-casing, and models
    the mutual-exclusivity naturally (one 3-valued axis, not two independent booleans that would
    wastefully allow a nonsensical "both" combination).
  - **Icons: neither is vendored**, same finding as the existing "Icons — reported, not vendored"
    note under "Gates" — `common/origins/` isn't in any source's vendored tree at all, so a visual
    indicator would need a new source directory pinned and reviewed (a real, separate follow-up),
    not something this toggle feature can ship with today.
  - **Recommendation (not acted on, decision is the user's per the prompt's own instruction):
    implement it.** The scale is real (comparable to, or larger than, thresholds this project
    already treats seriously — e.g. the 3% D-10 warn threshold), the payload cost is negligible,
    the indexing mechanism already generalises correctly, and the only real blocker (icons) is a
    separate, already-known, already-scoped gap that doesn't block a text-only toggle. The main
    design work is client-side (a toggle control, `EmpireProfileAxes` consumption already
    data-driven per the closed "EmpireProfileIndex parallel-formula" item) plus extending
    `AXES`/`profiles` generation and wiring `is_wilderness_empire`/`giga_has_frameworld_origin`
    into `AXIS_FACTS` (currently `EXCLUDED_KEYS`-only, gate-display-only) the same way the three
    existing axes are.
- **Distinct research-path status for a broken ancestor chain: now closed (Item 2d, a later
  session).** See "Research path" above for the new `"blocked"` status and the corrected P-12.9
  section 6. Left here only so a future session's memory of "this was still open" gets corrected
  on sight.
- **Middle-click isolation (P-7) is fully specced (`spec/P-07-isolation.md`) and entirely
  unbuilt.** Middle-click (or long-press ≥400ms on touch, P-9) isolates a node together with its
  direct prerequisites/unlocks (user-adjustable depth, default 1 hop, full-closure option),
  traversing all three edge kinds distinctly styled per P-8 — deliberately differs from the
  research path (P-12.9), which is prerequisite-edges-only. Visibility mask over the static
  layout, never a re-layout. Adjacency lists (forward/reverse, per edge kind) must be precomputed
  in the dataset for O(1) traversal, inside P-10's 100ms budget.
- **No pipeline-test CI workflow exists** — `pytest` still runs manually/locally only.
- **`tools/collect_vanilla.py`'s GitHub-fetch-and-pin automation for Gigastructures, plus a
  scheduled CI staleness check, is still unbuilt** — see "Source data" above; the current manual
  pin is a deliberate stopgap.
- **Pattern tile for Blokkats** needs tracing to clean SVG from the supplied flag image — the
  current herringbone motif is a procedural placeholder, not traced art.
- **Sirenalia's accent shade and Katzenartig Imperium's chevron pattern are both flagged
  provisional** in `client/src/tokens.ts`'s own comments — Sirenalia's geometry (curved wave
  bands) was ported from v1, but its accent colour is still a placeholder; Katzenartig has no
  in-game reference at all and its pattern is inferred, not described art.
- **`potential-gate` edges' long-span (up to 5-band) backward routing** was left `TODO(Stage 3)`
  before a real rendered canvas existed to design against — re-check whether the v1-style router +
  gutter-router fallback (`docs/BUILD-LOG.md`'s rendering sections) has since made this moot.
- **ΔE2000/WCAG mechanical colour checks are still unbuilt** — S-1's own CI-enforced acceptance
  criterion (pairwise contrast across the full token set). Every colour token is a first concrete
  pick, checked by eye only.
- **`repositoryLink` isn't live-validated** (no network access at build time) and its `lineRange`
  uses the block's start line for both ends (the AST doesn't track an end-of-block line).
- **Gate propagation down `potential-gate` edges is a deliberately deferred scope boundary.**
  Gates propagate down `prerequisite` edges only (the formal "must research first" chain). A
  `potential-gate` edge (`has_technology` inside `potential`) is a different kind of dependency
  (an eligibility check, not a declared prerequisite); whether/how it should also propagate gates
  needs real corpus study before extending.
- **Looping edges: surveyed twice, none found geometrically.** Three independent geometric checks
  (X-direction reversal, a Y-axis "hook" shape, literal polyline self-intersection) against the
  current dataset found zero matching edges. If a user reports this again, ask for a screenshot or
  a specific technology name rather than re-running the same survey.
- **Hover vs. selection scope discoverability** — hover shows immediate neighbours only, selection
  shows the full ancestor/dependent closure; the split is correct but nothing in the UI hints that
  selecting reveals more than hovering does. A cheap, optional follow-up, not yet built.
- **Two technologies named "Confluence of Thought" are a known, genuine same-name pair, not a
  bug.** `tech_hive_confluence` and `tech_wilderness_confluence` are two deliberately-parallel
  vanilla technology lines (confirmed via raw source's own "# Wilderness" section header) — one of
  5 documented genuine same-name pairs in the mod. Not an overwrite-resolution or localisation
  error.
