"""Errors raised by the localisation parser.

File-level structural problems (no `l_<language>:` header, invalid encoding) fail loudly, same
posture as pipeline/clausewitz/errors.py — see that module's docstring. Per-entry problems
(a malformed value line) do NOT raise; they become `nodes.MalformedEntry` diagnostics instead, so
one upstream typo in one shipped mod file never blocks the rest of the corpus. See parser.py and
nodes.py for why.
"""

from __future__ import annotations


class LocalisationError(Exception):
    """Raised on a file-level localisation parse failure (missing/malformed header, bad
    encoding). Never raised for a single malformed entry — see this module's docstring."""

    def __init__(self, message: str, path: str, line: int, column: int | None = None):
        self.path = path
        self.line = line
        self.column = column
        location = f"{path}:{line}" + (f":{column}" if column is not None else "")
        super().__init__(f"{location}: {message}")


class LocalisationEncodingError(LocalisationError):
    """Raised when a source file is not valid UTF-8 — same rationale as
    pipeline/clausewitz/errors.py's `ClausewitzEncodingError`."""


class MissingLocalisationKeyError(KeyError):
    """Raised by `table.LocalisationTable.require()` when a key that must be present (because it
    is about to be displayed) is absent from the resolved table — the real "fail the build"
    signal CLAUDE.md's "missing localisation for displayed strings" rule needs.
    `LocalisationTable.get()` returns `None` instead, for callers that want to check without
    raising."""

    def __init__(self, key: str):
        self.key = key
        super().__init__(f"no localisation entry for key {key!r}")
