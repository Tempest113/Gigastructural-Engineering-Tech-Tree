"""`technology_swap` parsing and axis-expressibility classification (spec/decisions.md's D-14).

A `technology_swap` sub-block gives a technology a different name/icon/area/category for certain
empire types, but it NEVER becomes its own rendered node -- D-1 (spec/decisions.md) keeps the
rendered node set at exactly 980 regardless of how many swaps exist. This module is entirely
about how ONE node presents differently; it has no opinion on graph/layout structure.

Classification reuses `pipeline.availability.AXIS_FACTS` as the single source of truth for "which
leaf names are axis facts" -- the same dict the trigger evaluator itself uses for `potential`
blocks, so a swap's classification here can never silently disagree with what the evaluator would
say about the same leaf name if it appeared in a `potential` block instead of a `trigger` block.
A swap is axis-expressible only when EVERY leaf anywhere in its trigger (including inside nested
AND/OR/NOT/NOR wrappers) is an axis fact -- a compound trigger is only as expressible as its
least-expressible leaf (D-14's tech_ring_world case: `country_uses_bio_ships AND
giga_can_use_habitables` is wholly non-axis because one leg is, matching the evaluator's own
Kleene short-circuit discipline of never granting partial credit on a compound condition)."""

from __future__ import annotations

from dataclasses import dataclass

from .availability import AXIS_FACTS
from .clausewitz.nodes import Assignment, Block, Identifier, StringLiteral


def _scalar_text(node) -> str | None:
    if isinstance(node, Identifier):
        return node.name
    if isinstance(node, StringLiteral):
        return node.value
    return None


def _collect_leaf_names(block: Block, out: list[str]) -> None:
    for item in block.items:
        if isinstance(item, Assignment):
            if isinstance(item.value, Block):
                _collect_leaf_names(item.value, out)
            else:
                out.append(item.key_name)


@dataclass(frozen=True)
class TechnologySwap:
    owner_key: str
    swap_key: str
    swap_block: Block
    trigger_block: Block | None
    trigger_leaf_names: tuple[str, ...]
    axis_expressible: bool


def collect_swaps(owner_key: str, block: Block) -> list[TechnologySwap]:
    """Every `technology_swap` sub-block directly on `block`, in declaration order.

    Declaration order matters: `pipeline.dataset_emit`'s empire-overlay substitution picks the
    FIRST axis-expressible swap whose trigger matches a given profile. This is a real, not
    hypothetical, tie-break -- 2 real technologies (`tech_juggernaut`, `tech_titans`) each carry
    both a nomadic swap and a bio-shipset swap, and a nomadic+bio-shipset profile matches both
    simultaneously. Stellaris's own engine precedence for this case is not documented anywhere
    this pipeline can verify offline, so "first declared wins" is a deliberate, DOCUMENTED
    modelling choice (spec/decisions.md's D-14), not a confirmed match to in-game behaviour --
    flagged honestly rather than guessed at, so a future session with access to verify real game
    behaviour can revisit it specifically for these two technologies."""
    swaps: list[TechnologySwap] = []
    for item in block.items:
        if not (isinstance(item, Assignment) and item.key_name == "technology_swap"):
            continue
        swap_block = item.value
        if not isinstance(swap_block, Block):
            continue
        name_assignment = next(
            (i for i in swap_block.items if isinstance(i, Assignment) and i.key_name == "name"), None
        )
        if name_assignment is None:
            continue
        swap_key = _scalar_text(name_assignment.value)
        if swap_key is None:
            continue
        trigger_assignment = next(
            (i for i in swap_block.items if isinstance(i, Assignment) and i.key_name == "trigger"), None
        )
        trigger_block = (
            trigger_assignment.value
            if trigger_assignment is not None and isinstance(trigger_assignment.value, Block)
            else None
        )
        leaf_names: list[str] = []
        if trigger_block is not None:
            _collect_leaf_names(trigger_block, leaf_names)
        axis_expressible = bool(leaf_names) and all(name in AXIS_FACTS for name in leaf_names)
        swaps.append(
            TechnologySwap(
                owner_key=owner_key,
                swap_key=swap_key,
                swap_block=swap_block,
                trigger_block=trigger_block,
                trigger_leaf_names=tuple(leaf_names),
                axis_expressible=axis_expressible,
            )
        )
    return swaps
