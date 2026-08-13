# P-7 — Middle-click isolation

**Requirement.** Middle-clicking a technology node MUST isolate that node together with all
directly related nodes — its prerequisites and the technologies it unlocks — dimming or hiding
all unrelated nodes.

## Acceptance criteria

- Middle-click (pointer button 1) on a node enters isolation mode centred on that node.
- The isolated set includes the target node, its direct prerequisites, and its direct unlocks. A
  user-adjustable traversal depth (default: 1 hop in each direction; options for full
  ancestor/descendant closure) MUST be provided.
- Traversal follows **all three edge kinds** (P-14): `prerequisite`, `potential-gate` and
  `alternative`. Each renders in its distinct connector style per P-8 (solid / dashed / dotted)
  within the isolated set, so a potential-gate or alternative relationship pulled in by isolation
  is never mistaken for a formal prerequisite. This deliberately differs from the research path
  (P-12.9), which is prerequisite-edges-only — isolation is a "show me everything related" view,
  the research path is specifically "how do I get here."
- Unrelated nodes are dimmed or hidden per a user-visible setting; edges between unrelated nodes
  follow the same treatment.
- Isolation is exitable via a clearly labelled control and via the `Escape` key.
- Isolation mode is indicated by persistent on-screen state (e.g. a chip naming the isolated
  technology).
- Default browser middle-click behaviour (autoscroll, open-in-new-tab) MUST be suppressed on node
  targets.

## Implied technical decisions

- **Middle-click does not exist on touch devices.** P-9 therefore requires an equivalent touch
  affordance. The specified equivalent is a **long-press** on a node (≥400 ms, movement tolerance
  ≤10 px), plus an explicit "Isolate" action in the detail popup so the feature is discoverable
  without gesture knowledge. Both paths MUST produce identical state.
- Isolation MUST be implemented as a visibility/emphasis mask over the static layout — not a
  re-layout — for the same reason as P-4.
- Adjacency lists (forward and reverse, per edge kind) MUST be precomputed in the dataset.
  Traversing them at interaction time — walking node-to-node via precomputed adjacency, to
  whatever depth the user selected — is permitted and expected; that is how the depth control and
  full-closure option are served. What's forbidden is scanning the **full edge record set**
  (e.g. iterating every edge in the dataset looking for matches) at interaction time — adjacency
  lookups must be O(1) per node, not O(edges). A full ancestor/descendant closure MUST complete
  within the P-10 interaction budget (100 ms) regardless of graph size.
