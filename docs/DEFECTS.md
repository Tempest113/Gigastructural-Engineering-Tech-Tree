# Defect classes

Recurring bug *shapes* this project has hit more than once, each independently discovered, each
worth recognising on sight rather than re-diagnosing from scratch. `CLAUDE.md`'s "Rules" section
keeps a one-line pointer to each; this file has the full account — what the class is, every real
instance found so far, and what generalises. `docs/BUILD-LOG.md` has the chronological session
record; this file is organised by class instead, since that's the useful axis when you're trying
to recognise "have I seen this shape before."

## Raw-vs-expanded: reading technology data by a route that skips `inline_script`/`@variable` expansion

Three independently-discovered bugs share one mechanism: a component acquiring technology data by
a route other than the full expanded canonical record silently gets a plausible-but-wrong answer,
with no error raised, because some fields on `giga_tech_repeatable_*`-family technologies exist
*only* after `inline_script` expansion.

1. **Tier resolution** (P-2's tier-source audit) — 50 `giga_tech_repeatable_*_cap` nodes have no
   `tier` field on the raw, unexpanded block at all; it only exists via `giga_mega_repeatable.txt`'s
   shared template. A raw-block reader places these nodes with no tier, or silently defaults one.
2. **`pipeline.layout.is_repeatable`** — a related but mechanistically distinct bug in the SAME
   family: a sign-only `levels < 0` predicate missed 12 finite-level repeatables (not itself a
   raw-vs-expanded input problem, since layout's real-corpus path was already expansion-fed — see
   `CLAUDE.md`'s "Repeatables" section) — found from a user's v1 screenshot (a card badged "T5 x5",
   which cannot exist under `levels = -1`), not by any test.
3. **`unconditionalUncertainty`** (Stage 2 cleanup session) — the same 50 `_cap` nodes have no
   `potential` field pre-expansion, so a raw-block availability survey silently reported them
   `AVAILABLE` instead of evaluating their real, expansion-only gating condition.

(1) and (3) share the exact mechanism (an expansion-only field) applied to two different fields;
(2) shares the same family and the same symptom (a plausible wrong answer, zero errors, found only
by independently checking against real evidence) without sharing the exact cause.

**The actionable generalisation**: any component that acquires technology data by a route other
than the full expanded canonical record is at risk of this failure mode, and the
`giga_tech_repeatable_*` family is the reliable canary for it — enough of that family's own data
(tier, potential, and probably other fields via the shared template) exists only post-expansion
that a raw-block consumer fails silently rather than loudly. When surveying corpus content for
this project, always confirm you're reading from the expanded canonical record before trusting a
"zero occurrences" or "N technologies affected" finding — see `docs/BUILD-LOG.md`'s availability
sections for the full audit of which pipeline components were checked against this and cleared.

## Parallel geometry: the renderer recomputing layout from its own copy of the formula

`client/src/main.ts` once re-derived row/band geometry (panel/tint/header positions) via its own
copy of `pipeline/layout.py`'s formulas, rather than deriving it from the emitted `nodePositions`.
D-17's same-band depth-slot fix changed those formulas server-side and silently desynced the
client's copy — row panels, tier tints and cell labels drew nowhere near their actual cards, with
no error, no failing test, caught only by a headless screenshot. Two independent implementations
of the same geometry will drift the moment either one changes, and nothing forces them to change
together.

**Fixed permanently, not re-synced**: client-side row/band geometry is now derived from the real
emitted positions (min/max over `nodePositions`, grouped by row/band), so client and server
geometry cannot drift apart again regardless of future formula changes. A milder residual form of
the same risk remains: mirrored SCALAR constants (`CARD_WIDTH`/`CARD_HEIGHT`, gutter constants,
`SUBGRID_WIDTH`, `AREA_ORDER`, `FLOATS_PER_EDGE_POLYLINE`, `MIN_STUB`) are still kept in sync by
hand since the dataset schema doesn't carry them as data — `CARD_WIDTH`/`CARD_HEIGHT` are the one
genuinely load-bearing pair (they size the actual card draw call); flagged as a scoped follow-up,
not fixed.

**The rule this produced** (`CLAUDE.md`'s Rules section): the pipeline owns all geometry; the
renderer consumes emitted positions and never recomputes them from a parallel formula. Any
renderer-side value derivable from emitted geometry MUST be derived from the real emitted
positions, never reimplemented client-side from the same inputs the pipeline consumes.

## Dict-keying: a missing discriminator field silently summing unrelated data

A *different* defect class produced the same visible symptom (rows overlapping) as the parallel-
geometry bug above, in a later session — worth keeping separate precisely because it looks like a
repeat of that bug at a glance and isn't. A sub-grid centring fix in `pipeline/layout.py` keyed
`column_member_count` by `(row_id, col)` alone, but `col` is BAND-RELATIVE — its cursor resets
every band — so two physically different columns in different bands of the same row shared a dict
key, silently SUMMING their member counts into one entry. That corrupted count could exceed the
row's real max and drive the centring offset negative, shifting a column's cards upward past row
0 into the row above (real corpus example: one node placed at row −16).

**This is a plain dict-keying bug (a missing discriminator field), not a parallel-geometry
violation** — nothing client-side re-derived anything; the client correctly derived row panels
from the (corrupted) emitted node positions exactly as the rule above requires, and faithfully
reproduced the bug rather than masking or independently causing it. Fixed by keying on the full
`(row_id, band_index, col)` triple, which is unique by construction, plus a same-turn
`assert centre_offset >= 0` in `pipeline/layout.py` itself as a second line of defence.

## The green-suite lesson: a passing test suite proves self-consistency, not correctness

Recorded once as its own lesson because it's now been the *actual* root cause, independently, at
least three times:

- `pipeline.layout.is_repeatable`'s `levels < 0` predicate shipped with every test for it passing,
  because no test encoded "the real corpus's repeatable population is 88, not 76" as an
  expectation — that number wasn't known to be wrong yet. Found from a screenshot, not a test.
- D-17's original sub-column assignment stacked every member sharing a depth in ONE column, with a
  test that asserted this AS intended behaviour (a real corpus case stacked 37 unrelated
  technologies 37 rows tall) — the suite didn't just fail to catch the bug, it actively enshrined
  it as spec.
- The dict-keying bug above: the existing test suite stayed fully green through the regression
  because nothing asserted the actual invariant (no two rows' card extents may intersect, no row
  index is ever negative) — canvas dimensions were genuinely unaffected, so nothing in the suite's
  existing coverage had a reason to move.

**The generalisation**: a green suite means the code is self-consistent with what the tests
encode, not that what the tests encode is correct. When a real-corpus figure is trusted across
sessions (a count, a membership rule, an invariant), periodically re-derive it from raw evidence
rather than assuming a passing suite is confirming it — the same discipline `CLAUDE.md`'s Rules
section states for `repr()`/raw-inspection, applied to test coverage instead of source syntax.

## EXCLUDED-as-vacuously-satisfied: an identity-element leaf standing alone resolves to a false-definite result

**Fixed (a later session, alongside the `weight-gated` AvailabilityState).** `pipeline.availability.
EXCLUDED_KEYS` (`has_technology`, `has_valid_civic`, `has_origin`, `has_ethic`, and others) is
correctly an identity element for `potential`-block evaluation — it means "not this evaluator's
job, defer to P-14/gates," and `_combine_and`/`_combine_or` treat an EXCLUDED-only child as
vacuously satisfied so the surrounding AND/OR can still resolve. That's correct for `potential`.
It was NOT correct when the same leaf stood alone as a `weight_modifier` zero-factor condition
(Item 2b) — the OLD `_apply_weight_gate` read `evaluate_trigger_block`'s PUBLIC result, which maps
both internal `TRUE` and internal `EXCLUDED` to `AVAILABLE` (correct for `potential`'s "presume
open," meaningless for "is the zero-weight condition currently met"). That silently laundered an
unresolvable condition into a definite LOCKED for every one of the 12 profiles — confirmed
empirically against the real corpus, 12 zero-factor `weight_modifier` entries (11 technologies)
were affected before the fix.

**The general lesson, generalised beyond this one call site**: EXCLUDED's soundness in `potential`
evaluation comes from two *specific, checkable* facts, never from any general property of the
identity element that automatically transfers to a new caller asking a different question of the
same evaluator:

- For `has_technology`, P-14 extracts every such leaf as a real `potential-gate` EDGE, so the
  deferral is caught downstream by the edge system — the fact is already conveyed visually,
  EXCLUDED here just avoids double-counting it as a trigger truth value too.
- For the origin/ethic/civic/perk keys, these are player CHOICES, not empire-TYPE facts, and
  `available` is the literally correct answer to "does empire type exclude this" — matching the
  project's show-what's-needed-never-assume stance (D-6).
- `pipeline.dataset_emit`'s `technology_swap` axis filter is structurally unreachable for this
  defect: only swaps with `axis_expressible = True` are evaluated, and that flag requires every
  leaf to be in `AXIS_FACTS`, which excludes `EXCLUDED_KEYS` entirely by construction.
- `pipeline.edge_constraints._edge_active_per_profile` is sound by purpose, not accident: it's a
  sensitivity comparison using its own monkeypatched leaf/combine functions (forcing a leaf true
  vs. false and checking whether state equality changes) — it never asserts a state as a verdict
  at all, so EXCLUDED's meaning there is moot.

`_apply_weight_gate` was the only unsound caller, because it asks a THIRD, different question ("is
weight currently zero") for which "presume open" has no meaning at all — the fix (working from the
internal `_State` directly rather than the public `AVAILABLE`/`LOCKED`/`UNCERTAIN`/`CONFIG_GATED`
wrapper, and giving `_State.EXCLUDED` its own branch that can only ever route to the new
`weight-gated` state, never `LOCKED`) is asserted with a standing test
(`evaluate_technology_for_profiles`'s decision-5 tripwire: impossible for a weight gate to lock all
12 profiles), not left as an emergent property of the `axis_pure` bucket routing that a future
change could silently reintroduce. Full write-up of the fix and the corpus figures:
`spec/decisions.md`'s D-10 Extension, `docs/BUILD-LOG.md`.
