"""General scripted-trigger leaf expansion, feeding `pipeline.availability`'s EXISTING Kleene
evaluator without touching its boolean semantics.

`common/scripted_triggers/` (all four sources) defines thousands of named triggers
(`name = { ... }`) that a technology's `potential` block can reference as a bare identifier leaf
(`giga_can_use_habitables = yes`). Before this module, `pipeline.availability` treated any such
name it didn't specifically recognise as an opaque, permanently-`unknown` leaf -- correct, but
needlessly conservative when the trigger's own real body is itself made of leaves the evaluator
*could* resolve (axis facts, DLC ground facts, ...). This module substitutes a trigger's real
body in place of its name, recursively, so those inner leaves reach the evaluator instead of a
name it has never seen. Nothing about `_evaluate_leaf`/`_combine_and`/`_combine_or`/`_negate`
changes -- this only rewrites the `Block` handed to `evaluate_trigger_block` beforehand.

**Not `pipeline.inline_scripts`, and not reusable as it stands -- confirmed by the survey that
preceded this module, not assumed.** `inline_scripts` does textual, PARAMETERISED substitution
(`inline_script = { script = "path" PARAM = value }`) on raw source text before tokenising,
required because ~46% of real `$PARAM$` usage is embedded mid-token, a shape no AST node can
represent. A scripted-trigger CALL is a completely different, simpler shape: a bare identifier
leaf (`trigger_name = yes` / `trigger_name = no`), already an ordinary `Assignment` node once
parsed -- no text substitution, no parameters, no mid-token splicing, no reparse. Expansion here
operates directly on already-parsed `Block`/`Assignment` nodes.

**Scope discipline matches every other consumer of a trigger tree in this project**
(`pipeline.availability._evaluate_node`, `pipeline.edges._scoped_has_technology`,
`pipeline.gate_patterns._scoped_gate_leaves`): only descend through `AND`/`OR`/`NOT`/`NOR`
wrappers. A trigger name appearing inside an opaque block-valued field (`count_country`,
`weight_modifier`, `ai_weight`, ...) is never substituted -- it was never evaluated there either,
so expanding it would change nothing except adding needless work, and risks the same kind of
false positive `pipeline.edges`' own docstring warns about for unscoped `has_technology` search.

**`is_ai = yes` branches are stripped, not modelled, exactly like the two hardcoded wrapper
mappings this module makes redundant.** `pipeline.gate_patterns.WRAPPER_TO_PERK`'s own docstring
already documents that `has_gigastructural_constructs`/`has_galactic_wonders` carry an
`OR = { AND = { is_ai = yes, has_country_flag = ... } has_ascension_perk = ... }` shape this
project deliberately never models (an AI-empire concession, never relevant to a player profile).
Survey (this module's own predecessor): 32 scripted triggers in the real corpus carry an `is_ai`
leaf somewhere in their body. Generalised here: any boolean-wrapper CHILD whose own subtree
contains a literal `is_ai` leaf anywhere is dropped from that wrapper's combination entirely,
before recursing into its surviving siblings -- at every nesting level, not just the two
previously-hardcoded triggers. This has zero effect on a technology's own `potential` block (the
real corpus has zero `is_ai` occurrences there, confirmed by survey), so the rule only ever fires
on content pulled in from an EXPANDED trigger body.

**Depth bound and cycles.** Real corpus: 3,463 distinct trigger names after overwrite resolution,
zero reference cycles, max observed reference-chain depth 8. `MAX_EXPANSION_DEPTH` is set above
that (12) as a sanity ceiling, not a expected-to-be-hit limit -- hitting it is a hard failure
(`ExpansionDepthExceededError`), the same "no partial dataset" posture `pipeline.variables` takes
for an `@variable` reference cycle, because a legitimate 12-deep trigger chain has never been
observed and hitting the ceiling means either a genuine new cycle or a corpus shape this module's
design didn't anticipate -- neither should be silently truncated. A true cycle (a name reappearing
in its own still-open expansion chain) is caught earlier and separately
(`ScriptedTriggerCycleError`, naming the full chain), the same shape as
`pipeline.variables.VariableCycleError`.

**One real corpus file, `zzz_overwrites.txt`, cannot be `inline_script`-expanded at all** --
`has_research_building`'s ACOT/AoT branch invokes `generic_parts/giga_toggled_code`, which computes
its OWN target file name via an arithmetic `@[ ... ]` expression (dynamic path selection), a shape
`pipeline.inline_scripts` cannot resolve outside a real parameterised invocation context. This is
an existing `inline_script` limitation, not something this module's expansion introduces or should
try to fix (a materially different, larger feature). The catalog loader falls back to that one
file's RAW (unexpanded) parse rather than losing every other definition the file carries (notably
`has_galactic_wonders` itself, defined later in the same file) -- `has_research_building`'s own
body keeps one literal, unexpandable `inline_script = { ... }` node, which the evaluator already
treats as an unrecognised opaque leaf (falls to `unknown`, never guessed at). Confirmed: no
rendered technology's `potential` currently references `has_research_building` at all, so this
has zero real-corpus effect today -- see `tests/test_scripted_triggers_corpus.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .availability import AXIS_FACTS, DLC_NAME_CHECK_KEYS, EXCLUDED_KEYS, GROUND_FACT_BOOL
from .clausewitz.nodes import Assignment, Block, Identifier
from .inline_scripts import InlineScriptError

BOOLEAN_WRAPPERS = {"AND", "OR", "NOT", "NOR"}

# Real corpus regression, found the hard way (this module's own development): `country_uses_bio_ships`
# -- already specially resolved by `pipeline.availability.AXIS_FACTS` as the shipset axis fact --
# is ALSO a real scripted-trigger name (vendor/stellaris/common/scripted_triggers/
# 07_scripted_triggers_ships.txt:33), whose own body opens with `exists = this`, a scope-existence
# tautology-shaped leaf (`= this`, not `= yes`/`= no`) the evaluator's leaf model has no notion of.
# Naively expanding EVERY catalog match blind to what `pipeline.availability` already resolves
# destroyed the axis-fact shortcut for every one of the ~238 real `country_uses_bio_ships`
# occurrences and replaced it with a permanently-unresolvable `exists = this` leaf -- a 110-
# technology regression (215 -> 320 uncertain) caught only by re-running the corpus survey after
# writing this module, not by design review. A name already resolved directly by one of
# `pipeline.availability`'s own dedicated tables (AXIS_FACTS/GROUND_FACT_BOOL/DLC_NAME_CHECK_KEYS,
# or -- a later session, Item 3's ethics/civic/origin gate exclusions -- EXCLUDED_KEYS) is skipped
# here unconditionally and left for that table to keep handling exactly as before -- expansion
# only ever applies to a name the evaluator would otherwise treat as a fully opaque, unrecognised
# leaf. `EXCLUDED_KEYS` needed the SAME fix as `country_uses_bio_ships`, found the same way: Item
# 3 added `is_megacorp` (`= { has_authority = auth_corporate }`), `is_wilderness_empire`, and a
# dozen more real scripted-trigger names to `EXCLUDED_KEYS` -- naively expanding any of them would
# replace the excluded leaf with its real body's UNEXCLUDED inner leaf (`has_authority`, for
# `is_megacorp`), silently undoing the exclusion. Two deliberate exceptions, kept expandable:
# `has_gigastructural_constructs`/`has_galactic_wonders` (their real bodies reduce to
# `has_ascension_perk` leaves, themselves still excluded, so expanding them is a confirmed no-op
# for availability -- exercising it is exactly what answers whether
# `pipeline.gate_patterns.WRAPPER_TO_PERK` becomes redundant, see that module). `has_technology`/
# `has_ascension_perk`/`can_research_technology` aren't scripted-trigger catalog names at all (no
# collision risk, confirmed by corpus search), so excluding them from this skip-set would be a
# no-op anyway -- listed here for completeness, not because they needed the fix.
_EXPANDABLE_EXCLUDED_KEYS = {"has_gigastructural_constructs", "has_galactic_wonders"}
_ALREADY_RESOLVED_KEYS = (
    frozenset(AXIS_FACTS)
    | frozenset(GROUND_FACT_BOOL)
    | frozenset(DLC_NAME_CHECK_KEYS)
    | (frozenset(EXCLUDED_KEYS) - _EXPANDABLE_EXCLUDED_KEYS)
)

# Above the real measured max reference-chain depth (8) -- a sanity ceiling, not an expected limit.
# See module docstring.
MAX_EXPANSION_DEPTH = 12

SOURCE_ORDER = ("Vanilla", "Gigastructural Engineering", "ACOT", "AoT")


class ScriptedTriggerError(Exception):
    """Base class for scripted-trigger expansion failures."""


class UnknownSourceError(ScriptedTriggerError):
    def __init__(self, source_name: str):
        self.source_name = source_name
        super().__init__(f"unknown source: {source_name!r} (expected one of {SOURCE_ORDER})")


class ScriptedTriggerCycleError(ScriptedTriggerError):
    """A trigger name reappeared in its own still-open expansion chain. `chain` is the full
    reference path, ending with the name that closed the cycle -- same shape as
    `pipeline.variables.VariableCycleError`."""

    def __init__(self, chain: tuple[str, ...]):
        self.chain = chain
        super().__init__("scripted-trigger reference cycle: " + " -> ".join(chain))


class ExpansionDepthExceededError(ScriptedTriggerError):
    """`MAX_EXPANSION_DEPTH` was hit. See module docstring -- this has never fired against the
    real corpus (max observed depth is 8) and is a hard failure, not a silent truncation, if it
    ever does."""

    def __init__(self, chain: tuple[str, ...]):
        self.chain = chain
        super().__init__(
            f"scripted-trigger expansion depth exceeded ({MAX_EXPANSION_DEPTH}): " + " -> ".join(chain)
        )


@dataclass(frozen=True)
class ScriptedTriggerDefinition:
    """The winning `name = { ... }` definition for one trigger name, after overwrite resolution
    (whole-key, last-source-wins across `SOURCE_ORDER`, same rule as P-15's technology overwrites
    and `pipeline.variables`' `@variable` resolution)."""

    name: str
    source: str
    document_path: str
    line: int
    body: Block


def collect_scripted_trigger_definitions(
    sources: Iterable[tuple[str, Iterable]]
) -> dict[str, list[ScriptedTriggerDefinition]]:
    """`sources` is (source_name, documents) pairs, already in load order. Returns name -> full
    occurrence history in load order -- same shape as
    `pipeline.overwrites.collect_technology_definitions`."""
    history: dict[str, list[ScriptedTriggerDefinition]] = {}
    for source_name, documents in sources:
        if source_name not in SOURCE_ORDER:
            raise UnknownSourceError(source_name)
        for document in documents:
            for item in document.items:
                if isinstance(item, Assignment) and isinstance(item.value, Block):
                    history.setdefault(item.key_name, []).append(
                        ScriptedTriggerDefinition(item.key_name, source_name, document.path, item.line, item.value)
                    )
    return history


def resolve_scripted_triggers(
    history: dict[str, list[ScriptedTriggerDefinition]]
) -> dict[str, ScriptedTriggerDefinition]:
    """Whole-key, last-source-wins winner per name -- `history` is already in load order, so the
    last occurrence in each list is the winner (135 real names are redefined by a later source;
    none 3-deep)."""
    return {name: occurrences[-1] for name, occurrences in history.items()}


def load_scripted_trigger_catalog(vendor_root: Path, scripts, source_roots: list[tuple[str, Path]]) -> dict[str, ScriptedTriggerDefinition]:
    """Parses every source's `common/scripted_triggers/*.txt`, `inline_script`-expanding each file
    where possible. `scripts` is `pipeline.inline_scripts.collect_scripts`' output. `source_roots`
    is `(source_name, source_root_path)` pairs in load order (e.g. `dataset_emit._source_roots`'
    output) -- passed in rather than re-derived so this module has no opinion on vendor directory
    layout beyond `common/scripted_triggers`.

    One file (`zzz_overwrites.txt`, Gigastructural Engineering) cannot be fully
    `inline_script`-expanded -- see module docstring. Falls back to that file's raw parse alone,
    never drops the whole source."""
    from .clausewitz import parse_file
    from .inline_scripts import expand_document

    sources: list[tuple[str, list]] = []
    for source_name, root in source_roots:
        d = root / "common" / "scripted_triggers"
        if not d.is_dir():
            continue
        docs = []
        for f in sorted(d.glob("*.txt")):
            try:
                doc, _report = expand_document(parse_file(f), scripts)
            except InlineScriptError:
                doc = parse_file(f)
            docs.append(doc)
        sources.append((source_name, docs))

    history = collect_scripted_trigger_definitions(sources)
    return resolve_scripted_triggers(history)


def _yesno(value) -> bool | None:
    if isinstance(value, Identifier):
        if value.name == "yes":
            return True
        if value.name == "no":
            return False
    return None


def _is_ai_gated_branch(node) -> bool:
    """True if `node` should be dropped entirely as an AI-only override branch. Three shapes, all
    confirmed real (`pipeline.gate_patterns.WRAPPER_TO_PERK`'s own docstring; this module's own
    corpus survey):

    1. `node` IS a bare `is_ai` leaf -- drop just this leaf; ANY siblings (whether inside an AND
       or an OR) stand on their own, unaffected.
    2. `node` is a CONJUNCTIVE wrapper (`AND`/`NOT`) whose direct children PAIR `is_ai` with at
       least one other condition (the real shape: `AND = { is_ai = yes, has_country_flag = X }`)
       -- `X` only has meaning conditioned on `is_ai`, so the whole wrapper goes, not just the
       `is_ai` leaf inside it (leaving `has_country_flag = X` behind on its own would introduce a
       real, unintended condition no one meant to apply to a player empire).
    3. `node` is a `hidden_trigger = { ... }` wrapper whose own direct children are ENTIRELY
       is_ai-gated by rules 1/2, recursively (the real shape, `zzz_overwrites.txt`'s
       `has_galactic_wonders`: `hidden_trigger = { and = { is_ai = yes, has_country_flag = X } }`).
       `hidden_trigger` is a real Stellaris trigger wrapper that only changes whether a failure
       reason shows in a tooltip, never the truth value of its contents -- functionally
       transparent, unlike `count_country`/`weight_modifier` (a genuinely different evaluation
       SCOPE this project's scope discipline must never search inside). Found the hard way (this
       module's own corpus verification, run against the real vendored corpus after the first two
       rules alone): `pipeline.availability`'s own `_evaluate_node` doesn't recognise
       `hidden_trigger` as a boolean wrapper either, so leaving it unexpanded turns it into one
       opaque, permanently-`unknown` leaf -- an 11-technology regression across every real
       `has_galactic_wonders`-gated technology, since 4 of that trigger's OR-siblings are
       `has_ascension_perk` (already EXCLUDED, contributing nothing) and the `hidden_trigger`
       branch, left unresolved instead of dropped, was the one UNKNOWN branch left standing.
       If `hidden_trigger` ever wraps something that ISN'T entirely is_ai-gated, this returns
       False and the wrapper is left as an ordinary unrecognised leaf (unchanged, conservative)
       rather than guessed at.

    Deliberately NEVER drops an `OR`/`NOR` wrapper wholesale for containing `is_ai` -- found the
    hard way (this module's own test suite): `OR = { is_ai = yes  is_nomadic = yes }` has two
    INDEPENDENT branches, not a conjunctive pairing; dropping the whole OR because one of its
    disjuncts happens to be `is_ai` would wrongly take `is_nomadic` down with it. For an OR/NOR,
    this function returns False for the wrapper itself, so `_expand_node`'s ordinary recursion
    processes its children individually and rule 1 catches the bare `is_ai` child on its own."""
    if not isinstance(node, Assignment):
        return False
    if node.key_name == "is_ai":
        return True
    key_upper = node.key_name.upper()
    if key_upper in ("AND", "NOT") and isinstance(node.value, Block):
        direct_children = [c for c in node.value.items if isinstance(c, Assignment)]
        return any(c.key_name == "is_ai" for c in direct_children)
    if node.key_name == "hidden_trigger" and isinstance(node.value, Block):
        direct_children = [c for c in node.value.items if isinstance(c, Assignment)]
        return len(direct_children) > 0 and all(_is_ai_gated_branch(c) for c in direct_children)
    return False


def _expand_items(
    items: list, catalog: dict[str, ScriptedTriggerDefinition], chain: tuple[str, ...], depth: int
) -> list[Assignment]:
    result = []
    for item in items:
        if not isinstance(item, Assignment):
            continue
        if _is_ai_gated_branch(item):
            continue  # AI-only override branch -- never modelled, see module docstring
        result.append(_expand_node(item, catalog, chain, depth))
    return result


def _expand_node(
    node: Assignment, catalog: dict[str, ScriptedTriggerDefinition], chain: tuple[str, ...], depth: int
) -> Assignment:
    key_upper = node.key_name.upper()
    if key_upper in BOOLEAN_WRAPPERS and isinstance(node.value, Block):
        new_items = _expand_items(node.value.items, catalog, chain, depth)
        return Assignment(node.key, node.operator, Block(new_items, node.value.line, node.value.column), node.line, node.column)

    if node.key_name in _ALREADY_RESOLVED_KEYS:
        return node  # pipeline.availability already resolves this key directly -- never override it

    definition = catalog.get(node.key_name)
    if definition is None:
        return node  # not a scripted-trigger name -- an ordinary leaf, left for the evaluator as-is

    target = _yesno(node.value)
    if target is None:
        return node  # not a plain yes/no invocation -- can't safely substitute, leave opaque

    if node.key_name in chain:
        raise ScriptedTriggerCycleError(chain + (node.key_name,))
    if depth >= MAX_EXPANSION_DEPTH:
        raise ExpansionDepthExceededError(chain + (node.key_name,))

    new_chain = chain + (node.key_name,)
    inner_items = _expand_items(definition.body.items, catalog, new_chain, depth + 1)
    wrapper_key = "NOT" if target is False else "AND"
    wrapper_ident = Identifier(wrapper_key, node.line, node.column)
    return Assignment(wrapper_ident, "=", Block(inner_items, definition.body.line, definition.body.column), node.line, node.column)


def expand_scripted_triggers(block: Block | None, catalog: dict[str, ScriptedTriggerDefinition]) -> Block | None:
    """Recursively substitutes every scripted-trigger leaf inside `block` (typically a
    technology's `potential` block) with its real body, honouring the same AND/OR/NOT/NOR-only
    descent discipline `pipeline.availability` itself uses. `block=None` passes through unchanged
    (no `potential` at all is unconditionally available, same as before -- this module never
    changes that). Raises `ScriptedTriggerCycleError`/`ExpansionDepthExceededError` -- never
    silently truncates (see module docstring)."""
    if block is None:
        return None
    return Block(_expand_items(block.items, catalog, (), 0), block.line, block.column)
