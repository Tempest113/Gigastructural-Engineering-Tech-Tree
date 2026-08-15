"""Shared trigger-condition -> text/category component.

HANDOFF.md flagged this as a genuine gap: "No trigger-condition -> human-readable-text renderer
exists yet. Needed for two schema fields that already exist
(`detail-payload.schema.json`'s `weight.modifiers[].conditionText`, and the empire-overlay's
trigger-derived lock `reason` string)... this is a missing *component*, not missing data."

Two independent things live here, both operating on a raw Clausewitz trigger node so neither is
private to `pipeline.availability`:

- `describe_condition(node)` -- best-effort human-readable text for ANY condition node (a leaf
  assignment, or a boolean-wrapper block), for P-13's lock-reason badge AND P-12.8's weight-
  modifier condition text. Falls back to the raw trigger source text when no phrasing is known
  for a given leaf key -- an honest "I don't have prose for this" rather than a guess.
- `categorize_leaf(assignment)` -- classifies an UNDECIDABLE leaf (one `pipeline.availability`
  could not resolve) into a `ReasonCategory`, so Stage 3 can render "requires the Blokkat crisis
  chain to have begun" differently from "unavailable for unknown reasons". Categories were
  derived from the real corpus's 224 unconditionally-uncertain rendered nodes (Task 3's category-
  distribution survey), not designed up front -- see each category's own comment for the
  evidence behind it and `tests/test_availability_corpus.py` for the measured distribution.
"""

from __future__ import annotations

from enum import Enum

from .clausewitz.nodes import Assignment, Block, Identifier, NumberLiteral, StringLiteral, VariableReference

BOOLEAN_WRAPPERS = {"AND", "OR", "NOT", "NOR"}


class ReasonCategory(str, Enum):
    """Why a leaf's truth value could not be determined, OR (MOD_CONFIGURATION only) why a
    definitively-resolved leaf produced a locked-but-not-empire-related result. Not exhaustive by
    design -- `UNCLASSIFIED` is the honest fallback for a leaf key this survey never saw, not a
    bug."""

    CRISIS_OR_STORY_PROGRESS = "crisis_or_story_progress"
    ORIGIN_REQUIREMENT = "origin_requirement"
    ETHICS_OR_CIVIC_REQUIREMENT = "ethics_or_civic_requirement"
    MOD_CONTENT_REQUIREMENT = "mod_content_requirement"
    # A has_global_flag leaf resolved via MOD_CONFIG_TOGGLE_SUFFIXES below -- the leaf IS
    # definitively resolved (never UNCERTAIN), but when it's the leaf responsible for a FALSE
    # result, that result is gated by a MOD SETTING, not by anything about the empire being
    # played (spec/decisions.md's D-10, "first real application" note). Distinct from
    # MOD_CONTENT_REQUIREMENT, which is about a technology needing ACOT/AoT content present, not
    # about a Gigastructures options-menu toggle.
    MOD_CONFIGURATION = "mod_configuration"
    OPAQUE_COUNTRY_STATE = "opaque_country_state"
    UNCLASSIFIED = "unclassified"


# Suffixes marking a has_global_flag as a MOD-CONFIGURATION toggle -- resolved to its unset/
# default state by pipeline.availability's `_evaluate_leaf` (the single source of truth for this
# list; trigger_text.categorize_leaf imports it rather than keeping its own copy, so the
# evaluator's resolution logic and the categoriser's classification can't drift apart). Two
# evidentially distinct sub-groups, in one tuple because both share the same resolution
# mechanism (assume unset/default) even though the evidence behind each differs:
# - `_forbidden`/`_disabled`/`_OFF`: general Paradox/Gigastructures modding convention, confirmed
#   by corpus survey (CLAUDE.md's "Documented evaluator assumptions").
# - `_capped_r`: giga_mega_repeatable.txt's inline_script template's per-megastructure cap-mode
#   selector (the giga_tech_repeatable_*_cap family, 50 rendered technologies -- confirmed by
#   corpus survey to be the ONLY rendered technologies using a `_capped_*`-shaped flag in their
#   `potential` block; no other suffix in that family, `_capped_1`/`_capped_2`/`_capped_3`/
#   `_capped_u`/`_capped_s`, appears there). This one is confirmed by the USER, not inferred from
#   a general convention: no core Gigastructures preset sets a cap to the "1+r" mode this flag
#   names, so it is unset in a default game. See spec/decisions.md's D-10 for the full evidence
#   and caveat (a non-core/custom preset may set it differently -- a Stage 3 presentation
#   concern, this evaluator still reports the default-preset answer).
MOD_CONFIG_TOGGLE_SUFFIXES = ("_forbidden", "_disabled", "_OFF", "_capped_r")


# Corpus-confirmed crisis-faction name fragments (CLAUDE.md's D-7 crisis factions, plus
# Gigastructures' own EHOF/EAWAF endgame-chain naming) and generic story/quest-progression
# suffixes/prefixes -- both confirmed by direct inspection of every has_country_flag /
# has_global_flag value in the 224-node unconditional-uncertain survey (see
# tests/test_availability_corpus.py). Deliberately NOT a blanket "any has_country_flag is
# crisis" rule -- flags outside this pattern (has_arcane_generator, advanced_identity_creation,
# acot_databank_sophia_agreed, colossus_project) fall through to OPAQUE_COUNTRY_STATE instead,
# because their names don't self-describe a story beat the way `blokkat_laser_possible` or
# `encountered_first_lgate` do.
_CRISIS_FACTION_FRAGMENTS = (
    "blokkat", "aeternum", "aeternite", "compound", "sirenalia", "siren", "katzenartig", "katzen",
    "ehof", "eawaf",
)
_STORY_PROGRESS_SUFFIXES = (
    "_possible", "_happened", "_solved", "_complete", "_completed", "_unlocked", "_aborted",
    "_knowledge", "_defeated", "_opened",
)
_STORY_PROGRESS_PREFIXES = ("encountered_", "completed_")


def _looks_like_story_progress(flag_name: str) -> bool:
    lowered = flag_name.lower()
    if any(fragment in lowered for fragment in _CRISIS_FACTION_FRAGMENTS):
        return True
    if lowered.endswith(_STORY_PROGRESS_SUFFIXES):
        return True
    if lowered.startswith(_STORY_PROGRESS_PREFIXES):
        return True
    return False


# Leaf keys resolved directly to a category regardless of value -- each confirmed by inspecting
# its scripted_trigger definition (not guessed from the name):
# - ETHICS_OR_CIVIC_REQUIREMENT: has_ethic/is_spiritualist are direct ethic checks;
#   is_natural_design_empire resolves to `has_valid_civic = civic_natural_design` (OR its hive
#   variant); has_valid_civic is the same mechanism directly; is_beastmasters_empire and
#   is_individual_machine are civic-shaped machine/hive subtype checks; is_megacorp checks for
#   the Megacorporation authority, a 4th authority value this tool's 3-value axis (D-6) doesn't
#   model -- closest real category is still "which government/civic choice", not opaque state.
# - ORIGIN_REQUIREMENT: has_origin directly; giga_has_frameworld_origin by name;
#   is_wilderness_empire resolves to `has_origin = origin_wilderness` (confirmed, not guessed --
#   00_scripted_triggers.txt:1723); is_void_dweller_empire is the Void Dwellers origin.
# - MOD_CONTENT_REQUIREMENT: has_acot literally checks "is ACOT-sourced content present" --
#   distinct from a DLC check, and from a mod-config toggle (which resolves, not undecidable).
_LEAF_KEY_CATEGORY: dict[str, ReasonCategory] = {
    "has_ethic": ReasonCategory.ETHICS_OR_CIVIC_REQUIREMENT,
    "is_spiritualist": ReasonCategory.ETHICS_OR_CIVIC_REQUIREMENT,
    "is_natural_design_empire": ReasonCategory.ETHICS_OR_CIVIC_REQUIREMENT,
    "has_valid_civic": ReasonCategory.ETHICS_OR_CIVIC_REQUIREMENT,
    "is_beastmasters_empire": ReasonCategory.ETHICS_OR_CIVIC_REQUIREMENT,
    "is_individual_machine": ReasonCategory.ETHICS_OR_CIVIC_REQUIREMENT,
    "is_megacorp": ReasonCategory.ETHICS_OR_CIVIC_REQUIREMENT,
    # is_world_forger_empire resolves to `OR(has_valid_civic = civic_world_forgers, ...)` (4
    # civic variants, 08_scripted_triggers_infernals.txt:8-13) -- a civic check, not an origin,
    # despite naming that could suggest either.
    "is_world_forger_empire": ReasonCategory.ETHICS_OR_CIVIC_REQUIREMENT,
    # has_genetically_ascended resolves to `OR(has_tradition = tr_genetics_finish, ...)` (4
    # tradition-tree-completion variants, 05_scripted_triggers_biogenesis.txt:424-429) -- a
    # tradition-path completion check, grouped with ethics/civic as the closest existing bucket
    # (a build-path choice, not crisis/story or origin).
    "has_genetically_ascended": ReasonCategory.ETHICS_OR_CIVIC_REQUIREMENT,
    "has_origin": ReasonCategory.ORIGIN_REQUIREMENT,
    "giga_has_frameworld_origin": ReasonCategory.ORIGIN_REQUIREMENT,
    "is_wilderness_empire": ReasonCategory.ORIGIN_REQUIREMENT,
    "is_void_dweller_empire": ReasonCategory.ORIGIN_REQUIREMENT,
    # giga_can_use_habitables resolves to `NOR(is_wilderness_empire, is_giga_one_planet_origin,
    # is_nomadic)` (ehof_triggers.txt:17-22) -- 2 of 3 branches are origin checks, the third is
    # the nomadic axis; grouped under origin as the closest single bucket for a "planet-based
    # content compatibility" check, not a clean fit anywhere else.
    "giga_can_use_habitables": ReasonCategory.ORIGIN_REQUIREMENT,
    "has_acot": ReasonCategory.MOD_CONTENT_REQUIREMENT,
    # has_ancrel: not a scripted_trigger definition anywhere in the vendored corpus (checked,
    # not assumed -- unlike every other leaf key in this table, its definition can't be shown
    # directly). Confirmed instead via giga_relics.txt's `country_event = { id = ancrel.NNNN }`
    # entries (a relic's dedicated event-id namespace) -- "Ancrel" is a Gigastructures relic/
    # precursor questline, so a technology gated on it is gated on relic-questline progress, the
    # same kind of "you achieved something through play" fact as the crisis/story-progress
    # bucket. 23 of 209 unconditional-uncertain rendered nodes (Task 3's residue audit) turned on
    # this single reclassification -- 209 was that audit's own denominator at the time, since
    # corrected to 259 (CLAUDE.md's "Availability evaluator" section: the 50-node difference is
    # the giga_tech_repeatable_*_cap group, unrelated to this has_ancrel finding, which stands as
    # originally audited).
    "has_ancrel": ReasonCategory.CRISIS_OR_STORY_PROGRESS,
    # Dynamic galaxy/country state that isn't a story beat, an origin, or a civic -- confirmed by
    # inspection (country_uses_consumer_goods resolves through a live resource-expense check;
    # the rest are structural/scope triggers or genuinely one-off runtime facts, not name-guessed):
    "country_uses_consumer_goods": ReasonCategory.OPAQUE_COUNTRY_STATE,
    "always": ReasonCategory.OPAQUE_COUNTRY_STATE,
    "any_country": ReasonCategory.OPAQUE_COUNTRY_STATE,
    "count_country": ReasonCategory.OPAQUE_COUNTRY_STATE,
    "check_variable": ReasonCategory.OPAQUE_COUNTRY_STATE,
    "days_passed": ReasonCategory.OPAQUE_COUNTRY_STATE,
    "has_encountered_psionic_auras": ReasonCategory.OPAQUE_COUNTRY_STATE,
    "has_encountered_any_fauna": ReasonCategory.OPAQUE_COUNTRY_STATE,
    "has_finished_psionic_tradition": ReasonCategory.OPAQUE_COUNTRY_STATE,
    "is_country_type": ReasonCategory.OPAQUE_COUNTRY_STATE,
}


def _flag_value_name(value) -> str | None:
    if isinstance(value, Identifier):
        return value.name
    if isinstance(value, StringLiteral):
        return value.value
    return None


def categorize_leaf(assignment: Assignment) -> ReasonCategory:
    """Classify one undecidable leaf. `assignment` is the leaf (or boolean-wrapper) Assignment
    an evaluator identified as the reason a condition could not be resolved -- see
    `pipeline.availability`'s `AvailabilityResult.category`."""
    key = assignment.key_name

    if key in _LEAF_KEY_CATEGORY:
        return _LEAF_KEY_CATEGORY[key]

    if key in ("has_country_flag", "has_global_flag"):
        flag_name = _flag_value_name(assignment.value) or ""
        if key == "has_global_flag" and flag_name.endswith(MOD_CONFIG_TOGGLE_SUFFIXES):
            return ReasonCategory.MOD_CONFIGURATION
        if _looks_like_story_progress(flag_name):
            return ReasonCategory.CRISIS_OR_STORY_PROGRESS
        return ReasonCategory.OPAQUE_COUNTRY_STATE if key == "has_country_flag" else ReasonCategory.UNCLASSIFIED

    return ReasonCategory.UNCLASSIFIED


# Human-readable phrasing for a leaf's `= yes` (or ground-fact-true) sense. Deliberately small --
# only leaves this module can say something confident about; anything else falls back to raw
# trigger text in `describe_condition` rather than a fabricated sentence.
_LEAF_PHRASES_TRUE: dict[str, str] = {
    "is_nomadic": "Nomadic empires",
    "is_machine_empire": "Machine intelligence empires",
    "is_mechanical_empire": "Machine intelligence empires",
    "is_robot_empire": "Machine intelligence empires",
    "is_hive_empire": "Hive mind empires",
    "is_regular_empire": "Regular-authority empires",
    "is_gestalt": "Gestalt-consciousness empires (hive mind or machine intelligence)",
    "country_uses_bio_ships": "Empires with a biological shipset",
    "is_fallen_empire": "Fallen empires",
    "merg_is_fallen_empire": "Fallen empires",
}


def _describe_leaf(assignment: Assignment) -> str:
    key = assignment.key_name
    value_name = _flag_value_name(assignment.value)

    if key in _LEAF_PHRASES_TRUE:
        phrase = _LEAF_PHRASES_TRUE[key]
        if value_name == "no":
            return f"Not: {phrase.lower()}"
        return phrase

    if key == "has_technology" and value_name is not None:
        return f"Requires researching {value_name}"
    if key == "has_ascension_perk" and value_name is not None:
        return f"Requires the {value_name} ascension perk"
    if key == "has_origin" and value_name is not None:
        return f"Requires the {value_name} origin"
    if key == "has_ethic" and value_name is not None:
        return f"Requires the {value_name} ethic"
    if key == "has_valid_civic" and value_name is not None:
        return f"Requires the {value_name} civic"
    if key in ("has_dlc", "host_has_dlc") and value_name is not None:
        return f'Requires the "{value_name}" DLC'
    if key == "has_country_flag" and value_name is not None:
        return f"Unresolved internal flag: {value_name}"
    if key == "has_global_flag" and value_name is not None:
        return f"Unresolved internal flag: {value_name}"

    return _raw_leaf_text(assignment)


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
        inner = " ".join(_raw_leaf_text(item) for item in value.items if isinstance(item, Assignment))
        return f"{{ {inner} }}" if inner else "{}"
    return "?"


def _raw_leaf_text(assignment: Assignment) -> str:
    return f"{assignment.key_name} {assignment.operator} {_value_text(assignment.value)}"


def describe_trigger_block(block: Block) -> str:
    """Best-effort human-readable text for a whole trigger BLOCK's top-level items, implicit-AND
    combined the same way `pipeline.availability.evaluate_trigger_block` treats a `potential`
    block's top level -- unlike `describe_condition` (a single leaf/wrapper Assignment), this
    takes the container Block itself, for callers (D-14's technology_swap variant descriptions)
    that need the FULL condition text, not just whichever leaf an evaluator happened to stop on.
    Falls back to describing nothing (empty string) only for a block with no Assignment items --
    not observed for any real trigger block in this project's corpus."""
    children = [describe_condition(item) for item in block.items if isinstance(item, Assignment)]
    return " and ".join(children)


def describe_condition(node) -> str:
    """Best-effort human-readable text for any condition node -- a leaf `Assignment`, or a
    boolean-wrapper `Assignment` (`AND`/`OR`/`NOT`/`NOR`, case-insensitive per
    `pipeline.availability`). Falls back to raw trigger source text wherever no phrasing is
    known, rather than fabricating prose."""
    if not isinstance(node, Assignment):
        return "?"

    key_upper = node.key_name.upper()
    if key_upper in BOOLEAN_WRAPPERS and isinstance(node.value, Block):
        children = [describe_condition(c) for c in node.value.items if isinstance(c, Assignment)]
        if not children:
            return _raw_leaf_text(node)
        if key_upper == "AND":
            return " and ".join(children)
        if key_upper == "OR":
            return " or ".join(children)
        if key_upper == "NOT":
            inner = " and ".join(children)
            return f"not ({inner})" if len(children) > 1 else f"not {inner}"
        if key_upper == "NOR":
            return "none of: " + "; ".join(children)

    return _describe_leaf(node)
