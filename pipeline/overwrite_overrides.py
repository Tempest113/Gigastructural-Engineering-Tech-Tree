"""Loader for `config/overwrite_overrides.txt` — read that file first for what an entry means,
why it exists, and the review bar for adding one.

Format: one entry per line, `<technology key> = <winning source>  # <justification>`. Blank
lines and lines starting with `#` (after stripping leading whitespace) are comments/header and
are skipped; every other non-blank line MUST carry a trailing `#` justification — a line without
one is a config error (fails loudly), not a silently-accepted entry with no accountable reason
attached. Mirrors pipeline/icons/overrides.py's format and review bar exactly.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "config" / "overwrite_overrides.txt"

VALID_SOURCES = ("Vanilla", "Gigastructural Engineering", "ACOT", "AoT")


@dataclass(frozen=True)
class OverwriteOverride:
    key: str
    winning_source: str
    justification: str
    line: int


class OverwriteOverrideConfigError(Exception):
    pass


def load_overrides(path: Path = DEFAULT_PATH) -> dict[str, OverwriteOverride]:
    if not path.is_file():
        return {}
    overrides: dict[str, OverwriteOverride] = {}
    for lineno, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if line == "" or line.startswith("#"):
            continue
        if "=" not in line:
            raise OverwriteOverrideConfigError(
                f"{path}:{lineno}: expected '<key> = <source> # <justification>', found {raw_line!r}"
            )
        key_part, rest = line.split("=", 1)
        key = key_part.strip()
        if "#" not in rest:
            raise OverwriteOverrideConfigError(
                f"{path}:{lineno}: missing required '#' justification for key {key!r}"
            )
        source_part, justification_part = rest.split("#", 1)
        winning_source = source_part.strip()
        justification = justification_part.strip()
        if not key or not winning_source or not justification:
            raise OverwriteOverrideConfigError(
                f"{path}:{lineno}: key, winning source and justification must all be non-empty, "
                f"got key={key!r} source={winning_source!r} justification={justification!r}"
            )
        if winning_source not in VALID_SOURCES:
            raise OverwriteOverrideConfigError(
                f"{path}:{lineno}: winning source {winning_source!r} is not one of {VALID_SOURCES}"
            )
        if key in overrides:
            raise OverwriteOverrideConfigError(f"{path}:{lineno}: duplicate override entry for key {key!r}")
        overrides[key] = OverwriteOverride(key=key, winning_source=winning_source, justification=justification, line=lineno)
    return overrides
