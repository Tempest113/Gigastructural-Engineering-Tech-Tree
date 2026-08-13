# P-5 — Crisis technology separation and filtering

**Requirement.** Technologies unlocked by Gigastructures crises MUST be visually separated from
standard technologies and MUST be independently filterable by crisis faction.

Five factions are supported: **Aeternum, Blokkats, Compound, Sirenalia, Katzenartig Imperium**.

Crisis lanes and tier columns are **orthogonal**: lanes run horizontally, tier columns run
vertically, and every technology has both a lane and a column. The standard-progression
technologies occupy an implicit lane; each crisis faction gets one more. A lane is not a
disconnected panel — it is tier-axis-aligned, so `column(B) > column(A)` (P-2) holds for
cross-lane prerequisite edges exactly as it does within a lane. A crisis-faction technology that
is also repeatable sits in the Repeatables column (P-2) within its own faction's lane, not in a
separate repeatables region — the two axes compose rather than compete.

**Every lane spans the same single, global column grid** (P-2) — a faction whose technologies
stop at T5 still has empty T6-through-Repeatables columns, rather than a compressed lane with
its own numbering. Lanes are fitted vertically to their own content; never horizontally. This
keeps a column index meaning the same tier in every lane, which the shared coordinate space
requires. Cross-lane edges route through dedicated inter-lane gutters owned by P-8.

## Acceptance criteria

- Crisis technologies render in a distinct, tier-axis-aligned lane — a horizontal band running
  the full width of the tier columns — rather than interleaved with the standard progression's
  lane. A disconnected panel is not an acceptable treatment: it cannot satisfy P-2's column
  ordering for cross-lane prerequisite edges.
- The lane is labelled with the faction name and its technology count.
- Each faction is an independently toggleable filter. Toggling one does not affect another.
- Crisis technologies carry the colour and background treatments defined in S-1.
- A crisis technology's prerequisite relationships to standard technologies, in either
  direction, remain visible when both are shown.

## Implied technical decisions

- The model MUST carry a nullable `crisisFaction` field. Membership is derived in this order:
  technology ID, then `potential` and prerequisite inspection, then a checked-in manual override
  file for the remainder. The derivation method MUST be documented in the pipeline README.
- The override file is permitted hand-maintained configuration under P-10, which forbids
  hand-authored technology *data* but allows hand-maintained *classification rules*.
- Because crisis techs occupy separate lanes that share the tier-column axis (see P-2), the
  layout engine MUST support multiple horizontal lanes over one shared coordinate space. A lane
  is a row range, not an independent sub-layout: column assignment is computed identically
  regardless of lane. Cross-lane routing mechanics (gutters, channel priority) are owned by P-8,
  not this file.
- A technology that is both crisis-sourced and normally researchable MUST be represented **once**
  with both classifications recorded. It MUST NOT be duplicated as two nodes.
- Adding a sixth faction MUST require only a colour and pattern token pair plus a classification
  rule — never a renderer change.
