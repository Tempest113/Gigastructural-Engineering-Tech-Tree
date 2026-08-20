# P-16 — External mod requirements

*New in specification 2.0.*

**Requirement.** Technologies whose availability depends on a mod other than Gigastructures MUST
be identified as such, and MUST display the dependency on the node card and in the detail popup.

A mod requirement states which mods must be installed **for the technology to exist in-game at
all**. It is purely informational: this is a static site with no session state, so nothing in the
system ever knows what mods the viewing player actually has, and the requirement is never
compared against a viewer's installation. It is neither a gate (a condition on empire state, P-3)
nor a prerequisite (a position in the research graph, P-14). It is a third, orthogonal dimension.

## Background

Gigastructures defines placeholder technologies for content that only fully exists when another
mod is present. The known case is the ACOT-tier supertensile materials, which reference scripted
variables, localisation strings and icons not present in base Gigastructures.

## Resolved — scope of ACOT and AoT

**D-18 (`spec/decisions.md`) corrects this section: the rendering-scope closure is DEPTH-1, not a
full transitive closure.** The tree renders vanilla and Gigastructural Engineering technologies
unconditionally. An ACOT or AoT technology is rendered **only when a rendered technology names it
directly in its own `prerequisites` block** — no recursion. An ACOT/AoT technology reachable only
through another ACOT/AoT technology's own prerequisite chain is not emitted as a node, even if
that intermediate technology is itself rendered. This corrects the ORIGINAL design (kept below,
struck through in spirit, not in text, for history): "only where they fall in the rendering-scope
closure of a rendered technology... directly or transitively... so that a rendered technology's
prerequisite chain is never broken by an invisible gap" — the user reported this over-included a
concrete case (an ACOT technology two hops removed from anything rendered), and D-18 records the
full reasoning, the rejected alternatives (keeping the full closure; a stub/ghost node for an
off-tree prerequisite), and the exact 3-link accepted cost. See D-18 for the real numbers; this
document states the rule only.

**This requirement involves two separate computations. Keeping them separate matters — conflating
them previously produced a correctness bug (a node could be wrongly locked as unreachable when a
non-`prerequisite` edge actually reached it for that profile). They are named distinctly below
and MUST NOT be merged back into one.**

**The rendering-scope closure** decides which ACOT/AoT nodes exist on the canvas at all. It is
computed over **formal `prerequisite` edges only** (not `potential-gate` or `alternative` edges,
P-14) — the same edge kind P-12.9's research path uses, and for the same reason: this is about
keeping a research *chain* unbroken, not about availability gating. It is computed **once, as a
union across all twelve empire profiles**, not per profile. The rendered node set is therefore
profile-invariant: selecting a different empire profile changes lock state (P-13) and which edges
are active, never which nodes exist on the canvas. This follows from `00-overview.md`'s dataset
structure, where the base dataset — including the node set and layout — is shared across empire
profiles and only the per-profile overlay varies.

This is a build-time computation over the resolved graph, not a user-facing filter. There is no
control that changes which mod technologies are rendered; the ACOT/AoT card badge communicates
the requirement, it does not toggle visibility.

**The per-profile structural-reachability check** decides, for each profile, whether a node that
the rendering-scope closure chose to render is actually reachable *for that profile*. Because the
rendering-scope closure is a profile-invariant union, a node reachable through only one profile's
tech-swap chain still renders for all twelve — so for the other eleven, something must decide
whether the node is available. That something is this check, and — unlike the rendering-scope
closure — it MUST consider **all three edge kinds**: `prerequisite`, `potential-gate` and
`alternative`. A `potential-gate` or `alternative` edge grants real in-game access; a node is
reachable for a profile if *any* edge kind provides a path under that profile's active edge set.
**A node MUST NOT be locked as unreachable when a `potential-gate` or `alternative` edge, even
though it doesn't count toward rendering scope, provides a path for that profile.** Where no edge
of any kind reaches the node for that profile, it renders **locked**, using P-13's existing
availability model (see P-13 for the distinction between trigger-derived and structure-derived
lock reasons), with a reason naming that it is not reachable for that profile (e.g. "Unavailable:
not part of this profile's research path"). A player on that profile sees the node, sees it
locked, and sees why — the same treatment any other profile-gated technology gets.

## Acceptance criteria

- The model carries `requiresMods: string[]`, empty for the overwhelming majority of
  technologies.
- Affected node cards render a compact badge naming the mod, for example `ACOT`, visually
  distinct from gate indicators and from the tier badge.
- The detail popup renders the requirement as field P-12.10, with an explicit "none" state
  where there is no dependency.
- ACOT and AoT technologies are emitted as nodes if and only if they are in the rendering-scope
  closure of a rendered vanilla or Gigastructures technology.
- Where a rendered technology's mod dependency cannot be resolved — it needs ACOT or AoT content
  that is not itself in the rendering-scope closure of anything rendered — the build MUST warn and
  the technology MUST render with an explicit unresolved state, never silently dropped and never
  silently rendered as if complete. **Closed (reconciliation session 3), after being flagged as a
  gap when D-18 first shipped.** `pipeline.rendering_scope.compute_off_tree_prerequisites`'s exact
  3-link accepted set (D-18) now resolves into each affected technology's own detail payload
  (`offTreePrerequisiteNames`, by localised name) and renders in the popup under "Also requires,"
  with a fixed client-side note that the name is outside the rendered scope
  (`client/src/main.ts`'s `openPopup`). Deliberately NOT a card badge — three affected nodes
  doesn't justify a new S-3 indicator; popup-only, same precedent as ascension-perk gates and D-14
  swap variants. The technology's own EDGE list is still correctly filtered to rendered
  technologies only (`pipeline/layout.py`'s `prereqs_of`), so no dangling reference exists in the
  emitted edge data either way — this note is purely additive information, not a data-integrity
  fix.

## Implied technical decisions

- The field is a list, not a boolean, so a second dependency costs no schema change.
- The rendering-scope closure runs once, at build time, over the fully resolved graph's
  `prerequisite` edges (vanilla, Gigastructures, ACOT and AoT together), before layout. It
  determines the final rendered node set; nothing about it happens at runtime, and it does not
  re-run per profile. **D-18: depth-1, a single pass** — every unconditionally-rendered
  technology's own `prerequisites` block is checked once for an ACOT/AoT reference; the
  technologies that pass reaches are NOT themselves expanded further. Real corpus: 4-technology
  closure, 977 rendered nodes (down from the pre-D-18 7-technology/980-node figures). **This
  diagnostic is rescoped to match, not left checking a stale rule**:
  `pipeline.rendering_scope.compute_alternative_only_gaps` now checks the SAME depth-1 pass with
  `alternative`-group members also treated as traversable, rather than a multi-hop recursive
  closure — empty on the real corpus today, never a build failure. The forward-looking risk it
  guards against is unchanged: a future re-vendor adding an ACOT/AoT technology a rendered
  technology reaches ONLY via an `alternative` branch, which depth-1's prerequisite-only rule
  would otherwise silently exclude.
- The per-profile structural-reachability check runs once per `(ACOT/AoT node, empire profile)`
  pair, over that profile's active edge set across all three edge kinds. It feeds P-13's
  availability state (locked, with a structure-derived reason, when no edge kind reaches the
  node) and never affects the rendered node set — that's the rendering-scope closure's job alone.
  Implementations MUST NOT share a single graph traversal between the two: the edge-kind filter
  differs, and collapsing them back into one pass is exactly how the two got conflated before.
- Where mods have dependencies among themselves — AoT requires ACOT — resolving an AoT ancestor
  requires ACOT to be vendored too. The build MUST fail clearly if AoT is vendored without ACOT,
  rather than silently emitting a partially resolved chain.
- The badge names the *requirement* (`ACOT`, `AoT`), not the content it unlocks, so it stays
  correct as Gigastructures adds further mod-dependent technologies; a content-descriptive label
  would not.
- ACOT and AoT are Steam Workshop only. They cannot be pinned to a commit, so the scheduled
  upstream sync (P-10) does not cover them, their versions are recorded by hand in dataset
  metadata, and the collector hashes each vendored tree so CI can at least detect local change.
