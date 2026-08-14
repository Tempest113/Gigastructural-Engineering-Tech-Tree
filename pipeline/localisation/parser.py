"""Line-oriented parser for Paradox's localisation YAML-like format.

Not YAML. `§` colour codes, `£icon£` tokens, embedded colons, doubled/escaped quotes, and
version-suffixed keys all fall outside the YAML spec — see CLAUDE.md's "Do not use a YAML
library" rule and the Step 1 survey this parser was built from. Hand-written, line-oriented:
survey evidence (see below) confirms a value never spans more than one physical line, so unlike
`pipeline/clausewitz/tokenizer.py` this parser never needs to track "are we still inside a
string" across a newline.

**Value scanning is first-quote-to-last-quote-on-the-line — the deliberate inverse of the
Clausewitz string scanner, and the single most load-bearing decision in this module.** Anyone
who has just worked on pipeline/clausewitz/tokenizer.py will reach for its rule by reflex — scan
to the next unescaped `"`, since newlines never terminate a string — and that rule is *wrong
here*, silently, not loudly. Real, shipped localisation text routinely uses raw unescaped `"` as
literal English quotation marks:

    akx.9021.desc:0 ""This will be the end of me," [horizonsignal_thirdleader.GetName] says
    ... "Impossible," one says. "I hope so," says another.\n\n...the "Foundling"...ever again."

"Scan to the next unescaped quote" would terminate this value after two characters, producing a
plausible-looking but wrong short string — no exception, no error, just silently corrupted data.
970 lines in the survey corpus carry more than two literal `"` characters; this is common, not a
one-off. The correct rule, confirmed against ~194,000 value lines with a single (real, upstream)
counter-example — a genuinely missing closing quote, reported as `MalformedEntry`, not silently
mis-scanned — is: the value's raw text is everything between the *first* `"` and the *last* `"*
on the physical line. Backslash-escaped quotes (`\\"`) do occur (576 sites) but are not the
primary mechanism this format relies on for embedded quotes, unlike Clausewitz script.

Malformed entries are reported (`nodes.MalformedEntry`), never raised — a single upstream typo in
one shipped mod file (three confirmed real instances, all in ACOT) must not block the ~194,000
well-formed entries around it. See nodes.py's docstring for the confirmed malformed shapes.
"""

from __future__ import annotations

import re

from .errors import LocalisationError
from .markup import parse_markup
from .nodes import Comment, LocEntry, LocFile, LocValue, MalformedEntry

_HEADER_RE = re.compile(r"^l_([a-z_]+):\s*$")
_KEY_CHARS_RE = re.compile(r"^[A-Za-z0-9_.\-']+$")

# Confirmed real key-body characters (see the Step 1 survey): letters, digits, underscore, dot
# (event-id namespacing, e.g. `crisis.2502.name`), hyphen (`NAME_VX-455`, `opinion-3`), and
# apostrophe. ':' is never part of a key — it's the key/value separator, so splitting on the
# first ':' is always safe.


def _normalise_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def parse_text(text: str, path: str = "<string>") -> LocFile:
    text = _normalise_newlines(text)
    lines = text.split("\n")

    items: list = []
    language: str | None = None
    header_seen = False

    for lineno, raw_line in enumerate(lines, start=1):
        stripped = raw_line.strip()

        if not header_seen:
            if stripped == "":
                continue
            m = _HEADER_RE.match(stripped)
            if not m:
                raise LocalisationError(
                    f"expected a language header 'l_<language>:' as the first content line, "
                    f"found {stripped[:60]!r}",
                    path,
                    lineno,
                )
            language = m.group(1)
            header_seen = True
            continue

        if stripped == "":
            continue
        if stripped.startswith("#"):
            idx = raw_line.find("#")
            items.append(Comment(text=raw_line[idx + 1 :], line=lineno, column=idx + 1))
            continue

        items.append(_parse_entry_line(raw_line, lineno, path))

    if not header_seen:
        raise LocalisationError("file is empty or contains no language header", path, 1)

    return LocFile(path=path, language=language, items=items)


def _parse_entry_line(line: str, lineno: int, path: str):
    key_start = len(line) - len(line.lstrip(" \t"))
    column = key_start + 1

    colon_idx = line.find(":")
    if colon_idx == -1:
        return MalformedEntry(
            reason="no ':' key/value separator found", raw_line=line, line=lineno, column=column, file=path
        )

    key = line[key_start:colon_idx].rstrip(" \t")
    if not _KEY_CHARS_RE.match(key):
        return MalformedEntry(reason=f"invalid key {key!r}", raw_line=line, line=lineno, column=column, file=path)

    rest = line[colon_idx + 1 :]
    version_match = re.match(r"\d*", rest)
    version = version_match.group() or None
    after_version = rest[version_match.end() :]
    content = after_version.lstrip(" \t")

    if content == "":
        return MalformedEntry(reason="missing value", raw_line=line, line=lineno, column=column, file=path)

    if content[0] == '"':
        value_open = len(line) - len(content)
        value_close = line.rfind('"')
        if value_close == value_open:
            return MalformedEntry(
                reason="missing closing quote", raw_line=line, line=lineno, column=column, file=path
            )
        raw_value = line[value_open + 1 : value_close]
        trailing = line[value_close + 1 :].strip()
        if trailing and not trailing.startswith("#"):
            return MalformedEntry(
                reason=f"unexpected content after closing quote: {trailing!r}",
                raw_line=line,
                line=lineno,
                column=column,
                file=path,
            )
        value = LocValue(raw=raw_value, quoted=True, spans=parse_markup(raw_value))
        return LocEntry(key=key, version=version, value=value, line=lineno, column=column, file=path)

    if '"' in content:
        # Unquoted-looking value that contains a quote later on the line is not a genuine
        # unquoted value (see ACOT_SC_GUNSHIP_4_DESC: Gunship" — the real corpus instance this
        # rule is drawn from): the opening quote was almost certainly omitted by mistake.
        return MalformedEntry(reason="missing opening quote", raw_line=line, line=lineno, column=column, file=path)

    value = LocValue(raw=content, quoted=False, spans=parse_markup(content))
    return LocEntry(key=key, version=version, value=value, line=lineno, column=column, file=path)
