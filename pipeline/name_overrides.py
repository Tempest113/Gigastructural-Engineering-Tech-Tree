"""Loader for `config/name_overrides.txt` — read that file first for what an entry means, why it
exists, and the review bar for adding one.

Found this session, by reviewing a real rendered screenshot (the same "user's screenshots catch
bugs no test could" pattern this project's history is full of -- here it was this session's own
screenshot review, not the user's, but the mechanism is identical): `giga_tech_aeternite_weaponry`
has a real localisation entry (`vendor/mods/gigastructures/localisation/english/
giga_ehof_functions_l_english.yml:93`), but its VALUE is verbatim the same string as its own KEY --
the mod author never actually wrote a display name for this technology. `pipeline/dataset_emit.py`
was previously happy to treat that as "resolved" (it contains no unresolved `$...$` token, the
only thing `_require_resolved` checked), and rendered the raw internal key as if it were the
technology's name -- CLAUDE.md's "the build fails rather than emitting a partial dataset...missing
localisation for displayed strings" rule existed for exactly this shape of gap and didn't cover it.

`pipeline/dataset_emit.py` now treats "resolved name equals the technology's own raw key" as
unresolved localisation and hard-fails (`UnresolvedLocalisationTokenError`) unless this file names
a reviewed, human-decided display name for that key -- same review bar and format as
`config/overwrite_overrides.txt`/`config/icon_overrides.txt`: `<technology key> = <display name>  #
<justification>`. Blank lines and lines starting with `#` (after stripping leading whitespace) are
comments/header and are skipped; every other non-blank line MUST carry a trailing `#`
justification -- a line without one is a config error (fails loudly), not a silently-accepted entry
with no accountable reason attached.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "config" / "name_overrides.txt"


@dataclass(frozen=True)
class NameOverride:
    key: str
    name: str
    justification: str
    line: int


class NameOverrideConfigError(Exception):
    pass


def load_name_overrides(path: Path = DEFAULT_PATH) -> dict[str, NameOverride]:
    if not path.is_file():
        return {}
    overrides: dict[str, NameOverride] = {}
    for lineno, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if line == "" or line.startswith("#"):
            continue
        if "=" not in line:
            raise NameOverrideConfigError(
                f"{path}:{lineno}: expected '<key> = <display name> # <justification>', found {raw_line!r}"
            )
        key_part, rest = line.split("=", 1)
        key = key_part.strip()
        if "#" not in rest:
            raise NameOverrideConfigError(f"{path}:{lineno}: missing required '#' justification for key {key!r}")
        name_part, justification_part = rest.split("#", 1)
        name = name_part.strip()
        justification = justification_part.strip()
        if not key or not name or not justification:
            raise NameOverrideConfigError(
                f"{path}:{lineno}: key, display name and justification must all be non-empty, "
                f"got key={key!r} name={name!r} justification={justification!r}"
            )
        if key in overrides:
            raise NameOverrideConfigError(f"{path}:{lineno}: duplicate override entry for key {key!r}")
        overrides[key] = NameOverride(key=key, name=name, justification=justification, line=lineno)
    return overrides
