# P-16 — External mod requirements

*New in specification 2.0.*

**Requirement.** Technologies whose availability depends on a mod other than Gigastructures MUST
be identified as such, MUST display the dependency on the node card and in the detail popup, and
MUST be filterable independently of every other dimension.

A mod requirement is a statement about the **player's installed mods**. It is neither a gate
(a condition on empire state, P-3) nor a prerequisite (a position in the research graph, P-14).
It is a third, orthogonal dimension.

## Background

Gigastructures defines placeholder technologies for content that only fully exists when another
mod is present. The known case is the ACOT-tier supertensile materials, which reference scripted
variables, localisation strings and icons not present in base Gigastructures.

## Acceptance criteria

- The model carries `requiresMods: string[]`, empty for the overwhelming majority of
  technologies.
- Affected node cards render a compact badge naming the mod, for example `ACOT`, visually
  distinct from gate indicators and from the tier badge.
- The detail popup renders the requirement as field P-12.10, with an explicit "none" state
  where there is no dependency.
- A checkbox labelled **"Requires ACOT"**, default on, hides affected technologies when
  unticked. Its state is encoded in the URL.
- Hiding is a visibility mask over static layout, per P-4. It MUST NOT reflow the graph.
- Edges to and from a hidden technology follow the same treatment as their endpoints.
- Where a dependency is unsatisfiable because the mod is not vendored, the build MUST warn and
  the technology MUST render with an explicit unresolved state — never silently dropped and
  never silently rendered as if complete.

## Implied technical decisions

- The field is a list, not a boolean, so a second dependency costs no schema change. The UI
  exposes one checkbox because there is currently one dependency; the control is generated from
  the distinct values present in the dataset, not hard-coded.
- Where mods have dependencies among themselves — AoT requires ACOT — unticking a prerequisite
  mod MUST force-untick and disable its dependents.
- The label names the *requirement*, not the content it unlocks. "Requires ACOT" stays correct
  if Gigastructures adds further ACOT-dependent technologies; a content-descriptive label would
  not.
- ACOT and AoT are Steam Workshop only. They cannot be pinned to a commit, so the scheduled
  upstream sync (P-10) does not cover them, their versions are recorded by hand in dataset
  metadata, and the collector hashes each vendored tree so CI can at least detect local change.

## UNRESOLVED — scope of ACOT and AoT

This requirement is written for the **narrow reading**: ACOT and AoT are vendored solely as
resolution sources for Gigastructures placeholder technologies, and their own technologies are
not emitted as nodes.

The v1 implementation appears to have rendered ACOT and AoT technologies as first-class nodes,
badged `ACOT` and `AoT`. If that behaviour is intended for v2, this requirement widens
substantially: those mods become rendered sources needing their own crisis classification, gate
patterns, icon extraction, tier assignment and localisation coverage, and the "out of scope"
statement in `00-overview.md` needs revising.

**This decision must be recorded before Stage 2 is built.** It changes the size of the graph,
the dataset budget under P-10, and the meaning of the mod-set control described above.
