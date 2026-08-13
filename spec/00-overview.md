# Overview

## Purpose

An interactive web tech tree visualiser for *Gigastructural Engineering & More*. It renders the
combined vanilla plus Gigastructures technology graph as a left-to-right, tier-columned
flowchart, and lets a user filter, search, isolate and inspect individual technologies.

The graph is large, heavily conditional on empire type, and subject to frequent upstream
change. Empire-type-aware graph computation and zero-manual-maintenance data extraction are
therefore first-class architectural concerns, not features bolted onto a static diagram.

## Scope

In scope: automated extraction from mod and base-game sources; build-time per-empire-type graph
computation; a client-side rendering and interaction layer; a developer diagnostics build; end
user documentation.

Out of scope: editing mod content; save-game parsing; server-side components of any kind. The
deliverable is a static site.

Mods other than Gigastructures are rendered only where necessary: an ACOT or AoT technology is
emitted as a node only if it falls in the rendering-scope closure of a rendered vanilla or
Gigastructures technology, so that no rendered technology's prerequisite chain has an invisible
gap. There is no user-facing control over this — see `P-16-mod-requirements.md`.

## Sources and load order

Ordered list, lowest priority first. Do not special-case any entry in resolution logic; adding
a source must be a configuration change.

| Source | Version | Provisioning | Update path |
| --- | --- | --- | --- |
| Stellaris base game | 4.5 | local, gitignored | manual, re-run the collector |
| Gigastructural Engineering & More | pinned commit | GitHub | automated, scheduled CI |
| Ancient Cache of Technologies (ACOT) | manual | Steam Workshop | manual |
| Acquisition of Technology (AoT) | manual | Steam Workshop | manual, requires ACOT |

Base-game and Workshop files are not redistributable. They live in a gitignored `vendor/`
directory populated by `tools/collect_vanilla.py`, which also records a hash of each tree so CI
can detect that a local copy changed even though it cannot fetch a new one.

Overwrite resolution is **whole-key replacement**, matching engine behaviour. Never a
field-level merge. Any field-level diff for presentation is computed *after* resolution and
never applied to the authoritative graph.

Required base-game directories: `common/technology`, `common/scripted_variables`,
`common/scripted_triggers`, `common/ascension_perks`, `common/inline_scripts`,
`localisation/english`, `gfx/interface/icons/technologies`.

`common/scripted_triggers` is the single biggest lever on the unresolved-trigger rate. Without
it the partial evaluator sees opaque tokens and returns `unknown` far more often than the
logic actually warrants.

## Glossary

| Term | Definition |
| --- | --- |
| Tech node | A single technology rendered as a card: icon, localised name, research cost, tier badge, repeatable indicator, and zero or more gate and mod badges |
| Tier | The technology's declared `tier` value. Drives column assignment. Range is unbounded |
| Area | Vanilla research area: physics, society, engineering. Drives background colour |
| Category | Sub-category such as Computing, Voidcraft, Psionics. Drives category filtering |
| Rare | A technology flagged by the mod's own rarity marker in source data, mirroring how "dangerous" is derived from the mod's own dangerous flag (P-12.3). Drives the outline-priority and badge treatment in S-1 |
| Gate | A non-prerequisite unlock condition displayed on the node, such as an ascension perk |
| Mod requirement | A dependency on a mod other than Gigastructures. Distinct from a gate |
| Empire profile | A composed point in the empire axis space, supplying trigger facts |
| Tech swap | Functionally equivalent technologies, mutually exclusive by empire type |
| Crisis tech | A technology from a Gigastructures crisis chain rather than normal research |
| Isolation | An interaction mode in which only a chosen node and its related nodes stay visible |
| Trigger block | A Clausewitz conditional block (`potential`, `allow`, `weight_modifier`) |

## Architecture

Three stages. The boundaries are load-bearing.

**Stage 1 — Extract** (Python, CI). Fetch pinned mod source and mount the vendored corpus.
Parse all technology files into a lossless AST preserving duplicate keys, block nesting,
comparison operators and comments. Parse localisation YAML. Decode `.dds` icons and pack
deterministic atlases.

**Stage 2 — Compute** (Python, CI). Resolve overwrites across the source list. Build the DAG
and validate acyclicity. Evaluate triggers per empire profile. Assign tiers and columns. Route
edges. Emit the dataset.

**Stage 3 — Render** (TypeScript + PixiJS, browser). Load the dataset, cull against the
viewport, handle pan, zoom, filter, search, isolate and inspect.

The browser never parses Clausewitz script and never computes layout. Runtime does visibility
masking over fixed geometry, nothing more.

The dataset schema is a cross-language contract: JSON Schema in `schema/`, TypeScript types
generated from it, Python output validated against it in CI.

### Dataset structure

- **Base dataset** — technology records, layout coordinates, edge geometry, search index, icon
  atlas references. Shared across empire profiles.
- **Empire overlays** — per-profile availability flags, lock reasons, active edge set, swap
  mappings, precomputed research paths. Loaded on demand.
- **Detail payloads** — descriptions, weight modifier lists, repository links. Chunked and
  lazily fetched when a popup opens.

The dataset MUST carry a `schemaVersion`. The client MUST refuse to render an unsupported
version with a clear message rather than degrading silently.
