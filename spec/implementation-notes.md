# Implementation notes

## Trigger evaluation

This is the highest-risk component of the system and deserves explicit design attention.

Clausewitz triggers are a full conditional language evaluated against live game state.
Determining "is technology X available to empire type Y" is therefore **not decidable in
general** from static analysis. The specified approach is a **partial evaluator**:

- Empire profiles (P-1) supply a set of known facts.
- The evaluator walks the preserved boolean structure of each trigger block and resolves what it
  can.
- Every condition resolves to `true`, `false`, or `unknown`.
- `unknown` MUST propagate: `unknown AND false` is `false`, but `unknown AND true` is `unknown`.
- Technologies whose availability resolves to `unknown` MUST be flagged in the dataset, rendered
  with an "availability uncertain" indicator, and listed in the `/?dev` overlay so that the fact
  registry can be extended over time.

Assuming `unknown` means "available" (or "unavailable") would produce a confidently wrong tree,
which is worse for the user than an honestly uncertain one.

## Stage 2 — Dataset emission

To satisfy both P-1 (per-empire-type correctness) and P-10 (transfer budget), the recommended
structure is:

- **Base dataset** — technology records, layout coordinates, edge geometry, search index, icon
  atlas references. Shared across empire types.
- **Empire overlays** — per-empire-profile availability state (available / locked / uncertain,
  P-13), lock or uncertainty reasons, active edge set, swap mappings, and precomputed research
  paths. Loaded on demand when the user selects a profile.
- **Detail payloads** — descriptions, weight modifier lists, and repository links, chunked and
  lazily fetched when a popup opens.

The dataset MUST carry a `schemaVersion`. The client MUST refuse to render a dataset whose schema
version it does not support, with a clear message, rather than degrading silently.

## Rendering architecture

- **Static layout, dynamic visibility.** All filtering, search and isolation operate as masks
  over fixed geometry. Nothing re-lays-out at runtime. This underpins P-2, P-4, P-6, P-7 and the
  performance budgets.
- **Viewport virtualisation.** Nodes and edges MUST be culled against the viewport, using a
  spatial index (grid or R-tree) computed at build time.
- **Layer separation.** Tier band backgrounds (S-3), connectors (P-8), node cards, and emphasis
  overlays SHOULD be separate render layers so that a filter toggle redraws only the affected
  layers.
- **Level of detail.** A single shared LOD threshold table governs S-1 pattern degradation, S-3
  band emphasis, and node card text/icon shedding.
- **Accessibility.** A canvas renderer is opaque to assistive technology. The application MUST
  maintain a parallel accessible representation — at minimum, keyboard-navigable focus over
  visible nodes, an accessible name for the focused node, and a DOM-based detail popup (which the
  popup already is). Full keyboard equivalence for pan/zoom/filter/search SHOULD be provided.

## Feature registry

A checked-in JSON file (e.g. `feature-registry.json`) enumerating every user-facing feature
identifier the user guide (P-11) is permitted to document — one entry per documented gesture,
control or field, each carrying at minimum an `id` and the requirement it implements (e.g.
`"long-press-isolate": "P-7"`). CI parses the guide content, extracts every feature identifier it
references, and fails the build if any identifier isn't present in this file — catching guide
content that documents a feature which was renamed or removed. Adding a feature to the
application requires adding its entry here in the same change, so the registry cannot silently
drift out of sync with what's actually built.

## Interaction composition semantics

Filters, search and isolation can be active simultaneously. The specified composition, in
precedence order, is:

1. **Empire-profile availability state (P-13)** applies first and is never overridden — a locked
   or uncertain technology is always shown as such when visible.
2. **Isolation (P-7)**, when active, defines the candidate set: only the isolated node and its
   related nodes are eligible for display.
3. **Category and crisis filters (P-4, P-5)** intersect with the candidate set.
4. **Search (P-6)** applies emphasis (highlight mode) or further restriction (isolate mode)
   within the result of steps 1–3.

The UI MUST show all active constraints simultaneously (e.g. as removable chips) and MUST
provide a single "clear all" control, so a user cannot get stuck looking at an empty graph
without understanding why.
