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
| P-12.9 | Research path | **See `spec/P-12.9-research-path.md` for the full algorithm (spec only, not yet implemented as of that file's writing) — this row is a summary, not the authority.** The complete ancestor set required to reach this technology, computed per selected empire profile over true `prerequisite` edges plus resolved `OR`-group (`alternative` edge) selection — cheapest total cost among viable (available/uncertain) branch candidates, expanded fully, never left as an unexpanded label. `uncertain` steps stay in the path with the total marked an estimate; `config-gated` steps are excluded from the total and listed separately with D-10's reason wording. Each step renders under the selected profile's D-14 name/icon substitution. Each step is clickable. The v1 "shortest chain" toggle is retired — see that file for why. |
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
  merely its labels. **Generalised in `spec/P-12.9-research-path.md`**: nothing about the path's
  shape — which `OR`-branch was chosen, which steps are in it, the total and whether it's an
  estimate — is computed client-side either, not just the D-14 name/icon substitution.
- The research path, as v1 presented it and as this project keeps it (confirmed wanted, not
  re-litigated), is a flat ordered list with a running cumulative cost, not the full ancestor
  subgraph rendered as its own structure — see `spec/P-12.9-research-path.md` for why a v1-shaped
  list survives even though the underlying computation (`OR`-group resolution, per-profile
  availability) does not.
- Wiki anchors derive from localised technology names and are occasionally wrong. CI MUST
  validate that each anchor resolves in the fetched page and fall back to a wiki search URL
  where it does not, so the field is never dead and never omitted.
- Description text, modifier lists and links are lazily fetched detail payloads (see
  `00-overview.md`), not part of the base dataset.
- **P-12.6 deliberately points at unexpanded source.** Where a technology's fields are partly
  contributed by an `inline_script` invocation, the link targets the technology's own file and
  line range as written — the `inline_script = { script = ... }` line itself, not the target
  script's file, and not a synthesised view of the post-expansion result. This is worth stating
  explicitly because a reader who knows the field came from an expanded script may reasonably
  wonder why the link doesn't point there: the field was already never showing a resolved
  `@variable` value either, for the same reason — the link is to the technology's declared
  source, not a flattened reconstruction of it. A curious reader can follow the `script = ...`
  path into the vendored repository themselves.
