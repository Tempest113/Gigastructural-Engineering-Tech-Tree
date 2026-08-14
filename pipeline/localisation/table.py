"""Cross-source resolution, lookup, and diagnostics for parsed localisation entries.

Deliberately its own namespace: never merged with `pipeline.variables`' `@variable` table or
`pipeline.inline_scripts`' script-path table, matching spec/implementation-notes.md's precedent
that each of these is a small, separately-correct table rather than one general mechanism forced
to cover unrelated namespaces (see pipeline/variables.py's module docstring for the same
reasoning applied to `@variable` vs. P-15's technology-overwrite table).

Resolution is load-order last-wins — the same whole-key, last-definition-wins rule as
technology overwrites and `@variable` resolution — applied uniformly to two different collision
shapes with the exact same mechanism: a same-file duplicate key (`giga_fe_planetcraft_buff`
redefined later in `giga_l_english.yml`) and a cross-source override (a vanilla/Gigastructures
*versioned* key redefined by an *unversioned* ACOT/AoT entry — confirmed real in 83 cases; see
nodes.py's `LocEntry.version` docstring for why the version suffix plays no part in this). Both
are just "a later `LocEntry` for this key, in iteration order" once files are fed in
(source-load-order, then file-path order, then line order).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .errors import MissingLocalisationKeyError
from .nodes import LocEntry, LocFile, MalformedEntry


@dataclass
class LocalisationTable:
    language: str
    entries: dict[str, LocEntry] = field(default_factory=dict)
    history: dict[str, list[LocEntry]] = field(default_factory=dict)
    malformed: list[MalformedEntry] = field(default_factory=list)

    def get(self, key: str) -> LocEntry | None:
        """The real "absent" signal CLAUDE.md's 'fail on missing localisation for displayed
        strings' rule needs — never a placeholder, never the key name echoed back. `None` means
        exactly one thing: no source, at any point in load order, ever defined this key."""
        return self.entries.get(key)

    def require(self, key: str) -> LocEntry:
        entry = self.entries.get(key)
        if entry is None:
            raise MissingLocalisationKeyError(key)
        return entry

    def __contains__(self, key: str) -> bool:
        return key in self.entries


def build_table(language: str, files_in_load_order: list[tuple[str, LocFile]]) -> LocalisationTable:
    """`files_in_load_order` is `(source_name, LocFile)` pairs, already in the order definitions
    should apply: sources in load order (vanilla, Gigastructures, ACOT, AoT — see
    sources.default_source_configs), and within a source, files in a deterministic order (see
    `sources.LocalisationSourceConfig.resolve`'s sorted glob) with each file's own entries
    already in source-line order (`parser.parse_text` preserves this). `source_name` is stamped
    onto every `LocEntry`/`MalformedEntry` here, not by the parser — the parser has no concept of
    "which of the four vendored sources this file belongs to" (same separation of concerns as
    pipeline.clausewitz never special-casing "vanilla" vs. "mod")."""
    entries: dict[str, LocEntry] = {}
    history: dict[str, list[LocEntry]] = {}
    malformed: list[MalformedEntry] = []
    for source_name, locfile in files_in_load_order:
        for item in locfile.items:
            if isinstance(item, LocEntry):
                item.source = source_name
                entries[item.key] = item
                history.setdefault(item.key, []).append(item)
            elif isinstance(item, MalformedEntry):
                item.source = source_name
                malformed.append(item)
    return LocalisationTable(language=language, entries=entries, history=history, malformed=malformed)


@dataclass
class ValueIsKeyDiagnostic:
    """A key whose *winning* value is, verbatim, itself a key that exists somewhere in this same
    resolved table — confirmed real, upstream (not this parser's invention):
    `giga_fe_planetcraft_buff`'s value was literally the string `"giga_fe_planetcraft_buff"`
    before Gigastructures' own later definition overrode it, and `giga_meopa_fe_resources`'s
    still is, uncorrected. Neither is display text — a bare key name as a whole quoted value is a
    stub/placeholder a translator or designer never finished, not something meant to reach a
    player.

    Two restrictions keep this to that one confirmed shape rather than drowning it in noise:

    - **Quoted values only** — the unquoted case has no corpus evidence either way.
    - **The value must contain an underscore.** A full corpus run without this restriction
      returns 3,370 hits, but 2,854 of them are self-referential *ordinary short English
      words* — `OK -> "OK"`, `sand -> "sand"`, `Human -> "Human"`, `northern -> "northern"` — a
      completely normal, common Paradox convention (a plain word used as both its own key and
      its own display text), not a bug. What actually distinguishes the two confirmed real cases
      from that noise is that `giga_fe_planetcraft_buff` and `giga_meopa_fe_resources` are
      snake_case *internal identifiers*, not English words — restricting to values containing
      `_` (the one cheap, reliable signal available without a dictionary) cuts the corpus count
      from 3,370 to 134, all matching this same internal-identifier-as-display-text shape (e.g.
      `giga_eawaf_disenchanter_1_speed_modifier -> "giga_eawaf_disenchanter_1_speed_modifier"`).
      This trades recall (a same-shape bug in a value with no underscore, e.g. `slotsjackpot1`,
      goes unflagged) for the diagnostic being worth a human's attention rather than 96% noise.
    """

    key: str
    value: str
    file: str
    line: int
    source: str | None


def find_value_is_key_diagnostics(table: LocalisationTable) -> list[ValueIsKeyDiagnostic]:
    findings = []
    for key, entry in table.entries.items():
        if not entry.value.quoted:
            continue
        candidate = entry.value.raw
        if candidate and "_" in candidate and candidate in table.entries:
            findings.append(
                ValueIsKeyDiagnostic(
                    key=key, value=candidate, file=entry.file, line=entry.line, source=entry.source
                )
            )
    return findings


@dataclass
class UnquotedValueDiagnostic:
    """A key whose winning value has no quote delimiters at all (`nodes.LocValue.quoted is
    False`) — e.g. `acot_omegan_blessed: Blessed By Light`.

    Kept as a *diagnostic*, not a `MalformedEntry`: the parser's design treats a genuinely
    unquoted value (no `"` anywhere on the line) as a distinct, valid value shape, separate from
    the confirmed-malformed "missing opening quote" case (a `"` appears later on the line —
    see `parser.py`). But the evidence base for "unquoted is a legitimate shape" is exactly one
    real occurrence in the entire ~194,000-line corpus this parser was built against
    (`acot_05_the_shadow_events_l_english.yml:40`). One occurrence is enough to justify *not*
    hard-failing the parse on it (a single upstream typo must not block the corpus, same
    reasoning as `MalformedEntry`), but it is not enough evidence to say the shape is common or
    reliably intentional — so it stays visible here rather than disappearing into ordinary
    `LocEntry`s. If a future corpus run finds this diagnostic firing at a rate materially above
    "roughly one," that is itself a finding: either the format's use of unquoted values is more
    common than currently known and this parser's model should be revisited with better
    evidence, or the upstream sources have started shipping more of the same class of typo.
    """

    key: str
    value: str
    file: str
    line: int
    source: str | None


def find_unquoted_value_diagnostics(table: LocalisationTable) -> list[UnquotedValueDiagnostic]:
    return [
        UnquotedValueDiagnostic(key=key, value=entry.value.raw, file=entry.file, line=entry.line, source=entry.source)
        for key, entry in table.entries.items()
        if not entry.value.quoted
    ]
