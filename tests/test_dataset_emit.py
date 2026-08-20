"""Stage 2 dataset emission, end to end against the real vendored corpus. Skipped when vendor/
isn't populated, same posture as the other corpus tests. Builds and schema-validates all five
artefacts, and measures real transfer sizes (including compression) against P-10's budget.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from tests.conftest import REPO_ROOT

from pipeline.dataset_emit import (
    build_base_dataset,
    build_context,
    build_detail_payload,
    build_diagnostics,
    build_empire_overlay,
    build_search_index,
)
from pipeline.dataset_schema import (
    validate_base_dataset,
    validate_detail_payload,
    validate_diagnostics,
    validate_empire_overlay,
    validate_search_index,
)
from pipeline.dataset_schema.empire_profile import check_availability_matrix_matches_overlays

VENDOR_ROOT = REPO_ROOT / "vendor"
_vendor_populated = VENDOR_ROOT.is_dir()

pytestmark = pytest.mark.skipif(not _vendor_populated, reason="vendor/ not populated")


def _gz(data: bytes) -> int:
    return len(gzip.compress(data, compresslevel=9))


@pytest.fixture(scope="module")
def ctx():
    return build_context(VENDOR_ROOT)


@pytest.fixture(scope="module")
def base_dataset(ctx):
    doc, node_bytes, edge_bytes = build_base_dataset(ctx)
    validate_base_dataset(doc)
    return doc, node_bytes, edge_bytes


def test_base_dataset_covers_all_977_rendered_technologies(ctx, base_dataset):
    # D-18 (spec/decisions.md): 980 -> 977, the depth-1 ACOT/AoT closure adopted this session.
    doc, _node_bytes, _edge_bytes = base_dataset
    assert len(doc["technologies"]) == 977
    assert {t["id"] for t in doc["technologies"]} == ctx.rendered_keys


def test_base_dataset_edge_count_matches_p14_survey(base_dataset):
    # D-18 (spec/decisions.md): 989 -> 984 -- the depth-1 ACOT/AoT closure drops 3 technologies,
    # removing 5 `prerequisite` edges that touched them; alternative/potential-gate unaffected.
    doc, _node_bytes, _edge_bytes = base_dataset
    assert len(doc["edges"]) == 984
    from collections import Counter

    assert dict(Counter(e["kind"] for e in doc["edges"])) == {
        "prerequisite": 883, "alternative": 76, "potential-gate": 25,
    }


def test_base_dataset_gates_match_the_gate_classification_survey(base_dataset):
    """P-3 (gate-classification session): real per-mechanism counts, pinned so a future corpus
    change is caught rather than silently drifting. 45 ascension_perk-kind gate instances (22
    has_ascension_perk + 9 has_gigastructural_constructs + 14 has_galactic_wonders) + 25
    technology-kind gate instances (== the 25 potential-gate edges, one-to-one) == 70 total, over
    60 technologies, 10 of which carry more than one gate INSTANCE (7 crossing two distinct
    mechanism types -- 6 tech_lathe_* + giga_tech_the_vat -- plus 3 more carrying two
    has_technology targets each -- giga_tech_disco_moon, tech_qnm_disruptors,
    tech_sm_autocannons -- which the survey's per-mechanism-TYPE grouping didn't distinguish from
    a single-target technology, only found once gates were actually built)."""
    from collections import Counter

    doc, _node_bytes, _edge_bytes = base_dataset
    gated = [t for t in doc["technologies"] if t["gates"]]
    all_gates = [g for t in doc["technologies"] for g in t["gates"]]
    assert len(all_gates) == 70
    assert dict(Counter(g["kind"] for g in all_gates)) == {"ascension_perk": 45, "technology": 25}
    assert len(gated) == 60
    assert sum(1 for t in gated if len(t["gates"]) > 1) == 10

    # Every technology-kind gate instance is exactly one of the 25 potential-gate edges, one to
    # one -- classification never removes or alters the underlying edge (spec/P-03-gates.md).
    potential_gate_pairs = {(e["from"], e["to"]) for e in doc["edges"] if e["kind"] == "potential-gate"}
    gate_tech_pairs = {
        (g["refId"], t["id"]) for t in doc["technologies"] for g in t["gates"] if g["kind"] == "technology"
    }
    assert gate_tech_pairs == potential_gate_pairs

    vat = next(t for t in doc["technologies"] if t["id"] == "giga_tech_the_vat")
    assert [g["kind"] for g in vat["gates"]] == ["ascension_perk", "ascension_perk"]
    assert {g["refId"] for g in vat["gates"]} == {"ap_galactic_wonders", "ap_mechromancy"}
    for g in vat["gates"]:
        assert g["label"].startswith("Needs ")
        assert g["icon"]["width"] > 1  # not the degenerate 1x1 placeholder


def test_gate_ordering_puts_ascension_perk_gates_first(base_dataset):
    """D-3 (spec/P-03-gates.md): ascension-perk gates outrank technology gates. The
    tech_lathe_* family (real corpus, gate-classification survey) is the only real case with one
    of each -- confirms the primary gate (index 0, P-12.7) is always the perk, never the tech."""
    doc, _node_bytes, _edge_bytes = base_dataset
    for key in [
        "tech_lathe_cogitator", "tech_lathe_life_support", "tech_lathe_overclocker",
        "tech_lathe_preserver", "tech_lathe_resonator", "tech_lathe_validator",
    ]:
        tech = next(t for t in doc["technologies"] if t["id"] == key)
        assert [g["kind"] for g in tech["gates"]] == ["ascension_perk", "technology"]


def test_gate_classification_leaves_d10_uncertainty_unchanged(ctx, base_dataset):
    """Item 2's own requirement: assert this rather than assume it. The four registered gate
    keys were already excluded from pipeline.availability's boolean combination before this
    module existed (EXCLUDED_KEYS, an identity-element state) -- gate classification adds only
    display metadata, touching zero availability-evaluation code paths.

    D-10 splits uncertainty into two metrics (spec/decisions.md): UNCONDITIONAL (a technology
    `uncertain` under all twelve profiles identically) and PROFILE-DEPENDENT (the excess over
    that baseline in the single worst profile) -- the latter is what the 3%/10% thresholds
    govern, per CLAUDE.md's "Trigger evaluation" section. Must stay exactly 33/977 (3.37%), no
    ratchet regression."""
    doc, _node_bytes, _edge_bytes = base_dataset
    per_profile_uncertain_counts = [
        sum(1 for t in doc["technologies"] if t["availabilityMatrix"][index] == "uncertain")
        for index in range(len(ctx.profiles))
    ]
    unconditional = sum(
        1 for t in doc["technologies"] if all(state == "uncertain" for state in t["availabilityMatrix"])
    )
    worst_profile_dependent = max(per_profile_uncertain_counts) - unconditional
    assert worst_profile_dependent == 33
    assert round(worst_profile_dependent / len(doc["technologies"]), 4) == 0.0338  # 33/977


def test_base_dataset_band_and_lane_shape(base_dataset):
    doc, _node_bytes, _edge_bytes = base_dataset
    assert len(doc["tierBands"]) == 11
    assert doc["tierBands"][-1]["tier"] == "repeatables"
    # D-16's row re-axis (spec/decisions.md): the "rows"/"rowId" JSON field names are
    # deliberately UNCHANGED (see D-16 for why), but there are now 18 entries -- the 13 derived
    # category rows (grouped by area, alphabetical within an area) then the 5 fixed crisis-faction
    # rows -- not the old 6 (Standard + 5 factions).
    assert [lane["id"] for lane in doc["rows"]] == [
        "computing", "field_manipulation", "particles",
        "archaeostudies", "biology", "military_theory", "new_worlds", "psionics", "statecraft",
        "industry", "materials", "propulsion", "voidcraft",
        "Aeternum", "Blokkats", "Compound", "Sirenalia", "Katzenartig Imperium",
    ]
    assert len(doc["rows"]) == 18
    # A category row's label is its resolved localised display name, not the bare machine id.
    voidcraft_row = next(lane for lane in doc["rows"] if lane["id"] == "voidcraft")
    assert voidcraft_row["label"] == "Voidcraft"
    assert voidcraft_row["crisisFaction"] is None
    # A faction row's crisisFaction is the faction name itself. Compound's population is now 15:
    # config/crisis_faction_flag_overrides.txt's flag-map entry (qnm_utilities_possible)
    # classifies tech_qnm_utilities, and config/crisis_faction_overrides.txt carries 14
    # technology-key override entries (the original 2 bypass-flag entries plus 12 for
    # tech_qnm_utilities' direct prerequisite dependents) -- see both files and
    # pipeline/crisis_faction.py's module docstring for the full reasoning.
    compound_row = next(lane for lane in doc["rows"] if lane["id"] == "Compound")
    assert compound_row["crisisFaction"] == "Compound"
    assert compound_row["technologyCount"] == 15


def test_no_rendered_technology_name_or_description_carries_a_raw_loc_token(ctx, base_dataset):
    """PART 2's survey (later session): 161/980 raw names and 223/980 raw descriptions carried an
    unresolved `$...$` token before `_resolve_loc_tokens` was applied to both fields (previously
    only `configGatedSubject` and swap names went through it). Real corpus check: zero remain."""
    doc, _node_bytes, _edge_bytes = base_dataset
    names_with_token = [t["id"] for t in doc["technologies"] if "$" in t["name"]]
    assert names_with_token == []

    sample_keys = ["giga_tech_blokkat_obliterator", "tech_waystation_1", "tech_civilian_arkship"]
    for key in sample_keys:
        tech = next(t for t in doc["technologies"] if t["id"] == key)
        assert "$" not in tech["name"]
    assert next(t for t in doc["technologies"] if t["id"] == "tech_waystation_1")["name"] == "Waystations"
    assert next(t for t in doc["technologies"] if t["id"] == "tech_civilian_arkship")["name"] == "Civilian Arkships"


def test_no_rendered_technology_name_equals_its_own_raw_key(base_dataset):
    """Found this session, by reviewing a real rendered screenshot: `giga_tech_aeternite_weaponry`
    has a real loc entry whose VALUE is verbatim its own KEY (the mod author never wrote a display
    name) -- the `$...$`-token check above didn't catch it, since there's no token, just a bare
    key masquerading as a name. `config/name_overrides.txt` now covers the one real case; this
    asserts the fix holds and would catch a future occurrence with no override on file."""
    doc, _node_bytes, _edge_bytes = base_dataset
    bad = [t["id"] for t in doc["technologies"] if t["name"] == t["id"]]
    assert bad == []
    aeternite = next(t for t in doc["technologies"] if t["id"] == "giga_tech_aeternite_weaponry")
    assert aeternite["name"] == "Aeternite Weaponry Systems"


def test_unresolved_localisation_token_in_a_name_fails_the_build(ctx):
    """CLAUDE.md's Rules: 'the build fails rather than emitting a partial dataset ... missing
    localisation for displayed strings.' Proven capable of firing before being trusted (CLAUDE.md:
    'a clean run proves nothing until the detector is shown capable of a dirty one') -- feeds
    `_require_resolved` a token that is genuinely absent from the real loc table and asserts the
    raise, rather than relying on the real corpus never hitting this path."""
    from pipeline.dataset_emit import UnresolvedLocalisationTokenError, _require_resolved

    with pytest.raises(UnresolvedLocalisationTokenError):
        _require_resolved("$this_token_does_not_exist_anywhere_in_the_loc_table$", "tech_fake", "name", ctx)


def test_cost_per_level_carried_exactly_on_the_88_repeatables(base_dataset):
    """Item 2: cost_per_level must be a secondary card indicator alongside the primary `cost`
    field (spec/P-02-layout.md), never a stand-in replacement for it. Real corpus: exactly the
    88-node repeatable set carries a resolvable costPerLevel; 0 non-repeatable technologies do."""
    doc, _node_bytes, _edge_bytes = base_dataset
    with_cost_per_level = [t["id"] for t in doc["technologies"] if t["repeatable"] and t["repeatable"]["costPerLevel"] is not None]
    assert len(with_cost_per_level) == 88
    non_repeatable_with_repeatable_field = [t for t in doc["technologies"] if t["repeatable"] is None]
    assert len(non_repeatable_with_repeatable_field) == 977 - 88  # D-18: 980 -> 977

    sample = next(t for t in doc["technologies"] if t["id"] == "tech_repeatable_reduced_building_cost")
    assert sample["cost"] == pytest.approx(50000.0)
    assert sample["repeatable"] == {"levels": 5, "costPerLevel": pytest.approx(5000.0)}


def test_cost_field_present_for_every_technology_null_only_when_unresolvable(base_dataset):
    """Real corpus (corrected, later session -- see `pipeline.dataset_emit._resolve_cost`'s own
    docstring for the full finding): 5/980 technologies have a null cost, not the originally
    reported 15 -- those 5 have no `cost` field at all (apparently-free starting technologies).
    The other 10, all vanilla 'cosmic storm' technologies whose `cost` is a Block
    (`cost = { factor = @var inline_script = {...} }`), now resolve via their own `factor`
    sub-field -- the ORIGINAL bug was reading a Block as unconditionally unresolvable, silently
    treating a real, resolvable cost as null. Neither the 5 genuine nulls nor a guessed value for
    the 10 formerly-null block-cost technologies -- see schema/base-dataset.schema.json's `cost`
    field description and `_resolve_cost`'s docstring for why `factor` alone (not the
    resolution-conditional `modifier` block) is the right static figure."""
    doc, _node_bytes, _edge_bytes = base_dataset
    null_cost_ids = {t["id"] for t in doc["technologies"] if t["cost"] is None}
    assert null_cost_ids == {
        "tech_asteroidal_carapace", "tech_missiles_1", "tech_solar_panel_network",
        "tech_flak_batteries_1", "tech_pd_tracking_1",
    }

    resolved_costs = {t["id"]: t["cost"] for t in doc["technologies"] if t["cost"] is not None}
    assert len(resolved_costs) == 977 - 5  # D-18: 980 -> 977
    assert all(c >= 0 for c in resolved_costs.values())

    # The 10 previously-null block-form ("cosmic storm") technologies now resolve to their real
    # `factor` value -- exact figures confirmed by direct raw-source survey, not guessed at.
    assert resolved_costs["tech_storm_manipulation"] == 2500.0
    assert resolved_costs["tech_storm_prediction_1"] == 1250.0
    assert resolved_costs["tech_storm_prediction_2"] == 5000.0
    assert resolved_costs["tech_ship_storm_weapons_1"] == 1250.0
    assert resolved_costs["tech_ship_storm_weapons_2"] == 2000.0
    assert resolved_costs["tech_ship_hull_storm_breaker_1"] == 1250.0
    assert resolved_costs["tech_ship_hull_storm_breaker_2"] == 2000.0
    assert resolved_costs["tech_industrial_storm_protection"] == 1000.0
    assert resolved_costs["tech_advanced_industrial_storm_protection"] == 2000.0
    assert resolved_costs["tech_advanced_storm_manipulation"] == 4000.0


def test_resolve_cost_handles_block_form_and_still_refuses_to_guess():
    """Synthetic, mechanism-level: proves `_resolve_cost` capable of BOTH outcomes before trusting
    the real-corpus result above -- resolves a block with a resolvable `factor`, and still returns
    `None` (never a guess) for a block whose `factor` doesn't resolve, or is absent entirely."""
    from pipeline.clausewitz import parse_text
    from pipeline.dataset_emit import _field, _resolve_cost
    from pipeline.variables import build_variable_table

    doc = parse_text(
        "tech_x = { cost = { factor = @storm_cost modifier = { factor = 0.75 is_galactic_community_member = yes } } }\n"
        "tech_y = { cost = { factor = @undefined_var } }\n"
        "tech_z = { cost = { modifier = { factor = 0.75 } } }\n"
        "@storm_cost = 2500\n",
        path="x.txt",
    )
    var_table = build_variable_table([doc])
    tech_x_cost = doc.items[0].value
    tech_y_cost = doc.items[1].value
    tech_z_cost = doc.items[2].value

    assert _resolve_cost(_field(tech_x_cost, "cost").value, var_table) == 2500.0
    assert _resolve_cost(_field(tech_y_cost, "cost").value, var_table) is None  # @undefined_var never resolves
    assert _resolve_cost(_field(tech_z_cost, "cost").value, var_table) is None  # no `factor` field at all


def test_base_dataset_compressed_transfer_size_under_p10_budget(base_dataset):
    """P-10: initial dataset transfer (JSON + geometry side-files, compressed) MUST be <= 2 MB."""
    doc, node_bytes, edge_bytes = base_dataset
    base_json = json.dumps(doc).encode()

    json_gz = _gz(base_json)
    node_gz = _gz(node_bytes)
    edge_gz = _gz(edge_bytes)
    total_compressed = json_gz + node_gz + edge_gz

    print(f"\nbase dataset JSON: {len(base_json):,} raw -> {json_gz:,} gz (ratio {len(base_json) / json_gz:.2f}x)")
    print(f"node side-file: {len(node_bytes):,} raw -> {node_gz:,} gz")
    print(f"edge side-file: {len(edge_bytes):,} raw -> {edge_gz:,} gz")
    print(f"TOTAL compressed base-dataset transfer: {total_compressed:,} bytes ({total_compressed / 1024:.1f} KB)")

    assert total_compressed <= 2 * 1024 * 1024, (
        f"{total_compressed} bytes exceeds P-10's 2 MB compressed base-dataset transfer budget"
    )
    # Real measured figure, locked in so a future change that materially grows the base dataset
    # is visible here rather than silently absorbed. See CLAUDE.md's Stage 2 emission section for
    # the full reconciliation against the ~275-305 KB pre-build projection.
    assert total_compressed < 100_000


def test_all_twelve_empire_overlays_validate(ctx):
    from pipeline.dataset_schema.empire_profile import all_profiles_in_canonical_order

    profiles = all_profiles_in_canonical_order()
    assert len(profiles) == 12
    for profile in profiles:
        overlay = build_empire_overlay(ctx, profile)
        validate_empire_overlay(overlay)
        assert len(overlay["availability"]) == 977  # D-18: 980 -> 977
        assert len(overlay["researchPaths"]) == 977


def test_availability_matrix_agrees_with_overlays(ctx, base_dataset):
    from pipeline.dataset_schema.empire_profile import all_profiles_in_canonical_order

    doc, _node_bytes, _edge_bytes = base_dataset
    overlays = [build_empire_overlay(ctx, p) for p in all_profiles_in_canonical_order()]
    check_availability_matrix_matches_overlays(doc["technologies"], overlays)  # raises if mismatched


def test_empire_profile_axes_emitted_and_matches_the_canonical_module(ctx, base_dataset):
    """Item 1b (gate-classification survey session): the client derives EmpireProfileIndex from
    this emitted field instead of restating pipeline.dataset_schema.empire_profile's formula --
    proves the real build's own emitted `empireProfileAxes` is exactly what that module would
    derive, so a client bug can only be "derived from stale/wrong data", never "two formulas
    disagree"."""
    from pipeline.dataset_schema.empire_profile import build_empire_profile_axes

    doc, _node_bytes, _edge_bytes = base_dataset
    assert doc["empireProfileAxes"] == build_empire_profile_axes()


def test_empire_profile_axes_total_matches_availability_matrix_width(ctx, base_dataset):
    """The cross-check that would catch a one-sided axis-cardinality change: if AXES ever grows
    (say a fourth authority value), `totalProfileCount` moves immediately (it's derived), but
    `availabilityMatrix`'s emitted width is controlled separately, by how many profiles
    `build_base_dataset` actually iterates when filling the matrix (dataset_emit.py) -- those two
    numbers agreeing here is what proves the matrix wasn't left at the old width while the axes
    metadata moved on, or vice versa."""
    doc, _node_bytes, _edge_bytes = base_dataset
    total = doc["empireProfileAxes"]["totalProfileCount"]
    assert total == 12  # today's real shape -- see the module docstring for the schema-version-bump policy.
    for tech in doc["technologies"]:
        assert len(tech["availabilityMatrix"]) == total


@pytest.fixture(scope="module")
def all_detail_payloads(ctx):
    return {key: build_detail_payload(ctx, key) for key in sorted(ctx.rendered_keys)}


def test_all_977_detail_payloads_validate(all_detail_payloads):
    # D-18: 980 -> 977
    assert len(all_detail_payloads) == 977
    for payload in all_detail_payloads.values():
        validate_detail_payload(payload)


def test_search_index_covers_all_technologies_and_validates(ctx, base_dataset, all_detail_payloads):
    doc, _node_bytes, _edge_bytes = base_dataset
    index = build_search_index(ctx, doc, all_detail_payloads)
    validate_search_index(index)
    assert len(index["entries"]) == 977  # D-18: 980 -> 977
    assert all(e["tokens"] for e in index["entries"])


def test_diagnostics_validates_and_reports_the_unconditional_uncertain_finding(ctx):
    """Real finding, corrected twice, not a bug in this emission code either time:

    1. Building the availability survey with inline_script-EXPANDED blocks (as this module does
       throughout) surfaces a real `potential` condition for all 50 `giga_tech_repeatable_*_cap`
       technologies that a raw-block survey cannot see at all -- those 50 initially moved into
       `unconditionalUncertainty`, taking the count from 209 to 259.
    2. Those 50 don't actually belong there: their `potential` is
       `NOT{has_global_flag=X_disabled} AND has_global_flag=X_capped_r`, both mod-configuration
       toggles that resolve DEFINITIVELY (not UNCERTAIN) once
       `pipeline.trigger_text.MOD_CONFIG_TOGGLE_SUFFIXES` recognises `_capped_r` -- confirmed by
       the user that no core Gigastructures preset sets a cap to the "1+r" mode this flag names.
       They resolve to `config-gated` (D-10's new fourth AvailabilityState), moving the count back
       to 209 -- the same number the ORIGINAL raw-block-survey code reported, by coincidence of
       arithmetic, not by the same (wrong) reasoning: that number skipped these 50 nodes entirely,
       this number evaluates them correctly and finds they belong in a different state.

    See CLAUDE.md's "Availability evaluator" section for the full writeup."""
    diagnostics = build_diagnostics(ctx)
    validate_diagnostics(diagnostics)

    assert diagnostics["unconditionalUncertainty"]["count"] == 209
    assert len(diagnostics["profileDependentUncertainty"]) == 12
    worst = max(d["rate"] for d in diagnostics["profileDependentUncertainty"])
    # D-18 (spec/decisions.md, this session): rate moved 0.033673 -> 0.033777 purely from the
    # denominator shrinking 980 -> 977 (the depth-1 ACOT/AoT closure) -- the worst profile's
    # UNCERTAIN count itself is unchanged at 33 (33/980 = 0.033673..., 33/977 = 0.033777...,
    # confirmed directly, not assumed): none of the 3 dropped ACOT technologies was ever
    # profile-dependent-uncertain.
    assert worst == pytest.approx(0.033777, abs=1e-5)

    cap_keys = {k for k in ctx.rendered_keys if k.startswith("giga_tech_repeatable_") and k.endswith("_cap")}
    assert len(cap_keys) == 50
    for key in cap_keys:
        from pipeline.dataset_emit import _field

        assert _field(ctx.rendered_defs[key].block, "potential") is not None, (
            f"{key}: expected a potential block visible only after inline_script expansion"
        )


def test_repeatable_cap_family_is_config_gated_in_every_profile(base_dataset):
    """The base dataset's `availabilityMatrix` must show `config-gated`, not `locked` or
    `uncertain`, for every one of the 50 giga_tech_repeatable_*_cap technologies, in all 12
    profile slots -- this is a profile-INVARIANT result (a mod-configuration toggle, not an
    empire-type fact), so unlike an ordinary uncertain/locked technology, every slot must be
    identical."""
    doc, _node_bytes, _edge_bytes = base_dataset
    cap_ids = {t["id"] for t in doc["technologies"] if t["id"].startswith("giga_tech_repeatable_") and t["id"].endswith("_cap")}
    assert len(cap_ids) == 50

    for tech in doc["technologies"]:
        if tech["id"] in cap_ids:
            assert tech["availabilityMatrix"] == ["config-gated"] * 12, tech["id"]

    non_cap_config_gated = [
        t["id"] for t in doc["technologies"] if t["id"] not in cap_ids and "config-gated" in t["availabilityMatrix"]
    ]
    assert non_cap_config_gated == []


def test_repeatable_cap_family_available_count_delta_is_exactly_minus_50(ctx, base_dataset):
    """Item 1 (CLAUDE.md/HANDOFF.md's 209 -> 259 -> 209 sequence): the unconditional-uncertainty
    count is identical (209) both before the inline_script-expansion fix and now, for entirely
    different reasons -- it does NOT show the substantive change. The AVAILABLE-state count does.
    Before the fix, a raw/unexpanded read saw no `potential` block at all for these 50
    technologies (a defect) -- `evaluate_trigger_block(None, profile)` is the exact counterfactual
    that reproduces what that defect saw, and is unconditionally AVAILABLE. After the fix, the
    real (expanded) evaluation used throughout this pipeline shows none of them AVAILABLE -- all
    50 are config-gated in every profile. The delta is exactly -50, profile-invariant."""
    from pipeline.availability import AVAILABLE, evaluate_trigger_block

    doc, _node_bytes, _edge_bytes = base_dataset
    cap_ids = sorted(t["id"] for t in doc["technologies"] if t["id"].startswith("giga_tech_repeatable_") and t["id"].endswith("_cap"))
    assert len(cap_ids) == 50

    profile = ctx.profiles[0]
    counterfactual_available = sum(
        1 for _ in cap_ids if evaluate_trigger_block(None, profile).state == AVAILABLE
    )
    assert counterfactual_available == 50

    real_available = sum(
        1 for tech in doc["technologies"]
        if tech["id"] in cap_ids and "available" in tech["availabilityMatrix"]
    )
    assert real_available == 0

    assert real_available - counterfactual_available == -50


def test_config_gated_subject_resolves_all_50_megastructure_names(ctx):
    """Item 2 follow-up (CLAUDE.md, spec/P-13-empire-locking.md): the config-gated reason
    template's semantic subject, sourced from each cap technology's own localised name
    (`<Name> Management Protocols`). An earlier session found 8/50 fell back to null because the
    technology's own name embeds a `$...$` token and assumed that token was an unresolvable
    Stellaris runtime name-pool reference. That assumption was WRONG, corrected against raw
    source inspection: every `$token$` here is ordinary Stellaris loc-key substitution -- `token`
    is itself a ordinary, statically-resolvable loc key (e.g. `dyson_swarm_3: "Dyson Swarm"`,
    `orbital_arc_furnace_4: "Arc Furnace"`, both in VANILLA's own localisation, since those two
    megastructures are vanilla ones Gigastructures extends -- confirming the lookup must search
    the full cross-source loc table, not just Gigastructures'). All 50/50 now resolve to a
    literal megastructure name; if a future corpus refresh ever reintroduces a genuinely
    unresolvable token, this test's exact-50 assertion fails loudly rather than silently
    tolerating a null."""
    overlay = build_empire_overlay(ctx, ctx.profiles[0])
    cap_keys = sorted(k for k in ctx.rendered_keys if k.startswith("giga_tech_repeatable_") and k.endswith("_cap"))
    assert len(cap_keys) == 50

    subjects = {k: overlay["availability"][k]["configGatedSubject"] for k in cap_keys}
    resolved = {k: v for k, v in subjects.items() if v is not None}
    unresolved = sorted(k for k, v in subjects.items() if v is None)

    assert unresolved == []
    assert len(resolved) == 50
    assert all("$" not in name for name in resolved.values())

    # The 8 that previously fell back to null -- pinned to their now-correctly-resolved names,
    # sourced by following the $token$ one hop to its own loc entry.
    assert resolved["giga_tech_repeatable_alderson_cap"] == "Alderson Disk"
    assert resolved["giga_tech_repeatable_asteroid_manufactory_cap"] == "Asteroid Industrial Site"
    assert resolved["giga_tech_repeatable_dyson_swarm_cap"] == "Dyson Swarm"
    assert resolved["giga_tech_repeatable_furnace_cap"] == "Arc Furnace"
    assert resolved["giga_tech_repeatable_observatory_cap"] == "Atmospheric Storm Observatory"
    assert resolved["giga_tech_repeatable_orbital_naval_logistics_cap"] == "Orbital Naval Logistics Office"
    assert resolved["giga_tech_repeatable_warmoon_cap"] == "Attack Moon"
    assert resolved["giga_tech_repeatable_warplanet_cap"] == "Behemoth Planetcraft"

    for key, entry in overlay["availability"].items():
        if key not in cap_keys:
            assert entry["configGatedSubject"] is None


# ---------------------------------------------------------------------------
# D-14 (spec/decisions.md): technology_swap per-profile substitution and variant listing.
# ---------------------------------------------------------------------------


def test_rendered_node_count_stays_977_regardless_of_technology_swap(ctx, base_dataset):
    """D-14 decision 1: a swap NEVER becomes its own node -- the rendered set is exactly 977
    (D-18: 980 -> 977) whether or not a technology carries a technology_swap, axis-expressible or
    not."""
    doc, _node_bytes, _edge_bytes = base_dataset
    assert len(doc["technologies"]) == 977
    assert len(ctx.rendered_keys) == 977


def test_swap_classification_split_uses_the_project_own_axis_facts(ctx):
    """Real corpus, using pipeline.availability.AXIS_FACTS (the SAME dict the trigger evaluator
    itself uses for `potential` blocks) as the axis-expressibility source of truth: 214 total
    swaps, 128 axis-expressible / 86 non-axis. This CORRECTS an earlier, narrower ad-hoc survey
    figure (126/88) that omitted is_mechanical_empire/is_robot_empire/is_regular_empire from its
    own axis-leaf set -- AXIS_FACTS already treats all three as resolvable to the authority axis
    (is_robot_empire per an established, already-audited approximation; see that module's own
    comment), and technology_swaps.collect_swaps reuses AXIS_FACTS directly rather than defining a
    second, competing classification that could silently disagree with it."""
    from pipeline.technology_swaps import collect_swaps

    total = axis = non_axis = 0
    for key in sorted(ctx.rendered_keys):
        for swap in collect_swaps(key, ctx.rendered_defs[key].block):
            total += 1
            if swap.axis_expressible:
                axis += 1
            else:
                non_axis += 1
    assert (total, axis, non_axis) == (214, 128, 86)


def test_axis_expressible_swap_substitutes_fission_power_for_bio_shipset_profile(ctx):
    """The prompt's own flagship example: tech_fission_power's bio-shipset swap must display
    'Fission Metabolism', not 'Fission Power', for a bio-shipset profile -- and must NOT appear at
    all for a mechanical-shipset profile. The swap's own loc entry is itself a `$token$`
    (`tech_bio_fission_power: "$BIO_FISSION_REACTOR$"`) rather than a literal string, exercising
    the same loc-token resolution `_config_gated_subject` needed earlier this session."""
    bio_profile = {"authority": "regular", "shipset": "biological", "nomadic": "no"}
    mech_profile = {"authority": "regular", "shipset": "mechanical", "nomadic": "no"}

    bio_overlay = build_empire_overlay(ctx, bio_profile)
    mech_overlay = build_empire_overlay(ctx, mech_profile)

    bio_entry = next(e for e in bio_overlay["swapMappings"] if e["technologyId"] == "tech_fission_power")
    assert bio_entry["name"] == "Fission Metabolism"
    assert bio_entry["area"] is None  # unchanged from base
    assert bio_entry["category"] is None

    assert not any(e["technologyId"] == "tech_fission_power" for e in mech_overlay["swapMappings"])


def test_non_axis_swap_never_substitutes_even_for_a_matching_profile(ctx):
    """D-14 decision 3 + the tech_ring_world exception confirmed in chat: a swap whose trigger
    mixes an axis leaf with a non-axis leaf (giga_can_use_habitables AND country_uses_bio_ships)
    is wholly non-axis, per NO special-casing. tech_ring_world must never appear in ANY profile's
    swapMappings -- it always keeps its own base name/area/category on the card."""
    bio_profile = {"authority": "regular", "shipset": "biological", "nomadic": "no"}
    for profile in ctx.profiles:
        overlay = build_empire_overlay(ctx, profile)
        assert not any(e["technologyId"] == "tech_ring_world" for e in overlay["swapMappings"])


def test_non_axis_swaps_appear_as_variants_in_the_detail_payload(ctx):
    """tech_ring_world's 3 non-axis swaps must be listed in its detail payload's `variants`,
    each with a resolved name, an icon, and a describe_condition-rendered conditionText."""
    payload = build_detail_payload(ctx, "tech_ring_world")
    assert len(payload["variants"]) == 3
    names = {v["name"] for v in payload["variants"]}
    assert names == {
        "Ring World Construction",
        "Large Scale Self Replicating Deconstruction Swarms",
        "Artificial Deconstructor Ecologies",
    }
    for variant in payload["variants"]:
        assert variant["conditionText"]  # never blank
        assert variant["icon"]["sheet"]


def test_axis_expressible_swap_has_no_variants_entry(ctx):
    """tech_fission_power's only swap is axis-expressible -- it substitutes, it never appears in
    the popup's variants list (that list is exclusively for non-axis swaps)."""
    payload = build_detail_payload(ctx, "tech_fission_power")
    assert payload["variants"] == []


def test_swap_icon_inheritance_diagnostic_fires_only_for_the_one_real_case(ctx):
    """Item 6 (chat): giga_tech_ring_world_swap_no_habitables has `inherit_icon = no` and no icon
    file of its own -- pipeline/icons/resolve.py correctly leaves it unresolved (never redirected
    at that layer), and pipeline.dataset_emit's presentation layer falls back to the OWNER's icon
    for display, tracked here. Must be exactly this one real case -- and must NOT include any of
    the 87 swaps that legitimately keep the base icon via inherit_icon defaulting to yes (those
    are never unresolved candidates in the first place, so they can't appear here)."""
    diagnostics = build_diagnostics(ctx)
    validate_diagnostics(diagnostics)
    assert diagnostics["swapsRenderingOnInheritedIcon"] == [
        {"technologyId": "tech_ring_world", "swapKey": "giga_tech_ring_world_swap_no_habitables"}
    ]

    payload = build_detail_payload(ctx, "tech_ring_world")
    inherited_variant = next(
        v for v in payload["variants"]
        if v["name"] == "Large Scale Self Replicating Deconstruction Swarms"
    )
    assert inherited_variant["icon"] == ctx.icon_refs["tech_ring_world"]


def test_swap_substitution_and_variant_node_coverage(ctx):
    """Real corpus figures: how many of the 980 rendered nodes carry per-profile substitution
    (>=1 axis-expressible swap), how many carry variants (>=1 non-axis swap), and how many carry
    both. 123 + 72 - 10 = 185, matching the survey's 185-technology swap-bearing count exactly."""
    from pipeline.technology_swaps import collect_swaps

    substitution_nodes = set()
    variant_nodes = set()
    for key in sorted(ctx.rendered_keys):
        swaps = collect_swaps(key, ctx.rendered_defs[key].block)
        if any(s.axis_expressible for s in swaps):
            substitution_nodes.add(key)
        if any(not s.axis_expressible for s in swaps):
            variant_nodes.add(key)

    assert len(substitution_nodes) == 123
    assert len(variant_nodes) == 72
    assert len(substitution_nodes & variant_nodes) == 10
    assert len(substitution_nodes | variant_nodes) == 185


def test_swap_payload_delta_against_base_dataset(ctx, base_dataset):
    """Real measured payload delta for D-14's substitution/variant data, reported rather than
    assumed from the pre-implementation ~9.7 KB gz worst-case estimate. The base dataset itself
    (P-10's ≤2 MB budget) is UNCHANGED -- swapMappings/variants live in the per-profile overlay
    and per-technology detail-payload artefacts, both lazy/excluded from that budget."""
    import copy

    from pipeline.dataset_schema.empire_profile import all_profiles_in_canonical_order

    doc, node_bytes, edge_bytes = base_dataset
    base_gz = _gz(json.dumps(doc).encode()) + _gz(node_bytes) + _gz(edge_bytes)
    assert base_gz < 100_000  # unchanged from the pre-existing budget assertion; swaps add 0 here

    profiles = all_profiles_in_canonical_order()
    overlays = [build_empire_overlay(ctx, p) for p in profiles]
    with_swaps_gz = _gz(json.dumps(overlays).encode())
    stripped = copy.deepcopy(overlays)
    for o in stripped:
        o["swapMappings"] = []
    without_swaps_gz = _gz(json.dumps(stripped).encode())
    overlay_delta_gz = with_swaps_gz - without_swaps_gz

    payloads = {key: build_detail_payload(ctx, key) for key in sorted(ctx.rendered_keys)}
    with_variants_gz = _gz(json.dumps(payloads).encode())
    stripped_payloads = copy.deepcopy(payloads)
    for p in stripped_payloads.values():
        p["variants"] = []
    without_variants_gz = _gz(json.dumps(stripped_payloads).encode())
    payload_delta_gz = with_variants_gz - without_variants_gz

    print(f"\nswapMappings delta across all 12 overlays: {overlay_delta_gz:,} bytes gz")
    print(f"variants delta across all 980 detail payloads: {payload_delta_gz:,} bytes gz")

    # Real figures, locked in so a future change that materially grows either is visible here.
    # Comfortably small relative to the ~64-67 KB base-dataset reference point, and irrelevant to
    # P-10's budget regardless since neither artefact counts against it.
    assert overlay_delta_gz < 25_000
    assert payload_delta_gz < 5_000


# ---------------------------------------------------------------------------
# Vendoring automation: reduced-corpus (ACOT/AoT-absent) build diagnostics.
# spec/decisions.md's vendoring-automation investigation.
# ---------------------------------------------------------------------------


def test_full_corpus_reports_all_four_sources_and_no_reduced_corpus_diagnostics(ctx):
    """The real, full build (all four sources present) must report all four in
    vendorSourcesLoaded and both reduced-corpus diagnostic lists empty -- these only fire when
    ACOT and/or AoT is genuinely missing."""
    diagnostics = build_diagnostics(ctx)
    validate_diagnostics(diagnostics)
    assert diagnostics["vendorSourcesLoaded"] == ["Vanilla", "Gigastructural Engineering", "ACOT", "AoT"]
    assert diagnostics["placeholderTechnologiesAbsent"] == []
    assert diagnostics["vanillaTechnologiesRevertedFromAcotOverwrite"] == []


def test_placeholder_technologies_constant_matches_full_corpus(ctx):
    """PLACEHOLDER_TECHNOLOGIES_REQUIRING_ACOT_AOT is a maintained constant (can't be derived
    from a reduced corpus -- that's the point) -- this regression guard re-verifies it against
    the real, full corpus so a future re-vendor that adds/removes/reassigns one of these 4 fails
    a test rather than silently going stale. D-18 (spec/decisions.md, this session): narrowed
    from 7 to 4 -- the 3 dropped entries are no longer rendered under the depth-1 ACOT/AoT closure
    regardless of whether ACOT/AoT is loaded, so they're no longer a "placeholder absent without
    ACOT/AoT" case at all (see the constant's own docstring in pipeline/dataset_emit.py)."""
    from pipeline.dataset_emit import PLACEHOLDER_TECHNOLOGIES_REQUIRING_ACOT_AOT

    assert len(PLACEHOLDER_TECHNOLOGIES_REQUIRING_ACOT_AOT) == 4
    for key, mod in PLACEHOLDER_TECHNOLOGIES_REQUIRING_ACOT_AOT.items():
        assert key in ctx.rendered_keys, key
        defn = ctx.rendered_defs[key]
        assert defn.source == mod, f"{key}: expected source {mod}, got {defn.source}"


def test_off_tree_prerequisite_names_surface_on_the_three_affected_detail_payloads(ctx):
    """Item 3 (reconciliation session 3): D-18's accepted 3-link cost was flagged as unsurfaced
    (spec/P-16-mod-requirements.md's acceptance criteria) -- now resolved into each affected
    technology's own detail payload, by localised name, real corpus values pinned directly (not
    just "non-empty")."""
    ae = build_detail_payload(ctx, "tech_dark_matter_power_core_ae")
    assert ae["offTreePrerequisiteNames"] == ["Precursor Databank Analysis"]

    dm = build_detail_payload(ctx, "tech_dark_matter_power_core_dm")
    assert dm["offTreePrerequisiteNames"] == ["Enhanced Zero Point Reactor", "Dark Energy Drawing"]

    # The other two D-18 closure members carry no off-tree prerequisite at all.
    se = build_detail_payload(ctx, "tech_dark_matter_power_core_se")
    assert se["offTreePrerequisiteNames"] == []
    phanon = build_detail_payload(ctx, "tech_civil_phanon_application")
    assert phanon["offTreePrerequisiteNames"] == []

    # Every OTHER rendered technology (974/977) has an empty list -- the field is real data, not
    # a fixed stub, and its non-emptiness is confined to exactly the D-18 accepted-cost set.
    non_empty = {
        key for key in ctx.rendered_keys
        if build_detail_payload(ctx, key)["offTreePrerequisiteNames"]
    }
    assert non_empty == {"tech_dark_matter_power_core_ae", "tech_dark_matter_power_core_dm"}


def test_description_literal_backslash_n_is_unescaped_to_a_real_newline(ctx):
    """Reconciliation session 3: found by reviewing a real detail-popup screenshot -- description
    was never actually DISPLAYED anywhere before the popup slice existed, so a literal two-char
    `\\n` escape sequence (Stellaris's own loc-format convention for a line break, confirmed
    directly against `tech_dark_matter_power_core_ae_desc`'s raw YAML value) went unnoticed.
    `strip_markup` only strips `§`/`£` markup, never touched this. Real corpus: 25 rendered
    technologies' descriptions carried this before the fix; 0 after."""
    ae = build_detail_payload(ctx, "tech_dark_matter_power_core_ae")
    assert "\\n" not in ae["description"]
    assert "\n\n" in ae["description"]  # the real double-line-break the raw source actually wants

    affected = [
        key for key in ctx.rendered_keys
        if "\\n" in build_detail_payload(ctx, key)["description"]
    ]
    assert affected == []


def test_vanilla_technologies_acot_overwrites_constant_matches_full_corpus(ctx):
    """VANILLA_TECHNOLOGIES_ACOT_OVERWRITES is likewise a maintained constant, re-verified here:
    each key must actually be an ACOT overwrite of a vanilla definition in the real corpus. All 4
    are, perhaps surprisingly, NOT themselves in the full build's rendered_keys at all -- their
    ACOT-overwritten form falls outside the P-16 rendering-scope closure (confirmed here, not
    assumed); `ctx.overwrite_records` still carries the overwrite relationship for every parsed
    technology, rendered or not, which is what this constant actually needs to be true against."""
    from pipeline.dataset_emit import VANILLA_TECHNOLOGIES_ACOT_OVERWRITES

    assert len(VANILLA_TECHNOLOGIES_ACOT_OVERWRITES) == 4
    for key in VANILLA_TECHNOLOGIES_ACOT_OVERWRITES:
        assert key not in ctx.rendered_keys, f"{key}: expected NOT rendered in the full (ACOT-overwritten) build"
        record = ctx.overwrite_records.get(key)
        assert record is not None and record.overwrites is not None, f"{key}: expected an overwrite record"
        assert record.defined_by == "ACOT", f"{key}: expected ACOT to be the winning source, got {record.defined_by}"
        assert record.overwrites == "Vanilla", f"{key}: expected ACOT to overwrite Vanilla, got {record.overwrites}"


@pytest.fixture(scope="module")
def vendor_without_acot_aot(tmp_path_factory):
    """A vendor/ view with Vanilla + Gigastructural Engineering only, built via symlinks so the
    real ~3.6 GB vendor/ is never copied or modified -- ACOT/AoT are simply absent, the same
    real-world shape a contributor without a Workshop subscription to those two mods would have."""
    root = tmp_path_factory.mktemp("vendor_no_acot_aot")
    (root / "mods").mkdir()
    (root / "stellaris").symlink_to(VENDOR_ROOT / "stellaris")
    (root / "mods" / "gigastructures").symlink_to(VENDOR_ROOT / "mods" / "gigastructures")
    return root


def test_reduced_corpus_build_is_977_nodes_not_a_naive_973(vendor_without_acot_aot):
    """The headline finding from the vendoring-automation investigation, re-verified as a
    regression test rather than left as a one-off manual measurement: pre-D-18, 980 - 7 + 4 = 977,
    not 980 - 7 = 973. D-18 (spec/decisions.md, this session): the full-build rendered count moved
    980 -> 977 for an UNRELATED reason (the depth-1 ACOT/AoT closure), and PLACEHOLDER_
    TECHNOLOGIES_REQUIRING_ACOT_AOT narrowed 7 -> 4 members (only the depth-1 ones can still be
    ABSENT when ACOT/AoT is missing -- the 3 dropped ones are never rendered regardless). Re-run
    against the real corpus, this reduced-build figure remains 977 -- confirmed empirically, not
    assumed from the arithmetic (977 - 4 + 4 = 977 is a genuine coincidence of these particular
    numbers, not a reason the two builds should always match)."""
    ctx = build_context(vendor_without_acot_aot)
    assert len(ctx.rendered_keys) == 977
    assert ctx.sources_present == ["Vanilla", "Gigastructural Engineering"]

    doc, _node_bytes, _edge_bytes = build_base_dataset(ctx)
    validate_base_dataset(doc)
    ids = {t["id"] for t in doc["technologies"]}
    dangling = [e for e in doc["edges"] if e["from"] not in ids or e["to"] not in ids]
    assert dangling == []


def test_reduced_corpus_diagnostics_fire_loudly_and_accurately(vendor_without_acot_aot):
    from pipeline.dataset_emit import (
        PLACEHOLDER_TECHNOLOGIES_REQUIRING_ACOT_AOT,
        VANILLA_TECHNOLOGIES_ACOT_OVERWRITES,
    )

    ctx = build_context(vendor_without_acot_aot)
    diagnostics = build_diagnostics(ctx)
    validate_diagnostics(diagnostics)

    assert diagnostics["vendorSourcesLoaded"] == ["Vanilla", "Gigastructural Engineering"]

    absent = {e["technologyId"]: e["requiresMod"] for e in diagnostics["placeholderTechnologiesAbsent"]}
    assert absent == PLACEHOLDER_TECHNOLOGIES_REQUIRING_ACOT_AOT
    for key in absent:
        assert key not in ctx.rendered_keys  # genuinely absent, not just flagged

    reverted = {
        e["technologyId"]: e["contentDiffersFromOverwrite"]
        for e in diagnostics["vanillaTechnologiesRevertedFromAcotOverwrite"]
    }
    assert reverted == VANILLA_TECHNOLOGIES_ACOT_OVERWRITES
    for key in reverted:
        assert key in ctx.rendered_keys  # genuinely reappeared, not just flagged
        assert ctx.rendered_defs[key].source == "Vanilla"
