"""D-10/P-13: partial trigger evaluator.

Produces `(technology, empire profile) -> {state, reason}`, state always one of
`available` / `locked` / `uncertain` / `config-gated` (schema's `AvailabilityState`, renamed from
`ThreeState` when the fourth value was added — see `spec/decisions.md`'s D-10) — **never**
a boolean. `unknown` (here: `uncertain`) propagates through boolean structure exactly like it
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
a trigger truth value. `has_ascension_perk` leaves are also excluded, for a parallel reason:
D-6/P-1 settle that ascension perks are gates, not profile facts — a perk-gated technology
always displays its gate rather than the tool silently assuming the perk is or isn't taken, so a
perk check is not this evaluator's to resolve either way. Folding either into this evaluator's
`uncertain` output would be a category error (they are never actually undecidable, they are
un-*checked-here*), so both are excluded from boolean combination entirely rather than resolved
either way — see `EXCLUDED_KEYS` and `_State.EXCLUDED`.

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
from .trigger_text import MOD_CONFIG_TOGGLE_SUFFIXES, ReasonCategory, categorize_leaf, describe_condition

AVAILABLE = "available"
LOCKED = "locked"
UNCERTAIN = "uncertain"
# D-10 (spec/decisions.md): a technology whose `potential` resolves definitively to FALSE because
# of a mod-configuration toggle (MOD_CONFIG_TOGGLE_SUFFIXES), not anything about the empire being
# played. Distinct from LOCKED, which elsewhere always means "your empire cannot obtain this" --
# rendering both the same way would tell a player content is off-limits when it's one options-
# menu toggle away. See schema/common.schema.json's AvailabilityState (renamed from ThreeState).
CONFIG_GATED = "config-gated"

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
    "has_ascension_perk",
    "has_gigastructural_constructs",
    "has_galactic_wonders",
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
    "is_fallen_empire": False,
    "merg_is_fallen_empire": False,
}

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


@dataclass(frozen=True)
class AvailabilityResult:
    """One `(technology, empire profile)` result. `state` is always one of AVAILABLE / LOCKED /
    UNCERTAIN / CONFIG_GATED (schema.AvailabilityState, renamed from ThreeState when this fourth
    value was added) -- never a boolean, per D-10/P-13.

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


def _flag_value_name(value) -> str | None:
    if isinstance(value, Identifier):
        return value.name
    if isinstance(value, StringLiteral):
        return value.value
    return None


def _bool_eval(resolved: bool, negate: bool, leaf: Assignment) -> _Eval:
    result = resolved != negate
    return _Eval(_State.TRUE, None) if result else _Eval(_State.FALSE, leaf)


def _evaluate_leaf(assignment: Assignment, profile: dict) -> _Eval:
    key = assignment.key_name
    negate = assignment.operator == "!="

    if key in EXCLUDED_KEYS:
        return _Eval(_State.EXCLUDED, None)

    if key == "has_global_flag":
        flag_name = _flag_value_name(assignment.value)
        if flag_name is not None and _is_mod_config_toggle_flag(flag_name):
            return _bool_eval(False, negate, assignment)  # unset default: content not forbidden
        return _Eval(_State.UNKNOWN, assignment)

    if key in DLC_NAME_CHECK_KEYS:
        return _bool_eval(True, negate, assignment)

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
        return _bool_eval(actual == target, negate, assignment)

    return _Eval(_State.UNKNOWN, assignment)


def _combine_and(children: list[_Eval]) -> _Eval:
    relevant = [c for c in children if c.state != _State.EXCLUDED]
    if not relevant:
        return _Eval(_State.EXCLUDED, None)
    false_ones = [c for c in relevant if c.state == _State.FALSE]
    if false_ones:
        return _Eval(_State.FALSE, false_ones[0].leaf)
    unknown_ones = [c for c in relevant if c.state == _State.UNKNOWN]
    if unknown_ones:
        return _Eval(_State.UNKNOWN, unknown_ones[0].leaf)
    return _Eval(_State.TRUE, None)


def _combine_or(children: list[_Eval]) -> _Eval:
    relevant = [c for c in children if c.state != _State.EXCLUDED]
    if not relevant:
        return _Eval(_State.EXCLUDED, None)
    if any(c.state == _State.TRUE for c in relevant):
        return _Eval(_State.TRUE, None)
    unknown_ones = [c for c in relevant if c.state == _State.UNKNOWN]
    if unknown_ones:
        return _Eval(_State.UNKNOWN, unknown_ones[0].leaf)
    return _Eval(_State.FALSE, relevant[0].leaf)


def _negate(inner: _Eval, wrapper: Assignment) -> _Eval:
    if inner.state == _State.TRUE:
        return _Eval(_State.FALSE, wrapper)
    if inner.state == _State.FALSE:
        return _Eval(_State.TRUE, None)
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


def evaluate_technology_for_profiles(
    block: Block | None, profiles: list[dict]
) -> dict[int, AvailabilityResult]:
    """Convenience: evaluate one technology's `potential` block against every profile in
    `profiles` (expected to be `pipeline.dataset_schema.empire_profile.all_profiles_in_canonical_order()`),
    keyed by list index (== EmpireProfileIndex when that's the list passed)."""
    return {i: evaluate_trigger_block(block, profile) for i, profile in enumerate(profiles)}


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


def survey_uncertainty(technologies: dict[str, Block | None], profiles: list[dict]) -> UncertaintySurvey:
    """Run the evaluator over every `(technology, profile)` pair in `technologies` (key ->
    `potential` block, or None) and split the result per the metric definitions above."""
    unconditional: list[str] = []
    unconditional_categories: dict[str, ReasonCategory] = {}
    profile_dependent: dict[int, list[str]] = {i: [] for i in range(len(profiles))}

    for key, block in technologies.items():
        results = evaluate_technology_for_profiles(block, profiles)
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
