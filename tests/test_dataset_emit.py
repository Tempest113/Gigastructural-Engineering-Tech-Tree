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


def test_base_dataset_covers_all_973_rendered_technologies(ctx, base_dataset):
    # D-18 (spec/decisions.md): 980 -> 977, the depth-1 ACOT/AoT closure.
    # Item 2c (user domain call, later session): 977 -> 973 -- 4 permanently-disabled
    # (`potential = { always = no }`) technologies excluded entirely.
    doc, _node_bytes, _edge_bytes = base_dataset
    assert len(doc["technologies"]) == 973
    assert {t["id"] for t in doc["technologies"]} == ctx.rendered_keys


def test_base_dataset_edge_count_matches_p14_survey(base_dataset):
    # D-18 (spec/decisions.md): 989 -> 984 -- the depth-1 ACOT/AoT closure drops 3 technologies,
    # removing 5 `prerequisite` edges that touched them; alternative/potential-gate unaffected.
    # Item 2c (later session): 984 -> 977 -- excluding the 4 permanently-disabled technologies
    # drops 7 more `prerequisite` edges (their own outgoing prerequisite references); nothing else
    # referenced them as a prerequisite, so alternative/potential-gate stay unaffected again.
    doc, _node_bytes, _edge_bytes = base_dataset
    assert len(doc["edges"]) == 977
    from collections import Counter

    assert dict(Counter(e["kind"] for e in doc["edges"])) == {
        "prerequisite": 876, "alternative": 76, "potential-gate": 25,
    }


def test_base_dataset_gates_match_the_gate_classification_survey(base_dataset):
    """P-3 (gate-classification session): real per-mechanism counts, pinned so a future corpus
    change is caught rather than silently drifting. 45 ascension_perk-kind gate instances (22
    has_ascension_perk + 9 has_gigastructural_constructs + 14 has_galactic_wonders), unaffected by
    Item 5 or the "path to zero uncertain" follow-up.

    **"path to zero uncertain" follow-up, Item 3 (ethics/civic/origin display gates) added two
    NEW kinds** -- 45 origin-kind and 24 ethics_or_civic-kind instances, real, measured, not
    estimated (see `pipeline.gate_patterns`' own registry comment for which leaf keys feed each).
    technology-kind gate instances: 25 raw `has_technology`-in-`potential` occurrences (== the 25
    potential-gate edges, one-to-one) plus 1 new `can_research_technology` occurrence (Item 3's
    engine-builtin alias -- NOT part of P-14's `potential-gate` edge extraction, which only ever
    looked for the literal `has_technology` key; extending edge extraction to cover
    `can_research_technology` too is out of this item's scope and not done here), minus 4 excluded
    by Item 5 (`giga_tech_amb_supertensiles_acot_alpha/sigma/phanon` and
    `giga_tech_arkship_neutronium_harvester`, each redundantly encoding the same dependency as
    BOTH a true `prerequisites` entry AND a `has_technology` check in `potential` -- CLAUDE.md's
    documented "4 real pairs are both a formal prerequisite and a potential-gate"; displaying the
    latter duplicated the former, already shown via the edge/popup) = 22 technology-kind gates.

    45 + 45 + 24 + 22 = 136 DIRECT total, over 109 technologies, 24 of which carry more than one
    directly-declared gate instance.

    **Two later sessions moved the DIRECT figures again, and added an INHERITED layer on top --
    both counted separately below, never conflated.**

    Item 4a ("Ring Segment / ascension-perk locking / gate-propagation" session): `on_enabled ->
    add_research_option` grants are now themselves a gate source. `ap_galactic_wonders`'s
    (Gigastructures-overwritten) `on_enabled` unconditionally grants `tech_ring_world`,
    `tech_dyson_sphere` and `tech_matter_decompressor` -- all three structurally UNREACHABLE any
    other way (unconditional zero weight) and previously invisible to gate detection entirely, so
    all three are NEW direct ascension_perk gates. `tech_mega_engineering` is ALSO granted this way
    but stays genuinely reachable by the ordinary weighted-draw route too, so it deliberately does
    NOT get one (see `pipeline.dataset_emit.ADD_RESEARCH_OPTION_PERK_GRANTS`'s own comment). Real
    corpus: DIRECT ascension_perk 45 -> 48, DIRECT total 136 -> 139, directly-gated technologies
    109 -> 112.

    Item 3 (the SAME session): gates now PROPAGATE down `prerequisite` edges -- a technology whose
    only real path to a requirement is "research my prerequisite first, and THAT tech needs the
    perk" now inherits it, tagged `inherited: true`/`sourceTechnologyId: <declaring tech>` (user
    report: the QSO family, `giga_tech_repeatable_*_cap` "Management Protocols"). This is INSTEAD
    OF the direct-only figures above for the FULL emitted `gates` field -- real corpus: 267 total
    gate instances (104 ascension_perk + 53 origin + 61 ethics_or_civic + 49 technology) over 196
    gated technologies, 48 of which carry more than one gate instance (direct + inherited
    combined). The DIRECT-only figures (139/112, still separately meaningful -- e.g. for
    reconstructing "which technology's own `potential`/perk-grant is the true source") remain
    exactly as the paragraph above states and are asserted separately below."""
    from collections import Counter

    doc, _node_bytes, _edge_bytes = base_dataset
    gated = [t for t in doc["technologies"] if t["gates"]]
    all_gates = [g for t in doc["technologies"] for g in t["gates"]]
    assert len(all_gates) == 267
    assert dict(Counter(g["kind"] for g in all_gates)) == {
        "ascension_perk": 104, "origin": 53, "ethics_or_civic": 61, "technology": 49,
    }
    assert len(gated) == 196
    assert sum(1 for t in gated if len(t["gates"]) > 1) == 48

    direct_gates = [g for t in doc["technologies"] for g in t["gates"] if not g["inherited"]]
    directly_gated = [t for t in doc["technologies"] if any(not g["inherited"] for g in t["gates"])]
    assert len(direct_gates) == 139
    assert dict(Counter(g["kind"] for g in direct_gates)) == {
        "ascension_perk": 48, "origin": 45, "ethics_or_civic": 24, "technology": 22,
    }
    assert len(directly_gated) == 112

    for key in [
        "giga_tech_amb_supertensiles_acot_alpha", "giga_tech_amb_supertensiles_acot_sigma",
        "giga_tech_amb_supertensiles_acot_delta", "giga_tech_amb_supertensiles_acot_phanon",
        "giga_tech_arkship_neutronium_harvester",
    ]:
        tech = next(t for t in doc["technologies"] if t["id"] == key)
        assert tech["gates"] == []

    # Every "has_technology"-sourced DIRECT gate instance is one of the 25 potential-gate edges
    # (still 25 -- Item 5 only filters the CARD-DISPLAY gate list, never the edge extraction
    # itself), but no longer a 1:1 match: the 4 excluded gate instances are a strict subset of the
    # edges, PLUS one extra pair from `can_research_technology` (a distinct engine trigger P-14's
    # edge extraction was never scoped to cover), so the two sets are no longer strictly nested
    # either direction -- asserted precisely below rather than as a subset relationship. Restricted
    # to DIRECT gates -- an INHERITED technology-kind gate is a different (ancestor, descendant)
    # pair than any potential-gate edge, by construction, so including inherited entries here
    # would just be noise against this specific direct-edge correspondence check.
    potential_gate_pairs = {(e["from"], e["to"]) for e in doc["edges"] if e["kind"] == "potential-gate"}
    assert len(potential_gate_pairs) == 25
    gate_tech_pairs = {
        (g["refId"], t["id"])
        for t in doc["technologies"] for g in t["gates"]
        if g["kind"] == "technology" and not g["inherited"]
    }
    assert len(gate_tech_pairs) == 22
    assert gate_tech_pairs - potential_gate_pairs == {("tech_genome_mapping", "tech_alien_cloning")}
    # 4 real exclusions, not the 4 amb_supertensiles technologies as originally assumed --
    # `giga_tech_amb_supertensiles_acot_delta`'s own `potential` has no `has_technology` leaf at
    # all (only `has_acot`/`has_global_flag`), so it was never a potential-gate owner to begin
    # with; only alpha/sigma/phanon are. The 4th real exclusion is the OTHER known dual-encoded
    # pair (CLAUDE.md's edge-typing example): `tech_mega_engineering ->
    # giga_tech_arkship_neutronium_harvester`, unrelated to the ACOT/AoT tensile family but the
    # same underlying redundant-encoding shape.
    assert potential_gate_pairs - gate_tech_pairs == {
        ("tech_dark_matter_power_core_ae", "giga_tech_amb_supertensiles_acot_alpha"),
        ("tech_dark_matter_power_core_se", "giga_tech_amb_supertensiles_acot_sigma"),
        ("tech_civil_phanon_application", "giga_tech_amb_supertensiles_acot_phanon"),
        ("tech_mega_engineering", "giga_tech_arkship_neutronium_harvester"),
    }

    vat = next(t for t in doc["technologies"] if t["id"] == "giga_tech_the_vat")
    assert [g["kind"] for g in vat["gates"]] == ["ascension_perk", "ascension_perk"]
    assert {g["refId"] for g in vat["gates"]} == {"ap_galactic_wonders", "ap_mechromancy"}
    # Item 4 ("path to zero uncertain" follow-up): real corpus finding, not limited to
    # technology-kind gates -- giga_tech_the_vat's own potential has has_galactic_wonders at the
    # AND top level (unconditional) but ap_mechromancy inside a genuine OR alongside
    # has_genetically_ascended/has_active_tradition ("robots go brrt" -- an alternative path, not
    # a strict requirement). The fix generalises correctly across gate kinds.
    for g in vat["gates"]:
        if g["refId"] == "ap_galactic_wonders":
            assert g["alternative"] is False
            assert g["label"] == "Needs Galactic Wonders"
        else:
            assert g["refId"] == "ap_mechromancy"
            assert g["alternative"] is True
            assert g["label"] == "or: Mechromancy"
        assert g["icon"]["width"] > 1  # not the degenerate 1x1 placeholder


def test_riddle_escort_gate_is_an_alternative_constrained_to_biological_shipset(base_dataset):
    """Item 4 ("path to zero uncertain" follow-up): the exact real bug the user reported --
    tech_torpedoes_1 displayed 'Needs Riddle Escort' (tech_cosmogenesis_escort) as an
    unconditional requirement, when it's really one of FOUR independent OR branches in the real
    potential block (country_uses_bio_ships=no OR has_tradition=tr_nanotech_4 OR
    has_crisis_level=crisis_level_2 OR has_technology=tech_cosmogenesis_escort) -- non-bio-ship
    empires (8/12 profiles) already qualify via the first branch alone, unrelated to this gate.
    tech_missiles_1 shares the exact same shape. Both must render as an alternative, both must
    carry the real per-axis constraint (pipeline.edge_constraints already computes
    shipset=[biological] for this exact edge -- reused here, not recomputed)."""
    doc, _node_bytes, _edge_bytes = base_dataset
    for key in ("tech_torpedoes_1", "tech_missiles_1"):
        tech = next(t for t in doc["technologies"] if t["id"] == key)
        assert len(tech["gates"]) == 1
        gate = tech["gates"][0]
        assert gate["refId"] == "tech_cosmogenesis_escort"
        assert gate["kind"] == "technology"
        assert gate["alternative"] is True
        assert gate["label"] == "or: Riddle Escort"  # never "Needs Riddle Escort" -- not unconditional
        assert gate["appliesToEmpireTypes"] == {"shipset": ["biological"]}


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
    govern, per CLAUDE.md's "Trigger evaluation" section. Was 33/977 (3.37%); Item 2's four
    resolution rules (later session -- DLC-check/progression-flag/mod-requirement resolution plus
    the always-no exclusion shrinking the denominator) moved this to 28/973 (2.88%). A later
    session's has_ancrel fix (the "path to zero uncertain" follow-up's Item 1 -- has_ancrel is a
    DLC-ownership check, not a story-progression flag, see CLAUDE.md's "Availability evaluator"
    defect-class writeup) moved this again to 27/973 (2.77%).

    **27 -> 34, the SAME session's Item 2 (`pipeline.scripted_triggers`' general expansion) -- a
    real, measured, and NOT a straightforward improvement.** Recursively expanding a technology's
    `potential` block against real scripted-trigger bodies (`giga_can_use_habitables`,
    `is_wilderness_empire`, ...) lets Kleene short-circuiting resolve some profiles where it
    couldn't before -- but the profiles it resolves are typically the ones an axis fact ALREADY
    ruled out (e.g. `is_wilderness_empire` requires hive authority, so 8/12 non-hive profiles now
    resolve LOCKED where they used to be UNCERTAIN), while the REMAINING axis-consistent profiles
    (hive-mind ones, for that example) stay genuinely UNCERTAIN on the real, still-unresolvable
    origin question. The net effect: `unconditionalUncertainty` genuinely improves (183 -> 176,
    7 technologies moved from "uncertain for everyone" to "uncertain only for the profiles that
    actually could have it"), but those SAME 7 (plus others) move INTO the profile-dependent
    bucket instead of staying unconditional, so the worst profile-dependent rate rises even though
    total uncertainty and information quality both improved. This is a considered, reported
    tradeoff, not a regression to hide -- see CLAUDE.md's "Availability evaluator" section for the
    full writeup and the specific 3%-warn-threshold consequence.

    **34 -> 15, the SAME session's Item 3 (ethics/civic/origin as display gates).** Once
    `is_wilderness_empire`'s own inner `has_origin` leaf (and 18 more ethics/civic/origin leaves)
    are ALSO excluded from availability the same way ascension perks already are, the hive-mind
    profiles that Item 2 alone left genuinely uncertain resolve too -- there's no real origin
    question left for availability to answer once origin itself is a display gate, not a profile
    fact. Real, dramatic drop: 34 -> 15, comfortably back under the 3% warn threshold (~1.54%)."""
    doc, _node_bytes, _edge_bytes = base_dataset
    per_profile_uncertain_counts = [
        sum(1 for t in doc["technologies"] if t["availabilityMatrix"][index] == "uncertain")
        for index in range(len(ctx.profiles))
    ]
    unconditional = sum(
        1 for t in doc["technologies"] if all(state == "uncertain" for state in t["availabilityMatrix"])
    )
    worst_profile_dependent = max(per_profile_uncertain_counts) - unconditional
    # 15 -> 16, a later session (Items 1, 2, 5: `always`, ascension-perk axis-locking, and
    # `has_active_tradition` leaf handling). Each fix resolves technologies that used to be
    # UNCONDITIONALLY uncertain into either AVAILABLE-for-everyone or genuinely profile-dependent
    # (LOCKED for some, AVAILABLE for others) -- net effect across all three: unconditional
    # uncertainty falls 34 -> 31 (see test_real_rates_against_projections's own writeup) while the
    # worst profile-dependent count rises by exactly one, still comfortably under the 3% warn
    # threshold (~1.64%, not the 3% ceiling).
    assert worst_profile_dependent == 16
    assert round(worst_profile_dependent / len(doc["technologies"]), 4) == 0.0164  # 16/973


def test_edge_constraints_leave_d10_uncertainty_unchanged(ctx, base_dataset):
    """Item 1's own requirement, mirroring the gate-classification test above:
    `pipeline.edge_constraints` never imports or calls into `pipeline.availability`'s real
    evaluation path (`evaluate_technology_for_profiles`) -- assert this rather than assume it, the
    same discipline the gate-classification session already established."""
    doc, _node_bytes, _edge_bytes = base_dataset
    per_profile_uncertain_counts = [
        sum(1 for t in doc["technologies"] if t["availabilityMatrix"][index] == "uncertain")
        for index in range(len(ctx.profiles))
    ]
    unconditional = sum(
        1 for t in doc["technologies"] if all(state == "uncertain" for state in t["availabilityMatrix"])
    )
    worst_profile_dependent = max(per_profile_uncertain_counts) - unconditional
    assert worst_profile_dependent == 16  # 15 -> 16, see test_gate_classification_leaves_d10_uncertainty_unchanged


def test_active_edge_ids_are_not_identical_across_all_twelve_profiles(ctx):
    """The exact regression this session found and fixed: `activeEdgeIds` shipped as a true no-op
    (every edge index, identically, for all twelve profiles) across many sessions, undetected,
    because the fallback (every edge active) happens to look correct. Fails loudly if this
    recurs -- e.g. a future edit that reverts `build_empire_overlay`'s `active_edge_ids` back to
    `list(range(len(ctx.layout.edges)))`."""
    overlays = [build_empire_overlay(ctx, p) for p in ctx.profiles]
    edge_id_sets = [frozenset(ov["activeEdgeIds"]) for ov in overlays]
    assert len(set(edge_id_sets)) > 1, "activeEdgeIds is identical across all 12 profiles -- the no-op defect has recurred"


def test_active_edge_ids_real_per_profile_counts(ctx):
    """Pins the real, corpus-measured per-profile active edge counts (977 total edges -- Item 2c,
    later session, dropped the total from 984 by excluding 4 permanently-disabled technologies
    and their 7 own prerequisite edges) so a corpus refresh that silently changes this is caught,
    not silently accepted. See `pipeline.edge_constraints`'s module docstring for the 5 real
    constrained edges this reflects: `nomadic` (2 edges), `shipset` (2 edges), and one two-axis
    (`authority` + `shipset`) intersection -- unaffected in COUNT by Item 2c (none of the 5
    constrained edges touched an excluded technology), just shifted down by the same flat -7."""
    overlays = {
        (p["authority"], p["shipset"], p["nomadic"]): build_empire_overlay(ctx, p) for p in ctx.profiles
    }
    counts = {key: len(ov["activeEdgeIds"]) for key, ov in overlays.items()}
    assert counts[("regular", "mechanical", "no")] == 973
    assert counts[("regular", "mechanical", "yes")] == 973
    assert counts[("regular", "biological", "no")] == 976
    assert counts[("regular", "biological", "yes")] == 976
    assert counts[("hive_mind", "mechanical", "no")] == 973
    assert counts[("hive_mind", "biological", "no")] == 976
    assert counts[("machine_intelligence", "mechanical", "no")] == 973
    assert counts[("machine_intelligence", "biological", "no")] == 975


def test_disco_moon_gate_edges_are_active_for_every_profile(ctx, base_dataset):
    """The specific case that drove Item 1's corrected definition of 'active': `giga_tech_
    disco_moon`'s two `has_technology` gate edges must stay active on all 12 profiles even though
    the node's own availability is unconditionally uncertain (an unrelated, unresolvable sibling
    fact, `giga_can_use_habitables`, dominates its `potential` block to UNKNOWN regardless of
    empire type). An earlier (rejected) sensitivity-based definition reported these edges 0/12
    active, which would have silently dropped real prerequisite structure to encode uncertainty
    that belongs on the NODE, not the edge -- see `pipeline.edge_constraints`'s module docstring."""
    doc, _node_bytes, _edge_bytes = base_dataset
    disco_edge_indices = [
        i for i, e in enumerate(doc["edges"])
        if e["to"] == "giga_tech_disco_moon" and e["from"] in ("tech_autocurating_vault", "tech_transcendent_faith")
    ]
    assert len(disco_edge_indices) == 2
    for p in ctx.profiles:
        overlay = build_empire_overlay(ctx, p)
        active = set(overlay["activeEdgeIds"])
        assert set(disco_edge_indices) <= active, f"Disco Moon gate edges inactive for {p}"


def test_applies_to_empire_types_populated_only_for_the_five_constrained_edges(base_dataset):
    """Pins the real corpus result of `pipeline.edge_constraints`: only 5 of 984 edges carry a
    non-empty `appliesToEmpireTypes`, all `potential-gate`, none `prerequisite`/`alternative`
    (structurally impossible for those two kinds -- see that module's docstring)."""
    doc, _node_bytes, _edge_bytes = base_dataset
    constrained = {(e["from"], e["to"], e["kind"]): e["appliesToEmpireTypes"] for e in doc["edges"] if e["appliesToEmpireTypes"]}
    assert constrained == {
        ("tech_mega_engineering", "giga_tech_arkship_neutronium_harvester", "potential-gate"): {"nomadic": ["yes"]},
        ("tech_terrestrial_sculpting", "giga_tech_orbital_artificial_eco", "potential-gate"): {"nomadic": ["no"]},
        ("tech_cosmogenesis_escort", "tech_missiles_1", "potential-gate"): {"shipset": ["biological"]},
        ("tech_cosmogenesis_escort", "tech_torpedoes_1", "potential-gate"): {"shipset": ["biological"]},
        ("tech_gene_tailoring", "giga_tech_planetary_seeder_nexus", "potential-gate"): {
            "authority": ["hive_mind", "regular"], "shipset": ["biological"],
        },
    }


def test_dual_kind_edge_pair_does_not_leak_its_gate_constraint_onto_the_prerequisite_edge(base_dataset):
    """CLAUDE.md's 'Edge-kind membership is NOT mutually exclusive per (from, to) pair':
    `tech_mega_engineering -> giga_tech_arkship_neutronium_harvester` is both a `prerequisite` edge
    (unconstrained, always) and a `potential-gate` edge (nomadic=yes only). A `(from_key, to_key)`
    keyed lookup would leak the gate's constraint onto the prerequisite edge -- this is the real
    corpus pair that would have caught it."""
    doc, _node_bytes, _edge_bytes = base_dataset
    pair = [
        e for e in doc["edges"]
        if e["from"] == "tech_mega_engineering" and e["to"] == "giga_tech_arkship_neutronium_harvester"
    ]
    assert {
        (e["kind"], tuple((k, tuple(v)) for k, v in sorted(e["appliesToEmpireTypes"].items()))) for e in pair
    } == {
        ("prerequisite", ()), ("potential-gate", (("nomadic", ("yes",)),)),
    }


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
    """Found earlier, by reviewing a real rendered screenshot: `giga_tech_aeternite_weaponry` had
    a real loc entry whose VALUE was verbatim its own KEY (the mod author never wrote a display
    name) -- the `$...$`-token check above didn't catch it, since there's no token, just a bare
    key masquerading as a name. `config/name_overrides.txt` covered that one real case at the
    time; Item 2c (later session) then excluded `giga_tech_aeternite_weaponry` from the rendered
    tree entirely (`potential = { always = no }`, disabled content), so the override was removed
    as dead rather than left in place -- see `tests/test_name_overrides.py`. This assertion still
    stands as the general guard: no CURRENTLY rendered technology's name equals its own raw key,
    with no example left to name-check specifically."""
    doc, _node_bytes, _edge_bytes = base_dataset
    bad = [t["id"] for t in doc["technologies"] if t["name"] == t["id"]]
    assert bad == []


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
    assert len(non_repeatable_with_repeatable_field) == 973 - 88  # D-18: 980 -> 977; Item 2c: 977 -> 973

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
    assert len(resolved_costs) == 973 - 5  # D-18: 980 -> 977; Item 2c: 977 -> 973
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
        assert len(overlay["availability"]) == 973  # D-18: 980 -> 977; Item 2c: 977 -> 973
        assert len(overlay["researchPaths"]) == 973


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


def test_all_973_detail_payloads_validate(all_detail_payloads):
    # D-18: 980 -> 977; Item 2c: 977 -> 973
    assert len(all_detail_payloads) == 973
    for payload in all_detail_payloads.values():
        validate_detail_payload(payload)


def test_search_index_covers_all_technologies_and_validates(ctx, base_dataset, all_detail_payloads):
    doc, _node_bytes, _edge_bytes = base_dataset
    index = build_search_index(ctx, doc, all_detail_payloads)
    validate_search_index(index)
    assert len(index["entries"]) == 973  # D-18: 980 -> 977; Item 2c: 977 -> 973
    assert all(e["tokens"] for e in index["entries"])


def test_search_index_includes_axis_expressible_swap_alternate_names(ctx, base_dataset, all_detail_payloads):
    """Item 2: a user who remembers a swap alternate's name (e.g. the bioship swap "Zero Point
    Metabolism") must be able to find `tech_zero_point_power` while browsing under ANY profile,
    including one where that swap isn't active -- search matching is pooled across all swap
    alternates, unconditionally, not gated by the currently selected profile."""
    doc, _node_bytes, _edge_bytes = base_dataset
    index = build_search_index(ctx, doc, all_detail_payloads)
    entry = next(e for e in index["entries"] if e["technologyId"] == "tech_zero_point_power")
    assert "metabolism" in entry["tokens"]
    base_name = next(t for t in doc["technologies"] if t["id"] == "tech_zero_point_power")["name"]
    assert base_name == "Zero Point Power"
    assert "power" in entry["tokens"]  # the base name's own tokens are still present too


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

    # Item 2 (later session): the four resolution rules (has_megacorp/DLC, colossus_project
    # progression flag, has_acot/has_aot_mod mod-requirement, plus Item 2c's always-no exclusion
    # shrinking the denominator 977 -> 973) moved unconditionalUncertainty 209 -> 205 and the
    # worst profile-dependent rate 0.033777 (33/977) -> 0.028777 (28/973) -- both real
    # IMPROVEMENTS (lower counts against a smaller corpus), not something the ratchet flags.
    # A later session's has_ancrel fix (see tests/test_availability_corpus.py's own writeup) moved
    # unconditionalUncertainty 205 -> 183 and the worst profile-dependent rate 0.028777 -> 0.027749.
    # A later session's Item 2 (`pipeline.scripted_triggers` general expansion) moved
    # unconditionalUncertainty 183 -> 176 (a real improvement) but the worst profile-dependent
    # rate 0.027749 -> 0.034944 (a real, reported tradeoff -- see
    # test_gate_classification_leaves_d10_uncertainty_unchanged's own writeup for why: previously
    # unconditional technologies became genuinely profile-dependent instead, which is more
    # informative but counts against this specific metric). The SAME session's Item 3 (ethics/
    # civic/origin as display gates) then moved unconditionalUncertainty 176 -> 107 and the worst
    # profile-dependent rate 0.034944 -> 0.015416 -- both real improvements, in the SAME direction
    # this time (see test_gate_classification_leaves_d10_uncertainty_unchanged's own writeup).
    # **107 -> 34, a later session ("commit + close the loop" follow-up, Item 2): the
    # story-progression flag CLASS.** Flags matching `pipeline.trigger_text.
    # looks_like_story_progress`'s naming pattern (verified real setting sites, same evidence shape
    # as the already-approved `colossus_project` precedent) resolve TRUE as a class -- 73
    # technologies move UNCONDITIONALLY uncertain -> AVAILABLE. Worst profile-dependent rate is
    # UNCHANGED (0.015416): every one of the 73 was unconditionally stuck before, none merely
    # profile-dependent, so none had anywhere to "move to" on that axis. See
    # tests/test_availability_corpus.py's own writeup for the full accounting, including the two
    # vanilla L-Gate flags deliberately excluded from this resolution.
    # 34 -> 31, a later session (Items 1, 2, 5): see
    # tests/test_availability_corpus.py::test_real_rates_against_projections's own writeup for the
    # three individual fixes (`always`, ascension-perk axis-locking's `_combine_or` correction,
    # `has_active_tradition`).
    assert diagnostics["unconditionalUncertainty"]["count"] == 31
    assert len(diagnostics["profileDependentUncertainty"]) == 12
    worst = max(d["rate"] for d in diagnostics["profileDependentUncertainty"])
    assert worst == pytest.approx(0.016444, abs=1e-5)  # 0.015416 -> 0.016444 (16/973), Items 1/2/5

    cap_keys = {k for k in ctx.rendered_keys if k.startswith("giga_tech_repeatable_") and k.endswith("_cap")}
    assert len(cap_keys) == 50
    for key in cap_keys:
        from pipeline.dataset_emit import _field

        assert _field(ctx.rendered_defs[key].block, "potential") is not None, (
            f"{key}: expected a potential block visible only after inline_script expansion"
        )


def test_diagnostics_uncertain_technologies_matches_d10(ctx):
    """Item 1 (later session): the dev health monitor's data must never disagree with D-10's own
    counts -- both come from the same evaluator call, but this proves it rather than assuming it
    (this project's own standing rule). unconditionalUncertainty.count must equal the number of
    uncertainTechnologies entries flagged `unconditional`; the union of unconditional + real
    profile-dependent entries must equal the total entry count."""
    diagnostics = build_diagnostics(ctx)
    entries = diagnostics["uncertainTechnologies"]
    unconditional_entries = [e for e in entries if e["unconditional"]]
    assert len(unconditional_entries) == diagnostics["unconditionalUncertainty"]["count"]
    for e in entries:
        assert len(e["perProfile"]) == (12 if e["unconditional"] else len(e["perProfile"]))
        assert 1 <= len(e["perProfile"]) <= 12
        for p in e["perProfile"]:
            assert p["category"]
            assert p["description"]
    assert len(entries) == len({e["technologyId"] for e in entries})  # no duplicate technologies
    assert entries == sorted(entries, key=lambda e: e["technologyId"])  # stable diffable order


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


def test_rendered_node_count_stays_973_regardless_of_technology_swap(ctx, base_dataset):
    """D-14 decision 1: a swap NEVER becomes its own node -- the rendered set is exactly 973
    (D-18: 980 -> 977; Item 2c, later session: 977 -> 973) whether or not a technology carries a
    technology_swap, axis-expressible or not."""
    doc, _node_bytes, _edge_bytes = base_dataset
    assert len(doc["technologies"]) == 973
    assert len(ctx.rendered_keys) == 973


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

    # Every OTHER rendered technology (971/973) has an empty list -- the field is real data, not
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


def test_reduced_corpus_build_is_973_nodes(vendor_without_acot_aot):
    """The headline finding from the vendoring-automation investigation, re-verified as a
    regression test rather than left as a one-off manual measurement: pre-D-18, 980 - 7 + 4 = 977,
    not 980 - 7 = 973 (the OLD, coincidentally-identical-looking wrong-arithmetic number, before
    Item 2c ever existed). D-18 (spec/decisions.md): the full-build rendered count moved
    980 -> 977 for an UNRELATED reason (the depth-1 ACOT/AoT closure), and PLACEHOLDER_
    TECHNOLOGIES_REQUIRING_ACOT_AOT narrowed 7 -> 4 members (only the depth-1 ones can still be
    ABSENT when ACOT/AoT is missing -- the 3 dropped ones are never rendered regardless). Item 2c
    (later session) then excluded 4 permanently-disabled technologies from BOTH build modes
    identically (none of the 4 is ACOT/AoT-sourced or reachable only through them), moving the
    full-build figure 977 -> 973 -- and, verified directly here rather than assumed, the
    reduced-build figure moves the SAME way, landing on 973 too (973 - 4 + 4 = 973, again a
    coincidence of these particular numbers, not a reason the two builds should always match)."""
    ctx = build_context(vendor_without_acot_aot)
    assert len(ctx.rendered_keys) == 973
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
