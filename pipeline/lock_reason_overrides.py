"""Loader for `config/lock_reason_overrides.txt` — P-13's checked-in lock-reason override table.
Read that file first for what an entry means, why it exists, and the review bar for adding one.

Mirrors `pipeline/overwrite_overrides.py`'s format and review bar exactly (P-15's precedent for
"hand-maintained config the resolver falls back to when it refuses to guess"), applied to a
different case: P-13 requires that when a LOCKED technology's reason can't be derived
automatically, the build fall back to this table and warn when an entry is missing (never a hard
failure — P-13 doesn't require blocking the build, only surfacing the gap via S-2).

Format: one entry per line, `<technology key> = <reason text> # <justification>`. Blank lines
and lines starting with `#` (after stripping leading whitespace) are comments/header and are
skipped; every other non-blank line MUST carry a trailing `#` justification — a line without one
is a config error (fails loudly), not a silently-accepted entry with no accountable reason
attached.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "config" / "lock_reason_overrides.txt"


@dataclass(frozen=True)
class LockReasonOverride:
    technology_key: str
    reason_text: str
    justification: str
    line: int


class LockReasonOverrideConfigError(Exception):
    pass


def load_overrides(path: Path = DEFAULT_PATH) -> dict[str, LockReasonOverride]:
    if not path.is_file():
        return {}
    overrides: dict[str, LockReasonOverride] = {}
    for lineno, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if line == "" or line.startswith("#"):
            continue
        if "=" not in line:
            raise LockReasonOverrideConfigError(
                f"{path}:{lineno}: expected '<technology key> = <reason text> # <justification>', "
                f"found {raw_line!r}"
            )
        key_part, rest = line.split("=", 1)
        key = key_part.strip()
        if "#" not in rest:
            raise LockReasonOverrideConfigError(
                f"{path}:{lineno}: missing required '#' justification for key {key!r}"
            )
        reason_part, justification_part = rest.split("#", 1)
        reason_text = reason_part.strip()
        justification = justification_part.strip()
        if not key or not reason_text or not justification:
            raise LockReasonOverrideConfigError(
                f"{path}:{lineno}: technology key, reason text and justification must all be "
                f"non-empty, got key={key!r} reason={reason_text!r} justification={justification!r}"
            )
        if key in overrides:
            raise LockReasonOverrideConfigError(f"{path}:{lineno}: duplicate override entry for key {key!r}")
        overrides[key] = LockReasonOverride(technology_key=key, reason_text=reason_text, justification=justification, line=lineno)
    return overrides
