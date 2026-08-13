# P-1 — Empire type support

**Requirement.** The tool MUST model empire type as a first-class dimension. For any selected
empire profile, the tool MUST compute and display technology availability, tech swaps and
research paths correct for that profile.

Empire type is modelled as **three independent axes composed at build time** (see D-6):

| Axis | Values |
| --- | --- |
| Gestalt/authority | regular, hive mind, machine intelligence |
| Shipset | mechanical, biological |
| Nomadic | yes, no |

Twelve profiles. The axes are genuinely independent: any authority type can be nomadic, and
nomadic empires use either shipset.

**Default profile.** On a first visit with no empire-profile URL parameter, the tool MUST render
immediately using **regular authority, mechanical shipset, non-nomadic** as the default profile.
The user is never forced to choose a profile before seeing the tree; the default is simply
whatever the URL encodes once they do.

## Acceptance criteria

- A visible, persistent empire selector is present in the primary UI, exposing the axes rather
  than a flat list of twelve names.
- Changing the selection updates which nodes are available, which are locked (P-13), all edges,
  and the research path field of the detail popup (P-12.9).
- Where a technology is swapped between empire types, the tool displays the technology
  appropriate to the selection and identifies its counterpart as a swap partner.
- The selection is encoded in the URL so a view can be shared or bookmarked.

## Implied technical decisions

- Profiles MUST be defined in a **declarative empire profile configuration** — a checked-in
  file — not hard-coded in application logic. Each profile enumerates the trigger facts
  asserted for that empire, such as `is_nomadic = yes`, `has_biological_ships = yes`,
  `is_machine_empire = no`, which the trigger evaluator consults.
- Adding an axis value or a new fact MUST require only a configuration entry, never a renderer
  change.
- Empire profile is a **build-time partition key**. Datasets are computed per profile, not
  derived in the browser.
- **Ascension perks MUST NOT be modelled as profile facts.** They are gates (P-3). A
  perk-gated technology always displays its gate regardless of profile, because the tree
  states what a player would need rather than assuming what they have.
- Origins are not an axis for v1. If extraction surfaces origin-gated technologies, they are
  added as facts in the registry — this MUST NOT require restructuring the axis model.
