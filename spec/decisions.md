# Decisions

Resolved open questions from the v1.0 draft. Each is now normative in its requirement file;
this document records the reasoning so it is not relitigated.

## D-1 — Research path shape (was OQ-1)

The popup shows the **complete ancestor set in topological order**, presented by tier with
cumulative research cost, plus a "shortest chain" toggle offering the cheapest single chain by
cumulative cost.

The ancestor set is the only unambiguously correct answer for a DAG — a research path is
generally not a single chain. The toggle exists because the cheapest chain is what most users
actually want to read.

## D-2 — Multiple prerequisites (was OQ-2)

**The concept of a primary prerequisite is removed.** Where a technology declares several
prerequisites, all are equally required by the game. Designating one as primary would be a
fiction the data does not support.

The model carries a flat `prerequisites` list ordered deterministically by tier descending,
then cost descending, then technology key. The popup lists all of them.

## D-3 — Gate ordering (was OQ-3)

Ascension perks outrank technology gates. Ordering is defined by a checked-in priority table in
the gate-pattern registry, not by source declaration order.

## D-4 — Research weight presentation (was OQ-4)

Base weight shown prominently, with an expandable list of weight modifiers and their
conditions. **No evaluated weight.** Weight is modified at runtime by live empire state;
static analysis cannot produce a number that is right often enough to present authoritatively,
and a confidently wrong number is worse than an honest base plus conditions.

## D-5 — Repository links (was OQ-5)

The field is always rendered, with three branches:

- Where Gigastructures overrides the technology: a permalink pinned to the build's source
  commit, targeting the file and line range.
- Where the technology is ACOT- or AoT-sourced (P-16): a link to that mod's Steam Workshop item
  page. Workshop items have no commit-pinned line-range permalink, and the technology isn't
  vanilla, so neither of the other two branches applies.
- Otherwise (unmodified vanilla): a link to the Stellaris wiki.

Wiki anchors derive from the localised technology name, so they are right most of the time and
silently wrong occasionally. CI validates that each anchor resolves in the fetched page and
falls back to a wiki search URL where it does not. The field is never dead and never omitted.

## D-6 — Empire type enumeration (was OQ-6)

**Three independent axes composed at build time**, never a flat enumeration:

- Gestalt/authority: regular, hive mind, machine intelligence
- Shipset: mechanical, biological
- Nomadic: yes, no

Twelve profiles. A flat list combinatorially explodes and cannot express that any empire type
can be nomadic and that nomadic empires use either shipset.

Origins are not an axis for v1 — there is little or no origin-gated technology content. The
fact registry stays extensible, so if extraction surfaces origin-gated techs, adding a fact is
a configuration line rather than a restructure.

**Ascension perks are gates, not profile facts.** A perk-gated technology always displays its
gate. The tree shows what you would need; it never assumes you have it. Modelling perks as
facts would silently hide the requirement from a player who has not taken the perk.

## D-7 — Crisis faction coverage (was OQ-7)

Five factions: Aeternum, Blokkats, Compound, Sirenalia, Katzenartig Imperium.

Assignment is derived in order: technology ID, then `potential` and prerequisite inspection,
then a checked-in manual override file for the remainder. The override file is permitted
hand-maintained configuration under P-10.

## D-8 — Vanilla corpus provisioning (was OQ-8)

Contributor-local, gitignored, populated by `tools/collect_vanilla.py` from the local Steam
install. Never committed, never redistributed. The build fails with a clear message when the
corpus is absent rather than silently producing a mod-only graph.

## D-9 — Localisation scope (was OQ-9)

English only for v1. The pipeline is language-parameterised so additional languages are a build
flag. Non-English output cannot be quality-checked by the maintainer, and shipping unverifiable
translations is worse than shipping one verified language.

## D-10 — Unknown availability tolerance (was OQ-10)

**D-10 splits into two distinct metrics over the RENDERED node set (not all 1,879 canonical
technologies — see "Two denominators" below).** Both come from the same partial trigger
evaluator (`pipeline/availability.py`); they differ in what they measure and, deliberately, in
whether the 10% ceiling applies.

### Profile-dependent uncertainty (what the thresholds below govern)

A technology whose resolved state (available/locked/uncertain) **varies by profile** — at least
one profile's boolean structure short-circuits to a definite `true`/`false` via `AND`/`OR` while
at least one other profile is left stuck on a genuinely undecidable leaf. This is the case D-10
was written for: the profile selector telling one user their empire can research something while
telling another (wrongly, because the tool couldn't finish the check) that it's unknown.

Thresholds are measured **per empire profile**, not pooled across all twelve. Each profile's
build produces its own rate (profile-dependent-uncertain technologies for that profile ÷ rendered
node count).

- Hard ceiling: 10% for any single profile. If the **worst** profile exceeds 10%, the build
  fails — one bad profile fails the build even if the other eleven are well under.
- Warn threshold: 3%, per profile.
- Ratchet: CI fails if any individual profile's rate rises against that same profile's figure in
  the previous dataset, even when the absolute figure is under 10%.

Pooling across profiles would let a bug that makes one specific profile (say, machine
intelligence) resolve badly hide inside an average dominated by the other eleven — exactly the
kind of profile-specific evaluator bug this threshold exists to catch. Measuring and ratcheting
per profile is the only way the ceiling means what it says for every profile a user can select,
not just the fleet average. Without the ratchet, 10% becomes the resting state rather than the
ceiling.

### Unconditional uncertainty (a separate figure, no ceiling)

A technology `uncertain` under **every one of the twelve profiles identically** — no axis check
anywhere in its trigger structure, so no profile can short-circuit to a definite answer either
way. This never happens because the profile selector is wrong about a user's empire: it's the
same honest "unknown" no matter which of the twelve profiles is selected, reporting a fact
outside the empire-axis model entirely (crisis-chain progress, story flags, mid-game player
state such as `has_country_flag = herculean_built`) rather than mis-describing the user's empire
type. That is a different quality signal from profile-dependent uncertainty, and one 10% ceiling
cannot honestly serve both — a build that is 100% honest about "this is crisis-chain-gated, not
computable from your empire type" is not the failure mode D-10's ceiling exists to catch.

Published as its own data-completeness figure, with its own ratchet against regression (an
upward move means the evaluator got worse at resolving triggers, or new undecidable content
landed — both worth seeing), but **NOT subject to the 10% ceiling**.

### Two denominators — use rendered nodes, not all 1,879 canonical technologies

Both metrics above are computed over **rendered nodes** (P-16's closure — 980 at last count),
not the full 1,879-technology canonical set, because rendered nodes are what actually ships to a
user; an unrendered ACOT/AoT technology's uncertainty is invisible and irrelevant. **The two
denominators give materially different, and oppositely-signed, answers** — checked, not assumed:
the all-1,879 uncertain rate (22.67% with the three resolutions below applied) is *lower* than
the rendered-980 rate (26.84%), because the ~1,780 non-rendered ACOT/AoT technologies excluded by
P-16's closure have a *lower* undecidable-leaf rate than the vanilla/Gigastructures content that
actually renders — Gigastructures' own crisis-faction/endgame-chain content is the concentration
point (39.00% at-risk at last measurement), not vendored-but-unrendered ACOT/AoT bulk content.
Narrowing ACOT/AoT rendering scope would not fix a ceiling breach; the two problems are
orthogonal. Always state which denominator a reported rate uses.

### Documented evaluator assumptions

Three assumptions the evaluator applies before anything counts as uncertain, each individually
justified against the vendored corpus (not a blanket "assume everything works"):

1. **Mod-config content-toggle global flags resolve to their unset default** — scoped to
   `has_global_flag` names matching `pipeline.trigger_text.MOD_CONFIG_TOGGLE_SUFFIXES`:
   `_forbidden`/`_disabled`/`_OFF` (e.g. `acot_weapons_forbidden`, `aot_phanon_content_OFF`,
   content not forbidden by default — confirmed by corpus survey to be the dominant shape), and
   `_capped_r` (the `giga_tech_repeatable_*_cap` family's cap-mode selector — see this section's
   "CONFIG_GATED" subsection below for why this suffix's evidence and consequence are both
   different from the other three). Flags outside this pattern (`compound_invasion_happened`,
   `blokkat_crisis_defeated`, `l_cluster_opened`, `has_aot_mod`, ...) are real, undecidable
   game/story state and are deliberately excluded from the assumption.
2. **All official DLC assumed owned** — both a literal `has_dlc`/`host_has_dlc` leaf (whose
   value names the DLC, not a yes/no target) and the dozen named per-DLC scripted-trigger wrappers
   confirmed by direct inspection to be pure `host_has_dlc` calls (`has_shroud_dlc`,
   `has_paragon_dlc`, `has_machine_age_dlc`, and others — see `pipeline/availability.py`'s
   `GROUND_FACT_BOOL` for the full, individually-verified list). Two adjacent, similarly-named
   triggers (`has_gigastructural_constructs`, `has_galactic_wonders`) were checked and found to
   NOT be DLC wrappers — both are actually ascension-perk-gate checks in disguise — and are
   deliberately left unresolved rather than swept in by name-pattern alone.
3. **Not-a-fallen-empire is a ground fact of all twelve profiles** (`is_fallen_empire`,
   `merg_is_fallen_empire` always resolve `no`) — none of the twelve empire-axis profiles models
   a fallen empire.

Two further exclusions are not "assumptions" in the same sense — they are leaf kinds this
evaluator does not resolve either way, because resolving them is a different mechanism's job
entirely, and folding them into `uncertain` would be a category error:

- **`has_technology`** — prerequisite-graph reachability (P-14), owned by the structural DAG
  check, not a trigger truth value.
- **`has_ascension_perk`** — a P-3 gate (D-6/P-1: ascension perks are gates, not profile facts),
  displayed on the card rather than folded into availability state.

Both are excluded from boolean combination entirely (an identity element under `AND`/`OR`, not
resolved `true` or `false`) rather than counted as undecidable.

### CONFIG_GATED — a fourth availability state, and this assumption's first real application

**`AvailabilityState` (`schema/common.schema.json`, renamed from `ThreeState` here) gains a
fourth value: `config-gated`.** Everywhere else in this project, `locked` means "your empire
cannot obtain this" — a property of the empire being played, the reason D-10's other three states
are keyed to the twelve-profile axis model at all. That framing breaks for one real case: the
`giga_tech_repeatable_*_cap` family (50 rendered technologies)'s `potential` is
`NOT{has_global_flag=$name$_disabled} AND has_global_flag=$name$_capped_r` — both leaves are
mod-configuration toggles (`pipeline.trigger_text.MOD_CONFIG_TOGGLE_SUFFIXES`), resolved to their
unset default per assumption 1 above, and the technology resolves DEFINITIVELY to FALSE for every
one of the twelve profiles identically. Rendering this as `locked` would tell a player their
empire is what stands between them and the technology, when in fact nothing about the empire
matters at all — the block is one options-menu toggle away, unrelated to authority, shipset, or
nomadic status. `config-gated` names this honestly, as a state distinct from `locked`, carrying
its own `reason` (the mod-config leaf's trigger text) and `category`
(`ReasonCategory.MOD_CONFIGURATION`, `pipeline.trigger_text`). Emitted as semantic state only —
Stage 3 decides the visual treatment (a distinct icon/colour, a "toggle X to unlock" phrasing,
etc.), not specified here.

**This is D-10's `_forbidden`/`_disabled`/`_OFF`/`_capped_r` mod-config assumption's first real
application to a bare (un-negated) flag, not a hypothetical extension.** Every prior real-corpus
occurrence of a `_forbidden`/`_disabled`/`_OFF` flag is wrapped in `NOT{}` ("if not forbidden,
proceed") and so contributes to an AVAILABLE result under the assumption, never a LOCKED one —
confirmed by re-running the corrected evaluator over the full 980-node rendered set: `config-gated`
fires for exactly the 50 `giga_tech_repeatable_*_cap` technologies and no others, even though the
underlying code change (recognising a mod-config-categorised leaf as the reason for a FALSE
result) applies generally to all four suffixes, not just `_capped_r`. **Producing a determinate,
explainable answer here is the outcome an assumption is supposed to produce, not something that
needs its own separate defence** — the same "assume documented default" reasoning that already
resolves `_forbidden`/`_disabled`/`_OFF` correctly turns out to also correctly resolve
`_capped_r`; it does not need to be treated as a riskier or less-grounded case just because it's
newly applied.

**Evidence for `_capped_r`'s default specifically, and its caveat**: user-supplied ground truth,
not inferred from the general modding convention the other three suffixes rest on — the default
cap differs across Gigastructures' three core presets, but no core preset sets a cap to the
`_capped_r`-named "1+r" (unbounded-scaling) mode, so the flag is unset in a default game. **A
player running a non-core or custom preset may set a cap to that mode and see a different real
availability than this tool reports.** That is a Stage 3 presentation concern (the same kind of
approximation D-10's other assumptions already carry — "default DLC ownership," "default mod
settings" — none of them promise to match every possible player configuration), not a data
problem to solve by making the evaluator less certain; the tool reports the default-preset answer
honestly and consistently, the same posture it already takes for the other three suffixes.

Real measured effect on the two D-10 metrics (980-node rendered set, both metrics recomputed
after `config-gated` was introduced): **profile-dependent uncertainty is UNCHANGED** (3.37%
worst-case, same profile, same rate to five decimal places) — none of the 50 was ever a
profile-dependent case, since their `potential` has no axis check at all. **Unconditional
uncertainty drops from 259/980 (26.4%) back to 209/980 (21.33%)** — the same 50 that an earlier,
narrower fix (recognising `_capped_r` as resolvable at all, without yet distinguishing
`config-gated` from `locked`) had moved from `uncertain` into `unconditionalUncertainty`
now leave that bucket for `config-gated` instead. **209 is the same number an even earlier,
now-corrected raw-block survey reported, by coincidence of arithmetic, not by the same
reasoning** — that number was wrong because it skipped these 50 nodes' real gating condition
entirely; this number is right because it evaluates all 980 correctly and finds the 50 belong in
a fourth state neither `uncertain` nor `locked` capture.

### The 209 -> 259 -> 209 sequence, recorded explicitly so it cannot be misread

Two sessions produced three unconditional-uncertainty figures for the same 50-technology family,
and the first and third are both 209 — read side by side with no further context, that looks like
the intervening work was a no-op. It was not. The two 209s exclude the same 50 nodes from
`unconditionalUncertainty`, but for opposite reasons, and the real change is visible in a
different figure (the AVAILABLE-state count), not in this one:

| Step | Unconditional uncertain | What happened to the 50 `giga_tech_repeatable_*_cap` nodes | Their state |
| --- | --- | --- | --- |
| 1. Original (raw-block survey) | **209/980** | Invisible — a raw/unexpanded read never saw their `potential` block at all. Excluded from `uncertain` by a defect: the evaluator never looked. | **AVAILABLE** (wrongly — "no potential block" reads as unconditionally available) |
| 2. After the `inline_script`-expansion fix | **259/980** (209 + 50) | Now visible. Both leaves (`NOT{has_global_flag=X_disabled}`, `has_global_flag=X_capped_r`) resolved as ordinary undecidable leaves, so all 50 became genuinely `uncertain`. | UNCERTAIN |
| 3. After `_capped_r` joins `MOD_CONFIG_TOGGLE_SUFFIXES` + `config-gated` is introduced | **209/980** | Still visible, now correctly evaluated: both leaves are mod-configuration toggles that resolve DETERMINATELY (not undecidably) under D-10's default-preset assumption, so all 50 leave `uncertain` again. | **CONFIG_GATED** |

Step 1's 209 excludes the 50 by failing to see them. Step 3's 209 excludes the same 50 by
evaluating them correctly and finding they belong in a fourth state, `config-gated`, that didn't
exist yet at step 1. **That is why the unconditional-uncertainty category distribution is
byte-identical between step 1 and step 3** (spec/decisions.md's category table, CLAUDE.md) — the
209 members are the same nodes both times.

**The substantive change is real and is visible in the AVAILABLE-state count, not the uncertainty
count**: all 50 moved from `AVAILABLE` (step 1's wrong reading) to `CONFIG_GATED` (step 3's
correct one). Measured directly
(`tests/test_dataset_emit.py::test_repeatable_cap_family_available_count_delta_is_exactly_minus_50`):
evaluating with no `potential` block visible (the step-1 counterfactual) is unconditionally
AVAILABLE for all 50; the real, expanded evaluation used throughout this pipeline is AVAILABLE for
**0** of them. **The available-count delta is exactly -50**, confirmed, not merely expected — if a
future corpus refresh moves this delta away from -50, that test fails, signalling something else
changed too.

**Ratchet status**: the D-10 unconditional-uncertainty ratchet (this file's D-10 section) compares
each build's count against the previous build's. Having gone 209 -> 259 -> 209 across two
sessions, the figure is back at its original seed value — no regression, no ratchet action needed,
and no special-casing required to avoid a false "increased" or "decreased" reading against a stale
259 baseline.

See P-13 (`spec/P-13-empire-locking.md`'s "Config-gated reason template" section) for what
happens next for these 50 nodes on the display side — the config-gated `reason` text, sourced from
each technology's own resolved megastructure name, not this uncertainty accounting.

## D-11 — Rendering stack

PixiJS over a hand-rolled WebGL renderer. Hand-rolling a 2D renderer that meets the P-10
budgets at 10³–10⁴ nodes is weeks of work that is not the interesting part of this project, and
PixiJS still permits the custom fills and shaders the crisis patterns need.

## D-12 — Pipeline language

Python, continuing from the v1 implementation. The dataset schema becomes an explicit
cross-language contract as a result — see `00-overview.md`.

## D-13 — Layout bands are declared tier, not computed position (corrects an earlier draft)

**A node's tier band is its own declared `tier` field, unmodified by graph depth.** An earlier
draft of P-2 had layout *promote* a node's displayed position whenever a prerequisite's declared
tier was at or above its own, and had S-3's column headers reflect that computed position rather
than the mod's own tier vocabulary. That draft is superseded, based on direct v1 evidence: v1's
tier-banded reading was close to right and not a reported failure; v1's real failures were
incorrect tier *placement* and inadequate lock/prerequisite labelling. Tier is vanilla's and
Gigastructures' own vocabulary — a band showing "Tier 5" should contain what the mod calls tier 5,
full stop, not a mix of promoted and native content under a renumbered header.

Computed position (longest-path depth over the rendered prerequisite graph) is retained, but
purely as **internal geometry**: it orders technologies horizontally within a band's sub-grid,
and gives the router a consistent signal for backwards edges (below). It is never displayed as a
number anywhere in the UI, so there is nothing for a band header to disagree with — see S-3's
"Band header and card tier badge always agree" note.

**Consequence: backwards edges are real graph structure, not an invariant violation.** Because
band placement no longer moves to keep every edge pointing strictly left-to-right, an edge can
run from a later band to an earlier one whenever its own declared tier is higher than its
dependent's. **Record this figure as a per-kind decomposition, never a single number — see the
note below for why.** Measured against the real 980-node rendered corpus, over the full P-14
three-kind edge set (989 edges: 888 `prerequisite` + 76 `alternative` + 25 `potential-gate`):
**34 backward edges total, decomposed as 25 `prerequisite` + 2 `alternative` + 7
`potential-gate`.** `prerequisite` and `alternative` both stay within 1-2 bands back (worst
cases: `tech_antimatter_power` (T3) → `tech_reactor_boosters_3` (T1) and `tech_mega_engineering`
(T5) → `giga_tech_penrose_sphere_1` (T3), both `prerequisite`; `tech_stingers` (T4) →
`tech_swarmer_missiles_1` (T2), `alternative`) — small and short-range, well within what P-8's
inter-band gutter routing can carry. `potential-gate` does NOT fit that characterization: its 7
backward edges span up to **5 bands back** (`tech_cosmogenesis_escort` (T5) → `tech_missiles_1`
(T0), the worst case) — a `has_technology` gate can reference any technology anywhere in the
tree, with no reason to sit near its owner's declared tier the way a formal prerequisite chain
does. See `spec/P-08-connectors.md` for the corrected routing-treatment text (rescoped to
`prerequisite`/`alternative`; `potential-gate`'s routing is `TODO(Stage 3)`, deliberately deferred
to a real rendered canvas). A build MUST NOT warn or fail merely because a backward edge of any
kind exists.

**Denominator/count reconciliation note — this figure has moved three times, purely through
re-scoping, never through an actual data change.** Recording it as one number is exactly what let
it drift unnoticed each time; recording the kind (and, where relevant, the repeatable-membership
rule) alongside the count is the fix:

1. **27 of 891** — original measurement, `prerequisite`-only, under the initial
   repeatable-membership rule that tested `levels < 0` only (76 nodes).
2. **27 of 881** — same edge scope, corrected repeatable membership (a `levels` field present at
   all — 88 nodes; see this section's repeatable-band exception below). Same 27 backward edges by
   key; only the denominator moved, because none of the 12 newly-recognised repeatables touches a
   backward edge.
3. **25 `prerequisite` + 2 `alternative` + 7 `potential-gate` = 34** — the true final figure, once
   `alternative`-branch members stopped being flattened into the `prerequisite` list (P-14 edge
   typing) and `potential-gate` was extracted as a real edge kind for the first time (it was never
   counted at all before). 2 of the original 27 were always `alternative`, not `prerequisite`,
   misclassified by the flattening; the other 7 are genuinely new, not previously tracked in any
   form. 964 = 888 `prerequisite` + 76 `alternative` reconciles exactly against the 964 figure from
   the 891-vs-964 session (nothing drifted, the count decomposed); adding the 25 `potential-gate`
   edges (not counted before) gives the real total, 989.

**One declared exception to "bands are declared tier, full stop": repeatable technologies.**
A repeatable technology (source declares a `levels` field at all — see the corpus-finding note
above) always bands into a terminal **Repeatables** band positioned after the last declared-tier
band, regardless of its own `tier` value, and its card badges **repeat count** (`×N`, or `∞` for
an unbounded `levels = -1`) in place of the tier badge. `tier` is still resolved, still validated
(`UnresolvedTierError` still applies unchanged — no exemption), and still emitted for these
nodes; it remains meaningful for internal sub-grid ordering and the detail popup. It is simply
not what the band header or the card display for a repeatable node.

**Why this is not a return of v1's bug, and must not be "corrected" back to strict declared-tier
banding by a future session that re-derives D-13 from first principles.** v1's failure was a band
header making a FALSE claim about the cards under it: a header reading "TIER 6" over a grid of
cards each internally badged T5 — the header asserted something the cards contradicted. The
repeatable exception does not do that. The Repeatables band header asserts "this is the
Repeatables band" and the card badges "this technology repeats N times" (or ∞) — both are true
statements, about two different things (band membership vs. repeat count), and neither
contradicts the other. No card under the Repeatables header claims to be tier-banded, and no
tier-banded card is ever badged with a repeat count it doesn't have. D-13's actual rule — "a
band's header must never assert something a card under it contradicts" — is upheld by this
exception, not violated by it. Read this paragraph before "fixing" the apparent inconsistency
between "bands are declared tier" and "except repeatables" — the exception is deliberate and
load-bearing, not an oversight.

Membership for this exception is deliberately **not** the same set as the 50
`giga_tech_repeatable_*_cap` nodes from P-2's tier-source audit (the ones whose `tier` field only
exists after `inline_script` expansion) — that is a different, though overlapping, set: all 50
`_cap` nodes happen to be repeatable (a proper subset of the 88), but the 88-node repeatable set
also contains 38 non-`_cap` repeatables (e.g. `tech_repeatable_reduced_building_cost`,
`tech_cosmogenesis_thesis`) that never went through inline_script expansion for their tier at
all. Conflating "repeatable" with "inline_script-tier-only" is a distinct bug from either finding
alone; `tests/test_layout_corpus.py::test_inline_script_tier_group_is_proper_subset_of_repeatable_group`
guards against it.

**The sink property**: every edge (of any P-14 kind) touching a repeatable node runs
non-repeatable → repeatable; zero edges run repeatable → non-repeatable or repeatable →
repeatable (verified over the corrected 88-node membership, not assumed carried over from the
old 76-node measurement). Consequently a repeatable node can never source a backward edge either
— it never sources any edge at all — so the Repeatables band needs no intra-band edge routing and
is guaranteed edge-simple. `tests/test_layout_corpus.py::test_repeatable_band_never_sources_an_edge`
asserts this directly against the real corpus rather than relying on it as an unstated
consequence.

**Edge-count reconciliation, per kind (P-14 edge-typing session) — every figure below is exact
against the previous session's, nothing drifted, only decomposed**:

| | non-repeatable → non-repeatable | non-repeatable → repeatable | total |
|---|---:|---:|---:|
| `prerequisite` | 809 | 79 | 888 |
| `alternative` | 72 | 4 | 76 |
| `potential-gate` | 25 | 0 | 25 |
| **all three kinds** | **906** | **83** | **989** |

964 (the previous session's `prerequisite`-only total, before `alternative` was split out) =
888 + 76, exactly. 881 (the previous session's non-repeatable-to-non-repeatable total) = 809 + 72,
exactly. 989 adds the 25 `potential-gate` edges, which weren't extracted as an edge kind at all
before this session, and the "all three kinds" row is a plain per-kind sum (809+72+25=906,
79+4+0=83) — the 4 pairs that are both a `prerequisite` and a `potential-gate` edge are two
distinct `TypedEdge` records, each counted once in its own kind's row, so they need no
deduplication adjustment here (see this file's D-13 exception paragraph above and
`spec/P-14-unconventional-prereqs.md` for why kind membership is not mutually exclusive per
pair).

## D-14 — `technology_swap` presentation: substitute the expressible, list the rest

**A `technology_swap` sub-block gives a technology a different name/icon/(sometimes)
area/category per empire type, but it NEVER becomes its own rendered node.** The rendered node
set stays exactly 980 (`pipeline.rendering_scope`'s P-16 closure) whether or not a technology
carries a swap — a swap changes how ONE node presents, never whether it, or a second node,
exists. Asserted directly against the real corpus
(`tests/test_dataset_emit.py::test_rendered_node_count_stays_980_regardless_of_technology_swap`),
not left as an unstated consequence of "nothing parses swaps into layout/edges."

**Real corpus: 214 swaps across 185 of the 980 rendered technologies.** Every swap's `trigger` is
classified against `pipeline.availability.AXIS_FACTS` — the SAME dict the trigger evaluator
itself uses for `potential` blocks, reused directly by the new `pipeline.technology_swaps` module
rather than a second, competing classification that could silently disagree with it. A swap is
**axis-expressible** only when every leaf anywhere in its trigger (through nested
AND/OR/NOT/NOR) is an axis fact — a compound trigger is only as expressible as its
least-expressible leaf, matching the evaluator's own Kleene short-circuit discipline of never
granting partial credit on a compound condition. **128 axis-expressible, 86 non-axis** — this
CORRECTS the pre-implementation survey's ad-hoc 126/88 split, which omitted
`is_mechanical_empire`/`is_robot_empire`/`is_regular_empire` from its own axis-leaf set;
`AXIS_FACTS` already treats all three as resolvable (the authority axis; `is_robot_empire`
specifically via an established, already-audited approximation documented on `AXIS_FACTS` itself)
— reusing the canonical source instead of a fresh classification caught this before it could
drift into a second, silently-wrong definition of "axis-expressible."

### Two treatments, never a third

1. **Axis-expressible (128 swaps, 123 technologies) substitute per profile.** The empire-overlay
   artefact's `swapMappings` (`schema/empire-overlay.schema.json`, redesigned this decision — the
   old `{baseTechnologyId, activeVariantId}` shape assumed a variant had its own id to point at,
   which decision 1 above rules out categorically) carries one entry per technology whose
   swap is active for that profile: `{technologyId, name, icon, area, category}`, with
   `area`/`category` `null` meaning "unchanged from the base dataset's own value" (only 8 real
   swaps ever redeclare either — see below). A technology with no matching swap for a profile has
   no entry at all; a renderer falls back to the base dataset's own fields. **Icons cost nothing
   new**: swap icon candidates are already resolved, decoded and packed into the atlas alongside
   base technology icons (confirmed before this decision was scoped — see the prior session's
   survey) — substitution only adds a small `IconRef` pointer, never new image bytes.

2. **Non-axis (86 swaps, 72 technologies) NEVER substitute — listed as popup-only variants
   instead.** The detail-payload artefact's new `variants` field
   (`schema/detail-payload.schema.json`) carries `{name, icon, conditionText}` for every non-axis
   swap on that technology, `conditionText` rendered by `pipeline.trigger_text.describe_condition`
   (via the new `describe_trigger_block` for a multi-leaf trigger's implicit-AND top level).
   Follows the ascension-perk-gate precedent already established elsewhere in this project: the
   tree shows what exists and what you would need, never assumes an empire fact it cannot verify.
   Extending the 3-axis model to cover origins/civics/species-traits/ascension-perks/galaxy-state
   (what the 86 non-axis leaves actually condition on) would explode the profile count and
   re-open D-6's settled empire-model decision — deliberately not done.

**A technology can appear in both** (10 real cases) — one swap substitutes, a different swap on
the same technology lists as a variant; the two mechanisms are independent per-swap, not
per-technology.

### The tech_ring_world exception: no partial credit on a compound trigger

`tech_ring_world` carries two swaps whose trigger is `country_uses_bio_ships = yes AND
giga_can_use_habitables = {no|yes}` — one axis leaf, one non-axis (origin-derived) leaf, mixed in
a single compound condition. **Decided in chat, explicitly: NO special-casing.** The whole
compound trigger is treated as non-axis, not "half substituted on the bio-ships leg." Substituting
on the axis leg alone would assert a fact about the player's empire
(`giga_can_use_habitables`) this tool cannot verify — the same reasoning the Kleene evaluator
already applies elsewhere (a compound condition is only as resolved as its least-resolved leg).
Cost is bounded and named: `tech_ring_world` keeps its base `society`/`voidcraft` presentation for
every profile, with all 3 of its non-axis swaps (including the pure `giga_can_use_habitables`-only
one, plus these two bio-ships-mixed ones) listed in its popup with their conditions described.
Recorded explicitly here, by name, so a future session doesn't rediscover this as an anomaly.

### area/category substitution: real, but narrow

Beyond name/icon, 8 of the 214 swaps redeclare `area` and/or `category` differently from their
owning technology (`tech_colossus`, `tech_juggernaut`, `tech_ring_world` ×2 — both non-axis, see
above — `tech_strike_craft_1/2/3/skrand`, `tech_titans`; all `society`→`engineering`,
`voidcraft`→`biology`). **All 8 belong to swaps confirmed axis-expressible or non-axis per the
same classification as name/icon** — no separate mechanism was needed: the 6 axis-expressible
ones (all bio-shipset) get their area/category substituted for free by the same `swapMappings`
entry that substitutes their name/icon; `tech_ring_world`'s 2 non-axis ones never substitute
anything, area/category included, consistent with the exception above.

### Icon inheritance for an `inherit_icon = no` swap with nothing to resolve to

One real swap, `giga_tech_ring_world_swap_no_habitables`, declares `inherit_icon = no` but has no
icon file of its own in the vendored corpus. `pipeline/icons/resolve.py` correctly and
deliberately leaves this as an unresolved atlas candidate — redirecting it to the owner's icon AT
THAT LAYER would override an explicit authorial refusal (that module's own docstring already
argued this, and remains correct: it is about atlas-packing honesty). **This decision adds a
SEPARATE, presentation-layer fallback in `pipeline.dataset_emit`**: when actually emitting
`swapMappings`/`variants` for display, a swap with no icon of its own falls back to the OWNING
technology's icon, so the card/popup shows something rather than nothing. An `overrides.txt`
config entry was explicitly rejected as the mechanism — it would require a human to notice and
remove it once upstream ships a real icon, and would silently shadow that real icon in the
meantime. The fallback instead yields automatically: the next re-vendor that ships a real icon for
this swap makes it resolve normally with zero config change, because the fallback only ever
triggers when the candidate is in `IconResolutionResult.unresolved` in the first place.

The fallback is tracked, not silent: `diagnostics.swapsRenderingOnInheritedIcon`
(`schema/diagnostics.schema.json`) lists every `(technologyId, swapKey)` pair currently rendering
on an inherited icon — today, exactly the one real case above. If this list shrinks on a future
re-vendor, upstream shipped a real icon; if it grows, a swap lost icon coverage. It deliberately
does NOT fire for the 87 swaps that legitimately keep the base icon via `inherit_icon` defaulting
to `yes` — those resolve successfully through the ordinary `inherit_icon` channel and are never
`unresolved` candidates in the first place, confirmed directly
(`tests/test_dataset_emit.py::test_swap_icon_inheritance_diagnostic_fires_only_for_the_one_real_case`).

### Trigger-text coverage: real gaps reported, not invented

`pipeline.trigger_text.describe_condition` is reused as-is for `conditionText`, per its own
"falls back to raw trigger text rather than fabricating prose" contract. **9 non-axis leaf names
have no dedicated phrasing and fall back to raw trigger text** (`is_wilderness_empire` — 41
occurrences, the largest by far — `is_beastmasters_empire` 16, `giga_can_use_habitables` 3,
`is_tankbound_empire` 2, `is_reanimator` 2, `is_eager_explorer_empire` 2,
`has_void_dweller_origin` 1, `is_cloning_authority` 1, `is_situation_type` 1). None of these were
invented phrasing for this decision — reported here as an open item for whoever next extends
`trigger_text.py`'s phrase table, same discipline as every other undecidable-leaf gap this project
tracks rather than papers over.

### `weight` and `prereqfor_desc`: seen, deliberately still unsurfaced

Two more fields a `technology_swap` sub-block can carry, found during this decision's own survey
and NOT wired into any artefact: `weight` (94/214 swaps — the swap's own weight-factor block,
distinct from the owning technology's `weight`) and `prereqfor_desc` (39/214 — a distinct
unlock-description string). Both are consistent with D-4's "no evaluated weight" precedent (a
swap-specific weight modifier is exactly the kind of static-analysis-can't-promise-a-real-number
case D-4 already declines to surface) and with `description`'s existing scope (only a
technology's own `_desc` loc key is read anywhere in this pipeline). Recorded here explicitly so a
future session knows this was seen and deliberately skipped, not missed.

### Real payload delta, measured (not the pre-implementation ~9.7 KB gz worst-case estimate)

The base dataset itself (P-10's ≤2 MB budget) is **unchanged** — `swapMappings`/`variants` live
in the empire-overlay and detail-payload artefacts, both already lazy/per-profile and excluded
from that budget. Measured directly against the real build
(`tests/test_dataset_emit.py::test_swap_payload_delta_against_base_dataset`): `swapMappings`
across all 12 empire overlays adds **~17.5 KB gzip** (~141 KB raw, 745 total entries); `variants`
across all 980 detail payloads adds **~2.8 KB gzip** (~15 KB raw, 86 total entries — one per
non-axis swap). Both trivially small next to the ~64-67 KB base-dataset reference point this
project has used for scale, and irrelevant to P-10's ceiling regardless since neither artefact
counts against it.

## D-15 — Deploy model: local build, manual deploy (vanilla is a permanent CI blocker)

**The dataset cannot be built in GitHub Actions, and this is a permanent constraint of the
project's inputs, not a gap scheduled to close.** Investigated directly (a prior session's
vendoring-automation investigation, referenced throughout this decision): `tools/collect_vanilla.py`
reads a *local Steam library directory* with no network fetch path at all. Making it CI-capable
would require SteamCMD authenticated as an account that **owns a paid Stellaris license** — game
depot downloads require app ownership; there is no anonymous path to a paid game's files. Two
ways around that, both foreclosed:
- Storing real Steam account credentials as a CI secret — a genuine security exposure (an account
  tied to a real purchase, used for unattended automated download) and very likely a Steam ToS
  violation for automated/CI use.
- Redistributing the extracted vanilla files some other way — foreclosed outright by this
  project's own standing rule that `vendor/` content is never redistributed (a copyright
  constraint, not a style preference).

No option closes this gap. It is therefore treated as permanent, and the deploy model is designed
around it rather than around an assumed future fix.

**Decision: the dataset is built LOCALLY (`tools/build_dataset.py`, where `vendor/` already
exists) and deployed via a manually-triggered (`workflow_dispatch`) GitHub Actions workflow that
takes a pre-built artefact and publishes it — it does not build anything itself.**
`tools/deploy_local.sh` orchestrates the local side: build the dataset, build the client
(`npm run build`), zip `client/dist/`, publish that zip as a GitHub Release asset, and print the
exact command to trigger `.github/workflows/deploy.yml` against that release tag. The workflow
downloads the named release's `dist.zip`, sanity-checks it actually contains a dataset and an
integrity manifest, and deploys it via the ordinary `actions/upload-pages-artifact` +
`actions/deploy-pages` steps — Pages deploying a build that happened elsewhere is fully supported;
those actions are agnostic to where the artefact directory came from.

### Options considered and rejected

- **Option A — a private artefact store the CI workflow fetches from at build/deploy time**
  (e.g., a private release, a separate object store). Rejected as the PRIMARY model: it still
  requires a human with vendor access to run the build and publish somewhere, so it doesn't
  actually avoid the "local build, manual publish" step — it just adds an extra fetch hop and,
  for anything beyond this repo's own Releases, another stored credential. The chosen model
  already IS a minimal version of this (a GitHub Release on this repo, fetched with the
  workflow's own default token) — a separate private store would be strictly more machinery for
  no additional capability.
- **Option C — CI builds without ACOT/AoT, accepting a reduced but real corpus.** Rejected as the
  PRIMARY model, though its findings are used elsewhere (this file's ACOT/AoT-absent diagnostic
  reasoning below): even a fully-solved ACOT/AoT story would not make CI builds possible, because
  vanilla remains blocked regardless — the harder, more fundamental constraint. Building this
  reduced mode as the STANDARD CI path would also mean the CANONICAL deployed site is quietly
  different from what a full local build produces (977 nodes, not 980 — see the diagnostic below)
  by default, which is the wrong default for the site real users see. It remains available as a
  genuinely useful LOCAL option (e.g., for a contributor without an ACOT/AoT Workshop
  subscription) via the same `tools/build_dataset.py`, which already tolerates missing sources
  and reports the difference loudly — it is just not what an ordinary deploy runs.

### Artefacts are not committed to the repo

`client/public/dataset/` is gitignored (reversed from an earlier session's opposite decision).
Reasons: it is derived from vendored third-party content (a real, if lesser, redistribution
question than `vendor/` itself, but not zero); git retains every committed version permanently,
so every corpus refresh would add its full size to history forever; and a committed artefact can
silently disagree with the pipeline commit that supposedly produced it — precisely the staleness
problem content-hashed filenames (an earlier session) exist to prevent, reintroduced one layer up
if the committed JSON and the current `pipeline/` code drift apart unnoticed.

### Integrity manifest — states provenance, does not verify it

Every `tools/build_dataset.py` run writes `client/public/dataset/integrity.json`: the pipeline
commit SHA (and whether the working tree was dirty), `vendor/manifest.json`'s per-source
identifying info (Vanilla's `game_version`; each mod's pinned commit/Workshop ID/content hash),
which sources were actually loaded, and a sha256 checksum of every other artefact this script
writes. **State this limitation honestly wherever this manifest is described: it does NOT make
the build CI-verifiable, and nothing can, given the constraint above.** What it provides is
narrower and real: every deployed build states exactly what produced it, so a mismatch between
deployed bytes and claimed provenance is *detectable* (recompute the checksums, compare) rather
than invisible. It does not, and cannot, prove the stated pipeline commit is what actually
produced the stated vendor content — that still rests on trusting whoever ran the local build,
the same trust model any pre-Actions "deploy from a laptop" workflow always had.

### ACOT/AoT-absent builds: loud, specific, not a generic warning

**977 rendered nodes, not 980 - 7 = 973, when ACOT and/or AoT is missing — verified precisely by
actually running the pipeline this way, not estimated.** The 7 real technologies whose
`requiresMods` names ACOT/AoT correctly disappear
(`PLACEHOLDER_TECHNOLOGIES_REQUIRING_ACOT_AOT`, `pipeline/dataset_emit.py`) — these are
Gigastructures' own "supertensile alternate" content (`giga_17_alternative_mega_build.txt`), the
actual reason ACOT/AoT are vendored at all: they show the TRUE prerequisites of those alternates,
not a cosmetic extra. But 4 vanilla technologies ACOT overwrites in the full corpus
(`VANILLA_TECHNOLOGIES_ACOT_OVERWRITES`) — `tech_adaptive_combat_algorithms`, `tech_biomechanics`,
`tech_titan_hull_1`, `tech_titan_hull_2` — are, perhaps surprisingly, **NOT themselves rendered in
the full build at all**: their ACOT-overwritten form falls outside the P-16 rendering-scope
closure (confirmed directly against the real corpus, not assumed). Without ACOT, they revert to
vanilla content, which is unconditionally rendered, and REAPPEAR. Net: 980 - 7 + 4 = 977.

This is dangerous precisely because nothing else looks broken: zero dangling edges, zero
alternative-only gaps, a schema-valid build — a plausible, self-consistent, quietly different
tree. `pipeline.dataset_emit.build_diagnostics` therefore reports this loudly and specifically,
never as a generic "some content missing" warning: `vendorSourcesLoaded` (which of the four
sources this build actually had), `placeholderTechnologiesAbsent` (the exact 7, each naming which
source they need), and `vanillaTechnologiesRevertedFromAcotOverwrite` (the exact 4, each flagging
whether the reversion is a real content difference). `tools/build_dataset.py` also prints a loud
console banner when ACOT/AoT is missing, so a contributor without a Workshop subscription to
either can't miss what they're building, not just whoever inspects the diagnostics artefact later.

**User-supplied domain context, recorded so the diagnostic's wording doesn't imply all four
reverted technologies differ equally**: most of ACOT's overwrites of vanilla technologies only
add modifiers, invisible to this tool's display regardless of which version renders —
`tech_adaptive_combat_algorithms` and `tech_biomechanics` are this case
(`contentDiffersFromOverwrite: false`). The titan hull technologies are the documented exception,
where ACOT's content materially differs from vanilla's (`contentDiffersFromOverwrite: true`) — a
reduced build showing vanilla `tech_titan_hull_1`/`tech_titan_hull_2` is a real, visible content
difference, not bookkeeping.

Both `PLACEHOLDER_TECHNOLOGIES_REQUIRING_ACOT_AOT` and `VANILLA_TECHNOLOGIES_ACOT_OVERWRITES` are
maintained constants, not dynamically derived — deliberately: 3 of the 7 placeholder technologies
are reached only through ACOT's OWN internal prerequisite chains (invisible without ACOT loaded,
so nothing present in a reduced corpus could ever discover them), and knowing "ACOT overwrites
these 4 vanilla keys" fundamentally requires ACOT's own source, which is exactly what's absent in
the case the diagnostic exists for. Both are re-verified against the real, full corpus by
`tests/test_dataset_emit.py::test_placeholder_technologies_constant_matches_full_corpus` and
`::test_vanilla_technologies_acot_overwrites_constant_matches_full_corpus`, so a future re-vendor
that adds, removes, or reassigns one of these 11 keys fails a test rather than silently going
stale.
