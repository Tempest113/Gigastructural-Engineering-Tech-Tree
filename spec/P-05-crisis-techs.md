# P-5 — Crisis technology separation and filtering

**Requirement.** Technologies unlocked by Gigastructures crises MUST be visually separated from
standard technologies and MUST be independently filterable by crisis faction.

Five factions are supported: **Aeternum, Blokkats, Compound, Sirenalia, Katzenartig Imperium**.

## Acceptance criteria

- Crisis technologies render in a distinct region of the layout — a dedicated band, lane or
  panel — rather than interleaved with the standard progression columns.
- The region is labelled with the faction name and its technology count.
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
- Because crisis techs occupy separate regions, the layout engine MUST support multiple layout
  zones with a shared coordinate space (see P-2), so cross-zone edges route without overlapping
  node cards.
- A technology that is both crisis-sourced and normally researchable MUST be represented **once**
  with both classifications recorded. It MUST NOT be duplicated as two nodes.
- Adding a sixth faction MUST require only a colour and pattern token pair plus a classification
  rule — never a renderer change.
