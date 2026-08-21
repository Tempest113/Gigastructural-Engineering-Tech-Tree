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

- ~~`appliesToEmpireTypes` is emitted unconstrained on every edge~~ **Closed** (Item 1 session):
  `pipeline.edge_constraints.compute_potential_gate_constraints` now populates real per-edge
  constraints for `potential-gate` edges (`prerequisite`/`alternative` are unconstrained by
  construction — see that module's docstring). `activeEdgeIds` now genuinely varies per profile
  (980–983 of 984, real corpus) instead of the previous constant 984/984 — see that module's
  docstring for the algorithm and why naive sensitivity was rejected in favour of an
  axis-fact-only criterion (`giga_tech_disco_moon`'s two gate edges are the case that mattered:
  they must never go inactive just because an unrelated fact is unresolvable).
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
  chooses the stripped half only for MARKUP specifically. Separately (later session), `$key$`
  loc-variable tokens embedded in description text ARE now fully resolved, same as `name` — see
  `_resolve_loc_tokens`/`_require_resolved` and PART 2's survey in this session's writeup.
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
    set_perk_potentials,
    survey_uncertainty,
)
from .clausewitz import parse_file
from .clausewitz.nodes import Assignment, Block, Identifier, NumberLiteral, StringLiteral, VariableReference
from .crisis_faction import CRISIS_FACTIONS, classify_crisis_factions
from .crisis_faction_flags import load_flag_overrides as load_crisis_flag_overrides
from .crisis_faction_overrides import load_overrides as load_crisis_overrides
from .dataset_schema.empire_profile import (
    all_profiles_in_canonical_order,
    build_empire_profile_axes,
    empire_profile_index,
)
from .edge_constraints import compute_potential_gate_constraints, edge_active_for_profile
from .edges import compute_typed_edges
from .gate_patterns import GATE_KIND_PRIORITY, classify_gates, order_gates
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
from .name_overrides import load_name_overrides
from .overwrite_overrides import load_overrides as load_overwrite_overrides
from .overwrites import (
    TechnologyDefinition,
    build_overwrite_report,
    collect_technology_definitions,
    collect_variable_definitions,
    ordered_prerequisites,
    resolve_technology_overwrites,
    resolve_variable_overwrites,
)
from .rendering_scope import compute_alternative_only_gaps, compute_off_tree_prerequisites, rendered_technology_keys
from .scripted_triggers import expand_scripted_triggers, load_scripted_trigger_catalog
from .technology_swaps import TechnologySwap, collect_swaps
from .trigger_text import ReasonCategory, describe_condition, describe_trigger_block
from .variables import build_variable_table

SCHEMA_VERSION = "1.0.0"


class UnresolvedLocalisationTokenError(Exception):
    """CLAUDE.md's Rules: 'the build fails rather than emitting a partial dataset... missing
    localisation for displayed strings.' Raised when a displayed string still contains a literal
    `$...$` token after `_resolve_loc_tokens` -- e.g. a token absent from every loaded source's
    loc table, or a chain deeper than `_LOC_TOKEN_MAX_HOPS` -- OR when a technology's `name`
    resolves to the exact same string as its own raw technology key with no override on file
    (found this session, by reviewing a real rendered screenshot: `giga_tech_aeternite_weaponry`'s
    loc entry genuinely exists, but its VALUE is verbatim its own KEY -- the mod author never
    wrote a real display name. Previously silently rendered the internal key as if it were the
    technology's name, since it contains no `$...$` token for the OTHER check above to catch --
    see `pipeline.name_overrides` for the reviewed-override mechanism this now requires instead).
    Never silently emitted raw (that was the previous, undetected behaviour that let
    `$PLANET_LANCE_BLOKKAT$`/`$waystation_plural$`-shaped strings, and separately a bare
    key-as-name, reach the rendered card -- see this session's survey). Exactly 1 real occurrence
    across all 980 rendered technologies' names at time of writing (`giga_tech_aeternite_weaponry`,
    covered by `config/name_overrides.txt`) -- this is a tripwire for a future corpus change on
    every OTHER technology, not a check expected to fire for any of them today."""

    def __init__(self, technology_key: str, field_name: str, raw_text: str):
        self.technology_key = technology_key
        self.field_name = field_name
        self.raw_text = raw_text
        super().__init__(
            f"{technology_key}: {field_name} still contains an unresolved localisation token "
            f"after resolution: {raw_text!r}"
        )


def _require_resolved(text: str, technology_key: str, field_name: str, ctx: "BuildContext") -> str:
    """Resolves `text` via `_resolve_loc_tokens` and hard-fails (`UnresolvedLocalisationTokenError`)
    rather than emitting it with a raw `$...$` token still inside -- the check PART 2 of this
    session's prompt asked for. Deliberately proven capable of firing before being trusted: see
    `tests/test_dataset_emit.py::test_unresolved_localisation_token_in_a_name_fails_the_build`,
    which feeds this a token absent from the loc table and asserts the raise, not just a clean run
    on the real corpus (CLAUDE.md's rule: 'a clean run proves nothing until the detector is shown
    capable of a dirty one')."""
    resolved = _resolve_loc_tokens(text, ctx)
    if resolved is None:
        raise UnresolvedLocalisationTokenError(technology_key, field_name, text)
    return resolved


def _resolve_technology_name(key: str, ctx: "BuildContext", name_overrides: dict) -> str:
    """Extracted to module level (was a `build_base_dataset`-local closure) so `build_diagnostics`
    (Item 1's dev health monitor, later session) can resolve the same real localised name a
    technology's card shows, rather than a second, independent resolution that could drift."""
    name_entry = _vanilla_loc_entry(key, ctx) if key in VANILLA_LOC_AND_ICON_PRECEDENCE_KEYS else ctx.loc_table.get(key)
    raw_name = strip_markup(name_entry.value.raw) if name_entry else key
    name = _require_resolved(raw_name, key, "name", ctx)
    if name == key:
        override = name_overrides.get(key)
        if override is None:
            raise UnresolvedLocalisationTokenError(
                key, "name", f"resolves to its own raw key {key!r} -- no real localisation exists; "
                f"see config/name_overrides.txt"
            )
        name = override.name
    return name


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
# `PLACEHOLDER_TECHNOLOGIES_REQUIRING_ACOT_AOT`: the real technologies whose `requiresMods` names
# ACOT/AoT in the full build (spec/decisions.md's vendoring-automation investigation). These are
# Gigastructures' own "supertensile alternate" content (`giga_17_alternative_mega_build.txt`) --
# the actual reason ACOT/AoT are vendored at all: they show the TRUE prerequisites of those
# alternates, not a cosmetic extra.
#
# D-18 (spec/decisions.md, this session): narrowed from 7 to 4. The original 7 included 3
# technologies (`tech_dark_matter_power_core_enig`, `tech_mine_dark_energy`,
# `tech_precursor_design`) reached only via ACOT's OWN internal prerequisite chains -- under the
# ORIGINAL full-transitive-closure rule these rendered whenever ACOT was loaded, so removing ACOT
# made them disappear, exactly the "placeholder absent" shape this list exists to report. D-18's
# depth-1 closure means those 3 are no longer in P-16's rendering scope AT ALL, regardless of
# whether ACOT is loaded -- there is no "placeholder absent" transition to report for them any
# more, since they're never present to begin with. Only the 4 depth-1 members remain in this
# list. Re-verified by
# `tests/test_dataset_emit.py::test_placeholder_technologies_constant_matches_full_corpus`
# whenever the full corpus is available.
PLACEHOLDER_TECHNOLOGIES_REQUIRING_ACOT_AOT: dict[str, str] = {
    "tech_dark_matter_power_core_ae": "ACOT",
    "tech_dark_matter_power_core_dm": "ACOT",
    "tech_dark_matter_power_core_se": "ACOT",
    "tech_civil_phanon_application": "AoT",
}

# `VANILLA_TECHNOLOGIES_ACOT_OVERWRITES`: the 4 vanilla technology keys ACOT redefines in the
# full build (P-15). Without ACOT loaded, these revert to their vanilla content and REAPPEAR in
# the rendered set -- P-16's closure had excluded their ACOT-overwritten form, not their vanilla
# one (pre-D-18 figures, spec/decisions.md's vendoring-automation investigation: 980 - 7 + 4 = 977,
# not 973; see `_reduced_vendor_diagnostics` for the post-D-18 reduced-build arithmetic, which
# lands on 977 again by a different, unrelated computation). User-
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

# Item 6 (later session): the DIFFERENT, previously-undiscovered case -- a technology whose
# BLOCK is won by Vanilla (P-15 never overwrites it; not the same set as
# `VANILLA_TECHNOLOGIES_ACOT_OVERWRITES` above, which is about a technology-BLOCK overwrite) but
# whose NAME/DESCRIPTION localisation key, and icon filename, is REDEFINED by a later-loaded
# source (ACOT in every real corpus case) purely because localisation/icon resolution is its own
# separate last-source-wins table, keyed by string identity, with no awareness of which source
# actually won the technology's own block. User-reported symptom: `tech_dark_matter_propulsion`
# rendered as ACOT's "Dark Matter Dimensional Thruster" instead of vanilla's own "Dark Matter
# Propulsion". Surveyed against the full corpus (not assumed): of 673 rendered technologies whose
# technology BLOCK winner is Vanilla, exactly these 3 also have a name/description loc key AND an
# icon file both redefined, with DIFFERENT content, by a later source -- every other Vanilla-won
# technology's name/description/icon (even where a later source happens to also define the same
# loc key) either has no such redefinition at all, or redefines it to IDENTICAL text (a harmless
# re-declaration, not a real divergence). `_resolve_technology_name`/`build_detail_payload`'s
# description resolution and `build_atlases`'s technology-icon call (both in this module) look up
# these 3 keys against Vanilla's OWN loc entries/icon file specifically, never the cross-source
# merged table, per CLAUDE.md's "Localisation precedence" rule. This is INDEPENDENT of and does
# NOT affect `VANILLA_TECHNOLOGIES_ACOT_OVERWRITES`/`PLACEHOLDER_TECHNOLOGIES_REQUIRING_ACOT_AOT`
# above -- those describe what happens when ACOT is ABSENT from the build; this fix instead
# changes what a technology's card shows in the FULL (ACOT-present) build, which is the tree this
# project actually deploys.
# Item 4a (later session): `on_enabled -> add_research_option` grants -- a technology this
# evaluator's ordinary `potential`/gate machinery has NO reference to at all, made available
# ONLY by an ascension perk's effect block firing once. Surveyed against the real corpus (not
# hardcoded blind): `ap_galactic_wonders`'s (Gigastructures-overwritten) `on_enabled` grants
# `tech_ring_world`, `tech_dyson_sphere`, `tech_mega_engineering`, `tech_matter_decompressor` --
# but only the first three are structurally UNREACHABLE any other way (unconditional
# `weight_modifier = { factor = 0 }`, confirmed by the earlier "Ascension-perk grants" survey
# recorded in CLAUDE.md's Open Items). `tech_mega_engineering` remains genuinely reachable by the
# ordinary weighted-draw route too (it has no such zero-weight block), so treating it as
# perk-gated here would overstate a real requirement -- deliberately excluded, matching the prior
# survey's own recommendation. `ap_gigastructural_constructs`'s on_enabled grants a LARGER set
# (giga_tech_hrae_mc, giga_tech_ringworld_behemoth, giga_tech_matrioshka_brain_1,
# giga_tech_quasi_stellar_1, giga_tech_birch_world_1, giga_tech_lunar_assembly,
# giga_tech_war_system_1, giga_tech_supermassive_ehof) -- checked and found to need NO new
# machinery: every one of those already carries `has_ascension_perk = ap_gigastructural_constructs`
# directly in its own `potential` block (confirmed by Item 2's perk-lockout survey, which already
# reports them as perk-gated), so `add_research_option` there is the game's real mechanism
# matching what this pipeline's ordinary gate detection already sees, not a hidden second path.
ADD_RESEARCH_OPTION_PERK_GRANTS: dict[str, str] = {
    "tech_ring_world": "ap_galactic_wonders",
    "tech_dyson_sphere": "ap_galactic_wonders",
    "tech_matter_decompressor": "ap_galactic_wonders",
}

VANILLA_LOC_AND_ICON_PRECEDENCE_KEYS = frozenset({
    "tech_dark_matter_power_core",
    "tech_dark_matter_propulsion",
    "tech_dark_matter_deflector",
})


def _vanilla_loc_entry(key: str, ctx: "BuildContext"):
    """The Vanilla-sourced `LocEntry` for `key`, if Vanilla ever defines it -- ignoring whatever
    a later-loaded source redefined the same key to. Used only for
    `VANILLA_LOC_AND_ICON_PRECEDENCE_KEYS` (Item 6); every other lookup keeps using
    `ctx.loc_table.get`, the ordinary cross-source merged view."""
    for entry in ctx.loc_table.history.get(key, []):
        if entry.source == "stellaris":
            return entry
    return None


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


_POTENTIAL_BOOLEAN_WRAPPERS = {"AND", "OR", "NOT", "NOR"}


def _potential_mod_requirements(block: Block) -> list[str]:
    """Item 2d (user domain call): a technology whose `potential` structurally requires
    `has_acot = yes` and/or `has_global_flag = has_aot_mod` is not ADDED by ACOT/AoT (its own
    `defn.source` is Gigastructural Engineering), but is only ACCESSIBLE with that mod's content
    present -- Gigastructures' own "supertensile alternate" pattern
    (`giga_17_alternative_mega_build.txt`). These carry the same `requiresMods` badge as a
    technology whose own source IS ACOT/AoT, rather than resolving `uncertain`. Same scope
    discipline as `pipeline.edges._scoped_has_technology` (only descend AND/OR/NOT/NOR; an opaque
    sub-scope like `count_country`/`weight_modifier` is never searched) -- real corpus: exactly 4
    technologies (`giga_tech_amb_supertensiles_acot_alpha/sigma/delta/phanon`), `alpha`/`sigma`/
    `delta` requiring ACOT only, `phanon` requiring both (AoT depends on ACOT)."""
    potential = _field(block, "potential")
    if potential is None or not isinstance(potential.value, Block):
        return []
    found: set[str] = set()

    def walk(node: Block) -> None:
        for item in node.items:
            if not isinstance(item, Assignment):
                continue
            if item.key_name == "has_acot":
                found.add("ACOT")
            elif item.key_name == "has_global_flag" and _scalar_text(item.value) == "has_aot_mod":
                found.add("AoT")
            elif item.key_name.upper() in _POTENTIAL_BOOLEAN_WRAPPERS and isinstance(item.value, Block):
                walk(item.value)

    walk(potential.value)
    return sorted(found)


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


def _resolve_cost(value, variable_table) -> float | None:
    """`cost` specifically -- a superset of `_resolve_numeric` that also handles the real corpus's
    third shape (10/980 rendered nodes, all vanilla 'cosmic storm' technologies, e.g.
    `tech_storm_manipulation`): `cost = { factor = @variable  inline_script = { ... } }`, a Block,
    where `_resolve_numeric` previously saw a Block and returned None unconditionally -- silently
    treating a real, resolvable cost as unresolvable (the same mechanism as the Stage 1
    tier-source bug: the field exists, in a shape the reader doesn't recognise, and the failure is
    silent). Survey (this session): all 10 block-form occurrences share the identical shape --
    `factor` is always present and always a plain `@variable` reference that resolves cleanly; the
    `inline_script`-expanded sibling field (a `modifier` block, in every real case) is a set of
    Galactic Community resolution-conditional multipliers (0.2x-1.8x, checked against
    `technologies/cosmic_storms_technologies_cost_modifiers.txt`) -- live diplomatic state, not
    statically resolvable, and deliberately NOT folded in here: per D-4/this project's existing
    cost-display rationale, `factor` (the base/declared cost) is the one figure the card can state
    truthfully regardless of which resolutions are active, the same reasoning already applied to
    `costPerLevel` for repeatables. A Block with no resolvable `factor` (none exist in the real
    corpus today, but the policy is never to guess) still resolves to `None`, same as before."""
    if isinstance(value, Block):
        factor_assignment = _field(value, "factor")
        if factor_assignment is None:
            return None
        return _resolve_numeric(factor_assignment.value, variable_table)
    return _resolve_numeric(value, variable_table)


_MARKUP_RE = re.compile(r"§.|£[^£]*£")


def strip_markup(raw: str) -> str:
    """P-12.1's stripped half: drop `§X`/`§!` colour codes and `£icon£` tokens, leave the rest
    verbatim. See module docstring's scope-limitation note -- this does not resolve embedded
    `$VAR$` tokens to real values."""
    return _MARKUP_RE.sub("", raw)


_MANAGEMENT_PROTOCOLS_SUFFIX = " Management Protocols"
_LOC_TOKEN_RE = re.compile(r"\$([^$]+)\$")
# Measured real max (later session, once every displayed string -- not just configGatedSubject --
# started going through this resolver): true nesting depth across all 980 rendered technology
# NAMES is 3 hops, across all 980 DESCRIPTIONS is 4 hops, both under the per-pass "resolve every
# sibling token, not just the first" algorithm below. 6 is that measured max plus headroom, not a
# guess.
_LOC_TOKEN_MAX_HOPS = 6


def _resolve_loc_tokens(text: str, ctx: "BuildContext") -> str | None:
    """Resolves Stellaris localisation's own `$key$` variable-substitution syntax against the
    full cross-source `ctx.loc_table` (vanilla, Gigastructures, ACOT, AoT, in load order) --
    ordinary static string substitution, corrected from an earlier, uncorrected assumption that
    a `$...$` token in a technology's own name was an unresolvable Stellaris runtime name-pool
    reference (see `_config_gated_subject`'s docstring for the corpus evidence).

    **Resolves every sibling token in the current text on each pass, not just the first**
    (corrected, later session, from an earlier version of this function that replaced only the
    first `$...$` match per hop). That earlier version silently needed one extra hop per SIBLING
    token at the same nesting level, not just per level of real nesting depth -- invisible while
    this function's only caller was `_config_gated_subject` (every one of its 50 real chains
    happens to carry at most one token per level), but a real bug once technology NAMES started
    resolving through this same function: `tech_civilian_arkship`'s name chains
    `$civilian_arkship_tier_1_plural$` -> `$civilian_arkship_name_plural$` ->
    `$civilian_arkship_class$ $arkship_cap_plural$` -- two SIBLING tokens on the same line, at the
    same nesting level -- which the old first-match-only algorithm could not resolve within any
    reasonable hop budget (it would need one extra hop per sibling, forever, for a string with N
    siblings at one level). Every occurrence in the current text is substituted in one `re.sub`
    pass instead, so hop count now tracks real nesting depth only.

    Bounded to `_LOC_TOKEN_MAX_HOPS` hops so a cyclic or unexpectedly deep reference can't loop
    forever. Returns None -- never a partial or guessed string -- if any token in the text can't
    be found in the loc table, or the text still contains an unresolved token after the hop
    limit."""
    for _ in range(_LOC_TOKEN_MAX_HOPS):
        if _LOC_TOKEN_RE.search(text) is None:
            return text
        missing = False

        def repl(match: re.Match) -> str:
            nonlocal missing
            entry = ctx.loc_table.get(match.group(1))
            if entry is None:
                missing = True
                return match.group(0)
            return strip_markup(entry.value.raw)

        text = _LOC_TOKEN_RE.sub(repl, text)
        if missing:
            return None
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
    # D-18 off-tree-prerequisite surfacing (Item 3, reconciliation session 3): technology key ->
    # list of off-tree prerequisite KEYS it names (never rendered as a node under D-18's depth-1
    # closure). Empty list for the 974/977 unaffected technologies. Grouped once here rather than
    # re-scanning `compute_off_tree_prerequisites`'s flat pair list per technology in
    # `build_detail_payload`.
    off_tree_prerequisites: dict[str, list[str]]
    # Full (all-source, not just rendered) technology history -- needed to resolve an off-tree
    # prerequisite's own localised NAME, since it has no TechnologyDefinition in `rendered_defs`
    # (that dict is rendered-keys-only by construction).
    history: dict[str, list[TechnologyDefinition]]
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
    # P-3 gate classification: ascension-perk id -> IconRef dict, same shape/lookup pattern as
    # `icon_refs` (technology key -> IconRef) but over the unfiltered perk atlas sheets -- see
    # `pipeline/icons/build.py`'s `filter_result_to_rendered_scope` docstring for why the perk
    # atlas is deliberately never filtered by P-16's technology rendering-scope closure.
    perk_icon_refs: dict
    sources_present: list[str]
    # (from_key, to_key) -> appliesToEmpireTypes, `potential-gate` edges only, absent entries
    # unconstrained -- see pipeline.edge_constraints's module docstring for the algorithm and why
    # naive sensitivity was rejected.
    edge_constraints: dict
    # rendered technology key -> its `potential` block, `pipeline.scripted_triggers`-expanded
    # (None if the technology has no `potential` at all). Computed ONCE here and reused by every
    # availability-evaluation call site in this module -- never re-derived per call, so there is
    # exactly one source of truth for "what does this technology's potential actually say," the
    # same discipline CLAUDE.md's "pipeline owns all geometry" rule already establishes for
    # layout, applied here to trigger content instead.
    expanded_potentials: dict[str, Block | None]
    # P-12.9 (research path, a later session): every rendered technology's own BASE (unswapped)
    # display name, resolved exactly once here via `_resolve_technology_name` -- the same
    # resolution `build_base_dataset`'s own `resolved_names` local used to compute independently
    # per build. Hoisted onto `ctx` so `build_empire_overlay` (called once PER PROFILE, unlike
    # `build_base_dataset`) can look up a research-path ancestor's name without re-resolving
    # localisation 12 times over; `build_base_dataset` now reads this field instead of
    # recomputing it, so there is exactly one source of truth for "what name does this technology
    # resolve to," matching CLAUDE.md's "pipeline owns all geometry" discipline applied to name
    # resolution instead.
    resolved_names: dict[str, str]


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

    trigger_catalog = load_scripted_trigger_catalog(vendor_root, scripts, _source_roots(vendor_root))
    expanded_potentials = {
        key: expand_scripted_triggers(_field(defn.block, "potential") and _field(defn.block, "potential").value, trigger_catalog)
        for key, defn in rendered_defs.items()
    }

    # Item 2 (later session): registers every ascension perk's own winning `potential` block so
    # `has_ascension_perk` leaves can resolve a real LOCKED result when the referenced perk is
    # axis-restricted (e.g. Galactic Wonders is nomadic-empire-impossible) -- see
    # pipeline.availability's module docstring for the corrected rule. `collect_technology_
    # definitions` is generic over any block-shaped top-level key, not technology-specific despite
    # the name, so it applies unchanged to `common/ascension_perks`; whole-key last-source-wins
    # matches the same overwrite semantics used for technologies.
    perk_docs = _load_expanded(vendor_root, "ascension_perks", scripts)
    perk_history = collect_technology_definitions(perk_docs)
    perk_potentials = {
        key: expand_scripted_triggers(
            _field(occurrences[-1].block, "potential") and _field(occurrences[-1].block, "potential").value,
            trigger_catalog,
        )
        for key, occurrences in perk_history.items()
    }
    set_perk_potentials(perk_potentials)

    crisis = classify_crisis_factions(rendered_defs, load_crisis_overrides(), load_crisis_flag_overrides())

    technologies = {
        key: TechnologyLayoutInput(key=key, block=defn.block, faction=crisis[key])
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
        "technology", vendor_root, overrides_path=None, rendered_keys=rendered_keys,
        source_priority_overrides={key: "stellaris" for key in VANILLA_LOC_AND_ICON_PRECEDENCE_KEYS},
    )
    perk_sheets, perk_icon_result = build_atlases("ascension_perk", vendor_root)

    typed_edges, _edge_diagnostics = compute_typed_edges({k: d.block for k, d in rendered_defs.items()})
    edge_constraints = compute_potential_gate_constraints(rendered_defs, typed_edges, profiles)

    icon_refs = _icon_ref_map(tech_icon_result, tech_sheets)
    swap_icon_refs, inherited_swap_icons = _swap_icon_ref_map(tech_icon_result, tech_sheets, icon_refs)
    # P-3 gate classification: `_icon_ref_map`'s logic (candidate.key -> tile location, swap
    # candidates excluded) is not actually technology-specific -- reused as-is for the
    # ascension-perk atlas so a gate badge's icon comes from the same already-atlased sheets a
    # rendered technology's icon comes from, never a manually-maintained path (P-3's acceptance
    # criteria).
    perk_icon_refs = _icon_ref_map(perk_icon_result, perk_sheets)

    off_tree_prerequisites: dict[str, list[str]] = {}
    for owner_key, prereq_key in compute_off_tree_prerequisites(history):
        off_tree_prerequisites.setdefault(owner_key, []).append(prereq_key)

    ctx = BuildContext(
        vendor_root=vendor_root, rendered_keys=rendered_keys, rendered_defs=rendered_defs,
        variable_table=variable_table, crisis=crisis, layout=layout,
        overwrite_records=overwrite_records, loc_table=loc_table, profiles=profiles,
        tech_icon_result=tech_icon_result, perk_icon_result=perk_icon_result,
        tech_sheets=tech_sheets, perk_sheets=perk_sheets, typed_edges=typed_edges,
        icon_refs=icon_refs, swap_icon_refs=swap_icon_refs, inherited_swap_icons=inherited_swap_icons,
        perk_icon_refs=perk_icon_refs, edge_constraints=edge_constraints,
        sources_present=sources_present, off_tree_prerequisites=off_tree_prerequisites, history=history,
        expanded_potentials=expanded_potentials, resolved_names={},
    )
    name_overrides = load_name_overrides()
    ctx.resolved_names = {key: _resolve_technology_name(key, ctx, name_overrides) for key in rendered_keys}
    return ctx


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
        applies_to = ctx.edge_constraints.get((e.from_key, e.to_key, e.kind), {})
        edges_json.append({
            "from": e.from_key, "to": e.to_key, "kind": e.kind, "groupId": e.group_id,
            "appliesToEmpireTypes": applies_to, "backward": e.backward, "bandSpan": e.band_span,
        })
        forward.setdefault(e.to_key, {}).setdefault(e.kind, []).append(i)
        reverse.setdefault(e.from_key, {}).setdefault(e.kind, []).append(i)

    # Resolved once, up front, for every rendered technology -- reused both for the technology's
    # own "name" field below AND for a technology-kind gate's label (P-3: a has_technology gate's
    # target is always itself a rendered technology, 17/17 real distinct targets confirmed by the
    # gate-classification survey, so it already goes through this exact resolution path; a second,
    # independent resolution during gate-building would risk drifting from the target's own
    # displayed name).
    resolved_names: dict[str, str] = ctx.resolved_names

    def _perk_gate_label(perk_id: str) -> str:
        entry = ctx.loc_table.get(perk_id)
        raw = strip_markup(entry.value.raw) if entry else perk_id
        name = _require_resolved(raw, perk_id, "gate label (ascension perk)", ctx)
        if name == perk_id:
            raise UnresolvedLocalisationTokenError(
                perk_id, "gate label (ascension perk)",
                f"resolves to its own raw id {perk_id!r} -- no real localisation exists"
            )
        return name

    def _trait_gate_label(ref_id: str) -> str:
        # Item 3 ("path to zero uncertain" follow-up): the same loc-lookup pattern as
        # _perk_gate_label above, for an origin/ethics-or-civic gate's target id (e.g.
        # `origin_wilderness` -> "Wilderness", `civic_machine_assimilator` -> "Driven
        # Assimilator"). Every real target confirmed to resolve during this item's own survey.
        entry = ctx.loc_table.get(ref_id)
        raw = strip_markup(entry.value.raw) if entry else ref_id
        name = _require_resolved(raw, ref_id, "gate label (origin/ethics/civic)", ctx)
        if name == ref_id:
            raise UnresolvedLocalisationTokenError(
                ref_id, "gate label (origin/ethics/civic)",
                f"resolves to its own raw id {ref_id!r} -- no real localisation exists"
            )
        return name

    def _downgrade_dangling_alternative(gates: list[dict]) -> list[dict]:
        """Item 7a (later session): the user reported Birch World showing a single gate reading
        "or: Vast Expanses" -- an alternative with no sibling to be alternative to. The OR-context
        gate fix (Item 4, earlier) marks a leaf `alternative` whenever it sits inside a real
        source `OR`, but that OR's OTHER real branches are frequently non-gate-shaped conditions
        (Birch World's own sibling is `any_owned_planet = { ... district check ... }`, never a
        gate this registry tracks) -- when the emitted gates LIST ends up with exactly one entry
        and it's the alternative one, "or:" reads as a dangling reference rather than communicating
        anything real. Downgraded to a plain "Needs X" requirement in that one case.

        Deliberately NOT applied when `appliesToEmpireTypes` is non-null -- that's the Riddle
        Escort/Missiles/Torpedoes shape (Item 4's own real bug fix,
        `tests/test_dataset_emit.py::test_riddle_escort_gate_is_an_alternative_constrained_to_
        biological_shipset`), where the SAME "sole gate in the list" shape is correct AS "or:":
        the gate is deliberately shown ONLY for the axis where it's relevant, and "or:" there
        communicates a real fact (a non-biological-shipset empire already qualifies some other
        way) that downgrading to "Needs X" would silently lose. The two-gate case (`giga_tech_
        the_vat`'s "Needs Galactic Wonders" / "or: Mechromancy") is untouched either way, since
        this only fires when the list has exactly one entry."""
        if len(gates) == 1 and gates[0]["alternative"] and gates[0]["appliesToEmpireTypes"] is None:
            sole = gates[0]
            label = sole["label"]
            if label.startswith("or: "):
                label = "Needs " + label[len("or: "):]
            return [{**sole, "alternative": False, "groupId": None, "label": label}]
        return gates

    def _build_gates(owner_key: str, defn: "TechnologyDefinition") -> list[dict]:
        # Item 5 (later session): CLAUDE.md's documented "4 real pairs are both a formal
        # prerequisite AND a potential-gate" (`giga_tech_amb_supertensiles_acot_alpha/sigma/
        # delta/phanon`, each redundantly encoding the same ACOT/AoT dependency in both its own
        # `prerequisites` field AND a `has_technology` check inside `potential`) means a
        # "technology"-kind gate whose target is ALSO a true prerequisite of this same
        # technology is not a real GATE in the P-3 sense -- it's an ordinary prerequisite,
        # already shown via the edge and the popup's Prerequisites list. Displaying it a second
        # time as "Needs X" card-badge text duplicates that, rather than communicating a
        # distinct eligibility condition (P-3's actual purpose). This is a DISPLAY-layer
        # exclusion only -- pipeline.edges' `potential-gate` edge extraction and pipeline.
        # gate_patterns' raw classification are both deliberately untouched (CLAUDE.md's
        # "Edge-kind membership is NOT mutually exclusive" precedent for the edge graph itself
        # stands; only the CARD/POPUP gate-badge display is filtered here).
        true_prerequisites = set(ordered_prerequisites(defn.block))
        matches = [
            m for m in order_gates(classify_gates(owner_key, defn.block))
            if not (m.kind == "technology" and m.ref_id in true_prerequisites)
        ]
        gates: list[dict] = []
        for match in matches:
            # Item 4 ("path to zero uncertain" follow-up): an alternative (OR-context) gate is
            # never worded as an unconditional requirement -- "or: X" instead of "Needs X",
            # matching the real semantics (tech_torpedoes_1's "Riddle Escort" is one of four
            # independent ways to satisfy potential, not a mandatory prerequisite).
            label_prefix = "or:" if match.alternative else "Needs"
            if match.kind == "ascension_perk":
                # Same graceful-degradation convention `_default_icon_ref` already establishes
                # for a technology's own icon -- never observed to trigger for a real gate target
                # in the survey (7 distinct has_ascension_perk ids, plus
                # ap_gigastructural_constructs/ap_galactic_wonders, all resolved cleanly), kept
                # only so the schema's required `icon` field is never missing.
                icon = ctx.perk_icon_refs.get(match.ref_id, _default_icon_ref(ctx))
                gates.append({
                    "kind": "ascension_perk",
                    "refId": match.ref_id,
                    "icon": icon,
                    "label": f"{label_prefix} {_perk_gate_label(match.ref_id)}",
                    "alternative": match.alternative,
                    "groupId": match.group_id,
                    "appliesToEmpireTypes": None,
                    "inherited": False,
                    "sourceTechnologyId": None,
                })
            elif match.kind in ("origin", "ethics_or_civic"):
                # Item 3 ("path to zero uncertain" follow-up): no `common/civics`/`common/origins`/
                # `common/ethics` source, and no icon directory, is vendored for ANY source today
                # (survey finding, reported not acted on this session -- vendoring a new source
                # directory is its own review-gated corpus-pinning change). A LATER session
                # (user-reported) corrected the fallback: `_default_icon_ref`'s degenerate 1x1
                # stretched pixel read as a rendering error (a solid "teal square"), not an honest
                # placeholder -- this is not a rare edge case, it fires 100% of the time for these
                # two gate kinds. `icon: None` instead, so the client renders the LABEL alone (the
                # real, loc-resolved informative content) with no icon element at all, until real
                # origin/civic/ethic icons are vendored.
                gates.append({
                    "kind": match.kind,
                    "refId": match.ref_id,
                    "icon": None,
                    "label": f"{label_prefix} {_trait_gate_label(match.ref_id)}",
                    "alternative": match.alternative,
                    "groupId": match.group_id,
                    "appliesToEmpireTypes": None,
                    "inherited": False,
                    "sourceTechnologyId": None,
                })
            else:  # "technology"
                # Every real has_technology gate target is itself rendered in the FULL corpus
                # (confirmed by the survey), but a reduced build (D-14: ACOT/AoT optionally
                # absent is a supported build mode, not an error) can still hit a gate whose
                # target belongs to the missing source -- e.g. `giga_tech_amb_supertensiles_
                # acot_alpha` gates on the ACOT-only `tech_dark_matter_power_core_ae`, which is
                # only unrendered because ACOT itself is absent from this build, the same
                # graceful-degradation situation `_resolve_off_tree_prerequisite_name` already
                # handles for D-18's off-tree prerequisite names. Falls back to the same
                # best-effort loc_table lookup that function uses, never a hard failure, and
                # never a guess beyond what that established precedent already does.
                target_name = resolved_names.get(match.ref_id) or _resolve_off_tree_prerequisite_name(match.ref_id, ctx)
                icon = ctx.icon_refs.get(match.ref_id, _default_icon_ref(ctx))
                # Item 4: reuse pipeline.edge_constraints' own per-edge axis constraint, computed
                # from the exact same has_technology leaf via the underlying potential-gate edge
                # -- e.g. tech_torpedoes_1/tech_missiles_1's Riddle Escort gate is genuinely only
                # relevant for shipset=[biological] profiles (non-bio-ship empires already qualify
                # via a completely different OR branch, so the gate shouldn't present as a
                # requirement for them at all). Only meaningful for an alternative gate -- an
                # AND-required gate applies to every profile by construction (if the constraint
                # ever fired there it would mean the technology itself is axis-locked, a
                # different, already-handled case via availability, not this field).
                applies_to = ctx.edge_constraints.get((match.ref_id, owner_key, "potential-gate")) if match.alternative else None
                gates.append({
                    "kind": "technology",
                    "refId": match.ref_id,
                    "icon": icon,
                    "alternative": match.alternative,
                    "groupId": match.group_id,
                    "appliesToEmpireTypes": applies_to,
                    "label": f"{label_prefix} {target_name}",
                    "inherited": False,
                    "sourceTechnologyId": None,
                })

        granting_perk = ADD_RESEARCH_OPTION_PERK_GRANTS.get(owner_key)
        if granting_perk is not None and not any(g["kind"] == "ascension_perk" and g["refId"] == granting_perk for g in gates):
            icon = ctx.perk_icon_refs.get(granting_perk, _default_icon_ref(ctx))
            gates.append({
                "kind": "ascension_perk",
                "refId": granting_perk,
                "icon": icon,
                "label": f"Needs {_perk_gate_label(granting_perk)}",
                "alternative": False,
                "groupId": None,
                "appliesToEmpireTypes": None,
                "inherited": False,
                "sourceTechnologyId": None,
            })
        return gates

    # Item 3 (later session): gates DECLARED on a technology never propagated down its own
    # prerequisite chain -- a technology whose only real path to a perk/origin/ethics-or-civic
    # requirement is "research my prerequisite first, and THAT tech needs the perk" showed no
    # gate at all, even though researching it genuinely requires the same perk transitively (user
    # report: the QSO family and the `giga_tech_repeatable_*_cap` "Management Protocols" family
    # both failed to inherit a perk gate from their own prerequisite). Scoped to `prerequisite`
    # edges only (the formal, declared "must research first" chain) -- NOT `potential-gate`
    # edges, which encode a DIFFERENT kind of dependency (an eligibility check, not a declared
    # prerequisite) and are deliberately left unpropagated pending real corpus study of what that
    # would even mean; see this bullet's own note in CLAUDE.md before extending propagation there.
    direct_gates: dict[str, list[dict]] = {key: _build_gates(key, ctx.rendered_defs[key]) for key in key_order}

    direct_prereq_parents: dict[str, list[str]] = {key: [] for key in key_order}
    in_degree: dict[str, int] = {key: 0 for key in key_order}
    for e in ctx.typed_edges:
        if e.kind == "prerequisite" and e.to_key in direct_prereq_parents and e.from_key in direct_prereq_parents:
            direct_prereq_parents[e.to_key].append(e.from_key)
            in_degree[e.to_key] += 1

    # Kahn's algorithm restricted to `prerequisite` edges: technologies are a DAG by construction
    # (a cycle would mean the mod itself requires researching X before X), so a topological order
    # always exists -- computed here rather than assumed from declared tier, since tier is
    # DECLARED (CLAUDE.md's D-13) and not guaranteed to be a valid dependency order (backward
    # edges are real and expected).
    topo_order: list[str] = []
    ready = [key for key in key_order if in_degree[key] == 0]
    remaining_in_degree = dict(in_degree)
    children_via_prereq: dict[str, list[str]] = {key: [] for key in key_order}
    for child, parents in direct_prereq_parents.items():
        for parent in parents:
            children_via_prereq[parent].append(child)
    while ready:
        node = ready.pop()
        topo_order.append(node)
        for child in children_via_prereq[node]:
            remaining_in_degree[child] -= 1
            if remaining_in_degree[child] == 0:
                ready.append(child)
    if len(topo_order) != len(key_order):
        raise ValueError(
            "gate propagation: prerequisite edges do not form a DAG over the rendered key set "
            f"({len(key_order) - len(topo_order)} technologies never reached in-degree zero) -- "
            "the build fails rather than silently propagating gates over an inconsistent order"
        )

    full_gates: dict[str, list[dict]] = {}
    for key in topo_order:
        gates_for_key = list(direct_gates[key])
        seen = {(g["kind"], g["refId"]) for g in gates_for_key}
        for parent in direct_prereq_parents[key]:
            for g in full_gates[parent]:
                ident = (g["kind"], g["refId"])
                if ident in seen:
                    continue
                seen.add(ident)
                gates_for_key.append({
                    **g,
                    "inherited": True,
                    "sourceTechnologyId": g["sourceTechnologyId"] or parent,
                })
        full_gates[key] = _downgrade_dangling_alternative(
            sorted(gates_for_key, key=lambda g: GATE_KIND_PRIORITY[g["kind"]])
        )

    technologies_json = []
    categories: set[str] = set()
    for key in key_order:
        defn = ctx.rendered_defs[key]
        node = layout.nodes[key]
        name = resolved_names[key]

        tier = resolve_declared_tier(key, defn.block, ctx.variable_table)
        repeatable = is_repeatable(defn.block, ctx.variable_table)
        raw_levels = _levels_value(defn.block, ctx.variable_table) if repeatable else None
        # schema: null = unbounded ('Repeatable: infinity'), positive int = finite cap. The
        # corpus's own negative-levels convention (levels = -1) IS the unbounded signal.
        levels = None if (raw_levels is None or raw_levels < 0) else raw_levels
        category = category_of(defn.block) or ""
        categories.add(category)

        cost_assignment = _field(defn.block, "cost")
        cost = _resolve_cost(cost_assignment.value if cost_assignment else None, ctx.variable_table)

        cost_per_level = None
        if repeatable:
            cpl_assignment = _field(defn.block, "cost_per_level")
            cost_per_level = _resolve_numeric(cpl_assignment.value if cpl_assignment else None, ctx.variable_table)

        area_assignment = _field(defn.block, "area")
        area = _scalar_text(area_assignment.value) if area_assignment else "physics"

        availability_results = evaluate_technology_for_profiles(ctx.expanded_potentials.get(key), ctx.profiles)
        matrix = [availability_results[i].state for i in range(len(ctx.profiles))]

        requires_mods = [defn.source] if defn.source in ("ACOT", "AoT") else _potential_mod_requirements(defn.block)

        icon = icon_refs.get(key, _default_icon_ref(ctx))

        technologies_json.append({
            "id": key,
            "name": name,
            "icon": icon,
            "cost": cost,
            "tier": tier,
            "rowId": node.row_id,
            "area": area if area in ("physics", "society", "engineering") else "physics",
            "category": category,
            "crisisFaction": ctx.crisis.get(key),
            "rare": _bool_flag(defn.block, "is_rare"),
            "dangerous": _bool_flag(defn.block, "is_dangerous"),
            "repeatable": ({"levels": levels, "costPerLevel": cost_per_level} if repeatable else None),
            "requiresMods": requires_mods,
            "gates": full_gates[key],
            "availabilityMatrix": matrix,
            "labelPriority": _label_priority(key, reverse_prereq_count, defn),
        })

    row_counts: dict[str, int] = {}
    for key in key_order:
        row_counts[layout.nodes[key].row_id] = row_counts.get(layout.nodes[key].row_id, 0) + 1

    # Row model (D-16): `layout.row_ids` is ROW_ORDER -- the derived category rows followed by the
    # 5 fixed crisis-faction rows (pipeline.layout's module docstring). JSON field names ("rows"/
    # "rowId") now match the row model directly -- renamed from the earlier "lanes"/"laneId" names
    # this session, once the client was updated to match (see CLAUDE.md/HANDOFF.md).
    # A faction row's id/label is the faction name itself; a category row's id is the bare category
    # id (`layout.row_ids` entry) but its LABEL is that category's own resolved, human-readable
    # localised name (e.g. "voidcraft" -> "Voidcraft") -- resolved through the same hard-fail
    # `_require_resolved` path as every other displayed string, not left as the bare machine id.
    rows_json = [
        {
            "id": row_id,
            "label": (
                row_id if row_id in CRISIS_FACTIONS
                else _require_resolved(strip_markup(ctx.loc_table.require(row_id).value.raw), row_id, "category label", ctx)
            ),
            "crisisFaction": (row_id if row_id in CRISIS_FACTIONS else None),
            "technologyCount": row_counts.get(row_id, 0),
        }
        for row_id in layout.row_ids
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
        "empireProfileAxes": build_empire_profile_axes(),
        "metadata": {
            "gigastructuresCommit": manifest.get("gigastructures_commit", "unknown"),
            "vanillaVersion": manifest.get("vanilla_version", "unknown"),
            "acotVersion": manifest.get("acot_version", "unknown"),
            "aotVersion": manifest.get("aot_version", "unknown"),
            "buildTimestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        },
        "tierBands": tier_bands_json,
        "rows": rows_json,
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


def _prereq_and_alt_maps(ctx: "BuildContext") -> tuple[dict[str, list[str]], dict[str, list[tuple[str, list[str]]]]]:
    """P-12.9: `prereq_of[to_key]` (true `prerequisite` edges only, matching every other
    prereq_of user in this module) and `alt_groups_of[to_key]` (that technology's own
    `alternative` OR-groups, as `(groupId, [candidate technologyId, ...])` pairs, P-14's
    `Edge.groupId`) -- both derived once from `ctx.typed_edges`, profile-invariant (edge
    membership doesn't change per profile; only each candidate's own availability state does),
    so this is computed once and shared across every profile's own path build."""
    prereq_of: dict[str, list[str]] = {k: [] for k in ctx.rendered_keys}
    alt_groups: dict[str, dict[str, list[str]]] = {}
    for e in ctx.typed_edges:
        if e.kind == "prerequisite":
            prereq_of.setdefault(e.to_key, []).append(e.from_key)
        elif e.kind == "alternative":
            alt_groups.setdefault(e.to_key, {}).setdefault(e.group_id, []).append(e.from_key)
    alt_groups_of = {k: sorted(v.items()) for k, v in alt_groups.items()}
    return prereq_of, alt_groups_of


class _UnreachablePath(Exception):
    """Raised internally by `_build_research_paths_for_profile`'s `closure` when an ancestor
    closure hits a dead end for the current profile: a plain (non-`alternative`) prerequisite
    that is itself `locked`/`config-gated`, or an `alternative` group with zero viable candidates.
    Always caught at the per-target level -- never lets one broken ancestor closure abort the
    whole profile's path build."""


def _build_research_paths_for_profile(
    ctx: "BuildContext",
    prereq_of: dict[str, list[str]],
    alt_groups_of: dict[str, list[tuple[str, list[str]]]],
    availability_json: dict[str, dict],
    costs: dict[str, float | None],
    tiers: dict[str, int],
    swap_by_key: dict[str, dict],
) -> tuple[dict[str, dict], list[str]]:
    """P-12.9 (`spec/P-12.9-research-path.md`): per-technology research path for ONE profile,
    replacing the old profile-blind, `OR`-flattening `researchPaths` shape (v1's own documented
    failure -- see the spec's "The failure being fixed"). Every ancestor closure is memoised ONCE
    across all `ctx.rendered_keys` targets sharing this profile (`closure` below), since real
    ancestor sets overlap heavily between targets.

    Section 2's `OR`-group resolution: at each technology with its own `alternative` group(s),
    candidates whose state is `locked`/`config-gated` for this profile are excluded; among the
    remaining VIABLE candidates (`available` or `uncertain` both count, section 2 -- excluding
    `uncertain` would be D-10's "unknown treated as no" mistake), the one with the cheapest
    TOTAL closure cost (its own cost plus its own full recursive ancestor closure's cost) is
    chosen -- never just its own declared cost, which is what fixes v1's "branch never expanded
    its own prerequisites" bug. The chosen candidate's own closure is unioned into the running
    ancestor SET (section "cheapest = ... as a SET, shared ancestors counted once").

    Returns `(paths, unresolvable_ids)`; `unresolvable_ids` is section 6's tripwire diagnostic --
    a technology whose OWN state is available/uncertain but whose ancestor closure still contains
    a dead end. Empty on the real corpus (confirmed by running this exact algorithm against it,
    not assumed) -- surfaced as `diagnostics.unresolvableResearchPaths` by the caller, not
    silently absorbed into a fabricated `unavailable` status."""

    memo: dict[str, tuple[frozenset, dict[str, tuple[str, list[str]]], bool, bool]] = {}
    direct_effective_deps: dict[str, list[str]] = {}

    def state_of(k: str) -> str:
        return availability_json.get(k, {}).get("state", LOCKED)

    def closure(k: str) -> tuple[frozenset, dict[str, tuple[str, list[str]]], bool, bool]:
        if k in memo:
            return memo[k]
        req: set[str] = set()
        group_info: dict[str, tuple[str, list[str]]] = {}
        has_uncertain = state_of(k) == UNCERTAIN
        has_null_cost = costs.get(k) is None
        deps: list[str] = []

        def _absorb(child_key: str, child_state: str) -> None:
            nonlocal has_uncertain, has_null_cost
            if child_key in req:
                return
            child_req, child_gi, child_unc, child_null = closure(child_key)
            req.add(child_key)
            req.update(child_req)
            for gk, gv in child_gi.items():
                group_info.setdefault(gk, gv)
            has_uncertain = has_uncertain or child_unc or child_state == UNCERTAIN
            has_null_cost = has_null_cost or child_null or costs.get(child_key) is None

        for p in prereq_of.get(k, []):
            p_state = state_of(p)
            if p_state in (LOCKED, CONFIG_GATED):
                raise _UnreachablePath()
            deps.append(p)
            _absorb(p, p_state)

        for group_id, members in alt_groups_of.get(k, []):
            viable = [m for m in members if state_of(m) in (AVAILABLE, UNCERTAIN)]
            if not viable:
                raise _UnreachablePath()
            chosen = min(viable, key=lambda m: (_closure_total_cost(m, closure, costs), m))
            deps.append(chosen)
            _absorb(chosen, state_of(chosen))
            group_info.setdefault(chosen, (group_id, [m for m in viable if m != chosen]))

        direct_effective_deps[k] = deps
        result = (frozenset(req), group_info, has_uncertain, has_null_cost)
        memo[k] = result
        return result

    def ordered_ancestors(key: str, req: frozenset) -> list[str]:
        seen: set[str] = set()
        order: list[str] = []

        def visit(k: str) -> None:
            for d in direct_effective_deps.get(k, []):
                if d not in seen:
                    seen.add(d)
                    visit(d)
                    order.append(d)

        visit(key)
        assert set(order) == set(req), (key, set(order) ^ set(req))
        return order

    def display(tid: str) -> tuple[str, dict]:
        swap = swap_by_key.get(tid)
        if swap is not None:
            return swap["name"], swap["icon"]
        return ctx.resolved_names.get(tid, tid), ctx.icon_refs.get(tid) or _default_icon_ref(ctx)

    def build_step(tid: str, group_info: dict[str, tuple[str, list[str]]]) -> dict:
        name, icon = display(tid)
        group_id, alt_ids = group_info.get(tid, (None, []))
        return {
            "technologyId": tid, "name": name, "icon": icon, "tier": tiers.get(tid, 0),
            "stepCost": costs.get(tid), "availabilityState": state_of(tid),
            "groupId": group_id,
            "alternatives": [{"technologyId": a, "name": display(a)[0]} for a in alt_ids],
        }

    paths: dict[str, dict] = {}
    unresolvable: list[str] = []

    for key in sorted(ctx.rendered_keys):
        target_state = state_of(key)
        if target_state == LOCKED:
            paths[key] = {"status": "unavailable"}
            continue
        try:
            req, group_info, has_uncertain, has_null_cost = closure(key)
        except _UnreachablePath:
            unresolvable.append(key)
            paths[key] = {"status": "unavailable"}
            continue

        order = ordered_ancestors(key, req)
        steps = [build_step(tid, group_info) for tid in order]
        ancestors_cost = sum((costs.get(tid) or 0.0) for tid in order)
        is_config_gated = target_state == CONFIG_GATED
        # Section 5: a config-gated target's own cost is excluded from totalCost entirely (the
        # ancestor chain up to, not including, the cap technology itself). Every other status
        # ("path") includes the target's own cost -- confirmed against the spec's own worked
        # example (tech_mega_engineering, regular/mechanical/non-nomadic: 15 ancestor steps sum to
        # 50,750; the spec's reported total, 74,750, is exactly that plus the target's own 24,000
        # declared cost) and against this session's corrected nomadic figure (76,250 = 52,250
        # ancestor sum + the same 24,000) -- "sum of stepCost" alone, read literally, reproduces
        # neither figure; this is the schema's own actual intent, not a deviation from it.
        total_cost = ancestors_cost if is_config_gated else ancestors_cost + (costs.get(key) or 0.0)
        target_uncertain = target_state == UNCERTAIN
        target_null_cost = (not is_config_gated) and costs.get(key) is None
        reasons = []
        if has_uncertain or target_uncertain:
            reasons.append("uncertain-availability")
        if has_null_cost or target_null_cost:
            reasons.append("unresolved-cost")

        entry = {
            "status": "config-gated" if is_config_gated else "path",
            "steps": steps,
            "totalCost": total_cost,
            "totalCostIsEstimate": bool(reasons),
            "estimateReasons": reasons,
            "configGatedTarget": None,
        }
        if target_state == CONFIG_GATED:
            name, icon = display(key)
            entry["configGatedTarget"] = {
                "technologyId": key, "name": name, "icon": icon,
                "subject": _config_gated_subject(key, ctx),
            }
        paths[key] = entry

    return paths, unresolvable


def _closure_total_cost(key: str, closure_fn, costs: dict[str, float | None]) -> float:
    """The FULL closure cost of `key` as an `alternative`-group CANDIDATE: its own declared cost
    plus its own recursive ancestor closure's cost, null-cost members contributing 0 (section 2's
    "the branch's own cost plus its own full prerequisite chain's cumulative cost, recursively" --
    what fixes v1's "Arkship Mastery never expanded its own prerequisites" bug). This is a
    per-candidate comparison figure only, deliberately NOT deduplicated against ancestors already
    chosen elsewhere in the path being built -- the final `totalCost` (computed once, over the
    actual chosen ancestor SET) is where sharing is naturally deduplicated instead."""
    req, _gi, _unc, _null = closure_fn(key)
    return (costs.get(key) or 0.0) + sum((costs.get(a) or 0.0) for a in req)


def _compute_profile_facts(
    ctx: "BuildContext", profile: dict,
) -> tuple[dict[str, dict], dict[str, float | None], dict[str, int], list[dict]]:
    """`(availability_json, costs, tiers, swap_mappings)` for ONE profile -- extracted from
    `build_empire_overlay` (which still calls this directly) so `build_diagnostics`'s
    `unresolvableResearchPaths` computation (P-12.9 section 6) can reuse the SAME per-profile
    availability/cost/swap resolution rather than an independent, driftable recomputation --
    matching CLAUDE.md's "pipeline owns all geometry" discipline applied to per-profile facts."""
    lock_reason_overrides = load_lock_reason_overrides()
    availability_json: dict[str, dict] = {}
    swap_mappings: list[dict] = []
    # P-12.9: `None` (not `0.0`) is preserved here -- the research-path algorithm needs to tell
    # "declared zero cost" (28/973 real starting technologies) apart from "cost unresolvable"
    # (5 more; `_resolve_cost`'s own docstring), the same distinction the base dataset's own `cost`
    # field already preserves (`_resolve_cost`'s null-means-unresolved contract). A `None` still
    # contributes exactly 0 to any running total, same numeric effect as before this change -- only
    # the "was this actually zero, or unknown" bookkeeping changed.
    costs: dict[str, float | None] = {}
    tiers: dict[str, int] = {}

    for key, defn in ctx.rendered_defs.items():
        cost_assignment = _field(defn.block, "cost")
        costs[key] = _resolve_cost(cost_assignment.value if cost_assignment else None, ctx.variable_table)
        tiers[key] = resolve_declared_tier(key, defn.block, ctx.variable_table)

        result = evaluate_technology_for_profiles(ctx.expanded_potentials.get(key), [profile])[0]
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

    return availability_json, costs, tiers, swap_mappings


def build_empire_overlay(ctx: BuildContext, profile: dict) -> dict:
    profile_index = empire_profile_index(profile)
    prereq_of, alt_groups_of = _prereq_and_alt_maps(ctx)
    availability_json, costs, tiers, swap_mappings = _compute_profile_facts(ctx, profile)

    active_edge_ids = [
        i for i, e in enumerate(ctx.layout.edges)
        if edge_active_for_profile(ctx.edge_constraints.get((e.from_key, e.to_key, e.kind)), profile)
    ]

    swap_by_key = {m["technologyId"]: m for m in swap_mappings}
    # Section 6's `unresolvableResearchPaths` tripwire (spec/P-12.9-research-path.md) is a
    # DIAGNOSTICS-artefact concern (S-2's own lazy, dev-only artefact), not part of the
    # empire-overlay schema -- `build_diagnostics` recomputes it directly via the same
    # `_build_research_paths_for_profile` call, matching this module's existing precedent
    # (its own D-10 survey and `uncertainTechnologies` section are independent recomputations
    # from `ctx` too, never smuggled through an unrelated function's return value).
    research_paths, _unresolvable_paths = _build_research_paths_for_profile(
        ctx, prereq_of, alt_groups_of, availability_json, costs, tiers, swap_by_key,
    )

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
    desc_entry = (
        _vanilla_loc_entry(f"{key}_desc", ctx)
        if key in VANILLA_LOC_AND_ICON_PRECEDENCE_KEYS
        else ctx.loc_table.get(f"{key}_desc")
    )
    raw_description = strip_markup(desc_entry.value.raw) if desc_entry else ""
    # Upgraded (later session) from strip-only to full token resolution, same as `name` -- see
    # PART 2's survey: 223/980 raw descriptions carried a literal, unresolved `$...$` token before
    # this fix, and all 223 resolve cleanly (measured max depth 4 hops) under the corrected
    # resolve-every-sibling-token algorithm. Hard-fails the same way `name` does: description is a
    # displayed string (the detail popup), and there is no remaining reason to tolerate a raw
    # token in it that `name` doesn't also tolerate.
    description = _require_resolved(raw_description, key, "description", ctx) if raw_description else ""
    # Reconciliation session 3, found by reviewing a real detail-popup screenshot (this field was
    # never actually DISPLAYED anywhere before the popup slice, so this was invisible until now):
    # Stellaris's own loc format uses a literal two-character `\n` escape sequence inside a
    # description string for a real line break (confirmed directly against raw source --
    # `tech_dark_matter_power_core_ae_desc`'s own YAML value contains the literal backslash-n
    # bytes, not a real newline) -- `strip_markup` only strips `§`/`£` markup, never touched this.
    # Unescaped here, not client-side, since the wrong (literal-backslash-n) string is genuinely
    # bad data to ship, not a presentation choice. Scoped to `description` only -- every other
    # loc-derived field (names, gate labels, swap names) is short-form and has never been observed
    # to carry this escape in the real corpus.
    description = description.replace("\\n", "\n")

    repeatable = is_repeatable(defn.block, ctx.variable_table)
    cost_per_level_assignment = _field(defn.block, "cost_per_level")
    repeatable_cost_progression = None
    if repeatable and cost_per_level_assignment is not None:
        per_level = _resolve_numeric(cost_per_level_assignment.value, ctx.variable_table)
        if per_level is not None:
            levels = _levels_value(defn.block, ctx.variable_table)
            n = levels if levels else 10  # unbounded: report first 10 levels' worth, not an infinite array
            base = _resolve_cost(_field(defn.block, "cost").value, ctx.variable_table) if _field(defn.block, "cost") else 0.0
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

    # D-18 off-tree-prerequisite surfacing (Item 3, reconciliation session 3): the exact 3 accepted
    # links (spec/decisions.md's D-18) name a prerequisite with no rendered node. Resolved
    # best-effort -- soft fallback to the raw key on an unresolvable name, since this is a
    # supplementary note, not a field this project's usual "hard-fail on unresolved localisation"
    # discipline applies to (the technology NAMING the off-tree prerequisite still renders and
    # still has its own, separately-resolved name; a missing NAME for the thing it merely
    # MENTIONS shouldn't fail the whole build).
    off_tree_prerequisite_names = [
        _resolve_off_tree_prerequisite_name(prereq_key, ctx)
        for prereq_key in ctx.off_tree_prerequisites.get(key, [])
    ]

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
        "offTreePrerequisiteNames": off_tree_prerequisite_names,
    }


def _resolve_off_tree_prerequisite_name(prereq_key: str, ctx: "BuildContext") -> str:
    name_entry = ctx.loc_table.get(prereq_key)
    if name_entry is None:
        return prereq_key
    raw_name = strip_markup(name_entry.value.raw)
    resolved = _resolve_loc_tokens(raw_name, ctx)
    return resolved if resolved is not None else prereq_key


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
    """Item 2: tokens include every AXIS-EXPRESSIBLE swap alternate's display name too, not just
    the base name -- a user who remembers "Zero Point Metabolism" (the bioship swap name) must
    still find `tech_zero_point_power` while browsing the default (regular/mechanical) profile,
    where the card shows "Zero Point Power". Pooled across ALL twelve profiles' worth of swap
    alternates unconditionally (not gated by whether a swap is active for the CURRENT profile --
    search matching is deliberately more permissive than display, per this session's own
    instruction); the CLIENT is responsible for displaying the profile-correct name in the result
    regardless of which name token matched."""
    entries = []
    for tech in base_dataset["technologies"]:
        key = tech["id"]
        defn = ctx.rendered_defs.get(key)
        swap_names = " ".join(
            _swap_display_name(s, ctx) for s in collect_swaps(key, defn.block) if s.axis_expressible
        ) if defn else ""
        text = f"{tech['name']} {key} {swap_names} {detail_payloads.get(key, {}).get('description', '')}"
        tokens = sorted(set(t for t in re.split(r"[^a-z0-9]+", text.lower()) if t))
        entries.append({"technologyId": key, "tokens": tokens})
    return {"schemaVersion": SCHEMA_VERSION, "entries": entries}


def build_diagnostics(ctx: BuildContext) -> dict:
    technologies_for_survey = ctx.expanded_potentials
    survey = survey_uncertainty(technologies_for_survey, ctx.profiles)
    d10_section = build_d10_diagnostics_section(survey, ctx.profiles)

    # Item 1 (later session): the dev health monitor's data. Reuses the exact same evaluator call
    # D-10's own survey already makes (evaluate_technology_for_profiles) -- never a second,
    # independently-derived pass that could disagree with what D-10 itself reports.
    name_overrides_for_diagnostics = load_name_overrides()
    uncertain_technologies: list[dict] = []
    for key, potential in sorted(technologies_for_survey.items()):
        results = evaluate_technology_for_profiles(potential, ctx.profiles)
        uncertain_indices = [i for i, r in results.items() if r.state == UNCERTAIN]
        if not uncertain_indices:
            continue
        uncertain_technologies.append({
            "technologyId": key,
            "name": _resolve_technology_name(key, ctx, name_overrides_for_diagnostics),
            "unconditional": len(uncertain_indices) == len(ctx.profiles),
            "perProfile": [
                {
                    "profile": ctx.profiles[i],
                    "category": (results[i].category or ReasonCategory.UNCLASSIFIED).value,
                    "description": results[i].description or results[i].reason or "",
                }
                for i in uncertain_indices
            ],
        })

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
    for key in ctx.rendered_defs:
        for profile in ctx.profiles:
            result = evaluate_technology_for_profiles(ctx.expanded_potentials.get(key), [profile])[0]
            if result.state == LOCKED:
                _reason, needs_warning = resolve_lock_reason(key, result, lock_reason_overrides)
                if needs_warning:
                    missing_lock_reasons.add(key)

    alt_gaps = compute_alternative_only_gaps(technology_history_all)

    # P-12.9 section 6's tripwire: a technology whose OWN state is available/uncertain but whose
    # ancestor closure still contains a dead end, for at least one profile. Recomputed directly
    # from `ctx` per profile (via the SAME `_build_research_paths_for_profile`/`_compute_profile_
    # facts` calls `build_empire_overlay` makes) rather than threaded through that function's
    # return value -- this module's existing precedent for a diagnostics-only figure (see this
    # function's own `uncertain_technologies` above). Empty on the real corpus (confirmed by
    # actually running the algorithm, not assumed) -- see spec/P-12.9-research-path.md section 6.
    prereq_of, alt_groups_of = _prereq_and_alt_maps(ctx)
    unresolvable_research_paths: list[dict] = []
    for profile in ctx.profiles:
        availability_json, costs, tiers, swap_mappings = _compute_profile_facts(ctx, profile)
        swap_by_key = {m["technologyId"]: m for m in swap_mappings}
        _paths, unresolvable = _build_research_paths_for_profile(
            ctx, prereq_of, alt_groups_of, availability_json, costs, tiers, swap_by_key,
        )
        unresolvable_research_paths.extend(
            {"technologyId": key, "profile": profile} for key in unresolvable
        )

    return {
        "schemaVersion": SCHEMA_VERSION,
        **d10_section,
        "uncertainTechnologies": uncertain_technologies,
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
        "unresolvableResearchPaths": unresolvable_research_paths,
        "overwriteReport": overwrite_report,
        **_reduced_vendor_diagnostics(ctx),
    }


def _reduced_vendor_diagnostics(ctx: BuildContext) -> dict:
    """`vendorSourcesLoaded`/`placeholderTechnologiesAbsent`/
    `vanillaTechnologiesRevertedFromAcotOverwrite` -- fires (non-empty) only when ACOT and/or AoT
    is absent from this build. Deliberately loud: a build missing ACOT/AoT is plausible and
    self-consistent (zero dangling edges, zero alternative-only gaps -- see spec/decisions.md's
    vendoring-automation investigation) precisely because nothing else looks broken. D-18 (this
    session): a reduced build's rendered-node count is no longer simply "977" restated --
    depth-1's own full-build count is ALSO 977 (coincidentally the same digits, a different
    computation: full build is 980 - 3 depth-2+ drops; reduced build is 977 - 4 remaining
    depth-1 placeholders + 4 vanilla-overwrite reversions = 977 again). Don't treat this
    coincidence as evidence the two builds are otherwise equivalent -- re-derive from the real
    corpus rather than reusing either cached figure. See
    `PLACEHOLDER_TECHNOLOGIES_REQUIRING_ACOT_AOT`/`VANILLA_TECHNOLOGIES_ACOT_OVERWRITES` above for
    why these two lists are maintained constants, not derived from the reduced corpus."""
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
