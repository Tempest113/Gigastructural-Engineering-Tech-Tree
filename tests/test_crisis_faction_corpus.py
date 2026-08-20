"""D-7's full three-step crisis-faction derivation, run against the real vendored corpus over
the exact 980-node P-16 rendered set -- the corrected counts Addition 2 asked for (layout
lane populations must come from the real derivation, not the provisional ID-only survey).

Skipped when vendor/ isn't populated, same posture as the other corpus tests.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from pipeline.clausewitz import parse_file
from pipeline.crisis_faction import CRISIS_FACTIONS, classify_crisis_factions
from pipeline.crisis_faction_flags import load_flag_overrides
from pipeline.crisis_faction_overrides import load_overrides
from pipeline.overwrites import collect_technology_definitions
from pipeline.rendering_scope import rendered_technology_keys

REPO_ROOT = Path(__file__).resolve().parent.parent
VENDOR_ROOT = REPO_ROOT / "vendor"

_SOURCES_IN_LOAD_ORDER = [
    ("Vanilla", VENDOR_ROOT / "stellaris"),
    ("Gigastructural Engineering", VENDOR_ROOT / "mods" / "gigastructures"),
    ("ACOT", VENDOR_ROOT / "mods" / "acot"),
    ("AoT", VENDOR_ROOT / "mods" / "aot"),
]

_vendor_populated = VENDOR_ROOT.is_dir() and any(root.is_dir() for _, root in _SOURCES_IN_LOAD_ORDER)

pytestmark = pytest.mark.skipif(not _vendor_populated, reason="vendor/ not populated locally")


@pytest.fixture(scope="module")
def rendered_history():
    tech_docs = [
        (name, [parse_file(f) for f in sorted((root / "common" / "technology").glob("*.txt"))])
        for name, root in _SOURCES_IN_LOAD_ORDER
        if (root / "common" / "technology").is_dir()
    ]
    history = collect_technology_definitions(tech_docs)
    rendered_keys = rendered_technology_keys(history)
    return {key: history[key][-1] for key in rendered_keys}


def test_corrected_faction_counts(rendered_history):
    overrides = load_overrides()
    flag_overrides = load_flag_overrides()
    result = classify_crisis_factions(rendered_history, overrides, flag_overrides)

    counts = Counter(faction or "Standard" for faction in result.values())
    print("\n--- D-7 corrected crisis-faction populations (977 rendered nodes, D-18) ---")
    for faction, count in counts.most_common():
        print(f"  {faction}: {count}")

    assert sum(counts.values()) == 977  # D-18: 980 -> 977
    # Regression anchor, EAWAF/Sirenalia correction session (see
    # config/crisis_faction_flag_overrides.txt's EAWAF block, config/crisis_faction_overrides.txt's
    # giga_tech_eawaf_psifusion entry, pipeline/crisis_faction.py's module docstring, and CLAUDE.md's
    # defect-class entry for the full story). Step 1 (ID) contributes 7 Sirenalia nodes on its own
    # ("siren" fragment: giga_tech_eawaf_sirens_secret/_strike_craft/_autocannon/_artillery/_missile/
    # _impactor/_voidbeam). Step 1.5 (config/crisis_faction_flag_overrides.txt) now classifies 7 nodes
    # beyond step 1: 1 Compound (tech_qnm_utilities, pre-existing) + 6 new Sirenalia
    # (giga_tech_thaumaturgic_weaponry via giga_faust_weaponry_possible,
    # giga_tech_eawaf_disenchanter_1/2/3/4 via their own _possible flags,
    # giga_tech_eawaf_weapons_repeatable via giga_tech_eawaf_weapons_repeatable_possible -- all six
    # flags confirmed set exclusively inside the Sirens' own giga_eawaf-namespace event chain, with
    # NO has_star_flag=giga_eawaf_siren_faust signal involved anywhere in the derivation, per the
    # user's explicit instruction that signal is unsound). Step 2 (prerequisite inheritance)
    # contributes zero, by design (see classify_by_prerequisite_inheritance's docstring: a mixed
    # prerequisite set never propagates). Step 3 (the technology-key override table,
    # config/crisis_faction_overrides.txt) now carries 15 entries: the original 14 (Compound) plus 1
    # new (giga_tech_eawaf_psifusion -> Sirenalia -- the one EAWAF technology with no `potential`
    # block at all, so neither step 1.5 nor any automatic mechanism can reach it; file/category/
    # event-chain co-location is the only evidence, hence an override rather than a flag-map entry).
    # Total Sirenalia: 7 (step 1) + 6 (step 1.5) + 1 (step 3) = 14, up from 7. Total Compound
    # unchanged at 15 (1 flag-map + 14 overrides, as before this session). If a corpus refresh ever
    # changes any of these counts, that's real news (new crisis content shipped, or existing content
    # restructured), not a silent drift to wave through.
    assert counts["Standard"] == 900  # D-18: 980 -> 977, all 3 dropped were Standard-faction
    assert counts["Blokkats"] == 42
    assert counts["Sirenalia"] == 14
    assert counts["Aeternum"] == 3
    assert counts["Katzenartig Imperium"] == 3
    assert counts["Compound"] == 15


def test_confirmed_false_positive_candidate_resolves_to_standard_lane(rendered_history):
    # See pipeline/crisis_faction.py's module docstring: giga_tech_tetradimensional_engineering
    # was tried via potential-block flag inspection and found to be a false positive (an
    # alternate unlock path through Blokkat crisis progress, not Blokkats-lane membership).
    # Confirm the real derivation (ID + prerequisite inheritance + override) correctly leaves it
    # in the standard lane -- no override entry exists for it, deliberately.
    overrides = load_overrides()
    flag_overrides = load_flag_overrides()
    result = classify_crisis_factions(rendered_history, overrides, flag_overrides)
    assert result["giga_tech_tetradimensional_engineering"] is None


def test_compound_weapon_bypass_override_candidates_resolve_to_compound(rendered_history):
    # The corrected verdict (see pipeline/crisis_faction.py's module docstring and
    # config/crisis_faction_overrides.txt): both technologies resolve to Compound only because
    # of the step-3 override, not the automatic derivation -- confirm both halves.
    overrides = load_overrides()
    flag_overrides = load_flag_overrides()
    result_without_override = classify_crisis_factions(rendered_history, overrides=None, flag_overrides=flag_overrides)
    assert result_without_override["tech_sm_autocannons"] is None
    assert result_without_override["tech_qnm_disruptors"] is None

    result_with_override = classify_crisis_factions(rendered_history, overrides, flag_overrides)
    assert result_with_override["tech_sm_autocannons"] == "Compound"
    assert result_with_override["tech_qnm_disruptors"] == "Compound"


def test_qnm_utilities_dependents_do_not_inherit_automatically_but_do_via_override(rendered_history):
    # Part-0 reconciliation (see HANDOFF.md): tech_qnm_utilities itself is classified Compound via
    # config/crisis_faction_flag_overrides.txt's entry (qnm_utilities_possible). Its 12 direct
    # dependents (the tech_sm_*/tech_qnm_* weapon-component techs in giga_08_ehof_components.txt,
    # each `prerequisites = { "<baseline weapon tech>" "tech_qnm_utilities" }`) do NOT inherit
    # Compound through step 2 WITHOUT the override table, because each also requires an ordinary
    # Standard-lane baseline weapon technology -- a mixed prerequisite set, which step 2 correctly
    # refuses to propagate through (see classify_by_prerequisite_inheritance's docstring: "a
    # mixed or partially-unclassified prerequisite set inherits nothing"). That gap is real and
    # deliberately not closed by widening step 2 -- it is closed instead by 12 individually
    # reviewed entries in config/crisis_faction_overrides.txt (same file, same review bar as the
    # two bypass-flag entries), confirmed here to resolve Compound WITH the override table loaded.
    dependents = [
        "tech_sm_flak_batteries", "tech_sm_mass_drivers", "tech_sm_kinetic_artillery",
        "tech_sm_mass_accelerator", "tech_sm_titanic", "tech_qnm_pd_tracking",
        "tech_qnm_lasers", "tech_qnm_plasma", "tech_qnm_energy_torpedoes",
        "tech_qnm_energy_lance", "tech_qnm_arc_emitter", "tech_qnm_titanic",
    ]
    flag_overrides = load_flag_overrides()

    result_without_override = classify_crisis_factions(rendered_history, overrides=None, flag_overrides=flag_overrides)
    assert result_without_override["tech_qnm_utilities"] == "Compound"
    present = [key for key in dependents if key in result_without_override]
    assert len(present) == 12, f"expected all 12 tech_qnm_utilities dependents in the rendered set, found {len(present)}"
    for key in present:
        assert result_without_override[key] is None, (
            f"{key} unexpectedly inherited a crisis faction without the override table: "
            f"{result_without_override[key]}"
        )

    overrides = load_overrides()
    result_with_override = classify_crisis_factions(rendered_history, overrides, flag_overrides)
    assert result_with_override["tech_qnm_utilities"] == "Compound"
    for key in present:
        assert result_with_override[key] == "Compound", f"{key} expected Compound via override, got {result_with_override[key]}"


def test_compound_weapon_bypass_technologies_potential_shape_is_unchanged():
    # Regression guard for config/crisis_faction_overrides.txt's two Compound entries: the
    # override's justification depends on the EXACT shape of each technology's `potential` block
    # (a bare has_country_flag = giga_special_tech_compound_weapon_bypass branch alongside a
    # has_technology AND-branch, no other reference to the flag). If a future corpus revision
    # restructures either block -- renames the flag, removes the bypass branch, merges the
    # has_technology conditions -- this fails and forces the override back under human review
    # rather than silently keeping a stale classification (config/crisis_faction_overrides.txt's
    # own header comment already states this override does not track corpus growth).
    path = (
        VENDOR_ROOT / "mods" / "gigastructures" / "common" / "technology"
        / "giga_08_ehof_components.txt"
    )
    text = path.read_text(encoding="utf-8")
    for key, baseline_tech in [
        ("tech_sm_autocannons", "tech_autocannons_3"),
        ("tech_qnm_disruptors", "tech_disruptors_3"),
    ]:
        start = text.index(f"{key} = {{")
        end = text.index("\n}", start)
        block = text[start:end]
        assert block.count("giga_special_tech_compound_weapon_bypass") == 1
        assert "has_country_flag = giga_special_tech_compound_weapon_bypass" in block
        assert f"has_technology = {baseline_tech}" in block
        assert "has_technology = tech_qnm_utilities" in block
        assert block.count("has_technology") == 2


def test_compound_technologies_are_commented_out_in_the_vendored_corpus():
    # Direct evidence for the "Compound is a real zero" claim: the seven tech_compound_* blocks
    # in giga_08_ehof_components.txt are present as raw text but never parse into technology
    # definitions, because every line is commented out.
    path = VENDOR_ROOT / "mods" / "gigastructures" / "common" / "technology" / "giga_08_ehof_components.txt"
    text = path.read_text(encoding="utf-8")
    compound_keys = [
        "tech_compound_armor", "tech_compound_computers", "tech_compound_drives",
        "tech_compound_reactors", "tech_compound_sensors", "tech_compound_shields",
        "tech_compound_thrusters",
    ]
    for key in compound_keys:
        assert f"# {key} = {{" in text or f"#{key} = {{" in text, f"{key} expected as commented-out source"


# --- Test-scope-only DNF reachability rule (EAWAF/Sirenalia correction session) -----------------
#
# A generalised classifier idea, tried against the real corpus and asked for here as a
# convergence CHECK, not a replacement for the hand-built D-7 derivation: a technology belongs to
# faction F if every DNF term of its unlock formula (its `prerequisites` list, mandatory-AND, cross
# distributed against its `potential` block's own AND/OR structure) requires either an
# F-classified `has_technology` reference or an F-mapped `has_country_flag` reference (via
# config/crisis_faction_flag_overrides.txt) in that term. `NOT`/`NOR`-wrapped conditions are
# scoped out entirely (contribute no atoms, same discipline `pipeline.edges._scoped_has_technology`
# and `pipeline.crisis_faction._scoped_has_country_flag` already use) -- a negative condition is
# never evidence of a positive membership requirement.
#
# This lives ONLY in this test module, deliberately -- it is not promoted to
# pipeline/crisis_faction.py. The hand-built three-step derivation (ID, flag-map, technology-key
# override) remains the live classifier; this is a second, independent check computed the same way
# a reviewer would reason about reachability by hand, run once here to see whether it agrees.
def _dnf_terms(block) -> list[frozenset[tuple[str, str]]]:
    from pipeline.clausewitz.nodes import Assignment, Block

    def target_name(value) -> str | None:
        from pipeline.clausewitz.nodes import Identifier, StringLiteral

        if isinstance(value, Identifier):
            return value.name
        if isinstance(value, StringLiteral):
            return value.value
        return None

    def single_item_terms(item) -> list[frozenset[tuple[str, str]]]:
        if not isinstance(item, Assignment):
            return [frozenset()]
        key_upper = item.key_name.upper()
        if item.key_name == "has_technology":
            name = target_name(item.value)
            return [frozenset({("tech", name)})] if name else [frozenset()]
        if item.key_name == "has_country_flag":
            name = target_name(item.value)
            return [frozenset({("flag", name)})] if name else [frozenset()]
        if key_upper == "AND" and isinstance(item.value, Block):
            return _dnf_terms(item.value)
        if key_upper == "OR" and isinstance(item.value, Block):
            branches: list[frozenset[tuple[str, str]]] = []
            for child in item.value.items:
                branches.extend(single_item_terms(child))
            return branches or [frozenset()]
        # NOT/NOR/anything else: opaque, contributes no atoms (identity element for AND).
        return [frozenset()]

    terms: list[frozenset[tuple[str, str]]] = [frozenset()]
    for item in block.items:
        item_terms = single_item_terms(item)
        terms = [t1 | t2 for t1 in terms for t2 in item_terms]
    deduped = list(set(terms))
    return deduped or [frozenset()]


def _reachability_classify(
    rendered_history: dict, overrides, flag_overrides
) -> dict[str, str | None]:
    from pipeline.crisis_faction import classify_by_tech_id
    from pipeline.overwrites import ordered_prerequisites

    def field(block, name):
        from pipeline.clausewitz.nodes import Assignment

        result = None
        for item in block.items:
            if isinstance(item, Assignment) and item.key_name == name:
                result = item
        return result

    result: dict[str, str | None] = {
        key: classify_by_tech_id(key) for key in rendered_history
    }

    def term_requires(term: frozenset[tuple[str, str]], faction: str) -> bool:
        for kind, name in term:
            if kind == "tech" and result.get(name) == faction:
                return True
            if kind == "flag" and flag_overrides.get(name) and flag_overrides[name].faction == faction:
                return True
        return False

    for _ in range(len(rendered_history)):
        changed = False
        for key, definition in rendered_history.items():
            if result[key] is not None:
                continue
            block = definition.block
            potential_field = field(block, "potential")
            potential_terms = (
                _dnf_terms(potential_field.value)
                if potential_field is not None and hasattr(potential_field.value, "items")
                else [frozenset()]
            )
            prereq_atoms = frozenset(
                ("tech", p) for p in ordered_prerequisites(block) if p in rendered_history
            )
            full_terms = [term | prereq_atoms for term in potential_terms]
            if not full_terms or all(not t for t in full_terms):
                continue
            candidate_factions = set(CRISIS_FACTIONS)
            for term in full_terms:
                candidate_factions &= {f for f in CRISIS_FACTIONS if term_requires(term, f)}
                if not candidate_factions:
                    break
            if len(candidate_factions) == 1:
                (only,) = candidate_factions
                result[key] = only
                changed = True
        if not changed:
            break

    for key, override in overrides.items():
        if key in result:
            result[key] = override.faction

    return result


def test_dnf_reachability_rule_convergence(rendered_history):
    """Test-scope-only convergence check (see module comment above) -- NOT promoted to the live
    classifier. Compares the generalised DNF-reachability rule's output against the real,
    override-inclusive D-7 derivation and reports any disagreement rather than silently asserting
    equality, so a future run that finds a real disagreement fails loudly and visibly rather than
    passing on a weakened assertion."""
    from pipeline.crisis_faction import CRISIS_FACTIONS as _CF

    overrides = load_overrides()
    flag_overrides = load_flag_overrides()
    hand_built = classify_crisis_factions(rendered_history, overrides, flag_overrides)
    rule_based = _reachability_classify(rendered_history, overrides, flag_overrides)

    disagreements = {
        key: (hand_built[key], rule_based[key])
        for key in rendered_history
        if hand_built[key] != rule_based[key]
    }
    print(f"\n--- DNF reachability rule vs. hand-built D-7 derivation: {len(disagreements)} disagreements ---")
    for key, (hand, rule) in sorted(disagreements.items()):
        print(f"  {key}: hand={hand!r} rule={rule!r}")

    assert disagreements == {}, (
        "DNF reachability rule diverged from the hand-built D-7 derivation -- see printed output "
        "above. This is a REPORT-ONLY finding for a test-scope-only rule; do not silently widen "
        "the assertion to make it pass without understanding why they disagree."
    )
