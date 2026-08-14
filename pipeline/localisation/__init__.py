"""Localisation YAML-like parser (Stage 1 of the pipeline, spec/00-overview.md).

Not YAML — see parser.py's module docstring. Produces a lossless-of-content parse: every value's
raw text (including `§`/`£`/`$`/`[...]` markup) is preserved verbatim; nothing is resolved. See
nodes.py and markup.py.

Public API: `parse_file(path)`, `parse_text(text, path=...)`, `LocalisationError`,
`LocalisationEncodingError`, `MissingLocalisationKeyError`.
"""

from __future__ import annotations

from pathlib import Path

from .errors import LocalisationEncodingError, LocalisationError, MissingLocalisationKeyError
from .nodes import (
    BracketCommand,
    ColorMarker,
    Comment,
    IconToken,
    LocEntry,
    LocFile,
    LocValue,
    MalformedEntry,
    VariableToken,
)
from .parser import parse_text

__all__ = [
    "LocalisationError",
    "LocalisationEncodingError",
    "MissingLocalisationKeyError",
    "parse_file",
    "parse_text",
    "LocFile",
    "LocEntry",
    "LocValue",
    "Comment",
    "MalformedEntry",
    "ColorMarker",
    "IconToken",
    "VariableToken",
    "BracketCommand",
]


def parse_file(path) -> LocFile:
    """Parse a localisation file from disk.

    Strips a UTF-8 BOM if present (100% of the real corpus carries one — see the Step 1 survey —
    but this doesn't assume that), normalises CRLF/CR to LF, and decodes strictly as UTF-8 — any
    other encoding raises `LocalisationEncodingError` naming the file and an approximate line,
    same posture as pipeline/clausewitz/__init__.py's `parse_file` (no real non-UTF-8 file was
    found in the corpus, but CLAUDE.md requires failing loudly rather than silently mangling one
    if it ever shows up)."""
    path_str = str(path)
    raw = Path(path).read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        line = raw[: exc.start].decode("utf-8", errors="replace").count("\n") + 1
        bad_byte = raw[exc.start] if exc.start < len(raw) else None
        byte_desc = f"0x{bad_byte:02X}" if bad_byte is not None else "?"
        raise LocalisationEncodingError(
            f"file is not valid UTF-8 ({exc.reason}); byte {byte_desc} at file offset "
            f"{exc.start} is not valid there — the file may be Windows-1252 or another "
            f"non-UTF-8 encoding",
            path_str,
            line,
        ) from exc

    return parse_text(text, path_str)
