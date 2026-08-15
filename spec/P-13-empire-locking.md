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

## Config-gated reason template (D-10's fourth AvailabilityState)

A technology can be unavailable because a *mod-configuration option* is off, not because of
anything about the empire — see `CONFIG_GATED` in `spec/decisions.md`'s D-10. The real corpus's
first (and, so far, only) instance is the 50-member `giga_tech_repeatable_*_cap` family, gated on
`has_global_flag = <name>_capped_r`.

**Display wording is user-supplied, matching the mod's own in-game option label — do not
"improve" it into something a player won't recognize:**

    Requires <Megastructure Name> cap: 1 + Repeatables

e.g. "Requires Alderson Disk cap: 1 + Repeatables". This deliberately echoes Gigastructures'
own `giga_menu_r` loc entry ("Megastructure Capacity: §S1§! + §BRepeatables§!"), the actual
option-value label players see for this exact setting.

**Stage 2 emits the semantic subject only, never the composed sentence** — the empire-overlay
schema's `availability[key].configGatedSubject` field (`schema/empire-overlay.schema.json`)
carries just the megastructure name (e.g. `"Alderson Disk"`), nullable. **Stage 3 composes the
final text** by substituting that subject into the fixed template above — the template string
itself lives in this spec (and in Stage 3's own code once built), not in the emitted data.

The subject is sourced from the technology's own already-resolved localised name
(`<Name> Management Protocols`, suffix stripped). That suffix-stripped name is frequently itself a
`$token$` (e.g. `giga_tech_repeatable_alderson_cap` -> `$name_alderson$`) rather than a literal
string — **corrected finding, superseding an earlier, uncorrected reading of this same data**: a
prior pass assumed such a token was an unresolvable Stellaris runtime name-pool reference (the
mechanism that assigns a random name to certain procedurally-varied content) and returned
`configGatedSubject: null` for all 8 real occurrences. Raw-source re-inspection
(vendor/*/localisation, per CLAUDE.md's "inspect raw bytes, never conclude from a formatted read"
rule) found this was wrong: every one of these tokens is ordinary Stellaris localisation `$key$`
variable substitution — `token` is itself a plain, statically-resolvable loc key one hop away
(`name_alderson: "Alderson Disk"`). Two of the 8 (`dyson_swarm_3`, `orbital_arc_furnace_4`) are
**vanilla** megastructures that Gigastructures extends with a repeatable cap, and their name is
defined in vanilla's own localisation, not Gigastructures' — the lookup (`_resolve_loc_tokens`)
therefore searches the full cross-source `ctx.loc_table` (vanilla, Gigastructures, ACOT, AoT, in
load order), never one source in isolation, and is bounded to a small hop limit (some tokens chain
through a second token, e.g. vanilla's `dyson_swarm_1: "$dyson_swarm_3$: Array"`) so a cyclic or
unexpectedly deep reference can't loop forever rather than failing cleanly to `null`.

**Real corpus, corrected: 50/50 resolve to a literal megastructure name** — every one of the
previously-failing 8 now does too: `giga_tech_repeatable_alderson_cap` -> "Alderson Disk" (the
user's own flagship example), `_asteroid_manufactory_cap` -> "Asteroid Industrial Site",
`_dyson_swarm_cap` -> "Dyson Swarm", `_furnace_cap` -> "Arc Furnace", `_observatory_cap` ->
"Atmospheric Storm Observatory", `_orbital_naval_logistics_cap` -> "Orbital Naval Logistics
Office", `_warmoon_cap` -> "Attack Moon", `_warplanet_cap` -> "Behemoth Planetcraft".
`configGatedSubject` remains nullable in the schema and the resolver still returns `None` rather
than guessing whenever a technology's own name has no loc entry, or a token can't be resolved
within the hop limit — no case in the current corpus hits either path, but the honest-null
contract stays in place for a future corpus that might.

See `pipeline/dataset_emit.py`'s `_config_gated_subject`/`_resolve_loc_tokens` for the
implementation and
`tests/test_dataset_emit.py::test_config_gated_subject_resolves_all_50_megastructure_names`
for the corpus assertion, including the exact resolved name for each of the 8 previously-null
cases.
