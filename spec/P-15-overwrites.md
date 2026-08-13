# P-15 — Vanilla technology overwrite accounting

**Requirement.** Where Gigastructures overwrites or modifies vanilla Stellaris technologies, the
tool MUST reflect the modded values, not the base-game values.

## Acceptance criteria

- The build loads vanilla technology definitions and mod definitions, and applies the game's
  load-order override semantics: a technology key defined in the mod fully replaces the vanilla
  definition of that key.
- Every affected technology is labelled `Vanilla (modified by Gigastructural Engineering)` in the
  detail popup (P-12.5).
- The detail popup for a modified vanilla technology MUST make the modification inspectable — at
  minimum, listing which fields differ from vanilla (cost, tier, prerequisites, weight, category,
  flags).
- The build emits a machine-readable overwrite report listing every overridden vanilla technology
  and the fields changed. This report is surfaced in the `/?dev` build (S-2).
- If the mod adds prerequisites to a vanilla technology, the graph reflects the modded
  prerequisite set, and layout (P-2) is recomputed accordingly.

## Implied technical decisions

- The build MUST require a **local vanilla `common/technology` corpus** in addition to the mod
  source. Because base-game files are not redistributable, the pipeline MUST support supplying
  them via a path or secret-mounted archive in CI, and MUST fail with a clear message when they
  are absent rather than silently producing a mod-only graph. This is a deployment prerequisite,
  not an optional extra.
- Overwrite resolution is **whole-key replacement**, matching engine behaviour — not a
  field-level merge. Any deviation from this rule for presentation purposes (e.g. field-level
  diffing for the popup) MUST be computed as a comparison *after* resolution, never applied to
  the authoritative graph.
- The vanilla corpus version MUST be pinned and recorded alongside the mod version in the dataset
  metadata.
