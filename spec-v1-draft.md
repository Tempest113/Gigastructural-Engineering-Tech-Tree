# Gigastructural Engineering & More — Interactive Tech Tree Visualiser

**Technical Specification**

| Field | Value |
| --- | --- |
| Document status | Draft for implementation review |
| Version | 1.0 |
| Target product | Static, client-side web application |
| Primary data source | *Gigastructural Engineering & More* mod source + vanilla Stellaris `common/technology` |
| Reference artefacts | Reference Image 1 (layout & connectors), Reference Image 2 (gate indicators) |

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Primary Requirements](#2-primary-requirements)
3. [Secondary Requirements](#3-secondary-requirements)
4. [Implementation Notes](#4-implementation-notes)

---

## 1. Introduction

### 1.1 Purpose

This document specifies an interactive, web-based technology tree visualiser for the Stellaris mod *Gigastructural Engineering & More* (hereafter "Gigastructures"). The tool renders the combined vanilla + Gigastructures technology graph as a left-to-right, tier-columned flowchart, and allows a user to filter, search, isolate and inspect individual technologies.

The core problem the tool solves is that the Gigastructures technology graph is (a) very large, (b) heavily conditional on empire type, and (c) subject to frequent upstream change. The specification therefore treats **empire-type-aware graph computation** and **automated, zero-manual-maintenance data extraction** as first-class architectural concerns rather than features bolted onto a static diagram.

### 1.2 Scope

**In scope:**

- Automated extraction of technology definitions from mod and base-game source files.
- Build-time computation of per-empire-type technology graphs.
- A client-side rendering and interaction layer (pan, zoom, filter, search, isolate, inspect).
- A developer diagnostics build.
- End-user documentation.

**Out of scope (unless explicitly added later):**

- Editing or authoring mod content.
- Save-game parsing or in-game state integration.
- Coverage of mods other than Gigastructures and base Stellaris. (The data pipeline SHOULD be structured so additional mods are a configuration change, not a rewrite — see §4.2.6.)
- Server-side components of any kind. The deliverable is a static site.

### 1.3 Requirement Language

The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT** and **MAY** are used per RFC 2119. Every requirement carries a stable identifier (`P-n` for primary, `S-n` for secondary) so that issues, commits and tests can reference it directly.

Each requirement is stated with:

- **Requirement** — the normative statement.
- **Acceptance criteria** — objectively verifiable conditions.
- **Implied technical decisions** — consequences a developer must implement, made explicit here rather than left to interpretation.

### 1.4 Glossary

| Term | Definition |
| --- | --- |
| **Tech node** | A single technology, rendered as a card: icon, localised name, research cost, tier badge, and zero or more gate indicators. See Reference Image 1. |
| **Tier** | The technology's declared `tier` value (T0–T5+ in Gigastructures). Drives column assignment. |
| **Area** | Vanilla research area: `physics`, `society`, `engineering`. Drives base colour. |
| **Category** | Vanilla/mod sub-category, e.g. Computing, Voidcraft, Psionics, Materials. Drives category filtering. |
| **Gate** | A non-prerequisite unlock condition displayed prominently on the node, e.g. *Cosmogenesis* Ascension Perk, *Galactic Wonders*, *Gigastructural Constructs*, *Tetradimensional Engineering*. See Reference Image 2. |
| **Empire type** | A named profile describing an empire's relevant characteristics (e.g. *Standard*, *Nomadic*, *Biological/Living Shipset*, *Machine*). Determines tech availability, tech swaps and research paths. |
| **Tech swap** | A pair/set of technologies that are functionally equivalent but mutually exclusive by empire type (e.g. mechanical Corvette→Battleship line vs. the biological ship equivalents). |
| **Crisis tech** | A technology unlocked through a Gigastructures crisis event chain (e.g. Blokkats, Sirenalia) rather than through normal research progression. |
| **Isolation** | An interaction mode in which only a chosen node and its related nodes remain fully visible. |
| **Trigger block** | A Clausewitz-script conditional block (`potential`, `weight_modifier`, `allow`, etc.) evaluated by the game engine. |

### 1.5 High-Level Architecture

The requirements collectively force a three-stage architecture. This is stated here because several requirements (P-1, P-10, P-14, P-15) are unimplementable in a naive "hand-authored JSON + render" design.

```
┌──────────────────────┐   ┌──────────────────────┐   ┌──────────────────────┐
│  Stage 1: Extract    │   │  Stage 2: Compute    │   │  Stage 3: Render     │
│  (CI, build-time)    │──▶│  (CI, build-time)    │──▶│  (browser, runtime)  │
├──────────────────────┤   ├──────────────────────┤   ├──────────────────────┤
│ • Fetch pinned mod   │   │ • Resolve overwrites │   │ • Load dataset       │
│   + vanilla sources  │   │ • Build DAG          │   │ • Layout → viewport  │
│ • Parse Clausewitz   │   │ • Per-empire-type    │   │ • Pan / zoom / touch │
│   script → AST       │   │   availability &     │   │ • Filter / search /  │
│ • Parse localisation │   │   research paths     │   │   isolate            │
│   YAML               │   │ • Tier/column assign │   │ • Detail popup       │
│ • Convert .dds icons │   │ • Static edge routes │   │ • /?dev diagnostics  │
│ • Emit raw AST JSON  │   │ • Emit dataset JSON  │   │                      │
└──────────────────────┘   └──────────────────────┘   └──────────────────────┘
```

**Key architectural decisions implied by the requirements:**

1. **All parsing and graph computation happens at build time, in CI.** The browser never parses Clausewitz script. This follows directly from P-10 (high performance) and P-15 (overwrite accounting, which requires whole-corpus analysis).
2. **The build emits a pre-computed dataset per empire type**, or a shared base dataset plus per-empire-type delta overlays (see §4.2.4). This follows from P-1 and the per-empire-type research path field of P-12.
3. **The site is a static bundle** deployable to GitHub Pages or equivalent, with no runtime backend. This follows from P-10 (CI/CD automation, minimal maintenance) and the `/?dev` query-string convention of S-2, which presumes client-side routing.
4. **Rendering is viewport-virtualised.** The combined graph is on the order of 10³–10⁴ nodes; naive DOM rendering will not meet P-9 (mobile) or P-10 (performance). See §4.3.

---

## 2. Primary Requirements

All requirements in this section are mandatory for the initial release.

---

### P-1 — Empire Type Support

**Requirement.** The tool MUST model empire types as a first-class dimension. Supported empire types MUST include, at minimum: standard/default empires, nomadic empires, empires using biological (living) shipsets, and empires using mechanical shipsets. For any selected empire type, the tool MUST compute and display technology availability, tech swaps and research paths correct for that empire type.

**Acceptance criteria.**

- A visible, persistent empire-type selector is present in the primary UI.
- Changing the empire type updates: which nodes are visible/available, which nodes are marked locked (see P-13), all edges, and the research-path field of the detail popup (P-12.9).
- Where a technology is swapped between empire types, the tool displays the technology appropriate to the selected empire type and identifies its counterpart as a swap partner.
- The selected empire type is encoded in the URL so that a view can be shared or bookmarked.

**Implied technical decisions.**

- Empire types MUST be defined in a **declarative empire profile configuration** (a checked-in file), not hard-coded in application logic. Each profile enumerates the trigger facts asserted for that empire (e.g. `is_nomadic = yes`, `has_biological_ships = yes`, `is_machine_empire = no`), which the trigger evaluator (§4.2.3) consults when resolving conditional blocks.
- Adding a new empire type MUST require only a new profile entry plus, where necessary, new trigger fact mappings — never changes to the renderer.
- Empire type is a **build-time partition key**: datasets are computed per profile, not derived in the browser.

---

### P-2 — Tier-Based Column Layout

**Requirement.** Technologies MUST be laid out left-to-right as a directed acyclic graph and MUST be visually separated into columns by tier. No technology may be rendered to the left of, or in the same column as, any of its prerequisites. The layout MUST be consistent with Reference Image 1: discrete tier bands running left to right, nodes stacked vertically within a band, and connector lines running rightwards between bands.

**Acceptance criteria.**

- For every edge `(A → B)` where A is a prerequisite of B, `column(B) > column(A)`.
- Every node's column corresponds to its tier band; tier bands are contiguous and ordered ascending left to right.
- The layout is deterministic: the same input dataset produces the same node positions on every build.
- The graph contains no cycles; if a cycle is detected during the build, the build fails loudly (see §4.2.5).

**Implied technical decisions.**

- Declared `tier` and graph depth can disagree. The specification resolves this as follows: **tier determines the band; longest-path depth determines ordering within and across bands**. If a technology's declared tier is less than or equal to that of one of its prerequisites, the build MUST promote it to `max(prereq columns) + 1` and MUST emit a warning listing the affected technologies, visible in the `/?dev` build (S-2).
- Vertical ordering within a column MUST be computed by a crossing-reduction pass (e.g. Sugiyama-style barycentre/median heuristic) to keep connector lines legible; grouping by category or by connected component is an acceptable additional constraint.
- Layout MUST be computed at build time and stored as coordinates in the dataset. Runtime layout of a graph this size is incompatible with P-9 and P-10.

---

### P-3 — Primary Gate Indicators

**Requirement.** Every technology that is gated behind a non-prerequisite unlock condition MUST display a visually prominent gate indicator on its node. The indicator MUST render the associated icon alongside the gate's localised name, consistent with Reference Image 2 (e.g. the Cosmogenesis perk icon paired with the label "Needs Cosmogenesis"). Gates include, at minimum: Cosmogenesis Ascension Perk, Galactic Wonders Ascension Perk, Gigastructural Constructs Ascension Perk, and the Tetradimensional Engineering technology.

**Acceptance criteria.**

- The gate indicator is rendered inside the node card and remains legible at default zoom.
- The gate icon is rendered as an image, not substituted with a glyph, emoji or text-only marker.
- Gate labels are localised strings sourced from the mod's localisation files, not hard-coded in application source.
- A technology with no gate renders no indicator and no empty placeholder row.

**Implied technical decisions.**

- **A technology may have more than one gate.** The data model MUST therefore store gates as an ordered list, with the first element designated the *primary gate* (surfaced in the detail popup per P-12.7). Node cards MUST render the primary gate; where space permits, additional gates render as compact secondary badges. The ordering rule MUST be deterministic and documented (see §4.5, open question OQ-3).
- Gate detection is a **classification pass** over trigger blocks: the build inspects each technology's `potential`/`allow`-equivalent conditions for recognised gate patterns (ascension perk checks, specific `has_technology` checks designated as gates) using a checked-in, extensible gate-pattern registry. Unrecognised conditions MUST NOT be silently dropped — they are reported by the build (§4.2.5).
- Gate icons MUST be extracted from mod assets during Stage 1 and converted to a web format (§4.2.2). Icon file paths MUST NOT be manually maintained.

---

### P-4 — Category Filtering

**Requirement.** Users MUST be able to filter the visible tech tree by technology category (e.g. Computing, Voidcraft, Psionics, Materials, Field Manipulation, Biology, Statecraft, Industry, Military Theory, New Worlds, Propulsion, Particles).

**Acceptance criteria.**

- The category list is derived from the dataset at build time; it is never a hard-coded UI list.
- Multiple categories can be selected simultaneously; the filter is additive (union of selected categories).
- Filtering is non-destructive: clearing the filter restores the full view without a page reload.
- Filter state is encoded in the URL.
- Filtering MUST NOT reflow the layout. Filtered-out nodes are hidden or dimmed in place, so that node positions remain stable and the user's spatial memory is preserved.

**Implied technical decisions.**

- Because layout is static (P-2), filtering is a *visibility* operation over a fixed coordinate space, not a re-layout. Edges with at least one hidden endpoint MUST be hidden or dimmed consistently with their endpoints.
- Category filters MUST compose with crisis filters (P-5), search (P-6) and isolation (P-7). Composition semantics are specified in §4.4.

---

### P-5 — Crisis Tech Separation and Filtering

**Requirement.** Technologies unlocked by Gigastructures crises (e.g. Blokkats, Sirenalia) MUST be visually separated from standard technologies, and MUST be independently filterable by crisis faction.

**Acceptance criteria.**

- Crisis technologies are rendered in a distinct region of the layout (a dedicated band, lane or panel) rather than interleaved with the standard progression columns.
- Each crisis faction is an independently toggleable filter; toggling one faction does not affect another.
- Crisis technologies carry the distinct colour and background treatments defined in S-1.
- A crisis technology's prerequisite relationships to standard technologies (in either direction) remain visible when both are shown.

**Implied technical decisions.**

- The data model MUST carry a `crisisFaction` field (nullable). Faction membership MUST be derived from the source data — e.g. from the technology's category, tag, unlocking event chain, or a checked-in classification rule set — and the derivation method MUST be documented in the pipeline README.
- Because crisis techs occupy a separate region, the layout engine MUST support **multiple layout zones** with independent internal ordering but a shared coordinate space, so that cross-zone edges can be routed (P-8) without overlapping node cards.
- A technology that is both crisis-sourced and normally researchable MUST be represented once, with both classifications recorded; it MUST NOT be duplicated as two nodes.

---

### P-6 — Technology Search

**Requirement.** Users MUST be able to search technologies by name or keyword, with matching results highlighted or isolated within the tree view.

**Acceptance criteria.**

- Search matches against, at minimum: localised name, internal technology key, and description text.
- Results update incrementally as the user types, with no perceptible input lag (see P-10 budgets).
- Matching nodes are visually emphasised; non-matching nodes are dimmed. The user can toggle between *highlight* mode (non-matches dimmed but present) and *isolate* mode (non-matches hidden).
- The view can pan/zoom to fit the result set on request, and can step through results sequentially.
- Search is diacritic- and case-insensitive and tolerant of partial word matches.
- Search state is encoded in the URL.

**Implied technical decisions.**

- A **search index MUST be built at build time** and shipped with the dataset. Linear scans over full description text at runtime are acceptable only if measured within the P-10 budget on a mid-range mobile device; otherwise a prefix/trigram index is required.
- Fuzzy matching (edit distance) is OPTIONAL; if implemented, exact and prefix matches MUST rank above fuzzy matches.

---

### P-7 — Middle-Click Isolation

**Requirement.** Middle-clicking a technology node MUST isolate that node together with all directly related nodes — its prerequisites and the technologies it unlocks — dimming or hiding all unrelated nodes.

**Acceptance criteria.**

- Middle-click (pointer button 1) on a node enters isolation mode centred on that node.
- The isolated set includes the target node, its direct prerequisites, and its direct unlocks. A user-adjustable traversal depth (default: 1 hop in each direction; options for full ancestor/descendant closure) MUST be provided.
- Unrelated nodes are dimmed or hidden per a user-visible setting; edges between unrelated nodes follow the same treatment.
- Isolation is exitable via a clearly labelled control and via the `Escape` key.
- Isolation mode is indicated by persistent on-screen state (e.g. a chip naming the isolated technology).
- Default browser middle-click behaviour (autoscroll, open-in-new-tab) MUST be suppressed on node targets.

**Implied technical decisions.**

- **Middle-click does not exist on touch devices.** P-9 therefore requires an equivalent touch affordance. The specified equivalent is a **long-press** on a node (≥400 ms, movement tolerance ≤10 px), plus an explicit "Isolate" action in the detail popup so the feature is discoverable without gesture knowledge. Both paths MUST produce identical state.
- Isolation MUST be implemented as a visibility/emphasis mask over the static layout — not a re-layout — for the same reason as P-4.
- Adjacency lists (forward and reverse) MUST be precomputed in the dataset; isolation MUST NOT require a graph traversal over edge records at interaction time.

---

### P-8 — Circuit-Trace Connection Lines

**Requirement.** Technologies MUST be connected by lines styled to resemble printed-circuit-board traces: orthogonal (axis-aligned) routing with rounded corners or equivalent PCB-aesthetic styling, consistent with Reference Image 1.

**Acceptance criteria.**

- Connectors run in horizontal and vertical segments only; corners are rounded at a consistent radius.
- Connectors do not pass through node cards.
- Connector colour follows the source technology's classification per S-1, and connectors are visually associated with their endpoints when highlighted or isolated.
- Overlapping parallel runs are separated by a consistent channel spacing so that individual traces remain traceable by eye.

**Implied technical decisions.**

- Edge routes MUST be **computed at build time** and stored as polyline point lists in the dataset. Runtime orthogonal routing with obstacle avoidance across a graph of this size is not compatible with P-9/P-10.
- The router MUST reserve **inter-column channels** for vertical runs and assign each edge a channel index to prevent collinear overlap — the behaviour visible in Reference Image 1, where several traces share a corridor at distinct offsets.
- Rounded corners SHOULD be produced by quadratic/arc segments at each vertex rather than by stroke-linejoin, so the radius is zoom-stable.
- The renderer MUST support drawing many thousands of polylines within frame budget; see §4.3.

---

### P-9 — Mobile Support

**Requirement.** The tool MUST be fully functional and usable on mobile devices, including touch-based panning, zooming, and interaction with technology nodes. No feature available on desktop may be unavailable on mobile.

**Acceptance criteria.**

- One-finger drag pans; two-finger pinch zooms; double-tap zooms to a sensible level centred on the tap point.
- Tap opens the detail popup; long-press isolates (per P-7).
- All interactive targets meet a minimum 44 × 44 CSS-pixel touch target at default zoom.
- The detail popup is usable on a narrow viewport (≥360 px wide) without horizontal scrolling, and is dismissible by swipe and by an explicit close control.
- Filter and search controls are reachable without obscuring the graph, e.g. via a collapsible panel or bottom sheet.
- The application is verified on at least one recent iOS Safari and one recent Android Chrome device, at a mid-range hardware tier, against the P-10 budgets.
- Browser page zoom, pull-to-refresh and overscroll must not conflict with in-canvas gestures.

**Implied technical decisions.**

- Input MUST be handled via Pointer Events with unified handling for mouse, touch and pen; separate mouse and touch code paths are prohibited to avoid behavioural divergence.
- Memory budget on mobile forces a compact dataset representation (typed arrays / columnar structures) and lazy loading of description text and icons (§4.2.4).
- Hover-only affordances are prohibited; every hover behaviour MUST have a tap or press equivalent.

---

### P-10 — High Performance and Automated Maintenance

**Requirement.** The tool MUST be high-performance and MUST support automation via scripts and GitHub Actions CI/CD pipelines. Manual maintenance burden MUST be minimised: data MUST be parseable and updatable programmatically from mod source files.

**Acceptance criteria — performance.**

| Metric | Budget |
| --- | --- |
| Time to interactive (desktop, warm cache) | ≤ 2.0 s |
| Time to interactive (mid-range mobile, cold cache, 4G) | ≤ 5.0 s |
| Sustained frame rate during pan/zoom (desktop) | ≥ 60 fps |
| Sustained frame rate during pan/zoom (mid-range mobile) | ≥ 30 fps |
| Search input → results rendered | ≤ 100 ms |
| Filter toggle → view updated | ≤ 100 ms |
| Initial dataset transfer (compressed) | ≤ 2 MB |

**Acceptance criteria — automation.**

- A single command (e.g. `npm run build:data`) regenerates the entire dataset from source with no manual editing steps.
- A scheduled GitHub Actions workflow checks the upstream mod for changes, regenerates the dataset, runs validation, and opens a pull request (or auto-deploys on a protected branch) when the output changes.
- CI runs on every pull request: parser tests, dataset schema validation, DAG validation (acyclicity, tier consistency), link validation (P-12.6), and a bundle-size check against the budget above.
- Deployment to the production static host is fully automated from the default branch.
- **Zero technology data is hand-authored.** The only hand-maintained files are configuration: empire profiles (P-1), gate patterns (P-3), crisis classification rules (P-5), and overwrite-resolution overrides (P-15).

**Implied technical decisions.**

- Upstream mod sources MUST be pinned to a specific commit or release, recorded in the dataset, and displayed in the UI as a "data as of" marker. Un-pinned fetching makes builds non-reproducible.
- The build MUST fail rather than emit a partial dataset when validation fails, and MUST produce a human-readable diff summary of what changed between dataset versions.

---

### P-11 — User Guide

**Requirement.** A clear, comprehensive user guide MUST be included, covering all interactive features and explaining filtering, search, isolation and navigation.

**Acceptance criteria.**

- The guide is reachable from the main UI in one interaction and does not require leaving the site.
- It documents, at minimum: empire-type selection; reading the tier columns; the meaning of every colour, pattern and badge (cross-referencing S-1); gate indicators; category filtering; crisis filtering; search modes; isolation (both middle-click and long-press); the detail popup fields; and pan/zoom on both desktop and touch.
- Every documented gesture lists both its desktop and its mobile form.
- The guide includes a compact legend that can be opened alongside the graph without losing view state.
- Guide content is versioned in the repository alongside the code, and CI fails if a documented feature identifier no longer exists in the application's feature registry (or, at minimum, a manual review checklist is enforced by PR template).

---

### P-12 — Technology Detail Popup

**Requirement.** Clicking a technology node MUST open a detail popup. All fields listed below are REQUIRED. Where a value is genuinely absent in the source data, the field MUST be rendered with an explicit "not applicable" or "none" state rather than omitted, so that the absence is distinguishable from a data pipeline failure.

| ID | Field | Definition and rendering requirements |
| --- | --- | --- |
| P-12.1 | **Description** | Localised description text for the technology, resolved from localisation files with any embedded formatting/variable tokens either resolved or stripped safely. |
| P-12.2 | **Repeatable** | Boolean, derived from the technology's repeatable/levels definition. If repeatable, the popup MUST also state the level count (finite `n` or infinite) and the per-level cost progression where defined. |
| P-12.3 | **Dangerous** | Boolean, derived from the technology's dangerous flag. MUST be rendered as a prominent warning treatment, not a plain-text row. |
| P-12.4 | **Primary prerequisite** | The technology's designated primary prerequisite. Where multiple prerequisites exist, the primary is selected by the documented rule in §4.5 (OQ-2) and all remaining prerequisites MUST also be listed as secondary. |
| P-12.5 | **Source** | `Vanilla`, `Gigastructural Engineering`, or `Vanilla (modified by Gigastructural Engineering)` — the third value being mandatory for technologies covered by P-15. |
| P-12.6 | **Repository link** | A direct hyperlink to the technology's definition in the Gigastructures GitHub repository. MUST be a permalink pinned to the build's source commit, and MUST target the file and line range of the definition, not merely the repository root. For unmodified vanilla technologies, the link target is specified in §4.5 (OQ-5). |
| P-12.7 | **Primary gate** | The primary gate per P-3, rendered with its icon. Additional gates MUST be listed beneath it. |
| P-12.8 | **Research weight & cost** | The technology's base research weight and its research cost. Because weight is modified at runtime by in-game conditions, the popup MUST render the base weight plus an expandable list of the weight modifiers and their conditions (see §4.5, OQ-4). Cost MUST reflect modded values per P-15 and, for repeatables, the cost progression per P-12.2. |
| P-12.9 | **Full research path** | The complete prerequisite chain required to reach this technology **computed for the currently selected empire type**. For an empire using biological shipsets, a path that would read Corvettes → Destroyers → Cruisers → Battleships for a standard empire MUST instead list the equivalent biological ship technologies. The path MUST be presented in research order, MUST indicate tier for each step, MUST show the cumulative research cost of the chain, and each step MUST be clickable to navigate to that node. |

**Additional acceptance criteria.**

- The popup MUST be openable by click (desktop) and tap (mobile), and MUST include an explicit "Isolate this technology" action (per P-7).
- Opening a popup MUST NOT reset pan/zoom state.
- The popup MUST be deep-linkable: its URL encodes the technology key and the selected empire type.
- The popup MUST display any empire-type lock state per P-13.

**Implied technical decisions.**

- P-12.9 requires **per-empire-type path computation at build time**. Storing a single canonical path and substituting swaps in the browser is prohibited, because tech swaps can change the *shape* of the chain, not merely its labels.
- The research path is a subgraph, not necessarily a single linear chain. The rendering rule is specified in §4.5 (OQ-1).

---

### P-13 — Empire-Type Tech Locking

**Requirement.** Technologies that are unavailable to specific empire types (e.g. nomadic empires) MUST be clearly labelled as locked, with the specific empire-type restriction displayed.

**Acceptance criteria.**

- When an empire type is selected, technologies unavailable to it are rendered in a distinct locked state (e.g. desaturated with a lock badge), and the state is distinguishable from the dimming used by filtering (P-4), search (P-6) and isolation (P-7).
- The lock badge names the restriction (e.g. "Unavailable: Nomadic empires").
- The detail popup lists the full set of empire types for which the technology is available and unavailable.
- The user can choose whether locked technologies are hidden entirely or shown in the locked state; the default is shown-and-locked, so that the restriction is discoverable.
- A locked technology's edges are rendered in the locked state as well, so that a broken path is legible as broken.

**Implied technical decisions.**

- Lock state MUST be stored per `(technology, empire type)` pair with a **human-readable reason string** derived from the trigger condition that caused the lock. A bare boolean is insufficient to satisfy the labelling requirement.
- Where the lock reason cannot be derived automatically from the trigger, the build MUST fall back to a checked-in reason override table and MUST warn when an override is missing (surfaced via S-2).

---

### P-14 — Unconventional Prerequisite Handling

**Requirement.** The tool MUST correctly parse and represent unconventional prerequisite definitions, including `has_technology = x` checks appearing inside a `potential` block rather than a `prerequisites` block. This pattern is used so that one empire type can research a technology through the normal prerequisite chain while a different empire type (e.g. nomads, for whom the standard prerequisite is inaccessible) can access the same technology under different conditions. **Both access paths MUST be represented accurately.**

**Acceptance criteria.**

- The parser extracts technology dependencies from `prerequisites` blocks **and** from `has_technology` checks located within `potential` and other trigger blocks.
- Each extracted dependency records: the technology it depends on, the block it came from (`prerequisites` vs. `potential` vs. other), and the empire-type conditions under which it applies.
- A technology reachable by two different routes for two different empire types renders **both** routes: the applicable route is shown as a solid edge for the selected empire type, and the alternative route is available for inspection (e.g. as a distinct edge style, or listed in the detail popup as "Alternative access path").
- The detail popup's research path (P-12.9) uses the route valid for the selected empire type.
- Dependencies extracted from trigger blocks are visually distinguishable from formal prerequisites, since they behave differently in game (they gate availability rather than forming the research chain).

**Implied technical decisions.**

- The edge model MUST support **typed, conditional edges**: `{ from, to, kind: "prerequisite" | "potential-gate" | "alternative", appliesToEmpireTypes: [...] }`. A plain unlabelled adjacency list cannot satisfy this requirement.
- Trigger blocks may contain arbitrary boolean structure (`OR`, `AND`, `NOT`, `NOR`). The extractor MUST preserve this structure rather than flattening it, because a `has_technology` inside a `NOT` is a *negative* dependency and inverting it silently would produce a wrong graph.
- Conditions the evaluator cannot resolve MUST be recorded as `unknown` and reported, never assumed true or false (§4.2.3).

---

### P-15 — Vanilla Technology Overwrite Accounting

**Requirement.** Where Gigastructures overwrites or modifies vanilla Stellaris technologies, the tool MUST reflect the modded values, not the base-game values.

**Acceptance criteria.**

- The build loads vanilla technology definitions and mod definitions, and applies the game's load-order override semantics: a technology key defined in the mod fully replaces the vanilla definition of that key.
- Every affected technology is labelled `Vanilla (modified by Gigastructural Engineering)` in the detail popup (P-12.5).
- The detail popup for a modified vanilla technology MUST make the modification inspectable — at minimum, listing which fields differ from vanilla (cost, tier, prerequisites, weight, category, flags).
- The build emits a machine-readable overwrite report listing every overridden vanilla technology and the fields changed. This report is surfaced in the `/?dev` build (S-2).
- If the mod adds prerequisites to a vanilla technology, the graph reflects the modded prerequisite set, and layout (P-2) is recomputed accordingly.

**Implied technical decisions.**

- The build MUST require a **local vanilla `common/technology` corpus** in addition to the mod source. Because base-game files are not redistributable, the pipeline MUST support supplying them via a path or secret-mounted archive in CI, and MUST fail with a clear message when they are absent rather than silently producing a mod-only graph. This is a deployment prerequisite, not an optional extra.
- Overwrite resolution is **whole-key replacement**, matching engine behaviour — not a field-level merge. Any deviation from this rule for presentation purposes (e.g. field-level diffing for the popup) MUST be computed as a comparison *after* resolution, never applied to the authoritative graph.
- The vanilla corpus version MUST be pinned and recorded alongside the mod version in the dataset metadata.

---

## 3. Secondary Requirements

Secondary requirements are expected in the initial release but MAY be deferred if they threaten the primary set. Any deferral MUST be recorded in the repository's roadmap.

---

### S-1 — Colour Coding by Technology Type

**Requirement.** Technologies MUST be colour-coded by research area and crisis faction as follows:

| Classification | Colour | Background treatment |
| --- | --- | --- |
| Physics | Blue | Flat (default) |
| Society | Green | Flat (default) |
| Engineering | Orange | Flat (default) |
| Blokkat crisis techs | Green | Hexagonal pattern |
| Sirenalia crisis techs | Purple | Swirl / wave pattern |

**Acceptance criteria.**

- Colours are defined as design tokens in a single source of truth consumed by both node rendering and connector rendering (P-8).
- Because Blokkat green and Society green share a hue, the hexagonal pattern is **load-bearing, not decorative**: the two MUST remain distinguishable at all zoom levels, including when patterns are simplified for performance (see below).
- Background patterns MUST NOT reduce the legibility of node text, icons or gate indicators.
- Colour MUST NOT be the sole carrier of any information required to use the tool. Each classification MUST also be conveyed by a non-colour channel (pattern, badge, or label) so the tool remains usable with colour-vision deficiency. The user guide legend (P-11) MUST document both channels.

**Implied technical decisions.**

- Patterns MUST degrade gracefully: at low zoom, per-node pattern fills become prohibitively expensive. The renderer SHOULD switch to a solid distinguishing treatment (e.g. a saturation/border variant) below a defined zoom threshold, and this threshold MUST be documented and consistent with S-3.

---

### S-2 — Developer Branch / Diagnostics Build

**Requirement.** A developer-accessible build MUST be available by appending `/?dev` to the URL. It MUST display page performance metrics and any runtime errors.

**Acceptance criteria.**

- Appending `?dev` to any application URL enables the diagnostics overlay without altering graph state or requiring a different deployment.
- The overlay displays, at minimum: current and rolling-average frame rate, frame time, node/edge counts (total and currently drawn), dataset load time and size, memory usage where the browser exposes it, and time-to-interactive.
- All runtime errors and unhandled promise rejections are captured and displayed in the overlay with message and stack, rather than being visible only in the browser console.
- Build-time warnings carried in the dataset — tier promotions (P-2), unrecognised gate patterns (P-3), missing lock reasons (P-13), unresolved triggers (P-14), and the overwrite report (P-15) — are browsable in the overlay.
- Dataset metadata (mod commit, vanilla version, build timestamp, schema version) is displayed.
- The overlay is inert unless explicitly enabled, and its code MUST NOT measurably affect the P-10 budgets when disabled.

**Implied technical decisions.**

- `?dev` is a query parameter, not a path segment. The application MUST parse it from the query string and MUST preserve it across in-app URL updates (empire type, filters, search, popup deep links) so that a developer does not lose the overlay while navigating.
- The diagnostics bundle SHOULD be code-split and loaded on demand to protect the initial transfer budget.

---

### S-3 — Tier Differentiation at Low Zoom

**Requirement.** Tiers MUST remain visually distinguishable when the user is zoomed out. The recommended approach is to alternate the tier band background between the default tier colour and a slightly desaturated variant. Alternative approaches achieving clear tier separation are acceptable.

**Acceptance criteria.**

- At the minimum supported zoom level, a user can identify tier boundaries without reading node text.
- Tier bands are labelled (e.g. a sticky "T4" header per band) and the labels remain legible or gracefully scale at low zoom.
- The alternating treatment does not conflict with, or reduce the contrast of, the node colour coding in S-1 or the locked-state treatment in P-13.

**Implied technical decisions.**

- Band backgrounds are part of the static layout and SHOULD be drawn as a single background layer beneath nodes and connectors, so the cost is independent of node count.
- A **level-of-detail (LOD) system** is implied: at low zoom, node cards should progressively drop text, then icons, then reduce to coloured blocks. LOD thresholds MUST be defined in one place and shared by S-1's pattern degradation and this requirement.

---

## 4. Implementation Notes

This section surfaces technical decisions implied by the requirements and open questions that MUST be resolved before implementation begins. It is normative where it uses RFC 2119 language and advisory otherwise.

### 4.1 Recommended Technology Choices

These are recommendations, not mandates; deviations MUST still satisfy the acceptance criteria above.

| Concern | Recommendation | Rationale |
| --- | --- | --- |
| Data pipeline language | TypeScript or Python, run in GitHub Actions | Single-language repo (TS) simplifies sharing the dataset schema between build and client. |
| Clausewitz parser | Purpose-built tokeniser + recursive-descent parser producing a lossless AST | Off-the-shelf parsers frequently discard comments, duplicate keys and block structure that P-14 depends on. |
| Rendering | WebGL/WebGPU-backed 2D canvas (e.g. PixiJS) or a hand-rolled canvas renderer, with an HTML/DOM overlay for popups and controls | Meets P-9/P-10 at 10³–10⁴ nodes; DOM/SVG-per-node does not. |
| State & URL | Lightweight client-side state store with URL as the single source of truth for shareable state | Required by P-1, P-4, P-6, P-12 deep links, S-2. |
| Hosting | Static host (GitHub Pages, Cloudflare Pages) | Required by P-10's automation and zero-backend architecture. |
| Dataset format | JSON (structural) + typed-array/binary side-files (geometry) | Keeps transfer within budget; geometry compresses poorly as JSON. |

### 4.2 Data Pipeline

#### 4.2.1 Stage 1 — Extraction

1. Fetch the mod source at a pinned commit; fetch/mount the vanilla `common/technology` corpus at a pinned game version.
2. Parse all technology files into a lossless AST. The parser MUST preserve: duplicate keys, block nesting, comparison operators (`=`, `>`, `<`, `>=`, `<=`), and comments (some mods encode intent in comments; retaining them costs nothing and aids debugging).
3. Parse localisation YAML for names, descriptions and gate labels, for at least English, with the language set configurable.
4. Extract and convert icon assets (`.dds`) to a web format (WebP with PNG fallback), packed into sprite atlases keyed by technology and gate identifier.

#### 4.2.2 Icon Handling

`.dds` (DXT-compressed) assets are not directly usable in browsers. The build MUST decode and re-encode them. Atlas generation MUST be deterministic so that unchanged icons produce byte-identical output and do not churn the deployment. Icons MUST be looked up by key derived from the source data, never by a hand-maintained path map.

#### 4.2.3 Trigger Evaluation

This is the highest-risk component of the system and deserves explicit design attention.

Clausewitz triggers are a full conditional language evaluated against live game state. Determining "is technology X available to empire type Y" is therefore **not decidable in general** from static analysis. The specified approach is a **partial evaluator**:

- Empire profiles (P-1) supply a set of known facts.
- The evaluator walks the preserved boolean structure of each trigger block and resolves what it can.
- Every condition resolves to `true`, `false`, or `unknown`.
- `unknown` MUST propagate: `unknown AND false` is `false`, but `unknown AND true` is `unknown`.
- Technologies whose availability resolves to `unknown` MUST be flagged in the dataset, rendered with an "availability uncertain" indicator, and listed in the `/?dev` overlay so that the fact registry can be extended over time.

Assuming `unknown` means "available" (or "unavailable") would produce a confidently wrong tree, which is worse for the user than an honestly uncertain one.

#### 4.2.4 Stage 2 — Dataset Emission

To satisfy both P-1 (per-empire-type correctness) and P-10 (transfer budget), the recommended structure is:

- **Base dataset** — technology records, layout coordinates, edge geometry, search index, icon atlas references. Shared across empire types.
- **Empire overlays** — per-empire-type availability flags, lock reasons, active edge set, swap mappings, and precomputed research paths. Loaded on demand when the user selects an empire type.
- **Detail payloads** — descriptions, weight modifier lists, and repository links, chunked and lazily fetched when a popup opens.

The dataset MUST carry a `schemaVersion`. The client MUST refuse to render a dataset whose schema version it does not support, with a clear message, rather than degrading silently.

#### 4.2.5 Validation Gates

The build MUST fail on: parse errors, cycles in the prerequisite graph, dangling technology references, missing localisation for a displayed string, missing icons, schema violations, and dead repository links. The build MUST warn (and record for S-2) on: tier promotions, unrecognised gate patterns, `unknown` trigger resolutions, missing lock-reason overrides, and newly overridden vanilla technologies.

#### 4.2.6 Extensibility

Although only Gigastructures is in scope, the pipeline SHOULD treat mods as an ordered list of sources with load-order override semantics (per P-15), so that adding a second mod is a configuration change. Hard-coding "vanilla" and "Gigastructures" as two special cases in the resolution logic SHOULD be avoided.

### 4.3 Rendering Architecture

- **Static layout, dynamic visibility.** All filtering, search and isolation operate as masks over fixed geometry. Nothing re-lays-out at runtime. This underpins P-2, P-4, P-6, P-7 and the performance budgets.
- **Viewport virtualisation.** Nodes and edges MUST be culled against the viewport, using a spatial index (grid or R-tree) computed at build time.
- **Layer separation.** Tier band backgrounds (S-3), connectors (P-8), node cards, and emphasis overlays SHOULD be separate render layers so that a filter toggle redraws only the affected layers.
- **Level of detail.** A single shared LOD threshold table governs S-1 pattern degradation, S-3 band emphasis, and node card text/icon shedding.
- **Accessibility.** A canvas renderer is opaque to assistive technology. The application MUST maintain a parallel accessible representation — at minimum, keyboard-navigable focus over visible nodes, an accessible name for the focused node, and a DOM-based detail popup (which the popup already is). Full keyboard equivalence for pan/zoom/filter/search SHOULD be provided.

### 4.4 Interaction Composition Semantics

Filters, search and isolation can be active simultaneously. The specified composition, in precedence order, is:

1. **Empire-type lock state (P-13)** applies first and is never overridden — a locked technology is always shown as locked when visible.
2. **Isolation (P-7)**, when active, defines the candidate set: only the isolated node and its related nodes are eligible for display.
3. **Category and crisis filters (P-4, P-5)** intersect with the candidate set.
4. **Search (P-6)** applies emphasis (highlight mode) or further restriction (isolate mode) within the result of steps 1–3.

The UI MUST show all active constraints simultaneously (e.g. as removable chips) and MUST provide a single "clear all" control, so a user cannot get stuck looking at an empty graph without understanding why.

### 4.5 Open Questions Requiring Resolution Before Implementation

These are genuine ambiguities in the requirements. Each needs a decision recorded in the repository before the affected component is built.

- **OQ-1 — Research path shape (P-12.9).** A "full research path" through a DAG is generally a set of ancestor technologies, not a single ordered chain, and multiple minimal chains may exist. Decide: does the popup show (a) the complete ancestor set in a topologically valid order, (b) the cheapest single chain by cumulative research cost, or (c) a small tree view? *Recommendation:* (a) as the default, presented in tier order with cumulative cost, with (b) offered as a "shortest path" toggle — (a) is the only one that is unambiguously correct, while (b) is what most users actually want to read.
- **OQ-2 — Primary prerequisite selection (P-12.4).** When a technology declares several prerequisites, which is "primary"? Candidate rules: first declared in source; highest tier; same research area as the technology itself; highest cost. *Recommendation:* same-area prerequisite if exactly one exists, otherwise highest tier, otherwise first declared — and always list the remainder.
- **OQ-3 — Gate ordering (P-3, P-12.7).** When a technology has multiple gates (e.g. an ascension perk *and* a gating technology), which is primary? *Recommendation:* a checked-in priority ordering in the gate-pattern registry, with ascension perks outranking technology gates.
- **OQ-4 — Research weight presentation (P-12.8).** Research weight in Stellaris is a base value plus a set of conditional multipliers evaluated against live empire state; a single number is misleading. Decide whether the popup shows base weight only, base plus a modifier list, or an empire-type-evaluated weight using the partial evaluator. *Recommendation:* base weight prominently, with an expandable modifier list; evaluated weight is beyond the reliability of static analysis and risks presenting a wrong number authoritatively.
- **OQ-5 — Repository links for unmodified vanilla technologies (P-12.6).** The requirement specifies a link into the Gigastructures repository, but unmodified vanilla technologies are not defined there. Decide: omit the link (conflicts with the "all fields required" rule), link to a vanilla reference such as the wiki, or link to the Gigastructures file only where an override exists. *Recommendation:* render the field always, with the Gigastructures permalink where an override exists and a clearly labelled vanilla-reference link otherwise.
- **OQ-6 — Empire type enumeration (P-1).** The requirements name nomadic, biological-shipset and mechanical-shipset empires as examples. The exact, complete list of supported profiles for v1 must be fixed, since it determines build time and dataset size. Are combinations (e.g. nomadic *and* biological) required as distinct profiles, or are the axes independent and composable? *Recommendation:* model empire type as **independent axes** (shipset type, nomadic status, machine status) composed at build time, rather than a flat enumeration — a flat list combinatorially explodes.
- **OQ-7 — Crisis faction coverage (P-5).** Blokkats and Sirenalia are named as examples. The full list of crisis factions to support, and the authoritative rule for assigning a technology to a faction, must be fixed. Colour and pattern treatments beyond the two specified in S-1 will need to be designed.
- **OQ-8 — Vanilla corpus provisioning (P-15).** Base-game files cannot be redistributed. The mechanism for supplying them to CI (licensed developer-supplied archive, contributor-local builds only, or an extracted metadata-only subset) must be settled early, as it gates the entire overwrite-accounting requirement.
- **OQ-9 — Localisation scope (P-11, P-12.1).** English-only for v1, or multi-language? This affects dataset size, the search index (P-6) and the user guide. *Recommendation:* English-only for v1, with the pipeline language-parameterised so additional languages are a build flag.
- **OQ-10 — Handling of `unknown` availability (§4.2.3).** The visual treatment and the tolerance threshold need agreement: what percentage of `unknown` results is acceptable before a release is blocked?

### 4.6 Suggested Delivery Sequence

1. Clausewitz parser + AST, with a test corpus of real mod files (highest risk, blocks everything).
2. Vanilla + mod overwrite resolution (P-15) and the base graph, validated for acyclicity.
3. Trigger extraction including `potential`-block dependencies (P-14) and the partial evaluator (§4.2.3).
4. Empire profiles and per-empire-type computation (P-1, P-13, P-12.9).
5. Layout, tier columns and orthogonal edge routing (P-2, P-8).
6. Renderer with pan/zoom, LOD and virtualisation, desktop and touch (P-9, P-10).
7. Node cards, colour coding, gate indicators (P-3, S-1, S-3).
8. Filtering, search, isolation (P-4, P-5, P-6, P-7).
9. Detail popup (P-12).
10. CI/CD automation, scheduled upstream sync (P-10).
11. `?dev` diagnostics overlay (S-2).
12. User guide (P-11).

Items 1–4 constitute the correctness core; if they are wrong, every downstream feature renders wrong information convincingly. They SHOULD be covered by unit tests against real mod source fixtures before any UI work begins.
