# P-12 — Technology detail popup

**Requirement.** Clicking or tapping a technology node MUST open a detail popup. All fields
below are REQUIRED. Where a value is genuinely absent in the source data, the field MUST render
an explicit "none" or "not applicable" state rather than being omitted, so absence is
distinguishable from a pipeline failure.

| ID | Field | Rendering requirements |
| --- | --- | --- |
| P-12.1 | Description | Localised description, with embedded formatting and variable tokens resolved or safely stripped. English only for v1 (D-9) |
| P-12.2 | Repeatable | Boolean plus level count. Rendered as `Repeatable: ×40` or `Repeatable: ∞`, with the per-level cost progression where defined. **Also rendered on the node card** |
| P-12.3 | Dangerous | Boolean, rendered as a prominent warning treatment, not a plain text row |
| P-12.4 | Prerequisites | **A flat list. There is no primary prerequisite** — all declared prerequisites are equally required. Ordered by tier descending, then cost descending, then key |
| P-12.5 | Source | `Vanilla`, `Gigastructural Engineering`, or `Vanilla (modified by Gigastructural Engineering)` |
| P-12.6 | Repository link | Gigastructures permalink pinned to the build commit, targeting file and line range, where an override exists. Otherwise a Stellaris wiki link. For ACOT/AoT-sourced technologies (P-16), a link to that mod's Steam Workshop item page (D-5) |
| P-12.7 | Primary gate | The primary gate per P-3, with its icon. Additional gates listed beneath |
| P-12.8 | Research weight and cost | Base weight prominently, plus an expandable list of weight modifiers and their conditions. **No evaluated weight** (D-4). Cost reflects modded values per P-15 |
| P-12.9 | Research path | The complete ancestor set required to reach this technology, **computed for the selected empire profile**, in topological order by tier, with cumulative cost. A "shortest chain" toggle offers the cheapest single chain. Each step is clickable |
| P-12.10 | Mod requirement | Any external mod dependency per P-16, or an explicit "none" state |
| P-12.11 | Rare | Boolean, derived from the technology's rarity flag in source data (see the glossary in `00-overview.md`). Rendered as a badge, not a warning treatment — contrast P-12.3 |

## Additional acceptance criteria

- The popup MUST include an explicit "Isolate this technology" action (P-7).
- Opening a popup MUST NOT reset pan or zoom state.
- The popup MUST be deep-linkable: its URL encodes the technology key and the empire profile.
- The popup MUST display empire availability state per P-13 (available, locked or uncertain),
  leading with the minimal violated-constraint summary and offering the full twelve-profile
  matrix behind an expand control, per P-13.
- The popup MUST be usable at a 360 px viewport width without horizontal scrolling, and
  dismissible by swipe and by an explicit close control.

## Implied technical decisions

- P-12.9 requires **per-profile path computation at build time**. Storing one canonical path and
  substituting swaps in the browser is prohibited: swaps change the shape of the chain, not
  merely its labels.
- The research path is a subgraph, not necessarily a linear chain. Presentation follows D-1.
- Wiki anchors derive from localised technology names and are occasionally wrong. CI MUST
  validate that each anchor resolves in the fetched page and fall back to a wiki search URL
  where it does not, so the field is never dead and never omitted.
- Description text, modifier lists and links are lazily fetched detail payloads (see
  `00-overview.md`), not part of the base dataset.
