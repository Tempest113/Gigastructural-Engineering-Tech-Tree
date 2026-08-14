"""AST node types for the lossless Clausewitz AST (spec/00-overview.md, Stage 1).

Design notes:

- Duplicate keys are preserved simply by never collapsing a block's contents into a dict —
  `Block.items` (and `Document.items`) is an ordered list, so two `modifier = { ... }` entries
  in the same block are just two `Assignment` list entries, in source order. `assignments_by_key`
  is a derived, on-demand convenience view (a dict of *ordered lists*) for callers that want to
  look up "all the `modifier` entries" without walking the list themselves; it is never the
  source of truth and nothing is lost by not calling it.
- `@variable` references are NOT resolved here — `VariableReference.name` carries the bare name
  (without the `@` sigil) and nothing else. Resolving it against scripted_variables/ is a later,
  separate pass (per the parser's own docstring and CLAUDE.md's stage boundaries).
- `inline_script` is not expanded here either — it is just an ordinary `Assignment` whose value
  happens to be a path-shaped `Identifier` (bare form) or a `Block` containing a `script = ...`
  member and parameters (structured form). Expansion is a separate pass.
- Comparison operators (`=`, `<`, `>`, `<=`, `>=`, `!=`) are preserved verbatim on `Assignment`;
  this parser does not interpret what they mean (that's Stage 2's trigger evaluator).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Union


@dataclass
class Comment:
    """A `#`-to-end-of-line comment, preserved with its position.

    `text` is everything after the `#`, verbatim (not stripped), so the exact original text is
    recoverable. Comments can appear anywhere a statement or block member can.
    """

    text: str
    line: int
    column: int


@dataclass
class Identifier:
    """A bare (unquoted) name: a key, or a bare scalar value.

    Continuation characters include `/`, because unquoted `inline_script`-style path values
    (e.g. `technology/tech_weight_boni/defensive_tech_weight_bonus`) are real, observed
    Clausewitz syntax — see tests/fixtures/NOTES.md and the fixtures under
    gigastructures/common/inline_scripts/.
    """

    name: str
    line: int
    column: int


@dataclass
class StringLiteral:
    """A double-quoted string value, with escapes (`\\"`, `\\\\`) already resolved.

    `raw` keeps the original source text between the quotes (escapes un-resolved), for callers
    that need byte-for-byte fidelity; `value` is the resolved, ready-to-use string.
    """

    value: str
    raw: str
    line: int
    column: int


@dataclass
class NumberLiteral:
    """A numeric literal. `value` is `int` when the source had no decimal point, else `float`;
    `raw` is the exact source text (so a leading `-` or trailing zeros are always recoverable).
    """

    value: Union[int, float]
    raw: str
    line: int
    column: int


@dataclass
class VariableReference:
    """An unresolved `@name` scripted-variable reference. `name` excludes the `@` sigil."""

    name: str
    line: int
    column: int


@dataclass
class ParameterReference:
    """An unresolved `$NAME$` inline_script parameter reference (e.g. `has_technology =
    $TECHNOLOGY$` inside an inline_script body). `name` excludes both `$` delimiters.

    Distinct from `VariableReference`: this is the inline_script parameter-substitution
    mechanism, resolved by whatever caller supplies `NAME = value` when invoking the script —
    a different mechanism from `@variable` (resolved against scripted_variables/), and both are
    out of scope for this parser (expansion is a separate pass, same as inline_script itself).

    `default` carries the fallback text of a `$NAME|default$` reference verbatim (unresolved,
    not type-converted), or `None` if the reference had no `|default` suffix. `safe` is `True`
    for a `$NAME$?` reference — the same trailing "safe scope" marker recognised on bare
    identifiers (`space_owner? = { ... }`), just attached to a parameter reference instead; kept
    off `name` (unlike the identifier case) because `name` is a lookup key into the invocation's
    parameter table, and corrupting it would break that lookup. Both confirmed real — see
    tests/fixtures/NOTES.md's scripted_triggers/ entries.
    """

    name: str
    line: int
    column: int
    default: str | None = None
    safe: bool = False


ScalarValue = Union[Identifier, StringLiteral, NumberLiteral, VariableReference, ParameterReference]


@dataclass
class ConditionalBlock:
    """A `[[GUARD] ... ]` (or negated `[[!GUARD] ... ]`) conditional-inclusion block: `items`
    (same shapes a `Block` can hold — assignments, bare scalars, comments, nested
    `ConditionalBlock`s) are only meant to be included when the invoking `inline_script`
    invocation did (or, if `negated`, did not) supply a parameter named `guard`. Confirmed real
    across `common/scripted_triggers/` in all four sources — e.g. `[[HABITABILITY]
    HABITABILITY = $HABITABILITY$ ]`, `[[!SPECIES] ... ]`.

    Resolving the condition (does this invocation supply `guard`?) is a later pass's job, same
    as `$PARAM$` substitution generally — this parser only needs to not choke on the syntax and
    preserve it losslessly. `guard` excludes the `!` and both `[`/`]` delimiters.
    """

    guard: str
    negated: bool
    items: list[Union["Assignment", "ScalarValue", Comment]] = field(default_factory=list)
    line: int = 0
    column: int = 0


@dataclass
class Block:
    """A `{ ... }` block: an ordered list of assignments, bare scalar values, comments and
    conditional-inclusion blocks.

    Bare scalar values (e.g. `category = { voidcraft }`, `prerequisites = { "tech_a" tech_b }`)
    are only valid *inside* a block — see `Document`.
    """

    items: list[Union["Assignment", ScalarValue, Comment, ConditionalBlock]] = field(default_factory=list)
    line: int = 0
    column: int = 0

    def assignments_by_key(self) -> dict[str, list["Assignment"]]:
        """Derived view: key -> ordered list of Assignments with that key.

        Convenience only; `items` (in source order, duplicates and all) remains the source of
        truth. See module docstring. `ConditionalBlock` items are opaque to this view — their
        own nested assignments aren't flattened up into it, matching how a nested `Block`'s
        assignments aren't either.
        """
        grouped: dict[str, list["Assignment"]] = {}
        for item in self.items:
            if isinstance(item, Assignment):
                grouped.setdefault(item.key_name, []).append(item)
        return grouped


AssignmentKey = Union[Identifier, StringLiteral, NumberLiteral, VariableReference, ParameterReference]
AssignmentValue = Union[ScalarValue, Block]


@dataclass
class Assignment:
    """A `KEY OP VALUE` statement, e.g. `cost = @tier1cost1`, `count > 0`, `weight_modifier = { ... }`.

    `operator` is one of `=`, `<`, `>`, `<=`, `>=`, `!=`, preserved verbatim — this parser does
    not interpret it. `key` is most often an `Identifier`, but every scripted_variables
    statement's key is a `VariableReference` (`@name = value`) — the parser accepts any scalar
    token type as a key, so `key_name` below must too.
    """

    key: AssignmentKey
    operator: str
    value: AssignmentValue
    line: int
    column: int

    @property
    def key_name(self) -> str:
        """The key's text, regardless of which scalar token type it was — a bare Identifier, a
        quoted string, a numeric literal, an `@variable` or a `$parameter` are all valid key
        tokens in Clausewitz script (the last two mainly seen as `@name = value` scripted
        variable definitions)."""
        if isinstance(self.key, Identifier):
            return self.key.name
        if isinstance(self.key, StringLiteral):
            return self.key.value
        if isinstance(self.key, NumberLiteral):
            return self.key.raw
        # VariableReference / ParameterReference both carry a bare `.name`.
        return self.key.name


@dataclass
class Document:
    """The root of a parsed file: an ordered list of top-level Assignments and Comments.

    Unlike `Block`, a `Document`'s root may NOT contain bare scalar values — every real
    Clausewitz technology file is a sequence of `tech_id = { ... }` assignments (and comments),
    never a loose scalar at the top level. (tests/fixtures/malformed/stray-token.txt exists
    specifically to exercise this rule.)
    """

    items: list[Union[Assignment, Comment]]
    path: str

    def assignments_by_key(self) -> dict[str, list[Assignment]]:
        grouped: dict[str, list[Assignment]] = {}
        for item in self.items:
            if isinstance(item, Assignment):
                grouped.setdefault(item.key_name, []).append(item)
        return grouped
