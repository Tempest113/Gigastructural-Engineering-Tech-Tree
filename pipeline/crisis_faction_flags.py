"""Loader for `config/crisis_faction_flag_overrides.txt` -- D-7/P-5's flag-to-faction map.

See that file's header for what an entry means and the review bar for adding one. Mirrors
`pipeline/crisis_faction_overrides.py`'s format exactly, except keyed by `has_country_flag` name
rather than technology key, and with no `None` token -- a flag either maps to a faction or has no
entry at all; there is nothing to "correct" for a flag the way a technology-key override can
correct a step 1/2 misclassification.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .crisis_faction import CRISIS_FACTIONS

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "config" / "crisis_faction_flag_overrides.txt"


@dataclass(frozen=True)
class CrisisFactionFlagOverride:
    flag_name: str
    faction: str
    justification: str
    line: int


class CrisisFactionFlagOverrideConfigError(Exception):
    pass


def load_flag_overrides(path: Path = DEFAULT_PATH) -> dict[str, CrisisFactionFlagOverride]:
    if not path.is_file():
        return {}
    overrides: dict[str, CrisisFactionFlagOverride] = {}
    for lineno, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if line == "" or line.startswith("#"):
            continue
        if "=" not in line:
            raise CrisisFactionFlagOverrideConfigError(
                f"{path}:{lineno}: expected '<flag name> = <faction> # <justification>', "
                f"found {raw_line!r}"
            )
        key_part, rest = line.split("=", 1)
        flag_name = key_part.strip()
        if "#" not in rest:
            raise CrisisFactionFlagOverrideConfigError(
                f"{path}:{lineno}: missing required '#' justification for flag {flag_name!r}"
            )
        faction_part, justification_part = rest.split("#", 1)
        faction = faction_part.strip()
        justification = justification_part.strip()
        if not flag_name or not faction or not justification:
            raise CrisisFactionFlagOverrideConfigError(
                f"{path}:{lineno}: flag name, faction and justification must all be non-empty, "
                f"got flag={flag_name!r} faction={faction!r} justification={justification!r}"
            )
        if faction not in CRISIS_FACTIONS:
            raise CrisisFactionFlagOverrideConfigError(
                f"{path}:{lineno}: faction {faction!r} is not one of {CRISIS_FACTIONS}"
            )
        if flag_name in overrides:
            raise CrisisFactionFlagOverrideConfigError(
                f"{path}:{lineno}: duplicate flag override entry for flag {flag_name!r}"
            )
        overrides[flag_name] = CrisisFactionFlagOverride(
            flag_name=flag_name, faction=faction, justification=justification, line=lineno
        )
    return overrides
