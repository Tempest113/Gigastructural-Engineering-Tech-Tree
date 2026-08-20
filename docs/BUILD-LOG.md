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
