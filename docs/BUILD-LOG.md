# Build log

Historical build record, organised by stage and component rather than chronologically. Moved out of CLAUDE.md (which had become an append-only session log — see that file's own note) in a reconciliation session; every entry below is preserved verbatim from CLAUDE.md's former "Open items" section, only regrouped under component headings and, where a single entry spans several components, filed under its primary one with a cross-reference. Nothing was summarised, cut, or rewritten -- this is a reorganisation, not a cull.

For CURRENT open items and where to look for detail, see CLAUDE.md's own (now short) "Open items" section. For locked, load-bearing decisions and rules that must not be re-litigated, see CLAUDE.md's main body and `spec/decisions.md`.

## Stage 1 — Extract

`pipeline/clausewitz/` (tokeniser, recursive-descent parser, lossless AST, round-trip serialiser, corruption detector), `pipeline/variables.py`, `pipeline/inline_scripts.py`, `pipeline/localisation/`, `pipeline/icons/`.

- **Stage 1 (Extract) is complete**, and the dataset schema — the cross-language contract Stage 2
  and Stage 3 both build against — is now written. See HANDOFF.md for the full picture.
  `pipeline/clausewitz/` (tokeniser + recursive-descent parser, lossless AST, plus a round-trip
  serialiser and corruption detector — see the Rules section) is built and green against every
  fixture in `tests/fixtures/`. `pipeline/variables.py` (`@variable` resolution),
  `pipeline/inline_scripts.py` (`inline_script` expansion), `pipeline/localisation/` (hand-written
  parser for the YAML-*like* localisation format — not YAML, see the Rules section), and
  `pipeline/icons/` (technology/ascension-perk icon resolution, DDS decode, deterministic,
  size-capped atlas packing — see the Rules section) are all built, each with its own test module
  (`tests/test_variables.py`, `tests/test_inline_scripts.py`, `tests/localisation/`,
  `tests/icons/`).

## Dataset schema (`schema/`)

JSON Schema for all five dataset artefacts, generated TypeScript types, Python-side validation.

- **`schema/`** carries the JSON Schema for all five dataset artefacts (base dataset, empire
  overlay, detail payload, search index, diagnostics — see "Dataset structure" above and
  `spec/implementation-notes.md`'s Stage 2 section for the full field assignment).
  `schema/generated/dataset-types.ts` is generated from it by
  `tools/generate_typescript_types.py` (hand-written in Python — no Node/npm toolchain in this
  environment, and D-12 already commits the pipeline to Python end to end) and checked in;
  `tests/schema/test_typescript_drift.py` re-runs the generator and fails if the checked-in copy
  doesn't match, so the two sides of the contract can't drift by hand-editing either end.
  `pipeline/dataset_schema/` validates Python-side output against the schema (structural
  validation, then a separate `schemaVersion`-support check — see
  `UnsupportedSchemaVersionError`) and owns the canonical `EmpireProfileIndex` derivation
  (`pipeline/dataset_schema/empire_profile.py`, strides derived from axis cardinalities at import
  time, never hardcoded, with an import-time bijection assertion) plus the
  `availabilityMatrix`/overlay consistency check. `tests/schema/` covers a minimal valid document
  per artefact and the four required rejection shapes (unsupported version, missing required
  field, invalid edge kind, boolean-where-three-state).
  ~~**TODO(Stage 3):** `schema/generated/dataset-types.ts` has never actually been typechecked~~
  **Closed, later session — see "Stage 3 toolchain foundation is built" below.** Zero `tsc`
  errors, verified three ways, not just by the drift test's self-consistency check.
- ~~One remaining Stage 2 handoff, recorded as a `TODO(Stage 2)` in `pipeline/icons/resolve.py`:
  the atlas currently packs every resolvable icon across all four sources unconditionally.~~
  **Done** (later session): `pipeline/icons/build.py`'s `filter_result_to_rendered_scope` filters
  technology icon candidates to the P-16 980-node rendered set (ascension-perk icons deliberately
  stay unfiltered — see HANDOFF.md's "Atlas content scope" note for why filtering them by the
  technology closure would be the wrong criterion entirely). Real filtered figures: technology
  atlas 4 sheets/8,387,616 bytes (unfiltered) → **2 sheets/4,564,314 bytes** (filtered); combined
  with the unchanged 262,676-byte perk sheet, **total ~4.83 MB, down from ~8.65 MB unfiltered**.
  `MAX_TOTAL_ATLAS_BYTES` re-calibrated from 12 MB to **6 MB** — deliberately kept below the old
  unfiltered ceiling, unlike 12 MB, so a regression that silently disables filtering is now
  actually caught by the tripwire. Icon atlas bytes remain excluded from P-10's ≤2 MB base-dataset
  budget (P-9/`implementation-notes` require lazy icon loading; P-10's budget is defined as the
  base dataset's compressed transfer size specifically). The other `TODO(Stage 2)` from the icon
  pipeline — 19 technology/swap and 6 ascension-perk candidates recorded as unresolved diagnostics
  — is now partially resolved by the filter: only 4 of the 19 technology candidates survive it
  (their owning technology is actually rendered); the 6 ascension-perk candidates are unaffected
  (perks aren't filtered) and still stand uninterpreted, same as before.

## `pipeline/availability.py` — trigger evaluation (D-10/P-13)

Partial three-valued trigger evaluation against empire-profile facts; the `CONFIG_GATED` fourth `AvailabilityState`.

- **D-10/P-13 availability evaluator is built**: `pipeline/availability.py` — the partial trigger
  evaluator described above (three-valued short-circuit boolean evaluation, the 3 documented
  ground-fact assumptions, `has_technology`/`has_ascension_perk`/`has_gigastructural_constructs`/
  `has_galactic_wonders` exclusion — the latter two added after direct inspection showed they're
  ascension-perk gates wearing a different name, not a new kind of undecidable leaf). Boolean
  wrapper keys (`AND`/`OR`/`NOT`/`NOR`) are matched case-insensitively — the corpus genuinely uses
  both `NOT = { ... }` and `not = { ... }` for the same semantics (found while building Task 3's
  category survey; missing this silently treated real lowercase wrappers as unrecognised leaves).
  Output is `AvailabilityResult(state, reason, description, category)` per `(technology, profile)`
  pair. `pipeline/rendering_scope.py` implements P-16's closure as real code (BFS over resolved
  `prerequisites`, matching HANDOFF.md's hand-computed 7-technology/980-rendered-node measurement
  exactly) so both D-10 metrics are computed over the EXACT rendered set, not an approximation.
  `pipeline/trigger_text.py` is the shared trigger-condition -> text/category component HANDOFF.md
  flagged as missing — `describe_condition()` (best-effort human-readable phrasing, also usable
  for P-12.8's weight-modifier condition text) and `categorize_leaf()` (classifies an undecidable
  leaf into a `ReasonCategory`, corpus-derived, not designed up front — see that module).
  `pipeline/lock_reason_overrides.py` loads `config/lock_reason_overrides.txt` (same format/review
  bar as `config/overwrite_overrides.txt`, seeded empty — the real corpus currently has zero
  LOCKED results that fall back to unphrased raw trigger text) and
  `needs_lock_reason_override()`/`resolve_lock_reason()`/`build_missing_lock_reason_overrides()`
  wire P-13's "warn when an override is missing" requirement. `survey_uncertainty()` computes the
  D-10 metric split; `classify_d10_status()`/`build_d10_diagnostics_section()` apply the
  3%/10%/ratchet thresholds and produce the `schema/diagnostics.schema.json`-shaped
  `profileDependentUncertainty`/`unconditionalUncertainty` sections (that schema was updated in
  the same session — see below). Tests: `tests/test_availability.py`,
  `tests/test_trigger_text.py`, `tests/test_lock_reason_overrides.py`,
  `tests/test_rendering_scope.py` (all synthetic, mechanism coverage), plus
  `tests/test_availability_corpus.py`/`tests/test_rendering_scope.py`'s real-corpus tests (skipped
  when `vendor/` isn't populated).

  **Real measured rates, over the EXACT 980-rendered-node P-16 closure (both metrics share this
  denominator, per this file's D-10 section)**: **3.37% worst-case profile-dependent uncertain**
  (below HANDOFF.md's 5.3% upper-bound projection, as expected — the projection counted "could
  vary by profile", the real short-circuit logic pins it lower; **confirmed to actually cross the
  3% warn threshold** — `classify_d10_status(0.0337) == "warn"`, asserted directly in
  `tests/test_availability_corpus.py`, not just eyeballed from a printed rate) and **21.33%
  unconditional uncertain (209/980)**.

  **This figure moved twice** (209 → 259 → 209) **before settling here — see the "`giga_tech_
  repeatable_*_cap` correctly categorized — CONFIG_GATED" bullet further down this section for
  the full history, both corrections, the re-derived category-distribution table, and why 209
  landing back where it started is a coincidence of arithmetic, not evidence nothing changed.**
  In short: the original 209 was wrong (raw-block parsing skipped 50 real technologies' gating
  conditions entirely); 259 was also wrong, differently (those 50, once evaluated correctly,
  were classified `uncertain` when their `potential` actually resolves determinately); 209 is
  now right, because those 50 correctly resolve to `config-gated` — a fourth `AvailabilityState`,
  not `uncertain` and not `locked` — and so belong in neither this metric nor its `locked`
  counterpart. The category distribution over this final 209-set is byte-identical to the
  original pre-correction table (89/41/34/34/7/4 — crisis/story, origin, opaque-country-state,
  ethics/civic, unclassified, mod-content) — restated below rather than in this paragraph, since
  it's identical to what was already documented before any of this session's or the previous
  session's corrections began. `has_country_flag`'s crisis/story sub-split is still a
  name-pattern heuristic, not individually verified per flag (see `_looks_like_story_progress`).

  **Defect class, not three unrelated bugs (Stage 2 cleanup session).** Three components have now
  independently produced a plausible-but-wrong answer, with no error raised, by reading
  `giga_tech_repeatable_*`-family technology data by a route other than the full expanded
  canonical record: (1) tier resolution — 50 `_cap` nodes have no `tier` field pre-expansion (P-2's
  tier-source audit); (2) `pipeline.layout.is_repeatable` — a related but mechanistically distinct
  bug (a sign-only `levels < 0` predicate missing 12 finite-level repeatables in the SAME family,
  not itself a raw-vs-expanded input problem, since layout's real-corpus path was already
  expansion-fed — see the "Repeatables" section); (3) this section's `unconditionalUncertainty` —
  50 `_cap` nodes have no `potential` field pre-expansion. (1) and (3) are the same mechanism
  (expansion-only field) applied to two different fields; (2) shares the same *family* and the
  same *symptom* (a plausible wrong answer, zero errors, discovered only by independently checking
  against real evidence — a screenshot for (2), a hand-recomputation for (3)) without sharing the
  exact cause. **The actionable generalisation**: any component that acquires technology data by a
  route other than the full expanded canonical record is at risk of this failure mode, and the
  `giga_tech_repeatable_*` family is the reliable canary for it, because enough of that family's
  own data (tier, potential, and — via `giga_mega_repeatable.txt`'s shared template — probably
  other fields too) exists ONLY post-expansion that a raw-block consumer fails silently rather
  than loudly. See the audit below for which of this pipeline's other components read technology
  blocks, and by which route.

  **Audit: every component that reads a technology block, and its input route** (Stage 2 cleanup
  session, reported not fixed — see HANDOFF.md for the one gap found and its scoped follow-up):

  | Component | Reads technology blocks via | Expanded? |
  | --- | --- | --- |
  | `pipeline/overwrites.py` (`collect_technology_definitions`, diffing, `ordered_prerequisites`, `alternative_prerequisite_groups`) | `Document`s passed in by the caller | Caller-dependent — never expands itself |
  | `pipeline/rendering_scope.py` | `TechnologyDefinition.block` from `overwrites`' history | Caller-dependent, same as above |
  | `pipeline/crisis_faction.py` | Same | Caller-dependent, same as above |
  | `pipeline/layout.py` (`compute_layout`, `resolve_declared_tier`, `is_repeatable`, `category_of`) | `TechnologyLayoutInput.block`, supplied by the caller | Caller-dependent; every real corpus test/emission call site feeds it expanded blocks (verified) |
  | `pipeline/edges.py` (`compute_typed_edges`) | `dict[str, Block]` passed in by the caller | Caller-dependent, same as above |
  | `pipeline/availability.py` (`evaluate_trigger_block` and friends) | A `Block` passed in by the caller | Caller-dependent — **this is exactly where the bug lived**: the evaluator itself was always correct, its caller (the old test fixture) fed it the wrong input |
  | `pipeline/dataset_emit.py` | Loads and expands technology documents itself, once, in `build_context` | Always expanded — verified, this is the one component with its own loading path rather than depending on a caller |
  | `pipeline/icons/resolve.py`/`build.py` (`collect_candidates`) | Parses technology/ascension-perk files directly via `parse_file`, no caller-supplied option at all | **NOT expanded — reads raw, unexpanded blocks unconditionally, no way to pass expanded documents in.** |

  **Every pipeline module above that takes a block as a parameter is correct-by-construction and
  depends entirely on its caller** — none of them expands internally, and none of them is wrong on
  its own terms. The failure mode lives at the CALL SITE, not in these modules, which is exactly
  why the bug was invisible: `pipeline/layout.py`'s and `pipeline/dataset_emit.py`'s real call
  sites already expand correctly (verified, not assumed), so the same shared functions are
  correct when called from there and were wrong only when called from
  `tests/test_availability_corpus.py`'s own fixture.

  **One real, not-yet-audited-away gap found**: `pipeline/icons/resolve.py`'s `collect_candidates`
  parses `common/technology`/`common/ascension_perks` files directly with `parse_file`, with no
  `inline_script`-expansion step anywhere in the icon pipeline, and no parameter to accept
  pre-expanded documents even if a caller wanted to supply them. Every one of the 50
  `giga_tech_repeatable_*_cap` technologies' icon resolution consequently runs off a raw block —
  **unaffected in practice today** (their `icon` field, if any, and their filename-convention
  fallback don't come from anything the `giga_mega_repeatable.txt` template splices in — checked:
  none of the 50 candidates is unresolved for a reason traceable to a missing expansion), but this
  is exactly the shape of gap that produced all three defects above, just not yet triggered for
  icons. **Not fixed in this session** (audit only, per this session's scope) — a follow-up should
  scope whether icon candidate collection needs the same `inline_script` expansion pass every
  other Stage 2 consumer already gets, or whether icon resolution's specific field set (`icon`,
  `technology_swap`/`tradition_swap`, `inherit_icon`) is safely never inline_script-templated in
  the real corpus (unverified either way — this audit checked today's zero-impact outcome, not the
  general question).

  **Leaf-matcher case-sensitivity audit** (prompted by the boolean-wrapper case bug above):
  checked every known leaf key (`is_nomadic`, `is_gestalt`, `country_uses_bio_ships`,
  `has_country_flag`, `has_global_flag`, `has_dlc`/`host_has_dlc`, `has_technology`,
  `has_ascension_perk`, `is_fallen_empire`, `has_ethic`, `has_origin`, `has_valid_civic`, ...) for
  case variants and found none in the real corpus; `= yes`/`= no` values are always lowercase
  (1,824 / 667 occurrences, zero `Yes`/`YES`/`No`/`NO` variants); every mod-config toggle suffix
  match (`_forbidden`/`_disabled`/`_OFF`) has no lowercase counterpart being missed; and every
  axis-fact leaf in the corpus uses `=` exclusively, never `!=`/`<>`. No further case- or
  syntax-variant bug found — the boolean-wrapper case bug was real but isolated, not a symptom of
  a broader pattern in leaf matching.

- **`giga_tech_repeatable_*_cap` correctly categorized — CONFIG_GATED, a fourth availability
  state** (later session). Follow-up to the "Small targeted correctness pass" bullet above: the
  50-node family's `unclassified` jump (7→57, "Availability evaluator" section) turned out to be
  a real classification GAP, not just missing corpus coverage. The template's `potential` —
  `NOT{has_global_flag=$name$_disabled} AND has_global_flag=$name$_capped_r` — is two
  mod-configuration toggles; the user confirmed `_capped_r` specifically (no core Gigastructures
  preset sets a cap to the "1+r" mode it names, so it's unset by default) is the SAME "assume
  documented default" shape as the already-recognised `_forbidden`/`_disabled`/`_OFF` suffixes,
  just not yet taught to the evaluator.

  **`pipeline.trigger_text.MOD_CONFIG_TOGGLE_SUFFIXES`** is now the single source of truth for
  this pattern (`_forbidden`/`_disabled`/`_OFF`/`_capped_r`) — moved out of
  `pipeline/availability.py`'s own private copy so the evaluator's resolution logic and
  `categorize_leaf`'s classification can't drift apart. **Corpus survey, scoped to `potential`
  blocks across all 1,879 canonical technologies** (not assumed confined to the known 50): every
  rendered technology using a `_capped_*`-shaped flag uses exactly `_capped_r`, and exactly the
  50 `giga_tech_repeatable_*_cap` technologies do so — `_capped_1`/`_capped_2`/`_capped_3`/
  `_capped_u`/`_capped_s` exist in the corpus (menu/button-effect files) but never in a rendered
  technology's `potential`, so nothing beyond the known 50 was in scope.

  **A new `AvailabilityState` (`schema/common.schema.json`, renamed from `ThreeState`) value:
  `config-gated`.** Elsewhere, `locked` means "your empire cannot obtain this" — an empire-state
  property, which is why D-10's states are keyed to the twelve-profile axis model at all. That
  framing is false for this family: their `potential` resolves definitively FALSE for every
  profile identically, but nothing about authority/shipset/nomadic status is the cause — a game
  OPTION is. Rendering them `locked` would misrepresent a one-toggle-away technology as
  empire-gated. `pipeline/availability.py`'s `evaluate_trigger_block` now checks whether the
  FALSE-causing leaf categorizes as `ReasonCategory.MOD_CONFIGURATION`
  (`pipeline.trigger_text`, new category) and emits `CONFIG_GATED` instead of `LOCKED` when it
  does — a mechanism that applies to any mod-config-toggle-caused FALSE result generally, not
  hardcoded to `_capped_r`; **verified against the real corpus that this generality costs
  nothing**: `config-gated` fires for exactly the 50 cap-family technologies and no others (every
  other real `_forbidden`/`_disabled`/`_OFF` occurrence is wrapped in `NOT{}`, contributing to
  AVAILABLE, never a bare FALSE). `$defs`/type renamed `ThreeState` → `AvailabilityState`
  deliberately (a value-count-independent name, so a fifth value later doesn't leave a stale name
  behind again) — TS types regenerated; both `$ref` sites (base-dataset's `availabilityMatrix`,
  empire-overlay's `availability[].state`) updated; empire-overlay's `reason`-required-when-
  non-available prose extended to cover `config-gated` too (this requirement was already
  documentation-only, not schema-enforced, for `locked`/`uncertain` — a pre-existing gap, found
  and reported, not fixed, since fixing it is unrelated new scope).

  **Real corrected figures, over the same 980-node rendered set (recomputed, not assumed)**:
  profile-dependent worst-case uncertainty **unchanged**, 3.37% (same profile, same rate to 5
  decimal places — none of the 50 was ever profile-dependent, since their `potential` has no axis
  check). Unconditional uncertainty **209/980 (21.33%), down from 259/980 (26.4%)** — the 50 that
  the earlier `_capped_r`-recognition fix had moved into `unconditionalUncertainty` now leave for
  `config-gated` instead. **209 is the same number the ORIGINAL raw-block-survey code reported,
  by coincidence, not by the same reasoning** — that number was wrong for skipping these 50 nodes
  entirely; this number is right for evaluating all 980 correctly and finding the 50 belong in a
  fourth state neither `uncertain` nor `locked` capture.

  **Category distribution over the final, corrected 209-node unconditional-uncertain set** —
  byte-identical to the table this project had before either correction began:

  | Category | Count | % of unconditional |
  | --- | ---: | ---: |
  | Crisis/story-chain progression | 89 | 42.6% |
  | Origin requirement | 41 | 19.6% |
  | Opaque mid-game country state | 34 | 16.3% |
  | Ethics/civic requirement | 34 | 16.3% |
  | Unclassified (honest fallback) | 7 | 3.3% |
  | Mod-content requirement (ACOT) | 4 | 1.9% |

  **~80% of unconditional uncertainty is explainable** (crisis/story + origin + ethics/civic + mod
  content), ~20% genuinely opaque or unclassified — restored exactly, since the intermediate
  259-node table's only difference (an `unclassified` count of 57, all 50 cap-family nodes
  landing there because `categorize_leaf` had no category for `_capped_r` yet) is now moot: those
  50 never reach `categorize_leaf` for the unconditional-uncertain path at all, because they
  resolve to `config-gated` before that classification would run. See `pipeline/trigger_text.py`'s
  own comments for the individual per-leaf verifications behind each row (`has_ancrel`,
  `is_world_forger_empire`, `giga_can_use_habitables`, etc.). See `spec/decisions.md`'s new D-10
  "CONFIG_GATED" subsection for the full
  evidence, the "first real application of the mod-config assumption to a bare flag" framing, and
  the explicit caveat that a non-core/custom Gigastructures preset may set a cap differently (a
  Stage 3 presentation concern, not a data one). Tests: `tests/test_availability.py`/
  `tests/test_trigger_text.py` (synthetic mechanism coverage, including that the suffix pattern
  applies only to `has_global_flag`, never `has_country_flag`), `tests/test_availability_corpus.py`
  (real-corpus figures, the corrected category-distribution table, and a two-layer regression
  guard — expansion AND correct-state — for all 50 cap technologies),
  `tests/schema/test_validation.py` (the new state's shape, plus the found-not-fixed
  reason-requirement gap recorded honestly), `tests/test_dataset_emit.py` (the real base dataset
  emits `config-gated` in all 12 `availabilityMatrix` slots for exactly the 50 cap technologies,
  never elsewhere).

  **The 209 → 259 → 209 sequence, recorded explicitly so it cannot be misread**: the two 209s
  above are not a no-op round trip — they exclude the same 50 nodes from
  `unconditionalUncertainty` for opposite reasons. Step 1 (original raw-block survey): 209,
  because a raw/unexpanded read never saw these 50 nodes' `potential` block at all — excluded by a
  defect, and (wrongly) counted `AVAILABLE`. Step 2 (after `inline_script` expansion, before
  `_capped_r`/`config-gated` existed): 259 = 209 + 50, because the now-visible `potential` made
  all 50 genuinely `uncertain`. Step 3 (current, after `_capped_r` joins
  `MOD_CONFIG_TOGGLE_SUFFIXES` and `config-gated` is introduced): 209 again, because those same 50
  now evaluate correctly to a fourth state, `config-gated`, that didn't exist at step 1 — same
  count, same 50 members, different (correct) reasoning. See `spec/decisions.md`'s D-10 section
  ("The 209 -> 259 -> 209 sequence...") for the full table.

  **The real change is visible in the AVAILABLE-state count, not the uncertainty count**: all 50
  moved from `AVAILABLE` (step 1's wrong reading) to `CONFIG_GATED` (step 3's correct one) — an
  **available-count delta of exactly -50**, confirmed directly
  (`tests/test_dataset_emit.py::test_repeatable_cap_family_available_count_delta_is_exactly_minus_50`):
  evaluating with no `potential` visible (the step-1 counterfactual) is unconditionally AVAILABLE
  for all 50; the real expanded evaluation is AVAILABLE for 0 of them. **Ratchet status**: having
  gone 209 → 259 → 209 across two sessions, the D-10 unconditional-uncertainty ratchet is back at
  its original seed value — no regression, no ratchet action needed.

  **Config-gated reason wording (P-13)**: display text is user-supplied, matching Gigastructures'
  own in-game option label — `Requires <Megastructure Name> cap: 1 + Repeatables`, e.g. "Requires
  Alderson Disk cap: 1 + Repeatables". Emitted as semantic data only, never a pre-composed
  sentence: the empire overlay's `availability[key].configGatedSubject`
  (`schema/empire-overlay.schema.json`) carries just the megastructure name; Stage 3 substitutes
  it into the fixed template, which lives in `spec/P-13-empire-locking.md`, not in the dataset.
  The name is sourced from the technology's own resolved localised name
  (`<Name> Management Protocols`, suffix stripped).

  **Corrected in a later session: all 50/50 resolve, not 42/50.** The suffix-stripped name is
  frequently itself a `$token$` (e.g. `giga_tech_repeatable_alderson_cap` -> `$name_alderson$`).
  An earlier pass assumed such a token was an unresolvable Stellaris runtime name-pool reference
  and returned `null` for all 8 real occurrences — including the flagship Alderson Disk example
  the reason wording was designed around. **That assumption was wrong**, found by re-inspecting
  raw localisation source (CLAUDE.md's own "inspect raw bytes, never conclude from a formatted
  read" rule, applied here to the previous session's own unverified claim): every `$token$` is
  ordinary Stellaris `$key$` loc-variable substitution — `token` is itself a plain,
  statically-resolvable loc key one hop away (`name_alderson: "Alderson Disk"`, Gigastructures'
  own localisation). Two of the 8 (`dyson_swarm_3`, `orbital_arc_furnace_4`) are **vanilla**
  megastructures Gigastructures extends with a repeatable cap, and their name lives in vanilla's
  own localisation — confirming the fix (`pipeline/dataset_emit.py`'s `_resolve_loc_tokens`) must
  search the full cross-source `ctx.loc_table` (vanilla, Gigastructures, ACOT, AoT, in load
  order), bounded to a small hop count (some tokens chain through a second token, e.g. vanilla's
  `dyson_swarm_1: "$dyson_swarm_3$: Array"`) so an unexpected cycle fails cleanly to `null` rather
  than looping. `configGatedSubject` stays nullable in the schema and the resolver still returns
  `None`, never a guess, if a technology has no loc entry at all or a token can't be resolved
  within the hop limit — no case in the current corpus hits either path.

  **Real corpus, corrected: 50/50 resolve** to a literal megastructure name — the 8 previously-null
  cases: `giga_tech_repeatable_alderson_cap` -> "Alderson Disk" (the user's own flagship example),
  `_asteroid_manufactory_cap` -> "Asteroid Industrial Site", `_dyson_swarm_cap` -> "Dyson Swarm",
  `_furnace_cap` -> "Arc Furnace", `_observatory_cap` -> "Atmospheric Storm Observatory",
  `_orbital_naval_logistics_cap` -> "Orbital Naval Logistics Office", `_warmoon_cap` -> "Attack
  Moon", `_warplanet_cap` -> "Behemoth Planetcraft". Implementation:
  `pipeline/dataset_emit.py`'s `_config_gated_subject`/`_resolve_loc_tokens`. Test:
  `tests/test_dataset_emit.py::test_config_gated_subject_resolves_all_50_megastructure_names`
  (supersedes the retired `..._resolves_42_of_50_...` test of the same name pattern).

## `pipeline/crisis_faction.py` — crisis-faction derivation (D-7/P-5)

Three-step derivation (technology ID, prerequisite inheritance, override table), the Compound population corrections (0 → 2 → 3 → 15), and the EAWAF/Sirenalia reclassification (7 → 14).

- **D-7/P-5 crisis-faction derivation is built**: `pipeline/crisis_faction.py` implements the
  three-step rule D-7 only stated before now — technology ID (`classify_by_tech_id`), then
  prerequisite-chain inheritance (`classify_by_prerequisite_inheritance`, iterated to a fixed
  point so a chain of inherited classifications propagates fully regardless of processing order),
  then `config/crisis_faction_overrides.txt` (loaded by `pipeline/crisis_faction_overrides.py`,
  same format/review bar as the other override tables — uniquely among this project's override
  tables explicitly allowed to CORRECT an automatic result, not just fill a gap, since faction
  membership is closer to an editorial call). **Deliberately does NOT implement `potential`-block
  flag inspection** as part of step 2, despite D-7's "potential and prerequisite inspection"
  wording — tried against the real corpus and found to produce one confirmed false positive
  (`giga_tech_tetradimensional_engineering` is a standard physics tech with an alternate
  Blokkat-crisis unlock path, not a Blokkats-lane technology) — confirmed by reading the actual
  block, not guessed from the flag name.

  **Compound is 2, not 0 — corrected in a later session, via override, not a classifier
  change.** `tech_sm_autocannons` was originally recorded alongside
  `giga_tech_tetradimensional_engineering` above as a second false positive, on identity grounds
  (EHOF/Urmazin-trader content referencing a Compound weapon-compatibility bypass flag, not
  Compound membership). That verdict tested the wrong thing: identity, not reachability. Re-read
  against the raw corpus, `giga_special_tech_compound_weapon_bypass` — the flag both
  `tech_sm_autocannons` and a second technology, `tech_qnm_disruptors` (found the same session,
  same file, byte-identical `potential` shape — an `OR` of a `has_technology` AND-branch and a
  bare `has_country_flag` branch), gate their `OR`'s non-`has_technology` branch on — is set in
  exactly one place in the entire vendored corpus:
  `vendor/mods/gigastructures/events/giga_compound_situation_09.txt:113`, inside the Compound
  situation's own event chain (`common/situations/giga_compound_09.txt` drives it). A technology
  whose only non-`has_technology` unlock branch is gated behind a flag with that sole-setter
  provenance is Compound content wearing an EHOF technology's clothes — every path to it that
  isn't the ordinary tier-3 tech chain is Compound-gated, not merely flag-adjacent. Both
  technologies are now forced to Compound via `config/crisis_faction_overrides.txt`, not by
  widening the automatic derivation.

  **This is an override, not a rule, deliberately.** The evidence for both entries lives in
  `vendor/mods/gigastructures/events/`, a directory this project has never declared a required
  extraction source (see "Required directories, per source" above — `events/` is not among them).
  Teaching the classifier to resolve `has_country_flag` provenance generally would mean adding
  `events/` as a required source and making event-namespace string inference load-bearing for
  layout output — disproportionate for two nodes. A rule of the shape "classify an `OR` branch as
  Compound-gated when a `has_technology` reference inside that branch resolves to Compound
  content" was also considered and rejected as incoherent: run literally against these two
  technologies' `has_country_flag` branch, it reports zero matches — correctly, since that branch
  contains no `has_technology` reference for a has_technology-scoped test to evaluate. Zero was
  the right output for the rule as specified; the rule's scope was wrong, not the corpus, which is
  why these two nodes are handled by direct flag-provenance evidence instead. **This override does
  not track corpus growth** — a future Gigastructures update that adds more technologies gated the
  same way will silently classify Standard until a human notices and adds an entry.
  `tests/test_crisis_faction_corpus.py::test_compound_weapon_bypass_technologies_potential_shape_is_unchanged`
  pins the exact `potential` shape of both technologies, specifically so a corpus revision that
  restructures either one fails that test and forces this override back under review.

  **Real derived counts, over the 980-node P-16 rendered set**: Standard 923, Blokkats 42,
  Sirenalia 7, Aeternum 3, Katzenartig Imperium 3, **Compound 2** (both via override; step 1/2
  alone still find 0 — `giga_08_ehof_components.txt`'s seven `tech_compound_*` blocks remain
  commented out in the vendored source, so Compound's OWN technology content is still a confirmed
  real zero, distinct from its rendered count). **Do not rebuild or extend the classifier chasing
  more Compound content on this basis** — there is nothing else in the current corpus for a
  smarter derivation to find; re-check only after a Gigastructures version bump that could
  plausibly have uncommented the `tech_compound_*` content (re-run
  `tests/test_crisis_faction_corpus.py::test_compound_technologies_are_commented_out_in_the_vendored_corpus`,
  which fails loudly the moment that's no longer true) or added new bypass-flag-gated content (no
  automated tripwire for this — see "does not track corpus growth" above). **The Compound lane
  MUST still be supported end-to-end in the schema and renderer** — D-7 names five factions
  unconditionally, `pipeline/crisis_faction.py`'s `CRISIS_FACTIONS` already enumerates all five
  regardless of live content, and the content may be uncommented in a later mod release without
  any pipeline change being needed if the lane was never special-cased down to "four factions"
  anywhere. Step 2 contributes zero additional nodes beyond step 1 for the current corpus — step 1
  (technology ID) plus step 3 (the two Compound override entries) is confirmed to be the entire
  currently-derivable signal, a finding, not an assumption. Tests: `tests/test_crisis_faction.py`,
  `tests/test_crisis_faction_overrides.py` (synthetic, plus a check that the checked-in file loads
  its two real entries), `tests/test_crisis_faction_corpus.py` (real corpus, skipped when
  `vendor/` isn't populated — asserts the corrected per-faction counts above, that the remaining
  false-positive candidate still resolves to the standard lane, that both Compound candidates
  resolve to Standard WITHOUT the override and to Compound WITH it, and pins both technologies'
  raw `potential` shape as a regression guard on the override itself).

- **D-7/P-5 crisis-faction derivation: Compound's population corrected from 0 to 2, via override,
  not a classifier rewrite (later session, pipeline-only — no client/dataset rebuild in this
  session's scope).** `tech_sm_autocannons` was documented above (this file, "D-7/P-5
  crisis-faction derivation is built") as a confirmed false positive found by trying
  `potential`-block flag inspection against the real corpus — true on identity grounds (the
  technology's own cost/weight variables and `ehof_disabled` gate mark it as EHOF/Urmazin-trader
  content, not Compound-authored) but the wrong test for the actual question, which is
  reachability, not identity. Its `potential` is `OR = { AND = { has_technology = ...,
  has_technology = tech_qnm_utilities }, has_country_flag =
  giga_special_tech_compound_weapon_bypass }` — that flag's SOLE setter anywhere in the vendored
  corpus is `vendor/mods/gigastructures/events/giga_compound_situation_09.txt:113`, inside the
  Compound situation's own event chain. A technology whose only non-`has_technology` unlock branch
  is gated behind a flag with that provenance is Compound content, regardless of which mechanic
  its own cost/weight variables belong to. Re-reading `giga_08_ehof_components.txt` (the same file
  `tech_sm_autocannons` lives in) this session found a second technology, `tech_qnm_disruptors`,
  with the byte-identical `potential` shape — same flag, same sole setter, never previously
  documented at all.

  Both are now forced to Compound via `config/crisis_faction_overrides.txt` (the first two real
  entries the file has ever carried — it was seeded empty and stayed empty through every prior
  session), not by widening `pipeline/crisis_faction.py`'s automatic derivation. **Why an override
  and not a rule**: the evidence for both entries lives in `vendor/mods/gigastructures/events/`, a
  directory this project has never declared a required extraction source (see "Required
  directories, per source" — `events/` is not among them); teaching the classifier to resolve
  `has_country_flag` provenance generally would mean adding `events/` as a required source and
  making event-namespace string inference load-bearing for layout output, disproportionate for two
  nodes. A candidate rule — "classify an `OR` branch as Compound-gated when a `has_technology`
  reference inside that branch resolves to Compound content" — was tried and rejected as
  incoherent: run literally against these two technologies' `has_country_flag` branch, it reports
  zero matches, correctly, because that branch has no `has_technology` reference for a
  has_technology-scoped test to evaluate. Zero was the right output for the rule as specified; the
  rule's scope was wrong, not the corpus. **This override does not track corpus growth** — a
  future Gigastructures update that adds more bypass-flag-gated technologies by the same pattern
  will silently classify Standard until a human notices and adds an entry; there is no generalised
  detector watching for this shape.
  `tests/test_crisis_faction_corpus.py::test_compound_weapon_bypass_technologies_potential_shape_is_unchanged`
  pins the exact `potential` shape of both technologies specifically so a future corpus revision
  that restructures either one (renamed flag, removed bypass branch, merged `has_technology`
  conditions) fails that test and forces this override back under review rather than silently
  keeping a stale classification.

  **Real corrected figures, over the 980-node rendered set, re-measured not assumed**: Standard
  923 (was 925), Compound 2 (was 0), Blokkats/Sirenalia/Aeternum/Katzenartig Imperium unchanged at
  42/7/3/3. Per D-16's row model, the two moved nodes leave their category rows for the Compound
  row: `particles` 104→103 (`tech_sm_autocannons`), `propulsion` 52→51 (`tech_qnm_disruptors`).
  Canvas dimensions: width unchanged at 12,888px (row membership doesn't affect band/column
  geometry, D-13); height **12,888 × 10,800px, up from 10,708px** — the Compound row's own height
  grows by more than the two category rows it left shrink by. Densest cell is unchanged at
  voidcraft×T5 (47) — neither moved node was ever in that cell. All figures reproduced directly via
  `pytest tests/test_crisis_faction_corpus.py tests/test_layout_corpus.py
  tests/test_dataset_emit.py`, all green (1,368 total pipeline tests pass, up from 1,365).
  `giga_tech_tetradimensional_engineering` remains the one documented false positive with no
  override entry — its correct classification (standard lane) is still what the automatic
  derivation produces without one, unaffected by this session.

  **Not done this session, tracked as a gap**: the client dataset was not rebuilt and the renderer
  was not re-screenshotted against the new Compound population. The Stage 3 visual-fidelity pass's
  own screenshot review (this file, above) described the Compound row's "collapsed panel, chip,
  and 'No technologies in the current corpus.' note" — that empty-state framing no longer matches
  reality (2 technologies) and should be re-verified against a real render the next time `client/`
  work touches row rendering, rather than assumed still accurate from a stale screenshot. **Closed
  by the next bullet** — this session's client rebuild re-screenshotted the Compound row for real,
  now populated (see below).


- **Part-0 reconciliation (later session): a queued third correction to Compound's population was
  never implemented, confirmed by direct repo inspection, not assumed.** A fresh session opened
  with two disagreeing writeups — one reporting Compound = 2 (Standard 923), another describing
  "the Compound row... now 15 nodes post-reclassification." Checked directly: no flag→faction map
  existed anywhere in `pipeline/` or `config/` before this session — `config/
  crisis_faction_overrides.txt` carried only its original 2 technology-key entries
  (`tech_sm_autocannons`, `tech_qnm_disruptors`). The "15" figure was queued (planned, described in
  a prompt) and then genuinely dropped, exactly as suspected, when a prior session pivoted to
  other work before implementing it.

  **Implemented as specified**: `config/crisis_faction_flag_overrides.txt` (new, same
  format/review bar as the technology-key override file) + `pipeline/crisis_faction_flags.py`
  (loader) + `pipeline.crisis_faction.classify_by_flag` (new D-7 "step 1.5," scoped-AND/OR/NOT/NOR
  traversal of a technology's own `potential` block for a `has_country_flag` leaf, mirroring
  `pipeline.edges._scoped_has_technology`'s discipline) — seeded with exactly the one entry asked
  for, `qnm_utilities_possible = Compound`. Verified before writing the entry, not assumed from the
  flag's name: that flag's sole setter in the vendored corpus is
  `vendor/mods/gigastructures/events/giga_191_annihilator_dialog.txt:87`, and that event's own
  localised text (`giga_ehof_l_english.yml:796`) is explicit that the NPC granting `tech_qnm_
  utilities` exists to achieve "[t]otal annihilation of the $ehof_the_compound_text$" — real
  Compound-crisis-storyline content, confirmed by reading the raw event and its localisation, not
  inferred from the name "annihilator" alone. Wired into `classify_crisis_factions` (new
  `flag_overrides` parameter, applied after step 1 and before step 2's fixed-point loop, exactly
  as asked, so a flag-classified technology can itself seed prerequisite-chain inheritance) and
  into `pipeline/dataset_emit.py`'s real build call site.

  **Real measured result: Compound = 3, Standard = 922 — NOT the expected 15/910.** Per this
  session's own blocking instruction ("if it differs, stop and report before continuing"), this is
  reported rather than silently accepted or forced to match. `tech_qnm_utilities` itself IS
  correctly classified Compound via the new flag map (the "+1" beyond the pre-existing 2-node
  override). Its 12 direct dependents (the `tech_sm_*`/`tech_qnm_*` weapon-component technologies
  in `giga_08_ehof_components.txt`, each `prerequisites = { "<baseline weapon tech>"
  "tech_qnm_utilities" }`) do **not** inherit Compound, and cannot under the existing, deliberately
  conservative step-2 rule (`classify_by_prerequisite_inheritance`'s own docstring: "a technology
  with a mixed or partially-unclassified prerequisite set inherits nothing") — every one of the 12
  also requires an ordinary Standard-lane baseline weapon technology as a co-prerequisite, so its
  prerequisite set is never uniformly Compound. The originally-queued "13 = 1 + 12" plan
  presupposed a weaker inheritance rule (propagate through ANY matching prerequisite, not require
  ALL of them to match) that was never actually specified or built, and this session did not
  invent one to force the number to 15 — widening step 2's semantics generally, versus leaving the
  12 as a set of individually-reviewed technology-key overrides (the project's own established
  precedent for exactly this shape of gap, per `config/crisis_faction_overrides.txt`'s two existing
  entries), is a real design choice the user should make, not one to guess silently. **Left open,
  flagged here rather than resolved**: if the 12 dependents should also be Compound, the
  proportionate fix (consistent with how `tech_sm_autocannons`/`tech_qnm_disruptors` were handled)
  is 12 more reviewed entries in `config/crisis_faction_overrides.txt`, each independently verified
  against its own `potential`/`prerequisites` shape — not a semantic change to step 2's inheritance
  rule, which would have much broader, unaudited effects across the rest of the corpus.

  Real corrected figures, over the 980-node rendered set: Standard 922 (was 923), Compound 3 (was
  2), Blokkats/Sirenalia/Aeternum/Katzenartig Imperium unchanged at 42/7/3/3. Per D-16's row model,
  `tech_qnm_utilities` leaves the `propulsion` category row for the Compound row: `propulsion`
  51→50 (on top of the earlier 52→51 from the technology-key override's two entries). Canvas
  dimensions: width unchanged at 13,632px; height **13,632 × 11,492px, down from 11,608px**
  (`propulsion`'s row shrinks by more than Compound's grows, since Compound was already
  non-empty). All figures reproduced directly via `pytest tests/test_crisis_faction.py
  tests/test_crisis_faction_flags.py tests/test_crisis_faction_corpus.py tests/test_layout_corpus.py
  tests/test_dataset_emit.py`, full suite green (1,369 pipeline tests, up from 1,368).
  `giga_tech_tetradimensional_engineering` remains the one documented false positive with no
  override entry, unaffected by this session.

  **Resolved, same session, after the user reviewed this report**: the user confirmed the 12
  dependents should indeed be Compound, via 12 individually-reviewed `config/
  crisis_faction_overrides.txt` entries exactly as proposed above (not a step-2 semantics change),
  each carrying the reachability justification "requires `tech_qnm_utilities`, which is
  Compound-only reachable, so no unlock path exists without Compound content, notwithstanding its
  Standard-lane co-prerequisite." **Final real figure: Compound = 15, Standard = 910 — exactly the
  originally-expected number**, confirmed directly (`tests/test_crisis_faction_corpus.py`'s
  `test_corrected_faction_counts`, `test_qnm_utilities_dependents_do_not_inherit_automatically_but_do_via_override`
  — the latter asserts BOTH halves: the 12 resolve to `None` with the override table unloaded,
  confirming the gap the flag map alone left open is real, and resolve to `Compound` with it
  loaded). `config/crisis_faction_overrides.txt` now carries 14 real entries total. Per D-16's row
  model, `particles` moves 104→96 (7 of the 12 dependents: `tech_qnm_pd_tracking/lasers/plasma/
  energy_torpedoes/energy_lance/arc_emitter/titanic`) and `propulsion` moves 51→45 (5 more:
  `tech_sm_flak_batteries/mass_drivers/kinetic_artillery/mass_accelerator/titanic`). Canvas: width
  unchanged at 13,632px; height returns to **13,632 × 11,608px** — the same figure as before the
  flag map was added, a coincidence of the specific pixel arithmetic (Compound's much larger row
  now costs more height than the two category rows lose), not evidence nothing changed — real
  per-row membership differs substantially (Compound 3→15, particles 103→96, propulsion 50→45).
  Full suite green (1,381 pipeline tests, up from 1,368 at session start).

  **Client dataset was not rebuilt and the renderer was not re-screenshotted against Compound's
  final 15-node population** — this session's scope stayed pipeline-only throughout, including
  after the reconciliation resolved; the same session continued directly into Parts 1-3 (edge
  routing, spacing, and the Sirenalia pattern port) per the user's own follow-up instruction, and
  the client rebuild/screenshots happen as part of that verification pass instead, not separately
  for the crisis-faction change alone.

## `pipeline/layout.py` + `pipeline/geometry.py` — band/row layout (P-2/D-13/D-16/D-17)

Band (declared-tier), row (D-16 category/faction), sub-column (D-17 same-band depth) computation; the D-16 row re-axis; the D-17 same-band-ordering survey and its `subgrid_width` follow-up survey.

- **P-2/D-13 layout is built**: `pipeline/layout.py` (band/lane/sub-grid position computation)
  and `pipeline/geometry.py` (packs it into `float32` typed-array side-files + `GeometryRef`
  pointers, per `00-overview.md`). Two correctness gaps the tier-source audit found were closed
  first, both tested: `pipeline.overwrites.resolve_variable_overwrites` now checks `tier` for
  cross-source `@variable` overwrites (not just `cost`/`weight`); `pipeline.layout.
  resolve_declared_tier` hard-fails (`UnresolvedTierError`) on any rendered node whose declared
  tier can't be resolved after `inline_script` expansion, never a silent default. Bands are a
  node's own declared `tier` — D-13's model, not the superseded computed-column one. Computed
  longest-path position is internal only: it orders nodes within a band's category-grouped
  N=4-wide sub-grid (`(category, computed_position, key)`, deterministic) and gives backward-edge
  routing a consistent signal. Lanes are the fixed D-7 order (`LANE_ORDER`, standard + 5 crisis
  factions), always all six, including Compound at its confirmed-real zero population. Edges are
  routed as simple 4-point orthogonal polylines (H-V-H) with a deterministic hash-based channel
  offset (the hash now includes `kind`, not just `from`/`to`, so the 4 pairs that are both a
  `prerequisite` and a `potential-gate` edge don't draw identical overlapping polylines) — a
  first-pass router, not a full crossing-minimising/obstacle-avoiding one; that remains open
  follow-on work, noted in P-2 rather than silently claimed done. `edges[].backward`
  (`schema/common.schema.json`) flags a backward edge for distinct rendering treatment;
  `edges[].bandSpan` (added for P-14 edge typing, see below) carries the signed band distance on
  every edge, not just backward ones.

  **Real run over the exact 980-node P-16 rendered set** (`tests/test_layout_corpus.py`): all 980
  resolve — 0 `UnresolvedTierError`, 0 `LayoutCycleError` (the rendered prerequisite graph is
  confirmed acyclic). 34 of 989 rendered edges are backward (25 `prerequisite` + 2 `alternative` +
  7 `potential-gate` — see the P-14 edge-typing bullet below for the full breakdown; this figure
  superseded the original 27/964 `prerequisite`-only measurement in the same session it was made).
  Tests: `tests/test_layout.py`, `tests/test_geometry.py` (synthetic, mechanism coverage),
  `tests/test_layout_corpus.py` (real corpus, skipped when `vendor/` isn't populated — asserts the
  real canvas dimensions, densest cell, and backward-edge count so a corpus refresh that silently
  changes any of them fails a test). Schema updated to match (`schema/base-dataset.schema.json`'s
  stale per-technology `column` field — described as "may exceed tier after promotion", the
  superseded model — removed entirely; `tierBands[].column` renamed `bandIndex` with a description
  matching D-13; `schema/common.schema.json`'s `Edge` gained the required `backward` field); TS
  types regenerated; fixtures updated; schema tests green.

  **Repeatable-membership correction (later session, found against a user's v1 screenshot, not by
  any test)**: `is_repeatable` widened from "`levels < 0`" to "`levels` field present at all" —
  see "Repeatables" above for the corpus finding (12 additional finite-level repeatables) and D-13
  in `spec/decisions.md` for the exception this membership rule feeds. Real figures shift
  accordingly: **canvas 12,544 × 8,146px** (was 8,350px — the 12 newly-recognised repeatables
  shrink their old declared-tier band rows and grow the Repeatables band), densest actual band
  cell **Standard × T5 = 253 nodes** (was 261 — 8 of the 12 were Standard-lane, declared-T5
  nodes that moved into Repeatables). Sink property re-verified over the corrected 88-node set:
  881 non-repeatable-to-non-repeatable prerequisite edges + 83 non-repeatable→repeatable edges =
  964 total (cross-checks the earlier 891-vs-964 reconciliation); 0 repeatable→non-repeatable, 0
  repeatable→repeatable, so a repeatable node can never source an edge, let alone a backward one.
  The 27 backward edges are the same 27 by key under both the old and corrected membership — none
  touches a repeatable node either way. `schema/base-dataset.schema.json`'s `repeatable` field
  changed shape from an always-present object to `null | { levels }` (`null` = not repeatable;
  object = repeatable, `levels` finite int or `null` for unbounded) — the old always-object shape
  had no way to represent "not repeatable" without also (incorrectly) claiming "unbounded
  repeatable" via `{"levels": null}`, which is what the four base-dataset fixtures were doing for
  their non-repeatable example technology before this session corrected them. TS types
  regenerated; `tests/schema/test_validation.py` gained explicit coverage of all three shapes
  (null / finite / unbounded) plus the zero-level rejection.


- **Stage 2 row re-axis + localisation token resolution (later session, back in the pipeline —
  deliberately NOT the renderer re-wire, which is the still-open next slice).** Two independent
  fixes, both prompted by showing the Stage 3 slice-1/2/3 rendered output to the user and finding
  real problems neither test suite nor spec review had caught.

  **1. Layout row re-axis (D-16, `spec/decisions.md`).** The row axis was the D-7 crisis-faction
  lane (`LANE_ORDER`), with category only a sub-grid wrap key inside a lane×band cell — the user
  confirmed from v1 screenshots this was never the intent, and it wasted enormous vertical space
  (a faction lane reserved a full-height row for as few as 0-7 nodes, the same weight as
  Standard's 925). Rows are now the vanilla technology categories, one row each, followed by the
  5 crisis-faction rows, unified. Row assignment is **faction-first and mutually exclusive**: a
  technology with a crisis faction goes in that faction's row; everything else goes in its own
  category's row. `pipeline/crisis_faction.py` and D-7's derivation are completely unchanged —
  only the consumer changed.

  **Category row set is derived, never hand-typed** (`pipeline.layout._row_order`): Gigastructures
  defines its own `blokkats` technology category (`common/technology/category/giga_category.txt`),
  carried by exactly the 42 rendered technologies the D-7 classifier already places in the
  Blokkats faction row by ID fragment — 42/42, confirmed by direct survey, zero non-faction
  technology carries it. A hand-typed "13 vanilla categories" list would need `blokkats` manually
  excluded or would emit a spurious always-empty 14th row; deriving the row set from whichever
  categories still have a non-faction member handles this for free. Real corpus check: no vanilla
  category is left empty or near-empty by the faction departures (largest single departure:
  Sirenalia's 7 psionics technologies, 41→34 remaining). **Row order**: derived categories grouped
  by `AREA_ORDER` (physics → society → engineering, matching the existing area-colour convention),
  alphabetical by category id within an area (each real category maps to exactly one area 1:1 —
  confirmed, no real tie to break), then the 5 faction rows in `CRISIS_FACTIONS`'s own order
  (reused directly, not re-declared). Every faction row is always emitted — Compound's population
  was 0 at the time this session ran; a later session's crisis-faction override raised it to 2
  (see "Availability evaluator"/crisis-faction section above), which changes counts, not the
  always-emitted-row mechanism this bullet actually describes.

  **Real measured geometry** (see D-16 for the full table): canvas grows from
  12,544 × 8,146px to **12,888 × 10,708px** in this session (later revised to **10,800px** tall
  after the Compound override moved 2 nodes into the Compound row — see the crisis-faction
  section above; width and densest cell are unaffected). Densest cell moves from Standard×T5 (253)
  to **voidcraft×T5 (47)** — categories are inherently smaller buckets than "everyone who isn't
  crisis content," so no cell is anywhere near as crowded now, an intended consequence of the
  re-axis. **Backward-edge decomposition is UNCHANGED, re-measured not assumed**: still
  34 = 25 `prerequisite` + 2 `alternative` + 7 `potential-gate`, max span 5 — a necessary
  consequence of D-13 (the band/column axis) being completely untouched by the row re-axis:
  `backward`/`bandSpan` are computed purely from declared-tier band indices, which have zero
  dependency on which row a node lives in. Total edge counts likewise unchanged (989 = 888 + 76 +
  25), confirmed directly.

  **Gutters, real values, one named place** (`pipeline/layout.py`): the user flagged the previous
  8px/10px sibling-card gaps and the single 40px combined header+separator strip as reading like
  edge-to-edge touching cards. `INTRA_GAP_X` 8→16px, `INTRA_GAP_Y` 10→16px, `INTER_BAND_GUTTER`
  40→48px; the old single `LANE_LABEL_MARGIN` splits into `ROW_HEADER_HEIGHT` (40px, unchanged,
  the header strip) plus a NEW `ROW_GUTTER` (24px, pure separation on top of the header) — 64px
  total between rows now, up from 40px.

  **Within-cell ordering**: `(category, computed_position, key)` → `(computed_position, key)` —
  category dropped because a (row, band) cell's members already all share the same
  category-or-faction by construction now, so it no longer discriminates anything.

  **JSON contract deliberately unchanged, only its content** — `lanes`/`laneId` keep their
  existing schema names (still 18 entries now instead of 6; `crisisFaction` still null for a
  category row exactly as it was for the old Standard lane) rather than being renamed to
  `rows`/`rowId`, specifically so this session could stay inside its own "no renderer changes
  beyond regenerating types" boundary — `client/`'s `base.lanes`/`tech.laneId` reads keep
  typechecking unchanged, just now over a reshaped row model they don't know about yet. The
  rename is tracked as the next slice's (the renderer re-wire's) own work.

  **2. Localisation `$key$` token resolution, extended to every displayed string.**
  `_resolve_loc_tokens` existed already (built for `configGatedSubject`, D-13/P-13) but was never
  applied to technology `name` — the reason raw tokens like `$PLANET_LANCE_BLOKKAT$` and
  `$waystation_plural$` reached rendered cards. Real corpus survey found **161/980 rendered names**
  (16.4%) and **223/980 descriptions** (22.8%) carried at least one unresolved token before this
  fix. **The `$waystation_plural$` (no closing `$`, extra trailing `s`) shape the user reported was
  checked against raw localisation source directly, not guessed at**: `tech_waystation_1`'s real
  raw name is exactly `"$waystation_plural$"` (19 chars, properly closed, no trailing `s`) — the
  corpus does NOT genuinely contain an unterminated token here; whatever the user saw was a
  display-side artefact of the pre-fix raw-token render, not a corpus data defect, and the fix
  (full resolution to "Waystations") makes the question moot either way since no raw token reaches
  the card anymore.

  **A real, second bug found while fixing the first**: `_resolve_loc_tokens`'s old algorithm
  replaced only the FIRST `$...$` match per hop, needing one extra hop per SIBLING token at the
  same nesting level, not per real nesting level — invisible while its only caller
  (`configGatedSubject`) never had more than one token per level in its 50 real chains, but a real
  failure once technology names started resolving through it: `tech_civilian_arkship`'s name
  chains through `"$civilian_arkship_class$ $arkship_cap_plural$"` — two SIBLING tokens on one
  line. Fixed to resolve every occurrence in the current text per pass (one `re.sub`, not
  `re.search`-then-replace-first); hop count now tracks true nesting depth only. Measured real max
  depth: 3 hops (names), 4 hops (descriptions) — `_LOC_TOKEN_MAX_HOPS` raised from 3 to 6 (measured
  max plus headroom, not a guess). **All 980 names and all 980 descriptions resolve cleanly with
  zero failures** under the corrected algorithm.

  **Applied to**: technology `name` (base dataset, hard-fail), detail-payload `description`
  (upgraded from strip-only to full resolution, hard-fail), and category row `label`s (new field
  this session, hard-fail) — all through a common `_require_resolved` helper. **Left as
  strip-only, deliberately not extended this session**: nothing else — `_swap_display_name`
  (swap names) and `_config_gated_subject` already routed through `_resolve_loc_tokens` before this
  session and needed no change beyond inheriting the sibling-token fix; the search index derives
  from already-resolved `name`/`description` so needs no separate change.

  **New hard build failure** (`UnresolvedLocalisationTokenError`, CLAUDE.md's Rules: "the build
  fails rather than emitting a partial dataset... missing localisation for displayed strings"):
  raised by `_require_resolved` whenever `_resolve_loc_tokens` returns `None` for a technology
  `name`, `description`, or category row `label`. Zero real occurrences at time of writing — this
  is a tripwire, not a check expected to fire. **Proven capable of firing before being trusted**
  (CLAUDE.md's own rule: "a clean run proves nothing until the detector is shown capable of a
  dirty one"): `tests/test_dataset_emit.py::
  test_unresolved_localisation_token_in_a_name_fails_the_build` feeds a deliberately-broken
  fixture (a token absent from the loc table) and asserts the raise.

  **Real measured browser performance** (Chrome, real hardware WebGL, not the sandbox's
  software-WebGL fallback the earlier edge-density measurement used): median 6.1ms / p95 12.1ms
  per frame across idle, dense-region-panning, and zoom-crossing runs. Comfortably inside a 16.7ms
  (60fps) frame budget with real margin. Viewport culling was measured (slice 2) and deliberately
  rejected as unnecessary complexity for a 980-node/989-edge scene at this stage — this real-
  hardware figure confirms that call rather than reopening it; it is not re-litigated here.

  **Defect-detection note, worth its own line rather than folding silently into the fix above**:
  the sibling-token bug in `_resolve_loc_tokens` (fixed in the prior session, "Stage 2 row re-axis
  + localisation token resolution" above) went undetected by that session's own test suite for the
  same reason `pipeline.layout.is_repeatable`'s `levels < 0` bug did (HANDOFF.md's "Methodology"
  section) — its 50 real test cases (the `giga_tech_repeatable_*_cap` `configGatedSubject` chains)
  each happened to carry exactly one token per nesting level, so a test asserting "all 50 resolve"
  passed while exercising only the single-token code path; nothing forced a multi-sibling-token
  case through it until `name` resolution started routing real technology names (like
  `tech_civilian_arkship`'s two-sibling-token chain) through the same function. A green suite
  proved the fix self-consistent with its own fixtures, not correct in general — the same
  distinction HANDOFF.md draws for `is_repeatable`.


## `pipeline/edges.py` — edge typing (P-14)

The three edge kinds (`prerequisite`/`alternative`/`potential-gate`), scope discipline, diagnostics.

- **P-14 full edge typing is built** (later session): `pipeline/edges.py` — the last structural
  gap in Stage 2 before dataset emission. Layout previously built `prerequisite` edges only
  (`pipeline.overwrites.ordered_prerequisites`, called from `pipeline.layout._route_edges`); all
  three P-14 kinds are now real, extracted and typed:
  - **`prerequisite`** — `pipeline.overwrites.ordered_prerequisites`, corrected to exclude nested
    `OR`-branch members (see "Prerequisites" above) — 888 edges.
  - **`alternative`** — `pipeline.overwrites.alternative_prerequisite_groups`, the OR-branch
    members `ordered_prerequisites` used to wrongly flatten in — 76 edges across 35 groups (32
    technologies), each group carrying a `groupId` (`f"{owner}#alt{index}"`,
    `pipeline.edges.extract_alternative_edges`).
  - **`potential-gate`** — `pipeline.edges.extract_potential_gate_edges`, `potential`-only,
    scope-disciplined to match `pipeline.availability._evaluate_node` exactly (only descend into
    `AND`/`OR`/`NOT`/`NOR`; any other block-valued field is an opaque leaf) — 25 edges. This
    discipline is load-bearing, not style: an earlier, unscoped draft of the extraction found a
    false self-loop on `tech_ehof_sentient_tier_7`, whose `potential` nests
    `has_technology = tech_ehof_sentient_tier_7` inside `count_country = { limit = { OR = {...}
    } } }` — checking OTHER empires in the galaxy for a scarcity mechanic, not the researching
    empire's own state.
    `tests/test_edges.py::test_count_country_nested_has_technology_does_not_produce_an_edge` and
    `tests/test_layout_corpus.py::test_tech_ehof_sentient_tier_7_has_no_self_loop_edge` are the
    permanent regression guards.

  **Two standing diagnostics** (`pipeline.edges.EdgeExtractionDiagnostics`, never a build
  failure): `has_technology_under_allow` (P-3's "potential and allow" framing is aspirational —
  `allow` never occurs on a rendered technology today, 0/980, verified; fires if a future mod
  update introduces one) and `negated_potential_gate` (a `has_technology` inside an odd `NOT`/
  `NOR` nesting is a negative dependency with no `EdgeKind` representation today — 0 real
  occurrences; excluded from edge output and diagnosed rather than emitted as a wrong-polarity
  edge). Both confirmed empty on the real corpus
  (`tests/test_layout_corpus.py::test_no_has_technology_under_allow_on_real_corpus`,
  `::test_no_negated_potential_gate_on_real_corpus`).

  **Edge-kind membership is NOT mutually exclusive per `(from, to)` pair** — 4 real pairs are both
  a `prerequisite` and a `potential-gate` (e.g.
  `tech_mega_engineering -> giga_tech_arkship_neutronium_harvester`); both are emitted as distinct
  `TypedEdge` records. Collapsing them for display, if ever wanted, is a Stage 3 rendering
  decision over the emitted data, not a data-model one (`spec/P-14-unconventional-prereqs.md`).

  **P-16's rendering-scope closure stays `prerequisite`-only**, decided on evidence
  (`spec/P-16-mod-requirements.md`): recomputing it with `alternative` treated as traversable
  changes nothing on the real corpus (identical 7-technology closure, identical 980 rendered
  nodes, all four "supertensile" trigger technologies reach ACOT/AoT via a true prerequisite
  chain). The forward-looking risk is mitigated by a standing diagnostic, not a closure change:
  `pipeline.rendering_scope.compute_alternative_only_gaps`, empty on the real corpus
  (`tests/test_rendering_scope.py::test_real_corpus_has_no_alternative_only_gaps`).

  **`pipeline/rendering_scope.py` and `pipeline/crisis_faction.py` needed zero code changes** —
  both already consumed `ordered_prerequisites()`, so correcting that function to exclude
  `OR`-branch members fixed both automatically. Measured effect of the fix (Task 1's audit, before
  implementing): `crisis_faction.py`'s D-7 step-2 inheritance — a real 0-technology change (no
  real-corpus classification ever actually depended on an OR member); `pipeline.layout`'s internal
  `computed_position` (never displayed, D-13) — 142 nodes shift by 1-3 internally, with **canvas
  dimensions and densest band cell confirmed unchanged** (12,544×8,146px, Standard×T5=253) since
  bands are declared tier and `computed_position` only orders within a band — asserted explicitly
  in `tests/test_layout_corpus.py::test_densest_actual_band_cell_and_canvas_dimensions`'s own
  docstring, not just carried as an assumption. `pipeline/availability.py` was confirmed to never
  consume `prerequisites` at all (P-16's per-profile structural-reachability check — the consumer
  that WOULD have turned OR-conflation into a false `locked` result — is specified but still not
  built; fixing the flattening now, before that check exists, is exactly the point: the bug was
  free to fix today and becomes a reachability bug the moment that check is written against the
  conflated list).

  **Final real figures, over the 980-node rendered set** (`tests/test_layout_corpus.py`,
  `tests/test_edges.py`, `tests/test_rendering_scope.py`): **989 total edges = 888 prerequisite +
  76 alternative + 25 potential-gate.** Sink property holds over the full set: 906
  non-repeatable-to-non-repeatable + 83 non-repeatable→repeatable = 989, 0 repeatable→non-
  repeatable, 0 repeatable→repeatable. Backward: 34 = 25 + 2 + 7 (see the "Tiers" section above
  for the full reconciliation against the earlier 27/891 and 27/881 figures). `schema/
  common.schema.json`'s `Edge` gained `groupId` (nullable, `alternative`-only) and `bandSpan`
  (signed, every edge); TS types regenerated; the one Edge-bearing schema fixture updated;
  `pipeline/geometry.py`'s `pack_edge_polylines` index dicts gained the same two fields.
  `spec/P-14-unconventional-prereqs.md`'s Requirement section reworded: an earlier draft described
  `alternative` as a profile-relative relabeling of whichever kind is "active" for the selected
  empire profile, which is architecturally impossible (`Edge.kind` lives in the profile-invariant
  base dataset; only the *active edge set* varies per profile, in the empire-overlay artefact) —
  `alternative` is, and operationally always was, the nested-`OR`-inside-`prerequisites`
  construct P-08 already defined edge direction for. `spec/P-08-connectors.md`'s backward-edge
  characterization ("1-2 bands back, small and short-range") is now explicitly rescoped to
  `prerequisite`/`alternative`; `potential-gate`'s real distribution (up to 5 bands back) is
  recorded separately with its own `TODO(Stage 3)` routing decision, deliberately not designed
  here. Tests: `tests/test_edges.py` (synthetic, mechanism coverage — scope discipline, group IDs,
  the count_country regression, the two diagnostics, dual-kind pairs),
  `tests/test_overwrites.py`/`tests/test_overwrites_corpus.py` (updated for
  `ordered_prerequisites`'s corrected contract and the new `alternative_prerequisite_groups`),
  `tests/test_rendering_scope.py` (the new tripwire diagnostic), `tests/test_layout.py`/
  `tests/test_layout_corpus.py` (the full three-kind edge set wired through real layout output).

## `pipeline/dataset_emit.py` — Stage 2 dataset emission

Assembly and schema validation of all five artefacts; the cost/costPerLevel/localisation-token correctness passes; icon-candidate expansion fix.

- **Stage 2 dataset emission is built** (later session): `pipeline/dataset_emit.py` assembles all
  five schema'd artefacts from every already-built Stage 2 component (P-15 overwrites, P-13
  availability, P-16 rendering scope, D-7 crisis faction, P-2/P-14 layout+edges, filtered icon
  atlases) and validates every one against its schema as part of the build
  (`pipeline.dataset_schema.validate_*`) — an invalid artefact raises during assembly, never a
  separate optional check. `tests/test_dataset_emit.py` runs the real build end to end against the
  vendored corpus: all 980 technologies, all 989 edges, all 12 empire overlays, all 980 detail
  payloads, the search index, and diagnostics — every one schema-valid, plus a direct
  `availabilityMatrix`/overlay consistency cross-check
  (`pipeline.dataset_schema.empire_profile.check_availability_matrix_matches_overlays`).

  **Real measured base-dataset transfer size: ~64 KB compressed** (65,585 bytes: 54,264 JSON +
  2,911 node side-file + 8,410 edge side-file, gzip level 9) — comfortably under P-10's 2 MB
  budget, but a real finding worth its own writeup rather than a quiet update: the pre-build
  projection was ~275-305 KB, and the **real measured compression ratio is 14.29x**, well above
  the 6-9x range the projection assumed (itself drawn from the deploy-spike's 9.34x synthetic
  ratio, with an explicit caveat that real content should compress *worse* than synthetic, not
  better). The projection held directionally (comfortably under budget) but its specific method
  was wrong, not just imprecise: the deploy-spike's synthetic ~1,878-record blob was dominated by
  free-text name/description-shaped content, while the real base dataset's size is dominated by
  small, highly-repetitive structured JSON — 980 near-identically-shaped technology records, each
  carrying a 12-slot enum array (`availabilityMatrix`), mostly-empty arrays (`gates`, `requiresMods`
  for 95%+ of nodes), and `null` (`crisisFaction` for 925/980) — exactly the shape gzip compresses
  far better than prose. Free-text content (descriptions) isn't even in the base dataset; it's in
  the lazy detail payloads. The lesson: a synthetic-content compression estimate is not a reliable
  stand-in for real structured-JSON compression, in either direction — re-measure against the real
  shape once it exists, don't extrapolate from a differently-shaped proxy.

  **Other four artefacts, measured for the first time** (never part of P-10's budget, but Stage 3's
  loading design needs real numbers): empire overlays ~486 KB raw / ~43 KB gz each (12 total: 5.8 MB
  raw / 512 KB gz); detail payloads 630 KB raw combined, 384 KB gz fetched individually per
  technology vs. 90 KB gz if batched into one file (batching wins substantially — worth deciding
  before Stage 3 commits to a fetch granularity); search index 297 KB raw / 64 KB gz; diagnostics
  48 KB raw / 4.4 KB gz.

  **Real finding, not a bug in this emission code**: `unconditionalUncertainty.count` is **259**
  (26.4%), not the previously-published **209** (21.33%) — CLAUDE.md's "Availability evaluator"
  section below is corrected to match. Same evaluator, same 980-node closure; the difference is
  that `pipeline/dataset_emit.py` evaluates `potential` blocks from `inline_script`-EXPANDED
  technology definitions throughout, while `tests/test_availability_corpus.py` (the source of the
  209 figure) parses raw, unexpanded blocks. All 50 `giga_tech_repeatable_*_cap` technologies —
  the exact same group P-2's tier-source audit already found only gets a `tier` field via
  `inline_script` expansion — likewise only get their real `potential` field via expansion; on the
  raw block they have no `potential` at all, so the unexpanded survey silently treats all 50 as
  unconditionally AVAILABLE regardless of their actual (real, inline_script-supplied) gating
  condition. 259 − 209 = 50, exactly the cap-group size — confirmed directly, not inferred from
  the arithmetic coincidence alone (`tests/test_dataset_emit.py::
  test_diagnostics_validates_and_reports_the_unconditional_uncertain_finding` asserts every one of
  the 50 has a real `potential` block post-expansion). ~~`tests/test_availability_corpus.py` itself
  is not fixed in this session.~~ **Fixed in the following Stage 2 cleanup session** — see this
  file's "Availability evaluator" section for the full writeup, the re-seeded ratchet, the moved
  category-distribution proportions, and the defect-class note this joined. The profile-dependent
  worst-case figure (3.37%) is UNCHANGED and matches exactly — expansion only affects technologies
  whose `potential` itself is inline_script-templated, and none of those 50 happens to be the
  profile-dependent worst case.

  **Known v1 scope limitations** (each schema-valid, none silently fabricated — see the module
  docstring for the full list): `appliesToEmpireTypes` is unconstrained on every edge (a real
  per-edge empire-type constraint extractor is new scope beyond what P-14 built); `activeEdgeIds`
  is therefore every edge index for every profile; `gates` is always `[]`
  (P-3's gate-pattern-registry classification pass isn't built — already tracked as open before
  this session); `repositoryLink`'s wiki URLs aren't live-validated (no network access) and its
  `lineRange` uses the block's start line for both ends (no end-of-block line is tracked in the
  AST). ~~`swapMappings` is always `[]`~~ **Closed in a later session — see D-14 below.**

- **Small targeted correctness pass, prompted by a manual review of `giga_mega_repeatable.txt`**
  (later session, three independent items):

  1. **Boolean-operator case-sensitivity — audited, not a bug.** The template's `potential` block
     uses lowercase `not = { has_global_flag = $name$_disabled }`. Both walkers that descend only
     into `AND`/`OR`/`NOT`/`NOR` (`pipeline/availability.py`'s `_evaluate_node`,
     `pipeline/edges.py`'s `_scoped_has_technology`) already normalise to uppercase before
     comparing (`key.upper()`) — confirmed by reading the code, not assumed from the earlier
     "case-insensitive" claim. **Real corpus case survey, scoped to `potential` blocks across all
     1,879 canonical technologies**: `NOT`=111/`not`=50, `OR`=62/`or`=5, `AND`=29 (0 lowercase in
     this scope), `NOR`=17 (0 lowercase in this scope). **54 distinct rendered technologies carry
     a lowercase operator in `potential`** — 50 are the `giga_tech_repeatable_*_cap` family (all
     `not`), but **4 are outside it** (`giga_tech_birch_world_1` — 2×`or`,
     `giga_tech_planetary_seeder_nexus`, `tech_qnm_disruptors`, `tech_sm_autocannons` — 1×`or`
     each), confirming lowercase isn't confined to the repeatable-cap family, as expected. No fix
     needed; added a case-insensitivity regression test to `pipeline/edges.py`'s test suite
     (`tests/test_edges.py::test_extract_potential_gate_edges_boolean_wrappers_are_case_insensitive`
     — this walker had none before) and extended `pipeline/availability.py`'s existing one to
     cover lowercase `and`/`nor` too (it only covered `not`/`or`).

  2. **`cost`/`costPerLevel` added to the base dataset.** Neither was carried in
     `schema/base-dataset.schema.json` before this session — `cost` wasn't in the schema at all
     despite `00-overview.md`'s glossary naming "research cost" as a card field, and repeatables'
     `cost_per_level` (the real v1 gap: a repeatable card showing only the bare first-level cost
     misrepresents the commitment) existed nowhere in any artefact. Added: a top-level `cost`
     field (`number | null` — null when unresolvable, never guessed/defaulted to 0, matching D-4's
     "no evaluated weight" discipline) and `repeatable.costPerLevel` (`number | null`, required
     alongside `levels` whenever `repeatable` is non-null). **Decision, recorded in
     `spec/P-02-layout.md`'s new "Cost display" section**: base `cost` is the primary displayed
     figure, `costPerLevel` a secondary indicator — in-game cost shifts heavily with empire size
     and other live modifiers, so any absolute number is approximate regardless of which is shown;
     the scaling RATE is the one thing the card can state truthfully for a repeatable technology.
     Exact visual treatment is Stage 3's; this session emits semantic data only. **Real corpus,
     verified**: exactly the 88-node repeatable set carries a resolvable `costPerLevel` (0
     non-repeatable technologies do). Separately (found while wiring `cost` itself, not part of
     the original ask): **15 of 980 rendered technologies have an unresolvable `cost`** — 5 with
     no `cost` field at all (apparently-free starting technologies:
     `tech_missiles_1`/`tech_flak_batteries_1`/`tech_solar_panel_network`/others) and 10 vanilla
     "cosmic storm" technologies whose `cost` is a dynamic modifier block
     (`cost = { factor = @var inline_script = {...} }`, a previously-unseen shape in this
     codebase's cost handling) rather than a scalar — both emit `cost: null`, never a guessed
     value. TS types regenerated; all four base-dataset fixtures updated; `tests/schema/
     test_validation.py` and `tests/test_dataset_emit.py` gained coverage for both fields.

  3. **`pipeline/icons/resolve.py`'s raw-block gap — closed.** The previous session's audit found
     `collect_candidates` read raw, unexpanded technology/ascension-perk blocks unconditionally,
     with no way to supply expanded documents — the same shape as the defect class above (tier
     resolution, `unconditionalUncertainty`), just not yet triggered for icons.
     `collect_candidates`'s signature changed from `(source_name, Path)` to
     `(source_name, Document)` pairs; `pipeline/icons/build.py::resolve_kind` now parses AND
     `inline_script`-expands every technology/ascension-perk document itself (mirroring
     `pipeline/dataset_emit.py`'s own loading pattern) before handing it to `collect_candidates`.
     **Verified zero-impact on the real corpus, as predicted**: every existing exact-count
     assertion (2,103/19 unfiltered, 1,192/4 filtered technology candidates; 63/6 ascension-perk
     candidates) passed unchanged after the fix, including the SPECIFIC unresolved-candidate key
     lists — strong enough evidence of byte-identical results that no separate diff was needed.
     Added `tests/icons/test_resolve.py::
     test_collect_candidates_sees_an_inline_script_supplied_icon_field`, a synthetic template that
     DOES define an `icon =` field, proving the expanded-vs-raw distinction actually matters (raw
     input falls back to filename convention; expanded input picks up the template's icon) rather
     than merely proving the plumbing compiles.

## `pipeline/overwrites.py` — technology-block overwrite resolution (P-15)

Whole-key resolution, field-level diffing, scripted-variable overwrite layer.

- **P-15 overwrite resolution is built**: `pipeline/overwrites.py` (technology-block whole-key
  resolution, field-level diff against the immediately-preceding definition in load order —
  never hardcoded to vanilla — cost/weight compared through `@variable` resolution with the raw
  pre-resolution form retained alongside, prerequisites/category diffed as sets, flags diffed as
  a single composite field, declaration-order prerequisite display list kept separate from the
  diff) plus `pipeline/overwrite_overrides.py` (loader for `config/overwrite_overrides.txt`,
  seeded empty — no case in the corpus needs one; format and required-warning mirror
  `pipeline/icons/overrides.py`). `pipeline.overwrites.resolve_variable_overwrites` is the
  distinct scripted-variable overwrite layer (Finding 5: a technology's effective cost/weight can
  change without its own block being touched). Tests: `tests/test_overwrites.py` (synthetic,
  mechanism coverage), `tests/test_overwrite_overrides.py` (loader), `tests/test_overwrites_corpus.py`
  (real vendored corpus, skipped when `vendor/` isn't populated — asserts the corrected 25-overlap
  survey counts so a future corpus refresh that silently changes them fails a test). `schema/`
  (`common.schema.json`'s new `SourceMod` def, `detail-payload.schema.json`'s `source`/
  `overwriteDiff`, `diagnostics.schema.json`'s two-section `overwriteReport`) and
  `spec/P-15-overwrites.md` were updated to match — overwriting is not vanilla-only, and most of
  the corpus's overwrites (19 of 25) have no vanilla baseline at all. (Status at the time this
  bullet was written: trigger evaluation, tier/layout/edge computation and dataset emission were
  still open — all but dataset emission are built now; see the later bullets in this section and
  HANDOFF.md's "Ordered next steps" for current status.)

## `pipeline/technology_swaps.py` — `technology_swap` substitution (D-14)

Axis-expressible vs. non-axis swap classification, per-profile name/icon substitution.

- **D-14: `technology_swap` per-profile name/icon substitution is built** (later session,
  prompted by a report that a bio-shipset player's card would show "Fission Power," a name that
  doesn't exist in their game). `pipeline/technology_swaps.py` (new module) parses every
  `technology_swap` sub-block and classifies its trigger against `pipeline.availability.AXIS_FACTS`
  (the SAME dict the evaluator uses for `potential` blocks — reused directly rather than a second,
  competing axis-leaf definition). **Real corpus: 214 swaps across 185/980 rendered
  technologies — 128 axis-expressible, 86 non-axis** (corrected from a pre-implementation
  ad-hoc survey's 126/88: `AXIS_FACTS` also resolves `is_mechanical_empire`/`is_robot_empire`/
  `is_regular_empire`, which that survey's own classification omitted).

  **Two treatments, never a third.** Axis-expressible swaps (128 swaps / 123 technologies)
  substitute per profile — `schema/empire-overlay.schema.json`'s `swapMappings` is redesigned
  (the old `{baseTechnologyId, activeVariantId}` shape assumed a variant had its own node id,
  which D-1's "a swap never becomes its own node" rules out) to carry
  `{technologyId, name, icon, area, category}` directly, `area`/`category` null meaning
  "unchanged from base." Non-axis swaps (86 swaps / 72 technologies — origin/civic/species-trait/
  ascension-perk/galaxy-situation leaves the 3-axis model can't express) NEVER substitute — listed
  instead in the detail payload's new `variants` field (`{name, icon, conditionText}`,
  `conditionText` via `pipeline.trigger_text.describe_condition`/new `describe_trigger_block`),
  popup-only, same precedent as ascension-perk gates. 10 technologies carry both (one swap
  substitutes, a different swap on the same technology lists as a variant). **The rendered node
  count stays exactly 980 regardless — asserted directly, not left as an unstated consequence.**

  **`tech_ring_world` exception, decided explicitly in chat, no special-casing**: its 2 swaps mix
  one axis leaf (`country_uses_bio_ships`) with one non-axis leaf
  (`giga_can_use_habitables`) in a single compound trigger — treated as WHOLLY non-axis (matches
  the evaluator's own Kleene "no partial credit on a compound condition" discipline). Cost is
  named: `tech_ring_world` keeps its base `society`/`voidcraft` presentation for every profile,
  with all 3 of its non-axis swaps listed as popup variants instead. Of the real corpus's 8
  area/category-changing swaps, all 8 fall out of this same classification for free — 6
  axis-expressible bio-shipset ones substitute automatically, `tech_ring_world`'s 2 non-axis ones
  never do — no separate area/category mechanism was needed.

  **Icon inheritance, item 6**: one real swap, `giga_tech_ring_world_swap_no_habitables`, declares
  `inherit_icon = no` with no icon file of its own. `pipeline/icons/resolve.py` still correctly
  leaves it an unresolved atlas candidate (unchanged — redirecting AT THAT LAYER would override an
  explicit authorial refusal, per that module's own docstring). A SEPARATE, presentation-layer
  fallback in `pipeline.dataset_emit`'s `_swap_icon_ref_map` shows the owning technology's icon for
  display instead, tracked via the new `diagnostics.swapsRenderingOnInheritedIcon`
  (`{technologyId, swapKey}[]`) — today exactly this one entry, confirmed to never fire for the 87
  swaps that legitimately keep the base icon via `inherit_icon` defaulting to `yes` (those resolve
  through the ordinary channel and are never `unresolved` candidates). No `config/
  icon_overrides.txt` entry was used deliberately — that would need a human to notice and remove it
  once upstream ships a real icon, and would silently shadow it until they did; the fallback
  instead yields automatically the moment a real icon resolves.

  **Trigger-text coverage gap reported, not invented**: 9 non-axis leaf names have no dedicated
  `describe_condition` phrasing and fall back to raw trigger text —
  `is_wilderness_empire` (41, by far the largest), `is_beastmasters_empire` (16),
  `giga_can_use_habitables` (3), `is_tankbound_empire`/`is_reanimator`/`is_eager_explorer_empire`
  (2 each), `has_void_dweller_origin`/`is_cloning_authority`/`is_situation_type` (1 each) — an open
  item for `pipeline/trigger_text.py`'s phrase table, not silently accepted or papered over.

  **`weight` (94/214 swaps) and `prereqfor_desc` (39/214) remain deliberately unsurfaced**,
  consistent with D-4's no-evaluated-weight precedent — seen during this decision's own survey,
  recorded so a future session knows it wasn't missed.

  **Real payload delta, measured**: the base dataset itself (P-10's budget) is unchanged —
  `swapMappings`/`variants` live in the lazy empire-overlay/detail-payload artefacts.
  `swapMappings` across all 12 overlays adds **~17.5 KB gzip** (~141 KB raw, 745 entries);
  `variants` across all 980 detail payloads adds **~2.8 KB gzip** (~15 KB raw, 86 entries) —
  both small next to the ~64-67 KB base-dataset reference point, well above the
  pre-implementation ~9.7 KB gz worst-case guess (icon-ref objects are heavier than bare
  strings) but nowhere near a concern either way. See `spec/decisions.md`'s D-14 for the full
  writeup. Tests: `tests/test_technology_swaps.py` (synthetic classification, including the
  compound-trigger and `is_robot_empire` cases), `tests/test_dataset_emit.py`'s D-14 section
  (real-corpus substitution/variant/icon-inheritance/payload-delta assertions).

## Deploy pipeline (D-15)

The original deploy-spike prototype (superseded, deleted) and its historical findings, later replaced by the real `tools/build_dataset.py`/`tools/deploy_local.sh` pipeline (see CLAUDE.md's D-15 summary and the Stage 3 toolchain entry below for the real pipeline).

- ~~**Deploy spike confirms P-10's compressed-transfer assumption.**~~ **Superseded, later
  session — `deploy-spike/` is deleted, replaced by the real pipeline below**, which re-confirms
  the same findings (relative-path base resolution, real hosting round-trip) against the ACTUAL
  toolchain and dataset rather than a throwaway synthetic stand-in. Historical record of what the
  spike proved before deletion: GitHub Pages serves both a JSON artefact and a binary typed-array
  side-file gzip'd (9.34x measured on a ~982 KB synthetic dataset), confirming P-10's ≤2 MB
  compressed-transfer budget assumption wasn't speculative.


## Pre-implementation survey records (P-16 closure, D-10 projection, layout model, research path, Stage 2 build sequencing)

Moved verbatim from HANDOFF.md, which carried these as hand-measurement / pre-code survey narratives before each was superseded by real, tested pipeline code (`pipeline/rendering_scope.py`, `pipeline/availability.py`, `pipeline/layout.py`, `pipeline/dataset_emit.py`'s `_build_research_paths_for_profile`). Kept for the historical figures and reasoning chains each one records — every later correction traces back to one of these.

## Vendor-backed corpus counts

| | Count | Δ vs. pre-re-vendor |
| --- | --- | --- |
| Clausewitz scoped corpus (`common/{technology,scripted_variables,scripted_triggers,ascension_perks}` + reachable `inline_scripts`, 4 sources) | 273 files, 0 parse errors | unchanged |
| Total technology-shaped definitions (`common/technology`, all occurrences across 4 sources, pre-overwrite-resolution) | 1,904 | new figure, not previously tracked as its own row |
| Distinct technology keys | 1,879 | unchanged (`tech_mega_engineering`'s key already existed in vanilla; the re-vendor added an *occurrence*, not a new key) |
| Round-trip allowlist entries | 434 | +1 (one new adjacency-only divergence in refreshed `giga_frameworld_triggers.txt`, reviewed) |
| Localisation (`localisation/english`, 4 sources, filename-suffix discovery) | 353 files, 0 file-level failures, **193,548** resolved keys | resolved keys **+52** (Gigastructures localisation content advanced along with the technology content when re-vendored to the pinned commit — same root cause, not a new one) |
| Localisation malformed entries / value-is-key diagnostics / unquoted-value diagnostics | 2 / 134 / 1 | unchanged (same files and lines) |
| Technology icon candidates (technologies + `technology_swap` alternates) | **2,122** candidates, **2,103** resolved, 19 unresolved | candidates/resolved **+1/+1** (the new `tech_mega_engineering` occurrence in Gigastructures is one more pre-resolution candidate, and it resolves cleanly against vanilla's existing icon); unresolved list unchanged, same 19 keys |
| Ascension-perk icon candidates (perks + `tradition_swap` alternates, 3 sources — AoT has none) | 69 candidates, 63 resolved, 6 unresolved | unchanged |
| Cross-source icon-file collisions (same relative path, >1 source) | 31 | unchanged |
| Technology atlas sheets (2048×2048 cap, WebP lossless), UNFILTERED | 4 sheets: 1008×2016 ×3, 1008×118; 8,387,616 bytes | corrected: this row's byte figure was previously mislabeled as 8,650,292 (that was tech+perk combined, see below) |
| Technology atlas sheets, FILTERED to P-16's 980-node rendered set (later session) | 2 sheets: 1008×2016, 1008×1468; 4,564,314 bytes | new row — the real build path now uses this, not the unfiltered row above |
| Ascension-perk atlas sheets (never filtered — see rendering-scope note below) | 1 sheet: 504×384; 262,676 bytes | byte figure added this session |
| Technology-block overwrites (P-15, corrected corpus) | 25: 2 `Gigastructural Engineering`×`Vanilla`, 4 `ACOT`×`Vanilla`, 19 `ACOT`×`AoT`, 0 chains of 3+ | n/a — this row only exists post-re-vendor |
| Scripted-variable overwrites feeding a technology's cost/weight (P-15) | 4 (`acot_tier6cost2/7cost2/8cost2/9cost2` — Gigastructures' compat-fallback stubs, overwritten by ACOT's real definitions when ACOT is present) | n/a — this row only exists post-re-vendor |

Full pytest suite: **1,114 passed, 0 failed** (`pytest tests/`).

**Verification pass, run explicitly after the re-vendor** (not assumed from "the icon test suite
stayed green"): every figure above was recomputed against the refreshed corpus and compared
against the numbers recorded before the re-vendor (`tests/localisation/test_corpus.py::test_full_corpus_report`,
`tests/icons/test_icon_corpus.py`, a direct parse/glob over `common/technology`, and the
round-trip suite). Every moved figure has an identified, single-cause explanation (Gigastructures'
own content growing between the stale Workshop snapshot and the pinned `Live-Branch` commit) —
nothing moved for an unexplained reason, and nothing that should have been stable (parse failure
counts, malformed-entry counts, diagnostic counts, other three sources' figures, atlas byte
total) actually moved.

**Gigastructures vendored snapshot was corrected mid-session.** The original snapshot (Steam
Workshop download, hash `0b60eb7186bba531`) was stale relative to GitHub's `Live-Branch` — it was
missing a real overwrite (`tech_mega_engineering`, added to `zz_giga_tech_overwrites.txt`), which
the P-15 survey's first pass correctly reported as absent because it genuinely was absent from
that snapshot, not because of a scan defect. Re-vendored to commit
`0f1f2b024f43249dc7dfe132fe7c0e4201398ef5` (tag `v3.39.3`, `Live-Branch`, confirmed by the user to
match the Steam Workshop release in content relevant to this tool) — see `vendor/manifest.json`
and CLAUDE.md's "Source data" section for the full provenance and the still-open collector gap
(GitHub fetch + commit pin + scheduled CI for Gigastructures is specified but not yet
implemented; this snapshot was pinned manually). One new round-trip allowlist entry was added
for content only present in the refreshed snapshot
(`vendor/mods/gigastructures/common/scripted_triggers/giga_frameworld_triggers.txt:1045` — a
missing space before `=`, reviewed as adjacency-only per the usual bar) — full suite re-ran green
after the refresh.

**Empire-type edge shape, confirmed against the corpus:** every real `prerequisite`/
`potential-gate`/`alternative` edge's empire-type applicability factors as a product of
independent axis constraints (25 `has_technology`-plus-axis-fact sites inspected raw; each is
either unconstrained or a single-axis rectangle — never an irregular union spanning multiple
axes). This is what licenses `schema/common.schema.json`'s `EmpireTypeConstraint` shape
(per-axis arrays, no flat 12-enum, no bitmask in JSON) — it isn't an assumption, it's a checked
finding.

**The "17 parse failures in `scripted_triggers/`" open item: resolved, not lost.**
`tests/fixtures/NOTES.md`'s "Scripted-triggers grammar gaps" section documents 17 real parse
failures found rescoping the Clausewitz corpus run to the four required directories, confined to
`scripted_triggers/` plus one `inline_scripts/` file, across six grammar constructs (conditional
`[[GUARD] ... ]` blocks, pipe-delimited `value:name|K|V|` calls, `$NAME|default$`, `$SCOPE$?`,
bare mid-token `$PARAM$` substitution, inline arithmetic `@[ ... ]`). All six were fixed earlier
in this project's history — before the round-trip/localisation/icon/schema work in this
document, not during it. **Verified fresh this session**, not just inferred from history: a
direct re-parse of the full 273-file scoped corpus, including every `scripted_triggers/` file,
right now, produces **0 parse failures**. The item dropped out of this file's rewrite because it
was resolved, not because it was forgotten — recorded here explicitly now specifically so that
ambiguity can't recur. If this count is ever non-zero again, that's a real regression in the
tokeniser/parser grammar, not a residual item finally being noticed.

## Recorded diagnostic sets — what exists, what's still undecided

Every one is a *diagnostic*, not a build failure, by deliberate design. Deciding whether any
should fail the build is explicitly left to Stage 2, not guessed at in Stage 1.

- **`roundtrip_allowlist.json`, 434 entries.** Reviewed, closed, all adjacency-only. A maintained
  list, not an open question.
- **`ValueIsKeyDiagnostic`, 134 hits.** A key's winning value is verbatim another key that exists
  in the resolved table — almost certainly an unfinished translation. Narrowed to values
  containing `_`; an unrestricted check returned 3,370 hits of which 2,854 were ordinary
  self-referential English words (`OK` → `"OK"`), a legitimate Paradox convention. **Do not
  re-widen this check blind** — the false-positive count is in the diagnostic's docstring.
  **Undecided**: whether Stage 2/3 treats any as build-blocking.
- **`UnquotedValueDiagnostic`, 1 hit** (`acot_omegan_blessed`). Parsed as valid, not malformed,
  but flagged because one occurrence in ~194,000 lines isn't enough to call the shape reliable.
  **Undecided**: nothing actionable; exists so a future rise is visible rather than absorbed.
- **`LocalisationTable.malformed`, 2 hits**, both ACOT, both real upstream typos. No local fix.
  These become failures only if the affected key is looked up via `.require()` for a displayed
  string; `.get()` returning `None` is the harness. This is the intended terminal state.
- **`IconResolutionResult.unresolved`, 19 technology/swap + 6 ascension perk.** See the two
  `TODO(Stage 2)` blocks in `pipeline/icons/resolve.py` in full. Summarised:
  1. **Scope-conditional failure.** Recorded uninterpreted; Stage 1 does not know which are
     permanently-unreachable technologies (needs trigger evaluation) versus real gaps. The one
     unambiguous real gap (`giga_tech_ring_world_swap_no_habitables`, explicit `inherit_icon = no`
     with no shipped icon) is deliberately left unresolved rather than guessed at. The 6
     ascension-perk cases (`ap_colossus`, `ap_eternal_vigilance_nomads`,
     `ap_organo_machine_interfacing_assimilator`, three `ap_galactic_wonders_*` DLC variants)
     have not been individually investigated — likely DLC-conditional perks resolved through a
     mechanism this model doesn't cover, but that's a guess, not a finding.
  2. ~~**Atlas content scope.**~~ **Done** (later session): `pipeline/icons/build.py`'s
     `filter_result_to_rendered_scope` filters technology icon candidates to those whose owning
     technology is in P-16's 980-node rendered set, before decode/pack, wired through
     `build_atlases(..., rendered_keys=...)`. **Ascension-perk icons are deliberately NOT
     filtered** — checked against spec, not assumed: P-16's closure is a technology-node concept
     (which ACOT/AoT technologies get their own canvas node); an ascension perk is never a canvas
     node, only a gate badge (P-3), and "which perks does a rendered technology actually reference
     as a gate" is a different computation — P-3's gate-pattern-registry/gate-detection pass,
     which still isn't built (see below) — so there is no correct filter to apply to perks yet.
     **Real filtered figures**: technology atlas drops from 4 sheets / 8,387,616 bytes (unfiltered)
     to **2 sheets (1008×2016, 1008×1468) / 4,564,314 bytes** — resolved candidates 2103→1192,
     unresolved 19→4 (the other 15 unfiltered-unresolved candidates' owning technologies are
     outside the rendered set and no longer matter; do NOT guess at the surviving 4 —
     `config/icon_overrides.txt` stays human-decided by design). Combined with the unchanged
     262,676-byte perk sheet: **total atlas bytes ~4.83 MB (4,826,990), down from ~8.65 MB
     unfiltered — a 44% reduction.**
  3. **SETTLED: atlases are excluded from P-10's ≤2 MB budget** — same reasoning as before,
     unchanged. `MAX_TOTAL_ATLAS_BYTES` re-calibrated to the filtered figure this session: **6 MB**
     (was 12 MB), ~1.24x above the real ~4.83 MB total, and deliberately kept BELOW the ~8.65 MB
     unfiltered ceiling — unlike the old 12 MB setting, which sat above the unfiltered figure too
     and so could never have caught a regression that silently disabled filtering. This one can.
  4. **Documentation correction found while re-measuring**: the "8,650,292 bytes total" figure
     previously recorded against "Technology atlas sheets" in this file's corpus-counts table
     (below) was actually **technology + ascension-perk sheets summed together**
     (8,387,616 + 262,676 = 8,650,292, confirmed by direct recomputation) — the two rows in that
     table were correct individually (4 sheets / 1 sheet) but the byte figure was mislabeled as
     belonging to the technology row alone. Corrected in that table now.
- **`config/icon_overrides.txt`** is currently empty by design. Expect entries only after a
  *human* decides what's correct for each case — not a future agent session guessing.
- ~~**P-13's lock-reason override table** is a newly-identified hand-maintained config file, not
  yet created.~~ **Done**: `config/lock_reason_overrides.txt` + `pipeline/lock_reason_overrides.py`
  (loader) + `pipeline/availability.py`'s `needs_lock_reason_override`/
  `build_missing_lock_reason_overrides` (the warn-when-missing wiring). Seeded empty — the real
  corpus currently has zero LOCKED results needing an entry (verified, not assumed — see
  `tests/test_availability_corpus.py::test_no_locked_reasons_currently_need_a_lock_reason_override`).
- ~~**No trigger-condition → human-readable-text renderer exists yet.**~~ **Done**:
  `pipeline/trigger_text.py`, built as a shared component (not private to availability) so it also
  serves `detail-payload.schema.json`'s `weight.modifiers[].conditionText` via
  `describe_condition()`, not just the empire-overlay's lock `reason` string. `categorize_leaf()`
  additionally classifies undecidable leaves into a `ReasonCategory` — see CLAUDE.md's
  "Availability evaluator" section for the measured category distribution.

**Base dataset size — REAL, MEASURED (later session), not the estimate below.** Stage 2 dataset
emission is built (`pipeline/dataset_emit.py`) and the real base-dataset compressed transfer size
is **~64 KB (65,585 bytes)** against the ≤2 MB budget — ~31x headroom, comfortably more than the
projection below assumed, but for a reason worth recording rather than absorbing: the **real
measured compression ratio is 14.29x**, well above the 6-9x range the projection used (drawn from
the deploy-spike's 9.34x *synthetic* ratio, which itself carried an explicit caveat that real
content should compress *worse* than synthetic). The projection's method turns out to have been
wrong, not just imprecise — the deploy-spike's synthetic blob was dominated by free-text
name/description-shaped content, but the real base dataset's size is dominated by small,
highly-repetitive structured JSON (980 near-identical technology record shapes, 12-slot enum
arrays, mostly-empty arrays, frequent `null`s) that gzips far better than prose; real description
text isn't even in the base dataset, it's in the lazy detail payloads. **`spec/P-10-performance-automation.md` now records this formally** (Stage 2 cleanup session): size
is no longer a binding constraint on Stage 3's loading design at ~30x headroom, the lazy-artefact
split's justification is restated as responsiveness/memory/cache-granularity rather than "must fit
the budget," and the 14.29x-vs-6-9x compression divergence and its cause are recorded there too —
read that file, not just this paragraph, before making a Stage 3 loading-design decision that
assumes size is still scarce. See CLAUDE.md's "Stage 2 dataset emission is built" bullet for the
full writeup, including the other four artefacts' real sizes (never measured before this session)
and a real, non-arithmetic-coincidence finding this
build surfaced: `unconditionalUncertainty` moved from a stale 209/980 (21.33%, computed from
unexpanded blocks that silently skip 50 real `giga_tech_repeatable_*_cap` availability
conditions — the same bug class the tier-source audit already found for `tier`) to 259/980
(26.4%) once expansion was fixed, then — a later session, once those 50 were correctly
categorized as mod-configuration-gated rather than undecidable — back to **209/980 (21.33%)**,
the same number as the ORIGINAL figure by coincidence of arithmetic only. See CLAUDE.md's
"`giga_tech_repeatable_*_cap` correctly categorized — CONFIG_GATED" bullet for the full history
and why this is the correct, final figure, not a reversion.

**The two 209s are not a no-op, even though the number is identical — record this explicitly so a
future read doesn't conclude nothing changed.** Both exclude the same 50 `giga_tech_repeatable_*_cap`
nodes from `unconditionalUncertainty`, but for opposite reasons: the original 209 excludes them by
never seeing their `potential` block at all (a raw-block parsing defect, and they were wrongly
counted `AVAILABLE` as a result); the current 209 excludes them by evaluating them correctly and
finding they belong in a fourth state, `config-gated`, that didn't exist at the time of the
original figure. **The real change is visible in the AVAILABLE-state count, not this one**: those
50 moved from `AVAILABLE` to `CONFIG_GATED`, an **available-count delta of exactly -50**, confirmed
by `tests/test_dataset_emit.py::test_repeatable_cap_family_available_count_delta_is_exactly_minus_50`
(evaluating with no `potential` visible — the original defect's exact counterfactual — is
AVAILABLE for all 50; the real expanded evaluation is AVAILABLE for 0 of them). The D-10
unconditional-uncertainty ratchet, having gone 209 → 259 → 209 across two sessions, is back at its
original seed value — no regression, no ratchet action needed. Full table:
`spec/decisions.md`'s D-10 "The 209 -> 259 -> 209 sequence..." subsection.

**Config-gated display wording (P-13, a separate follow-up item in the same session)**: the
reason text for these 50 nodes is user-supplied, matching Gigastructures' own in-game option label
— `Requires <Megastructure Name> cap: 1 + Repeatables`. Stage 2 emits only the semantic subject
(the empire overlay's `availability[key].configGatedSubject`, sourced from the technology's own
resolved name) — Stage 3 composes the final sentence from the fixed template recorded in
`spec/P-13-empire-locking.md`.

**Corrected in a following session: real corpus is 50/50 resolved, not 42/50.** The original pass
found 8/50 (including the flagship `giga_tech_repeatable_alderson_cap` example) fell back to
`configGatedSubject: null` because the technology's own name embeds a `$...$` token, and assumed
that token was an unresolvable Stellaris runtime name-pool reference. **That assumption was never
verified against raw source and turned out to be wrong**: every one of those tokens is ordinary
Stellaris `$key$` loc-variable substitution, resolvable one hop away as its own plain loc key
(`name_alderson: "Alderson Disk"`) — two of the 8 (`dyson_swarm_3`, `orbital_arc_furnace_4`) are
vanilla megastructures Gigastructures extends, with the name defined in vanilla's own
localisation, which is why the fix (`pipeline/dataset_emit.py`'s `_resolve_loc_tokens`) resolves
against the full cross-source `ctx.loc_table`, not Gigastructures' loc files alone. All 50/50 now
resolve: `alderson` -> "Alderson Disk", `asteroid_manufactory` -> "Asteroid Industrial Site",
`dyson_swarm` -> "Dyson Swarm", `furnace` -> "Arc Furnace", `observatory` -> "Atmospheric Storm
Observatory", `orbital_naval_logistics` -> "Orbital Naval Logistics Office", `warmoon` -> "Attack
Moon", `warplanet` -> "Behemoth Planetcraft". `configGatedSubject` remains nullable and the
resolver still reports `None` rather than guessing when a technology has no loc entry or a token
chain exceeds the hop limit — no case in the current corpus hits either path. See CLAUDE.md's
"Config-gated reason wording" bullet for the full writeup and
`tests/test_dataset_emit.py::test_config_gated_subject_resolves_all_50_megastructure_names`.

**Original projection, kept for the record of what was assumed before a real build existed:**
~275–305 KB compressed against the ≤2 MB budget (~6–7x headroom), computed from **1,879** — the
canonical technology count (see "Canonical technology count" below; previously recorded as 1,878,
an uncorrected off-by-one from an earlier ad-hoc count whose exact method wasn't preserved — the
1-record difference doesn't move the KB range at any meaningful precision, but the count itself is
now the reviewed, traceable figure, not a stale one) — real localisation string-length samples
(name median 22 chars, description median 154/mean 180 — description itself stays out of the base
dataset), and the search index moved to its own lazy artefact. This projection has now been
superseded by a real measurement (above) — kept here only as the historical record of the
estimate, not as a figure to still trust.

**Canonical technology count: 1,879 — see CLAUDE.md's "Canonical technology count" section for
the full reconciliation.** Three counts were in circulation and used interchangeably before this
was pinned down: 1,878 (a stale, unrecoverable-provenance earlier count, now corrected), 1,879
(distinct technology keys after whole-key overwrite resolution — the correct figure for "how many
technologies exist as identities," and today's best available upper bound on final node count
pending P-16's rendering-scope closure), and 2,122 (icon *candidates* — 1,904 raw pre-resolution
technology-block occurrences across all 4 sources, plus 218 `technology_swap` sub-block
alternates; neither term belongs in a node-count estimate, since an overwritten-away occurrence
never becomes its own node and a swap alternate is per-profile display data on an existing node,
not a separate one).

---

## P-16 rendering-scope closure — measured by hand, since implemented as real code

**Update (Task 3 session): implemented as `pipeline/rendering_scope.py`.** The measurement below
was originally a one-off manual computation; it is now reproducible pipeline code
(`compute_rendering_scope`/`rendered_technology_keys`), verified against the exact figures below
in `tests/test_rendering_scope.py` (both synthetic mechanism tests and a real-corpus regression).
The rest of this section is kept as the original measurement record — the numbers didn't change,
only their provenance (hand-computed -> code-computed-and-tested).

CLAUDE.md's "Scope of ACOT and AoT" section specifies the rule (prerequisite-edge closure from a
rendered vanilla/Gigastructures technology); this is the first time it was actually computed.
Script: BFS over the canonical (post-P-15) `prerequisites` field only, seeded from every
Vanilla/Gigastructures technology's direct references into ACOT/AoT, then transitively expanded
through ACOT/AoT's own `prerequisites`.

**Trigger**: the user's real requirement is 4 specific ACOT/AoT technologies Gigastructures uses
as placeholders for its "supertensile" building alternates — `tech_dark_matter_power_core_dm`,
`tech_dark_matter_power_core_ae`, `tech_dark_matter_power_core_se`, `tech_civil_phanon_application`.
All 4 confirmed present, un-renamed: `dm` in `acot_01_delta_components_tech.txt:30`, `ae` in
`acot_02_alpha_components_tech.txt:9`, `se` in `acot_03_stellarite_components_tech.txt:693`, AoT's
`tech_civil_phanon_application` in `z_aot_phanon_building_tech.txt:1`. All 4 referenced only by
`vendor/mods/gigastructures/common/technology/giga_17_alternative_mega_build.txt` (lines 201, 225,
250, 276), each as a `prerequisites` entry for one of Gigastructures' 4 "supertensile" techs.

**Closure result**: **7 ACOT/AoT technologies total** (6 ACOT + 1 AoT), max depth 2.
- Direct references from Vanilla/Gigastructures: **exactly 4** — the four named above. No other
  vanilla or Gigastructures technology references any ACOT/AoT technology as a prerequisite,
  anywhere in the corpus.
- Transitive-only additions (3): `tech_mine_dark_energy` (ACOT), `tech_dark_matter_power_core_enig`
  (ACOT), `tech_precursor_design` (ACOT). All bottom into ordinary vanilla technologies
  (`tech_mine_dark_matter`, `tech_zero_point_power`, `tech_sensors_4`, …) already rendered
  unconditionally.
- `tech_dark_matter_power_core_se` has **zero** ACOT/AoT ancestors — no `prerequisites` field at
  all (gated purely through `potential`).
- Inclusion-rule comparison: (a) direct-only = 4, (b) depth≤1 = 4 / depth≤2 = 7 / depth≤3 = 7
  (closure exhausted at depth 2), (c) current unbounded closure (the spec'd rule) = 7.

**Conclusion: no rule change needed.** The closure was feared to be large (CLAUDE.md's own text:
"ACOT reaches T9+ with deep chains") but measures small and shallow for this reference set — the
unbounded closure (rule c, already spec'd) adds only 3 extra nodes beyond the 4 wanted, all
needed to avoid an invisible prerequisite-chain gap for `tech_dark_matter_power_core_ae`
specifically. Rule (a) (direct-only) would hit exactly 4 with zero extra but breaks CLAUDE.md's
own "never broken by an invisible gap" invariant — not recommended. **When P-16 is actually
implemented, use the existing unbounded-closure rule as spec'd; this measurement is the
confirmation, not a proposed change.**

**Rendered node total (Vanilla + Gigastructures + this 7-technology ACOT/AoT closure): 980.**
Canonical technology counts by winning source (post-P-15 resolution, all 1,879): Vanilla 673,
ACOT 742, Gigastructural Engineering 300, AoT 164. Rendered-by-source: Vanilla 673,
Gigastructural Engineering 300, ACOT 6, AoT 1 — i.e. 742-6=736 ACOT and 164-1=163 AoT canonical
technologies never render at all under this closure.

## D-10 availability projection — corrected figures and three review checks

**Correction to the previous survey turn's numbers**: 428/353/80 (previously reported) had a
methodology bug — trigger-construct classification was accumulated across *every* historical
occurrence of a technology key, including definitions a key's canonical winner overwrote away,
not just the winning (post-P-15) block. Recomputed against canonical winning blocks only. **The
numbers below (426/350/76 etc.) are the corrected, authoritative ones — supersede the previous
turn's figures wherever they were cited.**

**Baseline (1,879 canonical technologies)**: 437 (23.3%) have no `potential` block at all —
unconditionally available, confirmed not assumed. Of the remainder, applying the 2 design
decisions the survey recommended (assume default/off mod-config `has_global_flag`s; assume all
official DLC owned) plus a `not-fallen-empire` ground fact (none of the 12 profiles is a fallen
empire, so `is_fallen_empire`/`merg_is_fallen_empire` resolve to a constant `no`):

| Scenario | At-risk technologies | % of 1,879 |
|---|---:|---:|
| No design decisions applied (naive) | 1,235 | 65.73% |
| **With the 3 resolutions applied** | **426** | **22.67%** |

**CHECK 1 — profile-dependent vs. unconditional split** (of the 426 at-risk technologies):

| | Count | % of 1,879 |
|---|---:|---:|
| (a) Profile-dependent (an axis check coexists with the undecidable leaf — some profiles can short-circuit via `AND` to a definite `locked`) | 76 | **4.04%** |
| (b) Unconditional (no axis check anywhere — all 12 profiles resolve identically to `uncertain`) | 350 | **18.63%** |

(a) is above the 3% warn threshold, below the 10% hard ceiling. (a)'s 4.04% is an *upper bound
per profile* (counts "could vary," not "does vary for profile X") — the exact per-profile number
needed the real evaluator's short-circuit logic, since built (see "Ordered next steps" below).
**Adopted** (a later session's Task 1, now in `spec/decisions.md`'s D-10 and CLAUDE.md's "Trigger
evaluation" section): D-10's threshold applies to (a) only; (b) is tracked as a separate published
data-completeness figure, since a node reading identically under all 12 profiles never misleads a
user about their specific empire type — it's honestly reporting a fact outside the axis model, a
different quality signal than "the tool got your empire's availability wrong."

**CHECK 2 — `has_country_flag` breakdown (131 occurrences, 82 distinct names)**: unlike
`has_global_flag` (dominated by one resolvable "assume default mod settings" pattern), no single
resolvable pattern was found here. Two largest confirmed by direct evidence, not pattern-guess:
- `herculean_built` (27, all ACOT) — confirmed mid-game: `set_country_flag = herculean_built`
  fires from `vendor/mods/acot/events/acot_herculean_events.txt:1316`, a player-triggered event
  effect. Genuinely undecidable.
- `colossus_project` (16, all vanilla) — traced to `ap_colossus` ascension perk
  (`vendor/stellaris/common/ascension_perks/00_ascension_perks.txt:1076`), whose `on_enabled`
  fires `country_event = { id = apoc.100 }`. That event lives in `common/events/`, outside
  vanilla's vendored scope — **could not confirm** whether this is fully redundant with
  `has_ascension_perk = ap_colossus` (plausible but unverified). Left classified undecidable.
- Remaining 80 distinct names (88 occurrences): read as crisis-chain/story-progression flags by
  name pattern (`blokkat_*_possible` ×20, `ehof_code_2..7_complete` ×6,
  `encountered_first_lgate`, `completed_lcluster_chain`, `synth_queen_knowledge`,
  `cosmogenesis_aborted`, `starfire_cannon_unlocked`, etc.), consistent with the 2 confirmed
  examples' pattern but individually unverified (82 names, mostly singleton occurrences).
- **Net effect: none of the 131 occurrences move out of the undecidable bucket.** The 426/350/76
  figures above already reflect this — no further reduction available here.

**CHECK 3 — rate over the 980 rendered nodes (Part 1's closure), by source:**

| Source | Rendered | At-risk | At-risk % | Unconditional (no axis) |
|---|---:|---:|---:|---:|
| Vanilla | 673 | 144 | 21.40% | 103 |
| Gigastructural Engineering | 300 | 117 | **39.00%** | 106 |
| ACOT | 6 | 2 | 33.33% | 2 |
| AoT | 1 | 0 | 0.00% | 0 |
| **Total** | **980** | **263** | **26.84%** | **211** |

**This inverts the "restrict ACOT/AoT scope to fix the rate" premise.** The rendered-only rate
(26.84%) is *higher* than the all-1,879-canonical rate (22.67%) — the ~1,780 non-rendered
ACOT/AoT technologies excluded by the closure have a *lower* undecidable-leaf rate than what's
kept. **Gigastructures' own content is the concentration point** (39.00% at-risk, its own
crisis-faction/endgame-chain story-progression flags — the same pattern found in Check 2), not
vendored-but-unrendered ACOT/AoT bulk content. Narrowing ACOT/AoT rendering scope per the P-16
section above does not address the ceiling breach; the two problems are orthogonal.

**This section's numbers predate the real evaluator and the (a)/(b) split's adoption — kept as the
original projection record, not the current authoritative figures.** See CLAUDE.md's "Availability
evaluator" section for the real, evaluator-measured rates over the exact 980-rendered-node closure
— **3.37% worst-case profile-dependent, 21.33% unconditional (209/980), final figures after two
corrections that happened to cancel numerically** (209 → 259 → 209; see CLAUDE.md's "`giga_tech_
repeatable_*_cap` correctly categorized — CONFIG_GATED" bullet for the full history and why 209
is the genuinely correct final answer, not the original uncorrected one). The category
distribution behind the unconditional figure is likewise back to its original table, for the
same reason. The (a)/(b) split was adopted, not left as an open proposal, and the ceiling was not
breached once the real short-circuit logic replaced this section's upper-bound projection.

---

## Layout model — settled from v1 evidence (D-13)

**v1's actual failure, diagnosed from a screenshot.** The user reported that v1's visual design
was close to right, but two things were wrong behaviourally: **incorrect tier placement** (worst
in tier 6, and "likely not the only one") and **inadequate labelling of locks and
prerequisites**.

**IMPORTANT correction to the second failure's diagnosis (later session, from the user
directly).** For many sessions this document read "inadequate labelling of locks and
prerequisites" as a *card text* problem — truncated gate strings, missing badges — and
`spec/P-02-layout.md` still carries design constraints derived from that reading. **That reading
was wrong.** Shown his own v1 screenshots and asked directly, the user's answer was:

> "the issue isn't the gate or tech names being cut off, while it isn't ideal, players will know
> what they're looking for, and in the event of them being confused, they can select the tech for
> more info"

**Truncated card text is acceptable.** The real second failure is the **research path** — see the
"Research path" section below. Do not spend design effort making card text untruncatable; that
constraint was inferred, never reported. The popup is the escape hatch for full text and the user
considers it sufficient.

The screenshot diagnoses the first precisely: the band headed **TIER 6 contained cards almost
all badged T5**. v1 was assigning nodes to bands by *computed column* (post-promotion position)
while badging them with *declared tier*. A T5 technology promoted to column 6 landed under a
"TIER 6" header. Tier 6 was the worst offender because it is the first band that exists almost
entirely from promotion rather than declaration — vanilla and Gigastructures barely declare T6+
at all.

**This is why D-13 matters and is not a cosmetic preference.** Bands are declared tier. The mod
does not define tiers beyond vanilla (only ACOT and friends do); most Gigastructures technologies
are declared T5, and the community expresses progression depth through **ascension-perk gates**
("Galactic Wonders tier", "Gigastructural Constructs tier"), not through tier numbers. Players
saying "tier" mean the declared vanilla tier. So: **tier organises, gates annotate.** The computed
column number appears nowhere in the game, the mod, or player vocabulary and must never be
surfaced.

A design direction that made gates the *band-organising* axis was proposed in chat and
**rejected** on the user's evidence — do not revive it. Gates are a prominent card element, not a
layout axis.

### Measured layout facts

- **Tier source audit** (v1's placement bug class): 930/980 take tier from a literal on the raw
  block; **50/980 only have a tier after `inline_script` expansion** (`giga_mega_repeatable.txt`'s
  template, all `giga_tech_repeatable_*_cap`) — a pipeline reading raw blocks places these with
  no tier at all. 0/980 unresolvable after expansion. **Policy: hard build failure on a missing
  tier, never a silent default.** 83/980 declare tier as an `@variable` (4 distinct, all resolve,
  none currently overwritten cross-source) — **known blind spot:
  `pipeline.overwrites.resolve_variable_overwrites` checks cost/weight for cross-source variable
  overwrites but NOT tier.** Zero impact today, must close before Stage 2's real build. 2/980 have
  declared tier changed by a P-15 block overwrite (`tech_adaptive_combat_algorithms`,
  `tech_biomechanics`, Vanilla→ACOT), already handled correctly.
- **Backwards edges**: 27 of 891 non-repeatable prerequisite edges (3.0%) point from a later
  declared-tier band to an earlier one — 24 by one band, 3 by two, max 2. Worst cases:
  `tech_antimatter_power`(T3)→`tech_reactor_boosters_3`(T1);
  `tech_mega_engineering`(T5)→`giga_tech_penrose_sphere_1`(T3);
  `tech_stingers`(T4)→`tech_swarmer_missiles_1`(T2). Small and short-range; P-8 updated to route
  them explicitly in a gutter rather than assume forward-only. The old
  `column(B) > column(A)` invariant is **false under D-13 and has been removed from the spec.**
  **Correction (later session)**: the 891 denominator used a repeatable-membership rule
  (`levels < 0` only) that undercounted repeatable technologies by 12 — see the correction note
  below. Corrected denominator is **881**. The 27 backward edges are the same 27 by key either
  way; only the denominator moved.
  **Correction (P-14 edge-typing session)**: this was always `prerequisite`-only figure, and 2 of
  the 27 (`tech_stingers`→`tech_swarmer_missiles_1` at T4→T2, plus one other) turn out to be
  `alternative` edges (OR-branch members), not `prerequisite` — they were flattened into the same
  list by the pre-fix `ordered_prerequisites()`. The real, final decomposition, over the full
  three-kind P-14 edge set: **34 backward = 25 `prerequisite` + 2 `alternative` + 7
  `potential-gate`** (`potential-gate` wasn't extracted as an edge kind at all before this
  session). `potential-gate`'s 7 backward edges reach up to **5 bands back**
  (`tech_cosmogenesis_escort`(T5)→`tech_missiles_1`(T0)) — well outside the "1-2 bands back" this
  bullet describes for `prerequisite`/`alternative`; see CLAUDE.md's P-14 bullet and
  `spec/P-08-connectors.md` for the full breakdown and the deliberately-deferred `TODO(Stage 3)`
  routing decision. Record this figure as a per-kind decomposition from now on — it has moved
  three times purely through re-scoping.
- **Density** (declared-tier denominator, the relevant one again): Standard × T5 = **261**, the
  layout-forcing cell. Broad midsection, not one anomaly. Category is the natural sub-grid wrap
  key — T5's 261 split 13 ways (voidcraft 49, particles 39, field_manipulation 30, biology 26,
  computing 25 … archaeostudies 1), and there are **zero multi-category nodes**.
  **Correction (later session)**: recomputed at **253** under the corrected repeatable-membership
  rule (8 of the 12 newly-recognised finite-level repeatables were Standard-lane, declared-T5
  nodes that moved into the Repeatables band) — see below.
- **Repeatable membership, corrected (later session, not part of the original hand survey)**: the
  original layout implementation's `is_repeatable` tested `levels < 0` only (76/980 nodes). Found
  wrong against a user's v1 screenshot: the corpus also uses `levels` as a positive **finite** cap
  (5, 20, or 40) on an otherwise identical repeatable-tech shape (`cost_per_level` field,
  `*_repeatable*.txt` source files) — 12 more nodes, for a corrected total of **88**. The
  screenshot's "T5 x5" card is `tech_repeatable_reduced_building_cost` ("Gravitational Analysis"),
  exactly one of the 12. Corrected membership is deliberately distinct from the 50
  `giga_tech_repeatable_*_cap` inline_script-tier-only nodes above — every `_cap` node is
  repeatable (a proper subset of the 88), but 38 of the 88 never went through inline_script tier
  expansion at all; conflating the two is a separate bug from either finding alone. Sink property
  re-verified over the corrected set: 881 non-repeatable-to-non-repeatable edges + 83
  non-repeatable→repeatable edges = 964 total, 0 edges run the other two directions. See CLAUDE.md's
  "Repeatables" section and `spec/decisions.md`'s D-13 for the full writeup, including why the
  5 non-T5 repeatables (mostly Blokkat-scrap/L-Cluster/Cosmogenesis crisis-chain nodes) are
  evidence *for* the repeat-count badge, not just a stray fact.
- **N-card-wide bands**: settled in principle (v1 clearly did this). Recommended **N = 3–4**. At
  270px cards: N=3 → 9,486 × 10,900px; N=4 → 12,544 × 8,350px. Canvas size itself is *not* the
  constraint — 980 nodes/964 edges is small for WebGL, S-3's LOD thresholds are zoom percentages
  not absolute pixels, and no dimension approaches float32 precision limits. What bites at N=1 is
  **wayfinding**: 161+ single-file stacked cards give a panning user nothing to chunk against.
  Any N≥2 fixes that; category grouping fixes it properly.
- **Card dimensions** (proposed, not yet locked in spec): **270×92px**. Name lengths over the 980
  rendered nodes: p50=21, p90=35, p95=39, p99=46, **max=54** ("Blokkilian Equations - Planckscale
  Particle Generation"; the `giga_tech_repeatable_*_cap` → "… Management Protocols" convention
  sits at 43–53). 17% of names carry `§` markup. Designed to p95 with ellipsis truncation, full
  name in popup and hover title — though 270px in practice fits even the 54-char max across two
  lines. ~~**Gate text is never truncated** — that was v1's literal reported failure.~~
  **CORRECTED (later session, from the user directly): this premise was false.** Gate text
  truncation was never the reported failure — see the correction note at the top of this section.
  The user explicitly accepts truncated gate and name text on the card, with the popup as the
  escape hatch. The 270×92px dimension and the p95 design target still stand on their own
  measurement merits; only the "never truncate gate text" *rationale* was wrong. Dropping the
  "Needs " prefix (the icon already carries the semantic per P-3) cuts the worst gate string from
  41 to 35 chars, which is still worth doing — but as a legibility improvement, not to satisfy a
  hard constraint that does not exist.
- **Gate population**: 46/980 nodes (4.7%) carry ≥1 gate, 9 carry 2 (max observed) — covered by
  P-3's existing primary+secondary rule, no design gap. Only 28 possible gate strings exist
  total, shared across many nodes — a small bounded set, unlike per-node names.
- **Reason-category surfacing**: same inline treatment as gates, not a corner badge — e.g.
  "Locked: Nomadic empires", "Uncertain: Blokkat crisis progress", falling back to "Uncertain:
  reason unknown". Full raw trigger text, category and 12-profile matrix in the popup. This
  directly targets v1's second reported failure: uncertain/locked states reading as missing data
  rather than as information.

---

## Research path — v1's real second failure, diagnosed from a screenshot (spec: P-12.9)

This is the other half of what the user reported about v1, and it is **not** a card-labelling
problem (see the correction at the top of the Layout model section). It is a correctness problem
in the research path, diagnosed from a v1 screenshot of the path to `tech_mega_engineering` —
a flat numbered list of steps with a running cost total, ending at Σ 74,750.

**What was wrong with it**, per the user, all four the same root cause — the path was computed
once, profile-blind, with OR branches flattened to inline annotations rather than traversed:

- "*or Arkship Mastery*" named an alternative but never expanded **its own prerequisites** — the
  path was incomplete for anyone who would actually take that branch.
- "*or Stingers*" was shown as optional when for a **bio-shipset** empire it is the only route
  (Maulers → Stingers), and belonged in the path proper.
- **Starbase techs were included for every empire**, though a **nomadic** empire does not need
  them.
- Consequently **the Σ total was wrong for most of the 12 profiles** — 74,750 is the
  regular-shipset non-nomadic figure presented as if universal. This is the worst of the four: a
  cost total reads as authoritative in a way an inline annotation does not.

**The data to fix this now exists and did not when v1 was built** — P-14 separated `alternative`
edges from true `prerequisite`s with group IDs, the empire overlay carries per-profile
availability across all 12 profiles, and D-14 added per-profile swap name substitution. The P-14
edge-typing work turned out to be the prerequisite for fixing this, not just a data-model tidy-up.

**Design decisions, all settled with the user in chat and written into
`spec/P-12.9-research-path.md`** (spec only — nothing is implemented):

- **Per selected profile.** Technologies not on that profile's route simply do not appear. This is
  correctness, not filtering. The user considered "show multiple paths, one per empire type" and
  rejected it once it was clear per-profile computation makes it unnecessary.
- **Shape stays as v1 had it** — one flat ordered list with a running cost total. Explicitly
  confirmed by the user; do not redesign it into a graph overlay without asking.
- **OR-branch selection: cheapest total cost**, including that branch's own prerequisite chain,
  with the alternative noted at that step. **Measured 0/72 disagreement with fewest-steps on the
  real corpus** — the rule is currently a distinction without a difference and is explicitly
  revisitable.
- **Uncertain steps stay in the path; the total is marked an estimate** (a lower bound). Excluding
  them understates cost; presenting an exact number over an unknown is a false claim. Worst
  profile is 182/980 paths carrying ≥1 uncertain step, so this must read as an ordinary annotated
  state, not an error.
- **Config-gated steps are excluded from the total and explained separately.** Structurally
  confirmed: config-gated technologies are sinks, so a config-gated step can only ever be the path
  **target**, never mid-path — no path total is ever mixed.
- **Triggered by selecting a technology**, as in v1. Pinning a goal technology for always-on
  display is a **deferred QOL feature**, explicitly out of scope for the first renderer. The
  user's framing: "main focus is getting the tree working, extra QOL features come after."

**The design was validated against the user's own bug report before being accepted**, which is
the strongest evidence in the project that it is right: recomputing `tech_mega_engineering`'s path
for regular/mechanical/non-nomadic reproduces **74,750 exactly** — v1's own reported figure — while
nomadic correctly routes through Arkship Mastery (**99,750**, a *higher* number, not a flattering
one) and bio-shipset correctly routes through Stingers (**73,750**) with Battleships excluded as
locked rather than shown as a false option.

---

## Ordered next steps

The dataset schema (`schema/`) is done — see "What's built" above. Stage 2 now has a contract to
emit into.

1. ~~**Overwrite resolution (P-15).**~~ **Done.** `pipeline/overwrites.py` +
   `pipeline/overwrite_overrides.py` — see "What's built" below for the full description. Not
   plain last-definition-wins alone: the resolution rule was corrected mid-implementation after
   a survey miss surfaced (see "Vendor-backed corpus counts" below) — Gigastructures' vendored
   snapshot was stale relative to its own GitHub `Live-Branch`, missing a real overwrite
   (`tech_mega_engineering`) the survey's first pass correctly reported as absent from the (then
   stale) corpus. The corpus was re-vendored to the pinned commit before resolution was built, so
   the counts and behaviour below reflect the corrected corpus, not the original survey's numbers.
   **This ordering was checked, not just carried over** — see the analysis below.

**Sequencing check: P-15 vs. localisation, verified with evidence.** `pipeline.localisation` is
already Stage-1-complete and has zero remaining work — it isn't actually competing with P-15 for
"next task," so the real question was whether P-15 has a hidden dependency on it, or vice versa.
Checked both directions: (1) P-15's own outputs — the `SourceMod`-based `definedBy`/`overwrites`/
`label` shape (P-12.5) and the field-level diff list (cost/tier/prerequisites/weight/category/
flags, `schema/detail-payload.schema.json`'s `overwriteDiff`) — are fixed enums and internal
field names, never localised text; P-15 needs no resolved localisation table to do its work.
(2) `pipeline/localisation/table.py`'s own docstring states the independence directly ("*never
merged with... P-15's technology-overwrite table*") — its last-wins resolution runs entirely
over the loc corpus, keyed by loc key string, with no reference anywhere to which source wins a
technology-block overwrite. Neither blocks the other. What *does* make P-15 come first is
`spec/00-overview.md`'s own Stage 2 ordering — "Resolve overwrites... Build the DAG... Evaluate
triggers... Assign tiers... Route edges... Emit the dataset" — every one of those needs the
canonical (post-overwrite) technology record first, including "attach a localised name to it."
P-15 is the one genuine blocker on the critical path; localisation is a leaf, consumed only at
final dataset-emission time, zero schedule risk. The current ordering is correct for the right
reason, not by default.
2. ~~**Partial trigger evaluator (D-10).**~~ **Done, including the P-13 reason-text/category
   layer.** `pipeline/availability.py` — see CLAUDE.md's "Availability evaluator" bullet under
   "What's built" for the full description. D-10 was split into two metrics (profile-dependent,
   ceiling-governed; unconditional, ceiling-exempt) — see `spec/decisions.md`'s D-10. **Real
   measured rates, over the EXACT 980-rendered-node P-16 closure** (`pipeline/rendering_scope.py`,
   built alongside — see point 3 below): 3.37% worst-case profile-dependent (below the 5.3%
   projected upper bound; confirmed to actually cross the 3% warn threshold, not just look close
   to it), **21.33% unconditional (209/980)**. Neither breaches the 10% ceiling. This figure moved
   twice across later sessions (209 → 259 → 209): first a real measurement bug (raw, unexpanded
   technology blocks in `tests/test_availability_corpus.py`'s fixture silently missed the real
   `potential`-gating condition on all 50 `giga_tech_repeatable_*_cap` technologies, undercounting
   at 209; fixed, giving 259), then a real classification gap (those 50, once visible, were being
   counted as `uncertain` when their `potential` actually resolves DEFINITIVELY to unavailable for
   a mod-configuration reason -- introduced as `config-gated`, a fourth `AvailabilityState`
   distinct from `locked`/`uncertain`/`available`; fixed, giving 209 again). **209 is the final,
   correct figure -- the same number as the original by coincidence of arithmetic, not because
   nothing needed fixing.** See CLAUDE.md's "`giga_tech_repeatable_*_cap` correctly categorized —
   CONFIG_GATED" bullet for the full writeup, including why the fix generalises to any
   mod-config-toggle-caused unavailability (verified to affect only these 50 on the real corpus).
   `pipeline/trigger_text.py` is the shared trigger-condition -> text/category renderer this
   section previously flagged as missing — `describe_condition()` (also usable for P-12.8) and
   `categorize_leaf()` (a corpus-derived `ReasonCategory` taxonomy: crisis/story-chain, origin,
   ethics/civic, mod-content, mod-configuration, opaque country state, unclassified — the
   `mod_configuration` category added alongside `config-gated`). **Category distribution over the
   final, corrected 209 unconditional-uncertain nodes is exactly the original table**: ~80%
   explainable (crisis/story 42.6%, origin 19.6%, ethics/civic 16.3%, mod-content 1.9%), ~20%
   opaque/unclassified (16.3% + 3.3%) — read as primarily a presentation problem Stage 3 can
   mostly solve with honest, category-specific reason text.
   `pipeline/lock_reason_overrides.py` + `config/lock_reason_overrides.txt` implement P-13's
   override table (seeded empty — zero real-corpus LOCKED results currently fall back to
   unphrased text). Still open, not done here: general scripted-trigger call inlining (the single
   biggest lever still left on the unconditional figure — `has_gigastructural_constructs` and
   similar custom triggers are individually special-cased, not generically resolved), and
   `has_country_flag` resolution beyond the name-pattern heuristic behind the crisis/story split
   (individually unverified per flag, same caveat the original survey carried). These unblock
   gate detection (P-3's pattern-matching layer, distinct from the universal `potential-gate` edge
   extraction) and both `TODO(Stage 2)` items in `pipeline/icons/resolve.py`.
3. ~~**P-16 ancestor closure.**~~ **Done** as real code, not just measured by hand:
   `pipeline/rendering_scope.py` (BFS over P-15-resolved `prerequisites`), verified against this
   file's earlier hand-computed measurement (7 ACOT/AoT technologies, 980 rendered nodes total) —
   see `tests/test_rendering_scope.py`. Closure stays `prerequisite`-only, decided on evidence in
   a later session (see point 4a below), not left as a placeholder.
4. ~~**Tier/column/edge computation.**~~ **Done, per D-13's corrected model** (`spec/decisions.md`
   — bands are declared tier, not computed position; see CLAUDE.md's "P-2/D-13 layout is built"
   bullet for the full description). `pipeline/layout.py` + `pipeline/geometry.py`. Real numbers
   over the 980-node rendered set: canvas 12,544×8,146px (corrected from an initially-reported
   8,350px — see the repeatable-membership correction below), densest band cell Standard×T5=253
   nodes (corrected from 261). Edge routing is a first-pass orthogonal H-V-H router with a
   deterministic channel offset, not a full crossing-minimising/obstacle-avoiding one — that
   refinement is still open, tracked in `spec/P-02-layout.md` rather than silently assumed done.
4a. ~~**P-14 full edge typing (DAG build).**~~ **Done** (later session): `pipeline/edges.py` — the
   last structural gap in Stage 2 before dataset emission. Layout previously built `prerequisite`
   edges only; all three P-14 kinds (`prerequisite`, `alternative`, `potential-gate`) are real now
   — see CLAUDE.md's "P-14 full edge typing is built" bullet for the full description (extraction
   mechanism per kind, the two standing diagnostics, the count_country self-loop regression guard,
   the P-16 `prerequisite`-only decision and its `compute_alternative_only_gaps` tripwire
   mitigation, and why edge-kind membership isn't mutually exclusive per pair). **Final real
   figures**: 989 total edges = 888 prerequisite + 76 alternative + 25 potential-gate; 34 backward
   = 25 + 2 + 7 (was reported 27/964 `prerequisite`-only before this session — see the "Backwards
   edges" correction note above for the full reconciliation). `schema/common.schema.json`'s `Edge`
   gained `groupId` and `bandSpan`; TS types regenerated; the icon atlas's real content scope
   still depends on P-16's closure the same way it always did (unaffected by this work — the
   closure itself didn't change, only the edges built alongside it).
   **Repeatable-band correction (later session)**: `pipeline.layout.is_repeatable` widened from
   "`levels < 0`" to "`levels` field present at all" — found by checking a user's v1 screenshot
   (a card badged "T5 x5") against the corpus, not by any test. See "Measured layout facts"'
   correction note below and CLAUDE.md's "Repeatables" section for the full finding and the
   corrected 88-node membership, the 881/83/964 edge-count reconciliation, and the schema change
   (`repeatable` is now `null | {levels}` rather than an always-present object) this drove.
4b. ~~**Dataset emission**~~ (assembling every Stage 2 component into the actual
   `base-dataset.schema.json`-shaped JSON + side-files, plus the other four artefacts). **Done**
   (later session): `pipeline/dataset_emit.py` — see CLAUDE.md's "Stage 2 dataset emission is
   built" bullet for the full writeup. All five artefacts build and schema-validate against the
   real corpus (`tests/test_dataset_emit.py`): 980 technologies, 989 edges, 12 empire overlays, 980
   detail payloads, the search index, diagnostics. Real base-dataset compressed transfer: **~64 KB**
   against the 2 MB budget (see the "Base dataset size" section above for the full reconciliation
   against the ~275-305 KB projection, including why the projection's *method*, not just its
   number, turned out to be wrong). A real bug surfaced along the way, not introduced by this work
   (later corrected again, in a following session, to a different final answer — 209/980, via a
   new `config-gated` state, not a reversion to the original bug): see the "Availability
   evaluator" correction in CLAUDE.md. Also closed in the same session: icon-atlas
   P-16 filtering (`pipeline/icons/build.py`'s `filter_result_to_rendered_scope`, technology atlas
   ~8.65 MB unfiltered → ~4.83 MB filtered including the unchanged perk sheet;
   `MAX_TOTAL_ATLAS_BYTES` re-calibrated 12 MB → 6 MB) — see "Vendor-backed corpus counts" above.
   Known v1 scope limitations (all schema-valid, none fabricated): `appliesToEmpireTypes`
   unconstrained on every edge, `gates` always `[]`, `repositoryLink`
   wiki URLs unvalidated — see the module's own docstring for the full list and why each is
   deferred rather than guessed at. ~~`swapMappings` always `[]`~~ **Closed in a later session —
   see CLAUDE.md's "D-14: `technology_swap` per-profile name/icon substitution is built" bullet**:
   real corpus is 214 swaps across 185/980 rendered technologies, 128 axis-expressible (substitute
   per profile via `swapMappings`) / 86 non-axis (listed as popup-only `variants` in the detail
   payload, never substituted — origin/civic/species-trait/ascension-perk/galaxy-situation
   conditions the 3-axis model can't express). **`cost`/`repeatable.costPerLevel` added next session** (they
   didn't exist in the base dataset at all before — `cost` wasn't in the schema despite
   `00-overview.md`'s glossary naming "research cost" as a card field): see CLAUDE.md's "Small
   targeted correctness pass" bullet for the real figures (15/980 rendered nodes have an
   unresolvable `cost`, 88/88 repeatables resolve `costPerLevel`) and `spec/P-02-layout.md`'s
   "Cost display" section for the primary/secondary display decision.
5. **Stage 3 (Render)** — real rendering, six passes in
   (`client/src/main.ts`/`camera.ts`/`lod.ts`/`tokens.ts`): slice 1 (static render), slice 2
   (camera + a first 3-tier LOD), slice 3 (edges), slice 4 (row rendering, D-16's re-axis), a
   **visual-fidelity pass** that fixed four appearance defects the user found reviewing slice 4's
   screenshots, and now a **second visual-fidelity pass** that fixed five more. See CLAUDE.md's
   "Stage 3 visual-fidelity pass" and "Stage 3 visual-fidelity pass 2" bullets for the full
   writeups. Pass 1 summary: the viewport-pinned sticky headers slice 4 built are REMOVED entirely
   (the user rejected them outright) and replaced with world-anchored row header chips plus a
   v1-style tier-band label repeated above every row's own populated band cell — this superseded
   S-03's "renders once across the full lane stack" criterion for a SECOND time (the first was
   D-16's lane→row rename), both supersessions now recorded explicitly in `spec/S-03-tier-
   differentiation.md` itself; every one of the 18 rows (not just the 5 faction rows) now gets a
   real tinted-panel/border/rounded-corner treatment, so category rows read as labelled containers
   instead of empty space; the faction row-backing patterns are rescaled for row (not card) scale,
   with a real unbounded-line bug found and fixed along the way (a faction row's diagonal pattern
   was bleeding across the entire canvas height, striping category rows too) and Sirenalia's
   pattern changed from flat rects to real curved "sweeping bands" via PixiJS's `quadraticCurveTo`;
   card name text is now hard-clamped to 2 lines with an ellipsis (matching the card's own original
   p95-name sizing intent), verified numerically over all 980 nodes that no name's bounding box
   exceeds its card. **Pass 2 summary**: card/band spacing widened again (real rebuilt canvas
   13,632×11,608px, up from 12,888×10,800px); tier bands now get an alternating background tint;
   edges get rounded corners (closing `spec/P-08-connectors.md`'s previously-skipped requirement)
   and a brighter light blue-cyan trace colour; the row-chip/per-cell-tier-label overlap Pass 1
   introduced is fixed (verified numerically, 0 violations across all 18 rows); the five faction
   row patterns are now real user-supplied artwork (Katzenartig's flagged provisional), which also
   surfaced and fixed two real bugs — the row panel was reading the chip's flag-identity colour
   instead of its own row-backing tone, and the pattern accent's clipping mask was never a
   scene-graph child so it silently clipped every faction pattern to nothing regardless of zoom.
   Still real gaps, next slice's scope: rare/dangerous/repeatable/gate/mod-requirement badges, the
   rare/dangerous outline override, hover/click/selection/popup, search, empire-profile switching,
   plus two still-open art items (real traced Blokkats flag SVG, a signed-off Sirenalia contrast
   colour). See CLAUDE.md's Stage 3 bullets for exactly what does and doesn't exist.
   `spec/P-12.9-research-path.md` is spec-only too — a design for one popup field, not yet
   implemented either.

---

## Next prompt to paste into Claude Code

**Most recent session ("commit + close the loop" follow-up): committed the previously-staged
has_ancrel/scripted-trigger-expansion/gate-extension work (Item 0, five logical commits); pinned
the corpus-wide uncertain count as a structural test invariant, proven capable of failing
(Item 1); resolved the crisis/story-progression flag naming pattern as a class, same treatment as
the user-approved `colossus_project` precedent — 73 technologies move unconditionally uncertain →
available, unconditional 107 → 34/973, union uncertain 127 → 54/973, worst profile-dependent rate
UNCHANGED at 1.54% (Item 2); confirmed `founder_species`/`has_authority` are already fully closed
by an earlier session's ethics/civic/origin gate work, no code change needed (Item 3); investigated
and reported (not applied) the `@giga_amb_flag` config-toggle candidate, pending user confirmation
of its default state (Item 4); catalogued the remaining 54-technology residue by classification,
with a domain question flagged for the user (`is_country_type = acot_phanon_base` on
`tech_dark_matter_power_core_se`) (Item 5). **Both flagged questions were answered by the user in
the same session, as a follow-up**: `acot_phanon_base` is confirmed AI/event-only, and the
technology IS reachable by a player who has progressed far into ACOT (not a permanent-
impossibility case) — `pipeline.availability.COUNTRY_TYPE_NEVER_PLAYER` now resolves that leaf as
a ground fact, correcting the technology's UNCERTAIN reason to the real one
(`has_country_flag = stellarite_tech_enable`, still genuinely unresolved). `giga_buildcap_j` was
DELIBERATELY left unresolved (not applied) — the user confirmed the reference-balance preset has
it ON by default but real players mostly change it and Gigastructures' own default may drift,
the opposite evidence shape from the already-approved `_capped_r` toggle; resolving to either
constant would misrepresent genuinely unstable state. See `docs/BUILD-LOG.md`'s "commit + close
the loop" section for the full writeup, real numbers, and the residue table. **Open follow-ups
from this session, not yet resolved:** `giga_rings_beh`/`_gar`/`_tit` (5 technologies, already on
CLAUDE.md's older unconfirmed candidate list) still need per-flag user confirmation; a scoped
evaluator-thoroughness relaxation for `if = { limit = {...} }` blocks (4 technologies) the user
already pre-approved in
principle but this session didn't implement; `exists`/`has_dna`/`always` leaf constructs not yet
individually surveyed.

**Stale as of an earlier session — kept for history.** Current as of the session that: built the
`?dev` uncertainty health monitor (Item 1); resolved four classes of
user-confirmed uncertainty (Item 2a-d — DLC/mod-presence/progression-flag resolution rules plus
the `always = no` exclusion, 977 → 973 rendered nodes); surveyed (not implemented)
ascension-perk `add_research_option` grants (Item 3); fixed gate-label collisions and enlarged
the gate icon (Item 4); stopped the ACOT/AoT tensile technologies from showing a redundant
prerequisite as gate text (Item 5); rebalanced sub-grid centring to fix top-heavy row padding
(Item 6); and clarified (without changing) hover-vs-selection scope (Item 7). All of Items 1-6 are
implemented, tested, and headless-verified; Item 3 and Item 7 are surveys only, per instruction.
See `docs/BUILD-LOG.md` for the full session writeup (real numbers, screenshots, every reasoning
step) and the immediately-prior session's writeup for the `activeEdgeIds`/tech-swap/prerequisite-
popup-list work this one built on top of.

**Next prompt should point at the research path (P-12.9) implementation.** The design was surveyed
against the real corpus in a still-earlier session and **approved by the user** — do not
re-litigate the design (per-profile, cheapest-total-cost `OR`-branch resolution, `uncertain`-
stays-in-estimate with the total marked an ESTIMATE, config-gated-target-only, unavailable-as-
one-state) — but three of the spec's own recorded validation figures are now stale against how far
the corpus has moved since they were measured, and **correcting them is part of the same
implementation pass, not a separate follow-up**:
- The "2 of 980 impossible" headline count is now **203 technologies / 1,270 (key, profile)
  pairs** — real, expected content growth (many more technologies are directly axis-gated than
  when this was last measured), not a bug. Re-verify the "dangerous" sub-case the spec's entire
  `status: "unavailable"` simplification rests on — an ancestor chain broken while the target
  itself stays `available`/`uncertain` — is still exactly zero before trusting the simplification;
  it was as of this session's survey, but re-check against whatever corpus state exists when you
  implement, don't assume it's still true.
- `tech_mega_engineering`'s nomadic total is now **76,250** (was 99,750 in the spec) — the
  regular/mechanical (**74,750**) and regular/biological (**73,750**) totals still reproduce
  exactly, so this is a real, narrow content-length change in the Arkship Mastery chain
  specifically, not an algorithm problem.
- The `OR`-group tie-break's "0 disagreements between cheapest-total-cost and fewest-steps" is now
  **12 disagreements** (out of 72 genuine 2+-viable-candidate choices, unchanged count) — cheapest-
  total-cost is genuinely load-bearing now, not a distinction without a difference the way the spec
  currently frames it.

Re-run the survey's own reproduction script (or equivalent) against whatever corpus state exists
at implementation time before trusting these three numbers verbatim — they were measured once,
this session, and the corpus does keep moving.

**Also still open, not part of the P-12.9 work but real and scoped:**
- ~~Item 3's `add_research_option` finding...~~ **DONE, a later session ("Ring Segment /
  ascension-perk locking / gate-propagation" session, Item 4a)**: `tech_ring_world`/
  `tech_dyson_sphere`/`tech_matter_decompressor` now carry a real `ap_galactic_wonders` gate via
  `pipeline.dataset_emit.ADD_RESEARCH_OPTION_PERK_GRANTS`. Left here only so a future session's
  memory of "this was still open" gets corrected on sight — see CLAUDE.md's "Gates" section.
- Middle-click isolation (P-7, fully specced, confirmed entirely unbuilt across every session
  asked about it).
- No `pytest` CI workflow exists yet (only `tsc --noEmit` runs in CI).
- Hover/selection discoverability (Item 7) — the right behaviour already exists, nothing surfaces
  it to the user; a cheap, optional follow-up, not asked for yet.
- **New this session**: gate propagation down `potential-gate` edges (as opposed to
  `prerequisite` edges, which now DO propagate) is a deliberately deferred scope boundary — see
  CLAUDE.md's Open Items.
- **New this session**: same-sub-column `alternative`/`potential-gate` edges (6 real cases, 2 in
  the Compound row) are a real, narrow gap in D-17's guarantee — surveyed, not implemented, per
  explicit instruction; see CLAUDE.md's Open Items for the recommended fix and why it's cheap
  (per-cell, not a global `subgrid_width` renegotiation).

**Prerequisite, same as every session**: `client/public/dataset/` is gitignored (D-15) and won't
exist in a fresh checkout — run `tools/build_dataset.py` locally (needs `vendor/` populated)
before `npm run dev`/`build` in `client/`. Re-run it fresh rather than assume any on-disk build is
current; the real node/edge counts are **973/977** (D-18 then Item 2c). **Gate instance count is
now stale here — see CLAUDE.md's "Gates" section for the current, real figure (TOTAL 267 instances
over 196 technologies, direct-only 139 over 112 technologies, as of the "Ring Segment /
ascension-perk locking / gate-propagation" session) rather than the 136/109 recorded in this
paragraph historically.**

---


## Specced but not yet implemented

- **P-12.9 (research path) is fully specced, not yet implemented** — `spec/P-12.9-research-path.md`
  (new file; the old P-12-detail-popup.md row is now a summary pointing to it). Fixes v1's second
  reported failure (profile-blind path, unexpanded `OR` branches, e.g. "or Arkship Mastery" never
  showing its own prerequisites). Per-profile traversal over true `prerequisite` edges + resolved
  `OR`-group selection (cheapest total cost among viable available/uncertain candidates — real
  corpus: 0 disagreements with fewest-steps across 72 genuine multi-candidate choices). `uncertain`
  steps stay in the path with the total marked an estimate; `config-gated` steps are excluded from
  the total and — confirmed structurally, not assumed — can ONLY ever be the path's own target,
  never a mid-path step (config-gated technologies are edge sinks, D-13's Repeatables finding
  extended to `alternative` edges too). **Pinned figure, corrected in a follow-up session**: the
  uncertain-path count is per SELECTED PROFILE (matching the path itself), not a single number —
  the original "163-182" was an unlabelled per-profile min/max range; canonical headline is
  **182/980 (18.6%), the worst profile** (machine_intelligence/biological/non-nomadic), with the
  full 12-profile table and the separately-labelled across-any-profile (191/980) and intersection
  (156/980) figures recorded in the spec. Also recorded: the path is selection-triggered, exactly
  as v1 (pinning a goal technology for persistent display is a deferred QOL feature, explicitly
  out of scope for the first renderer); a tripwire diagnostic
  (`diagnostics.unresolvableResearchPaths`) for the "target looks researchable but has no route"
  case that has zero real occurrences today. Real worked-example validation against the user's own
  v1 bug report: `tech_mega_engineering` for regular/mechanical/non-nomadic recomputes to exactly
  **74,750** (v1's reported figure); nomadic correctly routes through Arkship Mastery instead of
  the `is_nomadic = no`-gated Starbase line (**99,750**, higher — correctness, not flattery);
  bio-shipset correctly routes through Stingers with Battleships excluded as locked (**73,750**).

## Stage 3 — client toolchain foundation

TypeScript + PixiJS + Vite setup, real dataset wiring, content-hashed artefacts, D-15's local-build/manual-deploy model, icon atlas writing.

- **Stage 3 toolchain foundation is built** (later session): `client/` — TypeScript + PixiJS +
  Vite, no rendering logic yet (explicitly out of scope for this session; see spec/00-overview.md
  for what Stage 3 actually renders). **Node/npm now exist in this environment**, installed
  user-level via Homebrew/linuxbrew (`/home/linuxbrew/.linuxbrew`, owned by the working user, no
  root at any point) — CLAUDE.md's and `tools/generate_typescript_types.py`'s prior "no Node/npm
  toolchain in this environment" notes are now historical, not current. **A first attempt to set
  up headless-browser verification via `npx playwright install --with-deps chromium` tried to
  shell out to `apt-get` as root and was abandoned mid-session** (per-user instruction — it failed
  harmlessly here since this host has no `apt-get`, but the attempt itself was wrong regardless of
  whether it succeeded); the corrected, fully user-level equivalent (`npx playwright install
  chromium`, no `--with-deps`, browser binary in `~/.cache/ms-playwright/`) was used transiently
  for verification only and was never added to `client/package.json` — confirmed by a full
  `rm -rf node_modules && npm install` reproducing the working toolchain from the committed
  lockfile alone with zero trace of it.

  **Reproducibility, pinned properly**: `client/.nvmrc` (`26.7.0`, the exact version everything
  was verified against) for `nvm`/`fnm`/`actions/setup-node`'s `node-version-file`;
  `client/package.json`'s `engines.node` (`>=22`) as a looser compatibility floor. No
  `npm install -g` anywhere — every tool (`typescript`, `vite`) is a `devDependency`, run via
  `npm run <script>` or `npx`.

  **`tsc --noEmit` against `schema/generated/dataset-types.ts`: zero errors**, verified three ways
  — as part of the client project's full compile (confirmed via `tsc --listFiles` that the file is
  actually type-checked, not silently excluded), standalone in isolation under
  `--strict --exactOptionalPropertyTypes --noImplicitOverride --noPropertyAccessFromIndexSignature`
  (stricter than the project's own baseline `tsconfig.json`), and by importing/using several of
  the generated types (`BaseDataset`, `GeometryRef`, `EmpireOverlay`) in real, working client code.
  `tools/generate_typescript_types.py`'s hand-written generator produces valid, well-typed
  TypeScript — a genuine negative result (the module's own docstring expected possible real
  problems; there weren't any), not a gap in the check. `.github/workflows/typecheck.yml` runs
  this on every change to `client/**` or `schema/generated/dataset-types.ts`.

  **Real dataset wired in, content-hashed, and verified against a real browser.**
  `tools/build_dataset.py` runs the full Stage 2 pipeline against `vendor/` and writes all five
  artefacts + geometry side-files into `client/public/dataset/`, every filename content-hashed
  (`<name>.<sha256[:10]>.<ext>`) except two stable, unhashed entry points: `manifest.json` — the
  cache-busting mechanism GitHub Pages needs, since its cache headers aren't configurable (same
  pattern Vite's own `index.html` → hashed-JS-bundle already uses) — and `integrity.json` (see
  D-15, below). `client/src/dataset.ts` fetches `manifest.json` first, then every other artefact
  only through the path it names — `base-dataset.json`'s own `geometry.nodePositions`/
  `edgePolylines`/`iconAtlases[].webp`/`.png` fields are set to their files' final hashed names
  BEFORE `base-dataset.json` itself is serialised and hashed, so every reference is always
  correct. **Real corpus, not synthetic**: 980 technologies, 989 edges, 12 empire overlays, 980
  detail payloads, search index, diagnostics.

  **Verified against a REAL headless browser** (Chromium via a transiently-installed
  `playwright-core`, never added to `client/package.json` — confirmed by a full
  `rm -rf node_modules && npm install` reproducing the working toolchain with zero trace of it):
  fetched `manifest.json` → `base-dataset.json` → both geometry side-files → a sample empire
  overlay → a real WebP icon atlas texture, decoded and drawn as a PixiJS `Sprite`, all through
  the real Vite dev/preview server AND a manually-simulated GitHub Pages project-subpath layout
  (`http://localhost/Gigastructural-Engineering-Tech-Tree/`, matching deploy-spike's own base-path
  finding) — 980 technologies, 989 edges, 1,960 float32 node-position values (980 × 2, exactly as
  expected, all finite/non-NaN — the little-endian `struct.pack("<Nf", ...)` packing round-trips
  against a real browser's `Float32Array`, not just Python's own encoder). One harmless console
  message (`favicon.ico` 404 — no favicon was added; cosmetic) was the only anomaly found.

  **D-15 (spec/decisions.md, later session): deploy model is local build, manual deploy — a
  PERMANENT constraint, not an interim gap.** The dataset cannot be built in GitHub Actions at
  all: vanilla Stellaris requires a Steam account that owns the game, so CI-side building would
  mean storing real Steam credentials as a secret (security/ToS exposure) or redistributing
  extracted game files (foreclosed outright by this project's own never-redistribute-vendor-
  content rule). No automation closes this — investigated and confirmed directly (a prior
  session's vendoring-automation investigation), not assumed. Consequently:
  - `client/public/dataset/` is **gitignored**, reversed from this session's own earlier
    decision to commit it. It's derived from vendored third-party content (a real, if lesser,
    redistribution question than `vendor/` itself); git would retain every ~7–18 MB version
    permanently; and a committed artefact can silently disagree with the pipeline commit that
    claims to produce it — exactly the staleness problem content-hashed filenames exist to
    prevent, reintroduced one layer up. Confirmed nothing from the prior session was ever
    actually staged/committed (`client/` was entirely untracked the whole time).
  - `tools/deploy_local.sh` (new) orchestrates the local side: build dataset, build client, zip
    `client/dist/`, publish it as a GitHub Release asset via the `gh` CLI, print the exact
    `gh workflow run` command. **Not executed for real this session** — creating a live Release
    is a "visible to others" action, left for the user to run themselves.
  - `.github/workflows/deploy.yml` is now `workflow_dispatch`-only, takes a `release_tag` input,
    downloads that release's `dist.zip`, sanity-checks it, and deploys it via the ordinary
    `actions/upload-pages-artifact`/`deploy-pages` steps — it builds nothing itself. Confirms
    Pages CAN deploy a build that happened elsewhere; the trade is a weaker integrity story than
    a full CI build (see below), stated honestly rather than glossed over.
  - `client/public/dataset/integrity.json` (unhashed, stable name): the pipeline commit SHA
    (+ dirty-tree flag), `vendor/manifest.json`'s per-source provenance (Vanilla's
    `game_version`; each mod's pinned commit/Workshop ID/content hash), which sources were
    loaded, and a sha256 checksum of every other artefact. **States provenance, does not verify
    it** — a mismatch between deployed bytes and claimed provenance is detectable (recompute,
    compare); a mismatch between the claimed commit and what a human actually ran is not, beyond
    trusting whoever ran `tools/build_dataset.py`. Never presented as CI-grade auditability.
  - Options considered and rejected as the PRIMARY model: (A) a private artefact store the CI
    workflow fetches from — still needs a human to build+publish, so it's just the chosen model
    plus an extra hop and, usually, another credential; (C) CI builds without ACOT/AoT — doesn't
    solve vanilla either way, and would make the CANONICAL deployed site quietly different
    (977 nodes, not 980) by default, the wrong default for real users. Kept as a genuinely useful
    LOCAL option instead (below).

  **Icon atlases now actually written — closed a real, previously-unnoticed gap.**
  `tools/build_dataset.py` never wrote atlas image bytes at all before this session:
  `base-dataset.json` referenced `technologies_0.webp` etc. and none of those files existed
  anywhere — the site could not render a single icon. Fixed: every sheet (`ctx.tech_sheets` +
  `ctx.perk_sheets`) is now encoded to both WebP and PNG (`pipeline.icons.pack.encode_webp`/
  `encode_png`), content-hashed, and `base-dataset.json`'s `iconAtlases[].webp`/`.png` fields are
  rewritten to the real hashed paths before that document is itself hashed. **Real measured
  total: 4,826,990 bytes WebP (4.60 MB) + 5,994,998 bytes PNG (5.72 MB) = 10,821,988 bytes
  combined** across 3 sheets (`technologies_0` 1008×2016, `technologies_1` 1008×1468,
  `ascension_perks_0` 504×384) — matches the figure a prior session's vendoring-automation
  investigation had already measured directly, confirming consistency. Verified end to end in
  the real headless-browser check above, not just "file exists on disk": a real `Assets.load()`
  fetch of the hashed WebP, a real `Texture`/`Rectangle` tile crop, a real `Sprite` drawn to the
  PixiJS canvas.

  **ACOT/AoT-absent builds: loud, specific diagnostic, not a generic warning.** A prior session's
  vendoring-automation investigation found building without ACOT/AoT yields **977 rendered nodes,
  not 980 − 7 = 973** — the 7 real ACOT/AoT-`requiresMods` technologies correctly disappear, but 4
  vanilla technologies ACOT overwrites (`tech_adaptive_combat_algorithms`, `tech_biomechanics`,
  `tech_titan_hull_1`, `tech_titan_hull_2`) are, perhaps surprisingly, **not themselves rendered
  in the FULL build at all** (their ACOT-overwritten form falls outside the P-16 closure,
  confirmed directly) — without ACOT they revert to vanilla content, which IS unconditionally
  rendered, and reappear. `pipeline.dataset_emit.build_diagnostics` now reports this specifically:
  `vendorSourcesLoaded`, `placeholderTechnologiesAbsent` (the exact 7, each naming which source
  they need), `vanillaTechnologiesRevertedFromAcotOverwrite` (the exact 4, each flagging whether
  the reversion is a real content difference — see the user-supplied domain note below).
  `tools/build_dataset.py` also prints a loud console banner when ACOT/AoT is missing. Both lists
  are maintained constants (`PLACEHOLDER_TECHNOLOGIES_REQUIRING_ACOT_AOT`,
  `VANILLA_TECHNOLOGIES_ACOT_OVERWRITES`), deliberately NOT dynamically derived — 3 of the 7
  placeholders are reached only through ACOT's own internal prerequisite chains, invisible
  without ACOT loaded, so nothing present in a reduced corpus could ever discover them — each
  re-verified against the real, full corpus by its own regression test
  (`tests/test_dataset_emit.py`), so a future re-vendor that changes one of these 11 keys fails a
  test rather than silently going stale. **User-supplied domain context**: most of ACOT's
  overwrites of vanilla technologies only add modifiers, invisible to this tool's display either
  way (`tech_adaptive_combat_algorithms`/`tech_biomechanics`,
  `contentDiffersFromOverwrite: false`) — the titan hull technologies are the documented
  exception, where ACOT's content materially differs (`contentDiffersFromOverwrite: true`).

  **Base-path resolution re-verified, not just inherited from the spike's old finding**: built
  `client/dist/`, served it under a locally-simulated `/Gigastructural-Engineering-Tech-Tree/`
  path prefix (not domain root), and confirmed the real headless-browser check above still passes
  identically — `vite.config.ts`'s `base: "./"` (relative, matching the spike's own lesson) plus
  every hand-written `fetch()` call using a relative path (`./dataset/...`) is what makes this
  work; an absolute leading-slash path would have passed locally at a domain root and silently
  broken here, exactly the failure mode the spike existed to catch before Stage 3 built on it.

## Stage 3 — rendering slices (client/src/main.ts, camera.ts, lod.ts, tokens.ts)

Static render, camera/pan/zoom/LOD, edges, row rendering (D-16), visual-fidelity passes, edge router rewrites, spacing passes, real faction pattern artwork.

- **Stage 3 real rendering has started, one vertical slice at a time — nothing in P-2 through
  P-13 is fully built client-side yet.** `client/src/main.ts` no longer just proves the toolchain
  (its earlier "foundation" framing is superseded); it draws real content against the real
  dataset. Two slices done so far:

  **Slice 1 — static render.** All 980 rendered technologies draw at their real P-2/D-13 layout
  positions (`client/src/main.ts`, node index in `base.technologies` = node index in the
  `node-positions.f32` side-file, per `pipeline/geometry.py`'s own contract), coloured by research
  area or crisis faction (`client/src/tokens.ts` — S-1's palette; exact hex values exist only for
  the five crisis factions in `spec/S-01-colour.md`, so physics/society/engineering blue/green/
  orange are this session's own first concrete pick, not spec-derived, pending the real ΔE2000-
  checked token set S-1 calls for), with each card's real icon (from the packed atlas) and
  localised name, plus one tier-band label and one lane label per band/lane (never once per lane
  per band — already satisfied the "renders once across the full lane stack" half of S-3's header
  requirement from this slice onward). Fit to the viewport once at load, no interaction.

  **Slice 2 — camera: pan, zoom, zoom-driven LOD.** `client/src/camera.ts` (a reusable camera
  controller, independent of node-rendering code) and `client/src/lod.ts` (the LOD-tier/threshold
  definitions). One transform (scale + translate) on the `world` container; per-node world
  coordinates are never mutated. Wheel/trackpad zoom and two-pointer pinch zoom, both anchored at
  the cursor/pinch-midpoint (the world point under it stays under it — verified numerically, not
  by eye, in this slice's headless-browser check); pointer-drag pan (Pointer Events, not
  mouse-only, per this file's own "every hover behaviour needs a tap/press equivalent" rule);
  keyboard arrows/+/-/0/1; clamped to `[fit-to-viewport scale, 1.5x native (100%) scale]` for zoom
  and to a modest margin (35% of viewport per axis) around the content bbox for pan, both
  reclamped on window resize. Initial view is byte-for-byte slice 1's original fit-to-viewport
  framing, unchanged.

  **LOD**: `spec/S-03-tier-differentiation.md`'s shedding table defines thresholds only for the
  six card BADGES (gate label/repeatable/rare/mod-requirement/gate icon/tier badge/dangerous) and
  the crisis pattern — none of which are built yet — plus one final threshold ("Coloured block:
  < 5%: everything remaining ... a flat coloured block") that, read literally, is the only point
  where a card's own name text and icon are ever said to shed, and only together. Since this
  slice's card is just rect+icon+name, `client/src/lod.ts` reuses two of S-03's OWN threshold
  values rather than inventing new ones, as a deliberate simplification pending real badges: name
  text sheds at **< 20%** (S-03's "Tertiary badges" boundary — the wrapped 20px name text is
  already illegible there), and the icon sheds (card becomes a flat coloured block) at **< 10%**
  (S-03's "Minimal card" boundary, not the literal 5%, since nothing else remains to shed between
  10% and 5% without badges built). Replace this 3-tier ladder with the real 7-stage table once
  badges exist — tracked here, not silently left looking spec-complete.

  **Known, deliberate gap against S-3's acceptance criteria**: S-3 requires tier-band headers to
  be **"a sticky header"** (viewport-pinned) — this slice's headers are instead counter-scaled
  (constant screen size) but anchored to their band/lane origin in world space, i.e. they pan with
  the content rather than staying fixed on screen. Explicitly scoped out of slice 2, not an
  oversight; real sticky/pinned headers are follow-on Stage 3 work.

  **Viewport culling was measured, not built.** A scripted, continuous headless-Chromium pan (90
  frames, `panBy` called every `requestAnimationFrame`) at each LOD tier, run against the real
  980-node corpus: full tier ~60ms median/~69ms p95 per frame, reduced tier ~60ms/~69ms, minimal
  tier ~32ms/~35ms (icon+name hidden, confirming LOD shedding — not culling — is what actually
  moves the number). All measured under this sandbox's software-WebGL fallback (SwiftShader, no
  GPU passthrough — see the console warnings any headless run here produces), which is materially
  slower than real hardware-accelerated WebGL; these are not real-device numbers. No sustained,
  reproducible sub-30fps behaviour was found to justify the complexity of viewport culling for a
  980-node scene at this stage — left out, per this slice's own "measure first" instruction, with
  the measurement method and caveat recorded here rather than silently deferred.

  Debug/verification surface: `window.__tt` (camera instance, current LOD tier, content bbox) is
  always attached in `main.ts` — this is a static client-only site with no backend, so exposing
  camera introspection on `window` costs nothing and is what a headless-browser check drives
  directly (cursor-anchor invariant, clamp-boundary assertions, scripted frame-time measurement)
  rather than screenshot-only eyeballing.

  Verified: `tsc --noEmit` and `vite build` both clean; a real headless-Chromium run against the
  real dataset — zero failed network requests, zero console errors (closed a pre-existing bare
  favicon-404 cosmetic gap along the way — `client/index.html` now ships an inline data-URI
  favicon), 12/12 numeric assertions passing (cursor-anchor invariant at three anchor points and
  zoom factors, min/max zoom clamps, pan clamp at an extreme drag, resize reclamping, 100%-scale
  reachability, minimal-tier reachability at a shrunk viewport) — plus four reviewed screenshots
  (fit-to-viewport, an intermediate zoom, 100% native, and minimal-tier at a shrunk viewport),
  each confirming real technology names/icons render legibly at the zoom levels S-03 implies they
  should, and the flat-block minimal tier actually drops icon+name as designed.

  Explicitly out of scope for both slices so far (real, tracked gaps, not oversights): edges,
  badges (rare/dangerous/repeatable/gate/tier), pattern fills, hover, click, selection, popups,
  search, empire-profile switching, sticky band headers.

  **Slice 3 — edges.** All 989 P-14 edges now draw, in world space, beneath the node cards.
  `pipeline/geometry.py`'s edge-polyline side-file already carried computed 4-point orthogonal
  H-V-H routes (including backward edges, routed through the same channel-offset mechanism in the
  opposite direction — nothing new was routed client-side); `client/src/main.ts` consumes them
  directly via a fixed 8-floats-per-edge stride, index-aligned with `base.edges` the same way
  node-positions.f32 is aligned with `base.technologies`. Batched into 6 `Graphics` objects total
  (one line + one arrowhead object per `EdgeKind`), never one per edge. Dashed/dotted styles are
  hand-drawn (PixiJS v8 has no native dash-pattern stroke) by walking each polyline's 3 segments
  with a dash-phase counter carried across corners; arrowheads are a filled triangle at the `to`
  endpoint, oriented along the final segment.

  **Two deviations from `spec/P-08-connectors.md`, both deliberate, both flagged rather than
  silently taken:**
  1. **Connector colour does NOT follow the tail's area/faction classification**, contra P-08's
     explicit rule. One neutral, low-contrast stroke colour (`tokens.ts`'s `EDGE_COLOR`,
     `0x5b6472`) for every edge regardless of kind — chosen because at 989 edges crossing area
     boundaries constantly, tail-colour would be ambiguous for cross-area edges and would compete
     with the cards it runs beneath. Kind is still a second, composed dimension (line style +
     opacity), matching P-08's "independent of colour" framing, just without the colour half.
  2. **Rounded corners are not implemented.** P-08's acceptance criteria calls for a consistent
     rounding radius at each elbow; this slice draws sharp H-V-H joins. Combining round joins with
     hand-drawn dash/dot patterns is materially more geometry work than this slice's scope
     justified, on top of the router itself already being a documented first pass
     (`pipeline/layout.py`'s own "not a full crossing-minimising/obstacle-avoiding" caveat).

  **Edge LOD** (`client/src/lod.ts`'s `edgeTierForScale`) is a second, independent ladder from the
  node LOD, reusing S-03's 35%/20% zoom boundaries only because they're the project's existing
  breakpoints — S-03's own shedding table has no row for edges at all, so nothing here is
  spec-derived: below 35% zoom, `alternative` and `potential-gate` edges (and every arrowhead,
  including on the `prerequisite` edges that remain) shed; below 20%, all edges shed. The bottom
  status strip now reports the live visible-edge count and the active edge LOD tier alongside the
  existing camera/node-LOD line.

  **Verified**: `tsc --noEmit` and `vite build` clean; a real headless-Chromium run against the
  real 980-node/989-edge dataset — zero failed requests, zero console errors; drawn edge counts
  match the dataset exactly (989 total, 888/76/25 by kind, both from `base.edges` and from what
  was actually batched into the 3 line `Graphics` objects); every edge's polyline start/end point
  lands inside its source/target card's bounding box (small epsilon), checked for all 989, not
  sampled; edge-LOD boundaries assert correctly at 40%/30%/15% zoom. Four screenshots reviewed:
  fit-to-viewport (edges correctly hidden below the 20% full-shed floor at this zoom), the dense
  Standard×T5 cell at 100% (solid arrowed prerequisite lines read clearly; a faint dotted
  `alternative` line is visible only in the gaps between cards, as expected since edges draw
  beneath opaque card fills), a sparse Sirenalia cluster at 100%, and the one confirmed 5-band
  backward `potential-gate` edge (`tech_cosmogenesis_escort` → `tech_missiles_1`) — this last one
  could NOT be visually picked out by eye at any zoom tried, including a mid-point framing and an
  entry-point framing at its target; see the three open design questions below.

  **Three open design questions, deferred to the user, not decided this slice** (see
  HANDOFF.md's "Next prompt" section for the recommendations attached to each):
  1. Are the 34 backward edges legible in their shared channel-offset gutter, or do they read as
     noise?
  2. Do the 7 long-span (up to 5-band) backward `potential-gate` edges need a different treatment
     (stub connectors, suppress until selection, separate channel) than the generic router gives
     them today?
  3. Is edge density in the Standard×T5 cell (253 nodes) readable at 100% zoom, or does it need
     bundling/opacity/hide-until-selected treatment?

- **Stage 3 slice 4 — row rendering (D-16's re-axis), neutral cards, sticky headers, folded LOD**
  (later session). Closes the renderer/dataset naming debt slice 3's own writeup deferred
  ("`lanes`/`laneId`... renamed... tracked as the next slice's work") and makes the client match
  D-16's row model instead of the superseded crisis-faction-lane one.

  **Naming debt paid first, as planned**: `lanes`/`laneId` renamed to `rows`/`rowId` across
  `schema/base-dataset.schema.json`, `pipeline/layout.py`/`pipeline/dataset_emit.py` (including
  internal variable names — `lane_counts`→`row_counts`, `lanes_json`→`rows_json`, the
  `TechnologyLayoutInput.lane` field→`.faction`), `schema/generated/dataset-types.ts`
  (regenerated), and `client/src/main.ts`. A breaking dataset change, deliberately (D-15: the
  dataset is gitignored and rebuilt locally, no deployed consumer to migrate). Full pytest suite
  and `tsc --noEmit` both stayed green through the rename before any rendering work began, per this
  slice's own instruction not to write new code against the old names.

  **Row rendering**: all 18 rows draw in `base.rows` order, including the zero-population Compound
  row (a real, labelled, collapsed header-height strip — confirmed by direct headless screenshot,
  not just a count assertion). Category rows get a header chip (research-area colour, label + node
  count); faction rows get a header chip in the faction's own signed-off colour
  (`CRISIS_FACTION_COLORS`, unchanged) plus a tiled pattern as row backing at low opacity, beneath
  edges beneath cards. `client/src/tokens.ts` gained `CRISIS_FACTION_ROW_PATTERNS` (base + accent
  colour + motif style per faction) and `rowChipColorFor()` — every row colour decision reads from
  tokens.ts, no hardcoded hex at the main.ts call site. **The pattern motifs are procedural
  placeholders** (bounded diagonal-hatch/dot/band shapes drawn directly, no traced SVG, no PixiJS
  mask — clipped by construction instead, since a mask added real scene-graph complexity for no
  benefit here) — CLAUDE.md's open Blokkats-flag-tracing item is still open, and Sirenalia's
  "high-contrast sweeping bands" accent colour is this session's own placeholder pending a real
  signed-off hex, both flagged in `tokens.ts`'s own comments, not silently presented as final art.
  Row/band geometry (row heights, row y-offsets, band x-starts) is recomputed client-side from
  `pipeline/layout.py`'s own constants (`INTRA_GAP_X`/`_Y`, `INTER_BAND_GUTTER`,
  `ROW_HEADER_HEIGHT`, `ROW_GUTTER`, subgrid width 4) mirrored into `main.ts`, the same way
  `CARD_WIDTH`/`CARD_HEIGHT` were already mirrored in slice 2 — no geometry side-file carries row
  heights or band extents, only node positions and edge polylines do.

  **Cards go neutral**: `CARD_FILL`/`CARD_STROKE_NEUTRAL` (tokens.ts) replace the old
  `backgroundColorFor()` per-card area/faction fill, which is deleted (no dead fill code path left
  behind). The card's own OUTLINE still carries research area unconditionally — unaffected by
  D-16, per CLAUDE.md's own text that this is about the card's background, not its outline; the
  rare/dangerous outline override stays out of scope for this slice. Card content: icon, name,
  cost (`Cost: N`, omitted entirely — no line at all, never 0/"N/A" — for the 15/980 nodes with a
  null cost), and a small `T<n>` tier badge. A repeatable node renders no tier badge this slice
  (D-13's exception says its badge should be repeat count, which is explicitly next-slice scope —
  showing the wrong badge type would misrepresent it, so it shows neither this slice).

  **Sticky headers close the S-03 gap slice 2 deliberately deferred.** Band labels pin to the
  viewport's top edge, row labels to its left edge, tracking their band's/row's own screen position
  along the other axis (so a label still slides as its band/row scrolls, just clamped to the
  pinned edge) — closes CLAUDE.md's own recorded gap ("counter-scaled... rather than real
  sticky/pinned headers... follow-on Stage 3 work"), now done. Implementation is a "only the
  currently active band/row label is visible" model (never a z-order/overlap trick): exactly one
  band label and one row label are visible at any camera position, determined by which band's
  x-slot / row's y-slot contains the viewport's own top-left world corner — verified numerically
  (`bandLabelsVisibleCount()`/`rowChipsVisibleCount()` on `window.__tt`) at four independent
  camera positions (fit view plus three arbitrary pans), not just eyeballed from a screenshot.

  **LOD folded into the existing ladder, not a parallel one** (`client/src/lod.ts`): tier badge and
  cost text shed together with the name at the existing `NAME_SHED_THRESHOLD` (<20%, S-03's
  "Tertiary badges" boundary — both new aliases, `COST_SHED_THRESHOLD`/`TIER_BADGE_SHED_THRESHOLD`,
  point at the same constant); icon shedding unchanged (<10%). New: `PATTERN_SOLID_THRESHOLD`
  (0.07, S-03's own named pattern-degradation boundary) drops a faction row's accent motif below
  7% zoom, leaving only its flat base tint — the base/accent split was built as two separate
  Graphics layers specifically so this toggle needs no redraw. Edge LOD (35%/20%) is unchanged.

  **A real defect found by this session's own screenshot review, not a test** (the same
  "screenshots catch bugs no test could" pattern HANDOFF.md documents repeatedly): one rendered
  technology, `giga_tech_aeternite_weaponry`, displayed its raw internal key as its name. Root
  cause: its real localisation entry
  (`vendor/mods/gigastructures/localisation/english/giga_ehof_functions_l_english.yml:93`) has a
  VALUE that is verbatim its own KEY — the mod author never actually wrote a display name — and
  `_require_resolved` only checked for a leftover `$...$` token, which this string doesn't have,
  so it passed through as "resolved." Fixed with a new, minimally-scoped mechanism mirroring the
  project's existing override-file precedent: `pipeline/name_overrides.py` +
  `config/name_overrides.txt` (same format/review bar as `config/overwrite_overrides.txt` — a
  reviewed `<key> = <name>  # <justification>` line, hard-fail if a `name == id` case has no entry).
  Seeded with exactly the one real case found, named by pattern-matching its two sibling
  Aeternum T5 technologies ("Aeternite Loop-Quantum Defensive Matrix", "Aeternite Planetcraft
  Refurbishment") → "Aeternite Weaponry Systems", flagged in the override file's own justification
  as this session's inference pending a real upstream translation. `UnresolvedLocalisationTokenError`
  now also covers this shape; `tests/test_name_overrides.py` (loader mechanism) and
  `tests/test_dataset_emit.py::test_no_rendered_technology_name_equals_its_own_raw_key` (real-corpus
  regression, plus the specific fixed string) both green. A second, purely visual defect from the
  same review pass — the cost line colliding with a 2-or-3-line wrapped technology name — was fixed
  by anchoring cost to the card's bottom edge and pushing it below the name's actual measured
  height when a name wraps past two lines, rather than a fixed offset assuming exactly two.

  **Verified**: `tsc --noEmit`, `vite build`, and the full pytest suite (1,365 passed, up from
  1,357 — the new name-override tests) all clean. A real headless-Chromium run against the rebuilt
  980-node/989-edge/18-row dataset: zero console errors, zero failed requests; 980 cards drawn;
  18 rows drawn including the zero-population Compound row; every row's drawn card count matches
  its dataset `technologyCount` exactly; zero rendered names contain a literal `$`; exactly 15
  cards render no cost line; sticky-header handoff asserted at four camera positions (exactly one
  band + one row label visible each time). Four screenshots reviewed: fit-to-viewport, 100% on the
  densest cell (voidcraft × T5), 100% on the Blokkats row, and the collapsed zero-population
  Compound row framed at its own top edge.

  **Honest assessment, as asked**: density at 100% on voidcraft × T5 (47 nodes, down from the old
  Standard × T5 cell's 253) reads comfortably — cards are legible with real breathing room, a
  material improvement over what the 253-node cell would have looked like under the same per-card
  footprint. Faction row patterns read clearly as a distinct "you are in crisis-faction territory"
  signal at 100% without fighting the cards for attention — the low accent opacity and neutral card
  fill keep the pattern visually behind the content; the flat base tint alone (<7% zoom) is even
  less intrusive. The patterns are visibly procedural rather than polished art, which is expected
  and already flagged, not a new finding.


- **Stage 3 visual-fidelity pass (later session) — four appearance defects, found by the user
  reviewing slice 4's screenshots, fixed with no new features.** v1 (`github.com/Tempest113/
  Gigas-Tech-Tree`) was consulted for styling only (CSS, colour/panel/chip/spacing treatment) —
  never for layout computation, tier/column assignment, or data handling, per the user's explicit
  scope limit (v1's tier-placement bug is exactly why v2 exists). No v1 styling value conflicted
  with a CLAUDE.md signed-off value this session — the faction hex values were reused unchanged
  throughout; only scale/contrast/geometry of the patterns changed (see below).

  **1. Sticky headers removed entirely, not hidden behind a flag.** The user rejected slice 4's
  viewport-pinned band/row headers outright: "a banner floating in the top-left that swaps
  contents as you scroll doesn't belong to any visible object." `client/src/main.ts`'s `sticky`
  container, `repositionStickyHeaders`, and the single-active-label visibility toggling are gone.
  Row header chips are now ordinary WORLD-space content, anchored at their own row's top-left,
  scaling and panning with everything else — the slice-2 counter-scaling this project carried
  since the very first camera slice (`HEADER_LABEL_SCREEN_SIZE`, kept-at-scale-1 labels) is also
  gone, per the user's own diagnosis that counter-scaling was the ROOT CAUSE of the original label
  collision the sticky mechanism was built to fix: world-scaled labels can't collide with each
  other because each holds a position relative to its own geometry, not a shared screen corner.
  In its place, v1's treatment: a small, subdued tier-band label repeats above every row's own
  POPULATED band cell (`cellCounts.get(...) > 0`), not once globally. **This is the SECOND S-03
  header acceptance criterion superseded by direct user review**, after D-16's row re-axis already
  replaced "lane" with "row" in the first one — `spec/S-03-tier-differentiation.md`'s "sticky
  header... renders once across the full lane stack" criterion is struck through and replaced
  in-file with the repeated-per-cell model, with the reasoning and the "second-supersession"
  pattern recorded explicitly in the spec itself so a future session doesn't quietly reintroduce
  either superseded criterion. Labels becoming illegible at fit-to-viewport zoom is now stated as
  INTENDED behaviour, not a shortfall — at overview zoom the user navigates by row shape and
  colour, not by reading text.

  **2. Every row (18, not just the 5 faction rows) gets a real panel: tinted fill, border, rounded
  corners.** Previously only faction rows had any backing at all, so the 13 category rows read as
  empty space and the 5 faction rows looked like a different species of object on the canvas.
  `client/src/tokens.ts` gained `ROW_PANEL_RADIUS`/`ROW_PANEL_FILL_ALPHA`/`ROW_PANEL_BORDER_ALPHA`/
  `ROW_PANEL_BORDER_WIDTH` (no hardcoded colours at the `main.ts` call site); `drawRowPanel` draws
  the identical treatment for every row, differing only in the colour `rowChipColorFor` already
  returns (area colour for a category row, the faction's own signed-off colour for a faction row)
  — the SAME function the header chip itself uses, so a panel and its own chip can never disagree.
  Faction rows layer their pattern accent on top of this shared panel rather than owning a
  separate, differently-styled background.

  **3. Faction row patterns rescaled for row backing — a real, embarrassing bug found and fixed,
  not just a cosmetic tune.** CLAUDE.md's signed-off pattern specs (`S-1`) were pinned for a
  270x92px CARD fill, back when crisis faction was a card-level property; slice 4 promoted them to
  full-ROW backing (rows up to ~12,888px wide) with NO rescaling, so a pattern sized for a card
  tiled across a whole row read as dense wallpaper. **Rescale alone wasn't the only bug**: the
  "diagonal" style's line-drawing math (`accent.moveTo(x0, yy).lineTo(x0+width, yy+width)`, `yy`
  ranging across the row's own WIDTH rather than its height) drew each diagonal line completely
  UNBOUNDED in the y direction — a faction row's pattern visibly bled diagonal stripes across the
  ENTIRE canvas height, striping every category row above and below it too. Found by this
  session's own screenshot review (the "screenshots catch what tests couldn't" pattern this
  project's history is already full of, applied here to the session's own work rather than the
  user's). Fixed by clipping each diagonal line analytically to the row's own local rectangle
  `[0, width] x [0, height]` before it's ever handed to `Graphics` (line-vs-rectangle intersection
  on the `y = x + c` family), not by adding a PixiJS mask — the module's existing "no mask, bounded
  by construction" approach is kept, just actually applied correctly this time. Feature size now
  scales with the row's OWN height (`Math.min(320, Math.max(140, height * 0.9))`) rather than a
  fixed small constant, and `accentAlpha` is lowered across the board in `tokens.ts` (row backing
  is texture, not a foreground element) — Sirenalia's kept visibly higher than the other four
  ("high-contrast" is in S-1's own text, not flattened away). **Sirenalia's style changed from
  flat rects (`"bands"`) to real curved bands (`"sweeping"`)** — S-1 specifically names "soft
  sweeping bands," and flat horizontal stripes weren't that; PixiJS v8's `Graphics.
  quadraticCurveTo` draws genuine wavy strokes with no fallback needed, confirmed feasible rather
  than assumed infeasible. The real traced Blokkats flag SVG (still an open item) and a real
  signed-off Sirenalia accent colour (still a white placeholder) remain not done — flagged in
  `tokens.ts`, not silently treated as final art.

  **4. Card name text clamped to 2 lines with an ellipsis, never shrunk, never overflowing.**
  `pipeline/layout.py`'s own `CARD_WIDTH`/`CARD_HEIGHT` comment already states the card was sized
  "to fit the p95 rendered-name length (39 chars) across up to two lines" — 2 lines is therefore
  not a new number invented this session, it's the card's own original sizing intent, now actually
  enforced. Real corpus distribution: p50=21, p90=35, p95=39, p99=46, max=54 chars — 2 lines
  covers everything through p95 untruncated; only the ~5% beyond it (up to the 54-char real
  maximum, `"Blokkilian Equations - Planckscale Particle Generation"`) ever shows an ellipsis.
  Implementation: PixiJS's own `wordWrap` is turned OFF (it has no line-count cap, which is
  exactly how names previously overflowed) in favour of `wrapAndClampName` — a greedy word-wrap
  simulated against a real `CanvasRenderingContext2D.measureText` call (the same measurement
  PixiJS's own `CanvasTextRenderer` uses internally), capped at 2 lines, ellipsis-truncating the
  final line via binary search on the character count. Every produced line is DEFENSIVELY
  re-clamped to the column width regardless of how it was produced, so a single word wider than
  the text column on its own (not just an overlong full name) still can't push text past the card
  edge. Verified numerically over all 980 rendered nodes (`window.__tt.checkNameBounds()`, a real
  headless-browser assertion, not eyeballed): zero rendered name's bounding box exceeds its own
  card's bounds, in either direction, on either axis.

  **Verified**: `tsc --noEmit`, `vite build`, and the full pytest suite (1,365 passed, unaffected —
  this pass touched `client/` only) all clean. A real headless-Chromium run against the rebuilt
  980-node/989-edge/18-row dataset: zero console errors, zero failed requests; `app.stage` has
  exactly 1 child (`world` itself — no sticky/pinned layer survives, structurally, not just by
  eyeballing the render); 18 row panels drawn; 980 cards drawn; every row's drawn card count
  matches its dataset `technologyCount` exactly, including the zero-population Compound row; the
  name-bounds assertion above passes over all 980. Five screenshots reviewed: fit-to-viewport
  (category rows now visibly read as distinct tinted bands, not empty space, at ANY zoom — the
  direct fix for defect 2), 100% on a mid-density category row (`voidcraft` ROW, not merely
  `category === "voidcraft"` — a technology's own `category` field survives faction-first row
  reassignment unchanged, so filtering by `category` alone can silently pick a node that actually
  lives in a faction row; the verification script itself had this exact bug on a first pass, found
  and fixed the same way the pattern-bleed bug was), 100% spanning a category→Aeternum→Blokkats
  row boundary (patterns now cleanly confined to their own row, panel borders read as real
  container edges), 100% on the Compound row (its collapsed panel, chip, and "No technologies in
  the current corpus." note all render together, reading as deliberate rather than broken), and
  the longest-named node (`giga_tech_blokkilian_equations`, 54 chars) framed to show the ellipsis
  directly.

  **Honest assessment, as asked**: faction rows now read as the SAME class of object as category
  rows — same panel, same border treatment, same corner radius, differing only in colour and (for
  factions) an added texture layer on top, which is exactly what "differing only in colour and
  texture" asked for. Before this pass they read as a genuinely different, more "finished" species
  of object next to conspicuously empty category rows; that gap is closed. The one place a
  difference remains legible, by design: faction rows carry a visible accent pattern and category
  rows don't, which is correct per this session's own instruction (colour/pattern still encode
  faction membership) rather than a residual inconsistency.

- **Stage 3 visual-fidelity pass 2 (later session) — five more appearance defects from the user's
  own screenshot review, plus real faction pattern artwork replacing the procedural placeholders.
  No new features; v1's appearance remains the target, v1's layout/data logic is not a reference
  for anything.** Confirms the previous pass's own "collapsed panel/chip/note" description of the
  Compound row is now stale in a second way too: it's real screenshotted at 2 populated nodes in
  this session's own verification, not the 0-node empty state that description assumed.

  **1. Card/band spacing widened** (`pipeline/layout.py`, mirrored in `client/src/main.ts` —
  the single named place these values live, per that file's own comment). `INTRA_GAP_X`/`_Y`
  16→24px, `INTER_BAND_GUTTER` 48→96px — concrete values chosen because the re-axis's densest cell
  (voidcraft×T5, 47 nodes) leaves real room to spend and measured performance (median 6.1ms/p95
  12.1ms on real hardware WebGL) has real headroom; `INTER_BAND_GUTTER` doubled rather than
  incrementally nudged since it does double duty as both the visual tier-band separator and the
  reserved P-8 edge-routing channel. **Real rebuilt canvas: 13,632 × 11,608px, up from 12,888 ×
  10,800px** (`tests/test_layout_corpus.py::test_densest_actual_row_band_cell_and_canvas_dimensions`,
  updated and re-verified against the real corpus) — densest cell membership (voidcraft×T5=47) is
  unaffected, only the pixel spacing between/around it moved.

  **2. Tier-band alternating background tint** (`client/tokens.ts`'s
  `TIER_BAND_TINT_COLOR_EVEN/ODD`/`_ALPHA_EVEN/ODD`, drawn in `main.ts` as the FIRST layer in
  `world`, beneath every row panel). Two neutral, non-hued overlays (white lightens, black darkens
  the dark `#111318` canvas background) alternate by band index, spanning exactly each band's own
  card-slot width — the untinted `INTER_BAND_GUTTER` doubles as the boundary line between adjacent
  tints, so row/faction colour on top still dominates while a band boundary is visible at a glance
  across the whole canvas, confirmed in the fit-to-viewport screenshot.

  **3. Edges: rounded corners + brighter trace colour** — closes `spec/P-08-connectors.md`'s
  "rounded corners... quadratic/arc segments" requirement, previously a stated scoped
  simplification (sharp H-V-H joins) in the original edge slice; see that spec file's own updated
  entry for the mechanism (`roundPolylineCorners`, quadratic-bezier-sampled arcs at each of the
  4-point polyline's two interior corners, endpoints always preserved exactly — corner rounding is
  a RENDER-time transform only, the server-computed polyline in `edge-polylines.f32` is never
  re-routed). `EDGE_COLOR` `0x5b6472` slate → `0x5cc9e6` light blue-cyan (v1's PCB-trace look),
  `EDGE_STROKE_WIDTH` `2` → `1.4` — the single-neutral-colour-for-every-kind rule is unchanged,
  only the shared colour's hue/brightness and stroke width moved. Verified numerically, not just
  visually: every one of the 989 edges' rounded start/end point still lands inside its source/
  target card's bounds (`window.__tt.checkEdgeEndpointsInCards`, 0 violations).

  **4. Row-chip / per-cell tier-label overlap, fixed.** The Stage 3 visual-fidelity pass's own
  world-anchored chip and repeated-per-cell tier label (which replaced the removed sticky headers)
  occupied the SAME vertical sub-range of the 40px header strip — for band 0 (and any band whose
  x-start falls under a chip's own width, which varies by row label length), the two visibly
  collided. Fixed by giving each a strictly disjoint vertical band: `ROW_HEADER_HEIGHT` 40→52px
  (pipeline/layout.py, mirrored in main.ts — contributes to the canvas growth in point 1 above),
  chip top-anchored with a small pad, cell label anchored strictly below the chip's own bottom
  edge with a fixed gap. Verified numerically across every row and every one of that row's
  populated bands (`window.__tt.checkChipLabelOverlap`, 0 violations across all 18 rows), not by
  eye.

  **5. Real faction pattern artwork, replacing the procedural placeholders** — all five geometries
  user-supplied (a Gigastructures contributor), except Katzenartig's, explicitly flagged
  provisional. `RowPatternSpec.accent: number` → `accents: number[]` (Sirenalia needs several
  shades); every style function lives in `main.ts`'s `drawFactionRowPattern`:
  - **Aeternum**: tiled hexagon outlines, lighter pink (`#823269`, the in-game PINK flag colour)
    on a NEW burgundy row background (`#591227`, the in-game BURGUNDY flag colour rgb 89,18,39,
    added to `tokens.ts` this session).
  - **Blokkats**: the flag device (circle containing a lightning-bolt/arrow chevron) tiled as a
    staggered, interlocking herringbone lattice, lighter green (`#63A85C`) outline only on the
    darker flag green (`#1C451C`) — never solid shapes.
  - **Compound**: large-radius, slow-curving swirls (dark-matter theming), deliberately not tight
    spirals per the user's own warning that tight spirals read as noise once tiled across a
    12,000px+ row. Real population as of this session (15 nodes via the D-7 override
    reclassification above) — no longer the zero-population hypothetical the earlier "dots"
    placeholder was written against.
  - **Sirenalia**: several overlapping sinusoidal bands at different amplitude/phase, each its own
    pink/purple shade (3 shades) — S-1's own "high-contrast sweeping bands" wording, now actually
    multi-band/multi-shade rather than one accent colour repeated.
  - **Katzenartig Imperium**: gold chevrons/pinstripes on deep blue, military-heraldic —
    **PROVISIONAL**, the one faction the user had no specific in-game reference for; this is
    Claude's own inference from the two already-signed-off hexes alone, flagged in `tokens.ts`'s
    own comment so a future session doesn't treat it as settled art the way the other four are.

  **Two real bugs found and fixed while wiring this in, neither visible from the code alone —
  both found by this session's own screenshot review, the same "screenshots catch what tests
  couldn't" pattern this project's history already has several entries for:**
  - **Row panel background was reading the wrong colour source.** The row PANEL's fill/border
    (added in the previous visual-fidelity pass) called `rowChipColorFor` — the CHIP's own
    flag-identity colour (`CRISIS_FACTION_COLORS`) — instead of each faction's own row-BACKING
    tone (`CRISIS_FACTION_ROW_PATTERNS[...].base`). CLAUDE.md already stated this distinction for
    Blokkats specifically ("the authentic flag colour, reserved for tier-band/lane backing, not
    node fill") but the code never actually applied it — the panel and the chip drew the same
    colour, silently. New `tokens.ts` function `rowPanelColorFor` fixes this for all five
    factions, not just Aeternum (whose new burgundy exposed the bug).
  - **The pattern accent's clipping mask was never a scene-graph child, so its transform never
    updated and the mask clipped in the wrong coordinate space** — every faction row's pattern
    accent silently clipped to nothing (rendered correct geometry, zero visible pixels) regardless
    of zoom or row. `maskToRowRect`'s mask Graphics must be added as a child of the SAME container
    its target is in (`rowBackingLayer`) for PixiJS to update its transform each frame; an earlier
    version left it unparented on the (wrong) assumption that a `.mask` assignment alone was
    sufficient. Both `main.ts` and `tokens.ts` carry corrected comments recording this.

  **Verified**: full pytest (1,368 passed), `tsc --noEmit`, `vite build` all clean. A real
  headless-Chromium run against the rebuilt 980-node/989-edge/18-row dataset: zero console errors,
  zero failed requests; `checkNameBounds`/`checkChipLabelOverlap`/`checkEdgeEndpointsInCards` all
  report 0 violations (980, 18-rows-worth, and 989 checked respectively). Eight screenshots
  reviewed: fit-to-viewport (tier banding visible across the whole canvas at a glance), 100% on
  voidcraft×T5 (comfortable card spacing, cyan rounded-corner traces legible in the gaps), 100% and
  a row-fitted close-up on each of the five faction rows, and a framed multi-elbow backward
  `potential-gate` edge (visibly rounded corners, thin cyan PCB-trace look).

  **Honest assessment, as asked**: all five patterns read as distinct, identifiable textures at a
  glance without competing with cards — confirmed at both the dense 100%-zoom view (pattern visible
  only in the gaps between/around cards, cards still dominate) and the fit-to-viewport overview
  (patterns still legible as thin textured strips at 8.4% zoom). Aeternum's hexagons and Blokkats'
  herringbone are the clearest at a glance; Compound's slow swirls read cleanly as "dark, curving,
  not noisy" exactly as intended; Sirenalia's multi-shade waves are the most visually rich of the
  five, appropriately so per S-1's own "high-contrast" text; Katzenartig's gold chevrons read fine
  but, as flagged, are Claude's own inference rather than a described device — the weakest claim to
  being "real art" of the five, by design.

- **Edge router card-avoidance rewrite, spacing pass, and real Sirenalia geometry (same session,
  continuing directly from the Part-0 reconciliation above).** Closes P-2's long-standing "a
  first-pass router, not a full crossing-minimising/obstacle-avoiding one" follow-on note, the
  card-avoidance half of it specifically (crossing minimisation itself stays open, unchanged).

  **Measured first, not eyeballed.** A script counting edge-polyline segments intersecting an
  unrelated card's bounding box found **2,586 real crossings across 722 of 989 edges** on the
  pre-existing 4-point H-V-H router (`pipeline.layout._route_edges`) — this is the mechanism
  behind the user's reported false-connection case (an edge visually passing under an unrelated
  card). Root cause: the router's single vertical run always sat at a genuinely card-free x (any
  inter-column gap is empty across EVERY row sharing a band, since column x depends only on
  band+column, never row), but the long FINAL horizontal segment connecting that x to the actual
  target position necessarily crossed whatever unrelated cards occupied the intervening
  row(s)/band(s) at that fixed y. Several 4-point variants were tried and independently measured
  (vertical run adjacent to source vs. target's band, with and without forcing a true band-edge
  reach) — **none reduced the crossing count below the original baseline**, because a
  single-bend H-V-H shape always has exactly one long, unconstrained horizontal segment
  somewhere, regardless of which end the bend sits near.

  **The fix that reaches zero needs a second bend.** `_route_edges` now emits a 6-waypoint,
  5-segment polyline: exit stub → vertical run (in a column gap, card-free for its FULL height,
  independent of row) → horizontal transit through the edge's own SOURCE ROW's header/gutter
  strip (card-free for the FULL canvas width, independent of column/band) → vertical run → entry
  stub. Combining two independently-safe primitives (a column gap's full-height safety, a row
  header's full-width safety) is provably safe for the polyline's ENTIRE length, not just tuned
  to reduce a residual — **measured real result: 0 crossings across all 989 edges**. `MIN_STUB`
  (8px, `pipeline/layout.py`) enforces a real minimum stub at both ends (previously the hash-based
  channel offset could land at 0, reading as an immediate vertical drop rather than a PCB-trace
  lead-out).

  **Real schema/side-file change, not silently absorbed**: `pipeline/geometry.py`'s
  `POINTS_PER_POLYLINE` moved 4→6 (`FLOATS_PER_EDGE` 8→12); `client/src/main.ts`'s
  `FLOATS_PER_EDGE_POLYLINE` mirrored, 8→12. `roundPolylineCorners`/`tracePolyline`/`addArrowhead`
  were already written generic over point count (loop over `pts.length`, not a hardcoded 4) and
  needed zero logic changes — only their stale "4-point"/"3 segments"/"two interior corners"
  comments were corrected. The user's exact named technologies
  (`tech_improved_deflectors`/`tech_basic_cloaking_fields`) don't exist under those literal keys
  in the current vendored corpus, but the real corpus DOES contain "Improved Deflectors" (T1)
  directly above "Storm Manipulation" (T2) with "Basic Cloaking Field" (T2) beside it — the exact
  neighbourhood shape described — screenshotted and confirmed clean (no trace runs under "Storm
  Manipulation").

  **Spacing** (`pipeline/layout.py`, mirrored in `client/src/main.ts`, the one named place these
  constants live): `INTRA_GAP_X` 24→40px (flagged still-too-tight; `INTRA_GAP_Y` confirmed
  acceptable at 24, unchanged). `ROW_GUTTER` 24→48px. New `AREA_GROUP_GUTTER` (96px), applied
  only at the 3 real group boundaries (`computing`→`archaeostudies`, `statecraft`→`industry`,
  `voidcraft`→`Aeternum`) via `_row_order`'s new `row_group_of` return (0/1/2 for the three
  research areas, `len(AREA_ORDER)` for every faction row) — surfaced client-side from the SAME
  `tech.area` lookup `main.ts` already used for row-chip colouring, no schema change needed for
  this half. `ROW_HEADER_HEIGHT` 52→68px (more clearance before the first card row); the per-cell
  tier label's x moved from a hardcoded `+4` to `+CHIP_MARGIN`, sharing the chip's own left edge
  (closes the reported chip/label misalignment). **Real measured canvas: 14,160 × 12,616px**
  (was 13,632 × 11,608px).

  **Sirenalia geometry, ported from v1 directly (`github.com/Tempest113/Gigas-Tech-Tree`), at the
  user's explicit request after three earlier procedural attempts were rejected.** v1's actual
  pattern lives in `js/render.js`'s `drawWaves` — a canvas-2D function, NOT CSS (the CSS only
  holds a `--siren` colour custom property used for badges/legend elsewhere; scope-limit
  respected, no layout/data logic read from v1). Ported verbatim: 4 layers, each a FILLED region
  bounded above by a sine curve (`y = rowTop + rowHeight * (base + sin(t) * amp)`) and below by
  the row's own bottom edge — not a stroked ribbon, which is what all three earlier rejected
  attempts drew instead. v1's own per-layer `{amp, phase, base, alpha, period}` constants and 60px
  sampling step are copied directly, not re-tuned. **Corrects this project's own prior claim**:
  an earlier session's placeholder both stated and implemented "several distinct pink/purple
  shades" for Sirenalia; v1 actually uses ONE accent colour across all 4 layers with only ALPHA
  varying (0.05→0.09, low-to-high) — `tokens.ts`'s Sirenalia entry and its comment are corrected
  to match, using the already-signed-off `#B0338C` hex as that one colour (v1's own `--siren` CSS
  value belongs to a different, unrelated palette — out of this session's "styling only" scope,
  which extends to porting v1's rendering TECHNIQUE, not overriding an already-signed-off
  CLAUDE.md hex). No PixiJS-vs-canvas-2D capability gap was hit: `Graphics.fill()` called once per
  layer's built path reproduces v1's per-layer `ctx.fill()` call directly.

  **Aeternum lightening** (user: hexagon stroke read too dark against the burgundy backing): the
  signed-off hexes (`#591227` backing, `#823269` flag pink) are unchanged; `tokens.ts`'s Aeternum
  pattern spec's `accents[0]` (the colour `main.ts`'s hexagon stroke actually draws with) is now a
  LOCAL, rendering-only lightened variant — `#823269` blended 35% toward white → `#AE7A9E` — with
  `accentAlpha` also raised 0.30→0.42 ("opacity" was explicitly named as the other half of the
  ask). The signed-off constant itself (`CRISIS_FACTION_COLORS.Aeternum`, used elsewhere e.g.
  badges) is untouched.

  **Verified**: full pytest (1,381 passed), `tsc --noEmit`, `vite build` all clean. Real dataset
  rebuilt (`tools/build_dataset.py`) and served via `vite preview`; a real headless-Chromium run
  (`playwright-core`, transient, not added to `package.json` — same pattern every prior session's
  verification used): zero console errors, zero failed requests, `stageChildCount === 1`,
  `rowPanelCount === 18`, `checkNameBounds`/`checkChipLabelOverlap`/`checkEdgeEndpointsInCards`
  all 0 violations, and a NEW `checkMinStubLength` (this session, checks the RAW pre-rounding
  polyline's exit/entry segment lengths against `MIN_STUB`) — **0 violations across all 989
  edges**. Five screenshots reviewed: fit-to-viewport (the three research-area blocks and the
  faction block now visibly separated as 4 groups, not 18 evenly-spaced strips), the
  Improved-Deflectors/Storm-Manipulation/Basic-Cloaking-Field neighbourhood at 100% (clean
  gutter-routed traces, directly refuting the reported false connection), the Sirenalia row at
  100% (real layered wave fill, replacing the old stroked-ribbon placeholder), the Aeternum row at
  100% (visibly lighter hexagon stroke against the burgundy backing, confirmed side by side with
  the Blokkats herringbone row directly below it), and the voidcraft→Aeternum row-group boundary
  at 25% zoom (the larger inter-group gap reads clearly against the ordinary Aeternum→Blokkats
  row gap immediately below it).


## Combined session — EAWAF/Sirenalia reclassification, v1-style edge router, edge LOD, spacing (mixed pipeline + client)

Filed as one composite block rather than split, since its six numbered items interleave `pipeline/crisis_faction.py` (Item 1, the headline finding), `pipeline/rendering_scope.py` (Item 2, survey), `pipeline/layout.py` (Items 3 survey, 4 router rewrite, 6 spacing), and `client/src/lod.ts` (Item 5) in a single reviewed session — splitting it further risked breaking the cross-references between items. See the per-item headers inside this block for which component each item touches; cross-referenced from both the crisis-faction and rendering sections above.

- **EAWAF/Sirenalia correction, v1-style edge router, edge LOD, and spacing (later session, six
  numbered items from the user, three implemented directly, two surveyed-and-stopped-on-request,
  one more implemented).**

  **Item 1 — Sirenalia under-classification, IMPLEMENTED.** A prior session's 75-flag survey
  dismissed the ENTIRE `giga_tech_eawaf_*` flag family as "a distinct Gigastructures minor-faction
  storyline," on the strength of one signal: `has_star_flag = giga_eawaf_siren_faust`. The user
  confirmed that signal is unsound (Faust is where the Sirens spawn, not exclusive to them — another
  empire can occupy the system if the Sirens fail to spawn or are disabled) and that ALL EAWAF
  content is in fact Sirenalia-related. Re-derived without it: `vendor/mods/gigastructures/common/
  technology/giga_18_eawaf.txt` holds 15 technologies total. 7 were already classified Sirenalia by
  step-1 ID fragment (`sirens_secret`/`_strike_craft`/`_autocannon`/`_artillery`/`_missile`/
  `_impactor`/`_voidbeam`, all containing "siren"). The remaining 8 split: `giga_tech_eawaf_
  psifusion` has NO `potential` block at all (checked directly — unlike every other technology in
  the same file); the other 7 gate on their own `has_country_flag = *_possible`. **Every one of
  those 7 flags is confirmed set EXCLUSIVELY inside `vendor/mods/gigastructures/events/
  giga_034_eawaf_events.txt`** (namespace `giga_eawaf`), the Sirens' own event chain — and,
  critically, that event chain's own `create_country` block (line ~1303) names the country it
  creates `"Sirenalia"`, type `giga_eawaf_sirens` (the ONLY country type `giga_eawaf_country_types.
  txt` defines — there is no second, non-Siren country this content could belong to instead). This
  is sound, direct, Faust-independent evidence: `giga_faust_weaponry_possible`
  (`giga_tech_thaumaturgic_weaponry`'s gate) is set by an event whose trigger is
  `from = { has_country_flag = giga_eawaf_country, is_country_type = primitive }` — a check against
  the Sirens' own country specifically, not a generic Faust-primitive check, and `has_star_flag` is
  never consulted anywhere in this derivation. **Zero technologies' membership rested on the Faust
  star flag alone** — the question the user specifically asked to have checked.

  Classified via the existing mechanisms, not a new one: `config/crisis_faction_flag_overrides.txt`
  gained 6 new entries (`giga_faust_weaponry_possible`, `giga_tech_eawaf_disenchanter_1/2/3/4_
  possible`, `giga_tech_eawaf_weapons_repeatable_possible`, all → Sirenalia); `config/
  crisis_faction_overrides.txt` gained 1 new technology-key entry (`giga_tech_eawaf_psifusion` →
  Sirenalia, justified as file/category/event-chain co-location — its only unlock mechanism in the
  corpus is `add_research_option` inside the same `giga_eawaf`-namespace event chain, with no
  `potential`/`has_country_flag` for the flag map to key on). **Real corpus, re-measured**: Sirenalia
  7 → **14** (all 8 EAWAF-family non-ID-matched technologies now included, since
  `giga_tech_thaumaturgic_weaponry`'s own gate flag was ALSO confirmed Siren-exclusive, making it
  the 8th — 7 ID + 6 flag-map + 1 override = 14). Standard 910 → 903. `psionics` row 34 → 28 (-6:
  disenchanter_1/2/3/4, weapons_repeatable, psifusion — all declare `category = { psionics }`);
  `particles` row 96 → 95 (-1: `giga_tech_thaumaturgic_weaponry` declares `category = { particles
  }`, not psionics — checked directly, not assumed uniform across the file). Canvas dimensions
  unaffected by this item alone (see the combined figure in the spacing bullet below — this session
  changed several things at once).

  **This is the FOURTH instance of the project's recurring defect class**: a survey dismissed an
  entire content family on a faction-identity judgement that a later, more direct read contradicted
  — a plausible wrong answer, produced with no error signal, exactly like the first three: (1)
  `pipeline.layout.is_repeatable`'s `levels < 0` predicate, which silently missed 12 finite-level
  repeatables sharing the same family; (2) `_resolve_loc_tokens`' sibling-token bug, which silently
  under-resolved every technology name with more than one token per nesting level; (3) Compound's
  "confirmed real zero," where an identity-based verdict (EHOF/Urmazin-trader content) was the
  wrong test for the actual question (reachability). This fourth instance's specific shape —
  "dismissed on a FACTION-IDENTITY judgement that named the wrong distinguishing signal" — is
  closest to (3): both times, the FIRST verdict wasn't unreasonable given the evidence looked at,
  it just looked at the wrong evidence (identity/story-label instead of reachability/provenance).
  The generalisable lesson, restated for a fourth time because it keeps recurring: a classifier
  survey's negative result ("this whole family is X, not Y") is only as strong as the SPECIFIC
  signal it was tested against — a different, more direct signal (here: where a flag is actually
  SET, and what country that event acts on) can overturn it without the corpus itself having
  changed at all.

  **Reachability-rule convergence, test-scope only, re-verified.** A prior session computed a
  general rule — a technology belongs to faction F if every DNF term of its unlock formula (its
  `prerequisites`, mandatory-AND, cross-distributed against its `potential` block's own AND/OR
  structure) requires either an F-classified `has_technology` reference or an F-mapped
  `has_country_flag` reference — and found it converged EXACTLY with the hand-built classification,
  zero new captures, zero false positives. This session added that rule as a real, running test
  (`tests/test_crisis_faction_corpus.py::test_dnf_reachability_rule_convergence` — the DNF-term
  extraction and fixed-point classifier live ONLY in that test module, deliberately NOT promoted to
  `pipeline/crisis_faction.py`) and re-ran it after this session's own Sirenalia changes: **still
  zero disagreements** between the rule and the hand-built, override-inclusive derivation, over the
  corrected 14-node Sirenalia population. The rule stays a second, independent check, not a
  candidate replacement for the reviewed, evidence-cited step-1/1.5/3 mechanism.

  **Item 2 — ACOT/AoT over-inclusion, SURVEYED, no code changed, per the user's explicit
  stop-after-report instruction.** The user reported two named examples of technologies that
  "should not" appear — a "Dark Matter Infused..." technology and a "Precursor Databank..."
  technology — as evidence of P-16 rendering-scope over-inclusion. Investigated directly:

  - `pipeline.rendering_scope.compute_rendering_scope`'s BFS, re-run against BOTH raw (unexpanded)
    and `inline_script`-EXPANDED technology blocks, produces the BYTE-IDENTICAL 7-technology
    closure either way (`tech_civil_phanon_application`, `tech_dark_matter_power_core_ae/dm/enig/
    se`, `tech_mine_dark_energy`, `tech_precursor_design`) — **the documented "reads raw blocks"
    defect canary (the `giga_tech_repeatable_*_cap` family's tier/`potential` fields) does NOT
    apply here.** This is a genuine negative finding, checked, not assumed: this module's own
    inputs (`ordered_prerequisites`, called on whichever blocks the caller supplies) simply never
    touch a field that differs between ACOT/AoT's raw and expanded forms in a way that changes
    reachability, unlike the Gigastructures `_cap` family's `tier`/`potential`.
  - Every one of the 7 closure members has a directly traceable rendered ancestor requiring it (zero
    orphans) — e.g. `tech_precursor_design` is required by `tech_dark_matter_power_core_ae`, which
    is required by `giga_tech_amb_supertensiles_acot_alpha` (a **Gigastructures** technology,
    unconditionally rendered). The BFS direction and edge-source handling are correct; no bug found.
  - **Neither of the user's two named examples is actually an ACOT/AoT closure member.** "Dark
    Matter Infused Supertensile Production" is `giga_tech_amb_supertensiles_acot_delta` — a
    **Gigastructures** technology (unconditionally rendered by design, never part of the P-16
    closure computation at all; its NAME references ACOT lore/content, which is not the same as
    being ACOT-sourced). "Precursor Databank..." is `tech_precursor_design` ("Precursor Databank
    Analysis") — which IS one of the exact 7 documented ACOT closure members, correctly present as
    the required ancestor of a Gigastructures gateway technology, exactly as P-16 specifies.
  - Real cross-check: `tech_dark_matter_power_core_dm` ("Delta-class Enigmatic Power," an ACOT
    closure member) and `giga_tech_amb_supertensiles_acot_delta` ("Dark Matter Infused Supertensile
    Production," Gigastructures) land at the IDENTICAL x-position (7776) in the current layout —
    this is the exact pairing Item 3's survey (below) independently flagged as a same-band,
    same-column prerequisite/dependent stack, and is very likely what the user's screenshot report
    for THIS item was actually showing: not an over-inclusion defect, but Item 3's ordering
    invariant violation, misread as "an unfamiliar ACOT-named technology that shouldn't be there."
  - **Conclusion: no rendering-scope bug found on the current pipeline code and vendored corpus.**
    The measured closure is exactly the documented, previously-hand-verified 7 technologies, both
    raw and expanded reads agree, and every member traces to a real rendered ancestor. If the
    deployed dataset the user reviewed showed something different, the likely explanations are (a)
    a stale build predating the current P-16 code (unlikely — `client/public/dataset/` was rebuilt
    same-session and file timestamps are recent) or, far more likely, (b) Item 3's stacking defect
    making an ACOT ancestor and its Gigastructures dependent look like an unrelated pair sharing one
    column, which reads as "this shouldn't be here" even though it is exactly where the spec says
    it should be.

  **Item 3 — same-band prerequisite ordering invariant (a technology must never render left of, or
  vertically in line with, any of its own prerequisites), SURVEYED, no code changed, per the user's
  explicit stop-after-report instruction.** Measured directly against the real 980-node/989-edge
  layout (subgrid width 4, current spacing constants):
  - **315 of 888 `prerequisite` edges (35.5%) connect two technologies in the SAME tier band.**
    (`alternative`/`potential-gate` edges were not included in this count — the user's own framing
    named "prerequisite edges" specifically, and P-2/P-8 already treat the three kinds separately
    for routing purposes.)
  - **182 of those 315 (57.8%) currently violate the invariant** (target x <= source x) — the
    `tech_dark_matter_power_core_dm` / `giga_tech_amb_supertensiles_acot_delta` pair the user
    reported is confirmed as exactly this: both land at x=7776 (band 5 = Tier 6), stacked directly
    on top of each other in different rows (`particles` vs. `field_manipulation`).
  - **No same-band prerequisite cycle exists anywhere** (checked per band via topological sort over
    the same-band-only edge subgraph; zero cycles detected) — the invariant is satisfiable
    everywhere in the current corpus, just not currently satisfied.
  - **Longest same-band prerequisite chain: 8** (in band index 5, i.e. Tier 6) — this sets the
    MINIMUM number of sub-columns that band would need under a longest-path-depth column
    assignment. Per-band minimums, current subgrid width is a uniform 4 everywhere: band 0→4, 1→3,
    2→4, 3→3, 4→5, **5→8**, 6→2, 7→3, 8→2, 9→1, Repeatables→1 (Repeatables trivially needs 1 — D-13's
    sink property means no repeatable ever sources a same-band edge).
  - **Reassigning same-band sub-columns by longest-path depth within the band, keeping every band at
    least as wide as today's uniform 4** (never shrinking a band that doesn't need it): new canvas
    width **15,806px**, up from the current (pre-Item-6-spacing) 14,160px baseline — **+11.6%**.
    Worst-case band width (band 5, needing 8 columns): **2,440px**, roughly double band 5's current
    1,200px (4-column) width. Empty (wasted) grid slots rise modestly, from 176 to 219 out of
    ~1,156-1,199 total provisioned slots — not a dramatic cost, since most bands' chain depth (1-5)
    is already close to or below the current uniform 4. (These figures were measured against the
    layout as it stood BEFORE this session's own Item 6 spacing changes — INTRA_GAP_X 40→120px
    would scale the same relative percentages onto larger absolute pixel values; not re-measured
    against the final Item-6 constants, since Item 3 stayed survey-only and re-running it against a
    moving target wasn't the ask.)
  - **The invariant is not stated anywhere in `spec/` today** (checked: no "left of" / "vertically in
    line" / sub-column ordering language exists in any spec file). Proposed wording for a future
    decision record, not yet added since this item is survey-only: *"Within a tier band, a
    technology's sub-column position must never be less than or equal to any of its same-band
    prerequisites' sub-column position — i.e., a same-band prerequisite chain must render strictly
    left-to-right, never stacked in the same column. Sub-column assignment for a (row, band) cell
    with same-band prerequisite structure uses longest-path depth within that structure, not the
    plain wrap-at-N order D-13's sub-grid otherwise uses; a cell with no internal same-band
    prerequisite edges is unaffected and keeps the existing wrap. This may require a band to exceed
    the otherwise-uniform sub-grid width."*
  - **Not fixed this session, by explicit instruction** — the canvas-width cost (+11.6% width, worse
    in band 5 specifically) needs the user's sign-off before it's paid.
  - **SUPERSEDED, later reconciliation session: this WAS implemented, as D-17
    (`spec/decisions.md`), in a session that ran concurrently with the one that wrote the
    "not fixed" line directly above.** That created a real, found-and-corrected doc/code gap — the
    code shipped the invariant while this file kept describing it as awaiting sign-off. A
    follow-up reconciliation session then found and fixed a SEPARATE bug in the shipped
    implementation (same-depth members stacked in one unbounded column instead of wrapping),
    which had inflated canvas height to 30,152px, unpredicted by this section's own cost estimate.
    See D-17 in `spec/decisions.md` for the full mechanism, the stacking bug, and the corrected
    real canvas figure (30,840 × 9,736px). `subgrid_width` (4, chosen before D-17 existed) was
    never re-evaluated against D-17's new cost — see the next bullet.

  **Item 2 (reconciliation session) — `subgrid_width` trade-off at 4/6/8/12, SURVEYED, not
  changed.** D-17's wrap-within-depth correction (above) made canvas aspect ratio a direct
  function of `subgrid_width` (currently 4, chosen before D-17 existed and never re-evaluated
  against its cost): a 37-node depth wraps into `ceil(37/4)=10` columns and reserves that width
  across the whole band. Measured over the real corpus at 4/6/8/12 — full table (canvas dims,
  aspect ratio, worst-case band width/row height, WebGL-limit check) recorded in `spec/
  decisions.md`'s D-17 entry rather than duplicated here. No value was changed; this is a survey
  for the user to pick from, per Item 2's own instruction.

  **Item 4 — replaced the gutter-channel router with a port of v1's edge geometry, IMPLEMENTED, a
  DELIBERATE trade of a measured property for legibility.** The previous router
  (`_gutter_style_waypoints`, kept as the fallback below) achieved a PROVEN, measured **zero**
  unrelated-card crossings across all 989 edges by confining every vertical run to a shared
  inter-band/row-header gutter channel. The user reviewed the rendered result and rejected it: the
  dense parallel channel traffic it produces in every gutter reads as MORE visually confusing than
  the occasional pass-under it eliminates. **This is a knowing trade, made after seeing both
  results, not a silent regression or an accident** — recorded here explicitly so it is never
  mistaken for one.

  `pipeline.layout._v1_style_waypoints` ports `github.com/Tempest113/Gigas-Tech-Tree`'s own
  `addEdge` (`js/render.js`, the `TRACE_STYLE`/circuit-trace branch) near-verbatim: leave the source
  card's right edge horizontally, turn near the target with a 45°-chamfered two-bend shape
  (`reach = clamp(24, 70, dx*0.4)`, `mid = x2 - reach`, `chamfer = min(14, |dy|/2, max(6,
  (mid-x1)/2))`), arrive at the target's left edge horizontally. **v1's own claim ("a trace never
  crosses a card") was never re-proven for v2's layout** — v1 has no faction-row backing, no
  five-row-tall header strips, and (per Item 3's own survey) real same-band and up-to-5-band
  backward `potential-gate` edges v1's simpler grid may never have had to route; the geometry was
  ported for its LOOK, not re-derived as a new safety guarantee. v1's own formula has no minimum-
  stub guarantee at all — this port adds one (`_v1_style_waypoints`'s `mid` is clamped so both the
  entry and exit stub respect `MIN_STUB`) and returns a clean failure signal, rather than a stub
  violation, whenever a same-band or otherwise-too-short/backward edge leaves no room for ANY
  placement of `mid` to satisfy both minimums. `_route_edges` falls back to the proven-safe
  `_gutter_style_waypoints` (the previous session's router, unmodified) for exactly those edges, so
  the MIN_STUB guarantee itself is never traded away — only the zero-crossings property is, and
  only for the majority of edges the v1-style shape CAN route.

  **Real measured unrelated-card-crossing count: 2,828 crossings across 606 of 989 edges** (measured
  client-side, `window.__tt.checkUnrelatedCardCrossings()`, via Liang-Barsky segment/AABB clipping
  so a non-axis-aligned chamfered segment is tested correctly, not just the old router's pure H/V
  segments) — nonzero, as expected and accepted, a large but not universal fraction (61% of edges
  clean, 39% cross at least one unrelated card at least once). This is NOT directly comparable to
  the previous router's originally-measured 2,586-crossing BASELINE (that number was for the FIRST,
  4-point H-V-H router, before the gutter-channel rewrite reached zero) — it is a fresh measurement
  against a different (v1-style) geometry, not a regression relative to the zero the immediately
  prior router achieved. **Both endpoint-containment and minimum-stub-length checks remain 100%
  clean: 0 violations across all 989 edges** (`checkEdgeEndpointsInCards`, `checkMinStubLength`) —
  the fallback correctly absorbs every case v1's own shape can't handle safely, so the ONE property
  this session did not agree to trade (every edge visibly attached to real endpoints, with a real
  visible lead-out stub) held throughout.

  **Colour, corrected against v1's real source, not against an earlier session's mistaken belief
  about it.** An earlier session brightened `EDGE_COLOR` to a light blue-cyan (`0x5cc9e6`) believing
  that was v1's own PCB-trace colour — checked against v1's actual source this session and found
  WRONG: v1's real default edge colour is its `--line` CSS custom property, `#38363c`
  (`css/*.css:11`, consumed as `ctx.strokeStyle = C.line` at `js/render.js:618`) — a dark, LOW-
  CONTRAST GREY, not blue-cyan. `client/src/tokens.ts`'s `EDGE_COLOR` is now `0x38363c`, v1's real
  value. The light blue-cyan is kept as a new, separate `HOVER_COLOR` export — it turns out to BE
  v1's own highlighted-lineage stroke colour (`C.accent`, used only while tracing a technology's
  dependency chain, `js/render.js:626`), an exactly hover/selection-shaped use — reserved, with a
  comment, for this client's still-nonexistent hover/selection state (P-08/S-3 scope, still open);
  it is deliberately NOT wired into the default edge draw call. P-08's stroke-pattern-by-kind
  encoding (dashed `potential-gate`, dotted reduced-opacity `alternative`) is unchanged by this
  colour correction.

  **Item 5 — edge LOD threshold, IMPLEMENTED.** `client/src/lod.ts`'s `EDGE_FULL_SHED_THRESHOLD`
  lowered `0.20` → **`0.166`**, so edges now reappear at **16.6%** as the status strip itself reports
  it (`Zoom: N%` = `camera.getScale() * 100`, the exact same `scale` value `edgeTierForScale`
  receives — the two can never disagree by construction) — one step further zoomed out than the
  previously observed 21.5%, per the user's explicit ask. Card LOD (`NAME_SHED_THRESHOLD`/
  `ICON_SHED_THRESHOLD`) and the other edge threshold (`EDGE_PARTIAL_SHED_THRESHOLD`, 35%) are
  unchanged.

  **Item 6 — horizontal card spacing (a fourth pass at the same recurring complaint) plus a real
  row-separation rendering bug found and fixed, IMPLEMENTED.** `INTRA_GAP_X` raised **40px → 120px**
  (3x, well past the previous three incremental raises of 16→24→40 — the user explicitly flagged
  each prior increase as too small). `INTRA_GAP_Y` (24px) unchanged, per the user's own instruction.

  **A real bug, not just a tuning question, explains why `ROW_GUTTER` (48px) read as "no visible
  separation" between same-area rows and between every faction row**: `client/src/main.ts`'s row-
  panel draw call (`drawRowPanel`) used each row's FULL reserved `rowHeight` — which, mirroring
  `pipeline/layout.py`'s own `row_height = ROW_HEADER_HEIGHT + ROW_GUTTER + cards` formula, already
  INCLUDES that row's own trailing `ROW_GUTTER` — as the panel's drawn height. The panel therefore
  bled into the very gutter meant to separate it from the next row, so one row's panel bottom edge
  touched the next row's panel top edge directly on screen, even though `ROW_GUTTER` was a real,
  correctly-computed, nonzero number the whole time. **`AREA_GROUP_GUTTER` was never actually too
  large in absolute terms — it only LOOKED disproportionate next to a `ROW_GUTTER` that was
  invisible.** Fixed at the render call site: both the row panel and its faction pattern accent now
  draw at `rowHeight - ROW_GUTTER`, leaving that reserved space genuinely empty. With `ROW_GUTTER`
  now actually visible, `AREA_GROUP_GUTTER` (previously 96px, equal to the unrelated
  `INTER_BAND_GUTTER` and nearly 2x a suddenly-visible 48px `ROW_GUTTER`) was reduced to **64px** —
  still clearly larger than `ROW_GUTTER`, preserving three distinct, ordered separation levels (card
  gap < row gap < group gap), but no longer disproportionate. Both constants mirrored between
  `pipeline/layout.py` (the single named place they live) and `client/src/main.ts`, per the
  project's existing convention.

  **Real measured canvas: 16,800 × 12,520px** (was 14,160 × 12,616px before this session's Item 1 +
  Item 6 changes combined — width grows from `INTRA_GAP_X`'s tripling; height moves DOWN slightly
  despite Item 1's Sirenalia growth, because `AREA_GROUP_GUTTER`'s reduction at 3 group boundaries
  (-96px total) outweighs the net effect of Item 1's row-membership changes). Densest `(row, band)`
  cell unaffected: still `voidcraft` × T5 = 47 nodes — pure spacing and faction-membership changes,
  no sub-grid membership change. Real final per-row counts, over the 980-node rendered set:
  `computing` 83, `field_manipulation` 82, `particles` 95, `archaeostudies` 24, `biology` 130,
  `military_theory` 43, `new_worlds` 49, `psionics` 28, `statecraft` 82, `industry` 70, `materials`
  49, `propulsion` 45, `voidcraft` 123, `Aeternum` 3, `Blokkats` 42, `Compound` 15, `Sirenalia` 14,
  `Katzenartig Imperium` 3 (sums to 980). Per-faction totals, over the same set: Standard 903,
  Blokkats 42, Sirenalia 14, Compound 15, Aeternum 3, Katzenartig Imperium 3.

  **Verified**: full pytest (1,382 passed, up from 1,378 — the new DNF-reachability convergence
  test), `tsc --noEmit`, `vite build` all clean. Real dataset rebuilt (`tools/build_dataset.py`,
  980 technologies/989 edges) and served via `vite preview`; a real headless-Chromium run
  (`playwright-core`, transient, not added to `package.json`): zero console errors, zero failed
  requests; `checkEdgeEndpointsInCards`/`checkMinStubLength` both 0 violations across all 989 edges
  (proven CAPABLE of failing first, via a standalone Node reproduction of the same Liang-Barsky/
  stub-length math fed deliberately-broken synthetic inputs, before trusting the real clean pass —
  a segment run straight through a rect and a 3px stub both correctly flagged); `checkNameBounds`/
  `checkChipLabelOverlap` both still 0 violations (unaffected by this session's changes, re-checked
  anyway); new `checkUnrelatedCardCrossings` reports 2,828/606 as above. Five screenshots reviewed:
  fit-to-viewport (all 18 rows now show real, visibly separated tinted panels — including the 13
  category rows, which previously read as empty space next to the 5 already-backed faction rows;
  this is the direct, visible confirmation of the `ROW_GUTTER` bleed fix); a multi-elbow region
  (Autocannons → Flak Cannons/Ripper Cannons and neighbours) showing the v1-style chamfered
  diagonal corners clearly, distinct from the previous router's sharp H-V-H right angles; the
  Improved Deflectors / Storm Manipulation / Basic Cloaking Field neighbourhood at 100% — the
  previously-reported false-connection pass-under does NOT reappear in this specific,
  user-flagged case, though the 2,828-crossing figure above confirms it is not eliminated
  everywhere; the Sirenalia row at 100%, now showing all 14 members including the 7 newly-
  reclassified EAWAF technologies (localised names confirm real content: "Semithaumaturgic
  Crystalline Weaponry," "Early Sirens Countermeasures," "Disenchanter Tuning," "Crystalline
  Artillery/Autocannon," "Harass Decoys," "Grand Void Beam"); and one frame spanning both a
  within-area row boundary (`field_manipulation`→`particles`, both physics) and an area-group
  boundary (`particles`→`archaeostudies`, physics→society) together — the group boundary's larger
  gap and the physics-area rows' own blue tinted panels are both clearly visible in the same frame,
  confirming the three-level separation (card < row < group) the user asked for.

  **Not done this session** (both by explicit user instruction, "survey then stop"): Item 2's
  ACOT/AoT over-inclusion concern was investigated and found to have NO reproducible bug in the
  current pipeline/corpus — likely explained by Item 3's stacking defect instead (see above). Item
  3's same-band prerequisite ordering invariant was IMPLEMENTED in a concurrently-running session
  as D-17 (`spec/decisions.md`) — see the addendum on Item 3's own writeup above for the
  implement-then-reconcile history, including the unbounded-stacking bug a follow-up session found
  and fixed in that implementation.


## Reconciliation session 2 — D-18 depth-1 ACOT/AoT closure, parallel-geometry rule, badges slice

Continuation of the reconciliation session above, same session's later half. Full detail lives in
`spec/decisions.md`'s D-18 entry, CLAUDE.md's Rules section (the parallel-geometry rule), and
`spec/S-03-tier-differentiation.md`; this entry is a pointer plus the real numbers, not a
restatement.

**Ten untracked files committed.** `client/src/{tokens,camera,lod}.ts`, two config override
tables, their loaders, their tests, and this file (`docs/BUILD-LOG.md` itself) had accumulated
across many sessions with no `.gitignore` pattern excluding them — simply never `git add`ed.
`tests/test_repo_hygiene.py` now guards against a recurrence: a local-only pytest check (CI can't
see untracked files by construction) that fails if anything under `client/src/` or `pipeline/` is
untracked.

**D-18: ACOT/AoT rendering scope is depth-1, not a full transitive closure.** Adopted after the
user reviewed the exact 3-link accepted cost (all ACOT→ACOT, including their own named case:
`tech_dark_matter_power_core_ae` → `tech_precursor_design`) and rejected a considered stub/ghost-
node middle option as disproportionate. `pipeline.rendering_scope.compute_rendering_scope` is now
a single pass, no recursion; `compute_off_tree_prerequisites` (new) computes the accepted-cost set,
pinned by a corpus test. Real effect: 980 → 977 rendered technologies, 989 → 984 edges. Canvas
dimensions and densest cell UNCHANGED (30,840 × 9,736px, `voidcraft`×T5=47). Every corpus test
across the suite re-verified against the new 977/984 figures — full cascade in commit history, not
restated per-file here.

**Parallel-geometry rule recorded** (CLAUDE.md's Rules): the pipeline owns all geometry, the
renderer derives from real emitted positions, never a parallel formula. Audited `client/src/
main.ts` for other instances — the severe form (multi-step derived formulas) is now fully
eliminated; what remains is a set of mirrored scalar constants (`CARD_WIDTH`, gutters,
`SUBGRID_WIDTH`, `AREA_ORDER`, etc.) with lower blast radius, flagged as a scoped follow-up (adding
card dimensions to the schema) rather than fixed this session.

**Item 4 loose ends**: 6 real name-text collisions found (`checkNameRendering`'s
`duplicatePairs`) — 5 are genuinely identical real names from the mod itself (hive/wilderness
variant pairs, an ACOT/base duplicate), 1 (`tech_dark_matter_deflector`/`tech_dark_matter_
propulsion`, "Dark Matter Dimensional Deflector"/"...Thruster") is a genuine truncation-caused
collision — two different full names sharing a truncated 2-line prefix. `subgrid_width` left at 4,
untouched, per instruction.

**Badges slice, the main body of work.** Cards previously showed icon/name/cost/tier badge only.
Added: rare badge (gold "★"), dangerous badge (red "!"), mod-requirement badge(s) (`ACOT`/`AoT`
text chips), repeat-count badge (`×N`/`∞`, replacing the tier badge for repeatable nodes), gate
icon + label (wired to the schema, renders nothing today since `gates` is always `[]` — P-3's
pipeline-side classification isn't built, a real pipeline gap flagged honestly, not silently
shipped as if complete). Rare/dangerous also drive the card's OUTLINE per S-1 (dangerous outranks
rare; both → a 45°-split outline, dangerous red top-left, via a masked duplicate stroke).

**Layout**: a new fixed-width (34px) vertical badge gutter along the card's right edge, sized
against the real corpus's worst case (rare+dangerous+1 mod-requirement = 4 stacked slots
including tier/repeat, confirmed directly — never mod+repeatable, max 1 mod entry). Name text
width narrowed to make room (`NAME_MAX_WIDTH_PX`: 202px → 160px) — a real, reported trade-off:
more names now need the ellipsis than before slotting every indicator into the fixed 270×92 card.

**LOD**: `lod.ts`'s previous 3-tier simplification (documented at the time as existing "only
because badges didn't exist yet") is replaced with S-03's real 7-stage table verbatim. Real
correction along the way: the old simplification shed the icon/name at <10% ("nothing left to
shed between 10% and 5%" when it was written) — under the real table, icon/name/cost are the
"everything remaining" that only sheds at <5% ("Coloured block"), one stage later; the dangerous
badge is what now occupies the <10%–<5% gap.

**Real per-indicator counts, over the 977-node D-18 corpus** (`window.__tt.checkIndicatorCounts`,
matching the dataset's own real fields exactly): rare 411, dangerous 64, mod-requirement 4, gated
0, repeatable 88 (all in the terminal Repeatables band, all rendering a repeat-count badge, none a
tier badge). `checkIndicatorBounds`: 0 violations across 1,456 checked indicator placements — the
detector was proven capable of failing (fed a synthetic 500px-displaced badge, confirmed the same
math flags it) before trusting the clean real-corpus pass.

**Verified**: full pytest (1,387 passed), `tsc --noEmit`, `vite build` all clean. Real dataset
rebuilt against D-18; a real headless-Chromium run: zero console errors, zero failed requests,
`checkNameBounds`/`checkIndicatorBounds`/`checkEdgeEndpointsInCards`/`checkMinStubLength`/
`checkTierBadgeMatchesBand` all 0 violations. Six screenshots reviewed: a card carrying all four
simultaneous indicators (rare+dangerous+mod-req+tier, the same D-17 in-line case node, split
outline clearly visible), a dangerous-only card (solid red outline, distinct from a neighbouring
rare-only gold-outlined card), and one frame at each of five S-03 threshold bands showing
indicators dropping in the specified order (confirmed directly against the status line's own
reported LOD tier, not just eyeballed).

**Not done this session**: hover/click/selection, popups, search, empire-profile switching, real
gate data (P-3's pipeline classification pass), a traced Blokkats SVG, ΔE2000/WCAG mechanical
colour checks, the `subgrid_width` decision (left at 4, survey recorded in D-17 for the user to
choose from). See CLAUDE.md's Open items and HANDOFF.md's Next prompt for what's next.

## Reconciliation session 3 — hover, selection, detail popup, plus three corrections

**Item 1 — rare-count sanity check: 411/977 (42%) confirmed real, not a bug.** Verified the
reader uses inline_script-EXPANDED blocks (0 raw-vs-expanded mismatches — `is_rare` is never
templated, unlike the `giga_tech_repeatable_*_cap` family's tier/potential fields), and
spot-checked 3 Gigastructures entries directly against raw source (`is_rare = yes` literally
present). Per-source breakdown: Vanilla 223/673 (33%), Gigastructures 184/300 (61%), ACOT 3/3,
AoT 1/1. Vanilla's raw grep count (232 occurrences of `is_rare = yes` across all vanilla files)
independently corroborates the 223 rendered figure. Recorded here so it is never re-queried.

**Item 2 — the truncation collision fixed, and a real pre-existing under-count corrected along
the way.** `wrapAndClampName` (`client/src/main.ts`) now middle-ellipsizes on the final line,
preserving the name's true last word (`headOfLine + "…" + lastWord`) instead of plain
tail-truncation — mod naming conventions commonly vary only the final word of an otherwise-shared
name, and tail truncation is exactly what erased it. **A/B-measured directly, not assumed**: with
plain tail-ellipsis (temporarily reverted for the comparison), the REAL collision count on the
current corpus is **11 groups**, not the 6 a prior session reported — that 6 was apparently
measured against a stale or differently-configured build. The middle-ellipsis fix resolves all 6
truncation-CAUSED groups (Blokkilian Equations ×3, Long-Term Blokkat Scrap ×2, Matrioshka Brain
×2, Strategic Coordination ×2, Dark Matter Dimensional ×3, Doctrine Interstellar ×2), leaving
exactly the 5 genuine same-name-in-the-mod pairs untouched (Mass Neutronium Extraction, Curator
Archaeology Lab, Clustered Synapses, Confluence of Thought, Machine Template System) — zero
truncation-caused collisions remain, verified directly. Ellipsis count itself is unchanged at 253
either way (the fix changes WHAT a truncated name shows, never WHETHER a name needs truncation).

**Item 3 — the D-18 off-tree-prerequisite gap closed.** `pipeline.dataset_emit.build_detail_payload`
resolves each affected technology's off-tree prerequisite(s) to a localised name
(`offTreePrerequisiteNames`, new detail-payload field, soft-fallback to the raw key rather than a
hard build failure, since this describes a technology OTHER than the one being built). Real
values: `tech_dark_matter_power_core_ae` → `["Precursor Databank Analysis"]`,
`tech_dark_matter_power_core_dm` → `["Enhanced Zero Point Reactor", "Dark Energy Drawing"]`, the
other 975 → `[]`. Popup-only, no card badge (per instruction — 3 nodes doesn't justify one).

**Item 4 — the main slice: hover, selection, ancestry/dependent highlighting, detail popup.**
- Hit-testing: a plain O(977) linear scan over the real emitted `nodePositions` on each
  `pointermove`/`pointerdown` DOM event — never a parallel geometry formula, never per-frame.
  Measured at <1ms for 200 calls; the hover/selection graphics redraw only happens when the
  resolved node index actually changes.
- Hover: highlights the card outline plus its directly-incident edges in `HOVER_COLOR` (finally
  consumed, reserved since the edge-router session). Gated off below `CONTENT_SHED_THRESHOLD`
  (<5%, the flat-coloured-block LOD stage).
- Selection: click-to-select/click-empty-to-deselect, persists across pan/zoom. Highlights the
  selected card (`SELECTED_COLOR`, new token), its full ancestry (`ANCESTRY_COLOR`, new,
  cool-hued) and full dependents (`DEPENDENT_COLOR`, new, warm-hued) — a BFS over ALL THREE P-14
  edge kinds (prerequisite/alternative/potential-gate), explicitly NOT P-12.9's research-path
  algorithm (structural/profile-invariant vs. per-profile cheapest-OR-branch; stated in code
  comments so a later session doesn't conflate the two). Verified against a known OR group
  (`giga_tech_asteroid_artillery`'s alternative edge, members `tech_battleships`/`tech_stingers`):
  both members present in the ancestor set, confirming alternative branches are never flattened.
- Focus-pan: selecting a node pans (never zooms) so it centres in the viewport area LEFT of the
  fixed-width detail-popup panel — how "the popup must not obscure the selected card" holds
  structurally, not by luck.
- Detail popup: a DOM overlay (CLAUDE.md's Stack), right-side fixed panel. Shows untruncated name,
  row/tier/area/faction, cost, mod-requirement chips, three-state availability (never boolean —
  shows the unconditional state when all 12 `availabilityMatrix` slots agree, explicitly says
  "varies by empire type... not built this session" when they don't, never silently picks a
  profile), lazily-fetched description (`fetchDetailPayload`, new `dataset.ts` helper, small
  in-memory cache), direct prerequisites/dependents by localised name, and the Item-3 off-tree note
  where applicable.
- Long-span backward `potential-gate` edges (previously "unlocatable by eye" per HANDOFF.md):
  **selection resolves this.** Selecting `tech_cosmogenesis_escort` ("Riddle Escort") and zooming
  to 15% shows its highlighted dependent trace to `tech_missiles_1` clearly followable across the
  full 5-band span (confirmed by screenshot) — the stub-connector treatment recommended earlier is
  no longer necessary now that selection highlighting exists.

**A real bug found via screenshot review (again the recurring "screenshots catch what tests
couldn't" pattern): Stellaris's own loc format uses a literal two-character `\n` escape inside a
description string for a line break** (confirmed against `tech_dark_matter_power_core_ae_desc`'s
raw YAML — the literal backslash-n bytes, not a real newline). Invisible until now because
description was never actually DISPLAYED anywhere before this session's popup. `strip_markup`
never touched it (`§`/`£` markup only). Fixed in `pipeline.dataset_emit.build_detail_payload`
(scoped to `description` only). Real corpus: 25 affected before, 0 after.

**Frame-time note, sandbox caveat repeated because it matters here specifically**: measured
median ~288-300ms in this sandbox's software-WebGL (SwiftShader) fallback, both WITH and WITHOUT
hover active (pan-only baseline measured separately at ~299ms) — confirming hover adds negligible
marginal cost; the absolute figure is this sandbox's own rendering cost for the full scene, not a
hover regression, and is not comparable to the previously-reported 6.1ms/12.1ms real-hardware
figure (measured on different hardware in a different session, a gap this project has documented
multiple times before).

**Verified**: full pytest (1,389 passed), `tsc --noEmit`, `vite build` all clean throughout. A
real headless-Chromium run against the rebuilt corpus: zero console errors, zero failed requests;
`checkNameBounds`/`checkIndicatorBounds`/`checkEdgeEndpointsInCards`/`checkMinStubLength`/
`checkTierBadgeMatchesBand` all clean; hit-testing verified correct at 3 zoom levels × 3 named
technologies + empty-space checks, all matched. Six screenshots reviewed: a hovered card with
highlighted edges, a selected node with ancestry (violet) and dependents (amber) visibly
distinguished plus the popup listing both by name (including OR-group members), the popup on a
crisis-faction technology, the popup on an off-tree-prerequisite card (showing the "Also
requires" note and real multi-paragraph description), and the long-span edge trace at two zoom
levels.

**Not done this session** (explicitly out of scope): research path (P-12.9), search UI,
empire-profile switching, gate classification (P-3, still `gates: []` everywhere), faction pattern
refinement, `subgrid_width` change.

## Reconciliation session 4 — subgrid_width=6, empire-profile switching, search

**Item 1 — `subgrid_width` set to 6, the user's pick from D-17's 4/6/8/12 survey.**
`pipeline.layout.DEFAULT_SUBGRID_WIDTH` and `client/src/main.ts`'s mirrored `SUBGRID_WIDTH` both
changed. Real re-measured figures over the 977-node/984-edge D-18 corpus, matching the survey's
own projection exactly: canvas **29,670 × 13,448px** (2.21:1 aspect, down from 30,840 × 9,736px
at 3.17:1), worst band width **5,730px** (down from 8,460px), worst row height 672px (`industry`
row). Densest cell and row population unaffected (`voidcraft`×T5=47 — `subgrid_width` never
changes membership, only geometry). Every pinned test assertion updated
(`tests/test_layout_corpus.py`); synthetic mechanism tests (`tests/test_layout.py`) pass
`subgrid_width=4` explicitly and are unaffected, deliberately.

**Item 2 — empire-profile switching, fully built.** `client/src/empireProfile.ts` (new) mirrors
`pipeline/dataset_schema/empire_profile.py`'s canonical `EmpireProfileIndex` formula exactly
(round-trip verified across all 12 profiles). A three-axis selector (never a flat 12-item list)
drives `updateAvailabilityDisplay()`, which reads `tech.availabilityMatrix[index]` DIRECTLY from
the base dataset for every node — no client-side recomputation, verified by an independent
cross-check against the emitted matrix across all 12 profiles × 977 nodes (11,724 checks, 0
mismatches). Visual treatment: a neutral (non-hued) dim overlay at a per-state alpha, plus a
distinct glyph badge (✕ locked / ? uncertain / ⚙ config-gated) — colour is never the sole carrier,
per S-1's own discipline extended to a fourth classification. The detail popup shows the
SELECTED profile's real state (from the base dataset) and lazily fetches that profile's overlay
for the structure-derived/trigger-derived reason text (P-13) — never fabricated, never silently
defaulting to one profile.

Real per-profile availability counts, all 12, cross-validated against D-10's previously-recorded
figures: unconditional uncertainty (209, profile-invariant) plus the worst profile's
profile-dependent uncertain count (33, i.e. 3.37% of 977) sum to exactly 242 — the worst raw
"uncertain" count measured directly (regular/biological/no). D-10's regime is UNCHANGED by this
session: 3.37% sits above the 3% warn threshold, comfortably under the 10% hard ceiling, matching
the figure already on record (D-18 didn't move it — none of the 3 dropped technologies was ever
profile-dependent).

**Item 3 — search, fully built, consuming the emitted index directly.** The index tokenises
name + technology key + description (verified directly from `build_search_index`'s real
implementation — category/faction are NOT included, despite the schema's own description
mentioning them as a possibility; this is a real, reported finding, not assumed from the schema
text alone). Prefix-match search (P-6's optional fuzzy matching not implemented), ranked
exact-name > name-prefix > token-prefix. Matches highlight IN PLACE (`SEARCH_MATCH_COLOR`, new
token) — never a filter, so prerequisite-chain reading is never broken. Verified against known
queries including a resolved-loc-token name ("Civilian Arkships") and an ellipsis-truncated one
("Dark Matter Deflector") — both found correctly despite their card-display truncation, since
search operates on the full untruncated name via the index, never the rendered/wrapped text.
Clicking a result reuses the existing `setSelected`/`focusOnNode` path, no parallel selection
mechanism.

**Verified**: full pytest (1,389 passed — including `tests/test_repo_hygiene.py` catching a real
gap: `client/src/empireProfile.ts` was created but never `git add`ed, exactly the failure mode
that test exists to guard against), `tsc --noEmit`, `vite build` all clean. A real headless-
Chromium run: zero console errors, zero failed requests; all pre-existing invariant checks
(name/indicator bounds, edge containment, min-stub, tier-badge/band agreement) still 0 violations
after the `subgrid_width` change. Six screenshots reviewed: two visibly different profiles on the
same region (cards visibly dim/undim and change badge glyph between Regular/Mechanical/Non-nomadic
and Hive Mind/Biological/Nomadic), one card in each of the four real states (available, locked,
uncertain, config-gated), the popup showing a real locked reason ("locked — Nomadic empires" on a
technology gated to non-nomadic empires), and a search result selected with the camera panned to
centre it.

**Not done this session** (explicitly out of scope): research path (P-12.9), gate classification
(P-3, still `gates: []` everywhere), faction pattern refinement.

## Reconciliation session 5 — repo-hygiene guard extension, EmpireProfileIndex parallel-formula fix, gate classification (P-3)

Two small corrections requested first, then a full survey-then-implement pass on gate
classification (P-3), the last unbuilt pipeline piece.

**Correction (a) — the repo-hygiene guard couldn't catch its own absence.**
`tests/test_repo_hygiene.py` (built a session earlier specifically to catch untracked
load-bearing files) was itself untracked, and its guarded-tree list (`client/src/`, `pipeline/`)
didn't include `tests/` — the exact tree it lives in. Tracked and committed; guard extended to
`tests/`, `spec/`, `config/`, `docs/` (every tree where CLAUDE.md's Rules say an untracked file
is never legitimately derived/disposable). Nothing else turned up untracked in any of those trees
at the time of the fix — confirmed by running the extended check, not assumed.

**Correction (b) — the client's `EmpireProfileIndex` was a parallel formula, the exact defect
class CLAUDE.md's "pipeline owns all geometry" rule forbids (generalised here from geometry to an
indexing scheme).** `client/src/empireProfile.ts` used to hand-restate
`pipeline.dataset_schema.empire_profile`'s stride/axis-order formula — agreeing today, free to
drift silently later, the same shape that caused D-17's row-geometry desync. Fixed the same way:
the base dataset now emits `empireProfileAxes` (new field, `schema/common.schema.json`'s new
`EmpireProfileAxes` def — axis order, each axis's values, derived stride, `totalProfileCount`;
built by `pipeline.dataset_schema.empire_profile.build_empire_profile_axes`, itself derived from
the module's existing `AXES`/`_STRIDES`, never hand-restated). `client/src/empireProfile.ts` was
rewritten to derive `empireProfileIndex`/`allProfiles`/`axisValues` purely from that emitted
data — no hardcoded stride or axis-value list survives client-side; a caller that hasn't called
`initEmpireProfileAxes` yet gets a loud error, never a stale hardcoded answer. Verified: the
client-derived index round-trips correctly across all 12 real profiles (0 mismatches, headless
run against the real build), `tsc --noEmit`/`vite build` clean, detector-fails-first proven by
temporarily emitting a stub `empireProfileAxes` from the pipeline and confirming JSON Schema
validation catches the malformed shape immediately (before reverting). Two new pytest tests pin
this: the real build's emitted `empireProfileAxes` equals what `build_empire_profile_axes()`
independently computes, and `totalProfileCount` agrees with every technology's
`availabilityMatrix` width (12, today).

**Item 1 (this session) — the spec's wrong example, found and corrected before implementation.**
`spec/P-03-gates.md` cited "the Tetradimensional Engineering technology" as an example of one
technology gating another. Checked directly against the real corpus (this project's own
evidence-before-design rule) and found **false**: `giga_tech_tetradimensional_engineering` gates
several *ascension perks* (`common/ascension_perks/giga_ascension_perks.txt`'s
`custom_tooltip`/`has_technology` pairs) — out of P-3's scope entirely — and names no technology
of its own in any rendered technology's `potential` block. Corrected in place to a real example
(`giga_tech_amb_supertensiles_acot_alpha` → `tech_dark_matter_power_core_ae`), with the original
example's refutation recorded rather than silently swapped out, so a future session finding the
old example in git history learns it was checked and refuted.

**Item 2 — gate classification, built.** `pipeline/gate_patterns.py` is the new registry module:
four registered trigger patterns (`has_ascension_perk`, `has_technology`, `has_gigastructural_
constructs`, `has_galactic_wonders`), each walked with the same `potential`-only, scoped
AND/OR/NOT/NOR descent discipline `pipeline.edges`/`pipeline.availability` already use (reused
directly, not re-derived — the `count_country` false-positive `pipeline.edges`' own docstring
describes is exactly the bug class this discipline guards against here too). Real corpus counts,
confirmed by direct inspection before implementation began: `has_ascension_perk` 22 technologies/
22 instances, `has_technology` 22 technologies/25 instances (3 technologies name two targets
each), `has_gigastructural_constructs` 9/9, `has_galactic_wonders` 14/14 — 70 gate instances
total over 60 technologies, 10 of which carry more than one instance (7 crossing two distinct
mechanism types — 6 `tech_lathe_*` + `giga_tech_the_vat` — plus 3 more, found only once gates
were actually built rather than by the coarser per-mechanism-type survey grouping, carrying two
`has_technology` targets each: `giga_tech_disco_moon`, `tech_qnm_disruptors`,
`tech_sm_autocannons`).

**The two Gigastructures scripted-trigger wrappers were confirmed by direct inspection, not
assumed from their names**: `has_gigastructural_constructs` (`giga_scripted_triggers.txt`) is a
1:1 wrapper for `ap_gigastructural_constructs`; `has_galactic_wonders` (`zzz_overwrites.txt`) is
an `OR` of the base `ap_galactic_wonders` perk plus three DLC-ownership-variant perk IDs
unlocking the exact same thing (`ap_galactic_wonders_utopia`/`_megacorp`/
`_utopia_and_megacorp` — none of which has its own vendored icon or loc entry, confirmed, so the
base id is the only one that could be displayed anyway). Both wrappers carry an `is_ai = yes`
AI-only override branch neither this registry nor `pipeline.availability` models — recorded in
the module docstring so a future session doesn't mistake it for an oversight.

**Curation decision (the user's, recorded verbatim in reasoning): mechanism-level, not
occurrence-level.** Once a pattern is registered, every real occurrence badges — no further
per-technology editorial filter. Reasoning: 70 instances over 60 technologies is small enough
that badging all of them is informative rather than noisy, and a hand-curated per-occurrence
subset would be one more hand-maintained surface like the crisis-faction/flag/name override
files, for no evidenced benefit at this size. The registry's job is RESOLUTION (icon/label
lookup, the two wrapper→perk mappings), not SELECTION. Written into `spec/P-03-gates.md` itself,
not just this log.

**Zero interaction with availability evaluation, asserted rather than assumed.** All four
registered keys were already in `pipeline.availability.EXCLUDED_KEYS` (an identity-element state
predating this module) — gate classification adds only display metadata.
`tests/test_gate_patterns.py::test_gate_leaf_keys_matches_availabilitys_excluded_keys_exactly`
pins the two lists staying in exact sync (with its own detector-fails-first proof). D-10's
worst-case profile-dependent uncertainty is confirmed unchanged: still 33/977 (3.37%), asserted
against the real build in `tests/test_dataset_emit.py::
test_gate_classification_leaves_d10_uncertainty_unchanged` — not assumed, computed as
`max(per-profile raw uncertain count) − unconditional-uncertain count` per D-10's own two-metric
split. Edge counts are also confirmed unchanged: 984 total (883 prerequisite + 76 alternative +
25 potential-gate) — `tests/test_dataset_emit.py::
test_base_dataset_gates_match_the_gate_classification_survey` additionally asserts every
technology-kind gate is exactly one of the 25 `potential-gate` edges, one to one, no more no
fewer.

**Ordering (D-3) implemented and tested**: ascension-perk gates sort before technology gates;
declaration order preserved within a kind (Python's stable sort). The 6 `tech_lathe_*`
technologies (the only real corpus case with one of each kind) all confirmed to put the perk
gate first.

**Icon and label resolution**: ascension-perk gate icons reuse `_icon_ref_map` (previously
technology-only in name, generic in implementation) against the already-built, deliberately
unfiltered perk atlas (`pipeline/icons/build.py`'s own docstring anticipated this — "ascension-
perk atlas building stays fully unfiltered until gate detection exists to filter it correctly,"
and confirmed here: filtering was never needed, the unfiltered perk atlas was already small,
~262KB, well inside the 6MB tripwire). Technology-gate icons reuse the target's own already-
resolved technology icon. Labels are `"Needs {name}"`, the perk/technology's own already-resolved
localised display name — technology-gate labels reuse the exact same name-resolution pass now
factored out (`_resolve_technology_name`, precomputed once for all 977 rendered technologies) so
a gate's target name can never drift from that technology's own displayed name. One real
edge case found only by running the reduced-corpus test (D-14's ACOT/AoT-optional build mode):
`giga_tech_amb_supertensiles_acot_alpha` gates on the ACOT-only `tech_dark_matter_power_core_ae`,
which isn't rendered at all when ACOT is absent from the build — not a D-18 off-tree case, a
whole-source-absent case. Fixed by falling back to the same best-effort loc_table lookup
`_resolve_off_tree_prerequisite_name` already uses for D-18's off-tree names, never a hard
failure — D-14 already established "ACOT/AoT absent is a supported build mode, not an error."

**Client-side: only the popup needed a real change.** The card renderer (badges slice, an earlier
session) was already fully wired against `tech.gates[0]` and rendered nothing only for lack of
real data — confirmed by rebuilding the real dataset and checking `gated: 60` (rendered) exactly
matches `datasetGatedCount: 60` (emitted), 0 indicator-bounds violations across 1,576 checks. The
popup, however, had no gate section at all before this session — added one (`client/index.html`'s
new `.gate-row`/`.gate-icon` CSS, `client/src/main.ts`'s popup template), rendering every gate in
the technology's ordered list (not just the primary), each with its real cropped atlas icon (CSS
`background-position` against the same already-fetched atlas webp the PixiJS card icons use — no
second icon fetch) and localised label. Screenshotted and confirmed correct: `Synaptic Cogitator`
shows both "Needs Cosmogenesis" and "Needs Scalable Reservoir Computing" in the right order.
Secondary gate badges on the CARD itself (spec's "where space permits" language, for the 10/977
technologies with more than one gate instance) are explicitly NOT built — flagged in the code
comment and here, since only the primary gate has ever been asked for.

**Verified**: full pytest (1,409 passed, up from 1,389 — 20 new tests: 15 in
`tests/test_gate_patterns.py`, 5 corpus-level additions to `tests/test_dataset_emit.py`),
`tsc --noEmit`/`vite build` clean, headless-Chromium run zero console errors/zero failed
requests, all pre-existing invariant checks (name bounds, indicator bounds, edge-endpoints-in-
cards, D-17) still 0 violations after rebuilding with real gate data. Every new detector proven
capable of failing before being trusted: the `GATE_LEAF_KEYS == EXCLUDED_KEYS` test has its own
deliberately-diverged-set companion test; the `empireProfileAxes` equality test was proven by
temporarily emitting a broken stub from the pipeline and watching schema validation reject it.
Five screenshots reviewed: a card with an ascension-perk gate badge (`giga_tech_birch_world_1` →
"Needs Vast Expanses"), a card with a technology gate badge (`giga_tech_amb_supertensiles_
acot_alpha` → "Needs Alpha Project..."), the two-mechanism card (`giga_tech_the_vat`, primary
gate only per the card-vs-popup distinction above), the popup showing both of
`tech_lathe_cogitator`'s gates in the correct D-3 order, and a card at 35% zoom (between the
0.20 icon-shed and 0.60 label-shed S-03 thresholds) showing the gate icon with its label
correctly shed.

**Not done this session** (explicitly out of scope, or flagged rather than silently built):
research path (P-12.9, now the next open item — see HANDOFF.md's next prompt), secondary gate
badges on the card for a multi-gate technology (popup already shows all gates; only the card is
primary-only), faction pattern refinement.

## Screenshot-review session — card text/gate-label bugs, profile selector overflow, row-padding centring, LOD verification, gate-count/curation-wording reconciliation, swap/prerequisite-display and research-path surveys

Six items from real screenshot review, then two corrections to the previous session's own
writeup, then two surveys (stop-before-implementing on both).

**Item 1a — name truncation defaults back to plain tail-ellipsis.** The middle-ellipsis fix from
an earlier session (built to stop `tech_dark_matter_deflector`/`tech_dark_matter_propulsion` from
both truncating to the identical "Dark Matter\nDimensional…") had been applied unconditionally to
EVERY truncated name, not just the ones that actually needed it — destroying the informative
middle of names like "Runic Matter Manipulation Techniques" (rendered "Runic Matter
Ma…Techniques") for zero benefit. Fixed with a two-pass approach
(`resolveNameTruncations`, `client/src/main.ts`): every name wraps in TAIL mode first; names
whose tail-mode output COLLIDES with another name's (grouped by output string) switch to MIDDLE
mode; the switch is verified, not assumed. Real corpus result: 253 names truncated, only 18 use
middle-ellipsis (the minimal set), 5 duplicate-visible-text groups remain — all 5 confirmed to be
technologies with byte-IDENTICAL raw names (`tech_archeology_lab`/`_ancrel`, `tech_hive_cluster`/
`tech_wilderness_cluster`, `tech_hive_confluence`/`tech_wilderness_confluence`, and 2 of the 18
middle-ellipsis names — "Mass Neutronium Extraction" and "Machine Template System," each shared
by two real technologies) — genuinely unresolvable by any truncation strategy since the SOURCE
strings are identical, not a truncation artifact. This exact "5 genuine, 0 truncation-caused"
figure matches what an earlier session had already established, confirming the fix didn't
regress it.

**Item 1b — gate label font-measurement bug and name-overlap collision, both real, found from one
screenshot** (`giga_tech_amb_supertensiles_acot_phanon`, "Needs Civil Phanon Engineering"
rendering as a stray "Ne…Engineering" fragment overlapping the card name). Two distinct causes:
(1) `wrapAndClampName`'s shared `measureCtx` was left at the 20px NAME font by the main per-card
loop and never reset before measuring the 11px gate label, so every width came back ~1.8x too
large and the label over-truncated severely. Fixed by making `fontCss` a required-in-spirit
parameter the function sets on `ctx` itself, closing the class of bug (a caller can no longer
leave stale font state behind for the next measurement). (2) The label's Y-position was the gate
icon's own badge-gutter-stack slot Y — as early as the 2nd slot for a technology with no
rare/dangerous/mod badges before it — well within a 2-line name's own vertical span, since (unlike
the small square badges, which live entirely inside the gutter column) the label deliberately
extends leftward into the name's horizontal territory. Fixed by clamping the label's Y to never
start above where the name text block actually ends (`Math.max(gateIcon.y, nameText.y +
nameText.height + 2)`). Gate labels also switched to plain tail truncation (never middle) — unlike
card names, a gate label is never compared against another gate label for collisions, so there's
nothing for middle-ellipsis to protect. After both fixes: "Runic Matter Manipulation…" / "Needs
Civil Phanon…", cleanly separated, no overlap. Screenshotted before/after.

**Item 1c — the reported "garbled" AoT badge could not be reproduced.** Real per-mod counts
confirmed (ACOT 3, AoT 1 — `tech_civil_phanon_application` is the one AoT-requiring technology).
Checked at multiple zoom levels (36%–140%), via direct page load, and via search-then-click (a
different code path than direct camera positioning) — every check rendered the badge cleanly and
legibly, indistinguishable from an ACOT badge. Reported honestly as unreproduced rather than
inventing a speculative fix; real counts stated for the record in case it recurs.

**Item 2 — profile selector overflow, root-caused and fixed.** A `<select>`'s flex-item default
is `min-width: auto`, which resolves to its longest OPTION's intrinsic content width (e.g.
"Machine Intelligence") — this overrides `flex: 1`'s shrink behaviour entirely regardless of the
panel's own width. Fixed with the standard override (`min-width: 0` on `#profile-selector
select`, plus `overflow: hidden; text-overflow: ellipsis` for graceful degradation of whichever
select is tightest after an equal three-way split). Verified with the longest label on all three
axes simultaneously selected (Machine Intelligence / Biological / Non-nomadic) — all three fit
within the 300px panel.

**Item 3 — survey only, not implemented (see HANDOFF.md's next prompt for the full detail and
recommendation).** Confirmed real, evidenced findings: `swapMappings` (D-14) is emitted correctly
(123 distinct technologies carry an axis-expressible swap active for some profile, 0 for the
default profile, up to 123 for machine_intelligence/biological/nomadic — real per-profile counts)
but consumed nowhere in the client; the popup's Prerequisites/Dependents lists pool all three edge
kinds unlabelled with no profile filtering (`tech_mega_engineering`'s 5-edge list shows one true
`prerequisite` and 4 `alternative` OR-group members as one undifferentiated list — the same
OR-branch-flattening failure class documented as v1's own bug, now confirmed present in the popup
too). `appliesToEmpireTypes`/`activeEdgeIds` is confirmed a real no-op (984/984 — every edge,
every profile) by direct measurement against a real overlay, not just cited from CLAUDE.md's
existing note. Key finding: alternative-branch filtering does NOT need that unbuilt extractor —
each branch member's own `availabilityMatrix` entry already reflects per-profile reachability
correctly (measured directly: `tech_mega_engineering`'s 4 alternatives split available/locked
exactly as expected across three real profiles). Recommendation given to the user: two slices,
sequenced — swap/prerequisite-display first (smaller, and a real prerequisite for P-12.9's own
correct name display), research path second.

**Item 3c / research path (P-12.9) — survey only, not implemented.** Confirmed
`pipeline.dataset_emit`'s `researchPaths`/`_ancestor_research_path` is real and already shipping
in every empire overlay (not a stub), but is a simplified BFS-over-`prerequisite`-edges-only
placeholder — not P-12.9's per-profile cheapest-`OR`-branch algorithm. Full survey (missing
pieces, validation-figure reproduction plan) written up in HANDOFF.md's next prompt rather than
duplicated here.

**Item 4 — card vertical padding asymmetry, root-caused and fixed as real pipeline geometry.**
Confirmed from a real screenshot: a short sub-grid column (e.g. voidcraft/T0's 3-member
"Waystations" column, against the row's own 6-row shared height set by a denser column elsewhere
in the same row) was top-anchored, putting 100% of the row's leftover vertical space below the
last card and none above beyond the row's fixed header. Fixed in `pipeline/layout.py`: each
column's own member count is now tracked (`column_member_count`) and, in a second pass once every
row's shared height is final (`row_row_counts`), each column's local row is offset by
`(row_row_counts[row] - column_member_count[col]) // 2` — centring it within the row's shared
height instead of pinning it to the top. D-17's same-band column-ordering invariant is untouched
(this only changes vertical position WITHIN a column, never which column a node lands in).
**Canvas dimensions UNCHANGED — 29,670 × 13,448px** — this redistributes already-reserved space,
it doesn't add or remove any. New pipeline test
(`test_short_column_is_vertically_centred_within_the_row_height`, with its own
detector-fails-first companion) pins the behaviour. Full pytest (1,411 passed, up from 1,409),
`tsc`/`vite build` clean, all corpus tests (including the pinned canvas-dimension assertions)
unaffected. Screenshotted before/after — the 3-member column now sits with real, visible space on
both sides of its card stack, not just below.

**Item 5 — LOD text shedding, verified CORRECT, not a bug.** Checked whether S-03's real
shedding table is actually applied to name/cost/icon text (`.visible`, a real PixiJS hide, never
merely alpha-dimmed — confirmed via a new `checkLodTextShedding` debug hook). It is: all three
shed together, exactly at the `<5%` "Coloured block" threshold — the ONLY stage in S-03's table
that names them ("everything remaining"); no earlier stage in the table shortens for name/cost/
icon specifically. Verified numerically at 20% (all visible), 4.9% (all hidden), 100% (all
visible) against the real build. The user's report ("no longer appears to shed") is explained,
not contradicted: shedding happens right as the card becomes unreadably tiny anyway, so the
transition is imperceptible — spec-compliant, not a defect. Reported honestly rather than
inventing a change to something that already matches its own spec.

**Item 6 — middle-click isolation (P-7), confirmed spec-only.** `spec/P-07-isolation.md` fully
specifies it (depth-controlled, all-three-edge-kinds traversal, dimming/hiding mask, exit control
+ `Escape`, precomputed adjacency for the P-10 100ms budget) — confirmed genuinely unbuilt, not
partially built and missed. Left for a later, explicitly-requested slice per this session's own
instruction; recorded in CLAUDE.md's Open Items so it doesn't need re-discovering.

**Reconciliation (a) — gate-count arithmetic slip, confirmed and corrected.** The prior session's
own SURVEY reported "45 gate instances across 40 technologies"; the IMPLEMENTATION (same session,
later) correctly reports 70/60. Confirmed directly against the real build: 45 = 22
(`has_ascension_perk`) + 9 (`has_gigastructural_constructs`) + 14 (`has_galactic_wonders`) — the
survey figure silently omitted the 25 `has_technology` instances entirely, an arithmetic slip, not
a real discrepancy in the implementation (the implementation was always correct; CLAUDE.md,
HANDOFF.md and docs/BUILD-LOG.md's own implementation entry already carried the correct 70/60
figures — only `spec/P-03-gates.md`'s curation-decision paragraph still had the stale 45/40).
Corrected in `spec/P-03-gates.md` to 70/60, with the corrected per-technology `has_technology`
count (3 technologies name two targets each, not "a few").

**Reconciliation (b) — curation wording strengthened.** The prior session's spec wording ("45
gate instances... is small enough that badging all of them is informative rather than noisy") tied
the "badge everything" decision to a size threshold — readable as licence to reconsider if the
count ever grew, when the user's actual decision was unconditional: badge every occurrence,
always; the registry RESOLVES gates (icon/label lookup), it does not SELECT which occurrences
matter. `spec/P-03-gates.md` rewritten to lead with the unconditional rule and demote the real
corpus count to a parenthetical fact about the corpus, not the reason for the rule.

**Verified** (items 1, 2, 4, 5 only, per this session's own scope): full pytest (1,411 passed),
`tsc --noEmit`/`vite build` clean, headless-Chromium zero console errors/zero failed requests,
zero name-bounds violations, zero indicator-bounds violations (1,576 checked), zero
edge-endpoints-in-cards violations (984 checked), zero truncation-caused name collisions (5
remaining are source-identical, not truncation artifacts), LOD text shedding confirmed at the
real 5% threshold. New detectors proven capable of failing before being trusted: the
row-centring test's own top-anchored-bug simulation, the name-truncation collision/middle-
ellipsis-count reporting. Screenshots: the Runic Matter card before and after (both bugs fixed),
the profile selector at its longest labels (fits), a band cell showing the now-centred short
column, and a card at 4.9% zoom showing full LOD shedding (flat coloured blocks, no text/icons
anywhere).

**Not done this session** (explicitly out of scope, survey-only, or flagged rather than silently
built): swap-aware display and profile-filtered/kind-labelled prerequisite lists (surveyed,
recommended as the next slice, not implemented), the research path (P-12.9, surveyed, not
implemented), middle-click isolation (P-7, confirmed spec-only, not implemented), secondary gate
badges for a multi-gate technology on the CARD (popup already shows all gates).

## Hard regression fix session — row-overlap bug in the Item 4 vertical-centring change, plus the missing row-overlap invariant

A user screenshot at fit-to-viewport showed rows heavily overlapping — category rows drawing on
top of each other, both within a research area and across areas. The layout was correct before
the immediately-prior (screenshot-review) session's changes. All other planned work was stopped
per explicit instruction until this was root-caused and fixed.

**Root cause, confirmed by direct reproduction, not inferred.** The screenshot-review session's
Item 4 (short-sub-grid-column vertical centring, `pipeline/layout.py`) added
`column_member_count`, a dict tracking each sub-grid column's own member count so a short column
could be centred within its row's shared height instead of top-anchored. It was keyed by
`(row_id, col)` alone. `col` is BAND-RELATIVE — `depth_slot_start[(band_index, depth)]` resets
its own `cursor` to 0 for every `band_index` (confirmed by reading the `depth_slot_start`
construction directly) — so col 0 in one band and col 0 in a LATER band of the same row are
physically different columns (different `x`, via `band_x_start[band_index] + col * ...`) but
shared the same dict key. Two different bands' columns landing on the same local index had their
member counts silently SUMMED into one entry, which could exceed the row's real max
(`row_row_counts[row_id]`) and drive the centring offset `(row_row_counts[row_id] -
column_member_count[key]) // 2` NEGATIVE — shifting a column's cards upward past row 0, into the
row above. **Reproduced directly**: temporarily reverting the key back to `(row_id, col)` and
rerunning against the real corpus immediately produced `giga_tech_blokkat_afterburner`
(`column_member_count[('Blokkats', 0)] = 11` against `row_row_counts['Blokkats'] = 6`, offset
−3) and, with the same-session `assert centre_offset >= 0` also removed to let the corrupted
geometry through end to end, `giga_tech_birch_world_1` landing at row **−16** (`y = −1000`,
`column_member_count[('voidcraft', 0)]` corrupted to **37** against a real `row_row_counts` of
**6**) — confirming the exact symptom (rows drawing into each other) end to end, not just an
isolated assertion.

**Both named suspects investigated; only the first was real.** The vertical-centring change
itself (prime suspect) was confirmed as the sole cause. The second suspect — row-panel geometry
in `client/src/main.ts` desyncing from node positions again, the same defect class a prior
session found and fixed (CLAUDE.md's "pipeline owns all geometry" rule) — was checked directly
and ruled out: `client/src/main.ts` still derives every row's/band's extent from the REAL min/max
emitted node position within it (confirmed by reading the block's own code and comments), never
from an independent formula. It faithfully reproduced whatever the pipeline emitted, bug
included — that is the CORRECT behaviour of that architecture, not a second bug. This is recorded
explicitly in CLAUDE.md so it reads as "confirmed and ruled out," not "not checked."

**Fixed** by keying `column_member_count` (and the corresponding lookup in the second pass) on
the full `(row_id, band_index, col)` triple, which is unique by construction (each band's own
`col` values are only meaningful within that band). Added `assert centre_offset >= 0` directly in
`pipeline/layout.py` as a second, independent line of defence — a negative offset is provably
impossible for a correctly-scoped key, so this can only ever fire on a future instance of this
same mistake, never on legitimate data.

**Why canvas dimensions stayed byte-identical through the entire regression, and why that
shouldn't have been read as reassurance.** Row HEIGHT is derived from `row_row_counts[row_id]`,
computed entirely in the FIRST pass (per-band member counting), which the buggy second pass never
touches — only where an individual card sat WITHIN its already-correctly-sized row was corrupted.
Canvas width was never touched by either pass at all (`x`/`col` are set once, in the first pass,
and never revisited). So "canvas dimensions unchanged" was always going to be true regardless of
whether the centring fix was correct or badly broken — it measures a quantity the bug structurally
could not move, and its being unchanged carries no information about whether individual cards
landed inside or outside their own row's bounds. Explained here so a future "dimensions unchanged,
must be fine" shortcut doesn't recur for a similar bug shape.

**The real lesson, and why this reached the user**: the full existing test suite (1,411 tests,
including the pinned canvas-dimension and row-count assertions) stayed GREEN through the entire
regression. Nothing asserted the actual geometric invariant that matters — that no two rows'
card-occupied vertical extents intersect, and that no node's row index is ever negative. This is
the same lesson D-17's unbounded-stacking bug already taught this project once (a green suite
proves self-consistency, not correctness) — now recorded as a confirmed second occurrence, not a
new lesson.

**The missing invariant, added and proven capable of failing first.** Two new tests:
- `tests/test_layout.py::test_no_row_overlaps_when_the_same_row_spans_multiple_bands` — a fast
  synthetic case (one row, two bands, each band's own depth-0 column full at `subgrid_width`
  members) reproducing the exact collision shape, plus its own detector-fails-first companion
  test reconstructing the buggy vs. fixed key arithmetic directly.
- `tests/test_layout_corpus.py::test_no_row_overlaps_and_every_card_within_its_own_row_bounds` —
  real corpus: no node's `row` is ever negative, and no two rows' card-occupied vertical extents
  (min/max of `y`/`y + CARD_HEIGHT` per row) intersect, checked via a running-max-end sweep over
  rows sorted by start (not merely adjacent-pair comparison, which would miss one row's extent
  fully enclosing a later, shorter row's).

Both proven capable of failing BEFORE being trusted on the fix, per this project's own standing
rule: the corpus test was run against the actual pre-fix code (key reverted, internal assertion
also temporarily removed) and failed exactly as expected (`giga_tech_fe_megaworkshop_1` at row
−16), then the fix was restored and the same test passed clean.

**Audit of the screenshot-review session's other work (item 5's explicit ask): everything else
is intact.** Checked specifically because the regression's own dataset build was also used for
some of that session's verification screenshots:
- Item 1a (name truncation) and Item 1b (gate-label font/overlap fix): both pure per-card,
  Y-position-independent logic — unaffected regardless of which row a card's data happened to
  land in at build time. The demonstrated fixes remain valid evidence.
- Item 2 (profile selector CSS): no pipeline dependency at all — unaffected.
- Item 5 (LOD shedding): zoom-threshold based, not row-Y based — unaffected.
- Item 3's surveys (`swapMappings`, `activeEdgeIds`, availability-based alternative-branch
  filtering): read-only queries against availability/edge/gate data, computed independently of
  and before layout in `pipeline/dataset_emit.py` — the layout bug never touched any of the
  values reported. All findings stand as reported.
- The one casualty: `final_row_padding_centered.png` (the screenshot-review session's own "after"
  screenshot for Item 4) WAS built against the regression and has been superseded this session by
  fresh screenshots showing zero row overlap, both at fit-to-viewport and at close-up row
  boundaries.
- Items described in the prior turn's prompt as "activeEdgeIds wiring, tech swaps, prerequisite
  lists" were never implemented in the first place — Item 3 was explicit survey-only, nothing was
  built, so there is nothing there for a layout regression to have broken. Stated plainly here in
  case the phrasing in a future prompt implies otherwise.

**Verified**: full pytest (1,414 passed, up from 1,411 — 4 new tests: 2 regression tests + their
2 detector-fails-first companions), `tsc --noEmit`/`vite build` clean, headless-Chromium zero
console errors/zero failed requests. Real corpus row-overlap check: 0 violations across all 18
rows (full extent table reported: e.g. `computing` [68, 740] inside its [0, 788) panel,
`voidcraft` [9652, 10324] inside its [9584, 10372) panel, no adjacent or enclosing overlaps
anywhere). Zero name-bounds, indicator-bounds (1,576 checked) and edge-endpoints-in-cards (984
checked) violations. Canvas dimensions confirmed unchanged (29,670 × 13,448px) with the
mechanical reason why, not just the figure. Three screenshots: fit-to-viewport showing the full
18-row stack with clean separation, a 100%-zoom boundary between two rows in the same research
area (`computing` → `field_manipulation`), and a 100%-zoom boundary between two area groups
(`voidcraft` → `Aeternum`, showing the extra `AREA_GROUP_GUTTER` clearance).

## Screenshot-review follow-up session — dev monitor, four uncertainty resolution rules, gate/padding fixes, two surveys

Seven items from a fresh user screenshot-review round, building on the immediately-prior session's
`activeEdgeIds`/tech-swap/prerequisite-list work (see that entry above). All Items 1-6 implemented,
tested, and headless-verified (zero console errors, zero failed requests); Item 3 and Item 7 are
surveys only, per explicit instruction not to implement them yet.

**Item 1 — dev health monitor.** `diagnostics.schema.json` gained `uncertainTechnologies`
(`pipeline.dataset_emit.build_diagnostics`): every rendered technology with ≥1 `uncertain`
profile, `describe_condition()` reason text and `ReasonCategory` per profile,
`unconditional`/`perProfile` shape. Client: `client/src/dataset.ts`'s `fetchDiagnostics`, gated
behind `?dev`, rendering a plain DOM panel (`#dev-monitor`) grouped by category with click-through
to the node. BEFORE state (pre-Item-2): 247 technologies with ≥1 uncertain profile, 2738 uncertain
(tech, profile) pairs, category distribution `{crisis_or_story_progress: 1074,
origin_requirement: 528, ethics_or_civic_requirement: 480, opaque_country_state: 432,
unclassified: 176, mod_content_requirement: 48}`. AFTER (post-Items 2a-d, real corpus,
973-node denominator): 238 technologies, 205 unconditional + 33 profile-dependent.

**Item 2 — four resolution rules, all real evaluator behaviour changes, `pipeline/availability.py`:**
- **2a** `has_megacorp` (a genuine `host_has_dlc`-style DLC-ownership check) added to
  `GROUND_FACT_BOOL`, resolves `true` — 4 technologies move to `available`
  (`tech_mega_art`/`tech_interstellar_assembly`/`tech_matter_decompressor`/
  `tech_strategic_coordination`). Explicitly did NOT touch `is_megacorp` (a real empire-type/civic
  choice fact, a 4th axis this project's model doesn't track — confirmed by direct inspection of
  its usage site, `potential = { is_megacorp = yes }`, no DLC semantics at all).
- **2b** `colossus_project` (`has_country_flag`) added to a new `PROGRESSION_FLAGS_TRUE` set,
  resolves `true` — user-confirmed, one flag at a time, never a naming-pattern rule. 6 technologies
  (`tech_pk_cracker`/`_godray`/`_nanobots`/`_neutron`/`_shielder`/`_smelter`) had this leaf removed
  as their blocking reason; `tech_pk_shielder` moves fully to `available` (the other 5 have a
  separate, unrelated, genuinely-uncertain ethics/civic leaf). A broader candidate list was
  surveyed (all real `OPAQUE_COUNTRY_STATE`/`UNCLASSIFIED` leaf texts in the corpus) and presented
  for confirmation but NOT resolved: `giga_rings_beh`/`_gar`/`_tit`, `has_arcane_generator`,
  `has_finished_psionic_tradition`, `has_quantum_catapult_insight`, `is_country_type =
  acot_phanon_base`, `advanced_identity_creation`, `can_build_star_eaters`,
  `has_encountered_any_fauna`, `has_encountered_psionic_auras`, `days_passed = 0`,
  `country_uses_consumer_goods`, the `tech_ehof_sentient_tier_*` progression chain
  (`any_country`/`count_country`/`check_variable` shapes), and a `has_global_flag = @giga_amb_flag`
  variable-named flag (72 pairs, the single biggest UNCLASSIFIED contributor) affecting the ACOT/AoT
  tensile family from Item 2d.
- **2c** `pipeline.rendering_scope._is_permanently_disabled`: a technology whose `potential` has a
  TOP-LEVEL (not nested) literal `always = no` leaf is excluded from the rendered set entirely,
  never rendered locked/uncertain. Real corpus: exactly 4 — `giga_tech_aeternite_weaponry`
  (clean singleton `{ always = no }`), `giga_tech_interstellar_ringworld`,
  `giga_tech_orbital_elysium`, `giga_tech_stellar_ring_habitat` (all three carry `always = no`
  alongside now-dead siblings — e.g. `orbital_elysium`'s own `#disabled since 4.0` comment).
  Verified nothing else references any of the 4 as a prerequisite (no dangling-edge risk).
  `config/name_overrides.txt`'s now-dead `giga_tech_aeternite_weaponry` entry removed (its
  technology no longer renders, so the override can never fire) rather than left in place.
  Full reconciliation, every figure re-derived and asserted, not estimated: 977 → 973 nodes,
  984 → 977 edges (876 prerequisite + 76 alternative + 25 potential-gate, -7 prerequisite edges,
  all 4 excluded technologies' own outgoing references), row counts `voidcraft` 123→122,
  `statecraft` 82→81, `Aeternum` 3→2, `new_worlds` 49→48 (one excluded technology each, all other
  rows unaffected), crisis-faction counts `Standard` 900→897, `Aeternum` 3→2, densest cell
  `voidcraft`×T5 47→46, canvas 29,670×13,448px → 29,670×13,332px, icon atlas resolved candidates
  1189→1185 (4,799,342 → 4,783,554 bytes), reduced-corpus (no ACOT/AoT) build also lands on 973
  (973-4+4=973, the same kind of arithmetic coincidence D-15's 977-4+4=977 already was — verified
  directly, not assumed to hold).
- **2d** `has_acot` added to `GROUND_FACT_BOOL` (resolves `true`); `has_global_flag = has_aot_mod`
  added to a new `MOD_PRESENCE_FLAGS_TRUE` set (resolves `true`) — both a genuinely different
  reasoning class from DLC ownership (this deployed tree already assumes ACOT/AoT content is
  present; a technology gated on "does the content exist" isn't really uncertain about that).
  `pipeline.dataset_emit._potential_mod_requirements` (new, scope-disciplined the same way
  `pipeline.edges._scoped_has_technology` is) separately adds the `requiresMods` badge these
  technologies need — availability and mod-badge display are two different mechanisms keying off
  the same leaf. Real corpus: 4 technologies (`giga_tech_amb_supertensiles_acot_alpha/sigma/
  delta/phanon`), `alpha`/`delta` get `["ACOT"]`, `sigma`/`phanon` get `["ACOT", "AoT"]` (AoT
  depends on ACOT). None flip to fully `available` (each has a separate, still-unresolved
  `@giga_amb_flag` leaf), but the misleading "uncertain — has_acot = yes" reason is gone.

**D-10 net effect (all four rules combined, real corpus, 973-node denominator): worst
profile-dependent 33/977 (3.37%) → 28/973 (2.88%, now UNDER the 3% warn threshold);
unconditional 209/977 → 205/973.** Both real improvements (the ratchet only fires on an increase),
asserted directly (`tests/test_availability_corpus.py`, `tests/test_dataset_emit.py`), not assumed.

**Item 3 — survey only, `add_research_option` grants.** `common/ascension_perks/` is vendored but
had never been read for effect-block content (only icon-file lookup touches it). Full corpus
table: `ap_galactic_wonders` (Gigastructures-overwritten to add `tech_mega_engineering` to
vanilla's own `tech_ring_world`/`tech_dyson_sphere`/`tech_matter_decompressor` grant),
`ap_voidborn` → `tech_habitat_2/3`, `ap_weather_control` → 2 storm techs, `ap_gigastructural_
constructs` → 3 Gigastructures megastructure techs, plus 5 more Gigastructures perks whose grants
are already redundant with a visible `has_ascension_perk` gate (no action needed). Real, concrete
bug confirmed: `tech_dyson_sphere`'s `potential` is only `{ is_nomadic = no }`, `weight_modifier`
is an unconditional `factor = 0` — structurally impossible via the normal draw, `add_research_
option` is the ONLY real route, entirely invisible to this pipeline today. 3 technologies share
this exact unconditional-zero-weight shape (`tech_ring_world`, `tech_dyson_sphere`,
`tech_matter_decompressor`); the rest (including `tech_mega_engineering` itself) have a real
nonzero or merely-conditional-zero weight, so the grant is an accelerant for them, not the sole
route. Recommendation: extend P-3's gate registry (a perk gating access is exactly what a gate
badge means) rather than a new display concept. Not implemented.

**Item 4 — gate label collision + icon size, `client/src/main.ts`.** The existing name-collision
guard (from an earlier session) never checked the COST line — both the gate label's Y (name bottom
+ 2px) and the cost line's own `belowNameY` fallback (name bottom + 4px) are independently derived
from the same `nameText.height`, landing within 2px of each other for a 2-line name. Fixed with a
real rectangle-overlap check (not an unconditional clamp) against the cost text's actual bounds.
Icon enlarged 16px → 24px (`GATE_ICON_SIZE`, fits inside the 34px gutter). Real, load-bearing
finding surfaced by the fix: for a 2-line name + a real (non-null) cost + a gate together, there is
often NO room left on the fixed 270×92 card for label text at all once BOTH collisions are
correctly avoided — **50 of 56 gated technologies** (89%) hit this. Per instruction, the label is
dropped (icon-only) rather than shrunk or left overflowing the card; full "Needs X" text remains in
the popup's Gates section regardless. Verified against the real corpus:
`window.__tt.checkGateLabelFontAndCollision()` (a new detector, added this session) and the
existing `checkIndicatorBounds()` both report 0 violations; `debugGateGeometry(techId)` (new debug
hook) was used to trace the exact pixel numbers behind the fix before trusting it.

**Item 5 — redundant prerequisite-as-gate text, `pipeline/dataset_emit.py`'s `_build_gates`.**
CLAUDE.md's own documented "4 real pairs are both a formal prerequisite and a potential-gate" are
not real GATES in the P-3 sense — they redundantly encode one dependency twice, and the card/popup
showed "Needs X" duplicating what the Prerequisites list/edge already said. Fixed with a
DISPLAY-layer exclusion only (a `has_technology` gate match whose target is also a true
`prerequisites` entry of the same technology is dropped from the emitted `gates` list) —
`pipeline.gate_patterns`'s raw classification and the underlying `potential-gate` edges are
untouched. Real corpus, not the 4 originally assumed: `giga_tech_amb_supertensiles_acot_alpha/
sigma/phanon` (3 of the ACOT/AoT tensile family — `_delta` was never actually a gate owner, its own
`potential` has no `has_technology` leaf at all) plus `giga_tech_arkship_neutronium_harvester`
(the OTHER known dual-encoded pair, on `tech_mega_engineering`). Emitted totals: 70/60 → 66/56
(technology-kind 25 → 21); raw classification stays 70/60 (asserted separately).

**Item 6 — top-heavy row padding, `pipeline/layout.py`.** User-confirmed cause (offered as one of
three options, this was the selected one): a sparsely-populated sub-grid column, centred 50/50
within its row's shared height, reads as "a large gap at the top, cards touching the bottom" once
compounded with the row header's own content sitting immediately above row 0 — the header has no
comparable content below the last card to visually break up that side's blank space the same way.
The centring formula itself (`// 2`, a genuinely symmetric floor-division split) wasn't buggy; the
PERCEPTION was real given the surrounding content. Fixed by putting a quarter of the slack above
and three-quarters below (`// 4`). Canvas dimensions unaffected (centring only redistributes slack
within an already-fixed row height, never changes `row_row_counts`) — confirmed directly:
29,670×13,332px, same before and after. Visually confirmed via before/after screenshots of the
same sparse `field_manipulation`/Tier-0 cell (2 members in a 6-row-tall row): cards moved
noticeably closer to the header, freed space redistributed below.

**Item 7 — survey only, hover vs. selection scope.** No `spec/` file defines either; the only
hover-related spec text is P-9's tap/press-equivalent accessibility requirement. Direct code
reading (`client/src/main.ts`) found the CURRENT implementation already has exactly the split
requested: `setHovered` highlights only directly-connected edges (one hop); `setSelected` calls
`computeAncestryAndDependents`, a full BFS over all three edge kinds, highlighting the entire
ancestor/dependent closure. The feature already exists — it's simply not surfaced anywhere that
selecting reveals more than hovering does. Not changed, per instruction.

**Housekeeping**: CLAUDE.md's D-10, Gates, and Open Items sections updated in place (stale
`33/977`/`209/977`/`70/60` figures corrected throughout the file, not just in this log; the
`giga_tech_amb_supertensiles_acot_alpha` gate example in the Gates section was itself stale post-
Item-5 and replaced). Three now-fully-closed Open Items bullets (`appliesToEmpireTypes`
unconstrained, tech-swap consumed nowhere, popup pooling all edge kinds — all closed by the
IMMEDIATELY PRIOR session, but never reconciled into CLAUDE.md at the time) were also closed out
this session while touching the same section. HANDOFF.md's "Next prompt" section (stale for
several sessions, pointing at long-completed work) rewritten to point at the P-12.9
implementation, with the three stale validation figures named explicitly so they get corrected in
the same pass rather than silently trusted.

## "Path to zero uncertain" follow-up session — has_ancrel fix, scripted-trigger expansion, ethics/civic/origin gates, OR-context gate fix

Implements the mechanical, user-approved parts of a six-part survey run the prior session
(scratch scripts, never shipped). Four items, each measured against the real corpus, no estimates
carried forward unverified — several real figures diverged from the survey's own projections, and
each divergence is recorded with its real cause below rather than silently accepted.

**Item 1 — `has_ancrel` fix, the FIFTH instance of this project's recurring defect class.**
`pipeline/trigger_text.py` asserted `has_ancrel` was "not a scripted_trigger definition anywhere
in the vendored corpus" and a Gigastructures relic-questline flag — never verified against raw
source, and wrong: `vendor/stellaris/common/scripted_triggers/00_scripted_triggers.txt:2678` is
`has_ancrel = { host_has_dlc = "Ancient Relics Story Pack" }`, a literal DLC check. Fixed via
`pipeline.availability.GROUND_FACT_BOOL` (the existing DLC-ownership rule), not a `trigger_text`
category change, since it's never UNCERTAIN any more. 22 technologies (`tech_archaeo_*`) move
AVAILABLE, 1 (`tech_archeology_lab`) moves LOCKED. Distinct from the first four defect-class
instances: those were wrong ANSWERS computed by code; this was a wrong CLAIM written down as a
documented finding and trusted by every later session without re-verification. Real effect: 238 →
215 uncertain (any-profile), unconditional 205 → 183, worst profile-dependent 2.88% → 2.77%.

**Item 2 — `pipeline/scripted_triggers.py`, general recursive scripted-trigger expansion.** New
module: substitutes a trigger's real body in place of its name (bare-identifier-leaf shape, NOT
`inline_scripts`' parameterised text substitution — confirmed not reusable by survey before
implementation), then hands the rewritten block to the UNCHANGED Kleene evaluator. Real corpus:
3,463 distinct trigger names after overwrite resolution (135 redefined by a later source), zero
cycles, max depth 8 (`MAX_EXPANSION_DEPTH=12`, hard failure not silent truncation if ever hit).
`is_ai=yes` branches stripped, generalising the two previously-hardcoded wrapper mappings' own
treatment — took three real iterations to get right, each caught by re-running the corpus survey
after writing the previous version:
1. Naive "contains is_ai anywhere in this subtree" dropped whole unrelated sibling branches.
2. **The real regression**: `country_uses_bio_ships` is ALSO a real scripted-trigger name (body
   opens with `exists = this`, a shape the evaluator has no notion of) but is ALREADY specially
   resolved by `AXIS_FACTS` — blind expansion destroyed the axis-fact shortcut for all ~238 real
   occurrences, a 110-technology regression (215 → 320) caught only by re-running the survey.
   Fixed: any key already in `AXIS_FACTS`/`GROUND_FACT_BOOL`/`DLC_NAME_CHECK_KEYS` is skipped by
   expansion unconditionally (`_ALREADY_RESOLVED_KEYS`).
3. `has_galactic_wonders`'s real `is_ai` branch is wrapped in `hidden_trigger = { and = {...} } }`,
   not a bare `AND` — an 11-technology regression, fixed by recognising `hidden_trigger` as
   droppable specifically when ALL its own children are themselves is_ai-gated.
Real effect on its own (from Item 1's already-fixed 215 baseline): any-profile-uncertain count
UNCHANGED (215 → 215 — the target triggers only ever produce PARTIAL per-profile improvement, not
full resolution), but unconditional improves (183 → 176, e.g. `is_wilderness_empire`'s hive-only
origin now short-circuits LOCKED for the 8 non-hive profiles via the authority axis alone) while
the worst profile-dependent rate RISES (2.77% → 3.49%, crossing the 3% warn line) — the same 7
technologies moving from "uncertain for everyone" to "uncertain only where axis-consistent," more
informative but counted against this specific metric. A real, reported tradeoff, not hidden.

**Item 3 — ethics/civic/origin as display gates, 19 new `EXCLUDED_KEYS` entries.** Same
identity-element treatment ascension perks already get. Origin-shaped (`has_origin` direct, plus
1:1 wrappers `is_wilderness_empire`/`giga_has_frameworld_origin`), ethics/civic-shaped
(`has_ethic`/`has_valid_civic`/`has_civic` direct, plus 1:1 wrappers `is_fanatic_spiritualist`/
`is_fanatic_pacifist`), plus 11 more excluded-but-not-gate-classified compound triggers (an `OR`
of several real sub-conditions, no single clean `refId` — `is_void_dweller_empire`, `is_megacorp`,
...; see `pipeline.gate_patterns.NOT_GATE_CLASSIFIED_EXCLUDED_KEYS`). **Every one of the 19 that is
ALSO a real scripted-trigger catalog name needed the SAME fix as Item 2's `country_uses_bio_ships`
regression** — found again, at 19x the scale, and fixed generally this time
(`_ALREADY_RESOLVED_KEYS` now derives from `EXCLUDED_KEYS` wholesale, minus the two deliberately-
expandable wrapper names). New `GateKind` values `origin`/`ethics_or_civic` (D-3 priority: perk >
origin > ethics-or-civic > technology); icons NOT vendored (`common/civics`/`origins`/`ethics`
absent for every source — reported, not acted on; falls back to the existing
`_default_icon_ref` stub, label text is the real content). Real effect: any-profile-uncertain 215
→ 127, unconditional 176 → 107, worst profile-dependent 3.49% → **1.54%** (all 12 profiles back to
"ok" status) — `ORIGIN_REQUIREMENT`/`ETHICS_OR_CIVIC_REQUIREMENT` both drop to zero in the
unconditional distribution. Gate instances 66/56 → 136/109 (45 ascension_perk + 45 origin + 24
ethics_or_civic + 22 technology, the last including a new `can_research_technology` alias of
`has_technology`).

**Item 4 — the OR-context gate display bug, confirmed real and fixed.** `tech_torpedoes_1` showed
"Needs Riddle Escort" as unconditional when it's one of four independent OR branches (non-bio-ship
empires already qualify via a different branch entirely) — `tech_missiles_1` shares the shape.
11/25 (44%) real `has_technology`-under-`potential` occurrences sit inside an OR.
`GateMatch`/`Gate` schema gained `alternative: boolean` (`_scoped_gate_leaves` tracks OR-ancestry
independent of negation) — label becomes `"or: <name>"` instead of `"Needs <name>"`. Generalised
correctly beyond the reported bug: `giga_tech_the_vat`'s `ap_mechromancy` perk gate is ALSO
genuinely OR-context, now `"or: Mechromancy"` where its sibling `has_galactic_wonders` (AND-
context) stays `"Needs Galactic Wonders"`. Second field `appliesToEmpireTypes` (nullable
`EmpireTypeConstraint`) reuses `pipeline.edge_constraints`' EXISTING per-edge axis constraint
(`shipset: ["biological"]` for the Riddle Escort edge, already computed for `activeEdgeIds`, not
recomputed) — wired into the CLIENT too (`gateAppliesToProfile`, combined with the existing
zoom-driven LOD visibility loop via a new `nodePrimaryGateConstraint` index-parallel array, plus
the popup's gate-list filter), so a Mechanical-shipset profile never sees the badge at all and a
Biological-shipset profile sees it worded as an alternative. Verified visually against the real
built dataset (Playwright + headless Chromium, no `chromium-cli` available in this environment —
installed Playwright's own Chromium build instead): screenshots confirm the badge absent/present
correctly in both card and popup across the profile switch, zero console errors either way.
`pipeline/edges.py` deliberately untouched — confirmed not the bug, a different concern (edge
completeness) from gate display wording.

**Cumulative real effect, all four items, same measurement basis throughout (973 rendered
technologies)**: any-profile-uncertain **238 → 127** (111 technologies resolved), unconditional
**205 → 107**, worst profile-dependent **2.88% → 1.54%** (comfortably under the 3% warn threshold
throughout, despite a real intermediate rise to 3.49% under Item 2 alone). Gate instances
**66 → 136** over **56 → 109** technologies, four `GateKind` values instead of two. Full pytest
suite green throughout (1492 passed at session end), `tsc --noEmit` and `vite build` both clean,
zero headless-Chromium console errors or failed requests across every screenshot pass.

**Housekeeping**: CLAUDE.md's "Trigger evaluation" and "Gates" sections updated in place with the
real current figures and full writeups for all four items (not summarized elsewhere only).
HANDOFF.md's stale `66 gate instances over 56 technologies` prerequisite-paragraph figure flagged
as superseded, pointing at CLAUDE.md rather than restating the new number in two places. New test
files: `tests/test_scripted_triggers.py` (mechanism), `tests/test_scripted_triggers_corpus.py`
(real corpus, cycle/depth/is_ai regression guards). `tests/test_gate_patterns.py`'s cross-module
sync test extended from a strict equality (`GATE_LEAF_KEYS == EXCLUDED_KEYS`) to a three-way split
(`GATE_LEAF_KEYS | NOT_GATE_CLASSIFIED_EXCLUDED_KEYS == EXCLUDED_KEYS`, disjoint) now that not
every excluded key gets a badge. Real dataset rebuilt (`tools/build_dataset.py`) and client built
(`npm run build`) against it for the verification pass, not left as a stale on-disk artefact from
before this session's changes.

## "Commit + close the loop" follow-up session

**Item 0 — the prior session's work was staged but never committed, again.** Committed in five
logical groups (pipeline+schema, tests, client, docs, then this session's own standing-instruction
addition) instead of one giant commit — see `git log`. Added a standing Rule to CLAUDE.md: commit
at the end of every session, in logical groups, never left staged. This is the second time
bisectability was lost to accumulated uncommitted work across sessions; the fix from the first time
had already drifted back.

**Item 1 — the corpus-wide uncertain count is now a pinned, structural test invariant.**
`tests/test_availability_corpus.py::test_uncertain_count_and_per_profile_breakdown_pinned` pins the
union uncertain-technology count (any technology UNCERTAIN for ≥1 of 12 profiles — a number no
earlier test computed at all) and the full per-profile breakdown, at the same grain the
unconditional/category figures were already pinned at (`test_real_rates_against_projections`).
Proven capable of failing, not just passing: temporarily removing `country_uses_bio_ships` from
`pipeline.scripted_triggers._ALREADY_RESOLVED_KEYS` (this project's own historical bug, reintroduced
by hand, then reverted) made the assertion fail loudly — union count jumped 127 → 213. D-10's
existing ratchet mechanism (`build_profile_dependent_diagnostics`/`build_unconditional_diagnostic`'s
`regressed` flag) was already unit-tested synthetically; no further work needed there.

**Item 2 — the crisis/story-progression flag CLASS, applied by pattern rather than one flag at a
time.** `pipeline.trigger_text._looks_like_story_progress` (previously private, used only for
DISPLAY categorisation) is now public (`looks_like_story_progress`) and also consumed by
`pipeline.availability` to RESOLVE matching `has_country_flag`/`has_global_flag` names TRUE — the
same evidence-basis and treatment already user-approved for the `colossus_project` precedent
(`PROGRESSION_FLAGS_TRUE`): the survey found every sampled real setting site is a genuine
`is_triggered_only` country event with no empire-type restriction. Real corpus: 64 distinct flag
names, 73 technologies move UNCONDITIONALLY uncertain → AVAILABLE for all 12 profiles at once (none
became merely profile-dependent — the worst profile-dependent rate is UNCHANGED at 1.54%).
Unconditional uncertainty: 107 → 34/973 (3.49%). Union uncertain-for-≥1-profile: 127 → 54/973.

Two real pattern matches are deliberately EXCLUDED from this resolution
(`pipeline.availability.PROGRESSION_PATTERN_EXCLUDED_FLAGS`) despite matching the naming pattern:
`l_cluster_opened` and `encountered_first_lgate` are VANILLA Stellaris L-Gate storyline flags whose
setting sites live in vanilla's `events`/`decisions`, which this project does not vendor — unlike
every Gigastructures match, there is no corpus text to verify them against, so resolving them would
rest on outside-corpus knowledge, not evidence gathered this project's own way. They remain the
sole surviving `crisis_or_story_progress` unconditional-uncertain member (count 1) plus a
profile-dependent contribution from the other excluded flag.

Six outliers the survey found NOT matching the pattern (reported, not resolved, per the session's
explicit instruction): `can_build_star_eaters`, `acot_databank_sophia_agreed`,
`advanced_identity_creation`, `has_arcane_generator`, `has_quantum_catapult_insight`,
`has_encountered_psionic_auras`. Two more of the same non-matching shape turned up during this
session's own direct corpus walk and are reported the same way: `finish_shroud_forged_liberation_flag`
(2 technologies, `tech_pk_godray`/`tech_pk_neutron`), `machine_subspecies` (6 technologies, the
`is_individual_machine`-adjacent robotics family).

**Item 3 — `founder_species`/`has_authority`: already closed by prior work, not a new gap.**
Direct corpus inspection found `founder_species = { is_archetype = MACHINE }` never appears
directly in any rendered technology's `potential` block — the only real corpus wrapper containing
it, vanilla's `is_individual_machine` (`00_scripted_triggers.txt`'s
`02_scripted_triggers_machine_age.txt:62`), was already added to `EXCLUDED_KEYS` AND to
`pipeline.gate_patterns.NOT_GATE_CLASSIFIED_EXCLUDED_KEYS` by an EARLIER session's own Item 3
(ethics/civic/origin display gates). 21 rendered technologies reference `is_individual_machine`
(mostly `OR = { is_machine_empire = yes, is_individual_machine = yes }`), all already resolve
without ever reaching UNCERTAIN. Identical story for `has_authority = auth_corporate` via
`is_megacorp` (2 technologies: `tech_executive_retreat`, `tech_xeno_tourism_agency`) — already
excluded from availability and deliberately NOT gate-badged, for exactly the reasoning this
session's Item 3b would otherwise have had to work out from scratch (MegaCorp is a real 4th
authority value the 3-axis model doesn't carry; adding it as an axis would double
`EmpireProfileAxes`' cardinality — 12 → 24 profiles, doubling every per-profile emitted array — to
serve 2 technologies, not worth it against the display-gate alternative already shipped). No code
change made; this item's only output is the corrected understanding, recorded here and in CLAUDE.md
so a future session doesn't re-open it as if it were still a gap.

**Item 4 — the `@giga_amb_flag` config-toggle pattern: investigated, reported, NOT applied.**
`vendor/mods/gigastructures/common/scripted_variables/giga_amb_variables.txt:5`'s own comment
(`@giga_amb_flag = giga_buildcap_j # menu option variable name, checked for feature activation`)
confirms the MECHANISM matches `_capped_r` — a Gigastructures options-menu toggle, checked via
`has_global_flag`. But it differs from `_capped_r` in two ways that matter, either one enough to
withhold the pattern-match on its own:
1. `_capped_r`'s resolution to FALSE rests on an explicit USER confirmation that no core
   Gigastructures preset sets that specific mode. There is no equivalent confirmation for
   `giga_buildcap_j`'s default state, and unlike `_forbidden`/`_disabled`/`_OFF`, its name carries
   no self-describing suffix that the general "unset = feature not active" modding convention
   could be inferred from.
2. The corpus value is a `VariableReference` (`@giga_amb_flag`), not a literal `Identifier`/
   `StringLiteral` — `pipeline.availability._flag_value_name` only resolves the latter two today.
   Even with a confirmed default, applying it would require threading a `variable_table` through
   `evaluate_trigger_block`/`_evaluate_leaf`, a real (if scoped) signature change not attempted
   this session pending the confirmation that would make it worth doing.

Real corpus: **10 technologies**, not the originally-scoped 7 — a direct walk of the whole
`common/technology` corpus (not just `giga_17_alternative_mega_build.txt`, where the pattern was
first noticed) found `giga_tech_fe_megaworkshop_1`, `giga_tech_fe_megaworkshop_2`, and
`giga_tech_orbital_ring_supertensiles_mine_hub` also reference the same variable. Left unresolved,
folded into the residue reported in Item 5.

**Item 5 — remaining residue after Items 2-4, real corpus counts (973 rendered, 54 union
uncertain, 34 unconditional):**

| Leaf construct | Techs affected | Classification |
| --- | --- | --- |
| `has_country_flag`/`has_global_flag` one-off names (`acot_databank_sophia_agreed`, `advanced_identity_creation`, `can_build_star_eaters`, `finish_shroud_forged_liberation_flag`, `has_arcane_generator`, `has_encountered_psionic_auras`, `has_quantum_catapult_insight`, `machine_subspecies`) | 16 (some names shared across 2+ techs) | Genuinely unknowable runtime/player-choice state — no single resolvable pattern, matches HANDOFF's original CHECK 2 finding |
| `@giga_amb_flag` (`giga_buildcap_j`) | 10 | Item 4's config-toggle candidate — needs user confirmation of default state, see above |
| `giga_rings_beh`/`giga_rings_gar`/`giga_rings_tit` | 5 | On CLAUDE.md's existing surveyed-but-unconfirmed `PROGRESSION_FLAGS_TRUE` candidate list — same "ask one at a time" rule as `colossus_project`, not yet asked |
| `l_cluster_opened`/`encountered_first_lgate` | 2 | Vanilla L-Gate storyline flags, deliberately excluded from Item 2's resolution (events/decisions not vendored) |
| `if = { limit = {...} }` conditional-effect blocks | 4 (`tech_luxuries_1`/`_2`, `tech_consumer_good_refinement_1`/`_2`) | Relaxable by evaluator thoroughness (user explicitly offered this for `count_country`/`resource_expenses_compare`-shaped constructs) — not attempted this session, scoped follow-up |
| `has_tradition` | 4 (`tech_missiles_1`, `tech_torpedoes_1`, `giga_tech_shroud_conduit`, `giga_tech_psychic_hypersiphon`) | Genuinely unknowable live tradition-tree state |
| `exists` (scope-existence checks) | 4 (`tech_gravity_wells`, `tech_holographic_rituals`, `tech_consecration_fields`, `tech_transcendent_faith`) | Not previously catalogued by this project — worth a follow-up survey of what these actually check |
| `check_variable` on `ehof_phase` | 3 | Live EHOF crisis-chain progression counter, genuinely unknowable |
| `has_policy_flag` | 1 (`tech_neural_implants`) | Genuinely unknowable live policy-choice state |
| `has_menace_perk` | 1 (`tech_xeno_linguistics`) | Genuinely unknowable live menace-tree state |
| `has_active_tradition` | 1 (`giga_tech_the_vat`) | Genuinely unknowable live tradition state, distinct construct from `has_tradition` |
| `has_dna` | 1 (`tech_controlled_mutations`) | Not previously catalogued, needs its own look |
| `days_passed` | 1 (`tech_federation_code`) | Genuinely unknowable elapsed-game-time state |
| `always` | 1 (`tech_ring_world`) | Needs individual inspection — `always = no/yes` combined with other unresolved branches, not obviously a new construct on its own |
| `is_country_type = acot_phanon_base` | 1 (`tech_dark_matter_power_core_se`) | **Needs a domain answer, not a technical one — see below.** |

**`is_country_type = acot_phanon_base` — a genuine open question for the user, not decided.**
`tech_dark_matter_power_core_se`'s `potential` is `NOR = { is_fallen_empire = yes, is_country_type
= acot_phanon_base } AND has_country_flag = stellarite_tech_enable`
(`acot_03_stellarite_components_tech.txt:709-715`). `acot_phanon_base` appears widely across ACOT's
`common/armies`, `common/buildings`, `common/districts`, `common/bombardment_stances`,
`common/game_rules`, and `common/scripted_effects` — always alongside `is_fallen_empire` or a
`COUNTRY_TYPE = acot_phanon_base` scoped-effect target, and `acot_03_phanon_components_tech.txt`
defines `damage_vs_country_type_acot_phanon_base_mult` weapon modifiers, the same shape as a damage
multiplier against Marauders or a Fallen Empire. This is consistent with `acot_phanon_base` being
an AI/event-only country type (an NPC "Phanon" faction, not a selectable player empire type) —
meaning no player empire could ever satisfy this technology's `NOR`, a genuine
PERMANENT-IMPOSSIBILITY case this project's model has no state for (distinct from `uncertain`,
`locked`, or `config-gated` — those all describe conditions a player empire COULD satisfy under
different facts; this would describe a condition no player empire can ever satisfy). Not resolved
here — this rests on domain knowledge of ACOT's country-type system this project's vendored corpus
cannot itself confirm (there's no ACOT `common/country_types`/equivalent directory vendored to
check against). Asked of the user in this session's own report rather than guessed at.

**The realistic floor and its cost.** Of the 54 union-uncertain technologies: ~26 are genuinely
unknowable runtime/story state no static analysis will ever resolve (has_tradition,
has_active_tradition, has_policy_flag, has_menace_perk, check_variable/ehof_phase, days_passed, the
8 one-off has_country_flag names, is_country_type pending the domain answer above) — this is the
real floor, not a gap to close. ~19 are pending EITHER a user confirmation this session didn't have
(giga_buildcap_j's default state, 10; giga_rings_beh/gar/tit, 5) OR a scoped evaluator-thoroughness
relaxation the user already pre-approved but this session didn't implement (if/limit blocks, 4).
~5 (`exists`, `has_dna`, `always`) haven't been individually surveyed at all and may turn out to
belong in either bucket. Reaching the confirmable floor costs: one round of user confirmations
(giga_buildcap_j default state, giga_rings_beh/gar/tit, is_country_type=acot_phanon_base) plus one
small implementation pass (VariableReference resolution in `_flag_value_name`/`_evaluate_leaf` for
giga_buildcap_j, plus whatever `PROGRESSION_FLAGS_TRUE`/similar entries the confirmations produce);
reaching the true floor beyond that requires only surveying `exists`/`has_dna`/`always`, not more
user confirmation.

**Post-report follow-up: the two open questions were answered by the user.**

- **`acot_phanon_base` is confirmed AI/event-only, never a player empire — and, critically, the
  technology IS reachable** (the user: "the ...core_se tech is accessible to players who have
  progressed pretty much to the end of ACOT's content"). This is NOT the permanent-impossibility
  case the survey flagged as possible; it's an ordinary ground fact, same mechanism as
  `is_fallen_empire`, just keyed on a specific country-type VALUE rather than a bare leaf. Added
  `pipeline.availability.COUNTRY_TYPE_NEVER_PLAYER = {"acot_phanon_base"}` and an `is_country_type`
  branch in `_evaluate_leaf` resolving membership to FALSE (only this one confirmed value — an
  unconfirmed `is_country_type` value stays UNKNOWN, not swept in blind). Real corpus effect:
  `tech_dark_matter_power_core_se` stays UNCERTAIN (unchanged count), but the responsible leaf
  corrects from the wrong `is_country_type = acot_phanon_base` reason to the real one,
  `has_country_flag = stellarite_tech_enable` — genuine per-playthrough ACOT-progression state,
  correctly still unresolved. No node count or D-10 figure moves; this is a reason-text
  correctness fix, not a resolution-count fix.
- **`giga_buildcap_j` deliberately left UNRESOLVED — a considered call, not an oversight.** The
  user: the mod's own reference-balance preset has supertensiles ON by default, but most real
  players change the setting and Gigastructures' own default may drift over time. This is the
  OPPOSITE evidence shape from `_capped_r` (confirmed unset in every core preset, no ambiguity) —
  here the reference default is SET, real-world usage diverges from it, and the designer's own
  intent is explicitly volatile. Resolving to either constant would misrepresent a genuinely
  unstable fact as settled, exactly what UNCERTAIN exists to avoid. Left UNCERTAIN; the 10
  affected technologies (`giga_tech_amb_living_metal_infusion`, `giga_tech_amb_sentient_metal_
  molecular_foundries`, `giga_tech_amb_supertensiles(_acot_alpha/_delta/_phanon/_sigma)`,
  `giga_tech_fe_megaworkshop_1/2`, `giga_tech_orbital_ring_supertensiles_mine_hub`) keep an
  accurate `has_global_flag = @giga_amb_flag` reason string already (`_value_text` already renders
  `VariableReference`s correctly for display, even though `_flag_value_name` — the RESOLUTION path
  — still doesn't resolve them; that gap stays open, now confirmed not worth closing without a
  resolution target to apply it to).

**Three-state availability is unaffected and not up for revision.** `uncertain` remains a real,
reachable state regardless of how small its population gets (54 today, was 973's full complement
before this project's evaluator existed at all) — this session's resolutions each removed a
specific, evidenced, resolvable case, never widened what counts as resolvable, and the floor above
is explicitly NOT zero. A future corpus refresh introducing a genuinely new undecidable construct
must surface as UNCERTAIN, not be quietly guessed into AVAILABLE/LOCKED to make the count look
better.

**Verification**: full `pytest tests/` (1495 passed), `tsc --noEmit` and `npm run build` both
clean. Real dataset rebuilt (`tools/build_dataset.py`) and matches the pinned test figures exactly
(diagnostics.json: `unconditionalUncertainty.count` 34, `uncertainTechnologies` length 54, worst
`profileDependentUncertainty` rate 0.015416). Layout invariants
(`test_no_row_overlaps_and_every_card_within_its_own_row_bounds` and siblings in
`tests/test_layout_corpus.py`/`tests/test_layout.py`, plus `tests/test_edge_constraints.py`) all
green — this session touched no layout/geometry code, so this is a confirmation, not new coverage.
**No headless-Chromium screenshots this session** — this environment has no browser-automation tool
available (`claude-in-chrome` not connected) and no Playwright installation, and this session made
no client-visible UI changes (no new gate kind, no new card affordance) that would need one; the
`?dev` monitor's content was verified directly from the rebuilt `diagnostics.json` instead. Flagged
honestly rather than claimed.

## Reconciliation session — D-17 stacking fix, docs split, edge-router offset fix, row/band geometry desync fix

## Reconciliation session — D-17 stacking fix, docs split, edge-router offset fix, row/band geometry desync fix

Opened after a report that a concurrent session had stood down mid-work, leaving the repo in an
unreconciled state. Ran single-threaded throughout, no sub-agents, per explicit instruction.

**D-17 unbounded-stacking bug found and fixed.** `pipeline.layout.compute_layout` used
`same_band_depth` directly as sub-column, stacking every member sharing a depth in ONE column via
an unbounded counter — the real corpus's worst cell stacked 37 unrelated technologies 37 rows
tall. `tests/test_layout.py` had a test asserting this as intended behaviour (a THIRD instance of
this project's "green suite proves self-consistency, not correctness" pattern, and the first one
that didn't just have narrow fixture coverage — it actively enshrined the bug as spec). Fixed:
depth now sets a MINIMUM sub-column; each depth is a slot of one or more sub-columns, wrapped at
`subgrid_width`. Canvas moved 18,750×30,152 → 30,840×9,736. Full writeup, including the
`subgrid_width` 4/6/8/12 trade-off survey the new width cost prompted (not changed, left for the
user to pick from), is D-17 in `spec/decisions.md` — read that before touching sub-column
assignment again.

**CLAUDE.md split.** It had grown to 210,756 chars (past the CLI's 150k warning), 83% of it an
append-only "Open items" session log. Moved verbatim (byte-identical, checked) to
`docs/BUILD-LOG.md` (179,453 chars now), reorganised by component rather than chronology.
CLAUDE.md is now 38,605 chars with a short, genuinely-open "Open items" list. HANDOFF.md
(112,951 chars) was judged NOT to have the same problem — it's a working document with a real
"Next prompt" section, not an append-only log — and was left structurally intact.

**Two count discrepancies from a prior session, reconciled:**
- Sirenalia's 14th member (`giga_tech_eawaf_psifusion`) is classified via a technology-key
  override on genuinely weaker evidence than the other 13 (no `potential` block at all to key
  on — pure file/event-chain co-location). The other 13 all have a direct flag/ID signal. This is
  why v2 shows 14 against v1's 13 — not a miscount, a deliberate (documented) extra inclusion.
- The "2,828 crossings / 606 edges" figure was never a different denominator from 989 — 606 is
  `affectedEdgeCount` (edges with ≥1 crossing), always checked against all 989. Re-measured after
  this session's own changes: 2,992 crossings / 725 of 989 edges affected.
- `client/src/{tokens,camera,lod}.ts` were never git-tracked (zero commit history) so "edited vs.
  recreated" can't be answered from git — but every documented justification (camera clamps, LOD
  thresholds, `EDGE_COLOR`/`HOVER_COLOR`) is present and matches the narrative; nothing lost.

**ACOT/AoT closure depth (Item 5): surveyed, not implemented, per instruction.** Depth-1-only
would break exactly 3 links, all ACOT→ACOT, confirmed to include the user's own named case
(`tech_dark_matter_power_core_ae`, "Alpha-class Enigmatic Power" → `tech_precursor_design`,
"Precursor Databank Analysis", both verified against real vendored localisation). A middle option
(render an out-of-closure prerequisite as a distinct stub/ghost node) is feasible but unbuilt.
User needs to pick between depth-1, the current full-transitive-closure rule, or a stub option.

**Edge router: two real fixes, not just verification.**
1. Fetched v1's real `js/render.js` directly — confirmed `_v1_style_waypoints` is a byte-for-byte
   port of v1's own `addEdge` (the "chamfer" IS what v1 itself calls "corners chamfered at 45°";
   there is no separate longer-diagonal path in v1's real source to port instead).
2. Found the real trough cause: v1's own formula has no per-edge offset at all, so edges sharing
   similar geometry drew literally overlapping traces (worst cluster: 54 edges sharing one exact
   `mid` x-value). Added a small deterministic offset (reusing the existing `_channel_offset`
   hash) — worst cluster drops to 10, total overlapping-edge count 868 → 685. Crossing count
   against unrelated cards is materially unaffected by this specific change (~2,992 either way) —
   it addresses visual overlap, not card-crossing, which are different concerns.

**A second, serious desync bug found and fixed while re-verifying: `client/src/main.ts` computed
row/band geometry (panel/tint/header positions) via its OWN reimplementation of
`pipeline/layout.py`'s formulas, which silently went stale the moment D-17's wrap-within-depth fix
changed those formulas server-side.** Row panels, tier tints, and cell labels were drawing at
completely wrong positions relative to where cards actually rendered (found via a headless
screenshot: a faction row's pattern nowhere near its own cards). Permanent fix, not a re-sync:
row/band geometry is now DERIVED from the real min/max node positions in the geometry side-file,
so client and server geometry can never drift apart again regardless of future formula changes.
Verified: `rowGeometry.y` for every row now matches its real card positions exactly (header-offset
apart); confirmed visually across all four required screenshot cases.

**Item 7 verification, real numbers, current dataset:**
- Tier badge vs. band: 0/892 non-repeatable nodes disagree (checked directly, not assumed).
- 88 repeatable technologies, all in the terminal band; none render a repeat-count badge yet
  (badges slice, still unbuilt).
- 28/980 cards render `Cost: 0` — real corpus zero-cost starting technologies, not a fallback
  (5 more have `cost: null` and render no cost line at all, per existing policy).
- 107/980 names render with an ellipsis; 6 distinct visible-text collisions (different
  technologies whose wrapped/clamped display text happens to coincide — not itself a bug, since
  full names differ and are available on hover/popup, but worth knowing).
- 0/980 cards fall back to a missing icon.
- The 7 long-span backward `potential-gate` edges are now locatable and traceable (confirmed by
  screenshot) — `tech_cosmogenesis_escort → tech_missiles_1` (bandSpan 5) is the longest.

**Verified**: full pytest (1,384 passed), `tsc --noEmit`, `vite build` all clean throughout. Real
dataset rebuilt twice (once after the D-17/offset fix, once after the row/band geometry fix); a
real headless-Chromium run against the final rebuild: zero console errors, zero failed requests,
all existing invariant checks (name bounds, chip/label overlap, edge endpoints, min stub) still
0 violations. Four required screenshots taken and reviewed: fit-to-viewport (row panels now
correctly span their full real extent), the D-17 in-line case (`tech_dark_matter_power_core_ae`
isolated, no overlap), the Sirenalia row (patterns now aligned with real cards, all 14 members
visible including the reclassified EAWAF technologies), and a multi-elbow/long-span-edge region.

**Not done this session, by explicit instruction**: Items 3 and 5 (`subgrid_width` value itself,
ACOT/AoT closure rule) are surveyed only, awaiting the user's decision. `docs/BUILD-LOG.md`'s
reorganisation moved content but did not rewrite or re-verify any individual historical claim
inside it beyond the byte-identical-move check.

**Next prompt should point at the badges slice** (guidance above, in the "Next prompt to paste
into Claude Code" section, is otherwise still accurate) — but MUST run `tools/build_dataset.py`
fresh first (D-15, gitignored dataset) and should re-run the headless verification script rather
than trust any number in this section as still current once new code lands.

## Reconciliation + D-17 extension + P-12.9 implementation session

## "Ring Segment / ascension-perk locking / gate-propagation" session

Nine-item prompt, driven by real user reports. Full detail lives in CLAUDE.md's own sections
("Ascension perks are gates ..." and "Gates") — this entry is the full historical record.

1. **`always = yes` never handled as a leaf** (`pipeline/availability.py`) — only `always = no` at
   a technology's own top level was handled (a DIFFERENT mechanism, `pipeline.rendering_scope`'s
   permanently-disabled exclusion). Fixed: `always` gets its own leaf branch. Real corpus: 1
   technology, `tech_ring_world`.
2. **Ascension-perk axis-locking** — CLAUDE.md's "ascension perks are gates, not profile facts"
   locked decision corrected to a distinction: WHICH perk is a choice (unchanged); WHETHER a perk
   is obtainable at all is a fact when the perk's own `potential` carries a genuine axis
   constraint. Automated via `pipeline.availability.set_perk_potentials` (registers every perk's
   own winning `potential`) plus a new `has_ascension_perk` leaf branch that only turns FALSE on a
   definite perk LOCKED result, never on UNCERTAIN. Real corpus: 21 perks cleanly axis-restricted,
   20 left gate-only (residual undecidable conditions), 1 real cross-perk cycle
   (`ap_defender_of_the_galaxy` <-> `_nomads`) broken by a recursion guard. A necessary
   `_combine_or` correction fell out of this (an EXCLUDED sibling must not let a real FALSE
   sibling force the whole OR closed) — `pipeline.edge_constraints` needed its OWN, deliberately
   different `_relaxed_leaf`/sensitivity mechanism preserved exactly, so it now swaps in a local
   `_legacy_combine_or` copy for its one check.
3. **Gate propagation down `prerequisite` edges** (`pipeline.dataset_emit.build_base_dataset`) —
   gates previously classified only on the DECLARING technology, never inherited. Fixed via a
   topological (Kahn's-algorithm) pass unioning each technology's own gates with every
   `prerequisite`-ancestor's gates, deduplicated by `(kind, refId)`, tagged
   `inherited`/`sourceTechnologyId` (two new `Gate` schema fields). Scoped to `prerequisite` edges
   only, deliberately not `potential-gate`. Fixes the user-reported QSO family and
   `giga_tech_repeatable_*_cap` "Management Protocols" gap.
4. **`on_enabled -> add_research_option` perk grants** (Item 4a) — `ap_galactic_wonders` grants
   `tech_ring_world`/`tech_dyson_sphere`/`tech_matter_decompressor` (all three structurally
   unreachable any other way); these 3 now carry a real direct `ascension_perk` gate
   (`pipeline.dataset_emit.ADD_RESEARCH_OPTION_PERK_GRANTS`), closing a previously-surveyed,
   never-implemented gap. `tech_mega_engineering` (also granted this way, but reachable normally
   too) deliberately excluded. `ap_gigastructural_constructs`'s larger grant set needed no new
   machinery (already gate-classified via its own direct `has_ascension_perk` leaf).
   **Cosmogenesis (Item 4b)**: surveyed, found real (`giga_tech_fe_megaworkshop_1`,
   `tech_cosmogenesis_thesis`) but `weight_modifier`-based (`factor = 0` unless
   `has_crisis_level`), not a `potential`/gate condition — deliberately NOT treated as a gate,
   matching the project's weight-vs-availability separation. The "tensile buildings"
   (`giga_tech_amb_supertensiles*`) the user also named do not share this shape; their only real
   gate is the already-known `@giga_amb_flag` mod-config toggle.
5. **`has_active_tradition` never handled** — resolves TRUE by default, FALSE only for the
   user-confirmed `tr_genetics*` category (unavailable to machine-intelligence empires). Real
   corpus: exactly 1 `potential`-scoped occurrence, `giga_tech_the_vat`. Its only other real
   occurrence (Maginot's `tr_unyielding_federations_finish`) lives in a `weight_modifier`, out of
   scope for availability regardless.
6. **Localisation/icon precedence** — a vanilla-won technology (P-15 block winner) now uses
   vanilla's OWN name/description/icon even when ACOT's loc/icon files happen to redefine the same
   key/filename with different content. Surveyed first: exactly 3 real cases across the full
   673-technology Vanilla-won set (`tech_dark_matter_power_core`/`_propulsion`/`_deflector`).
   `pipeline.icons.resolve.resolve_icon_files` gained a general `source_priority_overrides`
   parameter (not special-cased to these 3 keys). Confirmed independent of the ACOT-absent
   reduced-build diagnostic (`VANILLA_TECHNOLOGIES_ACOT_OVERWRITES`).
7. **Dangling "or:" gates** (Item 7a) — a technology whose entire `gates` list is one alternative
   entry reads as a dangling reference when its true OR-sibling isn't itself gate-shaped (Birch
   World's sibling is an `any_owned_planet` district check). Downgraded to a plain "Needs X" in
   that exact case, deliberately excluding the `appliesToEmpireTypes`-constrained shape (Riddle
   Escort/Missiles/Torpedoes, an existing different fix that must keep its "or:" wording). Real
   corpus: 20 technologies. **OR-set popup grouping (Item 7b): not implemented** — `groupId` only
   exists on `Edge`, not `Gate`; reported as a real gap, not attempted this session.
8. **Small fixes**: enlarged the repeatable-infinity glyph (dedicated 20px style for "∞" only,
   since the shared 10px badge style could only ever shrink it, never enlarge a naturally-small
   glyph); rewrote the off-tree-prerequisite popup note for an end user (no decision codes, full
   detail kept under `?dev`); confirmed the 5 null-cost technologies still render no cost line.
9. **Same-sub-column edges — surveyed, not implemented, per explicit instruction.** 6 real edges
   (all `alternative`/`potential-gate`, zero `prerequisite`) sit in the exact same x-column as
   their counterpart, same band; 2 are in the Compound row, matching the user's report. D-17's
   guarantee only ever covered `prerequisite` edges — recommended a per-cell depth-slot extension
   (not a global `subgrid_width` renegotiation), left for the user to confirm before touching
   canvas geometry again.

**D-10 figures moved**: unconditional uncertainty 34 -> 31 (Items 1, 2, 5 combined — 3 independent
technologies each individually verified); worst profile-dependent 15/973 (1.54%) -> 16/973
(1.64%), still comfortably under the 3% warn threshold. Gate counts: DIRECT 136 -> 139 instances
over 109 -> 112 technologies (purely Item 4a's 3 new grants); TOTAL (direct + inherited) 267
instances over 196 technologies, 48 of which carry more than one (up from 24 pre-propagation).

**Verification**: full `pytest tests/` (1496 passed after deliberately updating every pinned
D-10/gate-count regression test with its own reasoning — never silenced), `tsc --noEmit` and
`npm run build` both clean, real dataset rebuilt via `tools/build_dataset.py` (973 technologies,
977 edges, matches). **No headless-Chromium/Playwright screenshots this session** —
`npx playwright install chromium --with-deps` was attempted and timed out before completing in
this environment; the client changes (inherited-gate popup rendering, the enlarged infinity
glyph, the rewritten off-tree note) were verified by direct inspection of the rebuilt dataset JSON
and the TypeScript build only, not visually. Flagged honestly rather than claimed.

## Reconciliation + D-17 extension + P-12.9 implementation session

Five numbered items from the user, run single-threaded.

1. **Uncertain count reconciled**: not a regression — the prior session's pin update
   (`c45448e`) carried a full, named reason for each figure's move. Rebuilt dataset confirms the
   pin exactly (31/973 unconditional, 53 union, 16/973 worst profile-dependent, D-10 ratchet
   holds).
2. **Perk-perk cycle**: already correctly handled by the existing recursion guard
   (`_perk_eval_in_progress`), confirmed by tracing both perks' raw `potential` blocks directly.
   Zero rendered technologies reference either perk id, so the cycle has zero gate/availability
   effect either way.
3. **Visual verification**: Playwright installed cleanly this session (unlike the prior session's
   timeout). All nine required cases confirmed by real screenshot, zero console errors; one
   pre-existing documented gap observed (origin/ethics-or-civic gates render no icon), not new.
4. **D-17 same-sub-column extension implemented**: `_same_band_depth` now also takes
   `alternative`/`potential-gate` edges as an additional ordering constraint. Canvas 29,670 ×
   13,448px → 30,060 × 13,448px (+1.3%). New corpus test proven to fail first (24 violations)
   before trusted on the fix.
5. **P-12.9 implemented**: `researchPaths` replaces its placeholder shape with the spec's
   `{status, steps, totalCost, totalCostIsEstimate, estimateReasons, configGatedTarget}`. A real
   correction found while implementing: `totalCost` for `status == "path"` must include the
   target's own declared cost to reproduce the spec's own worked examples (74,750/73,750/76,250) —
   the schema's literal "sum of stepCost" text was imprecise. Two spec figures re-measured (OR
   tie-break 12/72 disagreements, nomadic total 76,250); a THIRD, more significant one corrected
   against this session's own inherited assumption rather than forced to match it: the "dangerous"
   ancestor-chain-broken sub-case is real and substantial on the current corpus (78 technologies /
   472 pairs), confirmed against raw source (`tech_ehof_spinal` → `tech_arkship_tier_3`, itself
   `is_nomadic = yes`-locked) — reported honestly per this project's "raw inspection only" rule,
   not suppressed. New `diagnostics.unresolvableResearchPaths` surfaces every case. Client popup
   wired up (`renderResearchPath`), verified with 5 real screenshots reproducing the exact
   corrected cost figures.

**Verification**: full `pytest tests/` (1507 passed, up from 1496), `tsc --noEmit` and
`vite build` both clean. Largest empire overlay (research paths added): 1.25MB raw / 63.5KB gzip,
comfortably inside the ≤2MB compressed budget. Real dataset rebuilt and headless-Chromium-verified
throughout — zero console errors across every screenshot in both the Item 3 and P-12.9 verification
passes.

## Gate-polarity/nested-OR/wilderness-icon fix session

Six items from a domain-authority user's bug report. Full detail in CLAUDE.md's "Gates"/"Open
items" sections; this entry is the full historical record.

1. **Gate-polarity bug (real class bug).** `pipeline.gate_patterns` tracked negation only via a
   `NOT`/`NOR` wrapper ancestor, never a leaf's own literal `= no` value (Clausewitz's other way
   to write negation). `_leaf_negated` XORs three channels (wrapper, `!=` operator, literal
   `= no`); a real bug in the FIRST implementation (Python's `a != b != c` chained comparison,
   not a 3-way XOR) was caught by direct testing before shipping. Real corpus: 31 technologies
   lose a wrong "Needs Wilderness" badge. `can_research_technology` (an eligibility fact, not
   `has_technology`'s "already completed") removed from gate classification entirely — 1 real
   occurrence, but gate propagation had inherited the mis-badge onto 15 descendants. Gate counts:
   DIRECT 139 → 107, TOTAL 267 → 214.
2. **Nano-Assembler/Polyatomic Crucible: surveyed, not a bug** — raw source confirms neither has
   an ascension-perk requirement in `potential`; the prior session's weight-based conclusion
   stands.
2b. **Nested AND-of-OR gates (real structural bug).** `GateMatch.group_id` (mirrors
   `Edge.groupId`) names the `OR`/`NOR` block a gate belongs to. Real corpus: 1 technology
   (`giga_tech_the_vat`) mixes unconditional and grouped matches; client now nests them correctly.
3. **Wilderness/origin/ethics icon fallback (real bug).** The degenerate 1x1-pixel stretched
   fallback read as a rendering error for these two gate kinds (fires 100% of the time, no icon
   source vendored). `Gate.icon` is now nullable; client renders label-only when null.
3b. **Wilderness as a fourth axis: surveyed, not implemented.** 41/973 technologies (4.2%) / 148
   (tech, profile) pairs show a real availability difference between wilderness and non-wilderness
   hive empires — not small. Reported with cost (24 profiles) for the user to decide.
4. **Two "Confluence of Thought" technologies: confirmed already-known.** Two deliberately
   parallel vanilla technology lines (hive/wilderness variants), already one of the 5 documented
   genuine same-name pairs.
5. **Looping edges: surveyed, none found.** Three geometric checks (X-reversal, Y-hook,
   self-intersection) found zero matching edges in the rebuilt dataset.
6. **Dangerous ancestor-broken case (P-12.9 section 6): surveyed, stopped per instruction.**
   Re-measured after Item 1: still 78/472, unchanged — not an artefact of the polarity bug.
   Categorised by cause (44 nomadic-locked, 25 perk-locked, 4 hive/shipset-locked, 2 zero-viable
   OR, 3 unresolved); every traced case is a real dead end. Recommended a distinct status value
   (naming the blocking ancestor) instead of `status: "unavailable"` for both causes — not
   implemented, spec-decision-changing, left for user review.

**Verification**: full pytest 1514 passed (up from 1507), `tsc --noEmit`/`vite build` clean.
Headless-Chromium: zero console errors across all screenshots, all invariant checks 0 violations.
D-10 figures unchanged (31/973 unconditional, 53 union, worst 16/973 = 1.64%) and canvas
dimensions unaffected, both confirmed directly since gate-display fixes never touch
`pipeline.availability` or layout.

## CLAUDE.md's former "Open items" list — full text as of the docs-restructure session

Moved verbatim; CLAUDE.md now keeps only genuinely open items, all closed/resolved entries below are superseded by the real code/decisions they describe (each already cross-referenced into the component sections above).

## Open items

Full build history — every decision, measured figure, and defect found in past sessions — moved
to `docs/BUILD-LOG.md` in a reconciliation session (CLAUDE.md had become an append-only session
log rather than a list of open items; see that file's own header note). This section states only
what is genuinely still open, with a pointer to detail elsewhere. Locked, load-bearing decisions
live in this file's own body above and in `spec/decisions.md`, not here.

- **Gate classification (P-3) is now closed** — `pipeline/gate_patterns.py` classifies real gate
  data into `gates`; see this file's own "Gates" section above for the full account. Left here
  only so a future session's memory of "this was still open" gets corrected on sight.
- **Wilderness as a fourth profile axis: surveyed (a later session), NOT implemented, real
  decision needed.** A prior survey rejected a fourth axis because wilderness (`has_origin =
  origin_wilderness`, hive-authority-only) is a strict subset of hive authority, not orthogonal to
  it. Re-measured directly this session (simulate wilderness=true/false against the real evaluator
  for all 4 hive-authority profiles): **41 of 973 rendered technologies (4.2%) / 148 (technology,
  profile) pairs show a REAL availability difference between a wilderness and a non-wilderness
  hive empire** — not small, comparable in scale to other thresholds this project treats
  seriously. The display-gate-only treatment (Item "Gate-polarity bug fixed" above) is now
  correct on its own terms, but doesn't surface these 41 technologies' real per-profile
  availability difference at all. Cost of adding the axis, if chosen: 12 → 24 profiles, every
  per-profile emitted array doubles (`empireProfileAxes`, `availabilityMatrix`, every overlay) —
  re-check the ≤2MB compressed overlay budget before committing (current largest overlay: 63.5KB
  gzip, so headroom is large, but re-measure once implemented, don't assume). User needs to
  decide between: (a) leave as a display-gate, tell users the ~4% figure and accept it as a known
  gap; (b) add the fourth axis.
- **Two technologies named "Confluence of Thought" — already a known, genuine same-name pair, not
  a new gap.** `tech_hive_confluence` (the ordinary hive-authority statecraft line,
  `tech_hive_cluster → tech_hive_confluence`) and `tech_wilderness_confluence` (a parallel,
  wilderness-exclusive vanilla content track, `tech_wilderness_node → tech_wilderness_cluster →
  tech_wilderness_confluence`, confirmed real via raw source's own "# Wilderness" section header)
  are two DIFFERENT, deliberately-parallel vanilla technology lines that happen to share a display
  name — already recorded among the reconciliation session's "5 genuine same-name-in-the-mod
  pairs" (`docs/BUILD-LOG.md`). Not an overwrite-resolution error or a localisation collision.
  Left here only so a future session's memory of "is this new?" gets corrected on sight.
- **Looping edges: surveyed this session, NONE FOUND geometrically — real corpus report is
  either stale (predates the same-sub-column D-17 extension) or needs a specific example.** Three
  independent geometric checks against the rebuilt, current dataset (X-direction reversal on any
  edge's polyline, a Y-axis "hook" shape — large deviation then returning near the start Y before
  a very different end Y, and literal polyline self-intersection) all found ZERO matching edges
  across all 977. The D-17 same-sub-column extension (this session, see "Item 4" in HANDOFF.md's
  own session record) already covers the one class of edge previously confirmed to double back.
  Recommend asking the user for a screenshot or a specific technology name before investigating
  further — this session could not reproduce the report.
- **The "dangerous" ancestor-broken research-path case (P-12.9 section 6): surveyed, real, NOT an
  artefact of the gate-polarity fix.** Re-measured after the gate-polarity fix landed: still
  exactly 78 technologies / 472 (key, profile) pairs — UNCHANGED, confirming the gate-display fix
  (which never touches `pipeline.availability`) has zero bearing on this count. Categorised by
  cause: 44 pairs trace to a broken ancestor's `is_nomadic`-locked state (the `tech_starbase_*`
  chain and similar), 25 to an axis-locked ascension perk (`ap_gigastructural_constructs` 10,
  `ap_galactic_wonders` 8, `ap_celestial_printing` 7), 4 to hive-mind/shipset-locked ancestors, 2
  to a zero-viable `OR`-group, 3 unresolved by this session's quick trace (deeper nesting, not yet
  characterised). Every traced case is a REAL, non-alternative (`prerequisite`, not
  `alternative`-edge) dead end — none found to be a modelling artefact (an ancestor that's
  "really" reachable another way the evaluator missed). **Recommendation: `status: "unavailable"`
  does NOT adequately distinguish "the target itself is closed to you" from "the target is fine,
  but a specific ancestor blocks the only path" — these are different facts a player would act on
  differently (a real hard no, vs. "you could get here if this one blocking ancestor were
  reachable").** A distinct status value naming the actual blocking ancestor + its own lock reason
  (already computable from this session's survey) is recommended; not implemented, per explicit
  instruction to stop and report — this changes a spec decision (P-12.9 section 6) and the user
  should see the shape before it moves.
- **Gate propagation down `potential-gate` edges is a real, deliberately deferred scope
  boundary** (the "Ring Segment / ascension-perk locking / gate-propagation" session) — this
  session propagated gates down `prerequisite` edges only (the formal, declared "must research
  first" chain). A `potential-gate` edge (`has_technology` inside `potential`) is a DIFFERENT kind
  of dependency (an eligibility check, not a declared prerequisite), and whether/how it should
  ALSO propagate gates was left open pending real corpus study of what that would even mean —
  don't extend propagation there without first surveying real cases.
- **Same-sub-column (same-band) `alternative`/`potential-gate` edges — now closed (a later
  session).** D-17's own invariant (`spec/decisions.md`) is extended: `pipeline.layout.
  _same_band_depth` now also takes `alternative`/`potential-gate` edges as an additional same-band
  ordering constraint (not folded into `prereqs_of`/`computed_position`, which stay
  prerequisite-only). Real corpus: canvas 29,670 × 13,448px → 30,060 × 13,448px (+390px, +1.3% —
  well under the ~10% stop-and-report threshold), densest cell/row population unaffected.
  `tests/test_layout_corpus.py::test_zero_same_sub_column_pairs_across_all_edge_kinds` asserts
  zero same-band `(from, to)` pairs across all three edge kinds, proven to fail first (24
  violations pre-extension) before being trusted on the fix. Left here only so a future session's
  memory of "this was still open" gets corrected on sight.
- **P-12.9 (research path): now implemented (a later session).** See this file's own "Research
  path" section above for the full account — the placeholder `{ancestors, shortestChain}` shape is
  replaced by the spec's `{status, steps, totalCost, totalCostIsEstimate, estimateReasons,
  configGatedTarget}` shape, wired into the client popup. All three previously-stale spec figures
  were re-measured against the current corpus in the same pass (OR tie-break 12/72 disagreements,
  nomadic `tech_mega_engineering` total 76,250), and a fourth, more significant correction was
  found and recorded honestly rather than forced to match the inherited assumption: the
  "dangerous" ancestor-chain-broken sub-case is NOT zero on the current corpus (78 technologies /
  472 pairs, `diagnostics.unresolvableResearchPaths`) — see the "Research path" section for the
  confirmed example. Left here only so a future session's memory of "this was still open" gets
  corrected on sight.
- **`appliesToEmpireTypes`/`activeEdgeIds` is now closed** (a later session) — `pipeline.
  edge_constraints` computes real per-edge empire-type constraints for `potential-gate` edges
  (`prerequisite`/`alternative` are structurally unconstrained by construction — their own
  `prerequisites` field is never trigger-evaluated). Uses an axis-fact-only definition of
  "active" — an edge is inactive for a profile only when an AXIS FACT rules it out, never when an
  unrelated unresolvable leaf merely masks it (a naive sensitivity-based definition was tried and
  rejected specifically because it wrongly reported `giga_tech_disco_moon`'s two real gate edges
  as never-active, an artifact of an unrelated always-unresolvable leaf, not a real fact about the
  mod — do not "simplify" back to sensitivity, that is a regression). Real corpus: 980 → 977 → 973
  rendered edges total (D-18, then Item 2c), 5 of which carry a genuine per-axis constraint;
  `activeEdgeIds` varies 973–976 across the 12 profiles. See `pipeline/edge_constraints.py`'s own
  module docstring for the full algorithm and rejected-alternative reasoning.
- **Tech-swap display substitution (`swapMappings`, D-14) is now closed** (a later session) —
  card name/icon substitute per the selected profile's `swapMappings` (123 real technologies: 116
  name-only, 7 also change area/category); the popup, prerequisite/dependent lists, and search
  results all display the profile-correct name (including for OTHER technologies looked up in
  those lists, not just the selected one). Search matches on any profile's name (the search index
  pools all axis-expressible swap alternate names, unconditionally) but always displays the
  profile-correct one.
- **The popup's Prerequisites/Dependents pooling-all-edge-kinds bug is now closed** (a later
  session) — the lists are `kind`-labelled and `activeEdgeIds`-filtered: `prerequisite` shows as a
  required list, `alternative` groups each render as their own "need one of" choice (filtered to
  non-`locked` members for the selected profile via the already-emitted `availabilityMatrix`, per
  the exact mechanism this bullet used to describe as future work), and `potential-gate` is
  excluded entirely from both lists (already shown via the card's own Gates section — showing it
  twice would be the exact duplication Item 5 above separately closed for the CARD gate badge).
  `tech_mega_engineering`'s popup now correctly shows 1 required prerequisite plus two distinct
  1-member "need one of" groups for regular/mechanical/non-nomadic, matching the real
  availability-filtered set exactly.
- **`subgrid_width` is settled at 6** — the user's pick from D-17's 4/6/8/12 trade-off survey
  (`spec/decisions.md`). Not open any more; left here only so a future session's memory of "this
  was still open" gets corrected on sight.
- **The `EmpireProfileIndex` parallel-formula gap (this file's own "pipeline owns all geometry"
  rule, generalised beyond geometry) is now closed** — the base dataset emits `empireProfileAxes`
  (axis order, values, strides, `totalProfileCount`; `schema/common.schema.json`'s
  `EmpireProfileAxes`, built by `pipeline.dataset_schema.empire_profile.
  build_empire_profile_axes`), and `client/src/empireProfile.ts` derives its index purely from
  that emitted data — no hardcoded stride or axis list survives client-side. Left here only so a
  future session's memory of "this was still open" gets corrected on sight.
- **The D-18 off-tree-prerequisite gap is now closed.** `pipeline.rendering_scope.
  compute_off_tree_prerequisites`'s 3 accepted links now surface in each affected technology's own
  detail payload (`offTreePrerequisiteNames`) and render in the popup under "Also requires," with
  a fixed client-side note that the name is outside the rendered scope — see
  `spec/P-16-mod-requirements.md`'s acceptance criteria, no longer flagged as a gap there.
- **`repositoryLink` isn't live-validated** (no network access at build time) and its `lineRange`
  uses the block's start line for both ends (the AST doesn't track an end-of-block line).
- **Middle-click isolation (P-7) is fully specced (`spec/P-07-isolation.md`) and entirely
  unbuilt** — confirmed on request, screenshot-review session (a user tried middle-click and got
  ordinary left-click selection behaviour instead, since no session has ever implemented it).
  Spec requirement, in full: middle-click (or long-press ≥400ms on touch, P-9) isolates a node
  together with its direct prerequisites/unlocks (user-adjustable depth, default 1 hop, with a
  full-closure option), traversing **all three edge kinds** distinctly styled per P-8 — this
  deliberately differs from the research path (P-12.9), which is prerequisite-edges-only.
  Dimming/hiding is a visibility mask over the static layout (never a re-layout, P-4's precedent),
  exitable via a labelled control and `Escape`, with persistent on-screen state naming the
  isolated technology. Adjacency lists (forward/reverse, per edge kind) must be precomputed in the
  dataset so traversal is O(1) per node, never a full edge-set scan, to stay inside P-10's 100ms
  interaction budget. Not started this session — left here as a real, scoped, ready-to-build
  feature, not a vague future idea.
- **No pipeline-test CI workflow exists** — `pytest` still runs manually/locally only.
- **`tools/collect_vanilla.py`'s GitHub-fetch-and-pin automation for Gigastructures, plus a
  scheduled CI staleness check, is still unbuilt** — see this file's "Source data" section above
  for the full context; the current manual pin is a deliberate stopgap, not a placeholder waiting
  passively to be replaced.
- **Pattern tile for Blokkats** needs tracing to clean SVG from the supplied flag image — the
  current herringbone motif is a procedural placeholder, not traced art.
- **Sirenalia's accent shade and Katzenartig Imperium's chevron pattern are both flagged
  provisional** in `client/src/tokens.ts`'s own comments — Sirenalia's real geometry (curved wave
  bands) was ported from v1, but its exact accent colour is still a placeholder; Katzenartig has no
  in-game reference at all and its pattern is Claude's own inference, not described art.
- **`potential-gate` edges' long-span (up to 5-band) backward routing** was left `TODO(Stage 3)`
  when P-8 was written, before a real rendered canvas existed to design against — re-check whether
  the v1-style router + gutter-router fallback (see `docs/BUILD-LOG.md`'s rendering section) has
  since made this moot before treating it as still open.
- **ΔE2000/WCAG mechanical colour checks are still unbuilt** — S-1's own CI-enforced acceptance
  criterion (pairwise contrast across the full token set, including the new `RARE_COLOR`/
  `DANGEROUS_COLOR` badges-slice additions). Every colour token is a first concrete pick, checked
  by eye only.
- **A real, previously-open gap, now closed**: the ACOT/AoT closure rule (depth vs. full
  transitive closure) was surveyed, decided (depth-1), and implemented as D-18
  (`spec/decisions.md`) — no longer open. Left here as a pointer only in case a future session's
  memory of "this was still open" needs correcting.
- **Dev-only `?dev` uncertainty health monitor: now built (a later session).** Lists every
  rendered technology with ≥1 `uncertain` profile, grouped by `ReasonCategory`, with per-profile
  `describe_condition()` reason text and click-through to the node. Data lives in diagnostics'
  new `uncertainTechnologies` field (`pipeline.dataset_emit.build_diagnostics`); fetched
  client-side only when `?dev` is present (`client/src/dataset.ts`'s `fetchDiagnostics`),
  matching S-2's existing "lazy, dev-only, never affects P-10 budgets when unused" contract.
- **Ascension-perk `on_enabled → add_research_option` grants: surveyed (a later session), NOT
  implemented.** `common/ascension_perks/` is already vendored (Vanilla/Gigastructures/ACOT; AoT
  has none) but no pipeline module has ever read a perk's own effect blocks — only icon-file
  lookup touches that directory today. Real finding: `tech_dyson_sphere`'s `potential` is only
  `{ is_nomadic = no }` and its `weight_modifier` is an unconditional `factor = 0` — it is
  structurally impossible to research via the normal weighted draw; `ap_galactic_wonders`'
  (Gigastructures-overwritten) `on_enabled → add_research_option` is the ONLY real unlock path,
  entirely invisible to this pipeline's existing gate/availability machinery. 3 technologies
  (`tech_ring_world`, `tech_dyson_sphere`, `tech_matter_decompressor`) share this exact
  unconditional-zero-weight shape; several more (`tech_mega_engineering`, `tech_habitat_2/3`, two
  storm techs, 3 Gigastructures megastructure techs) are ALSO granted this way but remain
  genuinely reachable by the ordinary prerequisite/weighted-draw route too, so they don't need
  the same treatment. Recommendation: extend P-3's existing gate machinery (a perk-gates-access
  pattern is exactly what a gate badge means) rather than invent a new display concept — see
  `docs/BUILD-LOG.md` for the full corpus table and reasoning before implementing.
- **Hover vs. selection scope: clarified (a later session), not a gap.** No `spec/` file defines
  either. The current implementation already has the split a user asked for (hover = immediate
  neighbours only; selection = full ancestor/dependent closure via `computeAncestryAndDependents`)
  — it was simply not discoverable, since nothing in the UI hints that selecting reveals more
  than hovering does. Not changed; a discoverability affordance (e.g. a status-bar hint) is a
  scoped, easy follow-up if wanted, not yet built.

## `pipeline/availability.py` — full trigger-evaluation narrative (superseded condensed version now in CLAUDE.md's "Trigger evaluation" section)

Moved verbatim from CLAUDE.md during the docs-restructure session; every intermediate D-10 figure, every leaf-resolution defect and fix, in the order they were found.

### Trigger evaluation

Partial evaluation against empire profile facts (`pipeline/availability.py`). Every condition
resolves to `true`, `false`, or `unknown` (three-valued, Kleene-style short-circuiting through
`AND`/`OR`/`NOT`/`NOR`). `unknown` propagates. Never assume `unknown` means available or
unavailable. Output is always `(technology, empire profile) -> {state, reason}` with `state` in
`{available, locked, uncertain}` — never a boolean (D-10/P-13).

**D-10 splits into two distinct metrics, both computed over RENDERED nodes (P-16's closure —
973 at last count, D-18's depth-1 ACOT/AoT closure down from 980, then Item 2c's always-no
exclusion down from 977), not the full 1,879 canonical technologies** — see `spec/decisions.md`'s
D-10 for the full reasoning; summarised:

- **Profile-dependent uncertainty** — a technology whose state varies by profile (some profiles
  short-circuit to a definite answer, others stay stuck). This is what the thresholds below
  govern, per profile, worst-case:
  - Hard ceiling: 10% for any single profile. Above that, the build fails.
  - Warn threshold: 3%, per profile.
  - Ratchet: CI fails if any individual profile's rate rises against that same profile's figure
    in the previous dataset, even under 10%.
- **Unconditional uncertainty** — a technology `uncertain` under all twelve profiles identically
  (no axis check anywhere in its trigger structure). Never misleads a user about their specific
  empire — it's the same honest "unknown" for everyone, reporting a fact outside the axis model
  (crisis-chain/story progression, mid-game player state). Published as its own
  data-completeness figure with its own regression ratchet, but **NOT subject to the 10%
  ceiling** — a different quality signal, not a weaker version of the same one.

The two denominators (all-1,879-canonical vs. rendered-973) give materially different, and
oppositely-signed, answers: rendered-only uncertainty is *higher* than all-canonical, because
Gigastructures' own content — not unrendered ACOT/AoT bulk — is the concentration point. Narrowing
ACOT/AoT rendering scope does not fix a ceiling breach. Always state which denominator a reported
rate uses. **Real corpus (current, both moves from the "path to zero uncertain" follow-up session):
worst profile-dependent 34/973 (3.49%, back OVER the 3% warn threshold — was 33/977, 3.37%, over
it, then 28/973, 2.88%, then 27/973, 2.77%, under it); unconditional 176/973 (was 209/977, then
205/973, then 183/973).** The `has_ancrel` fix (below) improved both figures together, same as
every earlier rule; the scripted-trigger expansion module (also below) improved unconditional
uncertainty further but, in the SAME move, pushed the worst profile-dependent rate back over the
3% line — a considered, reported tradeoff, not a regression to hide: see that module's own
paragraph for why. See the "Availability evaluator" bullet in Open Items/BUILD-LOG for the full
before/after category breakdown.

**Unconditional figure moved again, a later session ("commit + close the loop" follow-up, Item 2):
176 → 107 (already recorded below at "Gates") → 34/973 (3.49%), while worst profile-dependent
stayed exactly 15/973 (1.54%), unmoved.** `pipeline.trigger_text.looks_like_story_progress`'s
naming pattern (crisis-faction fragments; `_possible`/`_solved`/`_unlocked`/`_happened`/`_complete`/
`_aborted`/`_knowledge`/`_opened` suffixes; `encountered_`/`completed_` prefixes) — previously used
only for DISPLAY categorisation — now also RESOLVES matching `has_country_flag`/`has_global_flag`
names TRUE as a class, the same treatment already user-approved for `colossus_project`
(`pipeline.availability.PROGRESSION_FLAGS_TRUE`). Every sampled real setting site is a genuine
`is_triggered_only` country event with no empire-type restriction. Real corpus: 64 distinct flag
names, 73 technologies move UNCONDITIONALLY uncertain → AVAILABLE for all 12 profiles; none became
merely profile-dependent, which is why the worst profile-dependent rate is unchanged. Union
uncertain-for-≥1-profile count: 127 → 54.

**Both figures moved again, a later session ("Ring Segment / ascension-perk locking /
gate-propagation" session, Items 1, 2 and 5): unconditional 34 → 31, worst profile-dependent
15/973 (1.54%) → 16/973 (1.64%), union 54 → 53.** Three real, independent leaf-handling gaps, each
never handled at all before this session (falling through to UNKNOWN unconditionally):
- **`always`** — the most trivially resolvable leaf in Clausewitz was never given a leaf-evaluation
  branch at all (only `always = no` at a technology's own top level was handled, via
  `pipeline.rendering_scope`'s DIFFERENT permanently-disabled-exclusion mechanism). Real corpus: 1
  technology, `tech_ring_world` (whole `potential` is `{ always = yes }`), moves from uncertain for
  all 12 profiles to AVAILABLE for all 12.
- **Ascension-perk axis-locking** (this file's own "Ascension perks are gates" section above) — one
  further technology's OR combination resolves cleanly once an axis-locked perk can contribute a
  real FALSE.
- **`has_active_tradition`** — also never handled, resolves TRUE by default except for the one
  user-confirmed restricted category (`tr_genetics*`, unavailable to machine-intelligence empires).
  Real corpus: exactly ONE `potential`-scoped occurrence in the whole corpus, `giga_tech_the_vat`'s
  `has_active_tradition = tr_genetics_finish_extra_traits` (its only OTHER real occurrence,
  Maginot's `tr_unyielding_federations_finish`, lives in a `weight_modifier`, not `potential`, so is
  out of scope for availability regardless — weight and availability are deliberately separate
  concerns, conflating them would be a category error). `giga_tech_the_vat` moves to AVAILABLE for
  all 12 profiles.

Two more real fixes in the SAME session touch DISPLAY, not availability, and moved no D-10 figure:
gate propagation down `prerequisite` chains and `add_research_option` perk-grants (both under
"Gates" below), and the dangling-alternative-gate downgrade (P-3, also under "Gates").

Two real cases where mods overwrite VANILLA content: **localisation/icon precedence** (a
DIFFERENT, previously undiscovered concern from any technology-BLOCK overwrite) — surveyed the
full 673-technology Vanilla-won set and found exactly 3 real cases where ACOT's own loc/icon
files, though never overwriting the technology BLOCK itself, redefine the SAME name/description
loc key and icon filename with DIFFERENT content: `tech_dark_matter_power_core`,
`tech_dark_matter_propulsion`, `tech_dark_matter_deflector` (user-reported: the last one rendered
as ACOT's "Dark Matter Dimensional Thruster" instead of vanilla's own "Dark Matter Propulsion").
Fixed: `pipeline.dataset_emit.VANILLA_LOC_AND_ICON_PRECEDENCE_KEYS` looks these 3 keys up against
Vanilla's OWN loc entries (`_vanilla_loc_entry`) and forces the technology ICON atlas to keep
Vanilla's own file (`pipeline.icons.resolve.resolve_icon_files`'s new `source_priority_overrides`
parameter — a general, reusable mechanism, not special-cased to these 3 keys) rather than the
cross-source last-source-wins pick. Independent of, and does not conflict with, the ACOT-absent
reduced-build diagnostic (`VANILLA_TECHNOLOGIES_ACOT_OVERWRITES`/
`PLACEHOLDER_TECHNOLOGIES_REQUIRING_ACOT_AOT`) — that diagnostic is about a technology BLOCK
reverting when ACOT is absent; this fix is about which SOURCE's loc/icon a Vanilla-BLOCK-won
technology shows in the FULL (ACOT-present) build, and is a full no-op when ACOT is absent (no
ACOT file exists to compete with vanilla's in that build mode anyway).

Two real pattern matches are DELIBERATELY EXCLUDED (`pipeline.availability.
PROGRESSION_PATTERN_EXCLUDED_FLAGS`) despite matching the naming pattern: `l_cluster_opened` and
`encountered_first_lgate` are VANILLA Stellaris L-Gate storyline flags whose setting sites live in
vanilla's `events`/`decisions`, which this project does not vendor — resolving them would rest on
outside-corpus knowledge, not evidence, unlike every Gigastructures match. Six outliers the survey
found NOT matching the pattern, reported but not resolved: `can_build_star_eaters`,
`acot_databank_sophia_agreed`, `advanced_identity_creation`, `has_arcane_generator`,
`has_quantum_catapult_insight`, `has_encountered_psionic_auras`, plus two more of the same
non-matching shape found this session: `finish_shroud_forged_liberation_flag`,
`machine_subspecies`. **The corpus-wide uncertain count is now a pinned, structural test invariant**
(`tests/test_availability_corpus.py::test_uncertain_count_and_per_profile_breakdown_pinned`,
Item 1 of the same session) — pins both the union count and the full per-profile breakdown, proven
capable of failing by temporarily reintroducing the historical `country_uses_bio_ships` collision
(union count jumped 127 → 213 before the reintroduction was reverted).

**Founder-species/authority axis gaps (Item 3 of the same session): already closed by prior work,
not a new gap.** `founder_species = { is_archetype = MACHINE }` never appears directly in any
rendered technology's `potential` — the only real corpus wrapper containing it, vanilla's
`is_individual_machine`, was already added to `EXCLUDED_KEYS` AND to
`pipeline.gate_patterns.NOT_GATE_CLASSIFIED_EXCLUDED_KEYS` by a prior session's Item 3 (ethics/
civic/origin display gates) — 21 rendered technologies reference it, all already resolve
AVAILABLE with no gate badge, never UNCERTAIN. Same story for `has_authority = auth_corporate`
via `is_megacorp` (2 technologies, `tech_executive_retreat`/`tech_xeno_tourism_agency`) — already
excluded from availability and deliberately not gate-badged for the exact reason this session's
Item 3b would have recommended (MegaCorp is a real 4th authority value outside the 3-axis model;
adding it as an axis would double `EmpireProfileAxes`' cardinality — 12 → 24 profiles, doubling
every per-profile emitted array — for 2 technologies, not worth it against the display-gate
alternative already in place).

**`@giga_amb_flag` config-toggle pattern (Item 4 of the same session): investigated, NOT applied
— reported instead, differs from `_capped_r` in a way that matters.** `vendor/mods/gigastructures/
common/scripted_variables/giga_amb_variables.txt:5`'s own comment (`@giga_amb_flag =
giga_buildcap_j # menu option variable name, checked for feature activation`) confirms the
MECHANISM matches `_capped_r` (a Gigastructures options-menu toggle, `has_global_flag`-checked) —
but unlike `_capped_r`, which the user explicitly confirmed defaults unset in every core preset,
there is no equivalent confirmation for `giga_buildcap_j`'s default state, and the flag name
carries no self-describing suffix (`_forbidden`/`_disabled`/`_OFF`) the way the general convention
does. A second, purely mechanical gap: the value is a `VariableReference` (`@giga_amb_flag`), and
`pipeline.availability._flag_value_name` only resolves `Identifier`/`StringLiteral` today — even
with a confirmed default, resolving it would need `evaluate_trigger_block`'s variable_table
threaded through, not done here. Real corpus: 10 technologies (not 7 — the earlier scoping only
counted `giga_17_alternative_mega_build.txt`'s obvious cases; `giga_tech_fe_megaworkshop_1/2` and
`giga_tech_orbital_ring_supertensiles_mine_hub` also reference it). Left unresolved pending user
confirmation — see the same session's report.

**`has_ancrel` fix (a later session, "path to zero uncertain" Item 1) — the FIFTH instance of this
project's recurring defect class**: `pipeline/trigger_text.py` carried a comment asserting
`has_ancrel` was "not a scripted_trigger definition anywhere in the vendored corpus" and was a
Gigastructures relic/precursor-questline flag, classified `CRISIS_OR_STORY_PROGRESS`. That claim
was never checked against raw source and was wrong: the real definition is `vendor/stellaris/
common/scripted_triggers/00_scripted_triggers.txt:2678`, `has_ancrel = { host_has_dlc =
"Ancient Relics Story Pack" }` — a literal DLC-ownership check, already covered by assumption 2
below. Fixed by adding `has_ancrel` to `pipeline.availability.GROUND_FACT_BOOL` (the same
DLC-ownership rule as every other named wrapper) rather than to `trigger_text`'s category table,
since it is no longer ever UNCERTAIN. Real corpus: 22 technologies (the `tech_archaeo_*` family)
move UNCERTAIN → AVAILABLE, 1 (`tech_archeology_lab`, `has_ancrel = no`) moves UNCERTAIN → LOCKED.
**What makes this the fifth instance, and distinct from the first four** (`is_repeatable`'s
`levels < 0`, `_resolve_loc_tokens`' sibling-token bug, Compound's "confirmed real zero," the
EAWAF flag-family dismissal — see `docs/BUILD-LOG.md`'s defect-class paragraph): those four were
each a wrong answer *computed* by code reading the wrong signal. This one was a wrong answer
*written down as a documented finding* — a claim in a code comment, cited and trusted by every
later session's understanding of the corpus, that nobody re-verified against raw text until this
session. The lesson isn't new (this project's own "raw inspection only" rule already exists for
exactly this reason), but the FAILURE MODE is new: a documented claim is not self-verifying just
because it's written down with confidence and a specific-sounding citation (`giga_relics.txt`'s
`ancrel.NNNN` event-id namespace was real, but didn't support the conclusion drawn from it).

**Recursive scripted-trigger expansion (same "path to zero uncertain" session, Item 2) —
`pipeline/scripted_triggers.py`.** A technology's `potential` block can reference a scripted
trigger by bare identifier leaf (`giga_can_use_habitables = yes`); before this module, any name
the evaluator didn't specifically recognise was permanently `unknown`, even when the trigger's own
real body was itself made of leaves the evaluator COULD resolve (axis facts, DLC ground facts).
This module substitutes a trigger's real body in place of its name, recursively, then hands the
rewritten block to `pipeline.availability`'s UNCHANGED Kleene evaluator — never a second evaluator,
never new boolean semantics. Wired into `pipeline.dataset_emit.BuildContext.expanded_potentials`,
computed once and reused by every availability call site in that module (matching the "pipeline
owns all geometry" discipline, applied here to trigger content).

Not `pipeline.inline_scripts` and not reusable as it stands — confirmed by survey before
implementation: a scripted-trigger call is a bare identifier leaf, already an ordinary AST node
once parsed, not the parameterised text substitution `inline_script` exists for. Real corpus:
3,463 distinct trigger names after overwrite resolution (135 redefined by a later source), zero
reference cycles, max observed reference-chain depth 8 — `MAX_EXPANSION_DEPTH` is set to 12 as a
sanity ceiling, a hard failure if ever hit, never a silent truncation. One file
(`zzz_overwrites.txt`'s `has_research_building`) can't be fully `inline_script`-expanded (a
dynamic `@[...]` file-path computation this module doesn't attempt to fix); the catalog loader
falls back to that one file's raw parse rather than losing every other definition it carries
(notably `has_galactic_wonders`, defined later in the same file) — zero real-corpus effect, since
no rendered technology references `has_research_building`.

**`is_ai = yes` branches are stripped, not modelled** — generalising the two previously-hardcoded
wrapper mappings' own treatment (`pipeline.gate_patterns.WRAPPER_TO_PERK`, which stays, see that
module's own docstring for why general expansion doesn't make it redundant). Getting this right
took three real, corpus-verified iterations, each caught by re-running the corpus survey after
writing the previous version, not by design review — worth recording as its own instance of "a
green test suite proved the mechanism self-consistent, not correct" until the corpus check itself
caught it:
1. A naive "does this subtree contain `is_ai` anywhere" check dropped whole sibling branches that
   merely happened to share an ancestor with an `is_ai` leaf several levels down — a 110-technology
   regression from a SEPARATE bug (below) made this one hard to see at first.
2. **The real regression, found first and the more serious of the two**: `country_uses_bio_ships`
   — already specially resolved by `pipeline.availability.AXIS_FACTS` as the shipset axis fact —
   is ALSO a real scripted-trigger name whose own body opens with `exists = this` (a scope-
   existence tautology-shaped leaf the evaluator's leaf model has no notion of). Expanding it blind
   to what the evaluator already resolves destroyed the axis-fact shortcut for every one of its
   ~238 real occurrences, a 110-technology regression (215 → 320 uncertain) only caught by
   re-running the corpus survey, not by design review. Fixed: any leaf key already in
   `AXIS_FACTS`/`GROUND_FACT_BOOL`/`DLC_NAME_CHECK_KEYS` is now skipped by expansion unconditionally
   — those tables keep resolving it exactly as before.
3. Once (2) was fixed, `has_galactic_wonders`'s real is_ai branch turned out to be wrapped in
   `hidden_trigger = { and = { is_ai = yes, ... } } }`, not a bare `AND` — a real Stellaris wrapper
   that only suppresses a tooltip, never changes truth value, but which `pipeline.availability`
   doesn't recognise as a boolean wrapper either. Left unexpanded, it became one opaque,
   permanently-`unknown` leaf of its own — an 11-technology regression (every real
   `has_galactic_wonders`-gated technology). Fixed: `hidden_trigger` is recognised as droppable
   specifically when ALL of its own direct children are themselves is_ai-gated, recursively —
   never for a `hidden_trigger` wrapping anything else, which stays untouched rather than guessed
   at. Verified: zero residual `is_ai` leaves anywhere in the expanded 973-node rendered corpus
   (`tests/test_scripted_triggers_corpus.py::test_zero_residual_is_ai_leaves_after_expansion`).

**Real measured effect on its own** (this session's actual corpus run, not the prior survey's
estimate — the survey's own 238→215/23-resolved figure turned out to be ENTIRELY the has_ancrel
fix, confirmed by rerunning with has_ancrel already fixed separately): starting from Item 1's
already-fixed 215-uncertain baseline, general expansion leaves the "≥1 uncertain profile" COUNT
unchanged (215 → 215 — the remaining target triggers only ever produce PARTIAL improvement, fewer
uncertain profiles per technology, never a full resolution to zero), but the D-10 split tells the
real story: unconditional uncertainty improves (183 → 176, 7 technologies moved from "uncertain for
every profile identically" to "uncertain only for the profiles that could actually have it" — e.g.
`is_wilderness_empire`'s hive-authority-only origin now correctly short-circuits to LOCKED for the
8 non-hive profiles via the authority axis alone, leaving only the 4 hive-mind profiles genuinely
uncertain on the real, unresolvable origin question), while the worst profile-dependent rate rises
(2.77% → 3.49%, crossing back over the 3% warn threshold) — the SAME 7 technologies (and others)
moving from the unconditional bucket into the profile-dependent one, which the 3%/10% thresholds
specifically govern. More informative output, worse against this one metric — reported honestly,
not smoothed over. See `tests/test_dataset_emit.py::
test_gate_classification_leaves_d10_uncertainty_unchanged` for the full writeup and
`tests/test_scripted_triggers_corpus.py` for the corpus-wide cycle/depth/is_ai regression guards.

Expansion also surfaces leaf shapes the evaluator has never seen and deliberately leaves
unresolved (no invented handling, per this session's own scope): `has_authority` (24 tech×profile
occurrences), `founder_species` (44), `has_civic` — distinct from `has_valid_civic` (28), and
`if = { limit = {...} }` conditional-effect blocks (48). These are real residue, not bugs; see the
"path to zero uncertain" survey's own item 3/6 for which are further resolvable and which are
genuinely unknowable.

**Documented evaluator assumptions**, applied before anything counts as uncertain (each
individually verified against the vendored corpus, not a blanket "assume everything works" —
see `pipeline/availability.py`'s module docstring and `spec/decisions.md`'s D-10 for the full
detail and the specific names each covers):

1. Mod-config content-toggle global flags (`has_global_flag` names ending `_forbidden`,
   `_disabled`, or `_OFF`) resolve to their unset default — content not forbidden. Flags outside
   that pattern (`compound_invasion_happened`, `l_cluster_opened`, ...) are real undecidable state
   and stay unresolved.
2. All official DLC assumed owned — covers a literal `has_dlc`/`host_has_dlc` leaf and a dozen
   named per-DLC scripted-trigger wrappers individually confirmed to be pure `host_has_dlc`
   calls, plus `has_megacorp` (a later session — the DLC-ownership check, NOT `is_megacorp`, a
   real empire-type/civic CHOICE fact outside this project's 3-axis model, deliberately left
   unresolved; conflating the two would wrongly claim every profile IS a megacorp). Two
   similarly-named triggers (`has_gigastructural_constructs`, `has_galactic_wonders`) were checked
   and found to be ascension-perk-gate checks in disguise, not DLC checks, and are deliberately
   left unresolved.
3. Not-a-fallen-empire is a ground fact of all twelve profiles (`is_fallen_empire`,
   `merg_is_fallen_empire` always resolve `no`).
4. **Mod-content-presence flags (a later session) — `has_acot` and `has_global_flag =
   has_aot_mod`, both resolve `true`.** Distinct reasoning from assumption 2 (DLC ownership):
   this deployed tree already assumes ACOT/AoT content is present (the whole reason they're
   vendored), so a technology gated on "does this mod's content exist" is not genuinely uncertain
   about that question — the pipeline already knows. `pipeline.dataset_emit.
   _potential_mod_requirements` separately adds the ACOT/AoT `requiresMods` card badge these
   technologies need (Gigastructures' own "supertensile alternate" pattern,
   `giga_17_alternative_mega_build.txt`) — availability resolution and mod-requirement display are
   two different mechanisms even though both key off the same leaf. Real corpus: 4 technologies
   (`giga_tech_amb_supertensiles_acot_alpha/sigma/delta/phanon`).
5. **User-confirmed progression-state flags (a later session, one at a time, never blanket-
   resolved from a naming pattern) — `has_country_flag`/`has_global_flag` names that gate
   Gigastructures-internal PROGRESSION state, distinct from a genuine per-empire-type ELIGIBILITY
   gate.** Only `colossus_project` is confirmed so far (`has_country_flag = colossus_project`, set
   by the Colossus Project ascension perk once built, accessible to every empire type — real
   corpus: 6 technologies, `tech_pk_cracker`/`_godray`/`_nanobots`/`_neutron`/`_shielder`/
   `_smelter`). A larger candidate list (`giga_rings_beh`/`_gar`/`_tit`, `has_arcane_generator`,
   `has_finished_psionic_tradition`, `has_quantum_catapult_insight`, others) was surveyed and
   presented for confirmation but NOT resolved — see `docs/BUILD-LOG.md` for the full candidate
   list. This is the ONE evaluator resolution category that is inherently per-flag, never a
   pattern rule — see `pipeline.availability.PROGRESSION_FLAGS_TRUE`'s own comment before adding
   an entry.

`has_technology` (P-14 prerequisite-graph reachability), `has_ascension_perk` (a P-3 gate,
D-6/P-1), and `has_gigastructural_constructs`/`has_galactic_wonders` (Gigastructures' own custom
scripted_triggers, individually inspected and confirmed to be pure `OR`-of-`has_ascension_perk`
chains — ascension-perk gates wearing a different name) are excluded from boolean combination
entirely — an identity element, not resolved either way — because all four are a different
mechanism's job; folding any into `uncertain` would be a category error. `has_nemesis` and
`has_infernals` were added to the DLC-owned assumption's named-wrapper list after the same kind
of individual verification (both are bare `host_has_dlc` calls).

`common/scripted_triggers/` is the single biggest lever on the unconditional figure: this
evaluator does not inline arbitrary custom scripted-trigger call bodies (a materially larger
feature than what's built), so any technology gated behind one falls to `uncertain` regardless of
what that trigger actually checks. `has_country_flag` (131 corpus occurrences, 82 distinct names)
is confirmed to have no single resolvable pattern and is left fully unresolved.

## `pipeline/gate_patterns.py` — full gates narrative (superseded condensed version now in CLAUDE.md's "Gates" section)

Moved verbatim from CLAUDE.md during the docs-restructure session.

### Gates

**Built (gate-classification session).** `pipeline/gate_patterns.py` classifies four registered
trigger patterns into the schema's `Gate` shape, layered on top of P-14's universal
`potential-gate` edge extraction — never removing or altering an edge, only adding a badge.
Real corpus counts (raw classification, `pipeline.gate_patterns`, UNCHANGED by the display-layer
exclusion below): `has_ascension_perk` (22 technologies), `has_technology` (22 technologies,
25 instances — one-to-one with the 25 `potential-gate` edges), `has_gigastructural_constructs`
(9), `has_galactic_wonders` (14) — 70 gate instances total over 60 technologies, 10 of which
carry more than one instance (7 crossing two distinct mechanism types, 3 more carrying two
`has_technology` targets each).

**Item 5 (later session): the CARD/POPUP display now excludes a "technology"-kind gate whose
target is ALSO a true prerequisite of the same technology** — CLAUDE.md's own documented "4 real
pairs are both a formal prerequisite and a `potential-gate`" (see "Prerequisites" below) are not
real GATES in the P-3 sense, they redundantly encode the same dependency twice, and showing
"Needs X" duplicated what the Prerequisites list/edge already says. This is a DISPLAY-layer
exclusion in `pipeline.dataset_emit._build_gates` only — `pipeline.gate_patterns`' raw
classification and the underlying `potential-gate` edges are untouched (still 70/60 and 25
respectively). Real corpus: `giga_tech_amb_supertensiles_acot_alpha/sigma/phanon` (the ACOT/AoT
tensile family, 3 of the 4 pairs — the 4th, `_delta`, was never actually a gate owner: its own
`potential` has no `has_technology` leaf at all) plus `giga_tech_arkship_neutronium_harvester`
(the other known dual-encoded pair, gated on `tech_mega_engineering`). **Emitted/displayed totals:
66 gate instances over 56 technologies** (was 70/60), technology-kind 25 → 21.

**Curation is at the MECHANISM level, not the occurrence level.** Once a pattern is registered,
every real occurrence badges — there is no further per-technology editorial filter. See
`spec/P-03-gates.md`'s "Curation is at the MECHANISM level" note for the full reasoning (the
alternative, a hand-curated per-occurrence subset, would be one more hand-maintained surface like
the crisis-faction/flag/name override files, for no evidenced benefit at this corpus size).

`has_gigastructural_constructs`/`has_galactic_wonders` are Gigastructures' own scripted-trigger
wrappers, not literal `has_ascension_perk` checks — confirmed by direct inspection, not assumed
from the names: `has_gigastructural_constructs` is a 1:1 wrapper for `ap_gigastructural_
constructs`; `has_galactic_wonders` is an `OR` of the base `ap_galactic_wonders` perk plus 3
DLC-ownership-variant perk IDs unlocking the same thing, displayed under the single canonical
base id (the only one of the four that's actually vendored/localised). Both wrappers carry an
`is_ai = yes` AI-only override branch the registry deliberately does not model, matching
`pipeline.availability`'s existing treatment.

**Zero interaction with availability evaluation.** All four registered keys were already in
`pipeline.availability.EXCLUDED_KEYS` (an identity-element state) before this module existed —
gate classification adds only display metadata.
`tests/test_gate_patterns.py::test_gate_leaf_keys_plus_not_classified_matches_availabilitys_excluded_keys_exactly`
pins the two lists staying in exact sync, so a future change to either without the other fails
loudly. D-10's worst-case profile-dependent uncertainty is unaffected by gate classification
itself (still asserted directly, not assumed —
`tests/test_dataset_emit.py::test_gate_classification_leaves_d10_uncertainty_unchanged`); see
"Trigger evaluation" above for the CURRENT figure (15/973, 1.54%), which moved for unrelated
reasons (the "path to zero uncertain" follow-up session's Items 1–3).

**Extended (later session, "path to zero uncertain" follow-up, Item 3) — ethics/civic/origin
display gates, two new `GateKind` values.** `GATE_KIND_ORIGIN` (`has_origin` direct, plus two 1:1
scripted-trigger wrappers, `is_wilderness_empire`/`giga_has_frameworld_origin`) and
`GATE_KIND_ETHICS_OR_CIVIC` (`has_ethic`/`has_valid_civic`/`has_civic` direct, plus two 1:1
wrappers, `is_fanatic_spiritualist`/`is_fanatic_pacifist`) — same registered-pattern shape
ascension perks already use, badged the same way. `can_research_technology` (an engine-builtin
alias of `has_technology`, not a scripted_trigger definition anywhere in the corpus) joins the
existing `GATE_KIND_TECHNOLOGY` bucket. D-3's priority order: ascension perk > origin >
ethics-or-civic > technology.

**11 more `EXCLUDED_KEYS` entries are deliberately NOT gate-classified** — genuinely compound
triggers (an `OR` of several real sub-conditions, no single clean `refId`: `is_void_dweller_
empire`, `has_void_dweller_origin`, `is_giga_one_planet_origin`, `is_spiritualist`, `is_natural_
design_empire`, `is_beastmasters_empire`, `is_world_forger_empire`) or not origin/civic/ethic-
shaped at all despite the same "empire-defining choice" character (`is_megacorp` — targets
`has_authority`, a real 4th authority value outside this project's 3-axis model; `is_individual_
machine` — species-archetype + gestalt check; `has_genetically_ascended` — tradition-completion
check; `is_infernal_empire` — species-trait check). These resolve AVAILABLE with no gate badge,
same as any leaf outside the registry always has, just no longer UNCERTAIN either. See
`pipeline.gate_patterns.NOT_GATE_CLASSIFIED_EXCLUDED_KEYS`'s own comment for the full per-key
reasoning.

**A real, non-obvious interaction with the general scripted-trigger expander
(`pipeline.scripted_triggers`, Item 2's own module) — found and fixed in the same session.**
Every new `EXCLUDED_KEYS` entry that is ALSO a real scripted-trigger catalog name (`is_wilderness_
empire`, `is_megacorp`, ... — most of them) needed adding to that module's own skip-set
(`_ALREADY_RESOLVED_KEYS`), or the general expander would blindly substitute the excluded leaf's
real body in place of its name, silently undoing the exclusion — the EXACT bug class the
`country_uses_bio_ships` regression already taught this session once, recurring at a larger scale
(19 keys, not one) the moment a second table (`EXCLUDED_KEYS`) needed the same protection as the
first (`AXIS_FACTS`/`GROUND_FACT_BOOL`/`DLC_NAME_CHECK_KEYS`). Fixed generally: `pipeline.
scripted_triggers._ALREADY_RESOLVED_KEYS` now includes all of `EXCLUDED_KEYS` except the two
wrapper names (`has_gigastructural_constructs`/`has_galactic_wonders`) deliberately left
expandable to answer `WRAPPER_TO_PERK`'s own redundancy question. See that module's own docstring
for the full writeup.

**Icons — reported, not vendored.** `common/civics`/`common/origins`/`common/ethics` are not
vendored for ANY source (not in `tools/collect_vanilla.py`'s required-directory list, and the
manually-pinned Gigastructures/ACOT snapshots happen to carry only their OWN custom civic/origin
icon directories, not vanilla's). Localised display NAMES resolve fine (`localisation/english` is
vendored in full, independent of the missing `common/` directories), but there is no icon file to
show — `_build_gates` falls back to the same graceful-degradation stub (`_default_icon_ref`)
already used elsewhere for a genuinely missing icon. The label text is the real informative
content for these two new gate kinds until real icons are vendored — vendoring a new source
directory is its own review-gated corpus-pinning change, deliberately not done this session.

**Extended again, same session — Item 4: OR-context (alternative) gates, the fix for a real bug the
user reported.** `tech_torpedoes_1` ("Space Torpedoes") displayed "Needs Riddle Escort"
(`tech_cosmogenesis_escort`) as an unconditional requirement — wrong: its real `potential` is
`OR = { country_uses_bio_ships = no, has_tradition = tr_nanotech_4, has_crisis_level =
crisis_level_2, has_technology = tech_cosmogenesis_escort }`, four INDEPENDENT ways to qualify;
non-bio-ship empires (8/12 profiles) already qualify via the first branch alone, unrelated to the
gate. `tech_missiles_1` shares the identical shape. Real corpus: **11 of 25 (44%) real
`has_technology`-under-`potential` occurrences sit inside an `OR`.**

`GateMatch` and the emitted `Gate` schema shape both gained an `alternative: boolean` field
(`pipeline.gate_patterns._scoped_gate_leaves` now tracks OR-ancestry independent of negation
polarity — an `OR`/`NOR` ancestor anywhere marks a descendant leaf `alternative`, an `AND`-only
path never does). Label wording changes accordingly: `"or: <name>"` for an alternative gate,
`"Needs <name>"` only for a genuinely unconditional one — the client renders `gate.label` directly
in both card and popup, so no client wording logic duplicates this. **Generalises correctly beyond
the reported bug**: `giga_tech_the_vat`'s own `ap_mechromancy` ascension-perk gate ("robots go
brrt") is ALSO genuinely OR-context (alongside `has_genetically_ascended`/`has_active_tradition`),
now correctly labelled `"or: Mechromancy"` where `has_galactic_wonders` on the same technology
(AND-context, unconditional) stays `"Needs Galactic Wonders"`.

**A second field, `appliesToEmpireTypes` (nullable `EmpireTypeConstraint`), closes the
"shouldn't present as a requirement for those profiles at all" half of the fix** — for a
`"technology"`-kind alternative gate backed by a real `potential-gate` edge,
`pipeline.edge_constraints`' EXISTING per-edge axis constraint (already computed for
`activeEdgeIds`, unchanged, not recomputed) is reused directly:
`tech_torpedoes_1`/`tech_missiles_1`'s Riddle Escort gate carries `shipset: ["biological"]`. The
CLIENT now consumes this too (`client/src/main.ts`'s `gateAppliesToProfile`, wired into both the
card's zoom-driven LOD visibility loop — `nodePrimaryGateConstraint`, index-parallel to
`nodeGateIcons`/`nodeGateLabels` — and the popup's gate list filter) — a Mechanical-shipset profile
never sees the badge at all for Torpedoes/Missiles; a Biological-shipset profile does, worded as
an alternative. Verified visually (Playwright + headless Chromium against the real built dataset,
not a synthetic fixture): screenshots confirm the badge absent for Regular/Mechanical/Non-nomadic
and present (icon + `"or: Riddle Escort"`) for Regular/Biological/Non-nomadic, in both card and
popup, zero console errors either way.

**Edge extraction (`pipeline/edges.py`) was NOT touched** — confirmed not the bug, per the
original diagnosis: its scope discipline (universal `has_technology`-under-`potential` extraction,
deliberately including OR-context leaves for edge/traversal completeness) is a different concern
from gate DISPLAY wording, and remains exactly as before.

Ordering (D-3): ascension-perk gates outrank origin gates outrank ethics-or-civic gates outrank
technology gates; index 0 is the primary gate, the only one the node card renders (spec's "where
space permits, additional gates render as compact secondary badges" for a technology with more
than one gate is not built — 24/973 real technologies now have a second gate instance, up from
10/973 before Item 3). The popup shows every gate in the ordered list (now profile-filtered by
`appliesToEmpireTypes`, Item 4), each with its resolved icon and localised
`"Needs <name>"`/`"or: <name>"` label. **Real corpus, current: 136 gate instances (45
ascension_perk + 45 origin + 24 ethics_or_civic + 22 technology) over 109 technologies** (was
66/56 before Item 3), of which real per-technology counts include several genuinely `alternative`
matches beyond the two reported/found this session — see `pipeline.gate_patterns.GateMatch`'s own
docstring for the count.

The spec's original "Tetradimensional Engineering" example of one technology gating another was
checked against the real corpus and found wrong — `giga_tech_tetradimensional_engineering`
gates several ascension perks, not any technology's `potential` block. Corrected in
`spec/P-03-gates.md` to `giga_tech_amb_supertensiles_acot_alpha` → `tech_dark_matter_power_
core_ae` at the time — **now itself a stale example, a later session (Item 5 above): this exact
pair is one of the 4 excluded from card/popup display**, since it's also a true prerequisite.
Not re-corrected in the spec file this session; the general shape (a technology gating on
another via `has_technology` in `potential`) is unaffected, a real still-valid example is any
`tech_lathe_*` → `tech_cosmogenesis_world` pair (unaffected by Item 5, since `tech_cosmogenesis_
world` is not also a true prerequisite of the lathe technologies).

**Gates now PROPAGATE down `prerequisite` chains (a later session, "Ring Segment /
ascension-perk locking / gate-propagation" session) — closed a real user-reported gap.** Gates
were previously classified only on the technology that DECLARES them, never inherited — a
technology whose only real requirement is "research my prerequisite first, and THAT tech needs
the perk" showed no gate at all (user reports: the QSO family, and `giga_tech_repeatable_*_cap`
"Management Protocols" repeatables). `pipeline.dataset_emit.build_base_dataset` now computes, for
every rendered technology, the union of its own DIRECT gates plus every gate any `prerequisite`
ancestor (transitively, via Kahn's-algorithm topological order) declares directly, deduplicated by
`(kind, refId)` — direct declarations always win the dedup, an inherited entry is only added when
no direct one already covers the same `(kind, refId)`. Scoped to `prerequisite` edges only,
deliberately NOT `potential-gate` edges (a different kind of dependency — an eligibility check, not
a declared "must research first" chain; propagating through it is left open, pending real corpus
study, see Open Items). Two new `Gate` schema fields carry this: `inherited: boolean` and
`sourceTechnologyId: string | null` (the ORIGINAL declaring technology, not an intermediate hop in
a longer chain) — the client's popup renders an inherited gate with a "(via <source technology>)"
note (`.gate-inherited-note`), the card's single primary-gate slot is unaffected (still index 0,
no new overflow — see the DIRECT/TOTAL count split below for why this doesn't blow out card
space in practice).

**`on_enabled → add_research_option` ascension-perk grants are now a gate source too (the SAME
session, Item 4a) — closed a previously-surveyed-but-unimplemented gap** (HANDOFF.md's "Ordered
next steps" used to flag this as open). `ap_galactic_wonders`'s (Gigastructures-overwritten)
`on_enabled` unconditionally grants `tech_ring_world`, `tech_dyson_sphere` and
`tech_matter_decompressor` — all three structurally UNREACHABLE any other way (unconditional
`weight_modifier = { factor = 0 }`), previously invisible to this pipeline's gate/availability
machinery entirely. `pipeline.dataset_emit.ADD_RESEARCH_OPTION_PERK_GRANTS` adds a direct
`ascension_perk` gate (`ap_galactic_wonders`) to exactly these 3 — deliberately NOT
`tech_mega_engineering` (also granted this way, but remains genuinely reachable by the ordinary
weighted-draw route too, so a gate would overstate a real requirement). `ap_gigastructural_
constructs`'s on_enabled grants a larger set (`giga_tech_hrae_mc`, `giga_tech_ringworld_behemoth`,
`giga_tech_matrioshka_brain_1`, `giga_tech_quasi_stellar_1`, `giga_tech_birch_world_1`,
`giga_tech_lunar_assembly`, `giga_tech_war_system_1`, `giga_tech_supermassive_ehof`) but needs no
new machinery — every one already carries `has_ascension_perk = ap_gigastructural_constructs`
directly in its own `potential`, confirmed already gate-classified before this fix. This is a
DISPLAY-only extension (matching how every other gate works) — it does NOT make `tech_ring_world`/
`tech_dyson_sphere`/`tech_matter_decompressor` LOCKED for axis-excluded profiles, since their own
`potential` never references the perk (only the DISPLAY gate does); left this way deliberately,
same posture as every other gate.

**Real corpus, current (both extensions together): DIRECT gates 139 (48 ascension_perk + 45
origin + 24 ethics_or_civic + 22 technology) over 112 directly-gated technologies — up from
136/109 purely from the 3 new `add_research_option` grants. TOTAL (direct + inherited) gates: 267
(104 ascension_perk + 53 origin + 61 ethics_or_civic + 49 technology) over 196 gated technologies,
48 of which carry more than one gate instance** (up from 24/973 before propagation). Card space:
unaffected in practice — the card still renders only the primary (index 0) gate, unchanged by
propagation; the popup renders the full list already, now including inherited entries with their
source noted.

**Dangling "or:" fixed (the SAME session, Item 7a) — a real user-reported display bug, P-3.** The
OR-context gate fix (an earlier item) marks a leaf `alternative` whenever it sits inside a real
source `OR`, but the OR's OTHER real branches are frequently non-gate-shaped conditions never
tracked as gates at all (Birch World's own sibling is `any_owned_planet = { ... district check
... }`) — when a technology's emitted `gates` list ends up with exactly ONE entry and it's the
alternative one, "or:" reads as a dangling reference with nothing to be alternative to. Downgraded
to a plain "Needs X" requirement in exactly that case (`pipeline.dataset_emit.
_downgrade_dangling_alternative`) — deliberately NOT when `appliesToEmpireTypes` is non-null (the
Riddle Escort/Missiles/Torpedoes shape, an existing, deliberate, tested fix where the SAME "sole
gate in the list" shape is correct AS "or:" for the axis where it's shown). Real corpus: 20
technologies affected (`giga_tech_birch_world_1`, the two Gigastructural-Constructs-gated
`Terrestrial Sculpting`/`Gene Tailoring`/`Driven Assimilator` families, ...); Riddle Escort/
Missiles/Torpedoes and `giga_tech_the_vat`'s genuine 2-gate case are both unaffected, confirmed
directly.

**Gate-polarity bug fixed (a later session, user-reported: habitat technologies showed as
REQUIRING a wilderness empire, backwards).** `pipeline.gate_patterns` tracked negation ONLY via a
`NOT`/`NOR` wrapper ancestor — never a leaf's own literal boolean-false VALUE
(`is_wilderness_empire = no`, Clausewitz's OTHER way to write a negative condition, no wrapper at
all). `_leaf_negated` now XORs three independent negation channels: wrapper ancestry, the `!=`
operator (zero real occurrences on a gate leaf key today, kept for symmetry with
`pipeline.availability`'s own identical check), and a literal `= no` value (the real bug — checked
safe to apply unscoped across every `GATE_LEAF_KEYS` member: `= no` occurs ONLY on
`is_wilderness_empire` in the real corpus, 31 technologies, all boolean-shaped leaves — no
VALUE-shaped key like `has_origin`/`has_technology` ever legitimately takes the literal string
"no"). Real corpus: origin-kind DIRECT gates 45 → 14 (31 technologies, `tech_habitat_1`/`_2`,
`tech_gene_banks`, ... lose their wrong "Needs Wilderness" badge).

**`can_research_technology` removed from gate classification entirely (the SAME session, user-
reported).** It was treated as an alias for `has_technology` ("Needs X" badge), but the two are
genuinely different engine semantics: `has_technology` means "you have ALREADY COMPLETED this" (a
real, satisfiable prerequisite — exactly what "Needs X" says); `can_research_technology` means
"this OTHER technology is not currently LOCKED OUT for your empire" (a structural eligibility
fact, nothing to "go get"). Real corpus: exactly ONE literal occurrence
(`tech_alien_cloning`'s `OR = { is_beastmasters_empire = yes, can_research_technology =
tech_genome_mapping }`), but gate propagation (above) had inherited the mis-badge onto 15
descendants (16 technologies total) — matching the user's "many technologies" report exactly.
Stays excluded from `pipeline.availability`'s boolean combination (an identity element there,
unaffected — moved from an implicit `TECHNOLOGY_ALIAS_KEYS` entry to an explicit
`NOT_GATE_CLASSIFIED_EXCLUDED_KEYS` one, same real-world treatment, clearer bucket). The "bioship
technologies not showing locked" half of the same user report was surveyed and found NOT the same
bug: of 88 real corpus technologies referencing `country_uses_bio_ships` directly, 87 already
resolve correctly differently for mechanical vs. biological profiles (the 1 exception is an
unrelated OR-branch case, not a polarity issue).

**Nested AND-of-OR gates fixed (the SAME session, user-reported: Gargantuan Cloning Facilities
showed "Needs Galactic Wonders" + "or: Mechromancy" as flat peers, when the real structure is
`AND(has_galactic_wonders, OR(has_genetically_ascended, has_active_tradition, ap_mechromancy))` —
Galactic Wonders is unconditionally required, the OR a SEPARATE branch beneath it).** `GateMatch`
gained a `group_id` field (mirroring `Edge.groupId`'s per-owner, per-block-index identity,
`f"{technologyId}#gate-alt{index}"`) naming the specific `OR`/`NOR` block a gate is a DIRECT child
of — computed by `_scoped_gate_leaves`'s new `group_index`/`counter` threading, a fresh index
allocated every time a NEW `OR`/`NOR` is entered (even nested inside another one), `AND`/`NOT`
never allocating one. Real corpus: exactly 1 technology (`giga_tech_the_vat`) mixes unconditional
and grouped gate matches today — the client (`main.ts`'s Gates section) now renders every
`groupId === null` gate flat, then each distinct `groupId` nested under its own "Need one of:"
cluster, so an AND requirement never reads as a peer of a choice beneath it. Every other
multi-gate technology (all-one-group, or all-ungrouped) renders exactly as before.

**Origin/ethics-or-civic gate icon fallback fixed (the SAME session, user-reported: these gates
rendered a meaningless solid-colour "teal square").** `_default_icon_ref`'s degenerate 1x1-pixel
stretched fallback is not a rare edge case for these two kinds — it fired 100% of the time, since
no civic/origin/ethic icon source is vendored at all (CLAUDE.md's own prior "Icons — reported, not
vendored" note). `Gate.icon` is now nullable; origin/ethics_or_civic gates emit `icon: null` and
the client renders the label alone, no icon element. `ascension_perk`/`technology` gates keep
their existing (real, vendored, rarely-missing) icon behaviour unchanged.

**Real corpus, current (all four fixes together): DIRECT gates 107 (48 ascension_perk + 14 origin
+ 24 ethics_or_civic + 21 technology) over 83 directly-gated technologies. TOTAL (direct +
inherited) gates: 214 (104 ascension_perk + 16 origin + 61 ethics_or_civic + 33 technology) over
147 gated technologies, 47 of which carry more than one gate instance.**

**Item 2b survey (SAME session): Nano-Assembler/Polyatomic Crucible have NO ascension-perk
requirement in their own `potential` block, confirmed by raw source inspection — the prior
session's "weight-based, not gate-based" conclusion for the Cosmogenesis family stands, it was NOT
too broad for these two.** Their only real conditions are the `@giga_amb_flag` mod-config toggle
(already the documented, deliberately-unresolved uncertain reason) and, inside `weight_modifier`
only, a `NOT = { has_crisis_level = crisis_cosmogenesis_level_5 }` zero-weight gate plus an
`ap_technological_ascendancy` weight BONUS (a real vanilla perk, not the Gigastructures-flavoured
"Cosmogenesis" the user meant) — neither is a `potential`-level requirement, so neither can
correctly badge as a gate. Reported to the user rather than fabricated.

## `pipeline/layout.py` — full "pipeline owns geometry" + row-overlap defect-class narrative (superseded condensed version now in CLAUDE.md's Rules section)

Moved verbatim from CLAUDE.md during the docs-restructure session.

- **The pipeline owns all geometry; the renderer consumes emitted positions and never recomputes
  them from a parallel formula.** Any renderer-side value that is derivable from emitted geometry
  (row/band extents, a cell's populated width, anything of that shape) MUST be derived from the
  real emitted positions (`nodePositions`/`edgePolylines`, per `00-overview.md`), never
  reimplemented client-side from the same inputs `pipeline/layout.py` consumes. Found the hard
  way: `client/src/main.ts` once re-derived row/band geometry via its own copy of
  `pipeline/layout.py`'s wrap/width formulas, and D-17's same-band depth-slot fix silently
  desynced it — row panels, tier tints and cell labels drew nowhere near their actual cards, with
  no error, no failing test, no warning, caught only by a headless screenshot. Two independent
  implementations of the same geometry WILL drift the moment either one changes, and nothing
  forces them to change together. The permanent fix, and the rule going forward: derive from the
  real positions (min/max over the emitted `nodePositions`, grouped by row/band), so client and
  server geometry cannot drift apart again regardless of how the underlying layout formula changes
  in the future — not a periodic re-sync. **Audited for other instances of this pattern**: the
  severe form (recomputing a multi-step DERIVED formula that can produce a different value than
  the pipeline's own) is now eliminated for row/band geometry, the only place it existed. What
  remains is a milder, harder-to-avoid form: a set of mirrored SCALAR constants
  (`CARD_WIDTH`/`CARD_HEIGHT`, the gutter constants, `SUBGRID_WIDTH`, `AREA_ORDER`,
  `FLOATS_PER_EDGE_POLYLINE`, `MIN_STUB`) that must still be kept numerically in sync with
  `pipeline/layout.py`/`pipeline/geometry.py` by hand, since the dataset schema doesn't carry them
  as data. Their blast radius if they drift is smaller than the row/band bug was — most now feed
  only the degenerate zero-population-row/band fallback path or are diagnostic-only (`MIN_STUB`,
  used only by `checkMinStubLength`). `CARD_WIDTH`/`CARD_HEIGHT` are the one genuinely
  load-bearing pair, since they size the actual card draw call and the dataset carries corner
  positions, not card dimensions. Not fixed this session (would mean adding card dimensions to the
  schema) — flagged as a scoped follow-up rather than silently left looking fully closed.
- **A second, DIFFERENT defect class produced the same visible symptom (rows overlapping) a later
  session, and must not be confused with the parallel-formula bug above.** The screenshot-review
  session's Item 4 (short-sub-grid-column vertical centring, `pipeline/layout.py`) introduced a
  hard regression: `column_member_count`, a dict tracking each sub-grid column's own member
  count, was keyed by `(row_id, col)` alone. `col` is BAND-RELATIVE — `depth_slot_start[(band_
  index, depth)]` resets its own cursor to 0 for every band — so col 0 in one band and col 0 in a
  LATER band of the SAME row are physically different columns (different x) but shared the same
  dict key, silently SUMMING their member counts into one entry. That corrupted count could
  exceed the row's real max (`row_row_counts[row_id]`) and drive the centring offset NEGATIVE,
  shifting a column's cards upward past row 0 into the row above — real corpus example:
  `column_member_count[('voidcraft', 0)]` corrupted to 37 against a real `row_row_counts` of 6,
  producing `giga_tech_birch_world_1` at row **−16**. **This is a plain dict-keying bug (a missing
  discriminator field), not a parallel-geometry violation** — nothing client-side re-derived
  anything; `client/src/main.ts` correctly derived row panels from the (corrupted) emitted node
  positions exactly as the rule above requires, and faithfully reproduced the bug rather than
  masking or independently causing it. Confirmed directly (not assumed) that this rules out the
  parallel-geometry rule as a second cause here. Fixed by keying on the full `(row_id, band_index,
  col)` triple, which is unique by construction, plus a same-turn `assert centre_offset >= 0` in
  `pipeline/layout.py` itself as a second line of defence. **The real lesson, and why it reached
  the user**: the existing test suite stayed fully green through this regression — canvas
  dimensions were genuinely unaffected (row HEIGHT is computed from `row_row_counts`, set in the
  first pass and never touched by the buggy second pass; only individual cards' position WITHIN
  their row was corrupted), and nothing asserted the actual invariant that matters (no two rows'
  card-occupied extents may intersect, no node's row index is ever negative). A green suite proved
  self-consistency, not correctness — the same lesson D-17's unbounded-stacking bug already taught
  this project once, now recorded as a second occurrence.
  `tests/test_layout_corpus.py::test_no_row_overlaps_and_every_card_within_its_own_row_bounds`
  (real corpus) and `tests/test_layout.py::test_no_row_overlaps_when_the_same_row_spans_multiple_
  bands` (fast synthetic regression case) are the missing invariant, added after this regression,
  each proven capable of failing against the actual broken code before being trusted on the fix.

## Source data — full narrative moved from CLAUDE.md (25k-restructure session)

Moved verbatim; CLAUDE.md now keeps a compact table plus short rules.

**Gigastructures target and mechanism are two separate questions — don't conflate them.**
The *target* is the released mod (what players run), not unreleased dev work. The
*mechanism* is a pinned commit on GitHub's `Live-Branch`
(`Pouchkinn-s-Gigastructures/Gigastructures`), confirmed to match the Steam Workshop upload
in content relevant to this tool — a commit hash is precise, fetchable, and reproducible in
a way a locally-mounted Workshop directory's provenance is not. If `Live-Branch` ever
diverges from the Workshop release, follow the release and re-pin the commit; do not track
HEAD unconditionally. Currently vendored: commit `0f1f2b024f43249dc7dfe132fe7c0e4201398ef5`
(tag `v3.39.3`), recorded in `vendor/manifest.json` alongside the existing content hash.
**ACOT and AoT remain Steam Workshop only, asymmetrically — and the reason is repo
reliability, not repo absence.** Both have source repos; neither is pinned against, because
ACOT's is not well maintained and AoT's carries the same risk (its repo tracks ACOT's, so an
unreliable ACOT repo makes AoT's no more trustworthy to pin against). Gigastructures gets the
stronger mechanism because its `Live-Branch` is confirmed to track the Workshop release
reliably — not because it's the only one of the three that happens to publish a repo at all.
**Do not "fix" this asymmetry by pinning ACOT or AoT to their repos** without first
re-establishing that those repos are reliable enough to track — the current manual Workshop
mechanism is the deliberate choice, not a placeholder waiting to be replaced. Their versions
are recorded by hand in dataset metadata. AoT depends on ACOT.

**Open item, not yet built**: `tools/collect_vanilla.py` does not implement any of this —
it currently collects all three mods identically, from local Steam Workshop directories
keyed by `workshop_id`, with no GitHub fetch and no commit pinning. The commit above was
pinned manually (`git clone` + `rsync` into `vendor/mods/gigastructures/`, hash and commit
recorded in `vendor/manifest.json`) to make the gap visible and the snapshot reproducible in
the meantime. Building an actual GitHub-fetch-and-pin path (plus the scheduled CI check that
reports how far behind the vendored snapshot is, as a warning not a blocker) is still open.

Load order, lowest to highest: vanilla, Gigastructures, ACOT, AoT. Treat this as an ordered
list of sources. Do not special-case "vanilla" and "mod" in resolution logic. Overwrite
semantics are whole-key replacement, matching the engine — never a field-level merge.

Surveyed, not assumed: Gigastructures redefines exactly **two** vanilla `common/technology`
blocks (`tech_ring_world`, `tech_mega_engineering`, both in `zz_giga_tech_overwrites.txt`),
and nothing else — checked and ruled out for Gigastructures-over-vanilla specifically: no
`@scripted_variable` indirect override of a vanilla-referenced variable, no `technology_swap`
appropriating a vanilla key. Overwriting between mods is a much bigger surface: 19
`acot`↔`aot` and 4 `acot`↔`stellaris` technology-block overlaps, with `aot` redefining `acot`
technologies as its dominant pattern (`aot` depends on and loads after `acot`). No 3+-source
overwrite chains exist anywhere in `common/technology`. `acot`↔`aot` scripted-variable
overwrite is real, though (14 cross-source keys, mostly component-cost variables) — a
technology's effective cost/weight can change without its own block being touched, so any
overwrite diff must resolve `@variable` references before comparing cost/weight fields.

**Canonical technology count: 1,879.** Three technology counts have been used interchangeably in
this project's notes and must not be — each counts something different, and only one is correct
for "how many technologies exist / will become nodes":

- **1,879 — distinct technology keys, canonical.** Every unique top-level `key = { ... }` name
  across `common/technology` in all four sources, after whole-key overwrite resolution collapses
  each redefined key to its one winning definition. This is the right number for "how many
  technology identities exist" and today's best available upper bound on the final rendered node
  count — it can only shrink further once P-16's rendering-scope closure exists (some ACOT/AoT
  keys outside that closure won't be emitted as nodes at all). **Use this for size estimates,
  node-count estimates, and any fixture meant to be shaped like the real dataset.**
- **1,904 — raw technology-block occurrences, pre-resolution.** Every `key = { ... }` block
  parsed, counting an overwritten key once per source that defines it (25 keys are defined twice,
  matching the 25 confirmed technology-block overwrites — see below — so 1,879 + 25 = 1,904). Not
  a node count: an overwritten-away definition merges into its winner's single node, it doesn't
  become a second one. Useful only for overwrite-resolution bookkeeping, never for size/count
  estimates.
- **2,122 — technology icon *candidates*, a different concept entirely.** `pipeline/icons/`'s
  candidate count: the 1,904 raw occurrences above, plus 218 `technology_swap` sub-block
  alternates (1,904 + 218 = 2,122). A swap alternate is per-empire-profile display data on an
  *existing* node's card, never a separate node. Correct for icon-atlas sizing; wrong for
  anything answering "how many technologies."
- **1,878 — retired.** Appeared in earlier size estimates and the deploy-spike fixture; its exact
  derivation was never preserved and could not be reconstructed, but it does not match any of the
  three real quantities above — treat any figure still citing 1,878 as stale and correct it to
  1,879 (or whichever of the three above is actually meant) on sight.

If a fourth technology count ever shows up, work out which of these three concepts it actually
is before recording it anywhere — do not add a fourth number to the set without first mapping it
onto raw-occurrences, icon-candidates, or canonical.

Required directories, per source (spec/00-overview.md is authoritative — this is a pointer, not
a copy): `common/technology`, `common/scripted_variables`, `common/scripted_triggers`,
`common/ascension_perks`, `common/inline_scripts`, `localisation/english`,
`gfx/interface/icons/technologies`, `gfx/interface/icons/ascension_perks`. The two icon
directories are separate because ascension perk icons (P-3's gates) are not filed under
`technologies/` in any source — a directory list naming only `technologies/` cannot satisfy
P-3's "every gate renders its icon as an image, path never manually maintained" requirement.
Adding a gate kind outside ascension perks and technologies means adding its own directory here
the same way, not inferring a location from a pattern.


## CLAUDE.md's former "Locked decisions" body, in full (25k-restructure session)

Moved verbatim from CLAUDE.md, which now keeps one line per decision plus a pointer into spec/decisions.md or the relevant P-file (or, where no such file exists, a short current-state statement with a pointer here for the full reasoning). Headings below match CLAUDE.md's former subsection structure exactly.

## Locked decisions

### Empire model

Three independent axes, composed at build time. Never a flat enumeration.

- Gestalt/authority: regular, hive mind, machine intelligence
- Shipset: mechanical, biological
- Nomadic: yes, no

Twelve profiles. Origins are not an axis for v1, but the fact registry is extensible — if
origin-gated techs turn up during extraction, add a fact, do not restructure.

**Ascension perks are gates, not profile facts — CORRECTED (a later session, "Ring Segment /
ascension-perk locking" session).** The original wording above was refuted by real corpus content
(Galactic Wonders is genuinely unobtainable for nomadic empires) and by the user's domain
knowledge, and is kept struck through only as the historical record of what was superseded:
~~A perk-gated tech always displays its gate. The tree shows what you would need; it never assumes
you have it.~~

**The corrected rule is a distinction, not a reversal:**
- **WHICH perk a player chooses remains a free choice, never a profile fact.** A perk-gated
  technology still always displays its gate rather than assuming the player has or hasn't picked
  it — this half of the original rule stands unchanged.
- **WHETHER a perk is obtainable AT ALL for an empire type is a real fact, when the perk's own
  `potential` carries a genuine axis constraint.** A technology gated behind a perk that is
  structurally impossible for a profile is genuinely LOCKED for that profile, not merely gated —
  the same as any other axis-impossible technology.

Implemented automatically (a full corpus survey, not a hand-curated table):
`pipeline.availability.set_perk_potentials` registers every ascension perk's own winning
`potential` block; `_evaluate_leaf`'s `has_ascension_perk` branch evaluates the referenced perk's
potential against the current profile through the SAME evaluator, and only turns the leaf into a
real `FALSE` when that sub-evaluation is a definite `LOCKED` (never for `UNCERTAIN` — a perk with
residual undecidable conditions stays gate-only, exactly as before). **Real corpus: 21 perks are
cleanly axis-restricted** (`ap_wanderlust`/`ap_hydrocentric`/`ap_eternal_vigilance(_nomads)` on
`is_nomadic`; `ap_synthetic_age`/`ap_machine_worlds`/`ap_mechromancy`/`ap_one_vision` on
`is_machine_empire`; `ap_organo_machine_interfacing`/`ap_hive_worlds` on `is_hive_empire`;
`ap_lord_of_war`/`ap_xeno_compatibility`/`ap_arcology_project` on `is_regular_empire`;
`ap_gigastructural_constructs`/`ap_qso`/`ap_vast_expanses`/`ap_celestial_printing`/
`ap_supermassive_ehof`/`ap_master_builders`/`ap_galactic_wonders` on `is_nomadic`; plus 3 perks —
`ap_defender_of_the_galaxy` and the `ap_galactic_wonders_utopia`/`_megacorp`/
`_utopia_and_megacorp` DLC-variant duplicates — found universally unobtainable, either a legacy
pre-Nomads-DLC fallback (`has_nomads_dlc = no`, impossible under this project's all-DLC-owned
assumption) or a superseded perk carrying a literal `potential = { always = no }`, resolved
correctly by the SAME session's `always` leaf fix below). **20 more perks carry a residual
undecidable condition** (compound triggers, mid-game player state) and are deliberately left
gate-only, never guessed at — see `pipeline.availability`'s module docstring for the full list.
A genuine cross-perk cycle exists in the real corpus (`ap_defender_of_the_galaxy` <->
`ap_defender_of_the_galaxy_nomads`, each excluding the other via a `NOR = { has_ascension_perk =
<the other> }` superseded-perk guard) — broken by a recursion guard
(`_perk_eval_in_progress`), not assumed absent.

**A real, necessary correction to `_combine_or` fell out of this fix.** Before a perk-gated leaf
could ever be a real `FALSE`, an `OR` mixing an EXCLUDED (gate-only, presumed-achievable) sibling
with a real FALSE sibling never arose; `_combine_or`'s original rule (ignore EXCLUDED siblings,
decide purely from the rest) then wrongly closed off the whole OR whenever the achievable sibling
was filtered away, leaving only the FALSE one. Real corpus case this fixes:
`giga_tech_ringworld_titanic_1`'s `OR = { has_ascension_perk = ap_galactic_wonders,
has_ascension_perk = ap_galactic_wonders_utopia }` — for a non-nomadic profile the first branch is
open (achievable) while the second is a real FALSE (permanently disabled); the whole OR must read
as still-gated (AVAILABLE), not LOCKED, since the open branch remains live. Fixed: an `OR` whose
non-EXCLUDED children are all FALSE, but at least one child WAS EXCLUDED, now resolves EXCLUDED
(open) rather than FALSE. `pipeline.edge_constraints`'s own, deliberately different sensitivity
mechanism (Disco Moon's masking-avoidance fix) needed the PRE-correction behaviour preserved
exactly, so it now swaps in its own `_legacy_combine_or` copy for the duration of its check —
these are two different questions ("is this technology available" vs. "does this specific
has_technology leaf's value change the outcome") that happen to share underlying code, not one
mechanism that regressed.

See CLAUDE.md's "Gates" section below for the propagation and `add_research_option`-grant
extensions this same finding led to, and the "Trigger evaluation" section for the moved D-10
figures.

Corpus confirmation, not a to-do: vanilla's `tech_mega_engineering` (also overwritten by
Gigastructures — see `### Prerequisites`) carries `is_nomadic = yes`-gated weight modifiers
mirroring its non-nomadic starhold/citadel starbase-count modifiers 1:1 (waystation tiers 2
and 3 in place of starhold/citadel). Direct evidence the nomadic axis affects research
weight, and therefore research path — relevant to `EmpireTypeConstraint` and P-12.9.

### Scope of ACOT and AoT

**D-18 (`spec/decisions.md`) — the closure is DEPTH-1, not a full transitive closure. This
supersedes this section's original justification below the line, kept only as historical
record of what was superseded and why.** The tree renders vanilla and Gigastructures technologies
unconditionally. An ACOT/AoT technology renders only when a rendered (vanilla/Gigastructures)
technology names it **directly** in its own `prerequisites` block — no recursion. An ACOT/AoT
technology reachable only through ANOTHER ACOT/AoT technology's own prerequisite chain does not
render, even if that intermediate technology does. This is a build-time computation, not a
user-facing filter — there is no checkbox and no mod-set URL state. Mod requirement is a
`requiresMods: string[]` field rendered as a card badge (`ACOT`, `AoT`) — distinct from gates and
from prerequisites — that communicates the requirement without toggling visibility.

**The accepted cost, real and named, not hypothetical**: exactly 3 off-tree prerequisite links in
the real corpus, all ACOT→ACOT — a rendered ACOT technology whose own card names a prerequisite
that itself has no node. `tech_dark_matter_power_core_ae` ("Alpha-class Enigmatic Power") →
`tech_precursor_design` ("Precursor Databank Analysis"); `tech_dark_matter_power_core_dm`
("Delta-class Enigmatic Power") → `tech_dark_matter_power_core_enig` and → `tech_mine_dark_energy`.
The user reviewed this exact set (surfaced by a reported over-inclusion complaint naming the first
pair) and chose depth-1 over both the original full-closure rule and a considered middle option
(rendering an out-of-closure prerequisite as a distinct stub/ghost node — rejected as
disproportionate to 3 links). `tests/test_rendering_scope.py::
test_depth_one_closure_off_tree_links_match_the_accepted_set` pins this exact 3-link set; a
corpus refresh that creates more fails it loudly rather than silently degrading chain completeness
further. Real measured effect: rendered node count 980 → 977, edges 989 → 984 (5 fewer
`prerequisite` edges; `alternative`/`potential-gate` unaffected). Canvas dimensions and densest
(row, band) cell were UNCHANGED by D-18 itself (30,840 × 9,736px at the `subgrid_width=4` in
effect when D-18 shipped, `voidcraft`×T5=47) — none of the 3 dropped technologies was in the
densest cell or its own band. (Canvas is now 29,670 × 13,448px under `subgrid_width=6`, the
user's later D-17 pick — see D-17's own record; the densest cell is still `voidcraft`×T5=47,
unaffected by either change.)

**977 → 973, a later session, Item 2c (user domain call): a technology whose `potential` block
contains a top-level literal `always = no` leaf is disabled content, not uncertain content, and is
now excluded from the rendered tree entirely** (`pipeline.rendering_scope._is_permanently_
disabled`), rather than rendered locked/uncertain. Real corpus: exactly 4 technologies —
`giga_tech_aeternite_weaponry`, `giga_tech_interstellar_ringworld`, `giga_tech_orbital_elysium`,
`giga_tech_stellar_ring_habitat` (the last two carry `always = no` alongside now-moot dead
siblings, not as a clean singleton the way the first two do — the detector checks any top-level
child, not just a singleton block). Nothing else references any of the 4 as a prerequisite
(confirmed by direct search), so no dangling-edge/off-tree-prerequisite consequence. Real measured
effect: 977 → 973 nodes, 984 → 977 edges (876 prerequisite + 76 alternative + 25 potential-gate;
7 fewer prerequisite edges, the 4 excluded technologies' own outgoing references — alternative/
potential-gate unaffected). Densest (row, band) cell moves 47 → 46 (`giga_tech_interstellar_
ringworld` was a real member of `voidcraft`×T5); canvas 29,670 × 13,448px → 29,670 × 13,332px.
`config/name_overrides.txt`'s `giga_tech_aeternite_weaponry` entry (see "Rules" below) was removed
as dead once its technology stopped rendering, rather than left in place unused.

**Original justification, superseded by D-18 above, kept for history**: the tree used to render
ACOT and AoT technologies wherever they fell in the **rendering-scope closure** of a rendered
technology — `prerequisite` edges only, pooled across all twelve profiles, so a rendered
technology's prerequisite chain was never broken by an invisible gap — with an ACOT/AoT technology
having no rendered descendant excluded as a node. The user reported this over-included: an
ACOT/AoT technology reachable only through another ACOT/AoT technology, itself required by nothing
actually rendered, still appeared. D-18 replaced this with depth-1.

Rendering scope is a separate computation from **per-profile structural reachability**: because
the closure above is profile-invariant, a node reachable via only one profile's tech-swap chain
still renders for all twelve. For the other eleven, a second check — over *all three* edge kinds
(`prerequisite`, `potential-gate`, `alternative`), never just `prerequisite` — decides whether the
node is actually reachable for that profile; if not, it renders locked with a structure-derived
reason. Conflating the two checks is a correctness bug: it wrongly locks a node that a
`potential-gate` or `alternative` edge actually reaches for that profile. See P-16.

### Prerequisites

There is no "primary prerequisite". Multiple prerequisites are all equally required. The data
model carries a flat list, ordered deterministically by tier, then cost, then key.

Dependencies must also be extracted from `has_technology` checks inside a `potential` block,
universally (`potential`-only — checked against the real corpus, not "and other trigger blocks"
as an earlier draft assumed; `allow` never occurs on a rendered technology, and
`weight_modifier`/`ai_weight` contribute zero occurrences once scoped correctly — see P-14's
"Implied technical decisions" for the full corpus finding). Preserve boolean structure — a
`has_technology` inside a `NOT` is a negative dependency; the real corpus has zero such
occurrences under `potential` today, and one is excluded from edge output and diagnosed rather
than emitted as a wrong-polarity edge, since flattening/inverting it silently would produce a
wrong graph. Edges are typed and conditional:
`{ from, to, kind, groupId, appliesToEmpireTypes, backward, bandSpan }`.

**Nested `OR` inside a `prerequisites` block (the `alternative` edge kind) is real and common in
the corpus — 35 confirmed `OR`-group instances (21 vanilla, 14 Gigastructures) across 32 distinct
technologies (18 vanilla, 14 Gigastructures — 3 vanilla technologies carry two independent groups
each), including vanilla's own `tech_mega_engineering`.** Corrected from an earlier, broader
claim: the real corpus contains only `OR` nested inside `prerequisites` — checked directly, not
assumed — 0 `AND`/`NOR`/`NOT` occur there. It is a distributional fact, not yet a gap, that ACOT
and AoT contain zero such instances — alternative-edge rendering is exercised only by vanilla and
Gigastructures nodes; keep that in mind when building fixtures or coverage around this edge kind.
Each `OR` group carries its own `groupId` (`Edge.groupId`, `schema/common.schema.json`) so two
independent 2-member groups on the same technology aren't indistinguishable from one 4-member
group.

**Edge-kind membership is NOT mutually exclusive per `(from, to)` pair.** 4 real corpus pairs are
both a formal `prerequisite` and a `potential-gate` (the same dependency redundantly encoded
twice, e.g. `tech_mega_engineering -> giga_tech_arkship_neutronium_harvester`). Both are emitted;
dropping either would corrupt one of the two traversals that consume that kind. Collapsing them
into one visual line for display, if ever wanted, is a Stage 3 rendering decision over the
emitted data, not a data-model decision — see `spec/P-14-unconventional-prereqs.md`.

### Trigger evaluation

Partial evaluation against empire profile facts (`pipeline/availability.py`). Every condition
resolves to `true`, `false`, or `unknown` (three-valued, Kleene-style short-circuiting through
`AND`/`OR`/`NOT`/`NOR`). `unknown` propagates. Never assume `unknown` means available or
unavailable. Output is always `(technology, empire profile) -> {state, reason}` with `state` in
`{available, locked, uncertain}` — never a boolean (D-10/P-13).

**D-10 splits into two distinct metrics, both computed over RENDERED nodes (973, P-16's closure)**
— see `spec/decisions.md`'s D-10 for the full reasoning; summarised:

- **Profile-dependent uncertainty** — a technology whose state varies by profile. Governed by:
  hard ceiling 10% for any single profile (build fails above it); warn threshold 3% per profile;
  a ratchet (CI fails if any profile's rate rises against its own prior-dataset figure, even
  under 10%).
- **Unconditional uncertainty** — a technology `uncertain` under all twelve profiles identically
  (no axis check anywhere in its trigger structure). Never misleads a user about their specific
  empire — an honest "unknown" reporting a fact outside the axis model. Its own
  data-completeness figure with its own regression ratchet, but **NOT subject to the 10%
  ceiling** — a different quality signal, not a weaker version of the same one.

Always state which of the two denominators (all-1,879-canonical vs. rendered-973) a reported rate
uses — rendered-only uncertainty is *higher* than all-canonical, because Gigastructures' own
content, not unrendered ACOT/AoT bulk, is the concentration point; narrowing ACOT/AoT rendering
scope does not fix a ceiling breach.

**Current real corpus figures (reconciled, latest session, after Item 2b's zero-weight-gate fold-in
below): unconditional 115/973 (11.8%); worst profile-dependent 58/973 (5.96%, over the 3% warn
threshold, under the 10% ceiling); union (uncertain for ≥1 profile) 180/973.** (Pre-Item-2b:
unconditional 31/973 (3.19%), worst profile-dependent 16/973 (1.64%), union 53/973 — see the
"Research weight" section below for the full accounting of what moved and why.) Full move-by-move
history — every intermediate figure and which fix moved it — lives in `docs/BUILD-LOG.md`'s
availability/trigger-evaluation sections; do not re-derive it
from memory, re-run the corpus survey if a figure here looks stale.

**Leaf types the evaluator resolves**, beyond the axis facts (gestalt/authority, shipset,
nomadic) and DLC-ownership ground facts:
- `always` (both `yes` and `no`).
- `has_active_tradition` — TRUE by default except the user-confirmed `tr_genetics*` category
  (unavailable to machine-intelligence empires; the only real corpus occurrence is
  `giga_tech_the_vat`).
- `has_ascension_perk` — resolves through the perk's own registered `potential` (see "Ascension
  perks are gates" above); only ever contributes a real `FALSE` on a definite perk LOCKED result,
  never on UNCERTAIN.
- `has_ancrel` — a literal `host_has_dlc = "Ancient Relics Story Pack"` check (real definition at
  `vendor/stellaris/common/scripted_triggers/00_scripted_triggers.txt:2678`), treated as an
  ordinary DLC-ownership ground fact.
- **Recursive scripted-trigger expansion** (`pipeline/scripted_triggers.py`) — a bare-identifier
  scripted-trigger reference in `potential` (e.g. `giga_can_use_habitables = yes`) is substituted
  with the trigger's real body, recursively, before evaluation — never a second evaluator, never
  new boolean semantics. Any leaf already in `AXIS_FACTS`/`GROUND_FACT_BOOL`/`DLC_NAME_CHECK_KEYS`
  is skipped by expansion unconditionally, so the axis-fact/ground-fact shortcuts for things like
  `country_uses_bio_ships` (also a real scripted-trigger name) are never destroyed by blind
  substitution. `is_ai = yes` branches are stripped (not modelled) during expansion, including
  through a `hidden_trigger` wrapper whose direct children are ALL is_ai-gated. Real corpus: 3,463
  distinct trigger names post-overwrite, zero reference cycles, max reference-chain depth 8
  (`MAX_EXPANSION_DEPTH = 12`, a hard-failure sanity ceiling). One file
  (`zzz_overwrites.txt`'s `has_research_building`) can't be fully expanded (a dynamic `@[...]`
  file-path computation) — zero real-corpus effect, since no rendered technology references it.
- `PROGRESSION_FLAGS_TRUE` (`pipeline.availability`) — `has_country_flag`/`has_global_flag` names
  matching a crisis-faction/story-progression naming pattern
  (`_possible`/`_solved`/`_unlocked`/`_happened`/`_complete`/`_aborted`/`_knowledge`/`_opened`
  suffixes, `encountered_`/`completed_` prefixes) resolve TRUE as a class — every sampled real
  setting site is a genuine `is_triggered_only` country event with no empire-type restriction.
  Real corpus: 64 distinct flag names. Two vanilla L-Gate storyline flags (`l_cluster_opened`,
  `encountered_first_lgate`) are deliberately EXCLUDED from the pattern — their setting sites live
  in vanilla's `events`/`decisions`, which this project doesn't vendor, so resolving them would
  rest on outside-corpus knowledge. `docs/BUILD-LOG.md` has the full outlier list.

**Documented evaluator assumptions**, applied before anything counts as uncertain (each
individually verified against the vendored corpus, never a blanket "assume everything works" —
see `pipeline/availability.py`'s module docstring and `spec/decisions.md`'s D-10 for full detail):

1. Mod-config content-toggle global flags (`has_global_flag` names ending `_forbidden`,
   `_disabled`, or `_OFF`) resolve to their unset default. Flags outside that pattern
   (`compound_invasion_happened`, `l_cluster_opened`, ...) stay genuinely unresolved.
2. All official DLC assumed owned — a literal `has_dlc`/`host_has_dlc` leaf plus a dozen named
   per-DLC scripted-trigger wrappers individually confirmed pure `host_has_dlc` calls
   (including `has_nemesis`/`has_infernals`), plus `has_megacorp` (the DLC-ownership check, NOT
   `is_megacorp`, a real empire-type/civic choice fact outside the 3-axis model, deliberately
   left unresolved). `has_gigastructural_constructs`/`has_galactic_wonders` were checked and
   found to be ascension-perk-gate checks in disguise, not DLC checks — left unresolved here.
3. Not-a-fallen-empire is a ground fact of all twelve profiles.
4. **Mod-content-presence flags** — `has_acot` and `has_global_flag = has_aot_mod` both resolve
   `true` (this deployed tree already assumes ACOT/AoT content is present). Distinct from the
   `requiresMods` card badge (`pipeline.dataset_emit._potential_mod_requirements`), which is a
   separate display mechanism keyed off the same leaf. Real corpus: 4 technologies
   (`giga_tech_amb_supertensiles_acot_alpha/sigma/delta/phanon`).
5. **User-confirmed progression-state flags, one at a time, never a blanket pattern-resolve** —
   `has_country_flag`/`has_global_flag` names gating Gigastructures-internal PROGRESSION state,
   distinct from a genuine per-empire-type ELIGIBILITY gate. Only `colossus_project` is confirmed
   (6 technologies, `tech_pk_cracker`/`_godray`/`_nanobots`/`_neutron`/`_shielder`/`_smelter`). A
   larger candidate list (`giga_rings_beh`/`_gar`/`_tit`, `has_arcane_generator`,
   `has_finished_psionic_tradition`, `has_quantum_catapult_insight`, others) is surveyed but not
   resolved — see `docs/BUILD-LOG.md`. This is the one evaluator category that is inherently
   per-flag, never a pattern rule — see `PROGRESSION_FLAGS_TRUE`'s own comment before adding one.

`has_technology` (P-14 prerequisite-graph reachability), `has_ascension_perk` (a P-3 gate), and
`has_gigastructural_constructs`/`has_galactic_wonders` are excluded from boolean combination
entirely — an identity element, not resolved either way, because each is a different mechanism's
job; folding any into `uncertain` would be a category error.

`common/scripted_triggers/` custom calls the evaluator can't expand (a materially larger feature
than what's built beyond the recursive expansion above) and `has_country_flag` (131 occurrences,
82 distinct names, no single resolvable pattern) remain the two biggest levers still left on the
unconditional figure. Leaf shapes deliberately left unresolved, no invented handling: `has_authority`,
`founder_species`, `has_civic` (distinct from `has_valid_civic`), `if = { limit = {...} }`
conditional-effect blocks — real residue, not bugs, see `docs/BUILD-LOG.md` for which are further
resolvable.

### Gates

`pipeline/gate_patterns.py` classifies registered trigger patterns into the schema's `Gate`
shape, layered on top of P-14's universal `potential-gate` edge extraction — never removing or
altering an edge, only adding a badge. **Curation is at the MECHANISM level, not the occurrence
level**: once a pattern is registered, every real occurrence badges — there is no further
per-technology editorial filter (`spec/P-03-gates.md`'s own note has the full reasoning).

**Registered gate kinds and their patterns** (D-3 priority order: ascension perk > origin >
ethics-or-civic > technology — index 0 is the primary gate, the only one the node card renders;
the popup shows every gate in the ordered list):
- `ascension_perk` — `has_ascension_perk` direct, plus two Gigastructures scripted-trigger
  wrappers confirmed by direct inspection, not assumed from naming: `has_gigastructural_
  constructs` (a 1:1 wrapper for `ap_gigastructural_constructs`) and `has_galactic_wonders` (an
  `OR` of the base `ap_galactic_wonders` perk plus 3 DLC-variant perk IDs, displayed under the
  single canonical base id). Both wrappers carry an `is_ai = yes` AI-only override branch,
  deliberately not modelled, matching `pipeline.availability`'s treatment.
- `origin` — `has_origin` direct, plus two 1:1 wrappers (`is_wilderness_empire`,
  `giga_has_frameworld_origin`).
- `ethics_or_civic` — `has_ethic`/`has_valid_civic`/`has_civic` direct, plus two 1:1 wrappers
  (`is_fanatic_spiritualist`, `is_fanatic_pacifist`).
- `technology` — `has_technology` (an engine-builtin alias, `can_research_technology`, was tried
  and then REMOVED — see "Gate-polarity/nested-OR fixes" below, it means something different).

**Zero interaction with availability evaluation** — every registered leaf key is also in
`pipeline.availability.EXCLUDED_KEYS` (an identity-element state), so gate classification adds
only display metadata, never changes an availability result.
`tests/test_gate_patterns.py::test_gate_leaf_keys_plus_not_classified_matches_availabilitys_
excluded_keys_exactly` pins the two lists staying in exact sync.

**11 further `EXCLUDED_KEYS` entries are deliberately NOT gate-classified**
(`pipeline.gate_patterns.NOT_GATE_CLASSIFIED_EXCLUDED_KEYS`) — genuinely compound triggers with
no single clean `refId` (`is_void_dweller_empire`, `has_void_dweller_origin`,
`is_giga_one_planet_origin`, `is_spiritualist`, `is_natural_design_empire`,
`is_beastmasters_empire`, `is_world_forger_empire`), or not origin/civic/ethic-shaped despite the
same "empire-defining choice" character (`is_megacorp` — targets a real 4th authority value
outside the 3-axis model; `is_individual_machine`, `has_genetically_ascended`,
`is_infernal_empire`). These resolve AVAILABLE with no gate badge — see the module's own comment
for the full per-key reasoning. Every new `EXCLUDED_KEYS`/`NOT_GATE_CLASSIFIED_EXCLUDED_KEYS`
entry that is ALSO a real scripted-trigger catalog name must be added to `pipeline.
scripted_triggers._ALREADY_RESOLVED_KEYS` too, or the general trigger expander (see "Trigger
evaluation" above) will blindly substitute its real body and silently undo the exclusion — the
same defect class the `country_uses_bio_ships` regression already taught this project once.

**Icons — reported, not vendored, for origin/ethics_or_civic.** `common/civics`/`common/origins`/
`common/ethics` aren't vendored for any source, so there's no icon file for these two gate kinds.
`Gate.icon` is nullable; the client renders the label alone when null (see "Gate-polarity/nested-
OR fixes" below for why this replaced an earlier, worse fallback).

**OR-context (`alternative`) gates.** A `has_technology`/perk/origin/civic leaf sitting inside a
real source `OR` is marked `alternative: boolean` (`GateMatch`/`Edge.groupId`-style tracking, OR
ancestry independent of negation polarity) — label wording is `"or: <name>"` for an alternative
gate, `"Needs <name>"` only for a genuinely unconditional one. Real corpus: 11/25 (44%) of real
`has_technology`-under-`potential` occurrences sit inside an `OR` (e.g. `tech_torpedoes_1`/
`tech_missiles_1`'s Riddle Escort requirement, non-bio-ship empires already qualify a different
way). A second field, `appliesToEmpireTypes` (nullable `EmpireTypeConstraint`), reuses
`pipeline.edge_constraints`' existing per-edge axis constraint for a `"technology"`-kind
alternative gate backed by a real `potential-gate` edge — the client filters the badge out
entirely for a profile the edge doesn't apply to, rather than showing a misleading requirement.
**Dangling "or:" downgrade**: when a technology's emitted `gates` list ends up with exactly ONE
entry and it's the alternative one (its real OR-sibling isn't itself gate-shaped, e.g. a district
check), it's downgraded to a plain "Needs X" (`pipeline.dataset_emit._downgrade_dangling_
alternative`) — deliberately NOT when `appliesToEmpireTypes` is non-null, where "or:" is correct.
Real corpus: 20 technologies.

**Nested AND-of-OR gates.** `GateMatch.group_id` (mirrors `Edge.groupId`) names the specific
`OR`/`NOR` block a gate is a direct child of, so an unconditional requirement (e.g. "Needs
Galactic Wonders") never reads as a flat peer of a choice beneath it (e.g. "or: Mechromancy" /
"or: a tradition"). The client nests same-`groupId` gates under their own "Need one of:" cluster.
Real corpus: 1 technology mixes unconditional and grouped matches (`giga_tech_the_vat`).

**Gate-polarity fix.** `_leaf_negated` XORs three independent negation channels: a `NOT`/`NOR`
wrapper ancestor, the `!=` operator, and a leaf's own literal `= no` VALUE (Clausewitz's other way
to write negation, no wrapper at all — the original bug: only the wrapper channel was checked).
Safe to apply unscoped — `= no` occurs only on `is_wilderness_empire` in the real corpus (31
technologies, all boolean-shaped). `can_research_technology` was removed from gate classification
entirely — it means "this OTHER technology isn't currently locked out" (an eligibility fact), not
`has_technology`'s "you have already completed this" — 1 real literal occurrence, but gate
propagation had inherited the mis-badge onto 15 descendants.

**Gates PROPAGATE down `prerequisite` chains.** A technology whose only real requirement is "my
prerequisite needs the gate" previously showed no gate at all. `pipeline.dataset_emit.
build_base_dataset` computes, for every rendered technology, the union of its own DIRECT gates
plus every `prerequisite`-ancestor's gates (transitively, via topological order), deduplicated by
`(kind, refId)` — direct declarations always win the dedup. Two new `Gate` schema fields carry
this: `inherited: boolean`, `sourceTechnologyId: string | null` (the original declaring
technology). Deliberately scoped to `prerequisite` edges only, NOT `potential-gate` — see Open
Items.

**`on_enabled → add_research_option` ascension-perk grants are a gate source too.**
`ap_galactic_wonders`'s (Gigastructures-overwritten) `on_enabled` unconditionally grants
`tech_ring_world`/`tech_dyson_sphere`/`tech_matter_decompressor` — all three structurally
unreachable any other way (`weight_modifier = { factor = 0 }` unconditionally). These 3 get a
direct `ascension_perk` gate (`pipeline.dataset_emit.ADD_RESEARCH_OPTION_PERK_GRANTS`),
deliberately NOT `tech_mega_engineering` (also granted this way, but remains reachable normally
too, so a gate would overstate a real requirement). DISPLAY-only — does not make these three
LOCKED for axis-excluded profiles, since their own `potential` never references the perk.
**Cosmogenesis-locked technologies (Nano-Assembler, Polyatomic Crucible, and the "tensile
buildings") are `weight_modifier`-based, not `potential`/gate-based** (`factor = 0` unless a
crisis-level condition, or the already-known `@giga_amb_flag` mod-config toggle) — surveyed twice
(the second time specifically to check Nano-Assembler/Polyatomic Crucible for a missed perk
requirement — none found in raw source), correctly NOT gate-classified, since that would conflate
weight and availability (a category error this project's rules already warn against).

**Current real corpus totals: DIRECT gates 107 instances (48 ascension_perk + 14 origin + 24
ethics_or_civic + 21 technology) over 83 directly-gated technologies. TOTAL (direct + inherited)
214 instances (104 ascension_perk + 16 origin + 61 ethics_or_civic + 33 technology) over 147
gated technologies, 47 of which carry more than one gate instance.** Full move-by-move history —
every intermediate count and which fix moved it — lives in `docs/BUILD-LOG.md`.

The spec's original "Tetradimensional Engineering" gate example was checked against the real
corpus and found wrong (it gates ascension perks, not a technology) — corrected once in
`spec/P-03-gates.md`, then found stale again since that replacement pair is one of the redundant-
prerequisite-plus-gate pairs excluded from display. A real still-valid example: any
`tech_lathe_*` → `tech_cosmogenesis_world` pair.

**Dangling "or:" downgrade extended to a single group nested inside a longer list — real bug fix
(Item 3b, a later session, user-reported).** The existing downgrade (above) only checked the
WHOLE `gates` list's length; it missed a `groupId` with exactly ONE member sitting alongside other
gates/groups — real corpus example: `tech_cloning`'s own direct gate ("Driven Assimilator") formed
a 1-member group next to a genuine 2-member INHERITED group (`tech_genome_mapping`'s "Rogue
Servitor"/"Genesis Architects"), so the card showed a dangling "or: Driven Assimilator" primary
badge and the popup rendered a "Need one of:" cluster containing a single, non-choice entry.
`pipeline.dataset_emit._downgrade_dangling_alternative` now also checks per-`groupId` size after
the whole-list check, downgrading any lone-member group the same way (`alternative: false`,
`groupId: null`, `"or: X"` → `"Needs X"`), regardless of how many other gates/groups the technology
carries. `#detail-popup`'s CSS also gained explicit `overflow-x: hidden` and `overflow-wrap`
safety on gate rows as defence-in-depth against a long localised name bleeding past the fixed-width
panel.

### Tiers

Tier range is **not** bounded. ACOT pushes tiers to T9 and beyond. Enumerate tier bands from
the data. No fixed upper bound anywhere in layout, LOD, or band labelling. Measured against the
real 973-node rendered corpus (D-18, then Item 2c): 10 declared-tier bands (T0-T9) plus the terminal Repeatables band.

**A node's band is its own declared `tier` field — never adjusted by graph depth (D-13,
corrected from an earlier draft that promoted a node's displayed position) — with one declared
exception: repeatable technologies band into the terminal Repeatables band regardless of their
own tier, and badge repeat count instead of tier on the card. See "Repeatables" below and D-13 in
`spec/decisions.md` for the full reasoning, including why this exception is not a return of v1's
band-header bug.** Tier is vanilla's and Gigastructures' own vocabulary; a band labelled "Tier 5"
contains exactly what the mod calls tier 5. Computed longest-path position still exists, but
purely as internal geometry — it orders technologies horizontally within a band's sub-grid and
gives the router a consistent signal for backwards edges, and is never displayed as a number.
**Within a shared depth slot, zero-cost technologies sort left of costed ones (Item 3a, a later
session, user-reported: zero-cost technologies appearing right of costed ones read as backwards
progression).** `pipeline.layout.compute_layout`'s sort key gained a zero-cost tie-break
(`same_band_depth`, then zero-cost-first, then `computed_position`, then key) — this only ever
reorders members that ALREADY share a `same_band_depth` value, exactly where D-17 permits free
reordering; it never changes which depth slot a node occupies, so it cannot violate D-17's own
invariant (a node never rendering left of/in line with its own prerequisite). No real case was
found where D-17 forbids the preferred order — the two constraints operate at different levels
(depth slot vs. position within a slot) and never conflict.
**Backwards edges are consequently real and expected**: an edge in a later band than its
dependent, whenever the tail's own declared tier is higher. **Record this as a per-kind
decomposition, never a single number — it has moved three times purely through re-scoping.**
Measured over the full P-14 three-kind edge set (989 edges: 888 `prerequisite` + 76
`alternative` + 25 `potential-gate`): **34 backward total = 25 `prerequisite` + 2 `alternative` +
7 `potential-gate`.** `prerequisite`/`alternative` both stay within 1-2 bands back — P-8 routes
these through the inter-band gutter, a build MUST NOT warn or fail merely because one exists.
`potential-gate` does NOT fit that characterization: its 7 backward edges reach up to **5 bands
back** (a `has_technology` gate can reference any technology anywhere, unlike a formal
prerequisite chain) — its routing treatment is `TODO(Stage 3)`, deliberately deferred to a real
rendered canvas rather than designed blind; see `spec/P-08-connectors.md`. (History: originally
27/891 — `prerequisite`-only, under the initial `levels < 0`-only repeatable rule; then 27/881
once repeatable membership was corrected to 88 nodes; the 27 always decomposed into 25
`prerequisite` + 2 `alternative` once `alternative`-branch members stopped being flattened into
the same list — the `potential-gate` figure was never counted at all before this session.) See
D-13 in `spec/decisions.md` for the full reasoning, the reconciliation, and worst cases.

**Tier-source audit** (prompted by v1's reported wrong-placement failures — checked the source of
every rendered node's declared tier, not assumed correct; pre-D-18 figures, not re-verified
against the 977-node closure since none of the 3 dropped ACOT technologies belonged to the
inline_script/@variable-tier subsets this audit tracks): of 980 rendered nodes, 930 (94.9%)
have `tier` literal on the raw, unexpanded technology block; **50 (5.1%) — all
`giga_tech_repeatable_*_cap` technologies — only get a `tier` field via `inline_script`
expansion** (`giga_mega_repeatable.txt`'s template), exactly the bug class that produces wrong
placement if expansion is skipped. 0 rendered nodes lack a resolvable declared tier after
expansion — but the correct policy going forward is a **hard build failure** for any that ever
do (CLAUDE.md/P-2: "the build fails rather than emitting a partial dataset"), never a silent
default tier. 83 nodes (8.5%) declare `tier` as a `@variable` reference (4 distinct variables,
all currently resolve, none currently subject to a cross-source scripted-variable overwrite) —
but **`pipeline.overwrites.resolve_variable_overwrites` only checks `cost`/`weight` for
cross-source variable overwrites, not `tier`** — a currently-latent blind spot (zero real impact
today) worth closing before Stage 2's real dataset build, not urgent now. 2 nodes
(`tech_adaptive_combat_algorithms`, `tech_biomechanics`) have their declared tier changed by a
P-15 technology-block overwrite (Vanilla → ACOT) — already correctly handled by existing P-15
machinery, since it's a literal field difference, not a variable-indirection issue.

### Colour and pattern

**Superseded by D-16's row re-axis (`spec/decisions.md`) — "background encodes research area" is
no longer the per-card rule.** Colour and pattern now encode the ROW, not the card: an
area-coloured header chip on a category row, faction colour and pattern as row backing on a
faction row, cards themselves neutral dark. Rare/dangerous outline and badge remain the one
per-card exception below, unchanged by the re-axis. **Research area is deliberately NOT
colour-encoded inside a faction row** — a technology that is both crisis-sourced and, say,
`voidcraft` shows its faction's colour, not its area's, once it's in that faction's row. This is
an accepted loss, stated explicitly so it isn't rediscovered as a bug later: faction membership is
mutually exclusive with category under D-16's row model (a technology is in exactly one row), so
there is no second colour channel left to carry area once a technology is in a faction row — the
row itself only has one colour to give. (Client rendering itself is a later slice; this section
states the rule the renderer must follow, not that it's built yet.)

Outline encodes research area unless the tech is rare or dangerous, in which case that takes
priority. Dangerous outranks rare. A tech that is both gets a 45° split outline, dangerous red on
the top-left half. (This per-card outline rule is unaffected by the row re-axis — it's about the
CARD's own outline, not its background.)

Colour is never the sole carrier. Rare and dangerous each also get a card badge. The LOD shedding
sequence is one shared table (spec/S-03): gate label and repeatable shed first (<60% zoom), then
rare (<35%), then gate icon and tier badge (<20%), then dangerous last of the badges (<10%,
deliberately kept longest since it's safety-critical), then crisis patterns go solid (<7%), then
the node reduces to a flat coloured block (<5%). Rare and dangerous do **not** shed together, and
neither sheds "at the same threshold as the gate label" — see spec/S-03 for the authoritative
table rather than restating specific thresholds here.

Crisis factions: Aeternum, Blokkats, Compound, Sirenalia, Katzenartig Imperium. Faction
assignment is derived from tech ID, then from `potential`/prerequisites, then from a checked-in
manual override file for the remainder. **This derivation (`pipeline/crisis_faction.py`) is
completely unchanged by D-16** — D-16 only changed what CONSUMES the classification (row
selection instead of lane selection); see D-16 in `spec/decisions.md`.

**Connector colour (P-8) is a single neutral colour for every edge, not tail-classification
colour** — `spec/P-08-connectors.md` is corrected to match the shipped Stage 3 slice 3
implementation (`client/src/tokens.ts`'s `EDGE_COLOR`); see that spec file and CLAUDE.md's
"Slice 3 — edges" bullet for the original decision and reasoning.

Exact hex values live in `tokens/` as the single source of truth, consumed by node rendering
and connector rendering alike. Do not hardcode colours in components.

Palette signed off: Aeternum `#823269`; Blokkats node fill `#2A6B2A` with pattern stroke
`#63A85C` (`#1C451C`, the authentic flag colour, reserved for tier-band/lane backing, not node
fill); Compound `#2F137F`; Sirenalia `#B0338C` with high-contrast sweeping bands; Katzenartig
`#2E3F98` with `#CC9429`.

### Repeatables

Shown on the card and in the popup as `Repeatable: ×40`, or `Repeatable: ∞` when unbounded.
**Cost display**: base `cost` (first-level, primary) plus `costPerLevel` (scaling rate,
secondary) — never `costPerLevel` alone, never omitted for a repeatable card. See
`spec/P-02-layout.md`'s "Cost display" section for the full rationale (in-game cost is
approximate regardless of empire state; the scaling rate is the one figure the card can state
truthfully) and the "Prerequisites"/schema sections for how a null `cost` (5/973 rendered nodes as
of D-18 — a later correctness pass resolved 10 of the originally-reported 15 via their `cost`
block's own `factor` sub-field, see `pipeline.dataset_emit._resolve_cost`'s docstring —
unresolvable, never guessed at) is represented.

**A literal zero cost and an unresolvable (`null`) cost both render NO cost panel — user decision
(a later session, Item 2a).** Distinguishing "this costs nothing" from "we couldn't work out what
this costs" is meaningless to an end user; both collapse to the same "no panel" treatment on the
card and in the popup (`client/src/main.ts`'s card cost line and the popup's `field-value`
block). Previously a zero cost rendered `Cost: 0` and a null cost rendered nothing (card) or
`Cost: unresolvable` (popup) — three different signals for what the user experiences as two
states worth distinguishing (has a real cost / doesn't). This is purely a client display decision
— the pipeline still emits the real resolved `cost` value (`0`, a positive number, or `null`)
unchanged; nothing about `_resolve_cost` or the schema changed.

**This is D-13's one declared exception to "bands are declared tier, full stop"**: a repeatable
technology bands into the terminal Repeatables band regardless of its own declared `tier`, and its
card badges repeat count instead of the tier badge. `tier` is still resolved, still validated
(`UnresolvedTierError` applies unchanged, no exemption), and still emitted — it stays meaningful
for internal sub-grid ordering and the detail popup, it just isn't what the band header or card
display. This is not v1's bug repeated: v1's failure was a band header making a FALSE claim about
the cards under it ("TIER 6" over T5-badged cards); here the band header asserts repeatable-ness
and the card asserts repeat count, and both are true at once. See D-13 in `spec/decisions.md` for
the full argument — read it before "fixing" this as an inconsistency.

**Membership is "source declares a `levels` field at all," not "`levels` is negative."** Corrected
against a user's v1 screenshot (a card badged "T5 x5"), not caught by any test: the original
`pipeline.layout.is_repeatable` only tested `levels < 0`, which is real for 76 of the corpus's
repeatable technologies but misses 12 more that declare `levels` as a positive **finite** cap (5,
20, or 40) on an otherwise identical `cost_per_level` shape — including
`tech_repeatable_reduced_building_cost` ("Gravitational Analysis"), the exact node visible in the
screenshot. Corrected membership is **88 nodes**, not 76. This set is deliberately distinct from
the 50 `giga_tech_repeatable_*_cap` inline_script-tier-only nodes (CLAUDE.md's "Tiers" section) —
every `_cap` node happens to be repeatable (a proper subset of the 88), but 38 of the 88 are
repeatable without ever going through inline_script tier expansion. Conflating the two sets is a
distinct bug from either finding alone.

**Sink property, verified over the corrected 88-node set**: every prerequisite edge touching a
repeatable node is non-repeatable → repeatable; zero run the other way or repeatable → repeatable.
A repeatable node therefore never sources an edge at all, so it can never source a backward edge
and the Repeatables band needs no intra-band edge routing.

### Repository links

Three branches, always populated, never dead. Gigastructures permalink pinned to the build
commit, targeting file and line range, where an override exists. ACOT/AoT-sourced technologies
link to that mod's Steam Workshop item page (no commit-pinned permalink is possible for a
Workshop item, and it isn't vanilla either). Otherwise a Stellaris wiki link. CI validates that
wiki anchors resolve and falls back to a wiki search URL where they do not.

### Research weight

Base weight prominently, expandable modifier list beneath. No evaluated weight — static analysis
cannot produce a number that is right often enough to present authoritatively.

**Zero weight IS an availability fact — user decision (Item 2b, a later session), a carve-out on
top of the rule above.** "Weight is a separate concern from availability" stands for weight as a
gradient — a modifier that boosts or reduces a nonzero weight stays purely a weight concern, never
folded into `state`. But a `weight_modifier` entry whose own `factor` is a literal `0` is
Stellaris's own idiom for "this technology cannot currently be drawn as a research option at all"
— functionally a gate, not a gradient. The motivating case: Cosmogenesis-locked technologies
(Nano-Assembler, Polyatomic Crucible, the "tensile" buildings) — a prior session correctly found
these `weight_modifier`-based, then wrongly concluded that meant no user-facing treatment at all.

**Implemented**: `pipeline.dataset_emit._weight_gate_condition_blocks` extracts every zero-factor
`weight_modifier` `modifier` entry's own condition (siblings of `factor`, `factor` itself
stripped) per rendered technology — deliberately `weight_modifier` only, never `ai_weight` (which
governs AI empires' own choices, not what the player is offered). Each condition is
scripted-trigger-expanded exactly like a `potential` block, then evaluated through the SAME
unchanged Kleene evaluator (`pipeline.availability._apply_weight_gate`) as an additional check
layered onto the technology's `potential`-based result, only when that result is AVAILABLE: if
the zero-factor condition resolves definitely TRUE for a profile (the modifier fires, weight is
currently zero), the technology downgrades to LOCKED with a reason naming the raw condition; if it
resolves UNKNOWN, it downgrades to UNCERTAIN the same honest way any other undecidable leaf does.
A technology already LOCKED/UNCERTAIN/CONFIG_GATED for a real `potential`-block reason is
unaffected — the more specific existing reason wins.

**Real corpus: 248 rendered technologies (301 zero-factor `modifier` entries — some carry more
than one) carry a `weight_modifier` factor=0 branch.** This is materially broader than the
motivating Cosmogenesis example — the same idiom is Stellaris's standard mechanism for excluding a
tech from the weighted draw under ANY condition, used throughout vanilla for ordinary things like
"don't offer this terraforming variant when the empire has no matching planets"
(`tech_mountain_range`/`tech_volcano`/`tech_toxic_kelp`/... via `num_owned_planets`), policy/civic
toggles (`has_policy_flag`), and FE/crisis-chain content, not just mod-configuration or
crisis-progression gates. Effect, measured directly (not estimated): **unconditional uncertainty
31/973 → 115/973 (11.8%); worst profile-dependent rate 16/973 (1.64%) → 58/973 (5.96%) — crosses
the 3% warn threshold but stays well under the 10% hard ceiling; union 53 → 180.** 39 technologies
gain a real LOCKED verdict for at least one profile that was previously AVAILABLE (mostly Fallen
Empire/crisis-chain content genuinely never offered through the normal weighted draw); 124 more
gain an UNCERTAIN verdict for at least one profile that was previously AVAILABLE (dynamic in-game
state the evaluator correctly can't resolve — planet counts, policies, crisis levels). This is a
considered, reported tradeoff per this project's own "report honestly, don't smooth over a worse
number" discipline (the same posture the scripted-trigger expansion session took) — the ceiling is
not breached, and the new signal is real and more informative than silence, even though it moves
the warn-threshold figure. The pinned corpus test
(`tests/test_availability_corpus.py::test_uncertain_count_and_per_profile_breakdown_pinned`) was
updated deliberately for this move, not silenced.

### Research path

**Implemented (P-12.9, a later session — `spec/P-12.9-research-path.md`).** The old placeholder
`{ancestors, shortestChain}` shape (a plain profile-blind `prerequisite`-edge BFS, `alternative`
edges never resolved — v1's own two documented failures: profile-blind traversal and flattened
`OR`-branch choices) is replaced by `researchPaths[technologyId]` = `{status, steps, totalCost,
totalCostIsEstimate, estimateReasons, configGatedTarget}`, precomputed per (technology, profile)
at build time in the empire overlay (`pipeline.dataset_emit._build_research_paths_for_profile`,
memoised once per profile across all 973 targets sharing it). `status` is `"path"` (ordinary),
`"config-gated"` (the target is one of the 50 `giga_tech_repeatable_*_cap` technologies — its own
cost is excluded from `totalCost` entirely, per D-13's sink property: a config-gated technology
can only ever be a path's own target, never an interior step), `"unavailable"` (no `steps` array
at all — the target ITSELF is `locked`), or **`"blocked"`** (Item 2d, a later session — no `steps`
array either, but the target's own state is `available`/`uncertain`; a plain, non-`alternative`
prerequisite somewhere in its ancestor chain is `locked`/`config-gated`, or an `alternative` group
has zero viable candidates). `"unavailable"` and `"blocked"` are deliberately DIFFERENT statuses,
not one shared state — see "When there is no route at all" below for why. An `alternative`
(`OR`-group) is resolved to whichever VIABLE
(`available`/`uncertain`, never `locked`/`config-gated`) candidate has the cheapest FULL recursive
closure cost — never just its own declared cost, which is what fixes v1's "chose a branch without
expanding its own prerequisites" bug — and the chosen step's own `alternatives` list names the
other viable siblings, never flattened away. `totalCost` for `status == "path"` includes the
TARGET's own declared cost (confirmed the only reading that reproduces the spec's own worked
example: `tech_mega_engineering` regular/mechanical/non-nomadic = 74,750 exactly, the 15-ancestor
sum plus the target's own 24,000 — the ancestor-sum-only reading does not); for `"config-gated"`
it excludes the target's cost, per section 5. An `uncertain` step or a `null`-cost step both stay
in the path (never excluded, matching D-10's "unknown ≠ excluded" discipline) and set
`totalCostIsEstimate`/`estimateReasons` (`"uncertain-availability"`/`"unresolved-cost"`,
composable). Every step's `name`/`icon` is D-14-substituted for the selected profile.

**Real corpus, current (re-measured this session — the original spec's 3 headline figures had
gone stale, per its own worked examples): OR tie-break (cheapest-total-cost vs. fewest-steps)
disagrees on 12 of 72 genuine 2+-viable-candidate group×profile choices** (of 420 total
group×profile evaluations over the corpus's 35 real `alternative` groups, 408 have ≥1 viable
candidate) — cheapest-total-cost is genuinely load-bearing now, not a defensible-either-way
footnote the original survey's "0 disagreements" figure implied.

**A real, previously-unmeasured finding, corrected against an earlier session's own inherited
assumption, not suppressed to match it: the "dangerous" sub-case (an ancestor chain broken while
the target's own state stays available/uncertain) is NOT zero on the current corpus.** Confirmed
directly against raw source, not assumed: `tech_ehof_spinal`'s `prerequisites` block
unconditionally (never inside an `OR`) requires `tech_arkship_tier_3`
(`giga_09_ehof_other.txt:260`), whose own `potential` is `is_nomadic = yes`
(`00_nomads_dlc_tech.txt`) — locked for every non-nomadic profile; `tech_ehof_spinal`'s own state
resolves `uncertain` (an unrelated `has_arcane_generator` flag), never `locked`. Real corpus: 78
distinct technologies / 472 (key, profile) pairs hit this.

**When there is no route at all — CORRECTED (Item 2d, a later session): `spec/P-12.9-research-
path.md` section 6 originally folded "target itself locked" and "ancestor chain broken while the
target is fine" into ONE status (`"unavailable"`), on the strength of a stale claim that the two
always coincide (2 of 980 technologies, both cases). That claim was never true of the real, current
corpus (78/472, above) — a documented figure trusted across sessions without being re-verified,
the same failure mode as the `has_ancrel` defect (see "Trigger evaluation" above). Fixed: a new,
distinct status, `"blocked"`, carries `blockedBy: {technologyId, name, reason}` naming the specific
ancestor whose own locked/config-gated state broke the route (one representative non-viable member
for a broken `alternative` group, not every one) — `pipeline.dataset_emit._UnreachablePath` now
carries the blocking key from its origin raise site up to the target-level catch, unchanged, so the
FIRST (deepest) real cause survives, not a synthesized one. `"unavailable"` now means ONLY "the
target's own state is locked" — 0 conflation with the ancestor-chain case going forward.
`pipeline.dataset_emit.build_diagnostics`'s `unresolvableResearchPaths` field
(`spec/P-12.9-research-path.md` section 6's tripwire) now tracks every `blocked` pair directly,
same 78/472 figure at the time this status was introduced.**

**The 78/472 figure moved again, same session, purely as a consequence of Item 2b (above) landing
alongside Item 2d — reported together honestly, not chased back down to the smaller pre-Item-2b
number.** Item 2b's weight-gate LOCKED downgrades add real new ancestor dead ends throughout the
prerequisite graph, and every downstream descendant of a newly-LOCKED technology now legitimately
hits the `"blocked"` case too. Real corpus, both fixes together: **958 (technology, profile) pairs
/ 116 distinct technologies are `"blocked"`.** This is not a bug in Item 2d's own mechanism — the
mechanism is proven correct against the smaller pre-Item-2b corpus and against direct raw-source
tracing (`tech_ehof_spinal`, above) — it is downstream fallout of Item 2b correctly surfacing more
real dead ends. Do not "fix" this by reverting Item 2b's weight-gate fold-in to make the smaller
number reappear.

**Nano-Assembler display bug fixed, same session, independent of the status split.**
`giga_tech_fe_megaworkshop_1` ("Nano-Assembler") has NO `prerequisites` at all — a legitimate
zero-step path (research it directly, `totalCost` = its own declared cost) — but the client
rendered "Research path (0) / none / Total: 70,000 (estimate: uncertain-availability)", which
reads as contradictory (a zero-step list next to a nonzero total). Fixed in `client/src/main.ts`'s
`renderResearchPath`: a zero-step `"path"`/`"config-gated"` status now renders "No prerequisites —
this is the direct cost of researching it" instead of the bare word "none", regardless of which
status it ends up with.

CLIENT: selection-triggered (matches v1's own trigger — no persistent "goal technology" pin, an
explicitly deferred feature). `client/src/main.ts`'s `openPopup` fetches the current profile's
overlay unconditionally (previously only for a non-`available` technology) and renders a
`renderResearchPath` section: ordered steps with per-step cost and an `uncertain` badge, the
running total with its estimate note where set, `alternatives` shown inline per OR-chosen step,
the `config-gated` target's own subject/template note, and (Item 2d) a distinct `"blocked"`
explanatory line naming `blockedBy`. Verified with real screenshots (an `OR`-choice path, the
nomadic Arkship-branch substitution, an `uncertain`-step estimate, an `unavailable` target, a
`config-gated` target, a `blocked` target naming its blocking ancestor, and Nano-Assembler's
corrected zero-step display) — zero console errors, all figures matching the pinned corpus tests.

### Localisation

English only for v1. The pipeline is language-parameterised so more languages are a build flag.



## `pipeline/layout.py` and `client/src/main.ts` geometry defects — full narrative (25k-restructure session)

Moved verbatim from CLAUDE.md's Rules section; the condensed rule statements now live in `docs/DEFECTS.md` ("Parallel geometry" and "Dict-keying" sections) with CLAUDE.md's Rules section keeping a one-line pointer to each.

- **The pipeline owns all geometry; the renderer consumes emitted positions and never recomputes
  them from a parallel formula.** Any renderer-side value derivable from emitted geometry
  (row/band extents, a cell's populated width) MUST be derived from the real emitted positions
  (`nodePositions`/`edgePolylines`), never reimplemented client-side from the same inputs
  `pipeline/layout.py` consumes. Found the hard way: `client/src/main.ts` once re-derived row/band
  geometry via its own copy of `pipeline/layout.py`'s formulas, and D-17's same-band depth-slot fix
  silently desynced it — row panels, tier tints and cell labels drew nowhere near their actual
  cards, no error, no failing test, caught only by a headless screenshot. Fixed permanently by
  deriving from real positions (min/max over emitted `nodePositions`, grouped by row/band), not a
  periodic re-sync — client and server geometry can't drift apart again regardless of future
  formula changes. A milder residual form remains: mirrored SCALAR constants (`CARD_WIDTH`/
  `CARD_HEIGHT`, gutter constants, `SUBGRID_WIDTH`, `AREA_ORDER`, `FLOATS_PER_EDGE_POLYLINE`,
  `MIN_STUB`) still kept in sync by hand since the dataset schema doesn't carry them as data —
  `CARD_WIDTH`/`CARD_HEIGHT` are the one genuinely load-bearing pair (they size the actual card
  draw call); flagged as a scoped follow-up, not fixed. See `docs/BUILD-LOG.md` for the full
  audit of what else was checked and ruled out.
- **A second, DIFFERENT defect class produced the same visible symptom (rows overlapping) a later
  session — do not confuse it with the parallel-formula bug above.** A sub-grid centring fix
  (`pipeline/layout.py`) keyed `column_member_count` by `(row_id, col)` alone, but `col` is
  BAND-RELATIVE (its cursor resets every band) — two physically different columns in different
  bands of the same row shared a dict key, silently summing member counts and driving the centring
  offset negative (real corpus: one node placed at row −16). A plain dict-keying bug, not a
  parallel-geometry violation — confirmed directly, not assumed. Fixed by keying on the full
  `(row_id, band_index, col)` triple, plus an `assert centre_offset >= 0` as a second line of
  defence. The existing test suite stayed green through this regression because nothing asserted
  the actual invariant (no two rows' card extents may intersect, no row index is ever negative) —
  the same "green suite proves self-consistency, not correctness" lesson D-17's unbounded-stacking
  bug already taught once. `tests/test_layout_corpus.py::
  test_no_row_overlaps_and_every_card_within_its_own_row_bounds` and `tests/test_layout.py::
  test_no_row_overlaps_when_the_same_row_spans_multiple_bands` are the missing invariant, each
  proven capable of failing against the broken code before being trusted on the fix.


## CLAUDE.md's former "Open items" full entries (25k-restructure session)

Moved verbatim from CLAUDE.md, which now keeps one line per open item plus a pointer here for the full reasoning/figures.

- **Wilderness/Frameworld as TOGGLES layered over the 12 profiles (not new axes): surveyed (Item
  2c, a later session), NOT implemented — real decision needed, user explicitly wants a
  recommendation.** The user's framing: two origins with the same shape (substantial exclusive
  content, `has_origin`-gated) is a pattern, not a special case — a toggle composes ("show me this
  as a frameworld empire") where a flat axis multiplies, and the two origins are MUTUALLY
  EXCLUSIVE, which bounds it to a 3-state dimension (neither / wilderness / frameworld), not two
  independent booleans.
  - **Scale, re-measured this session (methodology differs slightly from the original wilderness
    survey — see caveat below, not silently reconciled to the old number): wilderness affects 54
    technologies / 200 (technology, profile) pairs across the 4 hive-authority profiles; frameworld
    affects 8 technologies / 96 pairs across all 12 profiles** (frameworld's authority-restriction,
    if any, is UNCONFIRMED — `common/origins/` isn't vendored for any source, so its own `possible`
    block can't be inspected; simulated as unrestricted across all 12). Caveat: the wilderness
    figure was previously recorded as 41/973 (4.2%) / 148 pairs, hive-only; this session's
    re-measurement (54/200) used a direct true-vs-false leaf simulation rather than replicating the
    exact prior methodology bit-for-bit — flagged as an unreconciled discrepancy, not silently
    overwritten, since re-deriving the exact original method wasn't done. Either figure supports
    the same conclusion (both origins show a real, non-trivial availability difference).
  - **No other origin comes close in scale** — a full corpus survey of direct `has_origin = X`
    leaves found the next-largest at 2 technologies (`origin_shroudwalker_apprentice`,
    `origin_endbringers`, `origin_shroud_forged`, `origin_red_giant`), an order of magnitude below
    wilderness/frameworld — and `pipeline.gate_patterns.WRAPPER_TO_ORIGIN` confirms these two are
    the only origin-shaped scripted-trigger WRAPPERS registered at all. **Three states (neither /
    wilderness / frameworld) is enough** — nothing else in the real corpus argues for a fourth.
  - **Real emitted payload cost, MEASURED not estimated**: widening `availabilityMatrix` from
    12 to 36 slots (simulated directly against the real base dataset) moves the base dataset's
    compressed size **60,885 → 65,704 bytes gzip (+4.8 KB, +7.9%)** — negligible against the ≤2 MB
    base-dataset budget (spec/P-10), still ~30x headroom. A real built empire overlay for a
    simulated wilderness/frameworld profile is **54.2 KB / 54.5 KB gzip respectively**, essentially
    identical to an ordinary profile's overlay (currently ~56–64 KB) — overlays are explicitly
    OUTSIDE the ≤2 MB base-dataset budget (P-10's own scope statement) and are fetched one profile
    at a time (lazy, per-selection), so tripling the profile COUNT (12 → 36 files) does not
    multiply what any single session actually downloads; it multiplies the total artefact COUNT on
    disk/in a full prefetch, which was never the design's cost model anyway.
  - **`EmpireProfileIndex` (`pipeline/dataset_schema/empire_profile.py`) extends cleanly, no
    rework needed.** `AXES` is a plain list of `(name, ordered_values)` pairs with strides derived
    at import time from cardinalities, plus an import-time bijection assertion — adding a single
    3-valued axis (`("originToggle", ["neither", "wilderness", "frameworld"])`) is a one-line
    change that correctly yields `TOTAL_PROFILE_COUNT = 36` with zero special-casing, and models
    the mutual-exclusivity naturally (one 3-valued axis, not two independent booleans that would
    wastefully allow a nonsensical "both" combination).
  - **Icons: neither is vendored**, same finding as the existing "Icons — reported, not vendored"
    note under "Gates" — `common/origins/` isn't in any source's vendored tree at all, so a visual
    indicator would need a new source directory pinned and reviewed (a real, separate follow-up),
    not something this toggle feature can ship with today.
  - **Recommendation (not acted on, decision is the user's per the prompt's own instruction):
    implement it.** The scale is real (comparable to, or larger than, thresholds this project
    already treats seriously — e.g. the 3% D-10 warn threshold), the payload cost is negligible,
    the indexing mechanism already generalises correctly, and the only real blocker (icons) is a
    separate, already-known, already-scoped gap that doesn't block a text-only toggle. The main
    design work is client-side (a toggle control, `EmpireProfileAxes` consumption already
    data-driven per the closed "EmpireProfileIndex parallel-formula" item) plus extending
    `AXES`/`profiles` generation and wiring `is_wilderness_empire`/`giga_has_frameworld_origin`
    into `AXIS_FACTS` (currently `EXCLUDED_KEYS`-only, gate-display-only) the same way the three
    existing axes are.
- **Distinct research-path status for a broken ancestor chain: now closed (Item 2d, a later
  session).** See "Research path" above for the new `"blocked"` status and the corrected P-12.9
  section 6. Left here only so a future session's memory of "this was still open" gets corrected
  on sight.
- **Middle-click isolation (P-7) is fully specced (`spec/P-07-isolation.md`) and entirely
  unbuilt.** Middle-click (or long-press ≥400ms on touch, P-9) isolates a node together with its
  direct prerequisites/unlocks (user-adjustable depth, default 1 hop, full-closure option),
  traversing all three edge kinds distinctly styled per P-8 — deliberately differs from the
  research path (P-12.9), which is prerequisite-edges-only. Visibility mask over the static
  layout, never a re-layout. Adjacency lists (forward/reverse, per edge kind) must be precomputed
  in the dataset for O(1) traversal, inside P-10's 100ms budget.
- **No pipeline-test CI workflow exists** — `pytest` still runs manually/locally only.
- **`tools/collect_vanilla.py`'s GitHub-fetch-and-pin automation for Gigastructures, plus a
  scheduled CI staleness check, is still unbuilt** — see "Source data" above; the current manual
  pin is a deliberate stopgap.
- **Pattern tile for Blokkats** needs tracing to clean SVG from the supplied flag image — the
  current herringbone motif is a procedural placeholder, not traced art.
- **Sirenalia's accent shade and Katzenartig Imperium's chevron pattern are both flagged
  provisional** in `client/src/tokens.ts`'s own comments — Sirenalia's geometry (curved wave
  bands) was ported from v1, but its accent colour is still a placeholder; Katzenartig has no
  in-game reference at all and its pattern is inferred, not described art.
- **`potential-gate` edges' long-span (up to 5-band) backward routing** was left `TODO(Stage 3)`
  before a real rendered canvas existed to design against — re-check whether the v1-style router +
  gutter-router fallback (`docs/BUILD-LOG.md`'s rendering sections) has since made this moot.
- **ΔE2000/WCAG mechanical colour checks are still unbuilt** — S-1's own CI-enforced acceptance
  criterion (pairwise contrast across the full token set). Every colour token is a first concrete
  pick, checked by eye only.
- **`repositoryLink` isn't live-validated** (no network access at build time) and its `lineRange`
  uses the block's start line for both ends (the AST doesn't track an end-of-block line).
- **Gate propagation down `potential-gate` edges is a deliberately deferred scope boundary.**
  Gates propagate down `prerequisite` edges only (the formal "must research first" chain). A
  `potential-gate` edge (`has_technology` inside `potential`) is a different kind of dependency
  (an eligibility check, not a declared prerequisite); whether/how it should also propagate gates
  needs real corpus study before extending.
- **Looping edges: surveyed twice, none found geometrically.** Three independent geometric checks
  (X-direction reversal, a Y-axis "hook" shape, literal polyline self-intersection) against the
  current dataset found zero matching edges. If a user reports this again, ask for a screenshot or
  a specific technology name rather than re-running the same survey.
- **Hover vs. selection scope discoverability** — hover shows immediate neighbours only, selection
  shows the full ancestor/dependent closure; the split is correct but nothing in the UI hints that
  selecting reveals more than hovering does. A cheap, optional follow-up, not yet built.
- **Two technologies named "Confluence of Thought" are a known, genuine same-name pair, not a
  bug.** `tech_hive_confluence` and `tech_wilderness_confluence` are two deliberately-parallel
  vanilla technology lines (confirmed via raw source's own "# Wilderness" section header) — one of
  5 documented genuine same-name pairs in the mod. Not an overwrite-resolution or localisation
  error.

## HANDOFF.md's former "Methodology"/"Deliberately deferred"/duplicate-Architecture/duplicate-Locked-decisions/"What's built"/"Standing invariants" sections, in full (25k-restructure session)

Moved verbatim from HANDOFF.md, which now keeps only "what this is", "how we work" (verbatim), current headline figures, and a "where to look for what" pointer — everything else here duplicated CLAUDE.md (some of it, e.g. the old "ascension perks are gates, not profile facts" wording with no axis-lock correction, was a STALE duplicate at that) or was narrative/module-description material that belongs in this file. Headings below are HANDOFF.md's own former section headings, kept for orientation.

## Methodology that has worked — keep doing this

- **Evidence before design.** Every time a corpus assumption was checked rather than carried, it
  either broke or revealed something better. The localisation value-scanning rule, the
  `inherit_icon` resolution channel, the version-suffix identity question and three separate
  Clausewitz grammar rules all came from surveys, not reasoning. Ask Claude Code to survey with
  raw text and **report before implementing**, then review the findings before it proceeds.
- **Raw inspection only.** Never conclude anything about source syntax from output that passed
  through `repr()`, `pprint` or any formatter. A single misread `repr()` once produced a false
  "single-quoted strings exist" finding that drove real but baseless tokeniser changes. This is
  a rule in `CLAUDE.md`.
- **Iterative critical review.** Three rounds on the spec, each finding real structural problems.
  When asking for review, say explicitly not to manufacture findings if nothing is left —
  otherwise later rounds pad.
- **Prove a negative result before believing it.** A clean run means nothing until the detector
  is shown capable of a non-clean one. The round-trip mutation harness exists for exactly this
  reason and caught a comparator that would have passed both historical bugs.
- **Counts don't move silently.** When a reported number changes between sessions (352 vs 353
  files; 3 vs 2 malformed entries), reconcile it before proceeding. Both instances turned out to
  be real — one a discovery bug, one a deliberate reclassification.
- **A green test suite doesn't mean the classification is right — it means the classification is
  self-consistent.** `pipeline.layout.is_repeatable` shipped with `levels < 0` as the repeatable
  test, every test for it passed, and the corrected 980-node corpus run reported "0 unresolved
  tiers" — nothing in the suite could have flagged that 12 real repeatable technologies (positive
  finite `levels`, same shape otherwise) were being silently placed in ordinary tier bands
  instead of the Repeatables band, because no test encoded "the real corpus's repeatable
  population is 88, not 76" as an expectation — that number wasn't known to be wrong yet. It was
  found by checking a user's v1 screenshot (a card badged "T5 x5", which cannot exist under
  `levels = -1`) against the real corpus, the same "evidence before design" habit as the
  `repr()` bug above, applied to a screenshot instead of raw text. **What would have caught it
  without the screenshot**: a test asserting the repeatable count against an independently
  re-derived corpus figure (the same "counts don't move silently" discipline above, applied
  pre-emptively rather than after a number happens to be reported twice) — or naming the
  predicate's assumption explicitly enough in a docstring/comment ("assumes unbounded" without
  ever checking the corpus for finite repeatables) that a later reviewer would think to challenge
  it. Neither existed; the mechanism-level unit tests (`levels = -1` → True, `levels = 5` → False)
  tested the rule faithfully, which is exactly why they couldn't catch that the rule itself was
  wrong.
- **A defect class, found by pattern-matching across sessions rather than treating each fix as
  isolated.** Three separate components — tier resolution (P-2's tier-source audit), `pipeline.
  layout.is_repeatable` (above), and `unconditionalUncertainty` (Stage 2 cleanup session) — each
  independently produced a plausible, error-free wrong answer for technologies in the
  `giga_tech_repeatable_*` family. Two of the three (tier, `unconditionalUncertainty`) share an
  exact mechanism: the field in question only exists on the technology block AFTER
  `inline_script` expansion, and a component reading the raw block sees no field at all rather
  than an error — silently wrong, not loudly broken. The general form: **any component that
  acquires technology data by a route other than the full expanded canonical record is at risk of
  this failure mode, and `giga_tech_repeatable_*` is the reliable canary**, because enough of its
  data exists only post-expansion that a raw-block consumer fails silently. See CLAUDE.md's
  "Availability evaluator" section for the full write-up and the audit of every component's input
  route this prompted — one real, not-yet-triggered gap found (`pipeline/icons/resolve.py` reads
  raw blocks unconditionally, currently zero-impact but the same shape of risk), reported, not
  fixed, pending a scoped follow-up. ~~Follow-up~~ **Done, next session**: `collect_candidates`
  now takes expanded documents (`pipeline/icons/build.py::resolve_kind` parses+expands before
  calling it); verified zero-impact on the real corpus as predicted (every existing exact-count
  assertion held unchanged), plus a synthetic regression test proving the expanded-vs-raw
  distinction actually matters when a template DOES define an `icon=` field. See CLAUDE.md's
  "Small targeted correctness pass" bullet.
- **The defect-class hypothesis paid off directly, not just as a warning.** The same "Small
  targeted correctness pass" session's `unclassified` jump (7→57 unconditional-uncertain nodes,
  all 50 `giga_tech_repeatable_*_cap`) was initially read as expected fallout of fixing the
  raw-vs-expanded bug — a real fix revealing real, previously-invisible undecidable content. A
  follow-up review of the actual template found it wasn't undecidable at all: both leaves in its
  `potential` are mod-configuration toggles, one already resolvable, one (`_capped_r`) not yet
  taught to the evaluator. Recognising it turned an "opaque, unclassifiable" bucket into a
  fully-explained, DETERMINATE result — and revealed that `locked`/`uncertain` were both the
  wrong label for it, prompting a fourth `AvailabilityState` (`config-gated`). The number this
  produced (209) is numerically identical to the ORIGINAL, pre-any-correction figure — a good
  reminder that "the number went back to what it used to be" is not evidence nothing needed
  fixing; two real, unrelated corrections can net to zero by coincidence. See CLAUDE.md's
  "`giga_tech_repeatable_*_cap` correctly categorized — CONFIG_GATED" bullet for the full
  writeup.

## Deliberately deferred

- ~~**Deployment / GitHub Pages skeleton** for the real app is still postponed~~ **Done across
  two sessions — `deploy-spike/` deleted, replaced by a real pipeline with a deliberately
  PERMANENT (not interim) deploy model.** `client/` (TypeScript + PixiJS + Vite, foundation only,
  still no rendering logic) exists, typechecks cleanly, and builds. `.github/workflows/
  typecheck.yml` runs `tsc --noEmit` on every `client/**`/`dataset-types.ts` change — closed the
  `schema/generated/dataset-types.ts` "never actually typechecked" TODO from below: **zero
  errors**, verified three ways (see CLAUDE.md's "Stage 3 toolchain foundation is built" bullet).

  **Deploy model, decided in the second of these two sessions (D-15, spec/decisions.md) — read
  this before assuming CI can build anything**: the dataset cannot be built in GitHub Actions,
  ever, not as a temporary gap. Vanilla Stellaris requires a Steam account that owns the game;
  CI-side building would mean storing real Steam credentials as a secret (a security/ToS
  exposure) or redistributing extracted game files (foreclosed by this project's own
  never-redistribute-vendor-content rule). No automation closes this. Consequently:
  - The dataset is built LOCALLY (`tools/build_dataset.py`, where `vendor/` already exists) —
    **NOT committed to the repo** (`client/public/dataset/` is gitignored — an earlier session's
    opposite decision was reversed once the redistribution/git-bloat/staleness costs were
    weighed against the small deploy-cadence convenience of committing it).
  - `tools/deploy_local.sh` (new) builds the dataset, builds the client, zips `client/dist/`, and
    publishes it as a GitHub Release asset via the `gh` CLI — **not run for real this session**
    (creating a live Release is a "visible to others" action, left for a human to trigger).
  - `.github/workflows/deploy.yml` is `workflow_dispatch`-only: it downloads a named release's
    `dist.zip` and deploys it via the ordinary `actions/upload-pages-artifact`/`deploy-pages`
    steps. It builds nothing. Confirms Pages CAN deploy a build that happened elsewhere.
  - `client/public/dataset/integrity.json` (built into every local run, travels inside
    `dist.zip`): pipeline commit SHA + dirty-tree flag, `vendor/manifest.json`'s per-source
    provenance, which sources loaded, sha256 of every other artefact. **States provenance, does
    NOT verify it** — nothing can, given the constraint above. A byte mismatch is detectable; a
    false provenance claim is not, beyond trusting whoever ran the local build. Never describe
    this as CI-grade auditability in any future write-up.
  - Two alternatives were seriously considered and rejected as the PRIMARY model — a private
    artefact store (still needs a human to build+publish, just adds a hop) and CI building
    without ACOT/AoT (doesn't solve vanilla either way, and would make the canonical deployed
    site quietly different — 977 nodes, not 980 — by default). See D-15 for the full costing.

  **Icon atlases are now actually written** — closed a real gap the first of the two sessions
  left behind: `tools/build_dataset.py` built `base-dataset.json` referencing
  `technologies_0.webp` etc. but never wrote any atlas image file at all; the site could not
  render a single icon. Fixed: every sheet is encoded to WebP+PNG, content-hashed, referenced
  correctly. **Real measured total: 4,826,990 bytes WebP (4.60 MB) + 5,994,998 bytes PNG
  (5.72 MB) = 10,821,988 bytes combined**, verified loadable end to end (a real `Assets.load()`
  fetch, a real `Texture` tile crop, a real PixiJS `Sprite` drawn to canvas — not just "file
  exists on disk").

  **ACOT/AoT-absent builds get a loud, specific diagnostic.** Building without ACOT/AoT yields
  **977 rendered nodes, not 980 − 7 = 973** — see CLAUDE.md's "Stage 3 toolchain foundation is
  built" bullet or D-15 in spec/decisions.md for the full mechanism (4 vanilla technologies ACOT
  overwrites turn out not to be rendered at all in the FULL build, and reappear once ACOT is
  absent). `pipeline.dataset_emit.build_diagnostics` now reports this by name
  (`vendorSourcesLoaded`/`placeholderTechnologiesAbsent`/
  `vanillaTechnologiesRevertedFromAcotOverwrite`), and `tools/build_dataset.py` prints a loud
  console warning too. Both affected-technology lists are maintained constants with their own
  regression tests against the full corpus (not dynamically derivable — 3 of the 7 placeholders
  are reachable only through ACOT's own internal prerequisite chains).

  Historical record of what `deploy-spike/` (deleted) originally proved, kept for context since
  its four findings were re-confirmed against real data and a real hosting-layout simulation,
  not just inherited on faith:
  - Relative paths resolve correctly under the project subpath
    (`tempest113.github.io/Gigastructural-Engineering-Tech-Tree/`), not the domain root.
  - `.f32` side-file served as `application/octet-stream` — unrecognised extension falls back
    correctly, not mangled or refused.
  - Float32Array decoded to clean 0.5-increments (0.0, 0.5, 1.0, 1.5 …), confirming
    little-endian round-trips end to end. A byte-order mismatch would have produced garbage.
  - GitHub Pages serves gzip on BOTH `application/json` and `application/octet-stream` — measured
    9.34x on a ~982 KB synthetic JSON artefact against the 6x assumed in the P-10 estimate.
- ~~**GitHub Pages cache headers are not configurable — a Stage 3 decision, not something to act
  on now.**~~ **Decided.** `tools/build_dataset.py` content-hashes every artefact filename
  (`<name>.<sha256[:10]>.<ext>`, including icon atlases as of the second Stage 3 session) except
  two stable, unhashed entry points: `dataset/manifest.json` (the client fetches this first and
  reaches every other artefact only through it) and `dataset/integrity.json` (the provenance
  record, needs a stable name to be findable).
- **Blokkats SVG pattern tile.** Needs tracing from the supplied flag image. Unrelated to
  pipeline work, not blocking anything.

---

## Architecture

Three stages, boundaries load-bearing:

1. **Extract** (Python, CI) — parse Clausewitz script and localisation, decode icons, pack
   atlases. **Complete.**
2. **Compute** (Python, CI) — resolve overwrites, build DAG, evaluate triggers per empire
   profile, assign layout, route edges, emit dataset. **Complete and real.**
   `pipeline/dataset_emit.py` emits all five schema-validated artefacts (base dataset, empire
   overlay, detail payload, search index, diagnostics) against the full vendored corpus. Not
   wired into a CI build command (deliberately — see D-15 in `spec/decisions.md` and CLAUDE.md's
   "Source data"/deploy notes: the dataset can never build in CI, it's built locally via
   `tools/build_dataset.py` and shipped through `tools/deploy_local.sh`).
3. **Render** (TypeScript + PixiJS, browser) — load dataset and draw it. **In progress.** Static
   render, camera/LOD, edges, row/band layout, badges, hover/selection/popup, search, empire-
   profile switching, and the research-path popup are all built — see CLAUDE.md's "What's built"
   pointer and `docs/BUILD-LOG.md`'s Stage 3 sections for the full slice-by-slice record. Not yet
   built: middle-click isolation (P-7) — see CLAUDE.md's Open Items.

The browser never parses Clausewitz and never computes layout. The dataset schema is a
cross-language contract: JSON Schema in `schema/`, TypeScript types generated from it, Python
output validated in CI. **This contract is now written** — five artefacts (base dataset, empire
overlay, detail payload, search index, diagnostics), each independently `schemaVersion`'d — see
"What's built" below.

## Sources and load order

Ordered, lowest first: vanilla Stellaris 4.5 → Gigastructures (pinned commit, GitHub) → ACOT →
AoT. ACOT and AoT are Steam Workshop only, cannot be pinned, vendored manually. AoT requires
ACOT. Overwrite resolution is whole-key replacement, never field-level merge.

Source files live in gitignored `vendor/`, populated by `tools/collect_vanilla.py`. Nothing
third-party is ever committed.

## Locked decisions

Full detail in `spec/` (23 files) and `CLAUDE.md`. Read `CLAUDE.md` before making any design
call — the headlines below are a pointer, not a substitute:

- **Empire model**: three independent axes — gestalt/authority (regular, hive, machine),
  shipset (mechanical, biological), nomadic (yes/no). Twelve profiles. Origins not an axis.
- **Ascension perks are gates, not profile facts.** The tree shows what you'd need, never
  assumes you have it.
- **Mod scope**: renders vanilla + Gigastructures, plus ACOT/AoT technologies only where they
  fall in the rendering-scope closure (prerequisite edges only) of a rendered technology. Node
  set is profile-invariant. Separately, a per-profile structural-reachability check over all
  three edge kinds drives lock state — these two computations are deliberately distinct and
  named so they don't drift back together. Conflating them is a correctness bug.
- **No primary prerequisite.** Multiple prerequisites are all equally required.
- **Layout (corrected — see D-13/D-16 and the "Layout model" section below)**: rows are the 13
  derived vanilla technology categories plus the 5 crisis-faction rows, faction-first-else-
  category and mutually exclusive (D-16, corrects an earlier draft where the crisis-faction lane
  was the row axis and category was only a sub-grid wrap key); **bands are DECLARED tier, never
  computed column** (D-13, unaffected by D-16). A node declared T5 sits in the T5 band regardless
  of promotion. Band headers show the declared tier and nothing else. Computed column is internal
  geometry governing horizontal ordering *within* a (row, band) cell, and is never displayed.
  ~10 declared-tier bands plus a terminal Repeatables band. Tier range unbounded in principle
  (ACOT reaches T9+), but the rendered set tops out around T8.
- **Colour**: superseded by D-16 — colour/pattern now encode the ROW (an area-coloured header
  chip on a category row, faction colour/pattern as row backing on a faction row), cards
  themselves neutral dark; research area is deliberately NOT colour-encoded inside a faction row
  (an accepted loss). Outline = area unless rare or dangerous, dangerous outranks rare, both = 45°
  split (unaffected by D-16 — this is about the card's own outline, not its background). Colour
  never the sole carrier. Exact hexes in `CLAUDE.md`; `tokens/`/`client/src/tokens.ts` is the
  single source of truth for node colours (edge colours were added there too, Stage 3 slice 3).
- **Unknown tolerance (D-10)**: 10% ceiling per empire profile (worst profile, not pooled), 3%
  warn, plus a no-regression ratchet.
- English only for v1, pipeline language-parameterised.

---

## What's built

Five extraction packages plus the dataset schema contract, each self-contained and separately
tested, none merged into a shared "do everything" module:

- **`pipeline/clausewitz/`** — hand-written tokeniser + recursive-descent parser for Clausewitz
  script (not a general-purpose parser; grammar derived entirely from real corpus evidence, see
  `tests/fixtures/NOTES.md`). Produces a lossless AST: duplicate keys survive as ordered lists,
  comments are preserved with position, comparison operators other than `=` are kept verbatim.
  Also owns `serializer.py` and `roundtrip.py` — see "Standing invariants" below.
- **`pipeline/variables.py`** — `@scripted_variable` resolution. Memoised recursive lookup (not a
  sequential pass), whole-key last-definition-wins across load order, hard-fails on an undefined
  reference or a reference cycle (naming the full cycle chain).
- **`pipeline/inline_scripts.py`** — `inline_script` expansion. Text substitution on raw source
  before tokenising (required — ~46% of real `$PARAM$` usage is embedded mid-token, which no AST
  node shape can represent), then parsed with the ordinary Clausewitz parser. Runs before
  `@variable` resolution.
- **`pipeline/localisation/`** — hand-written parser for Paradox's localisation format. **Not
  YAML** — `§` colour codes, `£icon£` tokens, embedded colons, doubled/escaped quotes, and
  version-suffixed keys all fall outside the YAML spec; a YAML library would variously reject,
  coerce, or silently mangle real content. Preserves all markup verbatim, resolves nothing.
  **Value scanning is first-quote-to-last-quote-on-the-line — the inverse of the Clausewitz
  string rule.** 970 lines carry literal internal quotes; scanning to the next unescaped quote
  truncates them into plausible-looking short strings with no error. Do not reuse the Clausewitz
  scanner here.
- **`pipeline/icons/`** — technology/ascension-perk → icon-file resolution, DDS decoding
  (level 0 only), and deterministic, size-capped atlas packing to WebP (lossless) with PNG
  fallback. Sheets capped at 2048×2048 because WebGL's guaranteed `MAX_TEXTURE_SIZE` floor is
  2048 and mid-range mobile GPUs commonly report 4096 — an uncapped sheet fails to upload and
  every icon disappears, breaking P-9.
- **`schema/`** — the dataset schema itself: `common.schema.json` (shared `$defs` — `ThreeState`,
  `EdgeKind`, the composed `EmpireProfile`/`EmpireTypeConstraint` axis types, `Edge` with its
  `from`/`to` direction convention stated once as the property descriptions, `Gate`, `IconRef`,
  `GeometryRef`) plus one schema per artefact (`base-dataset`, `empire-overlay`,
  `detail-payload`, `search-index`, `diagnostics`). `schema/generated/dataset-types.ts` is
  generated from it by `tools/generate_typescript_types.py` — hand-written in Python, not an
  off-the-shelf `json-schema-to-typescript` run — D-12 already commits the pipeline to Python end
  to end, and (as of a later session) there's no longer a "no Node/npm" reason either; the
  generator's own `tsc`-verified correctness (below) means swapping it for a Node dependency has
  no problem left to solve. ~~**Unverified as TypeScript**~~ **Verified, later session: zero
  errors.** `.github/workflows/typecheck.yml` runs `tsc --noEmit` over the whole `client/`
  project (which includes this file via `client/tsconfig.json`), closing the `TODO(Stage 3)` that
  used to sit at the top of the generator and in CLAUDE.md's Open Items — see CLAUDE.md's "Stage 3
  toolchain foundation is built" bullet for the three ways this was checked.
  `pipeline/dataset_schema/` is the Python-side
  validator (`jsonschema` + a `referencing.Registry` wiring the local `$ref`s together) plus the
  canonical `EmpireProfileIndex` derivation (`pipeline/dataset_schema/empire_profile.py` —
  composed axes are the identity model, this integer is a documented, storage-only encoding of
  them for indexing the 12-slot `availabilityMatrix`; strides are *derived* from axis
  cardinalities at import time, not hardcoded, with an import-time bijection assertion —
  hardcoding was the original bug: correct for today's 3×2×2 shape but silently
  collision-prone if any axis ever grows) and the `availabilityMatrix`/overlay consistency check.
- **`pipeline/overwrites.py`** — P-15 technology overwrite resolution. Whole-key,
  last-source-wins across load order (`Vanilla` < `Gigastructural Engineering` < `ACOT` < `AoT`),
  refusing to guess (raising `OverwriteOverrideRequiredError`) on the two shapes the corpus survey
  never validated a rule for — a 3-or-deeper source chain, or two definitions from the *same*
  source — unless `config/overwrite_overrides.txt` names the winner. Per-technology output: a
  `definedBy`/`overwrites`/`label` triple (generalising the old single vanilla-only case — most
  of the corpus's overwrites have no vanilla baseline: 19 of 25 are `ACOT`→`AoT`), and a
  field-level diff (cost/tier/prerequisites/weight/category/flags) against whatever the winner
  actually replaced, never hardcoded to vanilla. `cost`/`weight` are compared through
  `@variable` resolution (via `pipeline.variables`) so an indirect scripted-variable overwrite is
  visible even when the technology's own block is untouched, but the raw pre-resolution form
  (literal vs. `@name` reference) is retained alongside the resolved value — a mechanism change
  and a value change are tracked separately, never collapsed. `prerequisites`/`category` are
  diffed as sets (reordering alone is not a change — confirmed against the corpus with no
  counter-example, treated as an inference not a proven invariant); the *displayed* prerequisite
  order is a separate, declaration-order, depth-first list from the winning definition, kept
  deterministic across builds. `resolve_variable_overwrites` is the distinct scripted-variable
  overwrite layer: a `@name` redefined by a later source, changing every technology that
  references it in `cost`/`weight` without their own blocks being touched — a different cause
  from a technology-block overwrite, reported in its own section of `build_overwrite_report`'s
  S-2 diagnostics output (`technologyBlockOverwrites` / `scriptedVariableOverwrites`), never
  collapsed into one list. `pipeline/overwrite_overrides.py` loads
  `config/overwrite_overrides.txt` (same format and required-`#`-justification bar as
  `pipeline/icons/overrides.py`'s `config/icon_overrides.txt`) — checked in seeded empty, since
  the corpus survey found no case needing one. Tests: `tests/test_overwrites.py` (synthetic,
  mechanism coverage — presence-vs-absence, set-vs-order, mechanism-vs-value, the ambiguity
  guard), `tests/test_overwrite_overrides.py` (loader), `tests/test_overwrites_corpus.py` (real
  vendored corpus end-to-end, skipped when `vendor/` isn't populated, asserting the corrected
  25-overlap counts so a corpus refresh that silently changes them fails a test instead of going
  unnoticed).

## Standing invariants — tests that exist to keep something from regressing silently

These aren't "just tests" — each closes a specific class of bug this project already hit once. Do
not weaken or delete them without understanding what they guard against; read the module
docstring named before touching the logic.

- **Round-trip adjacency check** (`pipeline/clausewitz/roundtrip.py`,
  `tests/clausewitz/test_roundtrip*.py`). A file parsing without raising proves nothing about
  whether it parsed into the *right* AST — two real bugs (`flag@root` silently split; a `$PARAM$`
  silently glued onto adjacent identifier text) parsed cleanly into wrong ASTs. The detector
  serialises the AST back to text and compares token streams against the source, and critically
  compares `preceded_by_whitespace` (whether *any* separator existed between two tokens) —
  **never** reconstructed by asking the tokeniser "could this pair lex differently," because that
  consults the same tool under test and would silently pass the exact corruption it exists to
  catch.
  - **Allowlist**: `tests/clausewitz/roundtrip_allowlist.json`, 434 entries across 48 files —
    every one a same-token, presence-only whitespace divergence, never a content mismatch. Read
    the file's own `_rationale` field before adding an entry; an entry only applies while the
    exact recorded token pair still matches.
- **Mutation harness, permanent** (`tests/clausewitz/test_roundtrip_detects_mutations.py`).
  Reintroduces the two historical tokeniser bugs via monkeypatching, so the *same* mutated
  tokeniser is used for both AST construction and comparison — the actual adversarial scenario —
  and asserts the round-trip check still fails on each. Also asserts a weaker comparator (no
  `preceded_by_whitespace`) would have silently passed both. Keep this file; it exists to stop
  the comparator being "simplified" back into blindness.
- **Determinism tests** (`tests/icons/test_pack.py`). Packing the same input twice is
  byte-identical (RGBA buffer, WebP bytes, PNG bytes, independently checked). Changing one source
  icon's pixels changes only its own sheet's content hash and leaves every other icon's
  sheet/position assignment untouched.
- **Corpus-size drift guards.** 273 Clausewitz files; 353 localisation files; the icon
  unresolved-candidate counts (19 technology/swap, 6 ascension perk) and zero ImageMagick
  fallbacks. A failure means vendored content or discovery logic has drifted — **re-derive the
  expected number before trusting anything measured against it, don't just bump the assertion.**
- **TypeScript drift test** (`tests/schema/test_typescript_drift.py`). Re-runs
  `tools/generate_typescript_types.py` and diffs against the checked-in
  `schema/generated/dataset-types.ts`. Without this, nothing stops the JSON Schema and the
  TypeScript types from being hand-edited independently until they silently disagree — exactly
  the failure mode the generated-file approach exists to prevent.
- **`availabilityMatrix`/overlay consistency check**
  (`pipeline/dataset_schema/empire_profile.py`'s `check_availability_matrix_matches_overlays`).
  The base dataset's compact 12-slot matrix and each empire overlay's richer per-profile
  `availability.state` are redundant by design (see the schema field's own description) — wired
  into the real `pipeline/dataset_emit.py` build and checked on every run.

All of the above are gated behind `vendor/` being populated locally (gitignored, CI never has
it) — see each test file's `skipif`. CI-safe regression coverage over a small committed fixture
subset exists in parallel (`tests/fixtures/`, manifest-driven, `tools/regenerate_fixtures.py`).

## `weight-gated` — the fifth `AvailabilityState`, correcting Item 2b's overbroad weight-modifier folding (a later session)

**Background.** Item 2b (an earlier session, `docs/BUILD-LOG.md` above) folded every zero-factor
`weight_modifier` entry into availability uniformly: a firing condition → `LOCKED`, an unresolvable
one → `UNCERTAIN`. Real corpus: 301 such entries across 248 of the 973 rendered technologies.
Measured effect at the time: unconditional uncertainty 31/973 (3.19%) → 115/973 (11.8%); worst
profile-dependent rate 16/973 (1.64%) → 58/973 (5.96%) — crossed D-10's 3% warn threshold, stayed
under the 10% hard ceiling, reported as a considered tradeoff rather than hidden.

**Three surveys (chat record, committed here in full for the first time) reclassified every entry
into four buckets** by whether its condition is decidable under the modelled empire axes:

| Bucket | Meaning | Entries | Technologies |
| --- | --- | ---: | ---: |
| A — PROFILE-DECIDABLE | every leaf resolves definitely: axis facts, DLC/ground facts, mod-config toggles, literal constants | 30 | 27 |
| B — CIRCUMSTANTIAL | mutable in-game state: owned planets, deposits, policies, crisis levels, resources, communications, traditions | 193 | 159 |
| C — OPAQUE | genuinely undecidable leaves (`check_variable` count-vs-cap, unknown-meaning `has_country_flag` values) | 61 | 61 |
| D — MIXED | both A-type and B/C-type leaves in one condition | 17 | 12 |

Folding B/C/D in accounts for 100% of the regression above — bucket A alone contributes ZERO new
uncertainty, by construction (every bucket-A leaf resolves definitely for every profile).

**Two figure pairs that looked inconsistent across the surveys are not**, recorded so a future
session doesn't re-litigate them: 159 (bucket-A-only-counterfactual vs. current) and 163 (pre-2b vs.
current) differ by exactly 4 technologies (`tech_fe_assembly_1`/`_clinic_1`/`_entertainment_1`/
`_market_1`) which hold a genuine axis LOCKED either way. The previously-recorded 39/124 split is
correct as stated: 39 = 35 locked-only + 4 both; 124 = uncertain-only, deliberately non-overlapping.

**Decisions taken, in full:**

1. Bucket A retains a definite verdict, subject to decision 4's narrowing (below).
2. Buckets B and C both map to the new fifth `AvailabilityState`, `weight-gated` — never to
   `uncertain`. D-10 uncertainty means "the tool cannot tell you whether this is available to your
   EMPIRE TYPE"; for B and C the tool CAN tell you that (it's available to your type, gated on
   something that isn't your type) — C differs from B only in how well the condition can be
   phrased, a presentation question, not a different kind of fact. `weight-gated` does NOT count
   toward D-10 uncertainty, exactly as `config-gated` doesn't.
3. Bucket D resolves per profile: where an A-type leaf independently decides a profile's outcome
   (Kleene AND/OR's own false/true-dominance — no extra mechanism needed), that verdict stands;
   otherwise that profile gets `weight-gated`.
4. A real LOCKED verdict from a weight gate is narrower than bucket A: `weight_modifier` describes
   eligibility in the weighted research draw ONLY, blind to `give_technology`, events, special
   projects, archaeology and relics — confirmed for `tech_akx_worm_1` (permanent `always = yes`
   zero weight, yet granted through a guaranteed event chain; `vendor/stellaris/` has no `events/`,
   `common/special_projects/`, `common/decisions/`, `common/on_actions/`, `common/relics/` or
   `common/archaeological_site_types/` by design, so a clean grep there is not evidence of
   absence). LOCKED is therefore permitted only when the deciding leaves are genuine empire-TYPE
   facts: `AXIS_FACTS`, or an ascension perk whose own `potential` carries a real axis restriction
   (D-6's correction, `spec/decisions.md`) — everything else in bucket A (`always`, an unrestricted
   perk, an unresolved wrapper) gets `weight-gated` too.
5. Tripwire: a weight-gate condition that yields LOCKED for all 12 profiles draws no empire-type
   distinction by definition and is misclassified — asserted directly in
   `pipeline.availability.evaluate_technology_for_profiles` (the full 12-profile call only), not
   left as an emergent property of the bucket routing.

**Implementation** (`pipeline/availability.py`): `_Eval` gained an `axis_pure` field, threaded
through `_bool_eval`/`_combine_and`/`_combine_or`/`_negate` alongside the existing Kleene state —
`True` only when a result's TRUE/FALSE rests solely on `AXIS_FACTS` leaves and/or an axis-locked
`has_ascension_perk`. `_apply_weight_gate` was rewritten to work from the internal `_State`
directly (see the EXCLUDED defect below) rather than `evaluate_trigger_block`'s public wrapper:
internal `TRUE` + `axis_pure` → real `LOCKED`; internal `TRUE` without `axis_pure`, or `EXCLUDED`,
or `UNKNOWN` → `weight-gated`; internal `FALSE` → untouched (the condition doesn't currently hold).
Condition text is wired through `pipeline.trigger_text.describe_condition` for both the real-LOCKED
and `weight-gated` branches (previously a fixed string), with a dedicated phrase for the two real
`always = yes` cases ("obtained outside the normal research draw, not through it") and a neutral
"not offered through the normal research draw currently" fallback everywhere the responsible leaf
isn't nameable — never speculating about which unmodelled mechanism might actually grant it.

**The EXCLUDED-as-vacuously-satisfied defect**, found while implementing this: the OLD
`_apply_weight_gate` read `evaluate_trigger_block`'s PUBLIC result, which maps both a real internal
`TRUE` and `EXCLUDED` (has_technology/has_ascension_perk/origin-ethic-civic — "presume open," the
right default for `potential`'s "does empire type exclude this" question) to `AVAILABLE`. That
default has no meaning for "is the zero-weight condition currently met," and silently laundered an
unresolvable condition into a false-definite `LOCKED` for all 12 profiles — 12 zero-factor
`weight_modifier` entries (11 technologies) were affected before the fix. Full write-up, including
why the other three `EXCLUDED`-touching call sites in this codebase are each sound for their own
specific, checkable reason (not by any general property of the identity element):
`docs/DEFECTS.md`'s "EXCLUDED-as-vacuously-satisfied" section.

**Real corpus verification (`pipeline.dataset_emit.build_context`, direct evaluation, not
asserted)**: exactly 5 technologies keep a real, axis-narrowed LOCKED from a weight gate alone —

| Technology | Deciding leaf | Locked profiles |
| --- | --- | ---: |
| `tech_fe_assembly_1` | `is_hive_empire = yes` | 4 |
| `tech_fe_clinic_1` | `is_machine_empire = yes` | 4 |
| `tech_fe_entertainment_1` | `is_gestalt = yes` | 8 |
| `tech_fe_market_1` | `is_gestalt = yes` | 8 |
| `giga_tech_maginot_world` | `has_galactic_wonders = no` (expanded) | 6 (nomadic profiles) |

`tech_akx_worm_1`/`_2` (`always = yes`) and `tech_gene_seed_purification` (`NOT = {
has_ascension_perk = ap_engineered_evolution }`, an unrestricted perk) reclassify to `weight-gated`
for every profile where their own `potential` doesn't already lock them for an unrelated reason
(8/12 for `tech_gene_seed_purification`, whose own `potential` separately locks the 4
machine-intelligence profiles on a genetics-tradition ground unrelated to this weight gate).

**`giga_tech_maginot_world` diverges from the pre-implementation survey's own worked example, and
this is a genuine finding, not a bug — reported per this task's own "stop and report" instruction
rather than adjusted to match.** The survey's worked example assumed `has_galactic_wonders = no`
would resolve via the `EXCLUDED_KEYS` shortcut (a bare, unexpanded literal key) and predicted
`weight-gated` for all 12 profiles, the same treatment as `giga_tech_maginot_world`'s OTHER
zero-factor modifier (a `NOR` over `has_tradition`/`has_active_tradition` leaves, which genuinely
does resolve `weight-gated` via the `has_active_tradition` default-true leaf). But
`pipeline.dataset_emit._weight_gate_condition_blocks` scripted-trigger-expands every weight-gate
condition exactly the way `potential` blocks already are (`ctx.expanded_potentials`) — and
`has_galactic_wonders` is itself a Gigastructures scripted trigger
(`vendor/mods/gigastructures/common/scripted_triggers/zzz_overwrites.txt:2095`) that expands into
`NOT = { OR = { has_ascension_perk = ap_galactic_wonders, ..._utopia, ..._megacorp,
..._utopia_and_megacorp } }`. The Galactic Wonders perk family is genuinely nomadic-excluded (the
same D-6 axis-restricted-perk fact CLAUDE.md's "Ascension perks are gates" section already
documents), so for the 6 nomadic profiles every branch of that `OR` resolves a real, axis-pure
`FALSE` (via the existing `has_ascension_perk` axis-lock mechanism, unchanged by this session),
making the `NOT` a real, axis-pure `TRUE` — a genuine LOCKED, not a misclassification. For the 6
non-nomadic profiles, the same perks are ordinary unclaimed choices (`EXCLUDED`), so the `NOT`
stays `EXCLUDED` → `weight-gated`, matching the survey's prediction for those profiles. The
scripted-trigger expansion this session relies on (`expand_scripted_triggers`, unchanged,
pre-existing) is what the hand-derived survey example didn't run — the actual pipeline result (6
LOCKED / 6 weight-gated, split exactly on the nomadic axis) is MORE precise than "all 12
weight-gated," not a defect to chase down.

**Per-state population, full 12×973 evaluation (`build_context`, this session's own verification
script)**:

| State | Count |
| --- | ---: |
| available | 7,492 |
| locked | 1,466 |
| uncertain | 482 |
| config-gated | 600 |
| weight-gated | 1,636 |

Of the 1,466 LOCKED and 1,636 weight-gated pairs, only 6 LOCKED pairs and roughly 1,830 weight-gated
pairs (163 technologies, up to 12 profiles each) are actually CAUSED by a weight gate specifically
(as opposed to the technology's own `potential`) — the 5-technology table above accounts for the
LOCKED side; 163 technologies carry a weight-gate-caused `weight-gated` verdict for at least one
profile (`giga_tech_maginot_world`, `tech_akx_worm_1`/`_2`, `tech_gene_seed_purification`, plus 159
more spanning bucket B/C conditions — deposit/building/megastructure ownership,
`has_market_access`/other internal flags, `is_country_type = fallen_empire`, `num_owned_planets`,
crisis-level gates, and others).

**Observation, recorded and acted on nowhere (explicitly out of scope this session)**:
`tech_akx_worm_1`/`_2`'s `weight_modifier`-level `always = yes` is a weight-side analogue of D-18's
`potential`-level `always = no` pattern (the 4 technologies excluded from rendering entirely,
`pipeline.rendering_scope._is_permanently_disabled`) — both are a literal boolean constant used to
permanently gate something, just at different points in the evaluation (rendering-scope exclusion
vs. a draw-eligibility gate). The node SET is untouched by this session either way: `always = yes`
inside `weight_modifier` doesn't affect rendering (D-18 only inspects `potential`), and this
session made no change to `pipeline.rendering_scope`. Noted as a parallel worth being aware of, not
a discrepancy to reconcile.

**D-10 diagnostics and research-path status counts, from an actual `tools/build_dataset.py` run
against the corrected pipeline (`client/public/dataset/diagnostics.*.json`, `base-dataset.*.json`,
`overlays/*.json`)**:

- Unconditional uncertainty: **31/973 (3.186%)**, exactly the pre-2b figure — matches
  `previousCount: 31` (no regression against the ratchet).
- Worst profile-dependent rate: **16/973 (1.644%)**, exactly the pre-2b figure — every one of the
  12 profiles reports `"status": "ok"`.
- Union (uncertain for at least 1 of 12 profiles): **53/973**, exactly the pre-2b figure.
- Per-state population, full 12×973 matrix: `available` 7,492, `locked` 1,466, `uncertain` 482,
  `config-gated` 600, `weight-gated` 1,636.
- Research-path status, `(technology, profile)` pairs / distinct technologies across all 12
  overlays: `path` 9,330/920, `unavailable` 1,466/233, `config-gated` 390/50, **`blocked` 490/81**.
  The bucket-A-only counterfactual predicted 526/82; the actual reduction (526→490 pairs, 82→81
  technologies) is exactly the weight-gated-is-viable rule (P-12.9's Extension) unblocking routes
  whose only broken ancestor was a technology that's now `weight-gated` (eventually researchable)
  rather than the counterfactual's `locked` (a hard route-breaker).

**The 5 technologies that survive as a real, weight-gate-caused LOCKED**, confirmed directly
against the built dataset's overlays (not just the earlier hand survey): `tech_fe_assembly_1`,
`tech_fe_clinic_1`, `tech_fe_entertainment_1`, `tech_fe_market_1`, `giga_tech_maginot_world` — see
the table earlier in this entry for each one's deciding leaf and locked-profile count.

**Live-render verification (a headless Chromium against the actual built `client/dist`, driven via
CDP + `playwright-core` — no dedicated Playwright test suite exists in this repo yet, so this was
ad hoc rather than a committed test)**: 0 console errors, 0 failed/4xx+ requests, across the
default profile and two profile switches. `giga_tech_blokkat_engineering_repeatable` (regular/
mechanical/non-nomadic) renders with the violet weight-gated dim (alpha 0.25) and `⧗` badge on its
card, and its popup shows `weight-gated — Unresolved internal flag: blokkat_crisis_defeated` plus
`Total: 576,000 (estimate: weight-gated-step)` on its research path. `tech_akx_worm_1` shows the
dedicated always-yes phrasing (`This technology is obtained outside the normal research draw, not
through it.`); `giga_tech_maginot_world` shows the neutral fallback
(`Not offered through the normal research draw currently.`) since its own deciding leaf has no
single nameable form after scripted-trigger expansion. Switching to hive_mind/mechanical/
non-nomadic and reselecting `tech_fe_assembly_1` shows it flip to a real `locked — Hive mind
empires`, red badge (`✕`), alpha 0.55 — the same technology, two profiles, two states, both
matching what the pipeline emits.

**Test suite regressions found and fixed while verifying this session's own work** (full account
in `docs/DEFECTS.md`-adjacent commentary, kept here since these are this session's own bugs, not a
recurring class):

1. `_build_research_paths_for_profile`'s `closure()` return tuple grew from 4 to 5 elements (the
   new `has_weight_gated` flag) but `_closure_total_cost` still unpacked 4 — every `alternative`
   OR-group evaluation raised `ValueError: not enough values to unpack`, breaking the whole
   research-path builder and 20+ dependent tests (`test_dataset_emit.py`,
   `test_research_paths.py`). One-line fix.
2. The first version of the `has_ascension_perk` axis_pure computation called BOTH the public
   `evaluate_trigger_block` and a second, redundant internal `_combine_and` pass over the same
   perk `potential` block whenever the perk was LOCKED — doubling that leaf's evaluation cost.
   Measured impact: building all 12 empire overlays went from ~8s to ~32s (worst, machine-
   intelligence profiles, where axis-restricted perks are most common), enough to make
   `test_dataset_emit.py` time out under CI-like conditions. Fixed by computing the perk's
   internal `_Eval` exactly once and deriving both the LOCKED-vs-CONFIG_GATED split and
   `axis_pure` from that single pass — restored to ~8s for all 12 overlays.
3. Three pinned test figures needed updating to the corrected (post-fix, pre-2b-equal) values, not
   silenced: `test_gate_classification_leaves_d10_uncertainty_unchanged` /
   `test_edge_constraints_leave_d10_uncertainty_unchanged` (worst profile-dependent 58 → 16),
   `test_diagnostics_uncertain_technologies_matches_d10` (unconditional 115 → 31, worst rate
   0.0596 → 0.016444), `test_no_step_is_locked_or_config_gated_for_its_own_profile` (added
   `weight-gated` to the allowed per-step states), and
   `test_or_tiebreak_cheapest_cost_vs_fewest_steps_disagreement_count` (its own independent
   closure reimplementation needed `weight-gated` added to its viability check too — once added,
   its figures returned to the exact pre-2b baseline: 420 evaluations / 408 viable / 72 genuine
   choices / 12 disagreements, unchanged from before this whole saga).

Full suite: **1,515/1,515 pipeline tests pass** (`pytest`, vendor populated), `tsc --noEmit` clean,
`vite build` clean, schema drift test clean (TypeScript types regenerated via
`tools/generate_typescript_types.py`).

## Weight-condition gate extraction (a later session)

A prior survey (recorded in this session's own handoff, not re-run) found: of the 206 zero-factor
`weight_modifier` blocks producing the 1,636-pair / 163-technology `weight-gated` population above,
running `pipeline/gate_patterns.py`'s existing classifier over those conditions matched an
ALREADY-REGISTERED gate pattern for 866 pairs / 87 technologies (ascension_perk 59 entries/43
techs/482 pairs, origin 5/5/54, ethics_or_civic 14/13/124, technology 32/32/272). No new pattern
registration was needed. This session extended gate extraction to cover that population: a
zero-factor condition that classifies to a registered gate pattern now badges the card as a
`Gate` and no longer produces a `weight-gated` verdict for that condition.

**Implementation.** `pipeline/gate_patterns.py` gained `classify_weight_gate_condition(technology_
key, condition_block, index)`, sharing `classify_gates`' dispatch table and `_scoped_gate_leaves`
descent via a new `_classify_leaves_in_block` helper. The one real design question: **polarity**.
`classify_gates` drops a negated leaf (a `potential` block's own polarity IS the requirement — "must
NOT have perk X" is not a positive "Needs X"). A naive first attempt applied the SAME filter to
weight conditions and found almost nothing (11 technologies, not 87) — `tech_lathe_*`'s real shape
wraps `has_ascension_perk = ap_cosmogenesis` in a `NOT` (zero weight unless the planet+perk
condition holds), and `tech_neuro_quantum_links` wraps three perks in a `NOR` (zero weight unless
the empire holds ANY of them) — both read NEGATED under the standard scoping. A second attempt
flipped the descent's starting polarity (`ancestor_negated=True`) to match `_apply_weight_gate`'s
own "the offered condition is the NEGATION of the zero-factor condition" framing — this recovered
`tech_lathe_*`/`tech_neuro_quantum_links` correctly but produced ZERO gates for `tech_housing_2`,
whose raw condition is a completely UNWRAPPED `has_valid_civic = civic_agrarian_idyll` (no `NOT` at
all — direct inspection of `vendor/stellaris/common/technology/00_eng_tech.txt:3768`). Investigating
that specific corpus case settled it: `tech_housing_2` and its swap-pair sibling `tech_housing_
agrarian_idyll` both zero their OWN weight based on the SAME civic, from OPPOSITE polarities (one
excludes Agrarian Idyll players, the other requires them) — and the intended, useful signal in both
cases is identical: "this technology's availability depends on the Agrarian Idyll civic." Final
design: `classify_weight_gate_condition` does NOT filter on leaf polarity at all (`filter_negated=
False`) — a `weight_modifier` condition naming a registered gate-pattern leaf badges the card
regardless of which side of the condition it appears on. This is a deliberate, documented departure
from `classify_gates`' own precision bar (recorded in `pipeline.gate_patterns`'s module docstring
and `spec/P-03-gates.md`), not an oversight — gate badges are already an approximate, best-effort
display layer elsewhere (an `alternative`'s "or:" wording, the dangling-alternative downgrade).

**Availability-side change, and the one correctness pitfall found while implementing it.** The
first cut simply DROPPED a gate-expressible block from `weight_gate_conditions` entirely before it
reached `_apply_weight_gate` — LOCKED dropped by 6 (1,466 → 1,460), which turned out to be wrong:
those 6 pairs were a REAL axis-pure LOCKED (a referenced ascension perk is genuinely unobtainable
for that empire type, D-6's corrected rule), not a `weight-gated` verdict — dropping the block
entirely lost that fact along with the (correct) suppression of `weight-gated`. Fixed by keeping
every block in `weight_gate_conditions` (so the axis-pure-LOCKED branch still sees it) and adding a
parallel `weight_gate_expressible_mask: dict[str, list[bool]]` on `BuildContext`, threaded through
`evaluate_technology_for_profiles`/`_apply_weight_gate` as a new optional parameter: a
gate-expressible block's non-axis-pure TRUE/EXCLUDED/UNKNOWN branches are suppressed (contribute
nothing, like a FALSE block) rather than becoming the `weight_gated_pick`, while its axis-pure TRUE
branch is untouched and still returns a real LOCKED. Result: LOCKED stays EXACTLY 1,466 (unchanged),
`weight-gated` drops from 1,636/163 pairs/technologies to **850/85**, and the freed pairs move to
AVAILABLE (7,492 → 8,278).

**`_build_gates`** (`pipeline/dataset_emit.py`) now merges `classify_gates(owner_key, defn.block)`
with `ctx.weight_gate_gate_matches[owner_key]` (the gate-expressible blocks' own matches, computed
once in `build_context`), deduped by `(kind, refId)` — NOT by kind alone, since a technology can
legitimately carry two different gates of the same kind — with the `potential`-derived match
winning a collision. The merged list is priority-sorted (`order_gates`, D-3, unchanged) AFTER the
merge, so a weight-derived match can outrank and displace a `potential`-derived match to secondary
exactly like two `potential`-derived matches of different kinds would.

**The two named verification cases, both reproduced exactly:**
1. **Deduplication**: 6 `tech_lathe_*` technologies (`_overclocker`, `_preserver`, `_validator`,
   `_life_support`, `_cogitator`, `_resonator`) each dedupe an identical `ap_cosmogenesis` match
   against their own `potential`-derived gate — confirmed no duplicate badge. 90 technologies carry
   at least one weight-derived match total (close to, not identical to, the 87-technology survey
   figure above — the survey scanned raw conditions with the classifier as a quick estimate before
   this session's polarity investigation settled the final design; the small gap is expected
   methodology drift, not a discrepancy to chase). `tech_housing_agrarian_idyll` and `tech_housing_2`
   both gain a genuinely NEW `ethics_or_civic: civic_agrarian_idyll` badge, from opposite polarities
   of the same civic-swap-pair condition (see above).
2. **D-3 priority conflict**: exactly ONE technology, `tech_neuro_quantum_links`, has its primary
   badge displaced — its `potential`-derived `ethics_or_civic: civic_machine_assimilator` ("Needs
   Driven Assimilator") moves to secondary, outranked by a weight-derived `ascension_perk`
   alternative group (`ap_the_flesh_is_weak` / `ap_organo_machine_interfacing` /
   `ap_organo_machine_interfacing_assimilator`, from a `NOR`-wrapped condition — "offered if the
   empire holds ANY of these three"). Verified via direct comparison of the merged primary gate
   against the `potential`-only primary gate across every rendered technology — no other technology
   is affected.

**Suspected defects investigated (both false alarms, no fix needed — investigated BEFORE
implementing, per this task's own instruction):**
- **(a) 72–78 pairs resolving a pure-axis-fact TRUE yet reading `weight-gated`.** Directly inspected
  the real corpus conditions (`tech_astral_harvesting`, `tech_mine_dark_matter`,
  `tech_mine_rare_crystals`, `tech_mine_volatile_motes`, `tech_mine_exotic_gases`,
  `tech_negative_e_s`, `tech_fe_nourishment_2`, `tech_nanite_transmutation`,
  `tech_weaver_bio_healing_4/5`-adjacent family — 9 distinct technologies, 78 pairs by this
  session's own count, close to the survey's 72): every one embeds its axis leaf (`is_nomadic`,
  `country_uses_bio_ships`) inside an `AND` alongside a genuinely UNRESOLVABLE sibling condition
  (`any_owned_nonprimary_starbase = { is_waystation_starbase = yes, solar_system = { ... } }`, an
  opaque, un-evaluable scope) — `_combine_and`'s `axis_pure` correctly requires ALL relevant
  children to be axis-pure, so the mixed AND correctly resolves non-axis-pure and routes to
  `weight-gated`, never a false LOCKED. The rule is working as designed; these are genuinely mixed
  conditions, not a bug.
- **(b) `has_ancrel = no` "never fires" under the ground-fact assumption.** Confirmed: `has_ancrel`
  is a `GROUND_FACT_BOOL` resolving `True` (DLC always owned), so `has_ancrel = no` always resolves
  `FALSE` and correctly contributes nothing. Of the 16 real technologies whose weight condition
  mentions it, 14 (the `tech_archaeo_*` family, `tech_archaeostudies`, `tech_arcane_deciphering`'s
  sibling techs) resolve cleanly AVAILABLE with this condition contributing nothing, exactly as
  designed. `tech_archaeo_rampart` shows a real `locked`/`available` split for an UNRELATED reason
  (its own `potential`, not this weight condition). `tech_arcane_deciphering` is `weight-gated` for
  all 12 profiles, but the cause is the OTHER branch of its `OR` (`NOT = { has_resource = {
  type = minor_artifacts, amount > 0 } }`, a genuinely unresolvable resource-amount check) — zero
  technologies are `weight-gated` purely because of a provably-never-fires `has_ancrel = no`
  condition. Not a bug.

**Final figures.**

| Metric | Before | After |
| --- | --- | --- |
| Gates: DIRECT total | 107 | 274 |
| Gates: DIRECT by kind | 48 ascension_perk / 14 origin / 24 ethics_or_civic / 21 technology | 106 / 24 / 56 / 88 |
| Gates: TOTAL (direct+inherited) | 214 | 643 |
| Gates: TOTAL by kind | 104 / 16 / 61 / 33 | 198 / 69 / 179 / 197 |
| Gated technologies | 147 | 304 |
| `weight-gated` entries | 1,636 | 850 |
| `weight-gated` distinct technologies | 163 | 85 |
| `available` entries | 7,492 | 8,278 |
| `locked` / `uncertain` / `config-gated` entries | 1,466 / 482 / 600 | 1,466 / 482 / 600 (unchanged) |

Per-state total: 8,278 + 1,466 + 482 + 600 + 850 = **11,676** (unchanged, as required — the node set
and per-pair total never move, only which state each pair lands in). D-10's three figures are
**exactly unchanged**: unconditional uncertainty 31/973, worst profile-dependent 16/973 (1.644%),
union 53/973 — expected, since `_apply_weight_gate` only ever fires on a `potential`-derived
AVAILABLE result and never itself produces UNCERTAIN.

The TOTAL gate count's growth (214 → 643, a ~3× increase) is larger than the direct-match count
alone (107 → 274, a ~2.6× increase) suggests, because the SAME `prerequisite`-chain propagation that
already existed for `potential`-derived gates (Item 3, prior session) now also propagates these new
weight-derived direct gates to their descendants — e.g. `giga_tech_amb_supertensiles` gained a new
direct `technology: tech_starbase_3` gate from its own weight condition (a `NOR` of three
alternatives, downgraded to a plain "Needs Starhold" since only one alternative is gate-classified),
which propagates to all four `giga_tech_amb_supertensiles_acot_*` descendants. This is the existing,
unchanged propagation mechanism doing exactly what it was built to do — not a new cascade bug. The
largest single gates list after this change is 11 entries (`tech_thought_enforcement`,
`tech_telepathy`, `giga_tech_shroud_conduit`, and 5 others in the psionics family), not indicative of
runaway growth.

One existing pinned test's premise needed updating, not silencing:
`test_base_dataset_gates_match_the_gate_classification_survey`'s subset check ("every DIRECT
`technology`-kind gate instance is one of the 25 `potential-gate` edges") no longer holds for the
FULL merged `gates` field, because weight-condition gate extraction is a genuinely SECOND source of
direct technology-kind gates that was never part of `potential_gate_pairs` to begin with (P-14's
edge extraction is `potential`-only). Fixed by recomputing the check against `classify_gates`
directly (bypassing the merged field) so it stays scoped to what it always meant to test.

Full suite after this session: **1,515/1,515 pipeline tests pass** (8 new unit tests added to
`tests/test_gate_patterns.py` covering `classify_weight_gate_condition`'s polarity-ignoring
behaviour, the `NOR`-alternative-group shape, and group-id namespacing against `classify_gates`'
own `#gate-alt` namespace), `tsc --noEmit` clean, `vite build` clean. Playwright (headless, Chromium
installed via `npx playwright install chromium` since neither Playwright nor a system browser was
present) against the real dev server: 0 console errors, 0 failed requests, across all three named
verification cases. `spec/P-03-gates.md` gained a normative section on weight-condition gate
extraction (the full mechanism backfill it's still missing otherwise remains open, per CLAUDE.md's
existing flag).

## Weight-gate completeness gaps (Items 1 and 2, a later session)

Two bounded completeness gaps in `_apply_weight_gate`/`_weight_gate_condition_blocks`, plus a
report-only sizing of a third.

**Item 1 — the player-is-standard-country-type ground fact.** `pipeline.availability`'s
`COUNTRY_TYPE_NEVER_PLAYER` (previously just `{"acot_phanon_base"}`) gains `"fallen_empire"` and
`"awakened_fallen_empire"`, user-confirmed: the player empire is always a standard
(`is_country_type = default`) country type. Surveyed exhaustively, walking the exact same AND/OR/
NOT/NOR descent `_evaluate_node` itself uses (so a value nested inside an unrecognised scope
switch like `any_relation`/`any_country` — never reachable as a direct leaf regardless — is
correctly excluded): across every rendered technology's `potential` AND zero-factor
`weight_modifier` condition, exactly THREE `is_country_type` values are ever directly reachable —
`acot_phanon_base` (already handled), and `fallen_empire`/`awakened_fallen_empire` (the same 9
technologies for both: `tech_dark_matter_deflector`/`_power_core`/`_propulsion`, and the six
`tech_weaver_bio_*_6` anti-fire-rate/evasion/anti-evasion/healing/fire-rate/confuser variants), each
a `NOR = { is_country_type = fallen_empire, is_country_type = awakened_fallen_empire }` zero-factor
weight condition. No `marauder_*`/`enclave*` value is ever a direct leaf anywhere in the corpus.

**Sole documented exception (user-confirmed): `is_country_type = blokkat_stripminers`** (and its
`_ascended_country`/`_blokkwork`/`_defeated` variants) is deliberately NOT added — a player CAN
become that type mid-playthrough (the Blokkat crisis's conversion mechanic), and no
`blokkat_stripminers*` value is a direct leaf anywhere in the corpus today regardless, so this is a
documented non-extension, not a behaviour change.

**Real effect, verified against the built pipeline, not assumed: NONE of the 9 technologies change
AVAILABILITY STATE.** Both leaves now resolve a real `FALSE` (previously `UNKNOWN`); `NOR` over two
`FALSE` children is a real `TRUE` (the zero-weight condition provably fires for every player
profile) — `_apply_weight_gate`'s non-axis-pure TRUE branch (`is_country_type` is a ground fact, not
an `AXIS_FACTS` entry, so `axis_pure` stays `False`) reaches the EXACT SAME `WEIGHT_GATED` outcome
the old UNKNOWN branch already reached, for every one of the 9 technologies across all 12 profiles.
None become MORE restricted (none become `locked`, confirmed directly and structurally: `axis_pure`
can never be `True` for a ground fact, and `_apply_weight_gate`'s LOCKED branch is gated on
`axis_pure`). One real, reported (not silently normalised away) side effect: the TRUE branch's
`_negate`-collapsed leaf is `None` (no single leaf survives negating a real FALSE), so
`_weight_gated_description` falls to the neutral `_WEIGHT_GATE_UNKNOWN_ROUTE` copy — for these 9
technologies specifically, description text actually LOSES the (technically one-sided, misleading
on its own) `is_country_type = fallen_empire` text the old UNKNOWN branch happened to carry, in
favour of the honest "Not offered through the normal research draw currently." This is reported as
the real, sole finding rather than forced to match a prior expectation of "these become available"
— the value of the fix is that the WEIGHT_GATED verdict for these 9 now rests on a PROVEN fact
instead of an accidentally-correct-looking UNKNOWN.

**Item 2 — bare top-level `factor = 0`.** `_weight_gate_condition_blocks` only ever iterated
`modifier`-keyed sub-items of `weight_modifier`; a BARE top-level `factor = N` (Stellaris's own
"always apply this factor" shorthand, no `modifier` wrapper) was invisible to it regardless of
value. Real corpus (verified directly against `BuildContext.rendered_defs`, not assumed): 222
rendered technologies use this bare shorthand (matches the investigation's own figure exactly); of
those, 24 carry a literal `factor = 0` with no other real (non-comment) sibling assignment — an
unconditional, permanent exclusion from the weighted draw, the same idiom `tech_akx_worm_1`'s
`modifier = { factor = 0, always = yes }` already expresses, just spelled without the wrapper.

Represented as an EMPTY synthetic condition Block (not a synthesized `always = yes` leaf):
`_combine_and([])` already resolves to `_State.EXCLUDED`/`leaf=None`, which `_apply_weight_gate`
already routes to `WEIGHT_GATED` with the neutral `_WEIGHT_GATE_UNKNOWN_ROUTE` copy — never the
`always = yes`-specific copy, which POSITIVELY CLAIMS a real route exists. That claim is earned for
`tech_akx_worm_1` by the user's own hand-confirmed event chain; it is not earned for these 24
(`vendor/stellaris/` has no `events/`, `common/special_projects/`, `common/decisions/` or
`common/relics/` at all, so this static pipeline cannot see what actually grants them).

**The 24, individually, and their split (exactly as required — "several", not all, pre-covered):**

| Technology | Pre-covered by `ADD_RESEARCH_OPTION_PERK_GRANTS`? |
| --- | --- |
| `tech_dyson_sphere` | Yes (`ap_galactic_wonders`) |
| `tech_matter_decompressor` | Yes (`ap_galactic_wonders`) |
| `tech_ring_world` | Yes (`ap_galactic_wonders`) |
| `tech_btc_1` | No |
| `tech_dragon_armor` | No |
| `tech_enigmatic_decoder` | No |
| `tech_enigmatic_encoder` | No |
| `tech_frameworld_defensive_station_2` | No |
| `tech_frameworld_defensive_station_3` | No |
| `tech_frameworld_defensive_station_4` | No |
| `tech_frameworld_defensive_station_5` | No |
| `tech_gargantuan_evolution` | No |
| `tech_leviathan_techgenesis` | No |
| `tech_lgate_activation` | No |
| `tech_nanite_autocannon` | No |
| `tech_nanite_flak_batteries` | No |
| `tech_nanite_repair_system` | No |
| `tech_neuroregeneration` | No |
| `tech_orbital_trash_dispersal` | No |
| `tech_prescient_data_modeling` | No |
| `tech_psionic_barrier` | No |
| `tech_regenerative_hull_tissue` | No |
| `tech_subspace_drive` | No |
| `tech_xeno_linguistics` | No |

3 pre-covered (already badge "Needs Galactic Wonders", untouched by this fix — no double-handling:
their existing gate badge is a completely separate mechanism from availability, and both now
correctly co-exist: `tech_dyson_sphere`/`tech_matter_decompressor` show `locked` for the 6
nomadic profiles — Galactic Wonders' own real axis restriction, unrelated to this fix — and
`weight-gated` for the other 6; `tech_ring_world` has no `potential` restriction of its own, so it
is `weight-gated` for all 12). 21 gain a NEW `weight-gated` verdict the pre-fix pipeline never
produced at all — except `tech_btc_1`, `tech_lgate_activation` and `tech_xeno_linguistics`, whose
own `potential` is never plainly AVAILABLE for any profile to begin with (uncertain/locked for an
unrelated reason in every profile), so `_apply_weight_gate` never even reaches them — this fix has
zero VISIBLE effect for exactly these three, reported rather than silently asserted away.

**Per-state population, full 12×973 matrix, verified directly (not estimated):**

| State | Before | After |
| --- | ---: | ---: |
| available | 8,278 | 8,038 |
| locked | 1,466 | 1,466 |
| uncertain | 482 | 482 |
| config-gated | 600 | 600 |
| weight-gated | 850 | 1,090 |
| **Total** | **11,676** | **11,676** |

`weight-gated`: 850/85 technologies → 1,090/106 technologies (+240 pairs / +21 technologies — all
from Item 2; Item 1 contributes exactly 0 pairs, per the finding above). `available` drops by
exactly 240 (240 pairs move `available` → `weight-gated`, everything else held fixed) — the ENTIRE
net movement is Item 2 pulling previously (wrongly) `available` bare-zero-factor technologies into
their correct `weight-gated` state; `locked`/`uncertain`/`config-gated` are untouched to the pair,
confirming neither fix reached into those buckets.

**D-10's three figures, confirmed via `build_diagnostics` directly, EXACTLY unchanged:** unconditional
uncertainty 31/973 (3.186%), worst profile-dependent 16/973 (1.6444%), union (`uncertainTechnologies`)
53 — expected, since `_apply_weight_gate` only ever fires on a `potential`-derived AVAILABLE result
and never itself produces UNCERTAIN; neither fix touches an UNCERTAIN leaf.

Gate counts (274 direct / 643 total) are unaffected by either fix — confirmed by rebuilding the real
dataset and recomputing both figures directly against it (`274`/`643`, `Counter` breakdown by kind
identical to the prior session's own table) — none of the 24 bare-zero-factor blocks (now
synthetic EMPTY Blocks) ever classify to a registered gate pattern, and the 9 country-type
technologies' gate classification is untouched by an availability-only fix.

## Gate-count reconciliation (multi-kind matching, direct vs. inherited growth)

The prior session's survey predicted 110 entry-level matches (ascension_perk 59, origin 5,
ethics_or_civic 14, technology 32) from running `classify_weight_gate_condition` over the
206 zero-factor `weight_modifier` blocks, and the actual DIRECT gate-instance total moved 107 → 274
(+167). Reconciled directly against the current pipeline (not re-assumed):

- Re-running `classify_weight_gate_condition` over every `weight_gate_conditions` block today finds
  **109 condition-block entries carry at least one match** (1 short of the survey's 110 — expected
  methodology drift, the same tolerance this project's own prior session already established for
  the parallel "90 vs 87 technologies" gap, not chased further), across **90 distinct technologies**.
- Those 109 entries produce **173 raw `GateMatch` instances** — 43 entries produce MORE than one
  instance each (multi-kind matches, e.g. an `OR`/`NOR`-alternative group naming several distinct
  perks/technologies), contributing 64 instances beyond one-per-entry (109 + 64 = 173). Kind
  breakdown of the 173 raw matches: ascension_perk 64, technology 67, ethics_or_civic 32, origin 10.
- Of those 173, **6 dedupe against an already-existing `potential`-derived direct gate of the same
  `(kind, refId)`** on the same technology (the 6 `tech_lathe_*` technologies, each redundantly
  re-matching `ap_cosmogenesis`) and are dropped before reaching the card's `gates` field.
- **173 − 6 = 167 net NEW direct gate instances** — exactly the observed 107 → 274 growth. Multi-kind
  matching is therefore the full, shown (not assumed) explanation: 109 entries is close to the
  survey's 110, and it is the 64 extra multi-kind instances (minus the 6 real dedup collisions) that
  turn ~110 entries into +167 net direct instances, not a discrepancy needing further chasing.
- The TOTAL gate-instance growth (214 → 643, +429) decomposes as **+167 direct** (above) **+262
  newly-inherited** (429 − 167 = 262) — the same pre-existing `prerequisite`-chain propagation
  mechanism (unchanged by this session) now also propagating these 167 new direct weight-derived
  gates down to their descendants, exactly as it already does for `potential`-derived direct gates.
  Not a new cascade bug — the largest single gates list after the full weight-condition-extraction
  session was still 11 entries (documented already), unaffected by this reconciliation.

## Item 3 (report only — no implementation)

Sizing the remaining gap: `factor` values expressed as an `@variable` reference or a `value:X`
scripted-value reference are skipped unconditionally by `_weight_gate_condition_blocks` (both the
pre-existing `modifier`-wrapped path and this session's new bare-top-level path), since neither is
a `NumberLiteral`.

**(a) `@variable` factor references: verified, zero resolve to literal zero.** Scanning every
rendered technology's `weight_modifier` (bare top-level factor AND `modifier`-wrapped factor, both
paths) for a `VariableReference` factor value finds **1,372 entries** (close to the investigation's
1,336 — expected minor methodology drift, e.g. whether a technology's OWN multiple `modifier`
sub-blocks are each counted once) resolving to **16 distinct variable names**, every one already
declared as a `scripted_variables` entry `pipeline.variables.VariableTable` resolves cleanly (zero
resolution errors). Resolving all 16 via the existing `VariableTable.resolve` machinery:
`EnigmaticEngineeringDraw` 0.025, `ap_grasp_the_void_travel_tech` 1.5, `ap_pending_tech_boost` 10,
`eager_explorer_effect` 5, `federation_perk_factor` 2, `giga_tech_weight_boost_five` 5,
`giga_tech_weight_boost_greater` 4, `giga_tech_weight_boost_large` 2,
`giga_tech_weight_boost_massive` 6, `giga_tech_weight_boost_medium` 1.5,
`giga_tech_weight_boost_small` 1.25, `giga_tech_weight_boost_ten` 10,
`giga_tech_weight_malus_large` 0.5, `giga_tech_weight_malus_medium` 0.75,
`repatableTechFactor` 0.5, `storm_chasers_storm_tech_weight_mult` 2.0. **None is zero** — this
population is a real, size-able weight SCALING concern (boosts/penalties), never a hidden gate;
no false negative exists here today. Cheap to check (as expected): `pipeline.variables` already
does the resolution, no new machinery needed to confirm this.

**(b) `value:X` scripted-value references: CANNOT be resolved with the current pipeline/vendored
corpus at all — this is real new work, not a cheap check.** 26 entries (close to the
investigation's 27) reference 2 distinct scripted values (`storm_callers_councilor_tech_discovery_
chance_multiplier`, `tech_weight_likelihood`). No `pipeline.scripted_values`-equivalent module
exists, and — checked directly, not assumed — **no `common/scripted_values` directory is vendored
by any of the four sources at all** (it is not one of CLAUDE.md's required directories). Resolving
these would require: (1) adding `common/scripted_values` to every source's required-directory list
and `tools/collect_vanilla.py`'s collection scope, (2) vendoring it (a `collect_vanilla.py`/manual
re-vendor step outside this session's scope), (3) building a NEW resolution module analogous to
`pipeline.variables` (scripted values have their own, more complex trigger-based conditional-value
shape in Stellaris, not simply `@name = <literal>` — a materially different, larger parser/resolver
surface than variable resolution). None of this exists today.

**(c) Moot given (a) and (b): zero new `weight-gated` pairs are knowable from either source without
new work.** (a) found no zero-resolving `@variable`, so no new pairs there. (b) cannot be evaluated
at all without vendoring a new source directory and writing a new resolution module — sizing that
work (not doing it) is the deliverable here: a `pipeline.scripted_values` module comparable in scope
to `pipeline.variables` (242 lines), plus updating `_load_expanded`/`_weight_gate_condition_blocks`
to consult it, plus a corpus re-vendor to actually populate `common/scripted_values/`. Until that
work happens, both `storm_callers_councilor_tech_discovery_chance_multiplier` and
`tech_weight_likelihood` remain an acknowledged, unquantified blind spot — reported plainly rather
than guessed at.

## Known unmodelled case: `add = N` weight modifiers

6 real corpus entries (`tech_terrestrial_sculpting`, `tech_xeno_linguistics`, `tech_crystal_armor_1`,
`giga_tech_maginot_world` ×2, `tech_mine_rare_crystals`) use `add = N` inside a `weight_modifier`
`modifier` block instead of `factor = N` — a structurally different additive mechanic (adds to the
base weight rather than multiplying it), never a hard zero-or-nonzero gate concern the way `factor`
is. Confirmed real, deliberately left unmodelled per this session's own scope fence — no
implementation, no config file, no suppression.

Full suite: pytest all pipeline tests pass (vendor populated; two new regression tests added:
`tests/test_availability.py::test_country_type_fallen_and_awakened_resolve_false_as_ground_facts`
and `tests/test_dataset_emit.py::test_weight_gate_condition_blocks_catches_bare_top_level_zero_factor`
plus `test_country_type_ground_fact_and_bare_zero_factor_real_corpus_effect` against the real
corpus — each individually confirmed capable of failing against the pre-fix code before being
trusted). `tsc --noEmit` clean, `vite build` clean, a real `tools/build_dataset.py` rebuild against
the corrected pipeline, and headless-Chromium verification (Playwright, driven via CDP) against the
rebuilt `client/dist`: 0 console errors, 0 failed requests; `tech_dark_matter_deflector` and
`tech_nanite_flak_batteries` both show `weight-gated` across all 12 profiles in the live dataset,
`tech_dyson_sphere` shows its pre-existing `ascension_perk: ap_galactic_wonders` gate badge
undisturbed alongside its new `weight-gated`/`locked` split.

## Session: weight-gate suppression config, and a copy split by resolution

**Item 3 (verify-first, no defect found).** User-reported: `tech_xeno_linguistics`'s `potential`
block (`has_paragon_dlc = yes, is_regular_empire = yes, is_gestalt = no, is_homicidal = no`) is on
the TECHNOLOGY ITSELF (`vendor/stellaris/common/technology/00_soc_tech.txt:6592`), not an
event/origin — confirmed directly against raw source, `vendor/stellaris/` genuinely has no
`events/`/`common/on_actions/`/`common/origins/` to check against for the alternative. Direct
evaluation confirms all 8 gestalt profiles resolve `locked` (`is_regular_empire = yes` fails for
hive/machine authority, and Kleene AND correctly lets that FALSE dominate the unresolved
`is_homicidal` sibling); the 4 regular profiles resolve `uncertain` (`is_homicidal` is genuinely
unmodelled, correctly falling through to UNKNOWN rather than `EXCLUDED`). This matches this
session's earlier finding (`tech_xeno_linguistics` is one of the 3 technologies where the prior
session's weight-condition gate extraction has zero VISIBLE effect, since its `potential` was
never plainly AVAILABLE to begin with — see the "21 gain a NEW `weight-gated` verdict" note
above). `is_regular_empire` is a registered `AXIS_FACTS` entry; `is_homicidal` is in neither
`EXCLUDED_KEYS` nor `NOT_GATE_CLASSIFIED_EXCLUDED_KEYS` — an unmodelled leaf resolving UNCERTAIN is
correct behaviour, not the EXCLUDED-as-vacuously-satisfied defect class. No defect; proceeded to
Items 1/2.

**Item 1: suppression config.** Real corpus mechanism shapes, derived directly (not guessed) by
enumerating every leaf inside `BuildContext.weight_gate_conditions` (the already-extracted
zero-factor condition blocks): `years_passed < 5` (1), `num_owned_planets < 2` (14),
`any_owned_nonprimary_starbase = { ... }` (3, a scope-block leaf, matched by key alone),
`num_communications < 1` (5) and `< 2` (1, `tech_galactic_markets`) — one config entry (`< 2`)
covers both, since a stricter corpus threshold is still at least as trivial —
`any_planet_within_border = { ... }` (5, matched by key alone, deliberately distinct from the
retained `any_owned_planet`/`has_deposit` leaves that can appear as AND/OR siblings in the SAME
condition), and `has_country_flag` ending in `_found` (8: `sr_dark_matter_found`,
`rare_crystals_found`, `volatile_motes_found`, `negative_mass_found`, `exotic_gases_found`,
`sr_living_metal_found`, `giga_sr_amb_megaconstruction_found`, plus one already covered by the
threshold count above) — confirmed the suffix pattern does NOT accidentally catch
`has_market_access` (31 occurrences, a completely different mechanism) or `found_presapients` (a
literal-but-unrelated "found" substring). 37 total leaf instances, `config/
weight_gate_suppressions.txt`, `pipeline/weight_gate_suppressions.py`.

**The identity-element trap, caught before shipping.** An early design treated a suppressed leaf
exactly like `EXCLUDED_KEYS` (drop it, let the rest of the AND/OR/NOT/NOR structure decide) — this
is UNSOUND here. Real corpus case: `tech_mine_rare_crystals`'s nomadic-branch modifier is `AND
(is_nomadic = yes, NOT { has_country_flag = rare_crystals_found })`. Dropping the flag leaf as an
identity element leaves `is_nomadic = yes` as the AND's sole relevant child — a real `AXIS_FACTS`
leaf — which the evaluator then (correctly, by its own existing rules) reports as a definite,
`axis_pure` TRUE, producing a false `locked` verdict for every nomadic profile, purely because the
identity element let an unrelated axis fact "decide" a condition it was never meant to decide
alone. Traced and confirmed by hand before this design shipped (`_combine_and`'s exact filtering
behaviour, not a hypothetical). Fixed by resolving a suppressed leaf to a FIXED CONSTANT instead
(`resolves_to` in the config: `false` for a "hasn't happened yet" threshold, `true` for a positive
existence/flag check) — standard Kleene boolean composition then handles every nesting shape
correctly with no special-casing: for the SAME `tech_mine_rare_crystals` case, `has_country_flag`
resolves to a constant `true` (presume found), `NOT(true) = false`, `AND(is_nomadic=yes, false) =
false` — the whole modifier correctly contributes nothing, exactly the "stays AVAILABLE" outcome
Item 1 asked for, with no false LOCKED. Verified against the non-nomadic sibling modifier too
(`is_nomadic = no AND NOT { any_owned_planet{...}, any_planet_within_border{...} }`): suppressing
only `any_planet_within_border` and resolving it `true` leaves the retained, unmodelled
`any_owned_planet` leaf as the sole UNKNOWN contributor — the technology correctly stays
`weight-gated` (via the retained real gate), not incorrectly forced to AVAILABLE. See
`docs/DEFECTS.md`'s "EXCLUDED-as-vacuously-satisfied" section and `spec/decisions.md`'s D-4
Extension for the full writeup.

**Figures, verified directly against the real corpus (`pipeline.dataset_emit.build_context`, full
12-profile evaluation, before vs. after suppression):**

| State | Before | After |
| --- | ---: | ---: |
| available | 8,038 | 8,228 |
| locked | 1,466 | 1,466 |
| uncertain | 482 | 482 |
| config-gated | 600 | 600 |
| weight-gated | 1,090 | 900 |
| **Total** | **11,676** | **11,676** |

`weight-gated`: 1,090/106 technologies → 900/89 technologies (−190 pairs / −17 technologies).
`available` rises by exactly 190 (the entire net movement) — reconciles exactly with the 190
pairs suppression moves out of `weight-gated`; `locked`/`uncertain`/`config-gated` untouched to
the pair, confirming suppression never reaches those buckets (by construction: `_apply_weight_gate`
only ever runs when the `potential`-derived result is already AVAILABLE). D-10's three figures,
confirmed unchanged (suppression never produces UNCERTAIN — `_apply_weight_gate` only ever
consumes an already-AVAILABLE `potential` result): unconditional uncertainty 31/973, worst
profile-dependent 16/973 (`hive_mind`/biological/non-nomadic, 0.016444), union
(`uncertainTechnologies`) 53.

**Item 2: copy split, resolution breakdown of the 900 remaining `weight-gated` pairs:** 120
resolve definitely TRUE (before suppression: 120 — suppression's 190 removed pairs were entirely
ex-UNKNOWN, 0 ex-TRUE), 516 UNKNOWN (before: 706 — the full −190 delta), 240 unconditional
bare-`factor=0` (unaffected, no condition to resolve), 24 `always=yes` (unaffected). Two new
copy strings for the TRUE/UNKNOWN split (`pipeline.availability._WEIGHT_GATE_TRUE_ROUTE`/
`_WEIGHT_GATE_UNRESOLVED_ROUTE`); the unconditional and `always=yes` strings are untouched
verbatim. Presentation-only — no `AvailabilityState` change, confirmed by the per-state table
above (the `weight-gated` row total obviously changes from suppression, but nothing crosses
between states as a result of the copy split itself).

**Suppression visibility**: `pipeline.dataset_emit.build_diagnostics`'s new
`weightGateSuppressions` array reports each config entry's real corpus `matchCount` (37 total
across the six entries, individually: `num_owned_planets` 14, `has_country_flag` 8,
`num_communications` 6, `any_planet_within_border` 5, `any_owned_nonprimary_starbase` 3,
`years_passed` 1) — a future entry matching zero is visible there as a stale rule, never a silent
no-op.

Verification: full pytest suite (1,520 passed after fixing one existing test's hand-built
diagnostics document, `tests/test_availability_corpus.py::test_d10_diagnostics_section_is_schema_valid`,
missing the new required `weightGateSuppressions` schema field — not a regression, the schema
gained a new required property this session), a dedicated `tests/test_weight_gate_suppressions.py`
(config-loader errors: missing arrow, missing justification, invalid bool, unrecognised shape,
duplicate leaf key; matcher correctness: stricter/looser numeric thresholds, suffix matching
including the two negative cases above, bare-key matching through nested scope content, AND/NOT/NOR
descent), `tsc --noEmit` clean, `vite build` clean, headless Playwright verification against the
rebuilt `client/dist` (0 console errors, 0 failed requests).
