#!/usr/bin/env python3
"""Builds `client/tests/fixtures/dataset/` -- a small, committed, REGENERABLE dataset fixture
for the client test suite (Item 1 of the "client test infrastructure" task).

**Why this exists.** `client/` had no tests at all before this script, and the real dataset
(`tools/build_dataset.py`'s output) can never be committed (gitignored -- derived from vendored
third-party content) or built in CI (D-15 -- vanilla Stellaris needs a Steam account). A client
test that needs dataset-shaped data therefore needs a small, committed substitute -- the same
problem `tests/fixtures/` already solves on the pipeline side, via `tools/regenerate_fixtures.py`.

**Why this is a SUBSET of a real build, not a hand-authored synthetic one.** Fabricating a tiny
synthetic mod corpus from scratch would still need real icon files (the build hard-fails on a
missing icon for a displayed technology -- CLAUDE.md's Rules), so it's no less vendor-dependent
than this approach, just a different, more fragile flavour of it. This script instead runs the
REAL pipeline against the REAL vendored corpus (exactly like `tools/build_dataset.py`), then
mechanically slices the result down to a curated technology set plus its immediate edge
neighbours -- every field in the fixture is real, pipeline-computed data, just fewer nodes. This
needs `vendor/` populated to REGENERATE (same posture as `tools/regenerate_fixtures.py` and
`tools/build_dataset.py` -- run locally, never in CI); the output itself IS committed (unlike
`client/public/dataset/`), because it is small, synthetic-scope, and contains no more of the
mod's content than a handful of individual technology records already quoted at length in
CLAUDE.md/docs/BUILD-LOG.md for exactly these examples.

**Positional geometry contract relied on here** (see `pipeline/dataset_emit.build_base_dataset`
and `client/src/main.ts`'s own `FLOATS_PER_EDGE_POLYLINE` constant): `technologies[i]`'s (x, y)
is `nodePositions[i*2 : i*2+2]`; `edges[i]`'s 6-point polyline is
`edgePolylines[i*12 : i*12+12]`. There is no per-record offset field in the schema -- position
IS the pointer. Slicing down to a subset is therefore just "pick the same indices out of both
the JSON arrays and the float arrays, in the same relative order" -- exactly what this script
does; it never recomputes layout.

Run: `python tools/build_client_fixture_dataset.py` (needs `vendor/` populated).
"""

from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pipeline.dataset_emit import (  # noqa: E402
    build_base_dataset,
    build_context,
    build_detail_payload,
    build_diagnostics,
    build_empire_overlay,
    build_search_index,
)
from pipeline.dataset_schema import (  # noqa: E402
    validate_base_dataset,
    validate_detail_payload,
    validate_diagnostics,
    validate_empire_overlay,
    validate_search_index,
)

VENDOR_ROOT = REPO_ROOT / "vendor"
OUT_DIR = REPO_ROOT / "client" / "tests" / "fixtures" / "dataset"

# ---------------------------------------------------------------------------
# Curated technology set -- one real technology per shape the client must handle. Each was
# picked by grepping the real corpus/CLAUDE.md for a confirmed example, not guessed.
# ---------------------------------------------------------------------------
CURATED_IDS = {
    "gated": "tech_habitat_1",  # is_wilderness_empire = no -- negative origin gate (D-3/negative gates)
    "weight_modifier_pair_a": "tech_housing_2",  # unwrapped civic weight condition (negated=True)
    "weight_modifier_pair_b": "tech_housing_agrarian_idyll",  # NOT-wrapped sibling (negated=False)
    "alternative_group": "tech_mega_engineering",  # nested OR inside `prerequisites` -- a real `alternative`-kind edge (D-2), 4 members
}


def _pick_repeatable(technologies_json: list[dict]) -> str:
    for tech in technologies_json:
        if tech["repeatable"] is not None and tech["repeatable"]["levels"] is not None:
            return tech["id"]
    for tech in technologies_json:
        if tech["repeatable"] is not None:
            return tech["id"]
    raise RuntimeError("no repeatable technology found in the real corpus")


def _pick_one_of_each_availability_state(technologies_json: list[dict], profile_index: int) -> dict[str, str]:
    wanted = {"available", "locked", "uncertain", "config-gated", "weight-gated"}
    found: dict[str, str] = {}
    for tech in technologies_json:
        state = tech["availabilityMatrix"][profile_index]
        if state in wanted and state not in found:
            found[state] = tech["id"]
        if len(found) == len(wanted):
            break
    missing = wanted - found.keys()
    if missing:
        raise RuntimeError(f"could not find a real technology in state(s) {missing} for profile index {profile_index}")
    return found


def _pick_variant_technology(ctx) -> str | None:
    from pipeline.technology_swaps import collect_swaps

    for key in sorted(ctx.rendered_keys):
        defn = ctx.rendered_defs.get(key)
        if defn is None:
            continue
        swaps = [s for s in collect_swaps(key, defn.block) if not s.axis_expressible]
        if swaps:
            return key
    return None


def _slice_floats(data: bytes, indices: list[int], stride_floats: int) -> bytes:
    (n_floats,) = (len(data) // 4,)
    all_floats = struct.unpack(f"<{n_floats}f", data)
    out: list[float] = []
    for i in indices:
        out.extend(all_floats[i * stride_floats : i * stride_floats + stride_floats])
    return struct.pack(f"<{len(out)}f", *out)


def main() -> None:
    if not VENDOR_ROOT.is_dir():
        raise SystemExit("vendor/ is not populated -- run tools/collect_vanilla.py first (see CLAUDE.md)")

    print("Building the real dataset from vendor/ (this reuses tools/build_dataset.py's own pipeline)...")
    ctx = build_context(VENDOR_ROOT)
    full_doc, node_bytes, edge_bytes = build_base_dataset(ctx)
    validate_base_dataset(full_doc)

    technologies_by_id = {t["id"]: t for t in full_doc["technologies"]}
    tech_index = {t["id"]: i for i, t in enumerate(full_doc["technologies"])}

    curated = dict(CURATED_IDS)
    curated["repeatable"] = _pick_repeatable(full_doc["technologies"])
    variant_id = _pick_variant_technology(ctx)
    if variant_id:
        curated["variants"] = variant_id
    curated.update({f"state_{k}": v for k, v in _pick_one_of_each_availability_state(full_doc["technologies"], 0).items()})

    for role, tid in curated.items():
        if tid not in technologies_by_id:
            raise RuntimeError(f"curated id for {role!r} ({tid!r}) is not a rendered technology in the real corpus")

    print("Curated technology set:")
    for role, tid in sorted(curated.items()):
        print(f"  {role:24s} {tid}")

    # Keep set: curated technologies plus every direct edge neighbour (either direction), so the
    # fixture carries real, non-dangling edges to look at -- not just isolated nodes. Membership
    # is tested against the ORIGINAL curated set only (a fixed snapshot) so this stays a single
    # hop -- testing against the growing `keep_ids` instead would cascade transitively through
    # however many edges happen to chain together, ballooning the "minimal" fixture unboundedly.
    seed_ids: set[str] = set(curated.values())
    keep_ids: set[str] = set(seed_ids)
    for edge in full_doc["edges"]:
        if edge["from"] in seed_ids or edge["to"] in seed_ids:
            keep_ids.add(edge["from"])
            keep_ids.add(edge["to"])

    kept_tech_order = [t["id"] for t in full_doc["technologies"] if t["id"] in keep_ids]
    old_tech_indices = [tech_index[tid] for tid in kept_tech_order]

    kept_edges = [
        (i, e) for i, e in enumerate(full_doc["edges"]) if e["from"] in keep_ids and e["to"] in keep_ids
    ]
    old_edge_indices = [i for i, _ in kept_edges]
    old_to_new_edge_index = {old_i: new_i for new_i, old_i in enumerate(old_edge_indices)}

    # --- technologies + geometry -------------------------------------------------------------
    technologies_json = [technologies_by_id[tid] for tid in kept_tech_order]
    row_counts: dict[str, int] = {}
    for t in technologies_json:
        row_counts[t["rowId"]] = row_counts.get(t["rowId"], 0) + 1
    rows_json = [dict(r, technologyCount=row_counts.get(r["id"], 0)) for r in full_doc["rows"]]

    edges_json = [e for _, e in kept_edges]

    forward: dict[str, dict[str, list[int]]] = {}
    reverse: dict[str, dict[str, list[int]]] = {}
    for old_kind_map, new_kind_map in ((full_doc["adjacency"]["forward"], forward), (full_doc["adjacency"]["reverse"], reverse)):
        for tid, by_kind in old_kind_map.items():
            if tid not in keep_ids:
                continue
            filtered_by_kind = {
                kind: [old_to_new_edge_index[i] for i in indices if i in old_to_new_edge_index]
                for kind, indices in by_kind.items()
            }
            filtered_by_kind = {k: v for k, v in filtered_by_kind.items() if v}
            if filtered_by_kind:
                new_kind_map[tid] = filtered_by_kind

    new_node_bytes = _slice_floats(node_bytes, old_tech_indices, 2)
    new_edge_bytes = _slice_floats(edge_bytes, old_edge_indices, 12)

    base_dataset = dict(full_doc)
    base_dataset["rows"] = rows_json
    base_dataset["technologies"] = technologies_json
    base_dataset["edges"] = edges_json
    base_dataset["adjacency"] = {"forward": forward, "reverse": reverse}
    base_dataset["geometry"] = {
        "nodePositions": {**full_doc["geometry"]["nodePositions"], "length": len(technologies_json) * 2},
        "edgePolylines": {**full_doc["geometry"]["edgePolylines"], "length": len(edges_json) * 12},
    }
    validate_base_dataset(base_dataset)

    # --- detail payloads (curated technologies only -- the fixture's point is these fields) ---
    detail_payloads: dict[str, dict] = {}
    for tid in set(curated.values()):
        payload = build_detail_payload(ctx, tid)
        validate_detail_payload(payload)
        detail_payloads[tid] = payload

    # --- search index (built against the FULL corpus for real token text, then filtered) ------
    full_search_index = build_search_index(ctx, full_doc, detail_payloads)
    search_index = {
        "schemaVersion": full_search_index["schemaVersion"],
        "entries": [e for e in full_search_index["entries"] if e["technologyId"] in keep_ids],
    }
    validate_search_index(search_index)

    # --- empire overlays (two profiles: the default, and one exercising every axis) -----------
    from pipeline.dataset_schema.empire_profile import all_profiles_in_canonical_order

    profiles = all_profiles_in_canonical_order()
    chosen_profiles = [profiles[0], profiles[-1]]

    def _profile_key(p: dict) -> str:
        return f"{p['authority']}-{p['shipset']}-{p['nomadic']}"

    overlays: dict[str, dict] = {}
    for profile in chosen_profiles:
        overlay = build_empire_overlay(ctx, profile)
        filtered = dict(overlay)
        filtered["availability"] = {k: v for k, v in overlay["availability"].items() if k in keep_ids}
        filtered["researchPaths"] = {k: v for k, v in overlay["researchPaths"].items() if k in keep_ids}
        filtered["swapMappings"] = [m for m in overlay["swapMappings"] if m["technologyId"] in keep_ids]
        filtered["activeEdgeIds"] = sorted(
            old_to_new_edge_index[i] for i in overlay["activeEdgeIds"] if i in old_to_new_edge_index
        )
        validate_empire_overlay(filtered)
        overlays[_profile_key(profile)] = filtered

    # --- diagnostics (global counts kept real; the one CONSUMED list, uncertainTechnologies, filtered) ---
    diagnostics = build_diagnostics(ctx)
    diagnostics = dict(diagnostics)
    diagnostics["uncertainTechnologies"] = [
        e for e in diagnostics["uncertainTechnologies"] if e.get("technologyId") in keep_ids
    ]
    # Not a consumed field (build-time-only, see the field-consumption annotation file) -- trimmed
    # purely to keep this fixture small; a full-corpus 490-entry list added nothing to test.
    diagnostics["unresolvableResearchPaths"] = [
        e for e in diagnostics["unresolvableResearchPaths"] if e.get("technologyId") in keep_ids
    ]
    validate_diagnostics(diagnostics)

    # --- write everything --------------------------------------------------------------------
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in OUT_DIR.glob("*"):
        if path.is_file():
            path.unlink()

    (OUT_DIR / "base-dataset.json").write_text(json.dumps(base_dataset, indent=2, sort_keys=True) + "\n")
    (OUT_DIR / "node-positions.f32").write_bytes(new_node_bytes)
    (OUT_DIR / "edge-polylines.f32").write_bytes(new_edge_bytes)
    (OUT_DIR / "search-index.json").write_text(json.dumps(search_index, indent=2, sort_keys=True) + "\n")
    (OUT_DIR / "diagnostics.json").write_text(json.dumps(diagnostics, indent=2, sort_keys=True) + "\n")

    detail_paths = {}
    for tid, payload in detail_payloads.items():
        fname = f"detail-{tid}.json"
        (OUT_DIR / fname).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        detail_paths[tid] = fname

    overlay_paths = {}
    for key, overlay in overlays.items():
        fname = f"empire-overlay-{key}.json"
        (OUT_DIR / fname).write_text(json.dumps(overlay, indent=2, sort_keys=True) + "\n")
        overlay_paths[key] = fname

    manifest = {
        "$comment": "Reproduced by tools/build_client_fixture_dataset.py from vendor/. Not hashed "
        "(unlike client/public/dataset/'s real manifest) -- this is a fixed, committed test "
        "fixture, not a cache-busted deploy artefact.",
        "baseDataset": "base-dataset.json",
        "searchIndex": "search-index.json",
        "diagnostics": "diagnostics.json",
        "overlays": overlay_paths,
        "details": detail_paths,
        "curatedIds": curated,
    }
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    print(f"\nWrote fixture dataset ({len(technologies_json)} technologies, {len(edges_json)} edges) to {OUT_DIR}")


if __name__ == "__main__":
    main()
