"""Loader for `config/icon_overrides.txt` — read that file first for what an entry means, why it
exists, and the review bar for adding one.

Format: one entry per line, `<candidate key> = <icon filename, without .dds>  # <justification>`.
Blank lines and lines starting with `#` (after stripping leading whitespace) are comments/header
and are skipped; every other non-blank line MUST carry a trailing `#` justification — a line
without one is a config error (fails loudly), not a silently-accepted entry with no accountable
reason attached.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "icon_overrides.txt"


@dataclass(frozen=True)
class IconOverride:
    key: str
    icon_name: str
    justification: str
    line: int


class IconOverrideConfigError(Exception):
    pass


def load_overrides(path: Path = DEFAULT_PATH) -> dict[str, IconOverride]:
    if not path.is_file():
        return {}
    overrides: dict[str, IconOverride] = {}
    for lineno, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if line == "" or line.startswith("#"):
            continue
        if "=" not in line:
            raise IconOverrideConfigError(f"{path}:{lineno}: expected '<key> = <icon> # <justification>', found {raw_line!r}")
        key_part, rest = line.split("=", 1)
        key = key_part.strip()
        if "#" not in rest:
            raise IconOverrideConfigError(
                f"{path}:{lineno}: missing required '#' justification for key {key!r}"
            )
        icon_part, justification_part = rest.split("#", 1)
        icon_name = icon_part.strip()
        justification = justification_part.strip()
        if not key or not icon_name or not justification:
            raise IconOverrideConfigError(
                f"{path}:{lineno}: key, icon name and justification must all be non-empty, got "
                f"key={key!r} icon={icon_name!r} justification={justification!r}"
            )
        if key in overrides:
            raise IconOverrideConfigError(f"{path}:{lineno}: duplicate override entry for key {key!r}")
        overrides[key] = IconOverride(key=key, icon_name=icon_name, justification=justification, line=lineno)
    return overrides
