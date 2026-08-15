"""P-15: technology overwrite resolution.

Design settled against the vendored corpus survey, not assumed up front — see CLAUDE.md's
"Source data" section for the corrected counts and spec/P-15-overwrites.md for the full
requirement. Two load-bearing findings that shape this module:

- Overwriting is not vanilla-only. Gigastructures redefines 2 vanilla technologies, ACOT
  redefines 4 more directly, and AoT redefines 19 ACOT technologies — the largest single
  overwrite relationship in the corpus, with no vanilla baseline anywhere in that chain. So the
  diff baseline is always "the immediately-preceding definition in load order, whatever its
  source", never hardcoded to vanilla. No 3-or-deeper chain exists in the corpus — every
  overwritten key is touched by exactly one other source — but the resolver still refuses to
  guess if one ever appears (see `resolve_technology_overwrites`'s override requirement).
- A technology's effective cost/weight/tier can change without its own block being touched, via a
  `@scripted_variable` it references being redefined by a later source. This is a distinct
  overwrite mechanism from a technology-block redefinition (different cause, different repair),
  so it gets its own record type and its own section of the overwrite report — see
  `resolve_variable_overwrites` and `build_overwrite_report`.

Like pipeline.variables, this is cross-file and load-order-aware — closer to Stage 2 ("Compute")
than Stage 1 ("Extract") even though its inputs are Stage-1 ASTs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .clausewitz.nodes import (
    Assignment,
    Block,
    Document,
    Identifier,
    NumberLiteral,
    StringLiteral,
    VariableReference,
)
from .overwrite_overrides import OverwriteOverride
from .variables import VariableTable

# Lowest to highest priority — matches spec/00-overview.md and CLAUDE.md's "Source data" section.
SOURCE_ORDER = ("Vanilla", "Gigastructural Engineering", "ACOT", "AoT")

# spec/P-15-overwrites.md's acceptance criteria. Order here is also the canonical, deterministic
# order changed-field lists are reported in.
DIFF_FIELDS = ("cost", "tier", "prerequisites", "weight", "category", "flags")

# The only top-level `is_*` boolean fields actually found directly on a technology block across
# the full vendored corpus (confirmed by survey, not guessed) — see CLAUDE.md's "Source data"
# section. Anything else named `is_*` in the corpus lives inside a trigger block (`potential`,
# `prerequisites`, etc.), not as a direct technology-block field, and is out of scope for this
# "flags" diff.
FLAG_FIELDS = ("is_rare", "is_reverse_engineerable", "is_dangerous", "is_insight")


class OverwriteError(Exception):
    """Base class for overwrite-resolution failures."""


class UnknownSourceError(OverwriteError):
    def __init__(self, source_name: str):
        self.source_name = source_name
        super().__init__(f"unknown source {source_name!r}; expected one of {SOURCE_ORDER}")


class OverwriteOverrideRequiredError(OverwriteError):
    """A technology key's overwrite history is too ambiguous to resolve automatically (a 3+
    source chain, or a same-source duplicate) and no config/overwrite_overrides.txt entry names
    the winner — see that file for the two shapes this covers and why."""

    def __init__(self, key: str, sources_involved: tuple[str, ...], reason: str):
        self.key = key
        self.sources_involved = sources_involved
        self.reason = reason
        super().__init__(
            f"technology {key!r} needs an entry in config/overwrite_overrides.txt: {reason} "
            f"(sources involved: {', '.join(sources_involved)})"
        )


@dataclass(frozen=True)
class TechnologyDefinition:
    """One occurrence of a `key = { ... }` technology block, attributed to the source it was
    parsed from. `collect_technology_definitions` keeps every occurrence, in load order, not
    just the winner — the diff needs to see what was replaced."""

    key: str
    source: str
    document_path: str
    line: int
    block: Block


@dataclass(frozen=True)
class VariableDefinitionOccurrence:
    """One occurrence of an `@name = value` scripted-variable definition, attributed to source.
    Parallels TechnologyDefinition but for the `@name` namespace — kept separate from
    pipeline.variables.VariableDefinition, which deliberately doesn't carry source attribution
    (it has no use for it; P-15 does)."""

    name: str
    source: str
    document_path: str
    line: int


@dataclass(frozen=True)
class FieldChange:
    field: str
    before_present: bool
    after_present: bool
    before_raw: object
    after_raw: object
    before_resolved: object = None
    after_resolved: object = None


@dataclass(frozen=True)
class OverwriteRecord:
    key: str
    defined_by: str
    overwrites: str | None
    label: str
    changed_fields: list[str]
    field_changes: list[FieldChange]
    prerequisites_ordered: list[str]


@dataclass(frozen=True)
class VariableOverwriteRecord:
    name: str
    defined_by: str
    overwrites: str
    affected_technologies: list[str]


def collect_technology_definitions(
    sources: Iterable[tuple[str, Iterable[Document]]],
) -> dict[str, list[TechnologyDefinition]]:
    """`sources` is (source_name, documents) pairs, already in load order (vanilla,
    Gigastructural Engineering, ACOT, AoT). Returns key -> full occurrence history in load
    order."""
    history: dict[str, list[TechnologyDefinition]] = {}
    for source_name, documents in sources:
        if source_name not in SOURCE_ORDER:
            raise UnknownSourceError(source_name)
        for document in documents:
            for item in document.items:
                if isinstance(item, Assignment) and isinstance(item.value, Block):
                    history.setdefault(item.key_name, []).append(
                        TechnologyDefinition(item.key_name, source_name, document.path, item.line, item.value)
                    )
    return history


def collect_variable_definitions(
    sources: Iterable[tuple[str, Iterable[Document]]],
) -> dict[str, list[VariableDefinitionOccurrence]]:
    """Same shape as collect_technology_definitions, for the `@name` namespace (any Assignment,
    since a scripted_variables document's top-level statements are `@name = value`, keyed by a
    VariableReference — see Assignment.key_name)."""
    history: dict[str, list[VariableDefinitionOccurrence]] = {}
    for source_name, documents in sources:
        if source_name not in SOURCE_ORDER:
            raise UnknownSourceError(source_name)
        for document in documents:
            for item in document.items:
                if isinstance(item, Assignment):
                    history.setdefault(item.key_name, []).append(
                        VariableDefinitionOccurrence(item.key_name, source_name, document.path, item.line)
                    )
    return history


def _last_assignment(block: Block | None, key: str) -> Assignment | None:
    if block is None:
        return None
    result = None
    for item in block.items:
        if isinstance(item, Assignment) and item.key_name == key:
            result = item
    return result


def _raw_scalar_text(node) -> object:
    if node is None:
        return None
    if isinstance(node, NumberLiteral):
        return node.raw
    if isinstance(node, VariableReference):
        return f"@{node.name}"
    if isinstance(node, Identifier):
        return node.name
    if isinstance(node, StringLiteral):
        return node.value
    return None


def _resolved_scalar_text(node, variable_table: VariableTable | None) -> object:
    if node is None:
        return None
    if isinstance(node, VariableReference) and variable_table is not None:
        return _raw_scalar_text(variable_table.resolve(node.name))
    return _raw_scalar_text(node)


def _flatten_leaf_names(node) -> frozenset[str]:
    """Flatten a Block's bare-scalar leaves (recursively through nested blocks, including
    boolean-logic sub-blocks like OR/AND/NOR/NOT) into a set of names. Used for `prerequisites`
    and `category`, where declaration order carries no diff-relevant meaning (see
    spec/P-15-overwrites.md's "Prerequisite diffing and display ordering") but the set of
    referenced names does."""
    names: set[str] = set()

    def walk(n) -> None:
        if isinstance(n, Block):
            for it in n.items:
                walk(it)
        elif isinstance(n, Assignment):
            walk(n.value)
        elif isinstance(n, Identifier):
            names.add(n.name)
        elif isinstance(n, StringLiteral):
            names.add(n.value)
        # NumberLiteral / VariableReference / ParameterReference / Comment: not name-bearing here.

    walk(node)
    return frozenset(names)


def ordered_prerequisites(block: Block) -> list[str]:
    """Declaration-order, depth-first, first-occurrence list of every **true (AND-required)**
    technology key referenced in `block`'s `prerequisites` field. This is the DISPLAY order
    (spec/P-15-overwrites.md, P-12.4) — deliberately separate from the diff, which treats
    prerequisites as a set.

    **Correction (P-14 edge typing session)**: this previously flattened `OR`-branch members in
    alongside true prerequisites — e.g. `prerequisites = { tech_z OR = { tech_y tech_x } }`
    returned `[tech_z, tech_y, tech_x]`, treating an any-one-required alternative exactly like an
    all-required prerequisite. That's wrong for every consumer that treats this list
    conjunctively (P-16's rendering-scope closure, D-7's crisis-faction inheritance, this
    module's own P-12.4 display order) — see CLAUDE.md's "Prerequisites" section and
    `spec/decisions.md` for the corpus survey and measured impact. `OR`-branch members are now
    excluded here and returned separately by `alternative_prerequisite_groups` below — a
    technology's true prerequisites and its alternative-access groups are two different lists,
    never flattened back into one."""
    assignment = _last_assignment(block, "prerequisites")
    if assignment is None or not isinstance(assignment.value, Block):
        return []

    seen: set[str] = set()
    ordered: list[str] = []

    def walk(n) -> None:
        if isinstance(n, Block):
            for it in n.items:
                walk(it)
        elif isinstance(n, Assignment):
            if n.key_name.upper() == "OR":
                return  # OR-branch members are alternative prerequisites, not true ones -- see
                        # alternative_prerequisite_groups.
            walk(n.value)
        elif isinstance(n, Identifier):
            if n.name not in seen:
                seen.add(n.name)
                ordered.append(n.name)
        elif isinstance(n, StringLiteral):
            if n.value not in seen:
                seen.add(n.value)
                ordered.append(n.value)

    walk(assignment.value)
    return ordered


def alternative_prerequisite_groups(block: Block) -> list[list[str]]:
    """Every nested `OR = { ... }` group inside `block`'s `prerequisites` field, in declaration
    order, each as its own ordered, deduplicated member list. The real corpus contains only `OR`
    nested inside `prerequisites` — 0 `AND`/`NOR`/`NOT` (checked directly, not assumed; CLAUDE.md
    previously stated the general "OR/AND/NOR/NOT" case before this was verified). A technology
    can carry more than one `OR` group (3 of the corpus's 32 alternative-bearing technologies do,
    e.g. `tech_mega_engineering`'s `tech_starbase_5`|`tech_arkship_tier_3` grouped separately from
    `tech_battleships`|`tech_stingers`); callers needing a stable per-group identity (P-14's
    `Edge.groupId`) must combine this function's list index with the owning technology's key —
    this function itself is key-agnostic, matching `ordered_prerequisites`'s own signature."""
    assignment = _last_assignment(block, "prerequisites")
    if assignment is None or not isinstance(assignment.value, Block):
        return []

    groups: list[list[str]] = []

    def collect_members(n) -> list[str]:
        seen: set[str] = set()
        members: list[str] = []

        def walk(sub) -> None:
            if isinstance(sub, Block):
                for it in sub.items:
                    walk(it)
            elif isinstance(sub, Assignment) and sub.key_name.upper() == "OR" and isinstance(sub.value, Block):
                walk(sub.value)
            elif isinstance(sub, Identifier):
                if sub.name not in seen:
                    seen.add(sub.name)
                    members.append(sub.name)
            elif isinstance(sub, StringLiteral):
                if sub.value not in seen:
                    seen.add(sub.value)
                    members.append(sub.value)

        walk(n)
        return members

    def find_groups(n) -> None:
        if isinstance(n, Block):
            for it in n.items:
                find_groups(it)
        elif isinstance(n, Assignment):
            if n.key_name.upper() == "OR" and isinstance(n.value, Block):
                groups.append(collect_members(n.value))
            else:
                find_groups(n.value)

    find_groups(assignment.value)
    return groups


def _diff_scalar_field(
    name: str, before: Block | None, after: Block, variable_table: VariableTable | None
) -> tuple[bool, FieldChange]:
    before_assign = _last_assignment(before, name)
    after_assign = _last_assignment(after, name)
    before_val = before_assign.value if before_assign else None
    after_val = after_assign.value if after_assign else None
    before_present = before_assign is not None
    after_present = after_assign is not None
    before_raw = _raw_scalar_text(before_val)
    after_raw = _raw_scalar_text(after_val)
    before_resolved = _resolved_scalar_text(before_val, variable_table)
    after_resolved = _resolved_scalar_text(after_val, variable_table)
    changed = (before_present != after_present) or (before_resolved != after_resolved)
    return changed, FieldChange(name, before_present, after_present, before_raw, after_raw, before_resolved, after_resolved)


def _diff_set_field(name: str, before: Block | None, after: Block) -> tuple[bool, FieldChange]:
    before_assign = _last_assignment(before, name)
    after_assign = _last_assignment(after, name)
    before_present = before_assign is not None
    after_present = after_assign is not None
    before_set = _flatten_leaf_names(before_assign.value) if before_assign else frozenset()
    after_set = _flatten_leaf_names(after_assign.value) if after_assign else frozenset()
    changed = (before_present != after_present) or (before_set != after_set)
    return changed, FieldChange(
        name, before_present, after_present, sorted(before_set), sorted(after_set), sorted(before_set), sorted(after_set)
    )


def _diff_flags_field(before: Block | None, after: Block) -> tuple[bool, FieldChange]:
    def snapshot(block: Block | None) -> dict[str, object]:
        result: dict[str, object] = {}
        if block is None:
            return result
        for item in block.items:
            if isinstance(item, Assignment) and item.key_name in FLAG_FIELDS:
                result[item.key_name] = _raw_scalar_text(item.value)
        return result

    before_flags = snapshot(before)
    after_flags = snapshot(after)
    changed = before_flags != after_flags
    return changed, FieldChange("flags", bool(before_flags), bool(after_flags), before_flags, after_flags, before_flags, after_flags)


def diff_technology(
    before: TechnologyDefinition | None, after: TechnologyDefinition, variable_table: VariableTable
) -> tuple[list[str], list[FieldChange]]:
    """Field-level diff of `after` against `before` (the immediately-preceding definition in
    load order, or None if this technology was never redefined). `cost`/`weight` are resolved
    through `variable_table` before comparing (so an indirect scripted-variable overwrite is
    visible), but the pre-resolution raw form is retained on the FieldChange alongside the
    resolved value — a literal-to-variable-reference change is a mechanism change, not just a
    value change, and collapsing the two would flatten that distinction away."""
    if before is None:
        return [], []

    field_changes: list[FieldChange] = []
    changed_names: set[str] = set()

    for name in ("cost", "weight"):
        changed, fc = _diff_scalar_field(name, before.block, after.block, variable_table)
        field_changes.append(fc)
        if changed:
            changed_names.add(name)

    changed, fc = _diff_scalar_field("tier", before.block, after.block, None)
    field_changes.append(fc)
    if changed:
        changed_names.add("tier")

    for name in ("prerequisites", "category"):
        changed, fc = _diff_set_field(name, before.block, after.block)
        field_changes.append(fc)
        if changed:
            changed_names.add(name)

    changed, fc = _diff_flags_field(before.block, after.block)
    field_changes.append(fc)
    if changed:
        changed_names.add("flags")

    changed_fields = [f for f in DIFF_FIELDS if f in changed_names]
    return changed_fields, field_changes


def resolve_technology_overwrites(
    history: dict[str, list[TechnologyDefinition]],
    variable_table: VariableTable,
    overrides: dict[str, OverwriteOverride] | None = None,
) -> dict[str, OverwriteRecord]:
    """Resolve every technology key's winning definition and, if it replaced something, diff it
    against what it replaced. Whole-key replacement, last-source-wins by default — but a key
    whose history is a 3+ source chain, or has more than one occurrence from the SAME source,
    is refused unless `config/overwrite_overrides.txt` names the winner (see
    OverwriteOverrideRequiredError and that file's header)."""
    overrides = overrides or {}
    records: dict[str, OverwriteRecord] = {}
    for key, occurrences in history.items():
        sources_involved = tuple(occ.source for occ in occurrences)
        same_source_run = any(
            sources_involved[i] == sources_involved[i + 1] for i in range(len(sources_involved) - 1)
        )
        distinct_sources = len(set(sources_involved))

        override = overrides.get(key)
        if (distinct_sources >= 3 or same_source_run) and override is None:
            reason = "3 or more sources define this key" if distinct_sources >= 3 else "the same source defines this key more than once"
            raise OverwriteOverrideRequiredError(key, sources_involved, reason)

        if override is not None:
            winner = next(occ for occ in occurrences if occ.source == override.winning_source)
            previous_candidates = [occ for occ in occurrences if occ is not winner]
            previous = previous_candidates[-1] if previous_candidates else None
        else:
            winner = occurrences[-1]
            previous = occurrences[-2] if len(occurrences) >= 2 else None

        overwrites_source = previous.source if previous else None
        label = f"{overwrites_source} (modified by {winner.source})" if overwrites_source else winner.source
        changed_fields, field_changes = diff_technology(previous, winner, variable_table)

        records[key] = OverwriteRecord(
            key=key,
            defined_by=winner.source,
            overwrites=overwrites_source,
            label=label,
            changed_fields=changed_fields,
            field_changes=field_changes,
            prerequisites_ordered=ordered_prerequisites(winner.block),
        )
    return records


def resolve_variable_overwrites(
    variable_history: dict[str, list[VariableDefinitionOccurrence]],
    technology_history: dict[str, list[TechnologyDefinition]],
) -> list[VariableOverwriteRecord]:
    """The scripted-variable overwrite layer, distinct from technology-block overwrites: a
    `@name` redefined by a later source changes the effective cost/weight/tier of every WINNING
    technology (across any source) whose `cost`/`weight`/`tier` still references that name, even
    though those technologies' own blocks were never touched. Only the winning technology
    definitions are considered — a technology that was itself overwritten no longer contributes
    its old cost/weight/tier reference to anything.

    `tier` was added to this check (alongside the original `cost`/`weight`) after the P-2 layout
    tier-source audit found 83/980 rendered nodes declare `tier` as a `@variable` reference —
    exactly the shape this layer exists to catch if one of those variables is ever redefined
    cross-source. No current case is affected (verified, not assumed — see
    tests/test_overwrites_corpus.py), but leaving `tier` unchecked here would have been a silent
    blind spot for exactly the class of bug ("wrong tier placement") v1 reported as a real
    failure."""
    results: list[VariableOverwriteRecord] = []
    for name in sorted(variable_history):
        occurrences = variable_history[name]
        if len(occurrences) < 2:
            continue
        winner = occurrences[-1]
        previous = occurrences[-2]
        if winner.source == previous.source:
            continue

        affected: list[str] = []
        for key, occs in technology_history.items():
            winning_def = occs[-1]
            for field_name in ("cost", "weight", "tier"):
                assignment = _last_assignment(winning_def.block, field_name)
                if (
                    assignment is not None
                    and isinstance(assignment.value, VariableReference)
                    and assignment.value.name == name
                ):
                    affected.append(key)
                    break

        if affected:
            results.append(VariableOverwriteRecord(name, winner.source, previous.source, sorted(affected)))
    return results


def build_overwrite_report(
    technology_records: dict[str, OverwriteRecord], variable_records: list[VariableOverwriteRecord]
) -> dict:
    """S-2 machine-readable overwrite report — dev-diagnostics artefact, separate from per-node
    dataset output. Two distinct sections (spec/P-15-overwrites.md): technology-block overwrites
    and scripted-variable overwrites. Never collapsed into one list — different causes, different
    repairs, a reader needs to tell them apart."""
    technology_section = []
    for key in sorted(technology_records):
        record = technology_records[key]
        if record.overwrites is None:
            continue
        technology_section.append(
            {
                "technology": key,
                "definedBy": record.defined_by,
                "overwrites": record.overwrites,
                "label": record.label,
                "changedFields": record.changed_fields,
                "fieldChanges": [
                    {
                        "field": fc.field,
                        "beforePresent": fc.before_present,
                        "afterPresent": fc.after_present,
                        "beforeRaw": fc.before_raw,
                        "afterRaw": fc.after_raw,
                        "beforeResolved": fc.before_resolved,
                        "afterResolved": fc.after_resolved,
                    }
                    for fc in record.field_changes
                ],
            }
        )

    variable_section = [
        {
            "variable": vr.name,
            "definedBy": vr.defined_by,
            "overwrites": vr.overwrites,
            "affectedTechnologies": vr.affected_technologies,
        }
        for vr in variable_records
    ]

    return {
        "technologyBlockOverwrites": technology_section,
        "scriptedVariableOverwrites": variable_section,
    }
