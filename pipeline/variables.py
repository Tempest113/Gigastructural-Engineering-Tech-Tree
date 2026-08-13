"""Scripted-variable (`@name`) resolution.

Deliberately NOT part of `pipeline.clausewitz`, which stays a pure per-file, load-order-unaware
parser. This module is cross-file and load-order-aware — closer to Stage 2 ("Compute") than
Stage 1 ("Extract") in spec/00-overview.md's architecture, even though its inputs are Stage-1
ASTs and its output is consumed by later Stage-2 passes.

Design (approved after two rounds of evidence-gathering against the full vendored corpus, not
just the fixture subset — see tests/fixtures/NOTES.md's "variables/" section):

- Resolution is memoised recursive lookup, not a single sequential pass over declaration order.
  A variable may reference another variable declared later in the same file, or in a
  later-loaded source; `reference-chain.txt` deliberately declares in the reverse of dependency
  order to catch a resolver that assumes otherwise.
- Overwrites follow the same whole-key, last-definition-wins rule as P-15's technology
  overwrites (see `collect_definitions`), applied to the `@name` namespace instead. This is
  intentionally the *only* piece of machinery shared with P-15 — P-15 additionally needs an
  overwrite report for P-12.5's source field, which variable resolution has no use for, so it
  is not built here. Two small correct implementations beat one over-general one.
- Reference cycles and undefined references are both hard build failures (no partial dataset,
  no silent zero-substitution) — but this is NOT the same kind of thing as D-10's `unknown`
  trigger-evaluation tolerance. Trigger truth values are inherently undecidable from static
  analysis; an undefined or cyclic `@variable` is an ordinary data error with no equivalent
  excuse, so there is no tolerated percentage here.
- A resolved variable's value is NOT assumed to be numeric. `giga_amb_variables.txt`'s
  `@giga_amb_flag = giga_buildcap_j` resolves to a bare Identifier, not a NumberLiteral — this
  was carried as an unstated assumption in an earlier draft of this design and was caught before
  implementation. Valid terminal (non-reference) values are NumberLiteral, Identifier or
  StringLiteral; a Block or ParameterReference as a scripted variable's value is an error.
- Resolution produces a separate layer — `(resolved_value, original_node)` pairs, conceptually
  — rather than mutating the parsed AST in place. See VariableDefinition.value (the original,
  untouched node) vs. what `VariableTable.resolve()` returns (the resolved terminal node,
  possibly several hops away via other variables). P-15 already establishes this principle for
  overwrite diffing ("computed as a comparison after resolution, never applied to the
  authoritative graph"); this module follows the same rule for the same reason: re-runnable,
  testable in isolation, and never destroys the "was this a literal or a reference" distinction
  that P-12.6/S-2 provenance wants later.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Iterator, Union

from .clausewitz.nodes import (
    Assignment,
    Block,
    Comment,
    Document,
    Identifier,
    NumberLiteral,
    ParameterReference,
    StringLiteral,
    VariableReference,
)

# A resolved variable's terminal value: whatever it bottoms out at once every @-reference in
# the chain has been followed. Never a VariableReference (that would mean resolution isn't
# finished) and never a Block/ParameterReference (see InvalidVariableValueError).
ResolvedScalar = Union[NumberLiteral, Identifier, StringLiteral]

_VALID_TERMINAL_TYPES = (NumberLiteral, Identifier, StringLiteral)


@dataclass(frozen=True)
class VariableDefinition:
    """The winning `@name = value` definition for one name, after overwrite resolution.

    `value` is the original, unresolved AST node (possibly itself a VariableReference) —
    kept exactly as parsed; resolution never mutates it.
    """

    name: str
    value: object  # ScalarValue, but avoiding the import-time Union re-export noise here
    source_path: str
    line: int


class VariableError(Exception):
    """Base class for scripted-variable resolution failures."""


class UndefinedVariableError(VariableError):
    """`@name` has no definition anywhere in the merged, load-order-resolved table.

    `chain` is the resolution path that led here: empty if `name` itself was looked up
    directly (e.g. a technology's `cost = @name`), or the sequence of VariableDefinitions
    followed transitively if resolving some other variable's value led here.
    """

    def __init__(self, name: str, chain: list[VariableDefinition]):
        self.name = name
        self.chain = chain
        if chain:
            path = " -> ".join(f"@{d.name}" for d in chain)
            message = (
                f"undefined scripted variable '@{name}': reached via {path} -> @{name}, "
                f"but '@{name}' is not defined anywhere in the loaded sources"
            )
        else:
            message = f"undefined scripted variable '@{name}': not defined anywhere in the loaded sources"
        super().__init__(message)


class VariableCycleError(VariableError):
    """A variable's definition depends on itself, directly or transitively.

    `chain` is the full cycle in resolution order — chain[i] depends on chain[i+1], and
    chain[-1] depends on chain[0], closing the loop. Each entry carries its own winning
    source/line, so the message names not just the names involved but which file each one's
    winning definition came from.
    """

    def __init__(self, chain: list[VariableDefinition]):
        self.chain = chain
        names = " -> ".join(f"@{d.name}" for d in chain) + f" -> @{chain[0].name}"
        links = "; ".join(f"@{d.name} defined at {d.source_path}:{d.line}" for d in chain)
        super().__init__(f"scripted variable reference cycle: {names} ({links})")


class InvalidVariableValueError(VariableError):
    """A scripted variable's value is neither a scalar literal nor an @-reference."""

    def __init__(self, definition: VariableDefinition):
        self.definition = definition
        super().__init__(
            f"{definition.source_path}:{definition.line}: '@{definition.name}' has a "
            f"{type(definition.value).__name__} value, which cannot be a scripted variable's "
            f"value — expected a number, identifier, string, or another @variable reference"
        )


def collect_definitions(documents: Iterable[Document]) -> dict[str, VariableDefinition]:
    """Merge scripted-variable definitions across sources, in load order.

    Whole-key replacement: the last definition of a given name wins, whether that's a later
    duplicate within one file or the same name redefined in a later-loaded source. `documents`
    MUST already be in load order (vanilla, Gigastructures, ACOT, AoT — per
    spec/00-overview.md's "Sources and load order"); this function does not know or care which
    source a document came from, matching CLAUDE.md's "do not special-case vanilla vs. mod"
    rule — that's exactly what makes zz_giga_compat_overwrite_me.txt's fallback-then-overwritten
    @acot_tier* stubs work with no special-casing.
    """
    definitions: dict[str, VariableDefinition] = {}
    for document in documents:
        for item in document.items:
            if not isinstance(item, Assignment):
                continue
            definitions[item.key_name] = VariableDefinition(
                name=item.key_name,
                value=item.value,
                source_path=document.path,
                line=item.line,
            )
    return definitions


def iter_variable_references(document: Document) -> Iterator[VariableReference]:
    """Every `VariableReference` anywhere in a document — assignment values, bare block
    members, at any nesting depth. Used both to validate technology files' `@` usages and to
    validate scripted_variables files' own variable-to-variable references (there is no
    separate mechanism for the two; the same walk covers both, since a scripted_variables file
    is just a Document like any other)."""
    yield from _walk(document.items)


def _walk(items) -> Iterator[VariableReference]:
    for item in items:
        if isinstance(item, VariableReference):
            yield item
        elif isinstance(item, Assignment):
            if isinstance(item.value, VariableReference):
                yield item.value
            elif isinstance(item.value, Block):
                yield from _walk(item.value.items)
        elif isinstance(item, Block):
            yield from _walk(item.items)
        # Comment, Identifier, StringLiteral, NumberLiteral, ParameterReference: no references inside.


class VariableTable:
    """Resolves `@name` references against a merged definition table, memoised, with DFS cycle
    detection. Construct via `build_variable_table()`."""

    def __init__(self, definitions: dict[str, VariableDefinition]):
        self._definitions = definitions
        self._cache: dict[str, ResolvedScalar] = {}

    def resolve(self, name: str) -> ResolvedScalar:
        """Resolve `@name` to its terminal value, following any chain of @-references.
        Raises UndefinedVariableError or VariableCycleError; never returns a VariableReference."""
        return self._resolve(name, stack=[])

    def _resolve(self, name: str, stack: list[VariableDefinition]) -> ResolvedScalar:
        if name in self._cache:
            return self._cache[name]

        cycle_start = next((i for i, d in enumerate(stack) if d.name == name), None)
        if cycle_start is not None:
            raise VariableCycleError(stack[cycle_start:])

        definition = self._definitions.get(name)
        if definition is None:
            raise UndefinedVariableError(name, list(stack))

        value = definition.value
        if isinstance(value, _VALID_TERMINAL_TYPES):
            resolved = value
        elif isinstance(value, VariableReference):
            resolved = self._resolve(value.name, stack + [definition])
        else:
            raise InvalidVariableValueError(definition)

        self._cache[name] = resolved
        return resolved

    def validate_all(self, documents: Iterable[Document]) -> list[VariableError]:
        """Eagerly resolve every `@` reference found anywhere across `documents` (technology
        files, scripted_variables files, whatever else references a variable), batching every
        failure found rather than stopping at the first — same reporting philosophy as
        tools/regenerate_fixtures.py. Cycle errors are de-duplicated by the set of names
        involved, so a cycle reached from several different usage sites is reported once."""
        errors: list[VariableError] = []
        seen_cycles: set[frozenset[str]] = set()
        for document in documents:
            for ref in iter_variable_references(document):
                try:
                    self.resolve(ref.name)
                except VariableCycleError as exc:
                    key = frozenset(d.name for d in exc.chain)
                    if key not in seen_cycles:
                        seen_cycles.add(key)
                        errors.append(exc)
                except VariableError as exc:
                    errors.append(exc)
        return errors


def build_variable_table(documents_in_load_order: Iterable[Document]) -> VariableTable:
    """Convenience: collect_definitions() + wrap in a VariableTable, in one call."""
    documents_in_load_order = list(documents_in_load_order)
    return VariableTable(collect_definitions(documents_in_load_order))
