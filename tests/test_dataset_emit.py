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


def test_base_dataset_covers_all_980_rendered_technologies(ctx, base_dataset):
    doc, _node_bytes, _edge_bytes = base_dataset
    assert len(doc["technologies"]) == 980
    assert {t["id"] for t in doc["technologies"]} == ctx.rendered_keys


def test_base_dataset_edge_count_matches_p14_survey(base_dataset):
    doc, _node_bytes, _edge_bytes = base_dataset
    assert len(doc["edges"]) == 989
    from collections import Counter

    assert dict(Counter(e["kind"] for e in doc["edges"])) == {
        "prerequisite": 888, "alternative": 76, "potential-gate": 25,
    }


def test_base_dataset_band_and_lane_shape(base_dataset):
    doc, _node_bytes, _edge_bytes = base_dataset
    assert len(doc["tierBands"]) == 11
    assert doc["tierBands"][-1]["tier"] == "repeatables"
    assert [lane["id"] for lane in doc["lanes"]] == [
        "Standard", "Aeternum", "Blokkats", "Compound", "Sirenalia", "Katzenartig Imperium",
    ]


def test_cost_per_level_carried_exactly_on_the_88_repeatables(base_dataset):
    """Item 2: cost_per_level must be a secondary card indicator alongside the primary `cost`
    field (spec/P-02-layout.md), never a stand-in replacement for it. Real corpus: exactly the
    88-node repeatable set carries a resolvable costPerLevel; 0 non-repeatable technologies do."""
    doc, _node_bytes, _edge_bytes = base_dataset
    with_cost_per_level = [t["id"] for t in doc["technologies"] if t["repeatable"] and t["repeatable"]["costPerLevel"] is not None]
    assert len(with_cost_per_level) == 88
    non_repeatable_with_repeatable_field = [t for t in doc["technologies"] if t["repeatable"] is None]
    assert len(non_repeatable_with_repeatable_field) == 980 - 88

    sample = next(t for t in doc["technologies"] if t["id"] == "tech_repeatable_reduced_building_cost")
    assert sample["cost"] == pytest.approx(50000.0)
    assert sample["repeatable"] == {"levels": 5, "costPerLevel": pytest.approx(5000.0)}


def test_cost_field_present_for_every_technology_null_only_when_unresolvable(base_dataset):
    """Real corpus: 15/980 technologies have a null cost -- 5 with no `cost` field at all
    (apparently-free starting technologies) and 10 vanilla 'cosmic storm' technologies whose
    `cost` is a dynamic modifier block (`cost = { factor = @var inline_script = {...} }`), not a
    scalar. Neither is guessed at or defaulted to 0 -- see schema/base-dataset.schema.json's
    `cost` field description."""
    doc, _node_bytes, _edge_bytes = base_dataset
    null_cost_ids = {t["id"] for t in doc["technologies"] if t["cost"] is None}
    assert len(null_cost_ids) == 15
    assert {"tech_missiles_1", "tech_flak_batteries_1", "tech_solar_panel_network"} <= null_cost_ids
    assert {"tech_ship_storm_weapons_1", "tech_ship_storm_weapons_2"} <= null_cost_ids

    resolved_costs = [t["cost"] for t in doc["technologies"] if t["cost"] is not None]
    assert len(resolved_costs) == 980 - 15
    assert all(c >= 0 for c in resolved_costs)


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
        assert len(overlay["availability"]) == 980
        assert len(overlay["researchPaths"]) == 980


def test_availability_matrix_agrees_with_overlays(ctx, base_dataset):
    from pipeline.dataset_schema.empire_profile import all_profiles_in_canonical_order

    doc, _node_bytes, _edge_bytes = base_dataset
    overlays = [build_empire_overlay(ctx, p) for p in all_profiles_in_canonical_order()]
    check_availability_matrix_matches_overlays(doc["technologies"], overlays)  # raises if mismatched


@pytest.fixture(scope="module")
def all_detail_payloads(ctx):
    return {key: build_detail_payload(ctx, key) for key in sorted(ctx.rendered_keys)}


def test_all_980_detail_payloads_validate(all_detail_payloads):
    assert len(all_detail_payloads) == 980
    for payload in all_detail_payloads.values():
        validate_detail_payload(payload)


def test_search_index_covers_all_technologies_and_validates(ctx, base_dataset, all_detail_payloads):
    doc, _node_bytes, _edge_bytes = base_dataset
    index = build_search_index(ctx, doc, all_detail_payloads)
    validate_search_index(index)
    assert len(index["entries"]) == 980
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
    assert worst == pytest.approx(0.033673, abs=1e-5)  # matches the previously-published 3.37%, unaffected

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


def test_rendered_node_count_stays_980_regardless_of_technology_swap(ctx, base_dataset):
    """D-14 decision 1: a swap NEVER becomes its own node -- the rendered set is exactly 980
    whether or not a technology carries a technology_swap, axis-expressible or not."""
    doc, _node_bytes, _edge_bytes = base_dataset
    assert len(doc["technologies"]) == 980
    assert len(ctx.rendered_keys) == 980


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
    the real, full corpus so a future re-vendor that adds/removes/reassigns one of these 7 fails
    a test rather than silently going stale."""
    from pipeline.dataset_emit import PLACEHOLDER_TECHNOLOGIES_REQUIRING_ACOT_AOT

    assert len(PLACEHOLDER_TECHNOLOGIES_REQUIRING_ACOT_AOT) == 7
    for key, mod in PLACEHOLDER_TECHNOLOGIES_REQUIRING_ACOT_AOT.items():
        assert key in ctx.rendered_keys, key
        defn = ctx.rendered_defs[key]
        assert defn.source == mod, f"{key}: expected source {mod}, got {defn.source}"


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
    regression test rather than left as a one-off manual measurement: 980 - 7 + 4 = 977, not
    980 - 7 = 973. No crash, no dangling edges."""
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
