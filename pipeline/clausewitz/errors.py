"""Errors raised by the Clausewitz tokeniser and parser.

Per P-10 (spec/P-10-performance-automation.md), the build fails loudly rather than emitting a
partial dataset. Every error here names the source file and the line the problem starts at, so
a failure is traceable without re-reading the whole file.
"""

from __future__ import annotations


class ClausewitzError(Exception):
    """Raised on any tokenising or parsing failure.

    Attributes:
        path: the source file (or "<memory>"/similar for in-memory parses).
        line: 1-indexed line the problem starts at.
        column: 1-indexed column, when known.
    """

    def __init__(self, message: str, path: str, line: int, column: int | None = None):
        self.path = path
        self.line = line
        self.column = column
        location = f"{path}:{line}" + (f":{column}" if column is not None else "")
        super().__init__(f"{location}: {message}")


class ClausewitzEncodingError(ClausewitzError):
    """Raised when a source file is not valid UTF-8 (with or without a BOM).

    Kept as a distinct subclass (rather than folded into ClausewitzError generically) because
    tests/fixtures/encoding/windows-1252.txt exists specifically to assert this fails loudly
    rather than silently decoding as mojibake — callers that want to tell "the bytes are wrong"
    apart from "the syntax is wrong" can catch this subclass specifically.
    """
