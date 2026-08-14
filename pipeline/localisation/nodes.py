"""AST node types for the lossless localisation YAML-like parser (spec/00-overview.md, Stage 1).

Mirrors pipeline/clausewitz/nodes.py's design principles, applied to a different, much simpler
grammar:

- `LocValue.raw` is the exact source text between the value's delimiters (the opening and closing
  quote, for a quoted value; the whole remaining line, for the rare unquoted form) — never
  stripped, never markup-resolved. `LocValue.spans` is a *derived* view over that same text (see
  markup.py) for callers that want to find `§`/`£`/`$`/`[...]` markup without re-scanning; `raw`
  remains the source of truth, same "derived convenience, never the source of truth" precedent as
  `Block.assignments_by_key()` in the Clausewitz AST.
- Nothing here resolves anything: `§` spans are not balance-checked, `£icon£` names are not looked
  up, `$VARIABLE$` references are not substituted, `[...]` commands are not evaluated. See
  markup.py's module docstring for why, and spec/P-12-detail-popup.md P-12.1 for why that's a
  later stage's job.
- A malformed entry (missing quote, unexpected trailing content) is reported as a `MalformedEntry`
  diagnostic, not raised as an exception — a single upstream typo in one shipped mod file must not
  block parsing the other ~194,000 well-formed value lines in the corpus. See parser.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Union


@dataclass
class Comment:
    """A `#`-to-end-of-line comment. `text` is everything after the `#`, verbatim."""

    text: str
    line: int
    column: int


@dataclass
class ColorMarker:
    """A `§`-code span marker: either an opener (`§Y`, `§H`, ...; `code` is the letter/digit) or a
    closer (`§!`; `code` is `None`). Stored as two independent markers rather than a matched pair
    — the real corpus has both unclosed openers and closers with no opener on the same string
    (48,052 opens vs 47,808 `§!` closes across the survey corpus; a leaf string's `§!` plausibly
    closes formatting opened by whatever spliced it in via `$KEY$`) — so balance is never assumed
    or validated here. `start`/`end` are offsets into the owning `LocValue.raw`."""

    code: str | None
    start: int
    end: int


@dataclass
class IconToken:
    """A `£...£` icon reference. `inner` is the exact text between the delimiters, verbatim —
    usually a plain icon name, but confirmed real variants include a `$VARIABLE$`-parameterised
    name (`£$KEY$£`) and a pipe-parameterised call (`£fleet_status|2£`,
    `£leader_skill|$LEVEL$£`) — `inner` carries all of these opaquely; nothing here decides which
    shape it is. A trailing space inside the delimiters (`£unity £`, real, confirmed in vanilla
    text) is preserved, not trimmed."""

    inner: str
    start: int
    end: int


@dataclass
class VariableToken:
    """A `$...$` substitution reference. `inner` is the exact text between the delimiters,
    verbatim. Confirmed real referents (see markup.py's module docstring): another localisation
    key, an engine/runtime value with no localisation-table entry at all, or (via a leading `@`)
    a Clausewitz `@variable` name — `is_scripted_variable` flags that last case so callers can
    route it into pipeline.variables' namespace without re-parsing `inner`, but the reference
    itself is never resolved here. A trailing `|FORMAT` suffix (`$FLEET_COUNT|Y$`,
    `$@shield_nullification_high|0%$`) is part of `inner`, not decomposed — same "opaque when
    embedded" precedent as the Clausewitz tokeniser's pipe-chain handling."""

    inner: str
    is_scripted_variable: bool
    start: int
    end: int


@dataclass
class BracketCommand:
    """A `[...]` scripted-localisation command: a bare dotted scope/method chain (`[Root.GetName]`,
    `[event_target:x.Planet.GetName]`), a single-quoted concept-link (`['concept_technician']`),
    or a two-argument comma form (`['concept_pc_frozen', Frozen Worlds]`). `inner` is the exact
    text between the brackets, verbatim — the scope-chain/argument grammar is not parsed out
    (same "opaque when embedded" treatment as the Clausewitz `@[...]` arithmetic scanner; nothing
    downstream needs to walk into it structurally, only find it). Genuinely nests — a concept
    link's second argument can itself be a bracket command (`['concept_roboticist',
    [roboticist.GetName]]`) — so `children` holds every directly-nested `BracketCommand` found
    inside this one's own span, recursively. `unterminated` is `True` if no matching `]` was found
    before the value ended (not observed in the real corpus, but the value's `raw` stays
    authoritative regardless — this is diagnostic metadata, not a parse failure)."""

    inner: str
    start: int
    end: int
    children: list["BracketCommand"] = field(default_factory=list)
    unterminated: bool = False


MarkupSpan = Union[ColorMarker, IconToken, VariableToken, BracketCommand]


@dataclass
class LocValue:
    """A localisation entry's value. `raw` is the exact source text between the delimiters —
    between the first and last `"` on the line for a quoted value (see parser.py's module
    docstring for why "first-to-last", not "first-to-next-unescaped"), or the rest of the line
    for the rare unquoted form. `quoted` records which. `spans` is markup.parse_markup(raw) — a
    derived, position-indexed view, never the source of truth; see this module's docstring."""

    raw: str
    quoted: bool
    spans: list[MarkupSpan] = field(default_factory=list)


@dataclass
class LocEntry:
    """A `KEY[:VERSION] "value"` (or `KEY[:VERSION] value`) statement.

    `version` is the raw digit string verbatim (e.g. `"0"`, `"1"`), or `None` if the source
    omitted the suffix. It is carried here purely as data — **it is never part of lookup
    identity**: confirmed decisively by finding 83 real cases where a versioned base-source key
    (vanilla or Gigastructures) is overridden by an unversioned ACOT/AoT definition of the same
    bare key (e.g. `mod_planet_jobs_energy_upkeep_mult`) — ACOT and AoT ship complete, working
    localisation overrides that use almost no version suffixes at all, so if the suffix were part
    of identity those 83 overrides would silently fail to apply. See table.py, which resolves
    purely on `key`.
    """

    key: str
    version: str | None
    value: LocValue
    line: int
    column: int
    file: str = ""
    # Which of the four vendored sources ("stellaris", "gigastructures", "acot", "aot") this
    # definition came from. `None` until table.py's `build_table` stamps it in while resolving
    # across sources — the parser itself never knows about sources (same separation of concerns
    # as pipeline/clausewitz's "does not special-case vanilla and mod in resolution logic").
    source: str | None = None


@dataclass
class MalformedEntry:
    """A key-shaped line that could not be turned into a `LocEntry` — reported, never raised.
    Real, confirmed shapes: a missing closing quote (`acot_herculean_built_score: "§EHerculean
    Built§!`, no closing `"` anywhere on the line, two blank lines follow, then the next entry
    starts normally), a missing opening quote (`ACOT_SC_GUNSHIP_4_DESC: Gunship"` — value starts
    unquoted but a stray `"` appears later on the line, which "genuinely unquoted, no quotes
    anywhere" cannot explain), or unexpected content trailing the closing quote (no real instance
    found in the corpus, but checked for defensively rather than silently accepted or dropped).
    """

    reason: str
    raw_line: str
    line: int
    column: int
    file: str = ""
    source: str | None = None


@dataclass
class LocFile:
    """A parsed localisation file: an ordered list of `LocEntry`/`Comment`/`MalformedEntry`, plus
    the declared language from the file's own `l_<language>:` header line."""

    path: str
    language: str
    items: list[Union[LocEntry, Comment, MalformedEntry]]

    @property
    def entries(self) -> list[LocEntry]:
        return [item for item in self.items if isinstance(item, LocEntry)]

    @property
    def malformed(self) -> list[MalformedEntry]:
        return [item for item in self.items if isinstance(item, MalformedEntry)]
