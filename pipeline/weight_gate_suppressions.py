"""Loader for `config/weight_gate_suppressions.txt` -- read that file first for what an entry
means, why it exists, the exact grammar, and the review bar for adding one.

This module owns two things: parsing the config file into `WeightGateSuppression` rules, and
matching those rules against real `Assignment` leaves inside a zero-factor `weight_modifier`
condition block (`find_suppressed_leaves`, `apply_suppressions`). `pipeline.dataset_emit.
build_context` runs `apply_suppressions` once per technology's zero-factor condition blocks (the
same ones `pipeline.availability._apply_weight_gate` evaluates), producing an `id(Assignment) ->
resolved bool` map threaded into every `evaluate_technology_for_profiles` call site --
`pipeline.availability` itself never reads this config or imports this module, keeping the
config-parsing/matching concern out of the shared evaluator (mirrors how `weight_gate_expressible_
mask` is computed once in `dataset_emit` and merely consulted as booleans elsewhere).

A suppressed leaf resolves to a FIXED boolean constant, not the EXCLUDED/"vacuously satisfied"
identity element `pipeline.availability.EXCLUDED_KEYS` leaves use -- see the config file's own
docstring for why that distinction matters (a real corpus shape, `is_nomadic = yes AND NOT {
has_country_flag = X_found }`, would silently promote to a false LOCKED verdict under identity-
element treatment; resolving to a real constant instead composes correctly through the same
Kleene AND/OR/NOT/NOR propagation `pipeline.availability` already implements, regardless of
nesting depth or sibling structure).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .clausewitz.nodes import Assignment, Block, Comment, ConditionalBlock, Identifier, NumberLiteral, StringLiteral

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "config" / "weight_gate_suppressions.txt"

# Mirrors pipeline.availability.BOOLEAN_WRAPPERS exactly -- duplicated rather than imported so this
# module has no dependency on pipeline.availability at all (see module docstring: the two modules
# are deliberately decoupled, dataset_emit is the only caller of both).
BOOLEAN_WRAPPERS = {"AND", "OR", "NOT", "NOR"}


@dataclass(frozen=True)
class WeightGateSuppression:
    leaf_key: str
    shape: str  # "any" | "numeric_at_most" | "suffix"
    resolves_to: bool
    justification: str
    line: int
    operator: str | None = None  # numeric_at_most only: "<" or "<="
    threshold: float | None = None  # numeric_at_most only
    suffix: str | None = None  # suffix only

    def matches(self, assignment: Assignment) -> bool:
        if assignment.key_name != self.leaf_key:
            return False
        if self.shape == "any":
            return True
        if self.shape == "numeric_at_most":
            if assignment.operator != self.operator:
                return False
            value = assignment.value
            if not isinstance(value, NumberLiteral):
                return False
            return value.value <= self.threshold
        if self.shape == "suffix":
            value = assignment.value
            name = None
            if isinstance(value, Identifier):
                name = value.name
            elif isinstance(value, StringLiteral):
                name = value.value
            if name is None:
                return False
            return name.endswith(self.suffix)
        return False


class WeightGateSuppressionConfigError(Exception):
    pass


def _parse_shape(shape_text: str, path: Path, lineno: int) -> tuple[str, dict]:
    shape_text = shape_text.strip()
    if shape_text == "":
        return "any", {}
    if shape_text.startswith("~"):
        suffix = shape_text[1:].strip()
        if not suffix:
            raise WeightGateSuppressionConfigError(f"{path}:{lineno}: empty suffix after '~'")
        return "suffix", {"suffix": suffix}
    for op in ("<=", "<"):
        if shape_text.startswith(op):
            rest = shape_text[len(op):].strip()
            try:
                threshold = float(rest)
            except ValueError:
                raise WeightGateSuppressionConfigError(
                    f"{path}:{lineno}: expected a number after {op!r}, found {rest!r}"
                ) from None
            return "numeric_at_most", {"operator": op, "threshold": threshold}
    raise WeightGateSuppressionConfigError(
        f"{path}:{lineno}: unrecognised comparison shape {shape_text!r} -- expected empty, "
        f"'< N'/'<= N', or '~ SUFFIX'"
    )


def load_suppressions(path: Path = DEFAULT_PATH) -> list[WeightGateSuppression]:
    if not path.is_file():
        return []
    suppressions: list[WeightGateSuppression] = []
    seen_keys: dict[str, int] = {}
    for lineno, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if line == "" or line.startswith("#"):
            continue
        if "->" not in line:
            raise WeightGateSuppressionConfigError(
                f"{path}:{lineno}: expected '<leaf key>[ <shape>] -> <true|false>  # <justification>', "
                f"found {raw_line!r}"
            )
        head, rest = line.split("->", 1)
        if "#" not in rest:
            raise WeightGateSuppressionConfigError(
                f"{path}:{lineno}: missing required '#' justification"
            )
        bool_part, justification_part = rest.split("#", 1)
        bool_text = bool_part.strip()
        justification = justification_part.strip()
        head = head.strip()
        if not head:
            raise WeightGateSuppressionConfigError(f"{path}:{lineno}: missing leaf key")
        if not justification:
            raise WeightGateSuppressionConfigError(f"{path}:{lineno}: empty '#' justification")
        if bool_text not in ("true", "false"):
            raise WeightGateSuppressionConfigError(
                f"{path}:{lineno}: expected 'true' or 'false' after '->', found {bool_text!r}"
            )
        resolves_to = bool_text == "true"
        head_parts = head.split(None, 1)
        leaf_key = head_parts[0]
        shape_text = head_parts[1] if len(head_parts) > 1 else ""
        shape, shape_kwargs = _parse_shape(shape_text, path, lineno)
        if leaf_key in seen_keys:
            raise WeightGateSuppressionConfigError(
                f"{path}:{lineno}: duplicate suppression entry for leaf key {leaf_key!r} "
                f"(first seen at line {seen_keys[leaf_key]}) -- this file keys suppression at the "
                f"mechanism level, one entry per leaf key"
            )
        seen_keys[leaf_key] = lineno
        suppressions.append(
            WeightGateSuppression(
                leaf_key=leaf_key, shape=shape, resolves_to=resolves_to,
                justification=justification, line=lineno, **shape_kwargs,
            )
        )
    return suppressions


def find_suppressed_leaves(
    block: Block, suppressions: list[WeightGateSuppression],
) -> list[tuple[WeightGateSuppression, Assignment]]:
    """Walks `block`'s AND/OR/NOT/NOR boolean structure (the same descent `pipeline.availability.
    _evaluate_node` performs) collecting every leaf `Assignment` that matches a registered
    suppression rule, at any nesting depth. A `Comment`/`ConditionalBlock` item is skipped (neither
    can ever be a leaf a suppression rule names)."""
    hits: list[tuple[WeightGateSuppression, Assignment]] = []

    def walk(node: Block) -> None:
        for item in node.items:
            if isinstance(item, (Comment, ConditionalBlock)):
                continue
            assert isinstance(item, Assignment)
            key_upper = item.key_name.upper()
            if key_upper in BOOLEAN_WRAPPERS and isinstance(item.value, Block):
                walk(item.value)
                continue
            for rule in suppressions:
                if rule.matches(item):
                    hits.append((rule, item))
                    break
    walk(block)
    return hits


def apply_suppressions(
    blocks: list[Block], suppressions: list[WeightGateSuppression],
) -> tuple[dict[int, bool], list[tuple[WeightGateSuppression, Assignment]]]:
    """Convenience over `find_suppressed_leaves` for a technology's full list of zero-factor
    condition blocks (`pipeline.dataset_emit._weight_gate_condition_blocks`'s output): returns
    `(id(assignment) -> resolved bool, all hits)`. The id-map is what `pipeline.availability.
    _apply_weight_gate` actually consults during evaluation -- `id()` is stable for the lifetime of
    one build, since every block is constructed once in `build_context` and reused unchanged
    across all 12 profile evaluations."""
    targets: dict[int, bool] = {}
    all_hits: list[tuple[WeightGateSuppression, Assignment]] = []
    for block in blocks:
        for rule, leaf in find_suppressed_leaves(block, suppressions):
            targets[id(leaf)] = rule.resolves_to
            all_hits.append((rule, leaf))
    return targets, all_hits
