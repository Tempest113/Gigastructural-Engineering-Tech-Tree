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

**Ascension perks are gates, not profile facts — with a correction (a later session).** WHICH
perk a player picks is always a free choice, never a profile fact: a perk-gated technology always
displays its gate, so the tree shows what you would need and never assumes you have it (modelling
perks as facts would silently hide the requirement from a player who has not taken the perk).
WHETHER a perk is obtainable AT ALL for an empire type IS a real fact, though, when the perk's own
`potential` carries a genuine axis restriction (Galactic Wonders is nomadic-empire-impossible, and
21 of the corpus's perks are cleanly axis-restricted this way) — a technology gated behind one of
those is structurally LOCKED for an axis-excluded profile, not merely gated, the same as any other
axis-impossible technology. Automated, not hand-curated: `pipeline.availability.set_perk_
potentials` registers every perk's own resolved `potential`, and `has_ascension_perk` leaves
consult it — only a definite LOCKED result for the referenced perk turns the leaf into a real
FALSE; a perk that's merely UNCERTAIN for some profile stays a gate (`EXCLUDED`), never guessed at.
A real mutual-exclusion cycle in the corpus (`ap_defender_of_the_galaxy` ↔
`ap_defender_of_the_galaxy_nomads`) is broken by a recursion guard rather than looping forever.
This correction is also what lets `weight-gated`'s own LOCKED narrowing (this file's D-10
Extension, below) recognise an axis-restricted perk as a genuine empire-type fact, not just a bare
`AXIS_FACTS` leaf.

## D-7 — Crisis faction coverage (was OQ-7)

Five factions: Aeternum, Blokkats, Compound, Sirenalia, Katzenartig Imperium.

Assignment is derived in order: technology ID, then `potential` and prerequisite inspection,
then a checked-in manual override file for the remainder. The override file is permitted
hand-maintained configuration under P-10.

**D-7's derivation itself is unchanged by D-16's row re-axis.** What changed is only what
CONSUMES the classification this derivation produces — see D-16: a faction is no longer the row
axis itself (the old crisis-faction lane), it's the ROW-SELECTION INPUT that decides, per
technology, whether that technology's row is its faction (if classified) or its category
(otherwise). `pipeline/crisis_faction.py` — this section's implementation — did not change at
all in that session; only `pipeline/layout.py`'s consumer of `classify_crisis_factions`'s output
did.

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

### Extension — zero `weight_modifier` factor is an availability fact (Item 2b, a later session)

The "weight is a separate concern from availability" rule (CLAUDE.md's "Research weight") stands
for weight as a GRADIENT — a modifier that boosts or reduces a nonzero weight never touches
`state`. It gains one carve-out: a `weight_modifier` entry whose own `factor` resolves to a
literal `0` is Stellaris's own idiom for "this technology cannot currently be drawn as a research
option at all," which is functionally a gate, not a gradient, and D-10's two-metric split now
counts it the same way a `potential` condition is counted. `pipeline.availability.
_apply_weight_gate` evaluates each zero-factor modifier's own condition through the SAME
unchanged Kleene evaluator (never a second mechanism) and, only when the technology's
`potential`-based state is already AVAILABLE, downgrades it to LOCKED (the zero-factor condition
resolves definitely true) or UNCERTAIN (it resolves unknown) — a technology already LOCKED/
UNCERTAIN/CONFIG_GATED for a real `potential` reason is untouched, since this project's `reason`
field is a single string and the more specific existing reason wins.

**Real corpus: 248 technologies (301 zero-factor `weight_modifier` entries) carry this shape** —
materially broader than the motivating Cosmogenesis-locked example (Nano-Assembler, Polyatomic
Crucible), since the same idiom is Stellaris's standard mechanism for "exclude this tech from the
weighted draw under any condition," used throughout vanilla for ordinary things (terraforming-
variant exclusivity via `num_owned_planets`, policy/civic toggles, FE/crisis-chain gating) as much
as mod-configuration or crisis-progression gates. Measured effect: unconditional uncertainty
31/973 (3.19%) → 115/973 (11.8%); worst profile-dependent rate 16/973 (1.64%) → 58/973 (5.96%) —
crosses the 3% warn threshold, stays under the 10% hard ceiling. A considered, reported tradeoff
per this project's own discipline (the scripted-trigger-expansion session took the same posture),
not a regression to hide.

### Extension, corrected — WEIGHT_GATED, a fifth AvailabilityState (a later session)

Item 2b's own generalisation above was too broad. Three surveys (recorded in full in
`docs/BUILD-LOG.md`) classified every one of the 301 zero-factor entries by whether its condition
is decidable under the modelled axes: bucket A (profile-decidable — axis facts, DLC/ground facts,
mod-config toggles, literal constants: 30 entries / 27 technologies) contributes zero new
uncertainty by construction; buckets B (circumstantial in-game state: 193/159), C (opaque leaves:
61/61) and D (mixed A+B/C: 17/12) account for 100% of the regression measured above.

**`AvailabilityState` gains a fifth value, `weight-gated`.** Buckets B and C both route here, never
to `uncertain`: D-10 uncertainty means "the tool cannot tell you whether this is available to your
EMPIRE TYPE"; for a zero-factor weight condition the tool CAN tell you that — it's available to
your type, gated on something that is not your type. `weight-gated` does NOT count toward D-10
uncertainty, exactly as `config-gated` doesn't. Bucket D resolves per profile: an A-type leaf that
independently decides a profile's outcome (Kleene AND/OR's own false/true-dominance) still stands;
otherwise that profile gets `weight-gated` too. This need not be hand-classified per leaf — it
falls out of running the SAME Kleene evaluator `pipeline.availability.evaluate_trigger_block`
already uses and reading its `_State`/`axis_pure` result, so a leaf that becomes decidable later
(the wilderness/frameworld axis landing, for one) reclassifies automatically.

**A definite LOCKED verdict from a weight gate is narrower than bucket A**, not identical to it.
`weight_modifier` describes eligibility in the weighted research draw only — it is blind to
`give_technology`, events, special projects, archaeology and relics, any of which can grant a
technology regardless of its weight (confirmed for `tech_akx_worm_1`: permanent `always = yes`
zero weight, yet obtained through a guaranteed event chain). So LOCKED requires the deciding
leaf(s) to be genuine empire-TYPE facts — `AXIS_FACTS`, or an ascension perk whose own `potential`
carries a real axis restriction (D-6's correction, below) — never a ground fact that reads the same
for every profile (`always`, DLC, a mod-config toggle, an unrestricted perk, an unresolved
wrapper); everything else in bucket A gets `weight-gated` too. Real corpus (`pipeline.dataset_emit.
build_context`, verified by direct evaluation, not asserted): exactly 5 technologies keep a real,
axis-narrowed LOCKED from a weight gate alone — `tech_fe_assembly_1` (`is_hive_empire = yes`, 4
profiles), `tech_fe_clinic_1` (`is_machine_empire = yes`, 4), `tech_fe_entertainment_1` /
`tech_fe_market_1` (`is_gestalt = yes`, 8 each), and `giga_tech_maginot_world` (`has_galactic_
wonders = no`, 6 profiles — nomadic ones only, because this leaf is a Gigastructures scripted
trigger that `pipeline.dataset_emit._weight_gate_condition_blocks`'s own scripted-trigger
expansion turns into a real `has_ascension_perk`-chain, and the Galactic Wonders perk family is
genuinely nomadic-excluded; the pre-implementation survey's own worked example assumed this leaf
would resolve as an opaque `EXCLUDED_KEYS` shortcut instead and predicted it would reclassify to
`weight-gated` for all 12 — that assumption did not hold once the same expansion this project
already applies to every weight-gate condition was actually run, and the axis-narrowed LOCKED for
6 nomadic-profile pairs is the more accurate result, not a bug). `tech_akx_worm_1`/`_2` (`always =
yes`) and `tech_gene_seed_purification` (`NOT = { has_ascension_perk = ap_engineered_evolution }`,
an unrestricted perk) reclassify to `weight-gated` exactly as the survey predicted.

**The EXCLUDED-as-vacuously-satisfied defect (`docs/DEFECTS.md`)**: the original `_apply_weight_
gate` read `evaluate_trigger_block`'s PUBLIC result, which maps both a real `TRUE` and an
`EXCLUDED` (has_technology/has_ascension_perk/origin-ethic-civic — a player CHOICE, "presume open"
for `potential` evaluation) to `AVAILABLE` — correct for `potential`, meaningless for a weight
gate, where "presume open" has no sense and silently laundered an unresolvable condition into a
definite LOCKED for all 12 profiles. Fixed by working from the internal `_Eval` state directly, so
`EXCLUDED` gets its own branch that can only ever route to `weight-gated`. A standing assertion
(`evaluate_technology_for_profiles`, the full 12-profile call only) makes it structurally
impossible for a weight gate to produce LOCKED for all 12 profiles again — such a condition draws
no empire-type distinction by definition and belongs in `weight-gated`.

**Research path (P-12.9) treats `weight-gated` as VIABLE**, unlike `locked`/`config-gated`: the
technology remains eventually researchable, so it's a real step (like `uncertain`), never a route-
breaker. Its own `estimateReasons` member, `weight-gated-step`, is distinct from `uncertain-
availability` — a determinate fact, not an undecidable one, but the total is still an estimate
because the gate could lift.

Post-fix D-10 figures (rendered set, both metrics recomputed against the same `pipeline.
dataset_emit.build_context`): see `docs/BUILD-LOG.md` for the full reconciliation table against
this Extension's own pre-fix numbers above.

**Two completeness gaps, closed (a later session).** `pipeline.availability.COUNTRY_TYPE_NEVER_PLAYER`
(D-6/P-1's ground-fact mechanism, already used for `acot_phanon_base`) is extended with
`fallen_empire`/`awakened_fallen_empire`: the player empire is always a standard (`is_country_type
= default`) country type, user-confirmed, with `is_country_type = blokkat_stripminers` (and its
variants) deliberately excluded — a player CAN become that type mid-playthrough via the Blokkat
crisis's conversion mechanic. Real corpus: 9 technologies' zero-factor `weight_modifier` condition
(`NOR = { is_country_type = fallen_empire, is_country_type = awakened_fallen_empire }`) now
resolves on a proven fact rather than an unresolved leaf — verified to change zero technologies'
final `weight-gated` state (a ground fact is never `axis_pure`, so this can never newly produce
`locked`) — see `docs/BUILD-LOG.md` for the full accounting.

Separately, `_weight_gate_condition_blocks` gains coverage for a BARE top-level `factor = N`
directly on `weight_modifier` (Stellaris's own "always apply this factor, no condition"
shorthand) — previously invisible to this Extension entirely, since only `modifier`-keyed
sub-items were scanned. An unconditional bare `factor = 0` (24 real technologies) is folded into
the same `weight-gated` evaluation as any other zero-factor condition, represented as an empty
condition Block (never a synthesized `always = yes` leaf, which would claim a specific
acquisition route this static pipeline cannot verify for these 24 the way it could for
`tech_akx_worm_1`). `docs/BUILD-LOG.md` has the full technology-by-technology split against
`pipeline.dataset_emit.ADD_RESEARCH_OPTION_PERK_GRANTS` and the before/after per-state population.

## D-11 — Rendering stack

PixiJS over a hand-rolled WebGL renderer. Hand-rolling a 2D renderer that meets the P-10
budgets at 10³–10⁴ nodes is weeks of work that is not the interesting part of this project, and
PixiJS still permits the custom fills and shaders the crisis patterns need.

## D-12 — Pipeline language

Python, continuing from the v1 implementation. The dataset schema becomes an explicit
cross-language contract as a result — see `00-overview.md`.

## D-13 — Layout bands are declared tier, not computed position (corrects an earlier draft)

**Unchanged by D-16's row re-axis.** D-13 governs the BAND (column) axis only — declared tier,
never promoted, one deliberate repeatables exception. D-16 replaced the OTHER axis (rows, née
lanes). Every figure and rule in this section (band enumeration, the repeatables exception, the
34-edge backward decomposition figured by kind) still holds exactly as stated below — band
membership is computed purely from a node's own declared tier, which the row a node lives in has
no bearing on whatsoever. See D-16 for what did change.

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

## D-16 — Layout ROW axis is category-first/faction-first, not the crisis-faction lane (corrects an earlier draft)

**A design divergence found by showing the rendered output to the user against a v1 screenshot.**
The row axis used to be D-7's crisis-faction lane — `LANE_ORDER`: the standard-progression lane
(all non-faction technologies, sub-grouped by category only as an internal sub-grid wrap key
within a lane×band cell) plus one lane per crisis faction. The user confirmed this was never the
intent: it wastes enormous vertical space reserving a full-height row for as few as 3
(Aeternum, Katzenartig Imperium), 7 (Sirenalia), or 0 (Compound) technologies — the same vertical
weight `voidcraft` (123) or `biology` (130) gets.

**The row model now:**

- Rows are the vanilla technology categories, one row each, followed by the 5 crisis-faction rows
  — unified, NOT sub-split by category or research area the way the old Standard lane's sub-grid
  used to.
- Row assignment is **faction-first and mutually exclusive**: a technology with a crisis faction
  (D-7, unchanged) goes in that faction's row; every other technology goes in its own category's
  row.
- Columns (bands) remain declared-tier bands — **D-13 is completely unchanged**; see that
  section's own note.
- Colour and pattern move from the CARD to the ROW (superseding CLAUDE.md's old "background
  encodes research area" per-card rule — see CLAUDE.md's "Colour and pattern" section for the
  corrected rule and its "research area is not colour-encoded inside faction rows" accepted loss).

**Why the category-row set must be DERIVED, never hand-typed as "the 13 vanilla categories."**
Gigastructures defines its own technology category, `blokkats`
(`common/technology/category/giga_category.txt`), carried by exactly the 42 rendered
technologies the D-7 classifier already places in the Blokkats faction row by technology-ID
fragment — **42/42, confirmed by direct corpus survey; zero non-faction technology carries
`category = { blokkats }`.** Under faction-first placement this category has zero remaining
members once its Blokkats technologies move to the Blokkats row. A hand-typed "13 known vanilla
categories" list would either need `blokkats` manually excluded (a silent, undocumented special
case) or would emit a spurious always-empty 14th category row. `pipeline.layout._row_order`
instead derives the category-row set from whichever categories actually have a non-faction member
once faction-first assignment has run — the same "enumerate from the dataset, never hardcode"
discipline `distinct_tiers`/bands already use (P-2). This yields exactly the 13 real vanilla
category ids with no special-casing anywhere in the code for `blokkats` at all.

**Row order**: the derived categories, grouped by research area (`AREA_ORDER`:
physics → society → engineering, matching the existing area-colour convention), alphabetically by
category id within an area (each real category maps to exactly one area 1:1 in the corpus,
confirmed by direct survey — there is no real tie to break), followed by the 5 crisis-faction rows
in D-7's own fixed order (`pipeline.crisis_faction.CRISIS_FACTIONS`, reused directly rather than
re-declared, so the two orderings can never drift apart). Every faction row is always emitted —
unchanged behaviour from the old lane model, just true of a row instead of a lane now. Compound's
population was 0 (confirmed-real zero) at the time this decision was written; a later session's
crisis-faction override (`config/crisis_faction_overrides.txt`, see D-7 and CLAUDE.md's
crisis-faction section) raised it to 2. The always-emitted-row mechanism this paragraph describes
is unaffected either way.

**No vanilla category is left empty or near-empty by the faction-first move** — checked, not
assumed: the largest single departure is Sirenalia's 7 psionics technologies (41 → 34 remaining),
comfortably populated. Full per-category departure table:

| Category | Total | Faction departures | Remaining (category row) |
| --- | ---: | --- | ---: |
| blokkats | 42 | Blokkats ×42 | **0 — excluded from ROW_ORDER entirely** |
| voidcraft | 125 | Aeternum ×1, Katzenartig Imperium ×1 | 123 |
| particles | 105 | Aeternum ×1 | 104 |
| psionics | 41 | Sirenalia ×7 | 34 |
| materials | 50 | Aeternum ×1 | 49 |
| military_theory | 44 | Katzenartig Imperium ×1 | 43 |
| industry | 71 | Katzenartig Imperium ×1 | 70 |
| (remaining 7 categories) | — | none | unchanged |

**Real measured geometry, over the same 980-node/989-edge rendered corpus** (see CLAUDE.md's
"Row re-axis" bullet for the full writeup, including gutter constants and the per-row height
table): canvas grows from 12,544 × 8,146px to **12,888 × 10,708px** — width grows slightly from
widened band gutters (INTER_BAND_GUTTER 40→48px, INTRA_GAP_X 8→16px — see below), height grows
substantially because rows are now individually sized to their own content instead of being
dominated by one 925-technology Standard lane that used to absorb everyone. Densest cell moves
from Standard×T5 (253) to **voidcraft×T5 (47)** — categories are inherently smaller buckets than
"everyone who isn't crisis content," so no single cell is anywhere near as crowded as before, a
direct, intended consequence of the re-axis, not a side effect.

**Backward-edge decomposition is UNCHANGED: still 34 = 25 `prerequisite` + 2 `alternative` + 7
`potential-gate`, max span 5, re-measured against the new geometry, not assumed carried over.**
This is a necessary consequence of D-13 being untouched, not a coincidence: `backward`/`bandSpan`
are computed purely from each edge's endpoints' BAND indices (declared tier), which have no
dependency on which row a node lives in. Total edge counts are likewise unchanged (989 = 888 + 76
+ 25) — verified directly rather than assumed, since a change here would indicate a real bug
(P-14's edge extraction doesn't touch layout at all).

**Gutters, real values, one named place** (`pipeline/layout.py`): the user flagged the previous
8px/10px sibling-card gaps and the single 40px combined header+separator strip between lanes as
reading like edge-to-edge touching cards. `INTRA_GAP_X` 8→16px, `INTRA_GAP_Y` 10→16px,
`INTER_BAND_GUTTER` 40→48px, and the old single `LANE_LABEL_MARGIN` (40px, doing double duty as
both header space and the only inter-lane separation) splits into `ROW_HEADER_HEIGHT` (40px,
unchanged, the header label strip) plus a NEW `ROW_GUTTER` (24px, pure visual separation on top of
the header) — 64px total between rows now, vs. 40px before.

**Ordering-within-cell change**: the old `(category, computed_position, key)` sort key inside a
(row, band) cell drops `category` — it no longer discriminates anything, since a row is now either
a single category or a single (unsplit) faction, so every member of a cell already shares the same
category-or-faction. The key is now `(computed_position, key)`.

**JSON contract deliberately unchanged, only its content**: `lanes`/`laneId` keep their existing
names in `schema/base-dataset.schema.json` and `schema/generated/dataset-types.ts` — this session
does not rename them to `rows`/`rowId`, even though the concept has changed, because doing so
would require touching `client/`'s renderer (which reads `base.lanes`/`tech.laneId` today) beyond
the "regenerate types only" boundary this session was scoped to. `lanes` now has 18 entries instead
of 6; `lanes[].crisisFaction` is `null` for a category row exactly as it always was for the old
Standard lane. The rename is tracked as the next slice's (the renderer re-wire's) own work — see
HANDOFF.md.

## D-17 — Same-band sub-column is prerequisite depth, wrapped within its own depth slot

**The invariant.** Within a tier band, a technology must never render left of, or vertically in
line with (stacked in the same sub-column as), any of its own SAME-BAND prerequisites — a
same-band prerequisite chain must always read strictly left-to-right, never top-to-bottom in one
column. This closes a real gap: D-13 fixed bands to declared tier and explicitly demoted computed
position to an internal, never-displayed ordering signal, but nothing enforced that a same-band
prerequisite chain's own SUB-COLUMN ordering respected the dependency direction at all — before
this decision, a (row, band) cell's sub-grid wrap was a plain positional wrap (D-16's
`(computed_position, key)` sort, wrapped at a fixed N), which could and did place a prerequisite
and its dependent in the same column, or with the dependent to the LEFT of its own prerequisite,
whenever wrap arithmetic happened to land them there. **Bands remain declared tier per D-13,
completely unaffected** — D-17 only changes how a node is positioned WITHIN its own band/row cell,
never which band it's in.

**Scope: same-band only, pooled across rows, not per-row.** A technology's same-band prerequisites
are exactly the members of `prereqs_of[key]` whose own band index equals its band index — a
prerequisite in an earlier or later band imposes no ordering constraint here at all (D-17 doesn't
touch cross-band edges; those are P-8's backward-edge routing, unchanged). Depth is computed
POOLED across every row sharing a band, not separately per row: `same_band_depth[key]` is the
longest same-band-prerequisite-chain length ending at `key`, via a topological sort over the
same-band-only edge subgraph (`pipeline.layout._same_band_depth`), the same Kahn's-algorithm
machinery `_computed_position` already used for the full graph. This has to be pooled, not
per-row, because a same-band prerequisite edge can and does cross row boundaries (a category
technology can be a same-band prerequisite of a faction technology, or vice versa) and every row
sharing a band shares the same column x-positions — column N means the same thing in every row of
that band, so the depth (and therefore column) assignment has to be computed over the whole band,
not reset per row. The real corpus survey found **zero same-band cycles** anywhere (checked via
topological sort over the same-band-only subgraph directly, not assumed) — the invariant is
satisfiable everywhere in the current corpus. A future same-band cycle is a hard build failure
(`LayoutCycleError`, from the same `_topological_order` machinery every other DAG check in this
pipeline already uses), never silently ignored or broken by dropping an edge.

**Depth sets a MINIMUM sub-column, not the sub-column itself — a depth is a SLOT of one or more
sub-columns, wrapped at `subgrid_width`.** The first implementation of this decision used
`same_band_depth[key]` directly as the sub-column index, with every node sharing a depth stacked
in ONE column via an unbounded per-(row, band, depth) counter — this is a distinct, later-caught
bug, not part of the decision itself; see "The unbounded-stacking bug" below. The corrected
mechanism: for each `(band, depth)` pair, `depth_slot_width` is `ceil(count / subgrid_width)`,
where `count` is the largest number of members any single row sharing that band has at that depth
— members WRAP at `subgrid_width` (4) rows per sub-column, spilling into additional sub-columns
within their own depth's slot exactly like D-16's plain wrap-at-N did for an undifferentiated
cell. `depth_slot_start[(band, depth)]` is the cumulative sum of every shallower depth's own slot
width in that band, so a deeper depth's sub-columns never overlap a shallower depth's. **The
invariant holds under wrapping exactly as it did without it**: a dependent's same-band depth is
strictly greater than its prerequisite's, so its slot start is `>= prerequisite's slot start +
prerequisite's full slot width` — strictly past every sub-column the prerequisite's depth could
ever use, regardless of how many sub-columns that depth's own population needed.

**The unbounded-stacking bug, found and fixed in a follow-up session, with the reconciliation
recorded here rather than silently folded into "how D-17 always worked."** The first
implementation of the depth-slot mechanism above skipped the wrap step: `compute_layout` set
`col = same_band_depth[key]` directly, and every member sharing a `(row, band, depth)` triple was
stacked via a plain incrementing counter with no cap. The real corpus's worst cell (Blokkats ×
band 5 × depth 0 — 37 mutually-unrelated Blokkats technologies, all at depth 0 since none has a
same-band prerequisite) rendered as a single column **37 sub-grid rows tall**. Canvas height moved
from the pre-D-17 figure of 12,520px to **30,152px** (+141%) — a change nothing had predicted:
the pre-implementation survey (see CLAUDE.md's Item-3 writeup) costed D-17 as a WIDTH change only
(+11.6%, from widening bands to fit same-band chain length), and the width prediction landed
almost exactly (18,750px measured vs. ~18,750px-15,806px predicted range) — but the height effect
was a real, unaccounted-for regression, caught only because canvas dimensions are asserted
directly in `tests/test_layout_corpus.py` and a fresh session cross-checked the reported numbers
against a clean re-run rather than accepting them.

**This is a THIRD instance of this project's "a green test suite proves self-consistency, not
correctness" pattern** (CLAUDE.md documents two prior instances under this same framing:
`pipeline.layout.is_repeatable`'s `levels < 0` predicate, and `_resolve_loc_tokens`'s
sibling-token bug), but a distinct variant within that pattern worth naming precisely: the two
prior instances were tests with narrow fixture coverage that never exercised the path where the
bug lived. This one is different and arguably worse — `tests/test_layout.py` had a test,
`test_unrelated_same_band_nodes_stack_in_one_column`, whose name and body **asserted the
unbounded-stacking behaviour as the intended design**, with a comment explicitly framing it as
D-17's own correct behaviour ("10 mutually unrelated technologies... all land in column 0, stacked
across 10 sub-grid rows"). The suite wasn't just narrow here; it actively enshrined the defect as
spec. Renamed to `test_unrelated_same_band_nodes_wrap_within_their_depth_slot`, asserting the
corrected wrap behaviour (10 unrelated depth-0 nodes → 3 sub-columns of at most 4 each), with the
history recorded in the test's own comment.

**Real measured canvas, before D-17 existed, immediately after its first (buggy) implementation,
and after the wrap-within-depth correction — all over the same 980-node/989-edge rendered corpus:**

| State | Canvas | Notes |
| --- | --- | --- |
| Pre-D-17 (D-16 + spacing passes only) | 16,800 × 12,520px | Baseline the Item-3 survey costed its width prediction against. |
| D-17, first implementation (unbounded stack) | 18,750 × 30,152px | Width matches the survey's prediction almost exactly (+11.6%). Height (+141%) unpredicted and unreconciled — the stacking bug. |
| D-17, wrap-within-depth correction | 30,840 × 9,736px | Height drops far below even the pre-D-17 figure, confirming the stacking bug (not D-17 itself) drove the height. Width grows well past the survey's prediction. |

**The wrap-within-depth correction's width cost is real and larger than the original survey
anticipated, for a reason worth stating precisely.** The Item-3 survey modelled column count as
one column per depth LEVEL (i.e., same-band prerequisite CHAIN LENGTH only) and never considered
that a depth level's own POPULATION would also need width once vertical stacking is capped at
`subgrid_width`. Because same-band depth is pooled across rows and every row sharing a band must
use the same column x-positions for a given depth, one row's population-heavy depth (Blokkats' 37
at depth 0) reserves wrap-driven width that every OTHER row sharing that band inherits too, even
though most other rows don't need anywhere near that many sub-columns at that depth. This is the
direct, examined cost of choosing wrap-within-depth over the alternative (accepting unbounded
height) — not a rule chosen to hit a specific width or height number. `subgrid_width` (4) itself
predates D-17 entirely and was never re-evaluated against this new cost; see CLAUDE.md's Item-2
writeup for the wider trade-off survey across `subgrid_width` = 4/6/8/12, left as an open decision
for the user to pick from.

**Card arrangement's `(computed_position, key)` sort (D-16, `spec/P-02-layout.md`) is now
`(same_band_depth, computed_position, key)`** — `same_band_depth` is the primary sort key
(determines the sub-column-slot boundary), `computed_position` (the full-graph longest-path depth)
only a tie-breaker for ordering WITHIN a shared depth slot, and `key` a final deterministic
tie-breaker. `category` was already dropped from this key under D-16 (a cell's members already
share one row by construction) and stays dropped — unaffected by D-17.

Tests: `tests/test_layout.py`'s "Sub-grid arrangement within a band" section (the renamed
wrap-within-depth test above, plus `test_same_band_ordering_invariant_widens_the_band`,
`test_same_band_ordering_invariant_ignores_cross_band_prerequisites`, unaffected by the
correction since neither exercises more than one member per depth);
`tests/test_layout_corpus.py::test_densest_actual_row_band_cell_and_canvas_dimensions` (the real
corpus canvas-dimension assertion, now pointing at the corrected 30,840 × 9,736 figure, with the
full before/first-implementation/corrected history recorded in the test's own comment).

### `subgrid_width` trade-off survey (reconciliation session, SURVEYED — value NOT changed)

`subgrid_width` (4) predates D-17 entirely (it was the plain wrap-at-N constant D-16 already
used) and was never re-evaluated once D-17's wrap-within-depth correction made canvas aspect
ratio a direct function of it: a larger `subgrid_width` lets one sub-column hold more stacked
cards before spilling into a new column, trading BAND WIDTH for ROW HEIGHT. Measured directly
over the real 980-node/989-edge corpus, `compute_layout(..., subgrid_width=N)` for N in
{4, 6, 8, 12}, holding every other constant fixed:

| `subgrid_width` | Canvas (W × H) | Aspect ratio | Worst band width (px, band 5 / Tier 6 throughout) | Worst row height (px) |
| ---: | --- | ---: | ---: | ---: |
| 4 (current) | 30,840 × 9,736 | 3.17:1 | 8,460 | 440 (`industry`) |
| 6 | 29,670 × 13,448 | 2.21:1 | 5,730 | 672 (`industry`) |
| 8 | 35,910 × 17,160 | 2.09:1 | 4,950 | 904 (`industry`) |
| 12 | 51,120 × 23,424 | 2.18:1 | 4,170 | 1,368 (`statecraft`) |

**Canvas width is non-monotonic in `subgrid_width`** (30,840 → 29,670 → 35,910 → 51,120): width
initially drops from 4→6 as fewer sub-columns are needed per depth slot, then rises again at 8
and 12 as the growing per-column card count starts requiring MORE bands to widen for their own
longest same-band chains (a longer same-band chain now needs proportionally more vertical room
per depth level too, which doesn't reduce column count the way spreading out unrelated same-depth
technologies does). Row height rises monotonically and by a wide margin (440px → 1,368px, 3.1×)
since a taller column is exactly what a larger `subgrid_width` buys. **None of the four risks any
WebGL texture-size or coordinate-precision limit**: nothing in `client/src/main.ts` renders to an
offscreen `RenderTexture` sized to the canvas (checked directly — no `RenderTexture`/
`generateTexture` call exists in the client at all), so canvas pixel dimensions never need to fit
inside a GPU's max-texture-size limit (typically 8,192–16,384px on real hardware) in the first
place; world coordinates are ordinary vertex-attribute floats under PixiJS's camera transform, and
even the largest figure here (51,120px) is far below float32's ~16.7M (2²⁴) exact-integer
threshold, so no precision loss either. **No value was changed by this survey** — the four rows
above are for the user to pick from.

### `subgrid_width` decision: 6, chosen

The user picked **6** from the four-row survey above. Stated reasoning, recorded here rather than
re-derived: 6 is the only value that REDUCES canvas width relative to 4 (29,670px vs. 30,840px)
while ALSO fixing the aspect ratio (2.21:1 vs. 3.17:1) — every other value trades one for the
other, never both. It cuts worst-case band width from 8,460px to 5,730px, the figure that governs
how far a user must pan to cross a single tier band, which is the more directly felt cost of a
wide canvas than total area. 8 buys negligible further aspect improvement (2.09:1, barely better
than 6's 2.21:1) for roughly double the canvas area; 12 is WORSE on aspect than 6 (2.18:1) while
quadrupling area. `pipeline.layout.DEFAULT_SUBGRID_WIDTH` and `client/src/main.ts`'s mirrored
`SUBGRID_WIDTH` constant are both set to 6.

**Real measured figures, over the same 977-node/984-edge D-18 corpus — the survey's own numbers
were projections; these are the actual re-run values, confirmed to match exactly**:

| Figure | Value |
| --- | --- |
| Canvas | 29,670 × 13,448px |
| Aspect ratio | 2.21:1 |
| Worst band width | 5,730px (band index 5, Tier 6) |
| Worst row height | 672px (`industry` row) |
| Densest (row, band) cell | `voidcraft`×T5 = 47 (unaffected — `subgrid_width` never changes cell membership, only geometry) |
| Row population | unaffected — identical to the `subgrid_width=4` distribution, since row/band membership doesn't depend on this constant |

Every test pinning a `subgrid_width=4`-era canvas/band/row-height figure was updated to these
values in the same session (`tests/test_layout_corpus.py`) — see that file for the exact
assertions. Synthetic mechanism tests (`tests/test_layout.py`) pass `subgrid_width=4` explicitly
and are unaffected by this default change, deliberately, since they test the wrap mechanism
generically rather than the real corpus default.

### D-17 extended to `alternative`/`potential-gate` edges (a later session)

D-17's own invariant, as written above, was scoped to `prerequisite` edges only — a prior
session's "same-sub-column edges" survey found this was a real, narrow gap: exactly 6 real edges
(all `alternative`/`potential-gate`, zero `prerequisite`) placed a dependent in the EXACT same
`(row, band, col)` cell as its counterpart, 2 of them in the Compound row
(`tech_qnm_utilities` → `tech_qnm_disruptors`/`tech_sm_autocannons`), and recommended a per-cell
extension rather than a global `subgrid_width` renegotiation. Implemented directly (the 6-edge
blast radius was small enough to take without a further survey pass, per the user's own framing):
`pipeline.layout._same_band_depth` gained an `extra_same_band_edges` parameter, fed from the SAME
`alternative`/`potential-gate` edges `compute_layout` already extracts for the emitted edge list
(`compute_typed_edges`, moved earlier in `compute_layout` so both consumers share one call) —
merged into the same-band topological sort as an ADDITIONAL ordering constraint alongside
`prereqs_of`, but deliberately NOT folded into `prereqs_of`/`computed_position` themselves, which
stay prerequisite-only exactly as D-17 originally defined them.

**Real measured effect, same 973-node/977-edge D-18/Item-2c corpus**: canvas 29,670 × 13,448px →
**30,060 × 13,332px** (width +390px, +1.3%; height unaffected — no affected cell's wrap-driven
column growth crossed a `subgrid_width`-row boundary that would add a new row of height). Well
under the "stop and report before committing past ~10% width growth" threshold the user set for
this change, so no further sign-off was sought. Densest (row, band) cell and row population are
unaffected (this extension never changes cell membership, only intra-cell column assignment).
Zero same-band cycles introduced by combining the three edge kinds into one topological sort
(checked directly — a hypothetical cycle here is the same hard `LayoutCycleError` failure D-17's
original prerequisite-only sort already guarantees, never silently dropped).

Test: `tests/test_layout_corpus.py::test_zero_same_sub_column_pairs_across_all_edge_kinds` asserts
zero same-band `(from, to)` pairs across ALL THREE edge kinds where `to`'s column fails to exceed
`from`'s — proven capable of failing first (24 violations against the pre-extension code, a
superset of the originally-surveyed 6 since it also catches the reversed-ordering case the survey
didn't separately count) before being trusted on the corrected code.

## D-18 — ACOT/AoT rendering-scope closure is depth-1, not a full transitive closure (corrects an earlier draft)

**Superseded rule.** `pipeline.rendering_scope.compute_rendering_scope` originally computed a full
transitive closure: starting from every unconditionally-rendered (vanilla/Gigastructures)
technology's own `prerequisites`, it recursed through ACOT/AoT technologies indefinitely, on the
stated reasoning that "a rendered technology's prerequisite chain is never broken by an invisible
gap" (CLAUDE.md's original "Scope of ACOT and AoT" wording). Real corpus measurement: 7 ACOT/AoT
technologies in the closure, max depth 2.

**The report that changed it.** The user reported a specific over-inclusion: "Precursor Databank
Construction still shows, shouldn't — it's a direct prereq for Alpha Reactors (which are a prereq
for alpha tier tensile buildings), but in the case of the ACOT tensile techs, if the tech doesn't
appear in the prereq block, it doesn't need to show." Verified directly against the real corpus,
not assumed: `tech_dark_matter_power_core_ae` ("Alpha-class Enigmatic Power") is named directly in
a rendered Gigastructures technology's own `prerequisites` — depth 1. Its own prerequisite,
`tech_precursor_design` ("Precursor Databank Analysis"), is NOT named by anything rendered — it's
only reachable by first passing through `tech_dark_matter_power_core_ae`, i.e. depth 2. The user's
complaint is exactly this: a technology should render only when something ACTUALLY RENDERED names
it, not when it merely sits somewhere in an eventually-reachable chain.

**Depth-1, adopted.** `compute_rendering_scope` now performs a single pass: an ACOT/AoT technology
renders iff a rendered (vanilla/Gigastructures) technology names it directly in its own
`prerequisites` block. No recursion — the technology at that single hop is never itself treated as
a new frontier to expand from. Real corpus: closure narrows from 7 to 4 members
(`tech_dark_matter_power_core_ae/dm/se`, `tech_civil_phanon_application` — all 4 directly
referenced by a real Gigastructures "supertensile alternate" technology, per
`giga_17_alternative_mega_build.txt`). The 3 dropped members
(`tech_dark_matter_power_core_enig`, `tech_mine_dark_energy`, `tech_precursor_design`) were always
the depth-2 members of the old closure.

**Two options considered and rejected before adopting depth-1 as stated:**
- **Keep the full transitive closure.** Rejected: this is exactly the reported defect, not a
  matter of taste — a technology two hops removed from anything rendered has no business
  appearing, per the user's own framing of what "needs to show."
- **A middle option: render an out-of-closure prerequisite as a distinct stub/ghost node**, so a
  rendered ACOT technology's chain still LOOKS complete without pulling in the full depth-2+
  subtree. Surveyed and rejected as disproportionate: the real cost of depth-1 is exactly 3 links
  (below), not a systemic gap — building a whole new node kind, schema field, and rendering
  treatment to paper over 3 links is more machinery than the problem warrants. If a future corpus
  refresh makes the off-tree-link count materially larger, this option should be reconsidered
  against the real cost at that time, not dismissed permanently on today's number.

**The accepted cost, exact and named** (`pipeline.rendering_scope.compute_off_tree_prerequisites`,
pinned by `tests/test_rendering_scope.py::
test_depth_one_closure_off_tree_links_match_the_accepted_set`): exactly 3 off-tree prerequisite
links, all ACOT→ACOT —

| Rendered technology (renders, depth 1) | Names as a prerequisite (does NOT render, depth 2) |
| --- | --- |
| `tech_dark_matter_power_core_ae` ("Alpha-class Enigmatic Power") | `tech_precursor_design` ("Precursor Databank Analysis") |
| `tech_dark_matter_power_core_dm` ("Delta-class Enigmatic Power") | `tech_dark_matter_power_core_enig` |
| `tech_dark_matter_power_core_dm` ("Delta-class Enigmatic Power") | `tech_mine_dark_energy` |

Each of these 3 rendered technologies' own card will name a prerequisite with no corresponding
node in the tree. This is the accepted, understood cost of depth-1 — not an oversight. A future
corpus refresh that creates a 4th such link (or removes one of these 3) fails the pinning test
loudly, per the user's explicit instruction, rather than silently degrading (or over-restoring)
chain completeness.

**Real measured effect on the rendered dataset, over the same corpus**:

| Figure | Before (full closure) | After (depth-1) |
| --- | ---: | ---: |
| Rendered technology count | 980 | 977 |
| Total edges | 989 | 984 |
| `prerequisite` edges | 888 | 883 |
| `alternative` edges | 76 | 76 (unaffected) |
| `potential-gate` edges | 25 | 25 (unaffected) |
| Canvas dimensions | 30,840 × 9,736px | 30,840 × 9,736px (unaffected) |
| Densest (row, band) cell | `voidcraft`×T5 = 47 | `voidcraft`×T5 = 47 (unaffected) |
| `computing` row | 83 | 82 |
| `field_manipulation` row | 82 | 81 |
| `particles` row | 95 | 94 |
| Standard (non-faction) population | 903 | 900 |

The 5 edges removed are the `prerequisite` edges that touched the 3 dropped technologies (both
their own outbound prerequisites and any inbound edges from other rendered technologies —
`alternative`/`potential-gate` are unaffected since none of the 3 participated in an OR-group or a
`potential`-gate relationship). Canvas dimensions and the densest cell are unaffected because none
of the 3 dropped technologies was in `voidcraft`×T5 or drove that band's/row's own extent. Exactly
1 technology drops from each of `computing`, `field_manipulation` and `particles` — confirmed
directly, not assumed uniform.

`PLACEHOLDER_TECHNOLOGIES_REQUIRING_ACOT_AOT` (`pipeline/dataset_emit.py`, the maintained
constant reporting which technologies disappear from a build missing ACOT/AoT) narrows from 7 to
4 members for a related but distinct reason: the 3 dropped-under-D-18 technologies are no longer
rendered AT ALL, with or without ACOT/AoT loaded, so there is no "placeholder absent without
ACOT/AoT" transition left to report for them. Real corpus check: the reduced-build (no ACOT/AoT)
rendered-node count remains 977 — the SAME digits as the new full-build count, confirmed to be
genuine coincidence (977 - 4 remaining placeholders + 4 vanilla-overwrite reversions = 977), not
evidence the two builds are otherwise equivalent.

Tests: `tests/test_rendering_scope.py` (synthetic depth-1 mechanism test, the real-corpus 4-member
closure and 977-node total, and the 3-link off-tree-prerequisite pin), plus every corpus test
across `tests/test_dataset_emit.py`, `tests/test_layout_corpus.py`, `tests/test_crisis_faction_corpus.py`,
`tests/test_availability_corpus.py`, `tests/icons/test_icon_corpus.py` and `tests/test_build_dataset.py`
re-verified against the real 977-node/984-edge closure.
