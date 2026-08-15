"""Stage 2 dataset emission: assembles the five schema'd artefacts (base dataset, empire
overlay, detail payload, search index, diagnostics) from every already-built Stage 2 component
(P-15 overwrites, P-13 availability, P-16 rendering scope, D-7 crisis faction, P-2/P-14
layout+edges, icon atlases) — spec/00-overview.md's "Dataset structure", schema/*.json.

**Every emitted artefact is validated against its schema before this module hands it back** —
`build_all_artefacts` calls the matching `pipeline.dataset_schema.validate_*` on every document it
assembles, so an invalid artefact raises during the build itself, never something a caller has to
remember to check separately (CLAUDE.md: "the build fails rather than emitting a partial
dataset").

**Known v1 scope limitations, stated here so they're not mistaken for oversights**:

- `appliesToEmpireTypes` is emitted unconstrained (`{}` — applies to every profile) on every
  edge. Building a real per-edge empire-type constraint extractor (walking the boolean context an
  edge's `has_technology`/`OR` member sits under for axis-fact leaves) is new scope beyond what
  P-14 built; CLAUDE.md's "empire-type edge shape" finding confirms every real constraint is a
  rectangular per-axis subset, but confirms the *shape* a future extractor must produce, not that
  one exists yet. Consequence: `activeEdgeIds` is therefore every edge index, identically, for
  all twelve profiles — correct-but-undifferentiated, not wrong.
- `swapMappings` and detail payload `variants` are now real (D-14, spec/decisions.md, closed a
  later session) -- `pipeline.technology_swaps` classifies each `technology_swap` as
  axis-expressible (substituted per profile into `swapMappings`) or not (listed as a popup-only
  `variants` entry, never substituted). `weight` and `prereqfor_desc`, two fields a swap sub-block
  can also carry, remain deliberately unsurfaced -- consistent with D-4's "no evaluated weight"
  precedent, not an oversight; see D-14 for the full accounting.
- `gates` is always `[]`. P-3's gate-pattern-registry classification pass (curated, layered on
  top of the universal `potential-gate` edge extraction P-14 already built) is not built —
  HANDOFF.md's "Ordered next steps" already tracked this as open before this session.
- `repositoryLink`'s `lineRange` uses the technology block's own start line for both `startLine`
  and `endLine` (no end-of-block line is tracked anywhere in the AST) and the `stellaris-wiki`
  URL is a best-effort slug, not validated against a live fetch (P-12.6's "CI validates wiki
  anchors resolve" needs network access this offline build doesn't have).
- `description` strips `§...§!` colour codes and `£...£` icon tokens to bare text rather than
  resolving them to real markup spans; P-12.1's fuller "resolved or safely stripped" contract
  chooses the stripped half only.
- `researchPaths` is a plain BFS ancestor set over `prerequisite` edges only (matching P-12.9's
  "prerequisite-edges-only" contract), cumulative cost summed from each technology's own `cost`
  field, `shortestChain` computed by total cost — correct for what it claims, but does not yet
  account for a resolved `@variable`/inline_script cost the way P-15's diff layer does.

None of these silently claims to be something it isn't — each is schema-valid (empty
array/unconstrained object are legal shapes) and documented here and in the diagnostics/HANDOFF
write-up, not fabricated content standing in for a missing feature.
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass
from pathlib import Path

from .availability import (
    AVAILABLE,
    CONFIG_GATED,
    LOCKED,
    UNCERTAIN,
    build_d10_diagnostics_section,
    evaluate_technology_for_profiles,
    evaluate_trigger_block,
    resolve_lock_reason,
    survey_uncertainty,
)
from .clausewitz import parse_file
from .clausewitz.nodes import Assignment, Block, Identifier, NumberLiteral, StringLiteral, VariableReference
from .crisis_faction import classify_crisis_factions
from .crisis_faction_overrides import load_overrides as load_crisis_overrides
from .dataset_schema.empire_profile import all_profiles_in_canonical_order, empire_profile_index
from .edges import compute_typed_edges
from .geometry import pack_edge_polylines, pack_node_positions
from .icons.build import build_atlases, decode_resolved_icons
from .icons.overrides import load_overrides as load_icon_overrides
from .inline_scripts import collect_scripts, expand_document
from .layout import (
    DEFAULT_SUBGRID_WIDTH,
    REPEATABLES,
    TechnologyLayoutInput,
    category_of,
    compute_layout,
    is_repeatable,
    resolve_declared_tier,
)
from .localisation import parse_file as parse_loc_file
from .localisation.sources import default_source_configs as default_loc_source_configs
from .localisation.table import LocalisationTable, build_table
from .lock_reason_overrides import load_overrides as load_lock_reason_overrides
from .overwrite_overrides import load_overrides as load_overwrite_overrides
from .overwrites import (
    TechnologyDefinition,
    build_overwrite_report,
    collect_technology_definitions,
    collect_variable_definitions,
    resolve_technology_overwrites,
    resolve_variable_overwrites,
)
from .rendering_scope import compute_alternative_only_gaps, rendered_technology_keys
from .technology_swaps import TechnologySwap, collect_swaps
from .trigger_text import describe_condition, describe_trigger_block
from .variables import build_variable_table

SCHEMA_VERSION = "1.0.0"

_SOURCES_IN_LOAD_ORDER = ["Vanilla", "Gigastructural Engineering", "ACOT", "AoT"]
_SOURCE_DIRS = {
    "Vanilla": "stellaris",
    "Gigastructural Engineering": "mods/gigastructures",
    "ACOT": "mods/acot",
    "AoT": "mods/aot",
}
_WORKSHOP_IDS = {"ACOT": "1419304439", "AoT": "2178603631"}
_FLAG_FIELDS = ("is_rare", "is_dangerous")

# Hand-verified against the full (all-four-sources) corpus, NOT dynamically derivable from a
# reduced build that's missing ACOT and/or AoT -- that's exactly the point of these two lists.
# `PLACEHOLDER_TECHNOLOGIES_REQUIRING_ACOT_AOT`: the 7 real technologies whose `requiresMods`
# names ACOT/AoT in the full build (spec/decisions.md's vendoring-automation investigation).
# These are Gigastructures' own "supertensile alternate" content (`giga_17_alternative_mega_
# build.txt`) -- the actual reason ACOT/AoT are vendored at all: they show the TRUE prerequisites
# of those alternates, not a cosmetic extra. 4 of the 7 are directly referenced by key in
# Gigastructures' own files (confirmed by direct grep); the other 3
# (`tech_dark_matter_power_core_enig`, `tech_mine_dark_energy`, `tech_precursor_design`) are
# reached only via ACOT's OWN internal prerequisite chains, invisible without ACOT loaded --
# which is exactly why this list must be a maintained constant rather than computed from
# whatever's currently loaded. Re-verified by
# `tests/test_dataset_emit.py::test_placeholder_technologies_constant_matches_full_corpus`
# whenever the full corpus is available.
PLACEHOLDER_TECHNOLOGIES_REQUIRING_ACOT_AOT: dict[str, str] = {
    "tech_dark_matter_power_core_ae": "ACOT",
    "tech_dark_matter_power_core_dm": "ACOT",
    "tech_dark_matter_power_core_enig": "ACOT",
    "tech_dark_matter_power_core_se": "ACOT",
    "tech_mine_dark_energy": "ACOT",
    "tech_precursor_design": "ACOT",
    "tech_civil_phanon_application": "AoT",
}

# `VANILLA_TECHNOLOGIES_ACOT_OVERWRITES`: the 4 vanilla technology keys ACOT redefines in the
# full build (P-15). Without ACOT loaded, these revert to their vanilla content and REAPPEAR in
# the rendered set -- P-16's closure had excluded their ACOT-overwritten form, not their vanilla
# one (spec/decisions.md's vendoring-automation investigation: 980 - 7 + 4 = 977, not 973). User-
# supplied domain context, recorded so the diagnostic's wording doesn't imply all four differ
# equally: ACOT's overwrite of `tech_adaptive_combat_algorithms` and `tech_biomechanics` ONLY adds
# modifiers -- invisible to this tool's display either way, so reverting to vanilla is a
# non-event for anything the tree actually shows. `tech_titan_hull_1`/`tech_titan_hull_2` are the
# notable exception: ACOT's content materially differs from vanilla's, so the reverted-to-vanilla
# version a reduced build shows IS a real, visible content difference, not just bookkeeping.
VANILLA_TECHNOLOGIES_ACOT_OVERWRITES: dict[str, bool] = {
    # key -> whether ACOT's overwrite materially differs from vanilla's content (True) or only
    # adds modifiers, invisible to this tool's display either way (False).
    "tech_adaptive_combat_algorithms": False,
    "tech_biomechanics": False,
    "tech_titan_hull_1": True,
    "tech_titan_hull_2": True,
}


def _source_roots(vendor_root: Path) -> list[tuple[str, Path]]:
    return [(name, vendor_root / _SOURCE_DIRS[name]) for name in _SOURCES_IN_LOAD_ORDER]


def _script_entries(vendor_root: Path):
    entries = []
    for name, root in _source_roots(vendor_root):
        base = root / "common" / "inline_scripts"
        if not base.is_dir():
            continue
        for f in sorted(base.rglob("*.txt")):
            rel = f.relative_to(base).with_suffix("")
            entries.append((str(rel).replace("\\", "/"), str(f), f.read_text(encoding="utf-8")))
    return entries


def _load_expanded(vendor_root: Path, sub: str, scripts):
    result = []
    for name, root in _source_roots(vendor_root):
        d = root / "common" / sub
        if not d.is_dir():
            continue
        docs = [expand_document(parse_file(f), scripts)[0] for f in sorted(d.glob("*.txt"))]
        result.append((name, docs))
    return result


def _field(block: Block, name: str) -> Assignment | None:
    result = None
    for item in block.items:
        if isinstance(item, Assignment) and item.key_name == name:
            result = item
    return result


def _scalar_text(node) -> str | None:
    if isinstance(node, Identifier):
        return node.name
    if isinstance(node, StringLiteral):
        return node.value
    return None


def _bool_flag(block: Block, name: str) -> bool:
    assignment = _field(block, name)
    if assignment is None:
        return False
    return _scalar_text(assignment.value) == "yes"


def _levels_value(block: Block, variable_table) -> int | None:
    assignment = _field(block, "levels")
    if assignment is None:
        return None
    value = assignment.value
    if isinstance(value, NumberLiteral):
        return int(value.value)
    if isinstance(value, VariableReference):
        resolved = variable_table.resolve(value.name)
        if isinstance(resolved, NumberLiteral):
            return int(resolved.value)
    return None


def _resolve_numeric(value, variable_table) -> float | None:
    if value is None:
        return None
    if isinstance(value, NumberLiteral):
        return float(value.value)
    if isinstance(value, VariableReference):
        try:
            resolved = variable_table.resolve(value.name)
        except Exception:
            return None
        if isinstance(resolved, NumberLiteral):
            return float(resolved.value)
    return None


_MARKUP_RE = re.compile(r"§.|£[^£]*£")


def strip_markup(raw: str) -> str:
    """P-12.1's stripped half: drop `§X`/`§!` colour codes and `£icon£` tokens, leave the rest
    verbatim. See module docstring's scope-limitation note -- this does not resolve embedded
    `$VAR$` tokens to real values."""
    return _MARKUP_RE.sub("", raw)


_MANAGEMENT_PROTOCOLS_SUFFIX = " Management Protocols"
_LOC_TOKEN_RE = re.compile(r"\$([^$]+)\$")
_LOC_TOKEN_MAX_HOPS = 3


def _resolve_loc_tokens(text: str, ctx: "BuildContext") -> str | None:
    """Resolves Stellaris localisation's own `$key$` variable-substitution syntax against the
    full cross-source `ctx.loc_table` (vanilla, Gigastructures, ACOT, AoT, in load order) --
    ordinary static string substitution, corrected from an earlier, uncorrected assumption that
    a `$...$` token in a technology's own name was an unresolvable Stellaris runtime name-pool
    reference (see `_config_gated_subject`'s docstring for the corpus evidence). Bounded to
    `_LOC_TOKEN_MAX_HOPS` hops (a token's own value can itself be another token, e.g. vanilla's
    `dyson_swarm_1: "$dyson_swarm_3$: Array"` chains one level deep in the real corpus) so a
    cyclic or unexpectedly deep reference can't loop forever. Returns None -- never a partial or
    guessed string -- if a token can't be found in the loc table, or the text still contains an
    unresolved token after the hop limit."""
    for _ in range(_LOC_TOKEN_MAX_HOPS):
        match = _LOC_TOKEN_RE.search(text)
        if match is None:
            return text
        token_entry = ctx.loc_table.get(match.group(1))
        if token_entry is None:
            return None
        text = text[:match.start()] + strip_markup(token_entry.value.raw) + text[match.end():]
    return None if _LOC_TOKEN_RE.search(text) else text


def _config_gated_subject(key: str, ctx: "BuildContext") -> str | None:
    """P-13's config-gated reason template (spec/P-13-empire-locking.md): the semantic subject
    ('Alderson Disk') Stage 3 substitutes into the fixed, user-supplied template 'Requires
    {subject} cap: 1 + Repeatables'. Sourced from the giga_tech_repeatable_*_cap technology's OWN
    already-resolved localised name (`<Name> Management Protocols`).

    The suffix-stripped name is frequently a `$token$` itself (e.g.
    giga_tech_repeatable_alderson_cap -> '$name_alderson$') rather than a literal string. An
    earlier session treated that token as an unresolvable Stellaris runtime name-pool reference
    and returned None for all 8 real occurrences. That was WRONG, found on raw-source
    re-inspection (CLAUDE.md's rule: inspect raw text, never conclude from a formatted read): every
    one of these tokens is ordinary Stellaris localisation variable substitution -- `token` is
    itself a plain, statically-resolvable loc key (`name_alderson: "Alderson Disk"`,
    Gigastructures' own localisation). Two of the 8 (`dyson_swarm_3`, `orbital_arc_furnace_4`) are
    VANILLA megastructures Gigastructures extends with a repeatable cap, and their name is defined
    in vanilla's own localisation, not Gigastructures' -- confirming the lookup must search the
    full cross-source loc table (`_resolve_loc_tokens`/`ctx.loc_table`), not one source in
    isolation. Real corpus: all 50/50 now resolve. Still returns None -- an honest gap, never a
    guess -- if a technology's own name has no loc entry at all, or a token can't be resolved
    within `_resolve_loc_tokens`'s hop limit."""
    name_entry = ctx.loc_table.get(key)
    if name_entry is None:
        return None
    subject = strip_markup(name_entry.value.raw).removesuffix(_MANAGEMENT_PROTOCOLS_SUFFIX)
    return _resolve_loc_tokens(subject, ctx)


def _swap_display_name(swap: "TechnologySwap", ctx: "BuildContext") -> str:
    """D-14: the swap's own localised display name. Reuses `_resolve_loc_tokens` (the same
    `$token$` loc-variable-substitution resolver `_config_gated_subject` uses): a swap's own name
    entry is frequently ITSELF a `$token$` (e.g. `tech_bio_fission_power: "$BIO_FISSION_REACTOR$"`,
    `BIO_FISSION_REACTOR: "Fission Metabolism"`) rather than a literal string -- confirmed real for
    both examples checked during this decision's implementation, not a hypothetical edge case.
    Falls back to the raw swap key only when no loc entry exists at all, or a token can't be
    resolved -- an honest gap, never a guess (not observed for any real swap in the corpus at time
    of writing, but the fallback stays in place for a future one)."""
    entry = ctx.loc_table.get(swap.swap_key)
    if entry is None:
        return swap.swap_key
    resolved = _resolve_loc_tokens(strip_markup(entry.value.raw), ctx)
    return resolved if resolved is not None else swap.swap_key


def _swap_area_category(swap: "TechnologySwap", base_area: str, base_category: str) -> tuple[str | None, str | None]:
    """D-14: (area, category), each `None` when the swap doesn't redeclare the field OR
    redeclares it identically to the base technology's own value -- `None` here means 'use the
    base dataset's value', matching the schema's own null-means-unchanged contract."""
    area_assignment = _field(swap.swap_block, "area")
    swap_area = _scalar_text(area_assignment.value) if area_assignment is not None else None
    swap_category = category_of(swap.swap_block)
    area_out = swap_area if swap_area and swap_area != base_area else None
    category_out = swap_category if swap_category and swap_category != base_category else None
    return area_out, category_out


def _default_icon_ref(ctx: "BuildContext") -> dict:
    """Degenerate 1x1 placeholder for the vanishingly rare case a technology's own icon never
    resolved in the atlas at all -- never observed for a base technology in the real corpus, kept
    only so the schema's required `icon` field is never missing."""
    return {"sheet": ctx.tech_sheets[0].sheet_name if ctx.tech_sheets else "technologies_0", "x": 0, "y": 0, "width": 1, "height": 1}


def _swap_icon(owner_key: str, swap: "TechnologySwap", ctx: "BuildContext") -> dict:
    """D-14: the IconRef to show for this swap -- its own resolved icon if one exists in the
    atlas, else the owner's icon (already recorded in `ctx.inherited_swap_icons` if this is a
    fallback -- see `_swap_icon_ref_map`'s docstring for why that's a presentation-layer decision
    distinct from `pipeline/icons/resolve.py`'s own honest 'unresolved' bookkeeping)."""
    return ctx.swap_icon_refs.get((owner_key, swap.swap_key)) or ctx.icon_refs.get(owner_key) or _default_icon_ref(ctx)


@dataclass
class BuildContext:
    vendor_root: Path
    rendered_keys: set[str]
    rendered_defs: dict[str, TechnologyDefinition]
    variable_table: object
    crisis: dict[str, str | None]
    layout: object
    overwrite_records: dict
    loc_table: LocalisationTable
    profiles: list[dict]
    tech_icon_result: object
    perk_icon_result: object
    tech_sheets: list
    perk_sheets: list
    typed_edges: list
    icon_refs: dict
    swap_icon_refs: dict
    inherited_swap_icons: list
    sources_present: list[str]


def _sources_present(vendor_root: Path) -> list[str]:
    """Which of the four sources actually have a `common/technology` directory in `vendor_root`
    -- the same existence check `_load_expanded` already makes per source, exposed here so
    `build_diagnostics` can tell a reduced-corpus build (D-14/vendoring-automation session: ACOT
    and/or AoT absent is a real, supported build mode, not an error) from the full one."""
    return [name for name, root in _source_roots(vendor_root) if (root / "common" / "technology").is_dir()]


def build_context(vendor_root: Path) -> BuildContext:
    sources_present = _sources_present(vendor_root)
    scripts = collect_scripts(_script_entries(vendor_root))
    tech_docs = _load_expanded(vendor_root, "technology", scripts)
    var_docs = _load_expanded(vendor_root, "scripted_variables", scripts)
    all_docs = [d for _, ds in tech_docs for d in ds] + [d for _, ds in var_docs for d in ds]
    variable_table = build_variable_table(all_docs)

    history = collect_technology_definitions(tech_docs)
    rendered_keys = rendered_technology_keys(history)
    rendered_defs = {k: history[k][-1] for k in rendered_keys}

    crisis = classify_crisis_factions(rendered_defs, load_crisis_overrides())

    technologies = {
        key: TechnologyLayoutInput(key=key, block=defn.block, lane=crisis[key])
        for key, defn in rendered_defs.items()
    }
    layout = compute_layout(technologies, variable_table, subgrid_width=DEFAULT_SUBGRID_WIDTH)

    overwrite_records = resolve_technology_overwrites(history, variable_table, load_overwrite_overrides())

    loc_configs = default_loc_source_configs(vendor_root)
    loc_files: list[tuple[str, object]] = []
    for config in loc_configs:
        for path in config.resolve("english"):
            loc_files.append((config.name, parse_loc_file(path)))
    loc_table = build_table("english", loc_files)

    profiles = all_profiles_in_canonical_order()

    icon_overrides = load_icon_overrides()
    tech_sheets, tech_icon_result = build_atlases(
        "technology", vendor_root, overrides_path=None, rendered_keys=rendered_keys
    )
    perk_sheets, perk_icon_result = build_atlases("ascension_perk", vendor_root)

    typed_edges, _edge_diagnostics = compute_typed_edges({k: d.block for k, d in rendered_defs.items()})

    icon_refs = _icon_ref_map(tech_icon_result, tech_sheets)
    swap_icon_refs, inherited_swap_icons = _swap_icon_ref_map(tech_icon_result, tech_sheets, icon_refs)

    return BuildContext(
        vendor_root=vendor_root, rendered_keys=rendered_keys, rendered_defs=rendered_defs,
        variable_table=variable_table, crisis=crisis, layout=layout,
        overwrite_records=overwrite_records, loc_table=loc_table, profiles=profiles,
        tech_icon_result=tech_icon_result, perk_icon_result=perk_icon_result,
        tech_sheets=tech_sheets, perk_sheets=perk_sheets, typed_edges=typed_edges,
        icon_refs=icon_refs, swap_icon_refs=swap_icon_refs, inherited_swap_icons=inherited_swap_icons,
        sources_present=sources_present,
    )


def _tile_location_map(tech_sheets: list) -> dict[str, dict]:
    """resolved icon name -> IconRef dict, from the packed atlas sheets."""
    tile_location: dict[str, dict] = {}
    for sheet in tech_sheets:
        for tile in sheet.tiles:
            tile_location[tile.name] = {
                "sheet": sheet.sheet_name, "x": tile.x, "y": tile.y, "width": tile.width, "height": tile.height,
            }
    return tile_location


def _icon_ref_map(tech_icon_result: object, tech_sheets: list) -> dict[str, dict]:
    """technology key -> IconRef dict, from the filtered technology atlas sheets. Swap
    candidates (`"<owner>/swap:<name>"` keys) are excluded here -- the base dataset shows exactly
    one, profile-invariant icon per node; see `_swap_icon_ref_map` for swap-specific lookup."""
    resolved_name_by_key = {}
    for candidate, _path, _channel in tech_icon_result.resolved:
        if "/swap:" not in candidate.key:
            resolved_name_by_key[candidate.key] = candidate.resolved_name

    tile_location = _tile_location_map(tech_sheets)

    result = {}
    for key, resolved_name in resolved_name_by_key.items():
        loc = tile_location.get(resolved_name)
        if loc is not None:
            result[key] = loc
    return result


def _swap_icon_ref_map(
    tech_icon_result: object, tech_sheets: list, icon_refs: dict[str, dict]
) -> tuple[dict[tuple[str, str], dict], list[tuple[str, str]]]:
    """`(owner_key, swap_key) -> IconRef` for every swap candidate whose OWN icon resolved in the
    atlas, plus the list of `(owner_key, swap_key)` pairs that fell back to the owner's icon.

    `pipeline/icons/resolve.py` deliberately leaves an `inherit_icon = no` swap with no icon file
    of its own as an unresolved candidate -- redirecting it to the owner's icon at THAT layer
    would override an explicit authorial refusal (see that module's own docstring). This function
    performs the redirect at the PRESENTATION layer instead -- a swap explicitly declared its own
    icon and none exists yet, so falling back to the owner's icon is a graceful degradation for
    display purposes only, tracked in the returned inherited-pairs list (surfaced as
    `diagnostics.swapsRenderingOnInheritedIcon`) rather than done silently. A swap that never
    asked for its own icon (`inherit_icon` omitted or `yes`, resolved via the `inherit_icon`
    channel to the owner's own resolved name) is never unresolved in the first place -- it always
    resolves successfully to the same tile the owner uses -- so it never appears in the inherited
    list; only a genuine `inherit_icon = no`-and-nothing-found case does."""
    tile_location = _tile_location_map(tech_sheets)

    swap_icon_refs: dict[tuple[str, str], dict] = {}
    for candidate, _path, _channel in tech_icon_result.resolved:
        if "/swap:" not in candidate.key:
            continue
        owner_key, swap_key = candidate.key.split("/swap:", 1)
        loc = tile_location.get(candidate.resolved_name)
        if loc is not None:
            swap_icon_refs[(owner_key, swap_key)] = loc

    inherited: list[tuple[str, str]] = []
    for candidate in tech_icon_result.unresolved:
        if "/swap:" not in candidate.key:
            continue
        owner_key, swap_key = candidate.key.split("/swap:", 1)
        owner_icon = icon_refs.get(owner_key)
        if owner_icon is not None:
            swap_icon_refs[(owner_key, swap_key)] = owner_icon
            inherited.append((owner_key, swap_key))
    return swap_icon_refs, inherited


def _label_priority(key: str, reverse_prereq_count: dict[str, int], defn: TechnologyDefinition) -> int:
    priority = reverse_prereq_count.get(key, 0)
    if _bool_flag(defn.block, "is_rare"):
        priority += 5
    if _bool_flag(defn.block, "is_dangerous"):
        priority += 5
    return priority


def build_base_dataset(ctx: BuildContext) -> tuple[dict, bytes, bytes]:
    layout = ctx.layout
    icon_refs = ctx.icon_refs

    reverse_prereq_count: dict[str, int] = {}
    for e in ctx.typed_edges:
        if e.kind == "prerequisite":
            reverse_prereq_count[e.from_key] = reverse_prereq_count.get(e.from_key, 0) + 1

    key_order = sorted(ctx.rendered_keys)
    node_bytes, node_ref = pack_node_positions(layout, key_order)
    edge_bytes, edge_ref, edge_index = pack_edge_polylines(layout)

    edges_json = []
    forward: dict[str, dict[str, list[int]]] = {}
    reverse: dict[str, dict[str, list[int]]] = {}
    for i, e in enumerate(layout.edges):
        edges_json.append({
            "from": e.from_key, "to": e.to_key, "kind": e.kind, "groupId": e.group_id,
            "appliesToEmpireTypes": {}, "backward": e.backward, "bandSpan": e.band_span,
        })
        forward.setdefault(e.to_key, {}).setdefault(e.kind, []).append(i)
        reverse.setdefault(e.from_key, {}).setdefault(e.kind, []).append(i)

    technologies_json = []
    categories: set[str] = set()
    for key in key_order:
        defn = ctx.rendered_defs[key]
        node = layout.nodes[key]
        name_entry = ctx.loc_table.get(key)
        name = strip_markup(name_entry.value.raw) if name_entry else key

        tier = resolve_declared_tier(key, defn.block, ctx.variable_table)
        repeatable = is_repeatable(defn.block, ctx.variable_table)
        raw_levels = _levels_value(defn.block, ctx.variable_table) if repeatable else None
        # schema: null = unbounded ('Repeatable: infinity'), positive int = finite cap. The
        # corpus's own negative-levels convention (levels = -1) IS the unbounded signal.
        levels = None if (raw_levels is None or raw_levels < 0) else raw_levels
        category = category_of(defn.block) or ""
        categories.add(category)

        cost_assignment = _field(defn.block, "cost")
        cost = _resolve_numeric(cost_assignment.value if cost_assignment else None, ctx.variable_table)

        cost_per_level = None
        if repeatable:
            cpl_assignment = _field(defn.block, "cost_per_level")
            cost_per_level = _resolve_numeric(cpl_assignment.value if cpl_assignment else None, ctx.variable_table)

        area_assignment = _field(defn.block, "area")
        area = _scalar_text(area_assignment.value) if area_assignment else "physics"

        availability_results = evaluate_technology_for_profiles(_field(defn.block, "potential") and _field(defn.block, "potential").value, ctx.profiles)
        matrix = [availability_results[i].state for i in range(len(ctx.profiles))]

        requires_mods = [defn.source] if defn.source in ("ACOT", "AoT") else []

        icon = icon_refs.get(key, _default_icon_ref(ctx))

        technologies_json.append({
            "id": key,
            "name": name,
            "icon": icon,
            "cost": cost,
            "tier": tier,
            "laneId": node.lane_id,
            "area": area if area in ("physics", "society", "engineering") else "physics",
            "category": category,
            "crisisFaction": ctx.crisis.get(key),
            "rare": _bool_flag(defn.block, "is_rare"),
            "dangerous": _bool_flag(defn.block, "is_dangerous"),
            "repeatable": ({"levels": levels, "costPerLevel": cost_per_level} if repeatable else None),
            "requiresMods": requires_mods,
            "gates": [],
            "availabilityMatrix": matrix,
            "labelPriority": _label_priority(key, reverse_prereq_count, defn),
        })

    lane_counts: dict[str, int] = {}
    for key in key_order:
        lane_counts[layout.nodes[key].lane_id] = lane_counts.get(layout.nodes[key].lane_id, 0) + 1

    lanes_json = [
        {
            "id": lane_id, "label": lane_id,
            "crisisFaction": (None if lane_id == "Standard" else lane_id),
            "technologyCount": lane_counts.get(lane_id, 0),
        }
        for lane_id in layout.lane_ids
    ]

    tier_bands_json = [
        {"tier": ("repeatables" if b.band_id == REPEATABLES else b.band_id), "bandIndex": b.index, "label": b.label}
        for b in layout.bands
    ]

    icon_atlases_json = [
        {"name": s.sheet_name, "webp": f"{s.sheet_name}.webp", "png": f"{s.sheet_name}.png", "width": s.width, "height": s.height}
        for s in ctx.tech_sheets + ctx.perk_sheets
    ]

    manifest = _read_manifest(ctx.vendor_root)
    document = {
        "schemaVersion": SCHEMA_VERSION,
        "metadata": {
            "gigastructuresCommit": manifest.get("gigastructures_commit", "unknown"),
            "vanillaVersion": manifest.get("vanilla_version", "unknown"),
            "acotVersion": manifest.get("acot_version", "unknown"),
            "aotVersion": manifest.get("aot_version", "unknown"),
            "buildTimestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        },
        "tierBands": tier_bands_json,
        "lanes": lanes_json,
        "categories": sorted(categories),
        "iconAtlases": icon_atlases_json,
        "technologies": technologies_json,
        "edges": edges_json,
        "adjacency": {"forward": forward, "reverse": reverse},
        "geometry": {
            "nodePositions": node_ref.to_json(),
            "edgePolylines": edge_ref.to_json(),
        },
    }
    return document, node_bytes, edge_bytes


def _read_manifest(vendor_root: Path) -> dict:
    import json

    path = vendor_root / "manifest.json"
    if not path.is_file():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    mods = raw.get("mods", {})
    return {
        "gigastructures_commit": mods.get("gigastructures", {}).get("commit", "unknown"),
        "vanilla_version": raw.get("game_version", "unknown"),
        "acot_version": mods.get("acot", {}).get("workshop_id", "unknown"),
        "aot_version": mods.get("aot", {}).get("workshop_id", "unknown"),
    }


def _ancestor_research_path(key: str, prereq_of: dict[str, list[str]], costs: dict[str, float], tiers: dict[str, int]) -> dict:
    seen: set[str] = set()
    order: list[str] = []

    def visit(k: str) -> None:
        for p in prereq_of.get(k, []):
            if p not in seen:
                seen.add(p)
                visit(p)
                order.append(p)

    visit(key)
    ancestors = []
    cumulative = 0.0
    for k in order:
        cumulative += costs.get(k, 0.0)
        ancestors.append({"technologyId": k, "tier": tiers.get(k, 0), "cumulativeCost": cumulative})

    # Shortest chain by cost: cheapest single path key->...->root, picked greedily by the
    # cheapest available prerequisite at each step (P-12.9's toggle; not a general shortest-path
    # search over alternative branches, since alternative/potential-gate routes are excluded here
    # by definition -- prerequisite-only, matching the research path's own contract).
    chain: list[str] = []
    cur = key
    visited_chain = {key}
    while prereq_of.get(cur):
        candidates = [p for p in prereq_of[cur] if p not in visited_chain]
        if not candidates:
            break
        nxt = min(candidates, key=lambda p: costs.get(p, 0.0))
        chain.append(nxt)
        visited_chain.add(nxt)
        cur = nxt

    return {"ancestors": ancestors, "shortestChain": list(reversed(chain))}


def build_empire_overlay(ctx: BuildContext, profile: dict) -> dict:
    profile_index = empire_profile_index(profile)
    lock_reason_overrides = load_lock_reason_overrides()

    availability_json = {}
    swap_mappings = []
    prereq_of: dict[str, list[str]] = {k: [] for k in ctx.rendered_keys}
    costs: dict[str, float] = {}
    tiers: dict[str, int] = {}
    for e in ctx.typed_edges:
        if e.kind == "prerequisite":
            prereq_of.setdefault(e.to_key, []).append(e.from_key)

    for key, defn in ctx.rendered_defs.items():
        cost_assignment = _field(defn.block, "cost")
        costs[key] = _resolve_numeric(cost_assignment.value if cost_assignment else None, ctx.variable_table) or 0.0
        tiers[key] = resolve_declared_tier(key, defn.block, ctx.variable_table)

        potential = _field(defn.block, "potential")
        result = evaluate_technology_for_profiles(potential.value if potential else None, [profile])[0]
        reason, _needs_warning = resolve_lock_reason(key, result, lock_reason_overrides)
        availability_json[key] = {
            "state": result.state,
            "reason": (reason if result.state != AVAILABLE else None),
            "configGatedSubject": (
                _config_gated_subject(key, ctx) if result.state == CONFIG_GATED else None
            ),
        }

        # D-14: the first axis-expressible swap (declaration order) whose trigger holds for this
        # profile -- see pipeline.technology_swaps.collect_swaps's docstring on why "first
        # declared wins" is a documented modelling choice, not a confirmed game-accurate rule.
        axis_swaps = [s for s in collect_swaps(key, defn.block) if s.axis_expressible]
        active_swap = next(
            (s for s in axis_swaps if evaluate_trigger_block(s.trigger_block, profile).state == AVAILABLE),
            None,
        )
        if active_swap is not None:
            base_area_assignment = _field(defn.block, "area")
            base_area = _scalar_text(base_area_assignment.value) if base_area_assignment else "physics"
            base_category = category_of(defn.block) or ""
            area, category = _swap_area_category(active_swap, base_area, base_category)
            swap_mappings.append({
                "technologyId": key,
                "name": _swap_display_name(active_swap, ctx),
                "icon": _swap_icon(key, active_swap, ctx),
                "area": area,
                "category": category,
            })

    active_edge_ids = list(range(len(ctx.layout.edges)))  # unconstrained appliesToEmpireTypes -- see module docstring

    research_paths = {key: _ancestor_research_path(key, prereq_of, costs, tiers) for key in ctx.rendered_keys}

    return {
        "schemaVersion": SCHEMA_VERSION,
        "profile": profile,
        "availability": availability_json,
        "activeEdgeIds": active_edge_ids,
        "swapMappings": swap_mappings,
        "researchPaths": research_paths,
    }


def build_detail_payload(ctx: BuildContext, key: str) -> dict:
    defn = ctx.rendered_defs[key]
    desc_entry = ctx.loc_table.get(f"{key}_desc")
    description = strip_markup(desc_entry.value.raw) if desc_entry else ""

    repeatable = is_repeatable(defn.block, ctx.variable_table)
    cost_per_level_assignment = _field(defn.block, "cost_per_level")
    repeatable_cost_progression = None
    if repeatable and cost_per_level_assignment is not None:
        per_level = _resolve_numeric(cost_per_level_assignment.value, ctx.variable_table)
        if per_level is not None:
            levels = _levels_value(defn.block, ctx.variable_table)
            n = levels if levels else 10  # unbounded: report first 10 levels' worth, not an infinite array
            base = _resolve_numeric(_field(defn.block, "cost").value, ctx.variable_table) if _field(defn.block, "cost") else 0.0
            repeatable_cost_progression = [round((base or 0.0) + per_level * i, 2) for i in range(n)]

    record = ctx.overwrite_records.get(key)
    if record is not None and record.overwrites is not None:
        source = {"definedBy": record.defined_by, "overwrites": record.overwrites, "label": record.label}
        overwrite_diff = {"changedFields": record.changed_fields}
    else:
        source = {"definedBy": defn.source, "overwrites": None, "label": defn.source}
        overwrite_diff = None

    repository_link = _repository_link(key, defn)

    # D-14: non-axis-expressible swaps listed here (popup only), never substituted onto the card
    # or into the empire overlay -- see pipeline.technology_swaps and spec/decisions.md's D-14.
    variants = []
    for swap in collect_swaps(key, defn.block):
        if swap.axis_expressible:
            continue
        condition_text = (
            describe_trigger_block(swap.trigger_block) if swap.trigger_block is not None else "always"
        )
        variants.append({
            "name": _swap_display_name(swap, ctx),
            "icon": _swap_icon(key, swap, ctx),
            "conditionText": condition_text,
        })

    weight_assignment = _field(defn.block, "weight")
    base_weight = _resolve_numeric(weight_assignment.value if weight_assignment else None, ctx.variable_table) or 0.0
    modifiers = []
    wm = _field(defn.block, "weight_modifier")
    if wm is not None and isinstance(wm.value, Block):
        factor_assignment = _field(wm.value, "factor")
        factor = _resolve_numeric(factor_assignment.value if factor_assignment else None, ctx.variable_table)
        if factor is not None:
            condition_items = [i for i in wm.value.items if isinstance(i, Assignment) and i.key_name != "factor"]
            condition_text = describe_condition(condition_items[0]) if condition_items else "always"
            modifiers.append({"factor": factor, "conditionText": condition_text})

    return {
        "schemaVersion": SCHEMA_VERSION,
        "technologyId": key,
        "description": description,
        "repeatableCostProgression": repeatable_cost_progression,
        "source": source,
        "overwriteDiff": overwrite_diff,
        "repositoryLink": repository_link,
        "variants": variants,
        "weight": {"base": base_weight, "modifiers": modifiers},
    }


def _repository_link(key: str, defn: TechnologyDefinition) -> dict:
    if defn.source == "Gigastructural Engineering":
        rel = Path(defn.document_path)
        try:
            rel = rel.relative_to(rel.parents[len(rel.parents) - 1])
        except Exception:
            pass
        commit = "0f1f2b024f43249dc7dfe132fe7c0e4201398ef5"
        url = f"https://github.com/Pouchkinn-s-Gigastructures/Gigastructures/blob/{commit}/{Path(defn.document_path).name}#L{defn.line}"
        return {
            "kind": "gigastructures-permalink", "url": url,
            "lineRange": {"file": Path(defn.document_path).name, "startLine": defn.line, "endLine": defn.line},
        }
    if defn.source in ("ACOT", "AoT"):
        workshop_id = _WORKSHOP_IDS[defn.source]
        return {
            "kind": "steam-workshop",
            "url": f"https://steamcommunity.com/sharedfiles/filedetails/?id={workshop_id}",
            "lineRange": None,
        }
    slug = key.removeprefix("tech_").replace("_", "_")
    return {"kind": "stellaris-wiki", "url": f"https://stellaris.paradoxwikis.com/{slug}", "lineRange": None}


def build_search_index(ctx: BuildContext, base_dataset: dict, detail_payloads: dict[str, dict]) -> dict:
    entries = []
    for tech in base_dataset["technologies"]:
        key = tech["id"]
        text = f"{tech['name']} {key} {detail_payloads.get(key, {}).get('description', '')}"
        tokens = sorted(set(t for t in re.split(r"[^a-z0-9]+", text.lower()) if t))
        entries.append({"technologyId": key, "tokens": tokens})
    return {"schemaVersion": SCHEMA_VERSION, "entries": entries}


def build_diagnostics(ctx: BuildContext) -> dict:
    technologies_for_survey = {k: (_field(d.block, "potential").value if _field(d.block, "potential") else None) for k, d in ctx.rendered_defs.items()}
    survey = survey_uncertainty(technologies_for_survey, ctx.profiles)
    d10_section = build_d10_diagnostics_section(survey, ctx.profiles)

    variable_history = collect_variable_definitions(
        _load_expanded(ctx.vendor_root, "scripted_variables", collect_scripts(_script_entries(ctx.vendor_root)))
    )
    technology_history_all = collect_technology_definitions(
        _load_expanded(ctx.vendor_root, "technology", collect_scripts(_script_entries(ctx.vendor_root)))
    )
    variable_records = resolve_variable_overwrites(variable_history, technology_history_all)
    overwrite_report = build_overwrite_report(ctx.overwrite_records, variable_records)

    lock_reason_overrides = load_lock_reason_overrides()
    missing_lock_reasons: set[str] = set()
    for key, defn in ctx.rendered_defs.items():
        potential = _field(defn.block, "potential")
        for profile in ctx.profiles:
            result = evaluate_technology_for_profiles(potential.value if potential else None, [profile])[0]
            if result.state == LOCKED:
                _reason, needs_warning = resolve_lock_reason(key, result, lock_reason_overrides)
                if needs_warning:
                    missing_lock_reasons.add(key)

    alt_gaps = compute_alternative_only_gaps(technology_history_all)

    return {
        "schemaVersion": SCHEMA_VERSION,
        **d10_section,
        "missingInlineScriptParameterCount": {"current": 0, "previous": 0},
        "tierPromotions": [],
        "swapsRenderingOnInheritedIcon": [
            {"technologyId": owner_key, "swapKey": swap_key}
            for owner_key, swap_key in sorted(ctx.inherited_swap_icons)
        ],
        "unrecognisedGatePatterns": [],
        "missingLockReasonOverrides": sorted(missing_lock_reasons),
        "unresolvedTriggers": [],
        "unresolvedModDependencies": sorted(alt_gaps),
        "overwriteReport": overwrite_report,
        **_reduced_vendor_diagnostics(ctx),
    }


def _reduced_vendor_diagnostics(ctx: BuildContext) -> dict:
    """`vendorSourcesLoaded`/`placeholderTechnologiesAbsent`/
    `vanillaTechnologiesRevertedFromAcotOverwrite` -- fires (non-empty) only when ACOT and/or AoT
    is absent from this build. Deliberately loud: a build missing ACOT/AoT is plausible and
    self-consistent (977 rendered nodes, zero dangling edges, zero alternative-only gaps -- see
    spec/decisions.md's vendoring-automation investigation) precisely because nothing else looks
    broken. See `PLACEHOLDER_TECHNOLOGIES_REQUIRING_ACOT_AOT`/`VANILLA_TECHNOLOGIES_ACOT_OVERWRITES`
    above for why these two lists are maintained constants, not derived from the reduced corpus."""
    missing_sources = [s for s in ("ACOT", "AoT") if s not in ctx.sources_present]

    placeholder_absent = []
    reverted = []
    if missing_sources:
        placeholder_absent = [
            {"technologyId": key, "requiresMod": mod}
            for key, mod in sorted(PLACEHOLDER_TECHNOLOGIES_REQUIRING_ACOT_AOT.items())
            if mod in missing_sources
        ]
    if "ACOT" in missing_sources:
        reverted = [
            {"technologyId": key, "contentDiffersFromOverwrite": differs}
            for key, differs in sorted(VANILLA_TECHNOLOGIES_ACOT_OVERWRITES.items())
        ]

    return {
        "vendorSourcesLoaded": list(ctx.sources_present),  # load order, not alphabetical
        "placeholderTechnologiesAbsent": placeholder_absent,
        "vanillaTechnologiesRevertedFromAcotOverwrite": reverted,
    }
