"""Loader for `config/crisis_faction_overrides.txt` — D-7's checked-in crisis-faction override
table, step 3 of P-5's derivation. Read that file first for what an entry means, why it exists,
and the review bar for adding one.

Mirrors `pipeline/overwrite_overrides.py`/`pipeline/lock_reason_overrides.py`'s format and review
bar exactly. `faction` MUST be one of D-7's five factions, or the literal `None` to force a
technology into the standard-progression lane (overriding a step 1/2 match that turns out wrong).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .crisis_faction import CRISIS_FACTIONS

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "config" / "crisis_faction_overrides.txt"

VALID_FACTION_TOKENS = CRISIS_FACTIONS + ("None",)


@dataclass(frozen=True)
class CrisisFactionOverride:
    technology_key: str
    faction: str | None
    justification: str
    line: int


class CrisisFactionOverrideConfigError(Exception):
    pass


def load_overrides(path: Path = DEFAULT_PATH) -> dict[str, CrisisFactionOverride]:
    if not path.is_file():
        return {}
    overrides: dict[str, CrisisFactionOverride] = {}
    for lineno, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if line == "" or line.startswith("#"):
            continue
        if "=" not in line:
            raise CrisisFactionOverrideConfigError(
                f"{path}:{lineno}: expected '<technology key> = <faction> # <justification>', "
                f"found {raw_line!r}"
            )
        key_part, rest = line.split("=", 1)
        key = key_part.strip()
        if "#" not in rest:
            raise CrisisFactionOverrideConfigError(
                f"{path}:{lineno}: missing required '#' justification for key {key!r}"
            )
        faction_part, justification_part = rest.split("#", 1)
        faction_token = faction_part.strip()
        justification = justification_part.strip()
        if not key or not faction_token or not justification:
            raise CrisisFactionOverrideConfigError(
                f"{path}:{lineno}: technology key, faction and justification must all be "
                f"non-empty, got key={key!r} faction={faction_token!r} justification={justification!r}"
            )
        if faction_token not in VALID_FACTION_TOKENS:
            raise CrisisFactionOverrideConfigError(
                f"{path}:{lineno}: faction {faction_token!r} is not one of {VALID_FACTION_TOKENS}"
            )
        if key in overrides:
            raise CrisisFactionOverrideConfigError(f"{path}:{lineno}: duplicate override entry for key {key!r}")
        faction = None if faction_token == "None" else faction_token
        overrides[key] = CrisisFactionOverride(technology_key=key, faction=faction, justification=justification, line=lineno)
    return overrides
