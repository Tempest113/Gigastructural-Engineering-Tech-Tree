"""Token types for the Clausewitz tokeniser."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class TokenType(Enum):
    IDENTIFIER = auto()  # bare word, e.g. `tech_ring_world`, `technology/tech_weight_boni/x`
    STRING = auto()  # "quoted text"
    NUMBER = auto()  # 123, -1, 0.5
    VARIABLE = auto()  # @tier1cost1 (the '@' is not part of Token.text)
    PARAMETER = auto()  # $TECHNOLOGY$ (inline_script parameter; '$'s not part of Token.text)
    OPERATOR = auto()  # one of = < > <= >= !=
    LBRACE = auto()  # {
    RBRACE = auto()  # }
    COMMENT = auto()  # # ... to end of line (text excludes the '#')
    EOF = auto()


@dataclass(frozen=True)
class Token:
    type: TokenType
    text: str
    line: int
    column: int
