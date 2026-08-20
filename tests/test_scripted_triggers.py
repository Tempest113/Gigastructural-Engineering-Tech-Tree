"""Tests for pipeline.scripted_triggers -- general scripted-trigger leaf expansion.

Synthetic fixtures throughout, mirroring tests/test_availability.py's split: this file exercises
the expansion mechanism in isolation; tests/test_scripted_triggers_corpus.py runs it against the
real vendored corpus and reports the actual effect on D-10's uncertainty figures.
"""

from __future__ import annotations

import pytest

from pipeline.availability import AVAILABLE, LOCKED, UNCERTAIN, evaluate_trigger_block
from pipeline.clausewitz import parse_text
from pipeline.dataset_schema.empire_profile import all_profiles_in_canonical_order
from pipeline.scripted_triggers import (
    ExpansionDepthExceededError,
    MAX_EXPANSION_DEPTH,
    ScriptedTriggerCycleError,
    ScriptedTriggerDefinition,
    UnknownSourceError,
    collect_scripted_trigger_definitions,
    expand_scripted_triggers,
    resolve_scripted_triggers,
)

REGULAR_MECH_SEDENTARY = {"authority": "regular", "shipset": "mechanical", "nomadic": "no"}
HIVE_BIO_NOMADIC = {"authority": "hive_mind", "shipset": "biological", "nomadic": "yes"}


def _potential(text: str):
    doc = parse_text(f"tech_x = {{ potential = {text} }}\n", path="x.txt")
    assignment = doc.items[0]
    potential = next(item for item in assignment.value.items if item.key_name == "potential")
    return potential.value


def _trigger_body(text: str):
    doc = parse_text(f"name = {text}\n", path="triggers.txt")
    return doc.items[0].value


def _catalog(defs: dict[str, str], source: str = "Vanilla") -> dict[str, ScriptedTriggerDefinition]:
    return {
        name: ScriptedTriggerDefinition(name, source, "triggers.txt", 1, _trigger_body(body))
        for name, body in defs.items()
    }


# ---------------------------------------------------------------------------
# collect_scripted_trigger_definitions / resolve_scripted_triggers
# ---------------------------------------------------------------------------


def test_collect_and_resolve_last_source_wins():
    vanilla_doc = parse_text("some_trigger = { is_nomadic = yes }\n", path="v.txt")
    giga_doc = parse_text("some_trigger = { is_nomadic = no }\n", path="g.txt")
    history = collect_scripted_trigger_definitions(
        [("Vanilla", [vanilla_doc]), ("Gigastructural Engineering", [giga_doc])]
    )
    assert [d.source for d in history["some_trigger"]] == ["Vanilla", "Gigastructural Engineering"]

    resolved = resolve_scripted_triggers(history)
    assert resolved["some_trigger"].source == "Gigastructural Engineering"


def test_collect_rejects_unknown_source():
    doc = parse_text("some_trigger = { is_nomadic = yes }\n", path="v.txt")
    with pytest.raises(UnknownSourceError):
        collect_scripted_trigger_definitions([("Not A Real Source", [doc])])


# ---------------------------------------------------------------------------
# expand_scripted_triggers -- mechanism
# ---------------------------------------------------------------------------


def test_expand_substitutes_leaf_with_body_as_and():
    catalog = _catalog({"my_trigger": "{ is_hive_empire = yes }"})
    block = _potential("{ my_trigger = yes }")
    expanded = expand_scripted_triggers(block, catalog)
    result = evaluate_trigger_block(expanded, {"authority": "hive_mind", "shipset": "mechanical", "nomadic": "no"})
    assert result.state == AVAILABLE
    result2 = evaluate_trigger_block(expanded, REGULAR_MECH_SEDENTARY)
    assert result2.state == LOCKED


def test_expand_negated_invocation_wraps_in_not():
    catalog = _catalog({"my_trigger": "{ is_hive_empire = yes }"})
    block = _potential("{ my_trigger = no }")
    expanded = expand_scripted_triggers(block, catalog)
    # my_trigger = no --> NOT { is_hive_empire = yes } --> available for non-hive, locked for hive
    assert evaluate_trigger_block(expanded, REGULAR_MECH_SEDENTARY).state == AVAILABLE
    assert evaluate_trigger_block(expanded, {"authority": "hive_mind", "shipset": "mechanical", "nomadic": "no"}).state == LOCKED


def test_expand_recurses_through_nested_reference():
    catalog = _catalog({
        "trigger_a": "{ trigger_b = yes }",
        "trigger_b": "{ is_nomadic = yes }",
    })
    block = _potential("{ trigger_a = yes }")
    expanded = expand_scripted_triggers(block, catalog)
    assert evaluate_trigger_block(expanded, {"authority": "regular", "shipset": "mechanical", "nomadic": "yes"}).state == AVAILABLE
    assert evaluate_trigger_block(expanded, REGULAR_MECH_SEDENTARY).state == LOCKED


def test_expand_never_descends_into_an_opaque_block_valued_leaf():
    # Same scope discipline as pipeline.availability._evaluate_node / pipeline.edges'
    # _scoped_has_technology -- a trigger name inside count_country/weight_modifier/etc is never
    # substituted, matching the fact the evaluator never looks inside it either.
    catalog = _catalog({"my_trigger": "{ is_nomadic = yes }"})
    block = _potential("{ count_country = { limit = { my_trigger = yes } } }")
    expanded = expand_scripted_triggers(block, catalog)
    inner = expanded.items[0].value.items[0].value.items[0]
    assert inner.key_name == "my_trigger"  # untouched, not expanded


def test_expand_leaves_unrecognised_name_alone():
    block = _potential("{ some_unknown_leaf = yes }")
    expanded = expand_scripted_triggers(block, {})
    assert expanded.items[0].key_name == "some_unknown_leaf"


def test_expand_leaves_non_yesno_invocation_alone():
    catalog = _catalog({"my_trigger": "{ is_nomadic = yes }"})
    block = _potential("{ my_trigger = { scope = root } }")  # block-valued, not yes/no
    expanded = expand_scripted_triggers(block, catalog)
    assert expanded.items[0].key_name == "my_trigger"
    assert expanded.items[0].value.items[0].key_name == "scope"  # untouched


def test_expand_passes_none_through():
    assert expand_scripted_triggers(None, {}) is None


# ---------------------------------------------------------------------------
# is_ai stripping
# ---------------------------------------------------------------------------


def test_expand_strips_is_ai_branch_from_or():
    # Real corpus shape: OR = { AND = { is_ai = yes, has_country_flag = X } has_ascension_perk = Y }
    catalog = _catalog({
        "my_trigger": "{ OR = { AND = { is_ai = yes has_country_flag = some_flag } has_ascension_perk = some_perk } }"
    })
    block = _potential("{ my_trigger = yes }")
    expanded = expand_scripted_triggers(block, catalog)
    # my_trigger -> AND { OR { has_ascension_perk = some_perk } } -- the is_ai branch is gone entirely
    or_wrapper = expanded.items[0].value.items[0]
    assert or_wrapper.key_name.upper() == "OR"
    remaining_keys = [item.key_name for item in or_wrapper.value.items]
    assert remaining_keys == ["has_ascension_perk"]


def test_expand_strips_is_ai_leaf_directly_in_potential():
    block = _potential("{ OR = { is_ai = yes  is_nomadic = yes } }")
    expanded = expand_scripted_triggers(block, {})
    or_wrapper = expanded.items[0]
    remaining_keys = [item.key_name for item in or_wrapper.value.items]
    assert remaining_keys == ["is_nomadic"]


def test_expand_strips_hidden_trigger_wrapped_is_ai_branch():
    # Real corpus shape (zzz_overwrites.txt's has_galactic_wonders):
    # OR = { hidden_trigger = { and = { is_ai = yes has_country_flag = X } } has_ascension_perk = Y }
    # `hidden_trigger` isn't a boolean wrapper pipeline.availability recognises, so an unstripped
    # `hidden_trigger` node left behind would itself become a permanently-unresolvable leaf --
    # regression caught by this module's own corpus verification (11 real technologies).
    catalog = _catalog({
        "my_trigger": (
            "{ OR = { hidden_trigger = { and = { is_ai = yes has_country_flag = some_flag } } "
            "has_ascension_perk = some_perk } }"
        )
    })
    block = _potential("{ my_trigger = yes }")
    expanded = expand_scripted_triggers(block, catalog)
    or_wrapper = expanded.items[0].value.items[0]
    assert or_wrapper.key_name.upper() == "OR"
    remaining_keys = [item.key_name for item in or_wrapper.value.items]
    assert remaining_keys == ["has_ascension_perk"]  # hidden_trigger branch gone entirely


def test_expand_leaves_hidden_trigger_alone_when_not_entirely_is_ai_gated():
    # A hidden_trigger wrapping a REAL, non-AI condition must never be silently dropped or
    # unwrapped -- it stays as an ordinary, conservative unresolved leaf.
    catalog = _catalog({
        "my_trigger": "{ OR = { hidden_trigger = { is_nomadic = yes } has_ascension_perk = some_perk } }"
    })
    block = _potential("{ my_trigger = yes }")
    expanded = expand_scripted_triggers(block, catalog)
    or_wrapper = expanded.items[0].value.items[0]
    remaining_keys = [item.key_name for item in or_wrapper.value.items]
    assert remaining_keys == ["hidden_trigger", "has_ascension_perk"]


# ---------------------------------------------------------------------------
# already-resolved keys are never expanded (the country_uses_bio_ships regression)
# ---------------------------------------------------------------------------


def test_already_resolved_axis_fact_key_is_never_expanded_even_if_a_catalog_entry_exists():
    # A catalog entry for a name pipeline.availability.AXIS_FACTS already resolves directly must
    # never be substituted -- see module docstring's country_uses_bio_ships regression writeup.
    catalog = _catalog({"country_uses_bio_ships": "{ exists = this }"})
    block = _potential("{ country_uses_bio_ships = yes }")
    expanded = expand_scripted_triggers(block, catalog)
    assert expanded.items[0].key_name == "country_uses_bio_ships"  # untouched
    # And the axis fact still resolves correctly through the (untouched) leaf.
    bio_profile = {"authority": "regular", "shipset": "biological", "nomadic": "no"}
    assert evaluate_trigger_block(expanded, bio_profile).state == AVAILABLE
    assert evaluate_trigger_block(expanded, REGULAR_MECH_SEDENTARY).state == LOCKED


def test_already_resolved_ground_fact_key_is_never_expanded():
    catalog = _catalog({"has_ancrel": "{ always = no }"})  # a deliberately-wrong body if it WERE expanded
    block = _potential("{ has_ancrel = yes }")
    expanded = expand_scripted_triggers(block, catalog)
    assert expanded.items[0].key_name == "has_ancrel"
    assert evaluate_trigger_block(expanded, REGULAR_MECH_SEDENTARY).state == AVAILABLE  # GROUND_FACT_BOOL, not the fake body


def test_already_excluded_gate_key_is_never_expanded_even_if_a_catalog_entry_exists():
    # The is_megacorp regression, found the hard way (pipeline.scripted_triggers' own module
    # docstring): is_megacorp is a real scripted trigger (`{ has_authority = auth_corporate }`),
    # and has_authority is NOT itself excluded -- expanding is_megacorp blind to
    # pipeline.availability.EXCLUDED_KEYS would replace the excluded leaf with an unexcluded one,
    # turning a display gate back into a permanently-unresolvable leaf.
    catalog = _catalog({"is_megacorp": "{ has_authority = auth_corporate }"})
    block = _potential("{ is_megacorp = yes }")
    expanded = expand_scripted_triggers(block, catalog)
    assert expanded.items[0].key_name == "is_megacorp"  # untouched
    assert evaluate_trigger_block(expanded, REGULAR_MECH_SEDENTARY).state == AVAILABLE  # EXCLUDED_KEYS, not has_authority


def test_has_gigastructural_constructs_and_has_galactic_wonders_still_expand():
    # The two deliberate exceptions: these ARE excluded keys but their real bodies reduce to
    # has_ascension_perk leaves (themselves still excluded), so expansion is a confirmed no-op --
    # exercising it is what answers pipeline.gate_patterns.WRAPPER_TO_PERK's own redundancy
    # question, so these two must stay expandable.
    catalog = _catalog({"has_gigastructural_constructs": "{ has_ascension_perk = ap_gigastructural_constructs }"})
    block = _potential("{ has_gigastructural_constructs = yes }")
    expanded = expand_scripted_triggers(block, catalog)
    assert expanded.items[0].key_name.upper() == "AND"  # expanded, not left as the bare leaf
    assert evaluate_trigger_block(expanded, REGULAR_MECH_SEDENTARY).state == AVAILABLE  # has_ascension_perk, still excluded


# ---------------------------------------------------------------------------
# cycles and depth
# ---------------------------------------------------------------------------


def test_expand_raises_on_direct_cycle():
    catalog = _catalog({"trigger_a": "{ trigger_a = yes }"})
    block = _potential("{ trigger_a = yes }")
    with pytest.raises(ScriptedTriggerCycleError) as exc_info:
        expand_scripted_triggers(block, catalog)
    assert exc_info.value.chain == ("trigger_a", "trigger_a")


def test_expand_raises_on_indirect_cycle_naming_the_full_chain():
    catalog = _catalog({
        "trigger_a": "{ trigger_b = yes }",
        "trigger_b": "{ trigger_a = yes }",
    })
    block = _potential("{ trigger_a = yes }")
    with pytest.raises(ScriptedTriggerCycleError) as exc_info:
        expand_scripted_triggers(block, catalog)
    assert exc_info.value.chain == ("trigger_a", "trigger_b", "trigger_a")


def test_expand_raises_when_depth_bound_exceeded():
    # A long, non-cyclic chain deeper than MAX_EXPANSION_DEPTH -- must hard-fail, never silently
    # truncate (module docstring).
    names = [f"trigger_{i}" for i in range(MAX_EXPANSION_DEPTH + 3)]
    defs = {names[i]: f"{{ {names[i + 1]} = yes }}" for i in range(len(names) - 1)}
    defs[names[-1]] = "{ is_nomadic = yes }"
    catalog = _catalog(defs)
    block = _potential(f"{{ {names[0]} = yes }}")
    with pytest.raises(ExpansionDepthExceededError):
        expand_scripted_triggers(block, catalog)


def test_expand_does_not_raise_just_under_the_depth_bound():
    depth = MAX_EXPANSION_DEPTH - 1
    names = [f"trigger_{i}" for i in range(depth)]
    defs = {names[i]: f"{{ {names[i + 1]} = yes }}" for i in range(len(names) - 1)}
    defs[names[-1]] = "{ is_nomadic = yes }"
    catalog = _catalog(defs)
    block = _potential(f"{{ {names[0]} = yes }}")
    expanded = expand_scripted_triggers(block, catalog)  # should not raise
    assert evaluate_trigger_block(expanded, HIVE_BIO_NOMADIC).state == AVAILABLE
