# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Gigastructural Engineering Tech Tree

Interactive tech tree visualiser for the Stellaris mod *Gigastructural Engineering & More*.
Static client-side site, deployed to GitHub Pages. No backend, ever.

The normative requirements live in `spec/`. This file records decisions that are
settled, so they are not re-litigated. If something here conflicts with `spec/`,
this file is newer — flag the conflict and amend the spec.

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

### Mods as a user-facing dimension

A mod-set selector sits beside the empire-type selector: checkboxes for ACOT and AoT, both on
by default, URL-encoded. Unticking ACOT force-unticks and disables AoT. Mod requirement is a
`requiresMods: string[]` field rendered as a card badge (`ACOT`, `AoT`) — distinct from gates
and from prerequisites.

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

Colour is never the sole carrier. Rare and dangerous each also get a card badge, shedding at
the same LOD threshold as the gate label.

Crisis factions: Aeternum, Blokkats, Compound, Sirenalia, Katzenartig Imperium. Faction
assignment is derived from tech ID, then from `potential`/prerequisites, then from a checked-in
manual override file for the remainder.

Exact hex values live in `tokens/` as the single source of truth, consumed by node rendering
and connector rendering alike. Do not hardcode colours in components.

*(Palette values pending sign-off — see open items.)*

### Repeatables

Shown on the card and in the popup as `Repeatable: ×40`, or `Repeatable: ∞` when unbounded.

### Repository links

Gigastructures permalink pinned to the build commit, targeting file and line range, where an
override exists. Otherwise a Stellaris wiki link. CI validates that wiki anchors resolve and
falls back to a wiki search URL where they do not — the field is always populated, never dead.

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
  profiles, gate patterns, crisis classification overrides, overwrite overrides, mod metadata.
- The build fails rather than emitting a partial dataset. Fail on parse errors, graph cycles,
  dangling references, missing localisation for displayed strings, missing icons, schema
  violations, dead repository links.
- All shareable state goes in the URL: empire type, mod set, filters, search, open popup.
- No runtime re-layout. Filtering, search and isolation are visibility masks.
- Every hover behaviour needs a tap or press equivalent. Pointer Events only — no separate
  mouse and touch code paths.
- Icon atlases must pack deterministically. Unchanged icons produce byte-identical output.

## Commands

*(To be filled in as the pipeline lands.)*

    python tools/collect_vanilla.py     # populate vendor/ from the local Steam install

## Open items

- Palette hex values not yet signed off. Blokkat `#1C451C` is too dark to survive the low-zoom
  LOD; Compound `#2F137F` and Katzenartig `#2E3F98` collide at low zoom.
- Pattern tile for Blokkats needs tracing to clean SVG from the supplied flag image.
- Repo layout and package scaffolding not yet created.
