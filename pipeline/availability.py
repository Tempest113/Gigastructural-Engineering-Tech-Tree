"""D-10/P-13: partial trigger evaluator.

Produces `(technology, empire profile) -> {state, reason}`, state always one of
`available` / `locked` / `uncertain` / `config-gated` / `weight-gated` (schema's
`AvailabilityState`, renamed from `ThreeState` when the fourth value was added, now carrying a
fifth — see `spec/decisions.md`'s D-10) — **never** a boolean. `weight-gated` (`_apply_weight_gate`
below) is the newest: a `weight_modifier` zero-factor condition that fires or can't be resolved,
narrower than a straightforward LOCKED because static analysis can't see `give_technology`/event/
special-project/archaeology/relic routes that bypass the weighted draw entirely. `unknown` (here: `uncertain`) propagates through boolean structure exactly like it
does in Stellaris's own trigger engine (Kleene three-valued logic): a `false` branch under `AND`
or a `true` branch under `OR` short-circuits regardless of an undecidable sibling, which is the
mechanism that separates D-10's profile-dependent metric from its unconditional one — see
CLAUDE.md's "Availability evaluator" section for the full reasoning.

Three documented assumptions ground this evaluator's leaf resolution (also recorded in
CLAUDE.md, not silently baked in here):

1. Mod-config content-toggle global flags (`pipeline.trigger_text.MOD_CONFIG_TOGGLE_SUFFIXES` —
   `*_forbidden`/`*_disabled`/`*_OFF`, confirmed by corpus survey to be the dominant
   `has_global_flag` shape, e.g. `acot_weapons_forbidden`, `aot_phanon_content_OFF`; plus
   `*_capped_r`, confirmed by the user rather than a general convention — see that module for the
   distinct evidence behind each) resolve to their unset default. Flags outside that naming
   pattern (`compound_invasion_happened`, `blokkat_crisis_defeated`, `l_cluster_opened`,
   `has_aot_mod`, ...) are real, undecidable game/story state and are deliberately NOT covered by
   this assumption — resolving those would be a guess, not a documented default. **When a
   mod-config leaf is the one responsible for an overall FALSE result, the state emitted is
   `config-gated`, not `locked`** — see `CONFIG_GATED` and `evaluate_trigger_block` below: unlike
   an ordinary LOCKED technology, nothing about the empire being played is what's stopping the
   player, a game option is.
2. All official DLC assumed owned (`has_dlc`, `host_has_dlc`).
3. Not-a-fallen-empire is a ground fact of all twelve profiles (`is_fallen_empire`,
   `merg_is_fallen_empire` always resolve `no`).

`has_technology` leaves are explicitly OUT OF SCOPE for this evaluator — they are
prerequisite-graph reachability (P-14), handled by a separate structural check over the DAG, not
a trigger truth value.

**`has_ascension_perk` is a narrower exclusion than it used to be (a later session, correcting
CLAUDE.md's own locked decision).** D-6/P-1's original wording ("ascension perks are gates, not
profile facts") was refuted by real corpus content and by the user's domain knowledge: Galactic
Wonders (and several other perks) carry a genuine axis restriction in their own `potential`
(nomadic empires can never take it), so a technology gated behind it is not merely "needs a perk
choice" for those profiles — it is structurally LOCKED, the same as any other axis-impossible
technology. The corrected rule, automated rather than hand-curated: WHICH perk a player picks
remains a free choice, never resolved either way (still `EXCLUDED` when the referenced perk's own
`potential` is satisfiable-or-uncertain for the current profile); WHETHER a perk is obtainable AT
ALL for an empire type is a real fact, resolved by evaluating the target perk's own `potential`
block (registered via `set_perk_potentials`) against the same profile, through this exact
evaluator. Only a definite `LOCKED` result for the perk turns the `has_ascension_perk` leaf into a
real `FALSE` (propagating like any other failed AND-branch); a perk that is merely `UNCERTAIN` for
some profile is left `EXCLUDED`, same as before — the survey found no perk that would need that
guess, and this evaluator does not make it. See CLAUDE.md's "Ascension perks are gates ..."
section for the real corpus counts (21 perks cleanly axis-restricted, 20 with residual undecidable
conditions left as gate-only).

Folding an ordinarily-EXCLUDED leaf into `uncertain` would still be a category error — this
correction only ever turns EXCLUDED into a real FALSE, never into UNCERTAIN, so `has_ascension_perk`
remains outside `uncertain`'s accounting exactly as before. See `EXCLUDED_KEYS` and `_State.EXCLUDED`.

The trigger-condition -> human-readable-text renderer HANDOFF.md flagged as missing
("no trigger-condition -> human-readable-text renderer exists yet") is now `pipeline.trigger_text`
— built as a shared component (not private to this module) so it also serves P-12.8's
weight-modifier condition text. `AvailabilityResult.reason` stays the raw trigger source text
(P-13: "the trigger *text* is always known"); `.description` is that module's best-effort
phrasing of the same leaf, falling back to the raw text where no phrasing is known rather than
fabricating prose; `.category` (`ReasonCategory`, UNCERTAIN results only) classifies *why* a leaf
was undecidable, so Stage 3 can render "requires the Blokkat crisis chain" differently from
"unavailable for unknown reasons" instead of one flat unknown string.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable

from .clausewitz.nodes import (
    Assignment,
    Block,
    Comment,
    ConditionalBlock,
    Identifier,
    NumberLiteral,
    StringLiteral,
    VariableReference,
)
from .trigger_text import (
    MOD_CONFIG_TOGGLE_SUFFIXES,
    ReasonCategory,
    categorize_leaf,
    describe_condition,
    looks_like_story_progress,
)

AVAILABLE = "available"
LOCKED = "locked"
UNCERTAIN = "uncertain"
# D-10 (spec/decisions.md): a technology whose `potential` resolves definitively to FALSE because
# of a mod-configuration toggle (MOD_CONFIG_TOGGLE_SUFFIXES), not anything about the empire being
# played. Distinct from LOCKED, which elsewhere always means "your empire cannot obtain this" --
# rendering both the same way would tell a player content is off-limits when it's one options-
# menu toggle away. See schema/common.schema.json's AvailabilityState (renamed from ThreeState).
CONFIG_GATED = "config-gated"
# D-10's fifth state (a later session, correcting Item 2b's overbroad weight-modifier folding --
# see CLAUDE.md's "Research weight -> Extension" and `_apply_weight_gate`'s own docstring for the
# full reasoning). A `weight_modifier` zero-factor condition that fires (or cannot be resolved)
# means the technology is not currently OFFERED in the weighted research draw -- but unlike
# LOCKED, this says nothing about whether the empire's TYPE can ever obtain it: `give_technology`,
# events, special projects, archaeology and relics are all invisible to this static evaluator and
# can grant the technology regardless. Parallel to CONFIG_GATED: a real, determinate fact, never
# folded into D-10's uncertainty accounting.
WEIGHT_GATED = "weight-gated"

BOOLEAN_WRAPPERS = {"AND", "OR", "NOT", "NOR"}

# has_technology is P-14 prerequisite-graph reachability, not this evaluator's concern -- see
# module docstring. has_ascension_perk is a P-3 gate, not a profile fact (D-6/P-1: "Ascension
# perks are gates, not profile facts... the tree shows what you would need; it never assumes you
# have it") -- gate display is a separate mechanism layered on top of availability, not a trigger
# this evaluator resolves either way. Both excluded from boolean combination entirely (identity
# element), not resolved. Confirmed non-trivial in the real corpus, not a theoretical case: 181
# has_ascension_perk occurrences across vanilla+gigastructures technology potential blocks.
#
# has_gigastructural_constructs / has_galactic_wonders are two more, discovered during Task 3's
# category-distribution survey: both are Gigastructures' own custom scripted_triggers, and both
# were individually inspected (giga_scripted_triggers.txt / zzz_overwrites.txt) and confirmed to
# be pure `OR` chains of has_ascension_perk checks (plus an AI-only override branch this
# evaluator doesn't model) -- ascension-perk gates wearing a different name, not a new kind of
# undecidable leaf. Excluding them by name here (rather than leaving them to the UNKNOWN default)
# removed 18 technologies from the unconditional-uncertain bucket that were never actually
# uncertain, just gated.
EXCLUDED_KEYS = {
    "has_technology",
    "has_gigastructural_constructs",
    "has_galactic_wonders",
}
# `has_ascension_perk` is deliberately NOT in this set any more -- it gets its own leaf-evaluation
# branch below (`_evaluate_leaf`) so it can turn into a real FALSE when the referenced perk is
# axis-locked. It still behaves exactly like an EXCLUDED_KEYS entry (identity element, never
# UNCERTAIN) for every perk that ISN'T axis-locked for the current profile -- see the module
# docstring's "has_ascension_perk is a narrower exclusion" section.

# "Path to zero uncertain" follow-up session, Item 3: ethics/civic/origin conditions the
# three-axis empire model deliberately cannot represent, treated the same way ascension perks
# already are -- a display gate (P-3), never a profile fact. Extends `EXCLUDED_KEYS`'s identity-
# element treatment, not resolved either way. The survey that preceded this change confirmed none
# of the real corpus's 97 ethics/civic/origin-gated technologies is eligibility-IMPOSSIBLE for
# every empire type (every one is a real, obtainable combination for SOME profile) -- the
# distinguishing question a display gate answers ("what would you need") rather than the
# eligibility question availability answers ("can your empire type ever have this").
#
# Real corpus (survey + this session's own verification): 19 leaf keys.
# - Origin-shaped: `has_origin` (direct), `giga_has_frameworld_origin` / `is_wilderness_empire`
#   (both single 1:1 `has_origin = X` wrappers, confirmed by direct inspection --
#   `pipeline.gate_patterns.WRAPPER_TO_ORIGIN` badges these two), `is_void_dweller_empire`,
#   `has_void_dweller_origin`, `is_giga_one_planet_origin` (all three are genuinely COMPOUND --
#   an OR of multiple real sub-conditions, e.g. `is_void_dweller_empire` = ascension perk OR
#   origin -- no single clean gate target, so these are excluded from AVAILABILITY here but
#   deliberately NOT gate-badge-classified; see gate_patterns.py's own docstring).
# - Ethic/civic-shaped: `has_ethic`, `has_valid_civic`, `has_civic` (direct, all three badged --
#   `has_civic` is a DISTINCT leaf from `has_valid_civic`, missed by the first survey pass),
#   `is_fanatic_spiritualist` / `is_fanatic_pacifist` (single 1:1 `has_ethic = X` wrappers,
#   badged via `pipeline.gate_patterns.WRAPPER_TO_ETHIC`), `is_spiritualist`,
#   `is_natural_design_empire`, `is_beastmasters_empire`, `is_world_forger_empire` (all four
#   compound -- an OR of multiple civics/ethics -- excluded from availability, not gate-badged).
# - Not origin/civic/ethic-shaped at all, but the same "which choice, not which empire type"
#   character, excluded here for the same reason even though they get no gate badge:
#   `is_megacorp` (targets `has_authority`, a real 4th authority value outside this project's
#   3-axis model -- CLAUDE.md's own is_megacorp note), `is_individual_machine` (species-archetype
#   + gestalt check), `has_genetically_ascended` (tradition-path-completion check),
#   `is_infernal_empire` (species-trait check).
# - `can_research_technology`: an engine-builtin alias of `has_technology` (P-14 prerequisite-
#   graph reachability, not a scripted_trigger definition anywhere in the corpus, confirmed by
#   direct search) -- same treatment, same reason, badged via `pipeline.gate_patterns`
#   alongside `has_technology`.
EXCLUDED_KEYS |= {
    "has_origin",
    "giga_has_frameworld_origin",
    "is_wilderness_empire",
    "is_void_dweller_empire",
    "has_void_dweller_origin",
    "is_giga_one_planet_origin",
    "has_ethic",
    "has_valid_civic",
    "has_civic",
    "is_fanatic_spiritualist",
    "is_fanatic_pacifist",
    "is_spiritualist",
    "is_natural_design_empire",
    "is_beastmasters_empire",
    "is_world_forger_empire",
    "is_megacorp",
    "is_individual_machine",
    "has_genetically_ascended",
    "is_infernal_empire",
    "can_research_technology",
}

# Mod-config toggle suffixes: defined once in pipeline.trigger_text (MOD_CONFIG_TOGGLE_SUFFIXES)
# since trigger_text.categorize_leaf needs the exact same list to classify the leaf responsible
# for a FALSE result -- see that module for the full list and the evidence behind each suffix
# (CLAUDE.md's "Documented evaluator assumptions" for _forbidden/_disabled/_OFF; spec/decisions.md's
# D-10 for _capped_r). Names outside this pattern (compound_invasion_happened, l_cluster_opened,
# has_aot_mod, ...) are real undecidable state and deliberately excluded rather than swept in.

# Trigger-leaf name -> profile predicate. Confirmed real corpus keys (occurrence counts at survey
# time): is_nomadic (175), is_machine_empire (82), is_hive_empire (59), is_regular_empire (30),
# is_gestalt (43), country_uses_bio_ships (238 -- the real Stellaris shipset trigger; P-1's
# illustrative `has_biological_ships` does not occur verbatim anywhere in the corpus).
# is_mechanical_empire / is_robot_empire (2 occurrences each) are treated identically to
# is_machine_empire per vanilla's own canonical semantics (both mean machine-intelligence
# authority, not the shipset axis, despite the "mechanical" name) -- too rare to have been
# individually surveyed further, but not ambiguous enough to leave unresolved.
AXIS_FACTS: dict[str, Callable[[dict], bool]] = {
    "is_nomadic": lambda p: p["nomadic"] == "yes",
    "is_machine_empire": lambda p: p["authority"] == "machine_intelligence",
    "is_mechanical_empire": lambda p: p["authority"] == "machine_intelligence",
    "is_robot_empire": lambda p: p["authority"] == "machine_intelligence",
    "is_hive_empire": lambda p: p["authority"] == "hive_mind",
    "is_regular_empire": lambda p: p["authority"] == "regular",
    "is_gestalt": lambda p: p["authority"] in ("hive_mind", "machine_intelligence"),
    "country_uses_bio_ships": lambda p: p["shipset"] == "biological",
}

# Item 5 (later session): `has_active_tradition` resolves TRUE by default -- a completed
# tradition tree is otherwise real per-playthrough state this evaluator can't know -- EXCEPT for a
# tradition category the user confirmed is unavailable to a whole empire type, checked one
# category at a time (same posture as `PROGRESSION_FLAGS_TRUE`: never a blanket pattern guess).
# Real corpus: exactly ONE `potential`-scoped occurrence of this leaf in all four sources,
# `giga_tech_the_vat`'s `has_active_tradition = tr_genetics_finish_extra_traits` -- the corpus's
# only other occurrence (`tr_unyielding_federations_finish`, Maginot) lives inside a
# `weight_modifier`, not `potential`, so it's out of scope for availability regardless (CLAUDE.md:
# weight is a separate concern from availability, conflating them is a category error). The user
# confirmed genetics-tradition-tree completion is unavailable to machine-intelligence empires
# (mechanical species can't pursue the Biological Ascension path), matched by category PREFIX
# (`tr_genetics`) rather than the single exact tradition name, since any other genetics-category
# tradition-finish check would carry the identical restriction if one is ever added.
TRADITION_CATEGORY_AXIS_RESTRICTIONS: dict[str, Callable[[dict], bool]] = {
    "tr_genetics": lambda p: p["authority"] != "machine_intelligence",
}


def _tradition_available(name: str, profile: dict) -> bool:
    for prefix, predicate in TRADITION_CATEGORY_AXIS_RESTRICTIONS.items():
        if name.startswith(prefix):
            return predicate(profile)
    return True

# Ground facts (documented assumptions 2 and 3): resolve to the same constant for every profile.
# Named per-DLC scripted triggers (has_shroud_dlc, has_paragon_dlc, ...) are NOT a separate
# resolution rule -- each was individually inspected (CLAUDE.md's "Documented evaluator
# assumptions") and confirmed to be a bare `host_has_dlc = "..."` wrapper (occasionally an OR of
# two, e.g. has_space_monster_dlc's Leviathans-or-Distant-Stars check), so they fall under the
# same "all official DLC assumed owned" assumption as a literal has_dlc/host_has_dlc leaf, just
# reached through a named indirection this evaluator doesn't generally resolve (it does not
# inline arbitrary scripted_triggers bodies -- that's a materially larger feature, matching
# pipeline.inline_scripts's scope for `inline_script` but for the different `scripted_triggers`
# call mechanism, not built here). Two adjacent triggers verified to NOT be pure DLC wrappers
# (has_gigastructural_constructs, has_galactic_wonders -- both actually OR chains of
# has_ascension_perk checks with an AI-only override branch) are deliberately left unresolved,
# falling through to UNKNOWN below, rather than guessed at.
# `has_dlc = "<name>"` / `host_has_dlc = "<name>"`: the value selects WHICH DLC, not a yes/no
# target -- always resolves True regardless of value under the all-DLC-owned assumption.
DLC_NAME_CHECK_KEYS = {"has_dlc", "host_has_dlc"}

# Named DLC-wrapper triggers are used `= yes`/`= no` (a real target polarity, unlike the two
# keys above), so they go through the same yes/no comparison as GROUND_FACT_BOOL below, with a
# constant `actual` of True (DLC owned) or False (not-a-fallen-empire) in place of a
# profile-derived one.
GROUND_FACT_BOOL: dict[str, bool] = {
    "has_astral_planes_dlc": True,
    "has_biogenesis_dlc": True,
    "has_cosmic_storms_dlc": True,
    "has_federations_dlc": True,
    "has_first_contact_dlc": True,
    "has_grand_archive_dlc": True,
    "has_machine_age_dlc": True,
    "has_nomads_dlc": True,
    "has_overlord_dlc": True,
    "has_paragon_dlc": True,
    "has_shroud_dlc": True,
    "has_space_monster_dlc": True,
    "has_nemesis": True,  # host_has_dlc = "Nemesis" wrapper, verified same as the others
    "has_infernals": True,  # host_has_dlc = "Infernals Species Pack" wrapper, verified same as the others
    "has_megacorp": True,  # MegaCorp DLC ownership -- same all-DLC-owned assumption as every
    # other named wrapper above. NOT the same leaf as `is_megacorp` (a real empire-type/civic
    # CHOICE fact -- "is this specific empire a Megacorporation" -- outside this project's 3-axis
    # model, deliberately left unresolved; conflating the two would wrongly claim every profile
    # IS a megacorp). Real corpus: 4 technologies (`tech_mega_art`, `tech_interstellar_assembly`,
    # `tech_matter_decompressor`, `tech_strategic_coordination`) carry `has_megacorp = yes` and
    # move from UNCERTAIN to AVAILABLE; `is_megacorp`-gated technologies (`tech_executive_retreat`,
    # `tech_xeno_tourism_agency`) are untouched by this entry.
    "has_ancrel": True,  # host_has_dlc = "Ancient Relics Story Pack" wrapper (vendor/stellaris/
    # common/scripted_triggers/00_scripted_triggers.txt:2678), verified same as every other named
    # DLC wrapper above -- NOT a Gigastructures relic-questline flag. A prior session's
    # pipeline.trigger_text categorisation claimed the opposite ("not a scripted_trigger
    # definition anywhere in the vendored corpus... a relic/precursor questline") without ever
    # checking raw source; that claim was wrong and is corrected here. Real corpus: resolves 23
    # technologies (the tech_archaeo_* family + tech_archeology_lab) from UNCERTAIN/
    # crisis_or_story_progress to AVAILABLE. See CLAUDE.md's "Availability evaluator" section for
    # the defect-class writeup.
    "has_acot": True,  # Item 2d: mod-content requirement, not DLC ownership -- this deployed
    # tree assumes ACOT (and AoT, which depends on ACOT) are always present, same as the existing
    # "renders vanilla + Gigastructures + ACOT + AoT" deployment assumption CLAUDE.md already
    # states. A technology gated on this is NOT uncertain about whether the CONTENT exists (the
    # pipeline already knows); resolving it true lets whatever ELSE actually gates the
    # technology (if anything) surface as the real reason. `pipeline.dataset_emit.
    # _potential_mod_requirements` separately adds the ACOT/AoT `requiresMods` badge these
    # technologies need -- that's presentation, this is availability, and they're deliberately
    # two different mechanisms even though both key off the same leaf.
    "is_fallen_empire": False,
    "merg_is_fallen_empire": False,
}

# Item 5 of the "commit + close the loop" follow-up session, user-confirmed: `acot_phanon_base` is
# an AI/event-only country type, never a player empire -- same "which country type would a player
# ever be" character as `is_fallen_empire` above, just keyed on a specific named country type
# rather than a bare yes/no leaf. `is_country_type = acot_phanon_base` therefore resolves FALSE
# unconditionally, same mechanism as GROUND_FACT_BOOL, just addressed by (key, value) instead of
# key alone since `is_country_type`'s target is a type name, not yes/no. Real corpus: 1 occurrence
# (`tech_dark_matter_power_core_se`'s `NOR = { is_fallen_empire = yes, is_country_type =
# acot_phanon_base } AND has_country_flag = stellarite_tech_enable`, acot_03_stellarite_
# components_tech.txt:709-715) -- the user confirmed the technology IS reachable by a player who
# has progressed far into ACOT's content, i.e. this is NOT a permanent-impossibility case; the
# `is_country_type` leaf was the wrong reason recorded and this fix corrects the leaf responsible
# for the technology's (still-genuine) UNCERTAIN result to `has_country_flag =
# stellarite_tech_enable`, real per-playthrough progression state, deliberately left unresolved.
# Only `acot_phanon_base` is confirmed here -- do NOT extend this to other `is_country_type` values
# without the same per-value confirmation this project's own methodology requires.
#
# Item 1 (a later session), user-confirmed ground fact: the player empire is always a standard
# (`is_country_type = default`) country type -- `fallen_empire` and `awakened_fallen_empire` are
# therefore never the player, same "which country type would a player ever be" character as
# `acot_phanon_base` above. Surveyed exhaustively (not guessed): across every rendered
# technology's `potential` AND zero-factor `weight_modifier` condition, walking the SAME AND/OR/
# NOT/NOR descent `_evaluate_node` itself uses (so a value nested inside an unrecognised scope
# switch like `any_relation`/`any_country` -- never reachable as a direct leaf by this evaluator
# regardless -- is correctly excluded from the count), exactly THREE `is_country_type` values are
# ever directly reachable: `acot_phanon_base` (1 technology, handled above), `fallen_empire` and
# `awakened_fallen_empire` (the same 9 technologies for both -- `tech_dark_matter_deflector`,
# `_power_core`, `_propulsion`, and the `tech_weaver_bio_*_6` family's six anti-fire-rate/evasion/
# anti-evasion/healing/fire-rate/confuser variants -- each a `NOR = { is_country_type =
# fallen_empire, is_country_type = awakened_fallen_empire }` zero-factor weight condition). No
# `marauder_*`/`enclave*` value is ever a direct leaf anywhere in the corpus -- both are named only
# inside CLAUDE.md's own request, not the corpus, so neither is added here.
#
# **Sole documented exception, per the user: `is_country_type = blokkat_stripminers` (and its
# `_ascended_country`/`_blokkwork`/`_defeated` variants) is deliberately NOT added to this set.**
# A player CAN become that country type mid-playthrough (the Blokkat crisis's conversion mechanic
# -- requires the crisis to spawn and the player to join it, itself empire-type-restricted), and
# country-type changes are unstable even in vanilla. Blokkat technologies are not touched by this
# fix and continue to be handled exactly as before (no `is_country_type = blokkat_stripminers*`
# leaf is directly reachable by this evaluator today regardless -- confirmed by the same survey --
# so this is a documented non-extension, not a behaviour change).
#
# **Real effect on the 9 `weaver_bio`/`dark_matter` technologies (verified against the built
# pipeline, not assumed): their AVAILABILITY STATE does not change.** Both leaves resolve a real
# `FALSE` now (previously `UNKNOWN`); `NOR` over two `FALSE` children is a real `TRUE` (the
# zero-weight condition provably fires for every player profile, not merely unresolved) --
# `_apply_weight_gate`'s non-axis-pure TRUE branch (`is_country_type` is a ground fact, not an
# `AXIS_FACTS` entry, so `axis_pure` stays False) reaches the exact same `WEIGHT_GATED` outcome the
# old UNKNOWN branch already reached. `description` text for these 9 technologies actually loses
# specificity (the NOR-of-two-FALSE-children TRUE result carries no single leaf per `_negate`'s own
# "FALSE inner -> leaf None" rule, where the old UNKNOWN branch happened to carry the first child's
# raw leaf text) -- `reason` (always the raw condition block text, independent of leaf resolution)
# is unaffected either way. Reported here rather than silently forced to an "available" outcome: the
# real value of this fix is that the WEIGHT_GATED verdict for these 9 technologies now rests on a
# proven fact instead of an accidentally-correct-looking UNKNOWN, not a state change.
COUNTRY_TYPE_NEVER_PLAYER = {"acot_phanon_base", "fallen_empire", "awakened_fallen_empire"}

# Item 2d companion: `has_global_flag = has_aot_mod` is AoT's own mod-presence flag (distinct
# shape from `has_acot`, which is a dedicated leaf key) -- same "assume present" reasoning,
# checked alongside `PROGRESSION_FLAGS_TRUE` in the `has_global_flag` branch below but kept in
# its own set since it's a different KIND of assumption (mod presence, not progression state) and
# must never be confused with a mod-config-toggle default (MOD_CONFIG_TOGGLE_SUFFIXES) either.
MOD_PRESENCE_FLAGS_TRUE = {"has_aot_mod"}

# Item 2b (user-confirmed, per-flag basis -- see this dict's own comment before adding an entry).
# A `has_country_flag`/`has_global_flag` name that names Gigastructures-internal PROGRESSION
# state reachable by every empire type, once its real eligibility gate (typically a separate
# `has_ascension_perk` check, already EXCLUDED from evaluation) is satisfied -- distinct from a
# genuine per-empire-type ELIGIBILITY gate, which must stay UNCERTAIN. Confirmed, one at a time,
# by the user (domain authority on the mod) -- NEVER blanket-resolved from a naming pattern, per
# this project's own "ask a specific game question rather than inferring" methodology. Only
# `colossus_project` is confirmed so far (set by the Colossus Project ascension perk once built;
# accessible to every empire type -- `has_country_flag = colossus_project`, real corpus: 6
# technologies, `tech_pk_cracker`/`tech_pk_godray`/`tech_pk_nanobots`/`tech_pk_neutron`/
# `tech_pk_shielder`/`tech_pk_smelter`). A larger candidate list was surveyed and presented to the
# user for confirmation before this session's implementation; see CLAUDE.md/docs/BUILD-LOG.md for
# the full candidate list and which remain open.
PROGRESSION_FLAGS_TRUE = {"colossus_project"}

# Item 2 of the "commit + close the loop" follow-up session: `pipeline.trigger_text.
# looks_like_story_progress`'s naming pattern (crisis-faction fragments; `_possible`/`_solved`/
# `_unlocked`/`_happened`/`_complete`/`_aborted`/`_knowledge`/`_opened` suffixes;
# `encountered_`/`completed_` prefixes), applied as a CLASS rather than one flag at a time, on the
# same evidence basis as `colossus_project` above: every sampled setting site is a real
# `is_triggered_only` country event with no empire-type restriction, confirmed by direct
# inspection, not inferred from the name alone. Real corpus: 64 distinct flag names (72
# technologies once `l_cluster_opened`/`encountered_first_lgate` below are set aside) move
# UNCERTAIN -> AVAILABLE.
#
# Two real matches are DELIBERATELY EXCLUDED from this class-wide resolution, even though their
# names fit the pattern (`_opened` suffix, `encountered_` prefix respectively) --
# `l_cluster_opened` and `encountered_first_lgate` are VANILLA Stellaris L-Gate storyline flags.
# Every other pattern match here is a Gigastructures flag whose setting site lives in vendored
# `common/`-adjacent script this project can and did inspect; vanilla's `events/`/`decisions/` are
# NOT vendored (CLAUDE.md's required-directories list), so there is no corpus text to check these
# two against -- resolving them would rest on outside-corpus knowledge of the base game, not
# evidence gathered the way this project requires. They stay UNCERTAIN, unresolved by the
# pattern, and are reported separately rather than silently swept in with the rest.
PROGRESSION_PATTERN_EXCLUDED_FLAGS = {"l_cluster_opened", "encountered_first_lgate"}

# has_country_flag: deliberately NOT resolved. The survey (HANDOFF.md CHECK 2) found no single
# resolvable pattern across 131 occurrences / 82 distinct names -- confirmed mid-game player
# state (herculean_built) and a plausible-but-unconfirmed ascension-perk redundancy
# (colossus_project) are the two directly-investigated examples; the remaining 80 names are
# read as crisis-chain/story-progression flags by naming convention, individually unverified.
# Falls through to the default UNKNOWN case below along with every other unrecognised leaf key
# (has_ascension_perk, num_owned_planets, is_ai_empire, ...).


class _State(Enum):
    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"
    EXCLUDED = "excluded"  # has_technology leaf: out of this evaluator's scope, see module docstring


@dataclass(frozen=True)
class _Eval:
    state: _State
    leaf: Assignment | None  # the leaf/wrapper Assignment responsible, when state is FALSE or UNKNOWN
    # Decision 4 (weight-gate LOCKED narrowing, a later session): True only when this result's
    # TRUE/FALSE resolution rests SOLELY on AXIS_FACTS leaves and/or `has_ascension_perk` leaves
    # whose own referenced perk resolved LOCKED for an axis-pure reason -- i.e. leaves that
    # genuinely distinguish between empire TYPES, never a ground fact (DLC, `always`, mod-config
    # toggle, progression flag) that's constant or circumstantial across every type. Meaningless
    # for UNKNOWN/EXCLUDED; consulted only by `_apply_weight_gate` on a TRUE result, never by
    # `evaluate_trigger_block`'s ordinary `potential` evaluation (which doesn't need this
    # distinction -- see that function's own LOCKED branch, unchanged by this addition).
    axis_pure: bool = False


@dataclass(frozen=True)
class AvailabilityResult:
    """One `(technology, empire profile)` result. `state` is always one of AVAILABLE / LOCKED /
    UNCERTAIN / CONFIG_GATED / WEIGHT_GATED (schema.AvailabilityState, renamed from ThreeState when
    the fourth value was added, now carrying a fifth) -- never a boolean, per D-10/P-13.

    `reason` is the raw trigger source text (P-13: "the trigger *text* is always known, only its
    truth value isn't"). `description` is `pipeline.trigger_text.describe_condition`'s
    best-effort human-readable phrasing of the same leaf -- may equal `reason` verbatim when no
    phrasing is known for that leaf key. `category` (`ReasonCategory`, see `pipeline.trigger_text`)
    is set when `state == UNCERTAIN` (why the leaf was undecidable) or `state == CONFIG_GATED`
    (always `MOD_CONFIGURATION` in that case); `None` for AVAILABLE/LOCKED."""

    state: str
    reason: str | None
    description: str | None = None
    category: ReasonCategory | None = None


def _value_text(value) -> str:
    if isinstance(value, Identifier):
        return value.name
    if isinstance(value, StringLiteral):
        return f'"{value.raw}"'
    if isinstance(value, NumberLiteral):
        return value.raw
    if isinstance(value, VariableReference):
        return f"@{value.name}"
    if isinstance(value, Block):
        inner = " ".join(_leaf_text(item) for item in value.items if isinstance(item, Assignment))
        return f"{{ {inner} }}" if inner else "{}"
    return "?"


def _leaf_text(assignment: Assignment) -> str:
    return f"{assignment.key_name} {assignment.operator} {_value_text(assignment.value)}"


def _yesno(value) -> bool | None:
    if isinstance(value, Identifier):
        if value.name == "yes":
            return True
        if value.name == "no":
            return False
    return None


def _is_mod_config_toggle_flag(name: str) -> bool:
    return name.endswith(MOD_CONFIG_TOGGLE_SUFFIXES)


# Registered once per build (`set_perk_potentials`) so `has_ascension_perk` leaves can consult
# each perk's own resolved (winner, post-overwrite) `potential` block -- see the module docstring's
# "has_ascension_perk is a narrower exclusion" section. Tests that never call
# `set_perk_potentials` get today's original all-perks-are-gates-only behaviour: an unregistered
# perk id is treated exactly like one with no restriction (EXCLUDED), never guessed at.
_perk_potentials: dict[str, Block | None] = {}
_perk_eval_in_progress: set[str] = set()


def set_perk_potentials(mapping: dict[str, Block | None]) -> None:
    """Registers every ascension perk's own winning `potential` block, keyed by perk id. Call once
    per build (`pipeline.dataset_emit.build_context`) before evaluating any technology's
    availability. A perk's own `potential` referencing ANOTHER registered perk resolves correctly,
    recursively -- including a real mutual-exclusion cycle in the corpus
    (`ap_defender_of_the_galaxy` <-> `ap_defender_of_the_galaxy_nomads`), broken by
    `_perk_eval_in_progress` rather than looping forever."""
    _perk_potentials.clear()
    _perk_potentials.update(mapping)


def _flag_value_name(value) -> str | None:
    if isinstance(value, Identifier):
        return value.name
    if isinstance(value, StringLiteral):
        return value.value
    return None


def _bool_eval(resolved: bool, negate: bool, leaf: Assignment, axis_pure: bool = False) -> _Eval:
    result = resolved != negate
    # Both branches now carry `leaf` (a change from the original TRUE-branch's `None`): harmless
    # for every existing caller, since `evaluate_trigger_block` only reads `.leaf` on a FALSE/
    # UNKNOWN result (a TRUE overall result maps straight to AVAILABLE without consulting it) --
    # but `_apply_weight_gate` needs to name the specific leaf responsible for a TRUE (zero-weight-
    # condition-met) result too, to phrase its LOCKED/WEIGHT_GATED description text.
    return _Eval(_State.TRUE, leaf, axis_pure) if result else _Eval(_State.FALSE, leaf, axis_pure)


def _evaluate_leaf(assignment: Assignment, profile: dict) -> _Eval:
    key = assignment.key_name
    negate = assignment.operator == "!="

    if key in EXCLUDED_KEYS:
        return _Eval(_State.EXCLUDED, None)

    if key == "has_ascension_perk":
        perk_id = _flag_value_name(assignment.value)
        # Real corpus has at least one mutual pair (`ap_defender_of_the_galaxy` <->
        # `ap_defender_of_the_galaxy_nomads`, each excluding the other via a `NOR =
        # { has_ascension_perk = <the other> }` superseded-perk guard) -- a real cycle, not a
        # hypothetical one, found by this exact recursion overflowing before the guard existed.
        # `_perk_eval_in_progress` breaks the cycle by treating a perk already being evaluated
        # higher up the same call stack as EXCLUDED (unresolved either way) rather than recursing
        # forever.
        if perk_id is not None and perk_id in _perk_potentials and perk_id not in _perk_eval_in_progress:
            perk_block = _perk_potentials[perk_id]
            if perk_block is None:
                return _Eval(_State.EXCLUDED, None)
            _perk_eval_in_progress.add(perk_id)
            try:
                # Single pass (a later session's perf fix -- a first version called both this AND
                # the public `evaluate_trigger_block` on the same block, doubling every axis-locked
                # perk's evaluation cost, measurable on the real corpus: ~4x slower per empire
                # overlay for machine-intelligence profiles, where axis-restricted perks are most
                # common). `perk_eval.state == FALSE` is exactly `evaluate_trigger_block`'s LOCKED
                # case; the `categorize_leaf` check below reproduces that function's own
                # LOCKED-vs-CONFIG_GATED split (a mod-config-toggle-caused FALSE must NOT turn this
                # leaf into a real FALSE -- that's a game OPTION, not an empire-type fact) without a
                # second full evaluation. `axis_pure` (Decision 4): a perk whose own `potential` is
                # LOCKED for a genuine axis reason makes THIS `has_ascension_perk` leaf axis_pure
                # too, per CLAUDE.md's D-6 correction ("a perk whose own potential carries a genuine
                # axis constraint" is a real profile fact, not a free choice).
                perk_children = [_evaluate_node(sub, profile) for sub in perk_block.items if isinstance(sub, Assignment)]
                perk_eval = _combine_and(perk_children)
            finally:
                _perk_eval_in_progress.discard(perk_id)
            if perk_eval.state == _State.FALSE:
                category = categorize_leaf(perk_eval.leaf) if perk_eval.leaf is not None else None
                if category != ReasonCategory.MOD_CONFIGURATION:
                    return _bool_eval(False, negate, assignment, axis_pure=perk_eval.axis_pure)
        return _Eval(_State.EXCLUDED, None)

    if key == "has_global_flag":
        flag_name = _flag_value_name(assignment.value)
        if flag_name is not None and _is_mod_config_toggle_flag(flag_name):
            return _bool_eval(False, negate, assignment)  # unset default: content not forbidden
        if flag_name is not None and (flag_name in PROGRESSION_FLAGS_TRUE or flag_name in MOD_PRESENCE_FLAGS_TRUE):
            return _bool_eval(True, negate, assignment)
        if (
            flag_name is not None
            and flag_name not in PROGRESSION_PATTERN_EXCLUDED_FLAGS
            and looks_like_story_progress(flag_name)
        ):
            return _bool_eval(True, negate, assignment)
        return _Eval(_State.UNKNOWN, assignment)

    if key == "has_country_flag":
        flag_name = _flag_value_name(assignment.value)
        if flag_name is not None and flag_name in PROGRESSION_FLAGS_TRUE:
            return _bool_eval(True, negate, assignment)
        if (
            flag_name is not None
            and flag_name not in PROGRESSION_PATTERN_EXCLUDED_FLAGS
            and looks_like_story_progress(flag_name)
        ):
            return _bool_eval(True, negate, assignment)
        return _Eval(_State.UNKNOWN, assignment)  # everything else: real per-playthrough state, deliberately unresolved

    if key == "always":
        # `always = yes`/`always = no` is a literal boolean constant, not a fact lookup -- the
        # leaf's own value IS the truth value. `always = no` at the top of a `potential` block is
        # already handled upstream (pipeline.rendering_scope._is_permanently_disabled excludes
        # those 4 technologies from rendering entirely, before this evaluator ever runs), but that
        # module only checks a direct top-level child; a NESTED `always = no`, or `always = yes`
        # anywhere, was never handled here and fell through to UNKNOWN -- confirmed real corpus
        # impact: `tech_ring_world`'s whole `potential` is `{ always = yes }`, reported uncertain
        # for every profile despite being the most trivially resolvable leaf in Clausewitz.
        resolved = _yesno(assignment.value)
        if resolved is None:
            return _Eval(_State.UNKNOWN, assignment)
        return _bool_eval(resolved, negate, assignment)

    if key == "has_active_tradition":
        name = _flag_value_name(assignment.value)
        if name is None:
            return _Eval(_State.UNKNOWN, assignment)
        return _bool_eval(_tradition_available(name, profile), negate, assignment)

    if key in DLC_NAME_CHECK_KEYS:
        return _bool_eval(True, negate, assignment)

    if key == "is_country_type":
        type_name = _flag_value_name(assignment.value)
        if type_name is not None and type_name in COUNTRY_TYPE_NEVER_PLAYER:
            return _bool_eval(False, negate, assignment)
        return _Eval(_State.UNKNOWN, assignment)

    if key in GROUND_FACT_BOOL:
        target = _yesno(assignment.value)
        if target is None:
            return _Eval(_State.UNKNOWN, assignment)
        return _bool_eval(GROUND_FACT_BOOL[key] == target, negate, assignment)

    if key in AXIS_FACTS:
        target = _yesno(assignment.value)
        if target is None:
            return _Eval(_State.UNKNOWN, assignment)
        actual = AXIS_FACTS[key](profile)
        return _bool_eval(actual == target, negate, assignment, axis_pure=True)

    return _Eval(_State.UNKNOWN, assignment)


def _combine_and(children: list[_Eval]) -> _Eval:
    relevant = [c for c in children if c.state != _State.EXCLUDED]
    if not relevant:
        return _Eval(_State.EXCLUDED, None)
    false_ones = [c for c in relevant if c.state == _State.FALSE]
    if false_ones:
        return _Eval(_State.FALSE, false_ones[0].leaf, axis_pure=false_ones[0].axis_pure)
    unknown_ones = [c for c in relevant if c.state == _State.UNKNOWN]
    if unknown_ones:
        return _Eval(_State.UNKNOWN, unknown_ones[0].leaf)
    # Every relevant child is TRUE: AND's own axis_pure requires ALL of them to be (decision 4 --
    # a single non-axis TRUE branch is enough to make the whole conjunction's truth not solely an
    # empire-type fact). `leaf` is only kept when there's exactly one relevant child -- with more
    # than one, no single leaf explains the combined TRUE, so text generation falls back to the
    # raw block text instead (see `_apply_weight_gate`).
    return _Eval(_State.TRUE, relevant[0].leaf if len(relevant) == 1 else None, axis_pure=all(c.axis_pure for c in relevant))


def _combine_or(children: list[_Eval]) -> _Eval:
    relevant = [c for c in children if c.state != _State.EXCLUDED]
    if not relevant:
        return _Eval(_State.EXCLUDED, None)
    true_ones = [c for c in relevant if c.state == _State.TRUE]
    if true_ones:
        # OR's axis_pure is conservative: True only when EVERY true branch is itself axis_pure --
        # `_combine_or` doesn't track which branch's truth "actually" explains the overall TRUE,
        # so a non-axis TRUE sibling alongside an axis-pure TRUE sibling must not let the whole OR
        # claim a real empire-type distinction (decision 4's "actually distinguishes between
        # empire types" bar -- err toward WEIGHT_GATED, never a false LOCKED).
        leaf = true_ones[0].leaf if len(true_ones) == 1 else None
        return _Eval(_State.TRUE, leaf, axis_pure=all(c.axis_pure for c in true_ones))
    unknown_ones = [c for c in relevant if c.state == _State.UNKNOWN]
    if unknown_ones:
        return _Eval(_State.UNKNOWN, unknown_ones[0].leaf)
    # Every RELEVANT (non-EXCLUDED) child is FALSE at this point. Item 2 (later session): if an
    # EXCLUDED sibling was filtered out above, it is a gate-only branch this evaluator
    # deliberately never rules out (an ordinary has_technology/has_ascension_perk choice) -- a
    # hard FALSE elsewhere in the same OR must not close off a branch that's still a live,
    # unresolved possibility. Real corpus case this fixes: `giga_tech_ringworld_titanic_1`'s
    # `OR = { has_ascension_perk = ap_galactic_wonders, has_ascension_perk =
    # ap_galactic_wonders_utopia }` -- for a non-nomadic profile the first branch is an ordinary
    # achievable gate (EXCLUDED) while the second is a real axis-locked FALSE (a permanently
    # disabled legacy perk); the whole OR must read as "still gated," not "locked," since the
    # first branch remains open. Before `has_ascension_perk` could ever become a real FALSE (Item
    # 2), no leaf that was sometimes EXCLUDED and sometimes FALSE existed, so this case never
    # arose and `relevant[0]` alone (this function's PRE-Item-2 behaviour) was safe.
    if len(relevant) < len(children):
        return _Eval(_State.EXCLUDED, None)
    return _Eval(_State.FALSE, relevant[0].leaf, axis_pure=relevant[0].axis_pure)


def _negate(inner: _Eval, wrapper: Assignment) -> _Eval:
    if inner.state == _State.TRUE:
        return _Eval(_State.FALSE, wrapper, axis_pure=inner.axis_pure)
    if inner.state == _State.FALSE:
        return _Eval(_State.TRUE, None, axis_pure=inner.axis_pure)
    return inner  # UNKNOWN / EXCLUDED propagate unchanged


def _evaluate_node(item, profile: dict) -> _Eval:
    if isinstance(item, (Comment, ConditionalBlock)):
        # Inline_script guard conditionals are expected to already be resolved by
        # pipeline.inline_scripts before this evaluator ever sees the block (see that module) --
        # treated as neutral/excluded here rather than guessed at if one somehow survives.
        return _Eval(_State.EXCLUDED, None)

    assert isinstance(item, Assignment)
    key = item.key_name
    # Case-insensitive: the corpus uses both `NOT = { ... }` (dominant, 301 occurrences) and
    # `not = { ... }` (17 occurrences) for the same wrapper -- confirmed real across all four
    # boolean-wrapper keywords, not a typo (e.g. giga_02_society.txt's `not = { any_owned_planet
    # = { ... } }`). Matching only the uppercase form would silently treat a real lowercase
    # wrapper as an unrecognised leaf.
    key_upper = key.upper()
    if key_upper in BOOLEAN_WRAPPERS and isinstance(item.value, Block):
        children = [_evaluate_node(sub, profile) for sub in item.value.items if isinstance(sub, Assignment)]
        if key_upper == "AND":
            return _combine_and(children)
        if key_upper == "OR":
            return _combine_or(children)
        if key_upper == "NOT":
            return _negate(_combine_and(children), item)
        if key_upper == "NOR":
            return _negate(_combine_or(children), item)

    return _evaluate_leaf(item, profile)


def evaluate_trigger_block(block: Block | None, profile: dict) -> AvailabilityResult:
    """Evaluate a `potential`-shaped trigger block (or any block with the same implicit-AND
    top-level semantics) against one empire profile's facts. `block=None` (no `potential` at
    all) is unconditionally AVAILABLE -- confirmed real, not assumed: 437/1,879 canonical
    technologies carry no `potential` block (HANDOFF.md's D-10 survey baseline)."""
    if block is None:
        return AvailabilityResult(AVAILABLE, None)

    children = [_evaluate_node(item, profile) for item in block.items if isinstance(item, Assignment)]
    result = _combine_and(children)

    if result.state in (_State.TRUE, _State.EXCLUDED):
        return AvailabilityResult(AVAILABLE, None)

    reason = _leaf_text(result.leaf) if result.leaf is not None else None
    description = describe_condition(result.leaf) if result.leaf is not None else None

    if result.state == _State.FALSE:
        # A definitively-FALSE leaf is usually an empire-state property (LOCKED, unchanged
        # meaning). The one exception: a mod-configuration toggle (MOD_CONFIG_TOGGLE_SUFFIXES) --
        # nothing about the empire is stopping the player, a game option is. D-10 (spec/
        # decisions.md): this is that rule's first real application, not a hypothetical case.
        category = categorize_leaf(result.leaf) if result.leaf is not None else None
        if category == ReasonCategory.MOD_CONFIGURATION:
            return AvailabilityResult(CONFIG_GATED, reason, description, category)
        return AvailabilityResult(LOCKED, reason, description)

    category = categorize_leaf(result.leaf) if result.leaf is not None else ReasonCategory.UNCLASSIFIED
    return AvailabilityResult(UNCERTAIN, reason, description, category)


_WEIGHT_GATE_UNKNOWN_ROUTE = "Not offered through the normal research draw currently."
_WEIGHT_GATE_ALWAYS_ROUTE = "This technology is obtained outside the normal research draw, not through it."


def _weight_gated_description(leaf: Assignment | None) -> str:
    """Per-instance condition text for a WEIGHT_GATED result (the "CONDITION TEXT" naming
    decision): the two real `always = yes` cases get dedicated phrasing ("obtained outside the
    normal draw"), since static analysis can positively confirm the draw itself is permanently
    excluded even though it can't confirm the REAL route (event/give_technology/special project/
    archaeology/relic -- see `_apply_weight_gate`'s own docstring). Everything else routes through
    `describe_condition` (raw-text fallback included), and a condition with no single named leaf
    (EXCLUDED-dominated, or an AND/OR combining more than one relevant branch) gets the neutral
    "not offered" phrasing -- never a guess at which unmodelled mechanism actually grants it."""
    if leaf is not None and leaf.key_name == "always" and _yesno(leaf.value) is True:
        return _WEIGHT_GATE_ALWAYS_ROUTE
    if leaf is not None:
        return describe_condition(leaf)
    return _WEIGHT_GATE_UNKNOWN_ROUTE


def _apply_weight_gate(
    result: AvailabilityResult, weight_gate_blocks: list[Block], profile: dict,
    gate_expressible: list[bool] | None = None,
) -> AvailabilityResult:
    """A later session's Item 2b: a `weight_modifier` entry with a literal `factor = 0` is
    Stellaris's own idiom for "this technology cannot currently be drawn as a research option at
    all" -- not a mere weight reduction, functionally a gate (the motivating case: Cosmogenesis-
    locked technologies, whose `weight_modifier` zeroes them out entirely until a late-game crisis
    level is reached). `weight_gate_blocks` are the zero-factor modifiers' own condition blocks
    (already scripted-trigger-expanded, `factor` itself stripped) -- each evaluated through the
    SAME unchanged Kleene evaluator `evaluate_trigger_block`/`evaluate_trigger_block` uses
    (`_evaluate_node`/`_combine_and`), never a second mechanism, but consulted here at the
    INTERNAL `_Eval` level rather than through `evaluate_trigger_block`'s public wrapper -- see
    "the EXCLUDED defect" below for why that distinction matters.

    Only ever applied when the technology's `potential`-based `result` is already AVAILABLE -- a
    technology LOCKED/UNCERTAIN/CONFIG_GATED for a real `potential`-block reason keeps that reason
    unchanged; this project's `reason` field is a single string, not a combined list, so the more
    specific existing reason wins over a weight-based one.

    A `weight_modifier` describes eligibility in the weighted research draw ONLY -- it says
    nothing about `give_technology`, `add_research_option`, event grants, special projects,
    archaeology rewards or relic activations, none of which this static evaluator can see.
    Reporting a technology LOCKED purely because its weight is zero would therefore claim
    something the pipeline cannot actually know: a real corpus case (`tech_akx_worm_1`, `always =
    yes`) is confirmed granted through an exclusive event chain despite permanent zero weight.
    Decision 4 (CLAUDE.md's "Research weight -> Extension"): a definite LOCKED verdict from a
    weight gate is therefore permitted ONLY when the condition's TRUE resolution is grounded
    SOLELY in AXIS_FACTS leaves (or an axis-restricted ascension perk) -- `_Eval.axis_pure`, which
    genuinely distinguishes empire TYPES, never merely a ground fact (DLC, `always`, mod-config
    toggle, story-progression flag) that reads the same for every profile. Every other zero-weight
    firing -- circumstantial state (bucket B), opaque leaves (bucket C), or a non-axis-pure
    bucket-A leaf (`always`, an unrestricted perk, an unresolved wrapper) -- downgrades to
    WEIGHT_GATED instead: the tool CAN tell the player this isn't offered in the draw, it just
    can't attribute that to their empire's TYPE. WEIGHT_GATED does not fold into D-10 uncertainty
    accounting (parallel to CONFIG_GATED, not a data gap) and is treated as VIABLE by the research-
    path builder (P-12.9), unlike LOCKED/CONFIG_GATED.

    **The EXCLUDED defect (fixed here, see docs/DEFECTS.md's "EXCLUDED-as-vacuously-satisfied"
    write-up):** `evaluate_trigger_block`'s public wrapper maps BOTH internal `_State.TRUE` and
    `_State.EXCLUDED` to `AVAILABLE` -- correct for `potential` evaluation (EXCLUDED there means
    "a player CHOICE, presume open", the right default for "can this empire type ever have this").
    That default has no meaning here: an EXCLUDED-dominated weight-gate condition (e.g. `NOT =
    { has_ascension_perk = <a perk with no axis restriction> }`, or a bare `has_galactic_wonders`
    leaf -- both real corpus cases) means the pipeline genuinely cannot evaluate whether the zero-
    weight condition holds, not that it's "presumed not to." Using the public wrapper here would
    silently launder that EXCLUDED into the OLD code's real-LOCKED branch (this defect's actual
    prior behaviour: 4 technologies reported permanently LOCKED for all 12 profiles on a condition
    this evaluator cannot interpret at all). Fixed by working from the internal `_Eval` directly
    and giving `_State.EXCLUDED` its own branch below, which can only ever route to WEIGHT_GATED,
    never LOCKED -- asserted, not an emergent property of the axis_pure check (an EXCLUDED result
    has no leaf to be axis_pure about; `axis_pure` defaults False and is never consulted for a
    state other than TRUE, so this is enforced structurally, not merely by convention).

    **Weight-condition gate extraction (a later session):** `gate_expressible`, when given, is a
    `weight_gate_blocks`-index-aligned list of booleans (`pipeline.dataset_emit.BuildContext.
    weight_gate_expressible_mask`) -- `True` at position `i` iff block `i` classifies to at least
    one registered gate pattern (`pipeline.gate_patterns.classify_weight_gate_condition`). A
    gate-expressible block's non-axis-pure TRUE/EXCLUDED/UNKNOWN branches are suppressed (skipped
    exactly like a FALSE block: contributes nothing) rather than becoming `weight_gated_pick` --
    the technology's own `gates` list badges the card instead
    (`pipeline.dataset_emit._build_gates`), so the same condition must not ALSO read WEIGHT_GATED.
    The axis-pure TRUE branch is deliberately UNCHANGED by this mask: whether a gate's own target
    (e.g. an ascension perk) is obtainable at all for an empire type is a genuine fact this
    evaluator must keep surfacing as a real LOCKED, per CLAUDE.md's "Ascension perks are gates,
    not profile facts -- with a correction" -- a gate badge is display metadata layered on top of
    that fact, never a replacement for it."""
    if result.state != AVAILABLE or not weight_gate_blocks:
        return result
    if gate_expressible is None:
        gate_expressible = [False] * len(weight_gate_blocks)

    weight_gated_pick: AvailabilityResult | None = None
    for cond_block, is_gate in zip(weight_gate_blocks, gate_expressible):
        children = [_evaluate_node(item, profile) for item in cond_block.items if isinstance(item, Assignment)]
        ev = _combine_and(children)
        reason = " ".join(_leaf_text(item) for item in cond_block.items if isinstance(item, Assignment)) or None

        if ev.state == _State.TRUE:
            if ev.axis_pure:
                # `ev.leaf` is None whenever more than one relevant child contributed to the TRUE
                # combination (or a NOT-wrapper's own inner had no single leaf, e.g. `has_galactic_
                # wonders = no` after scripted-trigger expansion, a real corpus case: the axis-
                # locked-perk-chain OR has no single named leaf once negated) -- raw block text
                # (`reason`, always non-None whenever a TRUE result was reachable at all, since
                # that requires >=1 relevant child) is the honest fallback, never the WEIGHT_GATED
                # "not offered" phrasing, which would misdescribe a real, definite LOCKED verdict.
                description = describe_condition(ev.leaf) if ev.leaf is not None else reason
                return AvailabilityResult(LOCKED, reason, description)
            if is_gate:
                continue
            if weight_gated_pick is None:
                weight_gated_pick = AvailabilityResult(WEIGHT_GATED, reason, _weight_gated_description(ev.leaf))
            continue

        if ev.state in (_State.EXCLUDED, _State.UNKNOWN):
            if is_gate:
                continue
            if weight_gated_pick is None:
                weight_gated_pick = AvailabilityResult(WEIGHT_GATED, reason, _weight_gated_description(ev.leaf))
            continue

        # ev.state == _State.FALSE: the zero-weight condition does not currently hold for this
        # profile -- this block contributes nothing, matching decision 3's "an A-type leaf that
        # independently decides the outcome" case (Kleene AND already gives FALSE priority over an
        # UNKNOWN/EXCLUDED sibling, so a definite non-firing axis fact correctly leaves the
        # technology untouched by this block even when another leaf in it is unresolved).

    return weight_gated_pick if weight_gated_pick is not None else result


def evaluate_technology_for_profiles(
    block: Block | None, profiles: list[dict], weight_gate_blocks: list[Block] | None = None,
    weight_gate_expressible: list[bool] | None = None,
) -> dict[int, AvailabilityResult]:
    """Convenience: evaluate one technology's `potential` block against every profile in
    `profiles` (expected to be `pipeline.dataset_schema.empire_profile.all_profiles_in_canonical_order()`),
    keyed by list index (== EmpireProfileIndex when that's the list passed). `weight_gate_blocks`,
    when non-empty, additionally folds in `_apply_weight_gate`'s zero-weight-unless-condition
    check (Item 2b) -- omitted or empty is a no-op, matching every technology with no zero-factor
    `weight_modifier` entry.

    `weight_gate_expressible` (weight-condition gate extraction, a later session) is passed
    straight through to `_apply_weight_gate` -- see that function's own docstring.

    Decision 5's tripwire (a later session): when `profiles` is the FULL canonical 12-profile set,
    it must be impossible for a weight gate to turn every one of them LOCKED -- a condition that
    locks all 12 draws no empire-type distinction at all and belongs in WEIGHT_GATED, not LOCKED
    (see `_apply_weight_gate`'s `axis_pure` gate, which this asserts actually holds). Guarded to
    the full 12-profile call only: a caller evaluating a single profile (e.g.
    `pipeline.dataset_emit._compute_profile_facts`, one profile at a time) legitimately sees a
    real axis-locked LOCKED with nothing else to compare it against, and must not trip this."""
    results = {i: evaluate_trigger_block(block, profile) for i, profile in enumerate(profiles)}
    if weight_gate_blocks:
        gated = {
            i: _apply_weight_gate(results[i], weight_gate_blocks, profile, weight_gate_expressible)
            for i, profile in enumerate(profiles)
        }
        if len(profiles) == 12:
            weight_gate_caused_locked = [
                i for i in gated
                if gated[i].state == LOCKED and results[i].state == AVAILABLE
            ]
            assert len(weight_gate_caused_locked) < 12, (
                "Decision 5 tripwire: a weight-gate condition produced LOCKED for all 12 profiles "
                "-- it draws no empire-type distinction and must route to WEIGHT_GATED instead "
                "(see _apply_weight_gate's axis_pure gate)."
            )
        results = gated
    return results


@dataclass(frozen=True)
class UncertaintySurvey:
    """D-10 metric split (CLAUDE.md's "Availability evaluator" section):

    - `unconditional_uncertain`: technology keys UNCERTAIN under every one of the 12 profiles
      identically -- a data-completeness figure, NOT subject to D-10's 10% ceiling.
    - `profile_dependent_uncertain_by_profile_index`: per profile, technology keys UNCERTAIN for
      THAT profile but not unconditional (i.e. at least one other profile resolves definitely) --
      this is what D-10's 3%/10%/ratchet actually govern, per profile, worst-case.
    """

    total_technologies: int
    unconditional_uncertain: list[str]
    profile_dependent_uncertain_by_profile_index: dict[int, list[str]]
    unconditional_uncertain_categories: dict[str, ReasonCategory]

    def category_distribution(self) -> dict[ReasonCategory, int]:
        """Task 3's deliverable: how the unconditional-uncertain nodes split across
        `pipeline.trigger_text.ReasonCategory`. A distribution dominated by explainable
        categories (crisis/story, origin, ethics/civic, mod content) means Stage 3 can render
        honest, specific reason text; a distribution dominated by OPAQUE_COUNTRY_STATE/
        UNCLASSIFIED means the uncertainty is a real data gap, not a presentation problem."""
        counts: dict[ReasonCategory, int] = {}
        for category in self.unconditional_uncertain_categories.values():
            counts[category] = counts.get(category, 0) + 1
        return counts

    def unconditional_rate(self) -> float:
        return len(self.unconditional_uncertain) / self.total_technologies

    def profile_dependent_rate(self, profile_index: int) -> float:
        return len(self.profile_dependent_uncertain_by_profile_index.get(profile_index, [])) / self.total_technologies

    def worst_profile_dependent_rate(self) -> float:
        if not self.profile_dependent_uncertain_by_profile_index:
            return 0.0
        return max(self.profile_dependent_rate(i) for i in self.profile_dependent_uncertain_by_profile_index)


def survey_uncertainty(
    technologies: dict[str, Block | None],
    profiles: list[dict],
    weight_gate_conditions: dict[str, list[Block]] | None = None,
) -> UncertaintySurvey:
    """Run the evaluator over every `(technology, profile)` pair in `technologies` (key ->
    `potential` block, or None) and split the result per the metric definitions above.
    `weight_gate_conditions` (Item 2b, a later session), when given, folds each technology's own
    zero-factor `weight_modifier` conditions into the same evaluation -- omitted or a missing key
    is a no-op, matching every technology with no such modifier."""
    unconditional: list[str] = []
    unconditional_categories: dict[str, ReasonCategory] = {}
    profile_dependent: dict[int, list[str]] = {i: [] for i in range(len(profiles))}

    for key, block in technologies.items():
        results = evaluate_technology_for_profiles(
            block, profiles, (weight_gate_conditions or {}).get(key)
        )
        uncertain_indices = [i for i, r in results.items() if r.state == UNCERTAIN]
        if not uncertain_indices:
            continue
        if len(uncertain_indices) == len(profiles):
            unconditional.append(key)
            # Every profile is UNCERTAIN with the same trigger structure (no axis check
            # anywhere), so every profile's category agrees -- take the first.
            unconditional_categories[key] = results[uncertain_indices[0]].category or ReasonCategory.UNCLASSIFIED
        else:
            for i in uncertain_indices:
                profile_dependent[i].append(key)

    return UncertaintySurvey(
        total_technologies=len(technologies),
        unconditional_uncertain=sorted(unconditional),
        profile_dependent_uncertain_by_profile_index={i: sorted(v) for i, v in profile_dependent.items()},
        unconditional_uncertain_categories=unconditional_categories,
    )


# ---------------------------------------------------------------------------
# D-10 thresholds / S-2 diagnostics (spec/decisions.md's D-10, spec/S-02-diagnostics.md)
# ---------------------------------------------------------------------------

D10_WARN_THRESHOLD = 0.03
D10_HARD_CEILING = 0.10


def classify_d10_status(rate: float) -> str:
    """"ok" / "warn" / "fail" against D-10's profile-dependent thresholds. Strict `>`: a rate
    exactly at 3% or 10% does not itself cross the line, only a rate genuinely above it does."""
    if rate > D10_HARD_CEILING:
        return "fail"
    if rate > D10_WARN_THRESHOLD:
        return "warn"
    return "ok"


@dataclass(frozen=True)
class ProfileDependentDiagnostic:
    profile_index: int
    rate: float
    previous_rate: float | None
    status: str  # "ok" | "warn" | "fail"
    regressed: bool  # True iff previous_rate is known and rate rose against it (the D-10 ratchet)


@dataclass(frozen=True)
class UnconditionalDiagnostic:
    count: int
    previous_count: int | None
    rate: float
    previous_rate: float | None
    regressed: bool
    category_distribution: dict[ReasonCategory, int]


def build_profile_dependent_diagnostics(
    survey: UncertaintySurvey, previous_rates: dict[int, float] | None = None
) -> list[ProfileDependentDiagnostic]:
    """One entry per profile (schema's `diagnostics.profileDependentUncertainty`), in profile-
    index order. `previous_rates` (profile index -> rate from the previous build) is optional --
    omit it for a first build, where there is nothing to ratchet against yet."""
    previous_rates = previous_rates or {}
    results = []
    for i in range(len(survey.profile_dependent_uncertain_by_profile_index)):
        rate = survey.profile_dependent_rate(i)
        previous_rate = previous_rates.get(i)
        regressed = previous_rate is not None and rate > previous_rate
        results.append(
            ProfileDependentDiagnostic(
                profile_index=i,
                rate=rate,
                previous_rate=previous_rate,
                status=classify_d10_status(rate),
                regressed=regressed,
            )
        )
    return results


def build_unconditional_diagnostic(
    survey: UncertaintySurvey, previous_count: int | None = None
) -> UnconditionalDiagnostic:
    """schema's `diagnostics.unconditionalUncertainty` -- NOT subject to D-10_WARN_THRESHOLD /
    D10_HARD_CEILING (see spec/decisions.md's D-10: a different quality signal, no ceiling), but
    still carries its own regression ratchet."""
    count = len(survey.unconditional_uncertain)
    previous_rate = (previous_count / survey.total_technologies) if previous_count is not None else None
    regressed = previous_count is not None and count > previous_count
    return UnconditionalDiagnostic(
        count=count,
        previous_count=previous_count,
        rate=survey.unconditional_rate(),
        previous_rate=previous_rate,
        regressed=regressed,
        category_distribution=survey.category_distribution(),
    )


def needs_lock_reason_override(result: AvailabilityResult) -> bool:
    """P-13: True when a LOCKED result's `description` is nothing more than the raw trigger text
    -- i.e. `pipeline.trigger_text` had no dedicated phrase for the leaf responsible, so
    `config/lock_reason_overrides.txt` is the fallback, and the build MUST warn if no entry names
    this technology. Always False for AVAILABLE/UNCERTAIN -- P-13's override table is specifically
    for the LOCKED-reason case."""
    return result.state == LOCKED and result.description == result.reason


def resolve_lock_reason(technology_key: str, result: AvailabilityResult, overrides: dict) -> tuple[str, bool]:
    """Returns `(display reason text, needs_warning)`. `overrides` is
    `pipeline.lock_reason_overrides.load_overrides()`'s output. A missing override never blocks
    the build (P-13 requires a warning, not a hard failure) -- the raw/derived text is always
    still returned, `needs_warning` just flags that S-2 should surface the gap."""
    if not needs_lock_reason_override(result):
        return result.description, False
    override = overrides.get(technology_key)
    if override is not None:
        return override.reason_text, False
    return result.description, True


def build_missing_lock_reason_overrides(
    locked_results: dict[str, AvailabilityResult], overrides: dict
) -> list[str]:
    """schema's `diagnostics.missingLockReasonOverrides`: every technology key whose LOCKED
    reason needed an override (per `needs_lock_reason_override`) but doesn't have one in
    `overrides`. `locked_results` is technology key -> its `AvailabilityResult` for whichever
    profile produced the LOCKED state under consideration."""
    return sorted(
        key for key, result in locked_results.items()
        if needs_lock_reason_override(result) and key not in overrides
    )


def build_d10_diagnostics_section(
    survey: UncertaintySurvey,
    profiles: list[dict],
    previous_profile_rates: dict[int, float] | None = None,
    previous_unconditional_count: int | None = None,
) -> dict:
    """S-2 machine-readable diagnostics section, shaped exactly like
    `schema/diagnostics.schema.json`'s `profileDependentUncertainty` / `unconditionalUncertainty`
    -- see `pipeline.overwrites.build_overwrite_report` for the equivalent pattern on P-15."""
    profile_diagnostics = build_profile_dependent_diagnostics(survey, previous_profile_rates)
    unconditional = build_unconditional_diagnostic(survey, previous_unconditional_count)

    return {
        "profileDependentUncertainty": [
            {
                "profile": profiles[d.profile_index],
                "rate": d.rate,
                "previousRate": d.previous_rate if d.previous_rate is not None else d.rate,
                "status": d.status,
            }
            for d in profile_diagnostics
        ],
        "unconditionalUncertainty": {
            "count": unconditional.count,
            "previousCount": unconditional.previous_count if unconditional.previous_count is not None else unconditional.count,
            "rate": unconditional.rate,
            "previousRate": unconditional.previous_rate if unconditional.previous_rate is not None else unconditional.rate,
            "categoryDistribution": [
                {"category": category.value, "count": count}
                for category, count in sorted(unconditional.category_distribution.items(), key=lambda kv: kv[0].value)
            ],
        },
    }
