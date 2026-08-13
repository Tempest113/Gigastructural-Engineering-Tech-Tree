"""`inline_script` expansion.

Design approved after a corpus survey (raw text, not any formatting layer — see
tests/fixtures/NOTES.md's inline_script-related fixtures for the specific evidence cited
throughout this module) — see spec/implementation-notes.md's "inline_script expansion" section
for the normative version of this design.

Key decisions, and why:

- **Text substitution on raw source, before tokenising — not AST-node substitution.** ~46% of
  real `$PARAM$` usage is embedded mid-token (e.g. a target's own key built as
  `giga_tech_repeatable_$name$_cap`), which a standalone `ParameterReference` AST node cannot
  represent. So expansion reads the target file's raw text, replaces `$NAME$` spans textually,
  and only then tokenises+parses the result with the ordinary, unmodified Clausewitz parser.
- **Runs before `@variable` resolution.** A parameter's value can itself be `@variable` syntax
  (`AMOUNT = @doubled_scaling_district_2_jobs`); after substitution that's just ordinary
  `@variable` syntax sitting in the expanded tree, which pipeline.variables handles with no
  inline_script-specific knowledge.
- **A block splice, not a value substitution.** The `inline_script` assignment is removed from
  its parent block and replaced by the target's (expanded) items — confirmed necessary by the
  `giga_mega_repeatable` case, where the *invoking* technology supplies the tech's own key and
  the target supplies only inner fields. Produces a new Document/Block; the original parsed AST
  is never mutated (same principle as pipeline.variables, for the same P-15/P-12.6 provenance
  reason).
- **Missing parameter → warning, not failure.** Confirmed to occur in real vanilla content
  (`grand_archive/collection/stage_3_reward_option` references `$RELIC$`, one real invocation
  never supplies it). The literal `$NAME$` text is left unsubstituted in that position, so the
  final tree contains a visible `ParameterReference` marker rather than a fabricated value.
- **Unused parameter → logged at debug level, not silently discarded.** A misspelled parameter
  name produces both a missing parameter (correct name, never supplied) and an unused one
  (misspelled name, supplied but ignored) at the same site; keeping both visible is what makes
  that pairing diagnosable as a typo.
- **Depth and size limits are hard failures.** No structural cycle exists in the corpus today
  (verified on the *parsed* AST, quote-aware — a naive raw-text scan finds false "cycles" inside
  the `code = "..."` embedded-script-as-string-data idiom), but that doesn't bound a future
  upstream change introducing runaway breadth without ever forming a cycle.
- **Script-path load-order overwrites get their own small table**, structurally identical to
  `pipeline.variables.collect_definitions` but deliberately not shared code with it — the two
  namespaces (`@name`, script path) don't overlap and gain nothing from being forced through one
  general mechanism (same reasoning as why this doesn't share machinery with P-15's technology
  overwrite report either).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

from .clausewitz import parse_text
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

# Observed real maximum nesting depth in the corpus: 6 (buildings/elysium/giga_elysium_host_jobs
# chain). 32 gives roughly 5x headroom for legitimate growth while still catching runaway
# recursion a future upstream change might introduce.
MAX_EXPANSION_DEPTH = 32

# Total AST items spliced across one top-level invocation's full (recursive) expansion. Real
# invocations are small (the largest observed supplies 32 parameters; target bodies are a few
# dozen statements) — this is generous relative to that, not a tight fit, but still bounded.
MAX_EXPANDED_SIZE = 200_000

_PARAM_PATTERN = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)\$")

# The synthetic key used to smuggle target-file content through the ordinary Document parser as
# a single Block, so expansion needs zero new parser API surface — see _parse_block_contents.
_SPLICE_WRAPPER_KEY = "__inline_script_expansion__"


class InlineScriptError(Exception):
    """Base class for inline_script expansion failures (all hard build failures)."""


class UnresolvedScriptError(InlineScriptError):
    """`script = path` doesn't resolve to any file in the loaded sources."""

    def __init__(self, path: str, chain: list[str]):
        self.path = path
        self.chain = chain
        trail = " -> ".join(chain + [path]) if chain else path
        super().__init__(f"unresolved inline_script: {trail} — '{path}' is not defined anywhere in the loaded sources")


class ExpansionDepthExceededError(InlineScriptError):
    def __init__(self, chain: list[str]):
        self.chain = chain
        super().__init__(
            f"inline_script expansion exceeded MAX_EXPANSION_DEPTH ({MAX_EXPANSION_DEPTH}): "
            f"{' -> '.join(chain)}"
        )


class ExpansionSizeExceededError(InlineScriptError):
    def __init__(self, chain: list[str], size: int):
        self.chain = chain
        self.size = size
        super().__init__(
            f"inline_script expansion exceeded MAX_EXPANDED_SIZE ({MAX_EXPANDED_SIZE}, reached "
            f"{size}): {' -> '.join(chain)}"
        )


class InlineScriptCycleError(InlineScriptError):
    """A script's expansion (structurally, in the parsed AST) invokes itself, directly or
    transitively. Distinct from the string-embedded "code as data" recursion idiom, which is
    never mistaken for this because string content is opaque and never walked as script."""

    def __init__(self, chain: list[str]):
        self.chain = chain
        super().__init__(f"inline_script cycle: {' -> '.join(chain)} -> {chain[0]}")


@dataclass(frozen=True)
class ScriptDefinition:
    """The winning `script = path` target for one relative path, after load-order overwrite
    resolution. `raw_text` is the target file's raw source — substitution happens on this,
    before any tokenising."""

    path: str
    source_path: str
    raw_text: str


@dataclass(frozen=True)
class MissingParameterWarning:
    """`$parameter$` appears in a script body but the invocation never supplied it. Non-fatal —
    see module docstring."""

    parameter: str
    script_path: str
    invocation_path: str
    invocation_line: int

    def __str__(self) -> str:
        return (
            f"{self.invocation_path}:{self.invocation_line}: inline_script invocation of "
            f"'{self.script_path}' does not supply '{self.parameter}', which the script body "
            f"references"
        )


@dataclass(frozen=True)
class UnusedParameterInfo:
    """A parameter was supplied at an invocation but the script body never references it.
    Logged at debug level, not a warning — see module docstring."""

    parameter: str
    script_path: str
    invocation_path: str
    invocation_line: int

    def __str__(self) -> str:
        return (
            f"{self.invocation_path}:{self.invocation_line}: inline_script invocation of "
            f"'{self.script_path}' supplies unused parameter '{self.parameter}'"
        )


@dataclass
class ExpansionReport:
    missing_parameters: list[MissingParameterWarning] = field(default_factory=list)
    unused_parameters: list[UnusedParameterInfo] = field(default_factory=list)


def collect_scripts(entries: Iterable[tuple[str, str, str]]) -> dict[str, ScriptDefinition]:
    """Merge script definitions across sources, in load order: entries are
    `(relative_path, source_file_path, raw_text)`. Whole-key replacement: the last definition of
    a given relative path wins — same rule as P-15's technology overwrites and
    pipeline.variables.collect_definitions' variable overwrites, applied to a third namespace."""
    table: dict[str, ScriptDefinition] = {}
    for path, source_file, raw_text in entries:
        table[path] = ScriptDefinition(path=path, source_path=source_file, raw_text=raw_text)
    return table


def _raw_source_text(node) -> str:
    """Reconstruct the literal source text a parameter's supplied value had, for textual
    substitution into a target script's body — sigils and quotes included, so a forwarded
    `@variable` reference or `$parameter$` pass-through survives substitution as the same kind
    of reference, and a quoted string stays quoted."""
    if isinstance(node, Identifier):
        return node.name
    if isinstance(node, NumberLiteral):
        return node.raw
    if isinstance(node, StringLiteral):
        return f'"{node.raw}"'
    if isinstance(node, VariableReference):
        return f"@{node.name}"
    if isinstance(node, ParameterReference):
        return f"${node.name}$"
    raise InlineScriptError(f"cannot use a {type(node).__name__} as an inline_script parameter value")


def _extract_invocation(value) -> tuple[str, dict[str, object]]:
    """From an `inline_script` assignment's value, return (script_path, {param_name: value_node}).
    Handles both bare (`inline_script = path`) and structured
    (`inline_script = { script = path  PARAM = value ... }`) forms — they unify here."""
    if isinstance(value, Identifier):
        return value.name, {}
    if isinstance(value, Block):
        script_path = None
        params: dict[str, object] = {}
        for item in value.items:
            if isinstance(item, Comment):
                continue
            if not isinstance(item, Assignment):
                continue
            if item.key_name == "script":
                script_path = item.value.name if isinstance(item.value, Identifier) else _raw_source_text(item.value)
            else:
                params[item.key_name] = item.value
        if script_path is None:
            raise InlineScriptError("inline_script block has no 'script = ...' member")
        return script_path, params
    raise InlineScriptError(f"inline_script value must be a path or a block, not {type(value).__name__}")


def _substitute(raw_text: str, params: dict[str, object], *, script_path: str, invocation_path: str, invocation_line: int, report: ExpansionReport) -> str:
    param_text = {name: _raw_source_text(node) for name, node in params.items()}
    used: set[str] = set()

    def repl(match: re.Match) -> str:
        name = match.group(1)
        used.add(name)
        if name in param_text:
            return param_text[name]
        report.missing_parameters.append(
            MissingParameterWarning(parameter=name, script_path=script_path, invocation_path=invocation_path, invocation_line=invocation_line)
        )
        return match.group(0)  # leave the literal $NAME$ in place — a visible "unresolved" marker

    substituted = _PARAM_PATTERN.sub(repl, raw_text)

    for name in param_text:
        if name not in used:
            report.unused_parameters.append(
                UnusedParameterInfo(parameter=name, script_path=script_path, invocation_path=invocation_path, invocation_line=invocation_line)
            )

    return substituted


def _parse_block_contents(text: str, path: str) -> list:
    """Parse `text` as block CONTENTS (assignments, bare values and comments — the grammar a
    target script's spliced content needs, not the assignments-only grammar a document root
    requires) by wrapping it in a synthetic `KEY = { ... }` and unwrapping the resulting Block.
    Reuses the ordinary parser verbatim; no new parser API surface."""
    # A newline must separate the interpolated text from both wrapper braces:
    # if the target's own last line is an unterminated `#`-comment, an appended
    # `}` on the same line is swallowed into that comment instead of becoming
    # a real token, leaving the wrapper's opening `{` unclosed.
    wrapped = f"{_SPLICE_WRAPPER_KEY} = {{\n{text}\n}}\n"
    doc = parse_text(wrapped, path=path)
    wrapper = doc.items[0]
    assert isinstance(wrapper, Assignment) and isinstance(wrapper.value, Block)
    return wrapper.value.items


@dataclass
class _ExpansionState:
    scripts: dict[str, ScriptDefinition]
    report: ExpansionReport
    total_size: int = 0

    def charge(self, n: int, chain: list[str]) -> None:
        self.total_size += n
        if self.total_size > MAX_EXPANDED_SIZE:
            raise ExpansionSizeExceededError(chain, self.total_size)


def _expand_items(items: list, state: _ExpansionState, chain: list[str], invocation_path: str) -> list:
    """Expand every `inline_script` assignment found anywhere in `items`, at any nesting depth
    — not just at this exact list's own top level. An invocation is very rarely a direct
    sibling of the technology's own root fields; it is usually nested inside `potential`,
    `weight_modifier`, etc., so every Block-valued Assignment must be recursed into and
    rebuilt, whether or not it itself needs expansion."""
    result = []
    for item in items:
        if isinstance(item, Assignment) and item.key_name == "inline_script":
            result.extend(_expand_invocation(item, state, chain, invocation_path))
        elif isinstance(item, Assignment) and isinstance(item.value, Block):
            new_items = _expand_items(item.value.items, state, chain, invocation_path)
            new_block = Block(items=new_items, line=item.value.line, column=item.value.column)
            result.append(Assignment(key=item.key, operator=item.operator, value=new_block, line=item.line, column=item.column))
            state.charge(1, chain)
        else:
            result.append(item)
            state.charge(1, chain)
    return result


def _expand_invocation(invocation: Assignment, state: _ExpansionState, chain: list[str], invocation_path: str) -> list:
    script_path, params = _extract_invocation(invocation.value)

    if len(chain) >= MAX_EXPANSION_DEPTH:
        raise ExpansionDepthExceededError(chain + [script_path])
    if script_path in chain:
        raise InlineScriptCycleError(chain[chain.index(script_path):] + [script_path])

    definition = state.scripts.get(script_path)
    if definition is None:
        raise UnresolvedScriptError(script_path, chain)

    substituted_text = _substitute(
        definition.raw_text,
        params,
        script_path=script_path,
        invocation_path=invocation_path,
        invocation_line=invocation.line,
        report=state.report,
    )
    target_items = _parse_block_contents(substituted_text, path=definition.source_path)

    new_chain = chain + [script_path]
    expanded = _expand_items(target_items, state, new_chain, invocation_path=definition.source_path)
    state.charge(len(expanded), new_chain)
    return expanded


def expand_document(document: Document, scripts: dict[str, ScriptDefinition]) -> tuple[Document, ExpansionReport]:
    """Return a NEW Document with every `inline_script` assignment, at any depth, replaced by
    its expanded, parameter-substituted content. `document` itself is never mutated. Raises
    InlineScriptError (or a subclass) on an unresolved script path, a depth/size limit breach,
    or a genuine structural cycle; missing/unused parameters are collected in the returned
    ExpansionReport rather than raised."""
    state = _ExpansionState(scripts=scripts, report=ExpansionReport())
    expanded_items = _expand_items(document.items, state, chain=[], invocation_path=document.path)
    return Document(items=expanded_items, path=document.path), state.report
