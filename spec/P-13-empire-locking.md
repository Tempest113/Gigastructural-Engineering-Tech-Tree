# P-13 — Empire-profile tech locking

**Requirement.** Technologies that are unavailable to specific empire profiles (e.g. nomadic
empires) MUST be clearly labelled as locked, with the specific restriction displayed. Where
availability cannot be determined at all, the technology MUST be labelled uncertain, not locked
and not available.

## Acceptance criteria

- When an empire profile is selected, technologies unavailable to it are rendered in a distinct
  **locked** state (e.g. desaturated with a lock badge), distinguishable from the dimming used by
  filtering (P-4), search (P-6) and isolation (P-7).
- Technologies whose trigger resolution is `unknown` for the selected profile (see
  `implementation-notes.md`, Trigger evaluation) are rendered in a third, distinct **uncertain**
  state — visually separate from both available and locked, e.g. a hatched or question-marked
  badge rather than the lock icon, and equally distinguishable from the dimming used by filtering
  (P-4), search (P-6) and isolation (P-7). Uncertain is not a variant of locked: the tree does not
  know whether the technology is available, and must not imply either answer.
- The lock badge names the restriction as the minimal set of violated axis constraints, e.g.
  "Unavailable: nomadic empires" — not a dump of all twelve profiles. The detail popup's primary
  display mirrors this minimal statement, with the full twelve-profile availability matrix
  available behind an expand control for users who want the complete picture.
- The uncertain badge names the specific condition that could not be evaluated (e.g. "Unresolved
  trigger: `has_communications`"), even though its result is unknown — the trigger *text* is
  always known, only its truth value isn't.
- The user can choose whether locked or uncertain technologies are hidden entirely or shown in
  their respective state; the default is shown, so that the restriction is discoverable.
- A locked or uncertain technology's edges are rendered in the matching state as well, so that a
  broken or uncertain path is legible as such.

## Implied technical decisions

- Availability MUST be stored per `(technology, empire profile)` pair as a **three-valued state**
  — available, locked, or uncertain — never a boolean. A bare boolean cannot represent uncertain
  at all, let alone label it.
- **A locked state's reason string has two valid origins, and both MUST be supported:**
  - **Trigger-derived** — the ordinary case. The reason comes from the specific trigger condition
    that failed evaluation for this profile (e.g. "Unavailable: requires Nomadic empires" from a
    failed `is_nomadic = yes` check). This is what P-13 originally specified.
  - **Structure-derived** — used by P-16's per-profile structural-reachability check. The reason
    comes not from a failed trigger but from graph reachability: no edge of any kind (P-14)
    connects anything this profile's active edge set uses to this technology. There is no trigger
    that "failed" — the technology's own conditions may all evaluate `true`; it's simply not
    reachable from anything this profile can get to.

  Both are ordinary human-readable strings in the same field; the UI does not need to know which
  produced a given lock. But **a structure-derived reason MUST NOT be phrased as though a trigger
  failed** (e.g. never "requires X = yes" for a structure-derived lock, since no such condition
  was evaluated) — phrase it in terms of reachability instead (e.g. "Unavailable: not part of
  this profile's research path", P-16's example). Misphrasing a structure-derived reason as a
  trigger failure would describe a condition that was never actually checked.
- An uncertain state carries the unresolved trigger's source text — always trigger-derived, since
  "uncertain" only exists because a specific trigger's evaluation stalled.
- Where the lock reason cannot be derived automatically from the trigger, the build MUST fall
  back to a checked-in reason override table and MUST warn when an override is missing (surfaced
  via S-2).
- The minimal violated-constraint summary (e.g. "nomadic empires") is derived from which axis
  values the trigger evaluator's known facts ruled out, not from re-deriving English from the raw
  trigger — see P-1's axis model.
