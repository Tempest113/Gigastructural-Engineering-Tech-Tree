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

