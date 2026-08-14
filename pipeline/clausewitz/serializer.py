"""Naive round-trip serialiser for the Clausewitz AST (spec/00-overview.md's lossless-AST
requirement).

This module is deliberately dumb: it emits exactly what each node claims to hold and nothing
more. It does not try to reproduce the source file's original whitespace, indentation, or blank
lines — those are not represented in the AST at all (see pipeline/clausewitz/nodes.py), so any
attempt to guess them here would be fabrication, not serialisation. Items within a block or
document are joined with a single newline; nothing else about layout is claimed to be preserved.

Used as a corruption detector: `pipeline/clausewitz/roundtrip.py` re-tokenises this serialiser's
output and diffs it against the original source (after a small, explicit, justified whitespace
normalisation) to catch parser bugs where a file parses cleanly into the *wrong* AST — see that
module's docstring for the normalisation set and the reasoning behind it.
"""

from __future__ import annotations

from .nodes import (
    Assignment,
    Block,
    Comment,
    ConditionalBlock,
    Document,
    Identifier,
    NumberLiteral,
    ParameterReference,
    StringLiteral,
    VariableReference,
)


def serialize_document(doc: Document) -> str:
    return _serialize_items(doc.items)


def _serialize_items(items: list) -> str:
    return "\n".join(_serialize_item(item) for item in items)


def _serialize_item(item) -> str:
    if isinstance(item, Assignment):
        return _serialize_assignment(item)
    if isinstance(item, Comment):
        return _serialize_comment(item)
    if isinstance(item, ConditionalBlock):
        return _serialize_conditional_block(item)
    return _serialize_scalar(item)


def _serialize_assignment(node: Assignment) -> str:
    return f"{_serialize_scalar(node.key)} {node.operator} {_serialize_value(node.value)}"


def _serialize_value(value) -> str:
    if isinstance(value, Block):
        return _serialize_block(value)
    return _serialize_scalar(value)


def _serialize_block(node: Block) -> str:
    if not node.items:
        return "{}"
    return "{\n" + _serialize_items(node.items) + "\n}"


def _serialize_conditional_block(node: ConditionalBlock) -> str:
    guard = ("!" if node.negated else "") + node.guard
    if not node.items:
        return f"[[{guard}]]"
    return f"[[{guard}]\n" + _serialize_items(node.items) + "\n]"


def _serialize_comment(node: Comment) -> str:
    return f"#{node.text}"


def _serialize_scalar(node) -> str:
    if isinstance(node, Identifier):
        return node.name
    if isinstance(node, StringLiteral):
        return f'"{node.raw}"'
    if isinstance(node, NumberLiteral):
        return node.raw
    if isinstance(node, VariableReference):
        return f"@{node.name}"
    if isinstance(node, ParameterReference):
        default = f"|{node.default}" if node.default is not None else ""
        safe = "?" if node.safe else ""
        return f"${node.name}{default}${safe}"
    raise AssertionError(f"not a serialisable scalar node: {type(node).__name__}")
