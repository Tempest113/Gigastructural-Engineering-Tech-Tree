# Parser fixtures

**Most of this directory is gitignored and not committed.** Fixtures copied or excerpted from
`vendor/` (Stellaris and Steam Workshop mod source) are verbatim third-party content and cannot
be redistributed in a public repository — the same constraint that keeps `vendor/` itself out of
git. What's committed instead is `manifest.json`: for every such fixture, its source path
relative to `vendor/`, whether it's a whole file or which lines it excerpts, and a sha256 of its
exact bytes. Run `python tools/regenerate_fixtures.py` (with a populated `vendor/`, per
`CLAUDE.md`'s "Source data") to reproduce the actual files locally; it fails loudly, rather than
writing anything, if `vendor/` is missing or if a source file's content no longer matches the
hash recorded when the fixture was captured. `malformed/`, `encoding/` and `variables/` are
hand-authored, not vendor-derived, carry no third-party content, and are committed directly —
the script doesn't touch them.

Real files copied from `vendor/`, selected to exercise the hard cases called out in `CLAUDE.md`
and `spec/`: inline script expansion, scripted-variable references, duplicate keys, deeply nested
`OR`/`AND`/`NOT`/`NOR` in `potential`/`weight_modifier` blocks, comparison operators other than
`=`, scripted triggers, mod-over-mod and mod-over-vanilla overwrites, ACOT/AoT ancestor closure,
encoding edge cases, malformed input, and localisation parsing. No fixture has been trimmed or
edited unless explicitly marked **excerpt** below — line numbers cited for whole-file fixtures
match the source files exactly, so a failing test can be traced straight back to `vendor/`.
Excerpted files are exact contiguous (or, where stated, spliced) slices of the source, never
paraphrased or reformatted; each excerpt note gives the precise source line range so it can be
re-derived from `vendor/` if it ever needs to be regenerated or extended.

Deliberately excluded: the three largest tech files (`00_soc_tech.txt` at 7093 lines,
`00_eng_tech.txt` at 3844, `00_phys_tech.txt` at 2980) and `00_biogenesis_tech.txt` (2661). See
**Verification: excluded large files**, below, for what was checked before relying on that claim.

Every technology file in this set uses `@scripted_variable` references and at least one form of
`inline_script`, since those two are pervasive in both source trees — they aren't called out
per-file below unless a file demonstrates an unusual *form* of one. Those references used to be
dangling (resolvable only against gitignored `vendor/`, which CI does not have); the
**Dependency closure** section below closes that gap.

## `gigastructures/`

- **`giga_01_physics.txt`** — largest single Gigastructures tech file (1133 lines). Broad-coverage
  stress case: mixes `@var` cost/weight expressions, `inline_script` in both bare-path and
  parameterised form, and numerous `OR`/`NOT` blocks across ~90 technologies. Good smoke-test file
  for "does the parser survive a large real file end to end" before drilling into narrower cases.

- **`giga_02_society.txt`** (787 lines) — added alongside the scripted-triggers fixtures below.
  `giga_tech_orbital_elysium`'s `potential` block (~line 58) calls the scripted trigger
  `giga_can_use_habitables = yes` as a flat member alongside `NOT = { has_global_flag = ... }` and
  `is_nomadic = no` — a scripted-trigger call **directly** inside `potential`, un-nested. Pairs
  with `giga_03_engineering.txt` below, which calls the same trigger family but nested inside
  `OR`. Also pairs with `localisation/gigastructures/giga_l_english_excerpt.yml` for this same
  technology's display strings.

- **`giga_03_engineering.txt`** — has the same `inline_script` line both active (line 72, 135,
  170, 205 — `technology/tech_weight_boni/exploitative_tech_weight_bonus`) and commented out
  (lines 105–106, a different variant left disabled). Tests that the parser preserves comments
  verbatim and does not mistake a commented-out directive for a live one. **Also** the primary
  scripted-trigger fixture: `giga_tech_equatorial_shipyard`'s `potential` (~line 268) calls
  `is_giga_one_planet_origin = yes` **nested inside an `OR`** alongside `NOT = { has_global_flag =
  shipyard_disabled }`; `giga_tech_ringworld_titanic_2` (~line 526) repeats the same nested shape.
  `is_giga_one_planet_origin` is itself a scripted trigger that calls a second scripted trigger
  (`giga_has_frameworld_origin`) in its own definition — see `common/scripted_triggers/` below for
  the full two-level chain this file depends on. Line ~536 also calls the *vanilla* scripted
  trigger `has_galactic_wonders = yes`, a Gigastructures technology depending on a base-game
  trigger macro, not just its own.

- **`giga_04_repeatables.txt`** — small (55 lines), high signal-to-noise. Line 10: `levels = -1`
  (infinite repeatable — spec's `Repeatable: ∞`). Line 39: `levels = 40` (finite — spec's
  `Repeatable: ×40`, P-12.2's exact example). Both also carry `cost_per_level = @var`. Use this as
  the baseline repeatable-field fixture.

- **`giga_06_special_project_tech.txt`** — `count >= 3/4/5` comparisons (lines 294, 331, 368)
  inside nested trigger scopes, plus `inline_script` and `OR`/`NOT`. Mid-sized (379 lines).

- **`giga_09_ehof_other.txt`** — the single best file for combined duplicate-key +
  nesting + inline_script coverage. `tech_abstract_1`'s `weight_modifier` (~line 24) has *eleven*
  duplicate `modifier = { ... }` keys in one block, one of which contains a 4-way `NOR`
  (leader-trait exclusion), followed by a parameterised `inline_script` in the same block. Also
  has bare comparisons (`years_passed < 10`, `years_passed > 20/30/40`). This is the file to reach
  for first when testing duplicate-key list preservation.

- **`giga_10_katzen.txt`** — small (82 lines) crisis-faction file. Two adjacent technologies
  (`giga_tech_kaiser_moon`, `giga_tech_stellarite_kaiser_moon`) share an identical `potential`
  block gated on a single country flag — a minimal, easy-to-diff case for trigger extraction
  before moving to the harder files.

- **`giga_11_aeternum.txt`** — smallest fixture (47 lines). `giga_tech_aeternite_weaponry`'s
  `potential = { always = no }` is a permanently-unreachable technology: the trigger evaluator
  must resolve this to `false` unconditionally, never `unknown`, regardless of empire profile.
  Cheap regression test for that specific evaluator rule.

- **`giga_12_asteroid_artillery.txt`** — the identical bare-path `inline_script` line
  (`technology/tech_weight_boni/defensive_tech_weight_bonus`) appears five times across five
  different technologies (lines 38, 64, 91, 118, 145). Not a duplicate-key case (different
  blocks), but a good check that inline-script expansion is applied independently per occurrence
  rather than cached/deduplicated incorrectly.

- **`giga_15_maginot.txt`** — `NOR` nested inside a `modifier` block (line 52) checking four
  tradition-completion facts, with an inline comment breaking up the list (line 56). Also uses
  `inline_script`. Mid-sized (200 lines).

- **`giga_17_alternative_mega_build.txt`** — heaviest use of comparison operators and
  `check_variable` in the Gigastructures set: `count > 0` (line 22) inside a `limit` sub-block,
  three `check_variable = { which = ... value > 0 }` triggers back to back (lines 35–38), and a
  bare `pop_amount > 5000` (line 171). Good file for testing that comparison operators parse
  correctly both as bare trigger lines and as fields inside a nested trigger object. **Also** the
  P-16 ancestor-closure fixture: `giga_tech_amb_supertensiles_acot_delta`,
  `_acot_alpha`, `_acot_phanon` and `_acot_sigma` (lines 196–296, to end of file) are Gigastructures placeholder
  technologies whose `prerequisites` chain through `tech_dark_matter_power_core_dm`,
  `tech_dark_matter_power_core_ae`, `tech_civil_phanon_application` and
  `tech_dark_matter_power_core_se` — real ACOT/AoT technologies, provided as fixtures under
  `acot/` and `aot/` below. This is the exact background case P-16 names ("the ACOT-tier
  supertensile materials"): the ancestor-closure computation must reach into `acot/`/`aot/` to
  keep this file's prerequisite chains from having an invisible gap.

- **`giga_19_nomad.txt`** — smallest whole-technology-set fixture (36 lines) with `inline_script`
  and nomadic-specific triggers. Useful as a "does the pipeline even run" fixture before throwing
  the bigger files at it.

- **`zz_giga_tech_overwrites.txt`** — the load-bearing fixture for P-15 (mod-over-vanilla
  overwrite accounting). Redefines `tech_ring_world` (line 4), which vanilla also defines
  (`stellaris/00_megastructures.txt` line 714) — pair these two files to test whole-key overwrite
  resolution. Within the block itself, the key `technology_swap` appears **three times** (lines
  16, 38, 54) with different `name`/`trigger`/`category` payloads each time — the clearest
  same-block duplicate-key case in either source tree. Also mixes `@var` costs and both
  bare-path and structured `inline_script`. The `trigger = { giga_can_use_habitables = yes }` /
  `= no` calls (lines 22, 44, 60) are further scripted-trigger uses, resolved by the same
  `common/scripted_triggers/ehof_triggers.txt` excerpt as `giga_03_engineering.txt`. Pairs with
  `localisation/gigastructures/giga_tech_overwrites_l_english.yml` for this technology's display
  strings.

## `stellaris/`

- **`000_documentation.txt`** — the vanilla format's own documentation, written entirely as
  commented-out example script (every line prefixed `#`). Adversarial in a specific way: a naive
  "strip lines starting with `#`" pre-pass would reduce this file to nothing, while a real
  tokeniser must still lex it as valid (if entirely commented) Clausewitz syntax. Also doubles as
  a readable reference for field names the extractor needs to recognise.

- **`00_megastructures.txt`** — vanilla counterpart to the overwrite fixture above; defines
  `tech_ring_world` at line 714 with a *different* `potential` block than the mod's overwrite,
  so a correct build must show the mod's version winning, not a merge of both. Separately, the
  file has 85 occurrences of the `modifier` key across its `weight_modifier` blocks (heavy
  duplicate-key load), six-step repeated `count >= 1..6` comparison ladders (lines 51–195), and
  nested `OR` blocks under `tech_mega_shipyard`'s weight modifiers (~line 762) checking
  council-leader traits.

- **`00_strategic_resources_tech.txt`** — deepest boolean nesting found in either tree.
  `tech_mine_dark_matter`'s `weight_modifier` (line ~545) is a `NOR` containing, among its
  members, an `AND` (line 550) and a second `AND` nested inside an `any_relation` scope (line
  560) — four levels of scope + boolean nesting in one block. `tech_nanite_transmutation`
  (~line 594) repeats the same `OR`-inside-`any_owned_nonprimary_starbase` shape. Also has
  `amount > 0` comparisons and a `technology_swap` block. The single hardest file to get right.

- **`00_apocalypse_tech.txt`** — `OR` containing a `NOT` (`OR = { is_spiritualist = no NOT = {
  has_psionic_ascension = yes } }`, line 167) — the negative-dependency case P-14 calls out
  explicitly. Also has `technology_swap`, `host_has_dlc = "Apocalypse"` (string-valued trigger,
  not boolean), and parameterised `inline_script` repeated across three colossus techs.

- **`00_cosmic_storm_tech.txt`** — `num_cosmic_storms_encountered >= 3/5` comparisons at several
  tiers (lines 49, 89, 384, 433, 490, 540), and `tech_advanced_storm_manipulation`'s `cost` block
  nests `inline_script` *inside a cost expression* rather than a `weight_modifier` — a different
  structural position for the same directive, worth checking the extractor handles it wherever it
  appears rather than only in known-good locations.

- **`00_nomads_dlc_tech.txt`** — eight separate `OR` blocks (lines 15, 52, 89, 226, 288, 347, 395,
  447) across a 781-line file, plus `NOT = { years_passed > N }` variants. Directly relevant to
  the nomadic axis of the empire profile model (P-1): several of these gate on nomadic-specific
  facts, good source material for empire-profile trigger tests.

- **`00_shroud_tech.txt`** — the deepest *structural* (non-boolean) nesting in the set: an `OR`
  containing an `AND` containing a `solar_system` scope containing a second `OR` containing an
  `AND` (lines ~106–140), each leaf comparing `opinion = { who = root value < 0 }`. Tests that
  comparison operators parse correctly when they're several scopes deep rather than a direct
  child of the trigger block — and that the `value < 0` shorthand (no explicit field name before
  the operator in that inner object) is handled.

- **`00_overlord_tech.txt`** — compact (239 lines) but dense: four `OR` blocks, two `NOR` blocks,
  a `NOT = { years_passed > 50 }`, and a `count >= 3` comparison, all within one small file. Good
  file to reach for when writing a fast unit test that shouldn't need a huge fixture.

- **`00_machine_age_tech.txt`** — newest-DLC file; uses 4-space indentation instead of the tabs
  every other fixture uses, which is worth keeping precisely because a whitespace-sensitive
  tokeniser bug would only show up here. Has `pop_amount >= 5000/10000` comparisons (lines 454,
  461) and `@var` cost expressions alongside `inline_script`.

- **`00_ancient_relics_tech.txt`** — largest fixture (996 lines). Includes a `NOR` block (line 69)
  and gives the extractor a big, thematically distinct (archaeology/anomaly techs) file to
  cross-check against the others for anything that only breaks at scale within a single file.

## Dependency closure (`gigastructures/common/`, `stellaris/common/`)

Every `@variable` and `inline_script` reference used by the technology fixtures above now
resolves inside `tests/fixtures/` itself. Paths mirror each mod's real layout below its `common/`
directory (e.g. an `inline_script = technology/tech_weight_boni/defensive_tech_weight_bonus` in a
gigastructures tech fixture resolves at
`gigastructures/common/inline_scripts/technology/tech_weight_boni/defensive_tech_weight_bonus.txt`),
so a parser fixture harness can point its include-resolver straight at
`tests/fixtures/gigastructures/common/` or `tests/fixtures/stellaris/common/` and have every
reference used above resolve. The top-level technology fixtures stay flat (not moved under
`common/technology/`) to avoid disturbing the existing set and its line-number citations.

- **`gigastructures/common/scripted_variables/giga_technology_scripted_variables.txt`** (141
  lines, whole file) — defines the `@tier1cost1`…`@tier5weight3` and `@giga_tier6*`…`@giga_tier8*`
  family used throughout every Gigastructures fixture.
- **`gigastructures/common/scripted_variables/ehof_vars.txt`** (164 lines, whole file) — defines
  the `@ehof_tier*` family used by `giga_09_ehof_other.txt`.
- **`gigastructures/common/scripted_variables/zz_giga_compat_overwrite_me.txt`** (25 lines, whole
  file) — **a scripted-*variable*-level compatibility overwrite**, distinct from the technology
  overwrite in `zz_giga_tech_overwrites.txt`. Gigastructures defines `@acot_tier6cost2` through
  `@acot_tier9cost2` here as `= 0` placeholders (plus similar zero-stubs for several other
  optional mods), so `@acot_tier*cost*` resolves to something even when ACOT isn't vendored. When
  ACOT *is* vendored, `acot/common/scripted_variables/acot_scripted_variables_tech_cost.txt`
  defines the same variable names with real values (e.g. `@acot_tier6cost2 = 80000`), and — same
  load-order rule as P-15's technology overwrites — ACOT's values win. This is the same
  whole-key-replacement resolution rule applied to scripted variables instead of technologies;
  pair these two files to test that the resolver doesn't special-case "variables" differently from
  "technologies."
- **`gigastructures/common/scripted_variables/giga_amb_variables.txt`** (260 lines, whole file) —
  line 5, `@giga_amb_flag = giga_buildcap_j`, is a scripted variable whose value is a **bare
  identifier, not a number** — the resolver must not assume every resolved variable is numeric.
  Pairs with `giga_17_alternative_mega_build.txt`'s `has_global_flag = @giga_amb_flag`, already a
  fixture: that's the reference site, this is the definition site.
- **`gigastructures/common/inline_scripts/technology/giga_ring_world_overwrite.txt`** (7 lines) —
  resolves the `inline_script` used three times in `zz_giga_tech_overwrites.txt`.
- **`gigastructures/common/inline_scripts/technology/tech_weight_boni/*.txt`** (11 files,
  30–145 lines each) — resolves every `inline_script = technology/tech_weight_boni/...` reference
  used across the Gigastructures fixtures (defensive, ecofriendly, expansionist, exploitative,
  judgemental, maniacal_or_spark, megaoriented, militarist, neighbor_spread, scientist,
  shipbuilding, spiritualist). `hive_or_genetics_tech_weight_bonus.txt` exists in `vendor/` but is
  not referenced by any current fixture, so it's omitted — add it if a fixture starts using it.
- **`stellaris/common/scripted_variables/00_scripted_variables.txt`** (650 lines, whole file) —
  defines the `@tier1cost1`…`@tier5weight3` family the vanilla fixtures use (the same names
  Gigastructures also defines its own copies of — the two mods don't share a variable namespace
  collision here because each mod's techs use its own file's definitions per normal load order).
- **`stellaris/common/inline_scripts/technologies/{cosmic_storms_technologies_cost_modifiers,
  cosmic_storms_technologies_weight_modifiers, rare_technologies_weight_modifiers}.txt`** — resolve
  the `script = technologies/...` references in `00_cosmic_storm_tech.txt` and the
  `rare_technologies_weight_modifiers` script used throughout the Gigastructures fixtures (yes,
  Gigastructures technologies call a *vanilla* inline script — cross-mod inline-script reference,
  same load-order resolution question as everything else).
- **`stellaris/common/inline_scripts/ai/weapon_preference_weight.txt`** (10 lines) — resolves a
  reference in `giga_01_physics.txt`.
- **`stellaris/common/inline_scripts/buildings/regular_empire_capital_jobs.txt`** (whole file) —
  its own first statement is `inline_script = { script = "jobs/politician_add" AMOUNT =
  $AMOUNT$ }` — a real, shipped example of a **quoted** structured `script = "..."` path. Before
  the fix this resolved against the literal quoted string (including the `"` characters) as the
  lookup key, which can never match any entry in the script table, so a script that genuinely
  exists always raised `UnresolvedScriptError`. Not reachable from
  technology/scripted_variables/scripted_triggers/ascension_perks in the current corpus (nothing
  under those directories invokes `buildings/regular_empire_capital_jobs`), so it sits outside
  the Stage 1 rescoping — kept as a fixture anyway because `_extract_invocation`'s quote-handling
  is shared code, not specific to any one reachability slice, and this is the only confirmed real
  instance of the quoted-structured-path shape found by raw-text survey.
- **`stellaris/common/inline_scripts/jobs/politician_add.txt`** (whole file) — the target of the
  above, referenced by its unquoted relative path `jobs/politician_add`.
- **`stellaris/00_leviathans_tech.txt`** (excerpt, source lines 1–30) — `tech_dragon_armor`'s
  `ai_weight = { inline_script = "ai/armor_preference_weight" }`: the **bare** form
  (`inline_script = path`, no block) with the path quoted — a StringLiteral value rather than an
  Identifier. Distinct from the structured-form quoting above. Confirmed real and common: 45
  instances across 6 vanilla technology files (`00_ancient_relics_tech.txt` ×16,
  `00_eng_tech.txt` ×18, `00_fallen_empire_tech.txt` ×1, `00_leviathans_tech.txt` ×1,
  `00_phys_tech.txt` ×7, `00_soc_tech.txt` ×2), all inside `ai_weight` blocks, all resolving to
  one of five trivial ai-preference/archaeotech-weight helper scripts that the corpus elsewhere
  invokes unquoted with the ordinary bare form — quoting here looks like a stylistic choice by
  whoever wrote these particular files, not a distinct feature.
- **`stellaris/common/inline_scripts/ai/armor_preference_weight.txt`** (whole file) — the target
  of the above, referenced by its unquoted relative path `ai/armor_preference_weight`.

## Scripted triggers (`*/common/scripted_triggers/`)

The highest-risk path for the D-10 `unknown` rate, per `00-overview.md`: unresolved scripted
trigger calls are the main source of spurious `unknown`. All excerpts below are exact contiguous
line ranges from their source file (cited), not reformatted.

- **`gigastructures/common/scripted_triggers/ehof_triggers.txt`** (excerpt, source lines 1–108) —
  defines `ehof_default_country`, `is_giga_one_planet_origin` and `giga_can_use_habitables`.
  `giga_can_use_habitables` is a `nor` block whose second member is
  `is_giga_one_planet_origin = yes` — **a scripted trigger calling another scripted trigger**,
  nested inside a boolean block, inside a third scripted trigger's own definition. Called from
  `potential` in `giga_02_society.txt` (flat) and, nested inside `OR`, in
  `giga_03_engineering.txt`; called from a `technology_swap.trigger` block (not `potential`) in
  `zz_giga_tech_overwrites.txt`. The excerpt was extended to line 108 to also cover
  `has_star_flag = ehof_megastructure_system@root` and
  `has_star_flag = empire_has_visited@root` — real instances of the `identifier@scope` flag
  idiom (a flag name suffixed, with no space, by a scope reference such as `@root`, `@from`,
  `@this`, `@owner`, `@prevprevprev`, or `@event_target:name`). Confirmed via raw grep across
  the rescoped corpus (technology/scripted_variables/scripted_triggers/ascension_perks +
  reachable inline_scripts/) that the no-dot form (`flag@root`, `flag@owner`, etc.) is real and
  common; the dotted-chain form (`flag@root.owner`, `flag@from.owner`) initially still failed to
  parse after this fix alone, since a bare `.` elsewhere in the grammar (e.g. the `id = bio.1`
  event-id idiom) was a separate gap at the time. Both `.` idioms below were subsequently fixed
  when `common/ascension_perks/` turned out to depend on them (see next two entries), and the
  tokeniser change ended up covering `flag@root.owner` too, as a natural consequence of the two
  fixes composing (the `@`-suffix scan appends `root`, then the general dotted-chain scan
  extends it with `.owner`).
- **`gigastructures/common/scripted_triggers/giga_frameworld_triggers.txt`** (excerpt, source
  lines 1–6) — defines `giga_is_frame_world` and `giga_has_frameworld_origin`, the second of
  which `is_giga_one_planet_origin` (above) calls — the second link in that two-level chain.
  (Originally captured as lines 1–5, cutting `giga_has_frameworld_origin`'s closing brace off
  the end — caught by `test_every_valid_fixture_parses_without_error` when the parser was
  built; corrected in the manifest and regenerated.)
- **`gigastructures/common/scripted_triggers/giga_megastructure_type_triggers.txt`** (excerpt,
  source lines 964–975) — defines `giga_is_wrecked_ship`, called from a `limit` sub-block in
  `giga_17_alternative_mega_build.txt` line 22 (not `potential`, but the same resolution
  mechanism).
- **`stellaris/common/scripted_triggers/00_scripted_triggers.txt`** (excerpt, source lines
  2532–2539) — defines the vanilla scripted trigger `has_galactic_wonders`, an `OR` over four
  `has_ascension_perk` checks, called from `potential` in `giga_03_engineering.txt` line ~536.
  Directly relevant to P-3 gate detection: a technology's gate condition can arrive already
  wrapped in a scripted trigger rather than a bare `has_ascension_perk` check in the tech file
  itself, so gate-pattern matching that only looks at literal trigger tokens in the tech file
  (without expanding scripted triggers first) will miss it.
- **`gigastructures/common/scripted_triggers/zzz_overwrites.txt`** (excerpt, source lines
  2067–2091) — `has_research_building`'s `OR` contains an `inline_script` invocation whose
  `code` parameter is a **multi-line double-quoted string**: the value opens with `"` at end of
  line, runs four more lines of ordinary-looking script (`has_building = ...`), and closes with
  a lone `"` on its own line. This is a real, shipped idiom — a whole nested
  `inline_script = { ... }` invocation passed as opaque string *data* to
  `generic_parts/giga_toggled_code`, which conditionally splices it back in — not something
  Stage 1 should try to parse as script; it's one `StringLiteral` whose `.value` happens to
  contain script-shaped text. Confirmed via `grep -rEln '="\s*$'` that 917 lines corpus-wide use
  this multi-line-string shape (concentrated in `inline_scripts/` and a handful of other
  non-technology directories — `common/technology/` and `common/scripted_variables/` are both
  clean of it). The tokeniser used to error on the first `\n` inside a string; this fixture is
  the regression test for scanning to the next unescaped `"` or EOF instead.

**Two technology files exercise a `potential`-block call**, as required: `giga_02_society.txt`
(flat, un-nested) and `giga_03_engineering.txt` (nested inside `OR`, twice). A third,
`zz_giga_tech_overwrites.txt`, calls the same trigger family from a `technology_swap.trigger`
block for contrast — same trigger name, different block context, worth checking the extractor
doesn't only look for scripted-trigger calls inside `potential`.

## Ascension perks (`*/common/ascension_perks/`)

`common/ascension_perks/` feeds P-3's gate identities, so every file in it across all four
sources must parse — no tolerance for "mostly parses." Both fixtures below were added when the
Stage 1 rescoped corpus run showed all four sources' `ascension_perks/` files failing on the
same underlying grammar gap: a bare `.` in a value position, which the tokeniser had no rule
for at all until this round.

- **`acot/common/ascension_perks/acot_ascension_perks.txt`** (whole file, 48 lines) —
  `ap_precursor_dream`'s `country_event = { id = acot_precursor_databank.8 }`: the
  namespace.number event-id idiom. Confirmed common and required in every source's
  `ascension_perks/` (2,142 distinct `namespace.number` values across `scripted_triggers/` and
  `ascension_perks/` in all four sources combined), and chainable
  (`crisis.8060.1`, `grand_archive.4105.3` — confirmed via raw grep, not just this fixture's
  single-dot case).
- **`stellaris/common/ascension_perks/00_ascension_perks.txt`** (excerpt, source lines
  2315–2368) — `ap_xeno_compatibility`'s `is_same_species = root.owner`: a scope-chain reference
  (no `@`) used directly as a plain value. This is the specific line that kept
  `00_ascension_perks.txt` failing after the event-id fix landed — the namespace.number fix
  alone (`.` followed only by a digit) doesn't cover `.owner`. 129 occurrences of this shape
  across the rescoped corpus, dominated by `from.owner` (84) and `root.owner` (24), also
  chainable (`root.owner.overlord`, 2 occurrences). One tokeniser change ended up covering both
  idioms (and, as a side effect, the deferred `flag@root.owner` case noted above under
  `ehof_triggers.txt`) — see `spec/implementation-notes.md` for the combined rule.

## Scripted-triggers grammar gaps found rescoping the run to the four required directories

The first rescoped run (see the Ascension perks section above) still had 17 parse failures
confined to `scripted_triggers/` and one `inline_scripts/` file — `scripted_triggers/` is a
required directory (unparseable triggers inflate D-10's `unknown` rate for reasons unrelated to
genuine trigger-evaluation undecidability), so these had to be chased down too, not left as an
accepted residue. All six constructs below compose with each other and with the two dotted-value
idioms above — see `spec/implementation-notes.md`'s combined identifier-grammar rule.

- **`stellaris/common/scripted_triggers/01_scripted_triggers_refugees.txt`** (excerpt, source
  lines 61–72) — `planet_has_habitability_and_housing`'s `[[HABITABILITY] ... ]` and
  `[[HOUSING] ... ]`: conditional-inclusion blocks, content meant to be included only when the
  invocation supplies that parameter. ~12 occurrences across 6 scoped files.
- **`stellaris/common/scripted_triggers/05_scripted_triggers_biogenesis.txt`** (excerpt, source
  lines 661–686) — the negated form, `[[!SPECIES] ... ]`, directly alongside the non-negated
  `[[SPECIES] ... ]` for contrast. Negation is real and appears in scoped content, not just the
  wider corpus (confirmed via `grep -rn '\[\[!' vendor/`).
- **`gigastructures/common/scripted_triggers/giga_birch_triggers.txt`** (excerpt, source lines
  16–19) — `[[WHO]]`: a conditional block with an empty body (the guard header's closing `]`
  immediately followed by the body's closing `]`, zero items between).
- **`stellaris/common/scripted_triggers/02_scripted_triggers_first_contact_dlc.txt`** (excerpt,
  source lines 303–342) — `value:fotd_support_cost|RESOURCE|minerals|`: a pipe-delimited
  parameterised scripted-value call. Flattened into one opaque `Identifier`, same treatment as a
  quoted string whose contents happen to look like script — nothing currently needs to walk into
  it structurally.
- **giga_vat_triggers.txt line 57** (real text, not a committed fixture — the enclosing `switch`
  block is ~90 lines of near-identical repetition, not worth a whole-file fixture for one
  construct; used via `parse_text` in `test_pipe_delimited_reference_with_an_embedded_parameter_
  reference`) — `value:giga_vat_grow_cost|VAT|$vat$|RESOURCE|primary|`: a pipe chain whose value
  segment is itself a live `$vat$` parameter reference, not plain text.
- **`stellaris/common/scripted_triggers/00_scripted_triggers_has_crisis_stage.txt`** (excerpt,
  source lines 1203–1207 of `00_scripted_triggers.txt`, separate `dest` from that file's other
  excerpt since the two source ranges aren't contiguous) — `has_global_flag =
  crisis_stage_$STAGE|1$`: a `$NAME|default$` parameter reference (fallback value used when the
  invocation doesn't supply `STAGE`), embedded mid-token. `$condition|always$` is the same shape
  (`giga_qso_triggers.txt`, `ndb_new_triggers.txt`, 6 occurrences).
- **`stellaris/common/scripted_triggers/09_scripted_triggers_nomads.txt`** (excerpt, source
  lines 36–41) — `$SCOPE$? = { ... }`: the trailing "safe scope" `?` marker (already handled on
  bare identifiers, e.g. `space_owner? = { ... }`) attached to a parameter reference instead.
  Kept off `ParameterReference.name` (unlike the identifier case) since `name` is a lookup key
  into the invocation's parameter table — corrupting it would break that lookup, not just cosmetics.
- **`stellaris/common/scripted_triggers/00_scripted_triggers_overlord.txt`** (excerpt, source
  lines 184–198) — `mult = $TARGET$.trigger:empire_size`: the dotted-scope-chain idiom (already
  fixed for plain identifiers, `root.owner`) attached to a `$parameter$` reference instead.
  Discovered only after the plain-identifier fix landed — this file's earlier, different parse
  failure was masking it.
- **`gigastructures/common/inline_scripts/generic_parts/giga_toggled_code.txt`** (whole file) —
  `value = @[ (-1 * (...)) ]`: an inline arithmetic expression (bracket-depth-aware scan, flattened
  to one opaque `Identifier`, same as everything else in this section). Not one of the originally
  five named grammar gaps for this round — found because it was still in the 17-failure list and
  blocked this script (itself referenced by `zzz_overwrites.txt`'s `code = "..."` idiom, see
  above) from parsing at all.
- A related, broader bug found while adding these fixtures: a `$PARAM$` reference embedded
  **directly** in identifier text with no connecting `.`/`@`/`|` at all (e.g. `crisis_stage_
  $STAGE|1$`, `planet_$JOB$_$RESOURCE$`) was silently split into two disconnected top-level
  items rather than failing or merging — a data-corrupting bug, not just a parse failure, caught
  by `test_parameter_reference_with_default_value` when the `$STAGE|1$` fixture's expected value
  came back truncated. Confirmed common across `scripted_triggers/` in all four sources (dozens
  of distinct names via `grep -rnoE` for identifier-glued-to-`$PARAM$` shapes). Fixed as part of
  the same general continuation mechanism, not a special case.

## `acot/`, `aot/`

New source trees, added for the P-16 ancestor-closure and placeholder-resolution cases, which had
no coverage. All technology fixtures here except `z_aot_mega_tech_override.txt` are **excerpts** —
the source files (1600–3300+ lines each) are almost entirely unrelated content; each excerpt is
one exact, complete technology block, line-range cited.

- **`acot/acot_tech_dark_matter_power_core_dm.txt`** (excerpt of
  `vendor/mods/acot/common/technology/acot_01_delta_components_tech.txt`, lines 30–64) — pairs
  with `gigastructures/giga_17_alternative_mega_build.txt`'s `giga_tech_amb_supertensiles_acot_delta`
  (its direct prerequisite).
- **`acot/acot_tech_dark_matter_power_core_ae.txt`** (excerpt of
  `acot_02_alpha_components_tech.txt`, lines 9–79) — pairs with
  `giga_tech_amb_supertensiles_acot_alpha`. Also independently useful: its own `ai_weight` has a
  `NOT = { any_country = { ... has_technology = tech_dark_matter_power_core_ae ... } }` — a
  self-referential `has_technology` check (a tech's weight depends on whether *other* countries
  have researched itself), nested three scopes deep.
- **`acot/acot_tech_dark_matter_power_core_se.txt`** (excerpt of
  `acot_03_stellarite_components_tech.txt`, lines 693–744) — pairs with
  `giga_tech_amb_supertensiles_acot_sigma`.
- **`acot/acot_tech_precursor_gateway.txt`** (excerpt of `acot_00_precursor_tech.txt`, lines
  2285–2314) — the ACOT **original** of `tech_precursor_gateway`, for the mod-over-mod overwrite
  pair below. Note the commented-out `prereqfor_desc` block (lines mid-file) — another
  brace-in-comment case, this time multi-line.
- **`acot/common/scripted_variables/acot_scripted_variables_tech_cost.txt`** (whole file, 35
  lines) — defines `@acot_tier6cost1` through `@acot_tier9cost3`, the real values that win over
  Gigastructures' `zz_giga_compat_overwrite_me.txt` zero-stubs (see Dependency closure, above)
  when ACOT is vendored.
- **`aot/aot_tech_civil_phanon_application.txt`** (excerpt of
  `vendor/mods/aot/common/technology/z_aot_phanon_building_tech.txt`, lines 1–35) — pairs with
  `giga_tech_amb_supertensiles_acot_phanon`. Note `prerequisites = { }` — an **empty** block,
  syntactically a block with nothing inside, distinct from omitting the key entirely.
- **`aot/z_aot_mega_tech_override.txt`** (whole file, 285 lines, **not excerpted** — small enough
  to copy whole and copying it whole means the mod-over-mod overwrite fixture below comes with
  nine further, uninspected overwritten technologies for free) — **the mod-over-mod overwrite
  fixture.** Redefines `tech_precursor_gateway` (line 2 of this file) with a different `weight`,
  `weight_modifier` and a *live* `prereqfor_desc` where `acot/acot_tech_precursor_gateway.txt`
  (above) has that block commented out. Load order is vanilla → Gigastructures → ACOT → AoT, so
  AoT's version must win. This is the fixture set's only mod-over-mod case (the existing P-15
  fixture, `zz_giga_tech_overwrites.txt`, is mod-over-*vanilla*); pair the two `tech_precursor_gateway`
  files to test that overwrite resolution doesn't assume "the mod" is always Gigastructures.

## `localisation/`

Stage 1 parses these; the set previously had no coverage at all.

- **`localisation/stellaris/technology_l_english.yml`** (whole file, 1279 lines) — vanilla
  technology localisation. UTF-8 BOM at byte 0. `§`-colour codes (45 occurrences: `§G`, `§H`,
  `§R`, `§Y`, `§E`, `§W`, closed with `§!`), `£icon£` tokens (10 occurrences), and `$VARIABLE$`
  substitution throughout, including chained value+unit strings
  (`corvette_hull_effect:0`, line 67). Line 1271,
  `requires_tech_synchronized_defences:0 "§RRequires £physics£ §Y$tech_synchronized_defences$§!
  technology.§!"`, combines all three token types in one string — the single densest line in the
  file syntactically. No non-ASCII characters (accented or otherwise) were found anywhere in this
  file; the vanilla technology localisation stays within ASCII plus the `§`/`£` control codes.
- **`localisation/gigastructures/giga_tech_overwrites_l_english.yml`** (whole file, 12 lines) —
  pairs directly with `gigastructures/zz_giga_tech_overwrites.txt`: the four `l_english` keys are
  exactly that fixture's `technology_swap.name` values
  (`giga_tech_ring_world_swap[_no_habitables[_bio]]`). Has `§H...§!` colour, `£giga_sr_bulk_matter£`
  icon token, `$VAR$` substitution including the **dotted** form `$utopia.2000.name$` (distinct
  token syntax from plain `$var$`), and an escaped `\n` inside a quoted string.
- **`localisation/gigastructures/giga_orbital_elysium_l_english.yml`** (whole file, 179 lines) —
  pairs with `giga_tech_orbital_elysium` in `gigastructures/giga_02_society.txt`. Line 27,
  `d_giga_elysium_buildings_desc`, nests two `§W...§!` spans around a `£building£` icon token and
  a `$name_orb_elysium$` substitution, separated by an escaped `\n§W--------------§!\n` — colour,
  icon and substitution tokens interleaved in one string, with an escaped-newline-delimited
  divider in the middle of it.
- **`localisation/gigastructures/giga_l_english_excerpt.yml`** (**spliced excerpt** — not
  contiguous; assembled from five separate line ranges of the 14878-line
  `vendor/mods/gigastructures/localisation/english/giga_l_english.yml`, each range copied verbatim
  and separated by a blank line exactly as in the source, with the splice points documented here
  rather than marked in the file itself):
  - source line 1 — the `l_english:` root key. This file is CRLF-terminated with a UTF-8 BOM
    throughout (unlike every technology-script fixture, which is LF); the whole excerpt preserves
    CRLF line endings and the BOM for that reason — see `encoding/` for the isolated case.
  - source lines 159–160 — `allow_orb_elysium` / `desc_orb_elysium`, the `prereqfor_desc.custom`
    keys `giga_tech_orbital_elysium` in `giga_02_society.txt` references.
  - source line 1556 — `SHIP_AURA_PLANET_DESC`, a clean example of an escaped `\"quoted\"` word
    inside an already-quoted string, combined with `$name_war_planet$` substitution.
  - source lines 4130–4131 — `giga_psychic_beacon.003.desc` / `giga_dominate_t`: `§B` colour
    wrapping a **fully-quoted sentence** (`§B\"Select the system...\"§!`) — escaped quotes nested
    inside a colour span, the most syntactically tangled string found in either mod's
    localisation.
  - source lines 6179–6180 — `giga_tech_orbital_elysium` / `_desc`, the technology's own display
    name (itself containing escaped quotes: `\"Top Down\" Orbital Infrastructure`) and
    description, completing the `giga_02_society.txt` pairing started at lines 159–160.

## `malformed/`

Hand-written, not copied — the only fixtures in this set that are authored rather than sourced
from `vendor/`. Each is a syntactically realistic technology file (styled after the real
fixtures, using real vanilla tech IDs and `@tier*` variables) with exactly one injected defect.
P-10 requires the build to fail loudly rather than emit a partial dataset; nothing previously
tested that failure path.

- **`unclosed-brace.txt`** — **expected failure: unterminated block / unexpected end of file.**
  `tech_malformed_unclosed`'s outer `{` (line 1) and its `weight_modifier`'s `{` (line 16) are
  both left open; the file ends mid-block with no closing braces for either. A correct parser
  must fail at or before EOF, naming the unclosed block — not silently treat EOF as an implicit
  close.
- **`unexpected-closing-brace.txt`** — **expected failure: unmatched closing brace.** Line 12 has
  one `}` too many immediately after `tech_malformed_extra_brace`'s own closing brace, popping the
  parser back past document root. A well-formed neighbour technology follows (lines 14–19) to
  check whether a resilient parser can (or, per P-10, correctly refuses to) recover and keep
  parsing rather than cascading the error into the next block.
- **`unterminated-string.txt`** — **expected failure: unterminated quoted string.** Line 6's
  `prerequisites = { "tech_sapient_ai }` opens a `"` that is never closed on that line or,
  consequently, anywhere sensible in the file — a naive scanner will consume the rest of the file
  as string content looking for the matching quote. A well-formed neighbour technology follows
  (lines 13–18) for the same reason as above.
- **`stray-token.txt`** — **expected failure: unexpected token outside any key/value or block.**
  Line 9, `oops_forgot_to_delete_this_debug_line`, is a bare identifier at document root: not
  followed by `=`, not inside a block. Modding a real file by hand produces exactly this kind of
  leftover debug artifact; the parser must reject it rather than silently ignoring the line.
- **`truncated-file.txt`** — **expected failure: unexpected end of file mid-token.** The file
  stops mid-identifier (`giga_elysi`, cut off from what was evidently going to be
  `giga_elysium_disabled`) inside a doubly-nested `OR`/`NOT` block, with no closing braces at all.
  Simulates a truncated download or a write that was interrupted partway — distinct from
  `unclosed-brace.txt` in that here the very last *token* is incomplete, not just the block
  structure.

## `encoding/`

Paradox files are inconsistently encoded in practice; this directory covers the cases actually
observed in `vendor/` (see `localisation/gigastructures/giga_l_english_excerpt.yml`'s note above,
which found real CRLF+BOM in a shipped file) plus the classic silent-corruption case. Encoding
bugs corrupt output rather than crashing the build, so they need fixtures a test can assert
byte-for-byte against, not just "did it throw."

- **`windows-1252.txt`** — a technology file whose comment contains real Windows-1252 bytes: `’`
  (curly apostrophe, `0x92`), `—` (em dash, `0x97`) and `é` (`0xE9`), verified via `iconv` and
  `xxd` to be genuine single-byte cp1252, not UTF-8 multi-byte sequences. `0x92` alone is not a
  valid UTF-8 continuation byte, so a strict UTF-8 decoder should error or replace it — this
  fixture is for asserting *which* of those two happens, and that it happens loudly rather than
  silently mangling the comment (which is harmless) or, worse, a string field (which wouldn't be).
- **`utf8-bom.txt`** — a minimal, otherwise-ordinary technology file with a UTF-8 BOM (`EF BB
  BF`) prepended, verified with `xxd`. The BOM must not end up as part of the first token
  (`tech_encoding_utf8_bom`) or the file's first key will fail to match anything.
- **`lf.txt`** / **`crlf.txt`** — the same technology file content, byte-identical except line
  endings: `lf.txt` uses `\n` (matching every technology-script fixture elsewhere in this set),
  `crlf.txt` uses `\r\n` (matching what `giga_l_english_excerpt.yml` shows real shipped
  localisation using). A parser that splits on `\n` alone will leave a trailing `\r` on every
  line's last token in `crlf.txt` — harmless for a `}` line, silently wrong for a value like
  `tier = 2\r` if that `\r` ends up inside a parsed field.

## `variables/`

Hand-written, not copied — same status as `malformed/` and `encoding/`: no third-party content,
committed directly. Exist because the vendored corpus has zero live cases of either construct
(verified across all 53 `scripted_variables/*.txt` files in `vendor/`, not just the fixture
subset): no scripted variable's value is ever another `@variable` reference, so the resolver's
recursive resolution and its DFS cycle detection would otherwise have nothing real to run
against.

- **`reference-chain.txt`** — `@chain_top = @chain_middle`, `@chain_middle = @chain_base`,
  `@chain_base = 1000`, in that declaration order — deliberately the *reverse* of dependency
  order, so a resolver that just walks the file top-to-bottom in one pass and resolves
  eagerly (rather than recursing into each reference) gets this wrong on the first name it
  looks up.
- **`reference-cycle.txt`** — `@cycle_a = @cycle_b = @cycle_c = @cycle_a`. Three names, not
  two, so the requirement that a cycle error name the *full* chain has a chain worth naming
  rather than a trivial A↔B pair.

## Verification: excluded large files

The claim above — that `00_soc_tech.txt`, `00_eng_tech.txt`, `00_phys_tech.txt` and
`00_biogenesis_tech.txt` contain only repetition of cases already covered — was checked, not
assumed. For all four files: no duplicate top-level technology IDs within a file; no comparison
operators beyond what's already covered (`00_soc_tech.txt` and `00_eng_tech.txt` use `>=` only,
already covered by `giga_06_special_project_tech.txt` et al.; `00_phys_tech.txt` and
`00_biogenesis_tech.txt` use no comparison operators at all); no `!=` or `<=` anywhere in any of
the four; no boolean block type beyond `OR`/`AND`/`NOT`/`NOR` (no `NAND`/`XOR`/etc.); braces
inside comments occur (`00_soc_tech.txt` ×152, `00_eng_tech.txt` ×23, `00_phys_tech.txt` ×23,
including a fully commented-out tech block at `00_soc_tech.txt` line 943) but that case is already
covered by `000_documentation.txt` and the commented-out `inline_script` lines in
`giga_03_engineering.txt`. Nothing found warranted adding a fixture from these files.
