# P-15 — Technology overwrite accounting

**Requirement.** Where a later-loaded source (Gigastructures, ACOT, or AoT) overwrites or
modifies a technology defined by an earlier one, the tool MUST reflect the winning values, not
the values of whatever it replaced.

**Overwriting is not a vanilla-only phenomenon, and a vanilla baseline does not exist for most
overwrites in the corpus.** Surveyed against the vendored corpus (see CLAUDE.md's "Source data"
section for the corrected counts and provenance): Gigastructures redefines exactly two vanilla
technologies; ACOT redefines four vanilla technologies directly (independent of Gigastructures);
and AoT redefines nineteen ACOT technologies — the largest single overwrite relationship in the
corpus, with no vanilla original anywhere in that chain. "Diff against vanilla" has no baseline
for those nineteen cases. No 3-or-deeper overwrite chain exists anywhere in the corpus — every
overwritten key is touched by exactly one other source.

## Acceptance criteria

- The build loads vanilla, Gigastructures, ACOT, and AoT technology definitions and applies the
  game's load-order override semantics: a technology key defined in a later-loaded source fully
  replaces an earlier source's definition of that key.
- Every redefined technology's detail popup (P-12.5) carries a precomputed label identifying who
  defined the winning block and, if it replaced something, whose definition that was — e.g.
  `Vanilla`, `ACOT`, `Vanilla (modified by ACOT)`, `ACOT (modified by AoT)`. This generalises the
  original single-case wording (`Vanilla (modified by Gigastructural Engineering)`), which
  remains one instance of the pattern, not the only one.
- The detail popup for a redefined technology MUST make the modification inspectable — at
  minimum, listing which fields differ from the source it replaced (cost, tier, prerequisites,
  weight, category, flags). **The diff baseline is the immediately-preceding definition in load
  order, whatever its source — never hardcoded to vanilla.**
- The build emits a machine-readable overwrite report listing every overridden technology, its
  winning and replaced source, and the fields changed. This report is surfaced in the `/?dev`
  build (S-2). It carries two distinct sections: technology-block overwrites (a key redefined
  outright) and scripted-variable overwrites (a `@name` redefined, changing the effective
  cost/weight of every technology that references it without touching those technologies' own
  blocks — see "Scripted-variable overwrites" below). These have different causes and must not be
  collapsed into one list.
- If a later source adds prerequisites to a technology it redefines, the graph reflects the
  redefined prerequisite set, and layout (P-2) is recomputed accordingly.

## Scripted-variable overwrites

A technology's `cost`/`weight` field is frequently a `@variable` reference rather than a literal
(e.g. `cost = @tier5cost3`). A later source can redefine that variable without touching the
technology's own block at all — the technology's effective cost/weight still changes, but no
technology-block overwrite is recorded for it. This is a real, confirmed mechanism in the corpus
(ACOT and AoT redefine 14 shared scripted-variable names between them, mostly component-cost
variables), and diffing must not miss it:

- `cost`/`weight` comparison MUST resolve `@variable` references (via `pipeline.variables`)
  against the final, fully-overwrite-resolved variable table *before* comparing values, so an
  indirect overwrite through a redefined variable is visible as a real change.
- The raw, pre-resolution form (literal vs. `@name` reference) MUST be retained alongside the
  resolved value. A technology whose `weight` changes from a `NumberLiteral` to a
  `VariableReference` (or vice versa) between two definitions is a mechanism change, not just a
  value change, and collapsing the two into a single resolved-value comparison would silently
  flatten that distinction away.

## Prerequisite diffing and display ordering

- Prerequisite lists are diffed as **sets**, not ordered lists — reordering alone is not a
  change. Confirmed against the corpus: no case was found where a redefinition reordered a
  carried-over prerequisite (every multi-prerequisite pair checked preserved order exactly), so
  this is a safe default with no observed counter-example, not a proven invariant — treat it as
  an inference, not a documented fact, if the corpus later contradicts it.
- Independently of diffing, the **displayed** prerequisite list (P-12.4, flat and ordered) MUST
  have a build-deterministic order: declaration order from the winning definition's own
  `prerequisites` block (depth-first, as encountered in source order). Two builds over the same
  corpus MUST produce identical ordering.

## Implied technical decisions

- The build MUST require a **local vanilla `common/technology` corpus** in addition to the mod
  sources. Because base-game files are not redistributable, the pipeline MUST support supplying
  them via a path or secret-mounted archive in CI, and MUST fail with a clear message when they
  are absent rather than silently producing a mod-only graph. This is a deployment prerequisite,
  not an optional extra.
- Overwrite resolution is **whole-key replacement**, matching engine behaviour — not a
  field-level merge. Any deviation from this rule for presentation purposes (e.g. field-level
  diffing for the popup) MUST be computed as a comparison *after* resolution, never applied to
  the authoritative graph.
- Every vendored source's version MUST be pinned and recorded alongside the others in the dataset
  metadata — not vanilla alone. See CLAUDE.md's "Source data" section for the current mechanism
  per source (vanilla: manual; Gigastructures: pinned GitHub commit; ACOT/AoT: manual Steam
  Workshop, no pinning mechanism available).
- An overwrite the resolver cannot explain automatically (a near-miss key, an ambiguous chain)
  MUST be resolvable via the hand-maintained overwrite override table (CLAUDE.md's Rules
  section), and the build MUST warn when a case needs an override entry that isn't present. As of
  the corpus survey behind this revision, no case has actually required one — every overwrite
  found fits the plain last-source-wins, whole-key-replacement rule with no ambiguity — so the
  table is seeded empty, not with speculative entries.
