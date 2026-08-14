"""Technology/ascension-perk → icon-file resolution.

**Stage boundary — read this before touching the diagnostic/failure split.** This module has no
concept of rendering scope and never decides a build should fail. Recognising
`potential = { always = no }` (a permanently-unreachable technology) requires partial trigger
evaluation — that's Stage 2's partial evaluator (spec/00-overview.md), not something Stage 1
should do by pattern-matching a handful of trigger shapes by hand. An earlier version of this
resolver did exactly that (grepping for `always = no` to exclude "clearly unreachable"
technologies from a missing-icon count) and it was wrong for the same reason a hand-rolled
trigger evaluator anywhere else in Stage 1 would be wrong: it's Stage 2's job, done badly, in the
wrong place. So: `resolve_all` records **every** unresolved candidate as a diagnostic,
uninterpreted, and packs every icon it *can* resolve. **TODO(Stage 2):** once the partial trigger
evaluator and rendering-scope computation exist, the consumer of `IconResolutionResult.unresolved`
is the place that turns "unresolved candidate whose owning technology is in scope" into a build
failure and leaves the rest as a diagnostic — do not move that logic back here.

**TODO(Stage 2) — atlas content must be filtered by rendering scope before it's a real byte-size
number.** This module (and `pack.py`) currently resolve and pack every icon reachable through
the four channels above, across **all four sources unconditionally** — including all 774 of
ACOT's technology icons and AoT's, even though spec/00-overview.md's "Scope of ACOT and AoT"
rule only renders an ACOT/AoT technology when it falls in the prerequisite-edge closure of a
rendered technology, a computation this stage cannot perform (it needs the resolved DAG, which
is Stage 2). The 1,970-tile / 8.5 MB technologies figure measured before this cap (see the git
history around the `MAX_SHEET_DIMENSION` fix) was measured over that superset, not the real
rendering-scope-filtered set — the true tile count is an unknown subset of it, and P-10's ≤2 MB
initial-transfer budget should not be evaluated against the superset figure. Once Stage 2's
closure computation exists, the atlas build's `decode_resolved_icons`/`build_atlases` step needs
an additional filter: only pack icons for candidates whose owning technology survives that
closure. Lossless WebP stays the default until then; switching to lossy is an available lever
*after* the real, scope-filtered size is known, not a workaround for measuring the wrong set.

**Also TODO(Stage 2/3, dataset schema) — whether atlases even count toward the ≤2 MB budget is
still open.** spec/implementation-notes.md and P-9 both require icons to load lazily (not as
part of the initial payload), while P-10's ≤2 MB figure is specifically the *initial* dataset
transfer. If atlases are fetched lazily, they may be entirely outside that budget's accounting,
in which case the 8.5 MB (superset) / eventual scope-filtered figure is not a P-10 violation at
all. This isn't an icon-pipeline decision — it belongs to whoever defines the dataset schema and
the initial-payload/lazy-payload split, and should be resolved there, not assumed here.

Resolution order — four channels, all confirmed against the real corpus (see the Step 1/2 icon
survey):

1. An explicit `icon = "X"` field on the technology/ascension-perk itself → `X`.
2. A `technology_swap` (technologies) or `tradition_swap` (ascension perks) block, checked in
   order: (a) its own explicit `icon = "X"` field; (b) `inherit_icon = yes` → the *owner's*
   resolved icon (channel 1/3, recursively); (c) `inherit_icon = no`, **or the field absent
   entirely** → filename convention on the swap's own `name`. (Absent-field defaults to (c): all
   6 real cases where the field is omitted have their own matching file, so this is not a guess.)
3. No swap, no explicit field → filename convention on the technology/perk's own key.
4. If none of the above resolves to an existing file: `config/icon_overrides.txt` is checked by
   candidate key (see overrides.py). If that has no entry either, the candidate is unresolved —
   recorded as a diagnostic, never silently defaulted to some other icon. In particular,
   `inherit_icon = no` with no icon file of its own is NOT quietly redirected to the owner's
   icon — that would override an explicit authorial refusal, which is exactly the kind of "silent
   wrong colour" this domain has to avoid. The one real instance of this combination
   (`giga_tech_ring_world_swap_no_habitables`) is deliberately left as an unresolved diagnostic;
   see config/icon_overrides.txt for why it isn't seeded with a guessed answer.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pipeline.clausewitz import parse_file
from pipeline.clausewitz.nodes import Assignment, Block, Identifier, StringLiteral

from .overrides import IconOverride, IconOverrideConfigError
from .sources import IconSourceConfig

SWAP_KEYWORD_BY_KIND = {
    "technology": "technology_swap",
    "ascension_perk": "tradition_swap",
}


@dataclass(frozen=True)
class IconCandidate:
    key: str  # bare technology/perk key, or "<owner key>/swap:<swap name>"
    kind: str  # "technology" | "ascension_perk"
    resolved_name: str  # candidate icon key (without .dds) this channel implies
    channel: str  # "explicit_icon" | "inherit_icon" | "swap_filename_convention" | "filename_convention"
    definition_source: str
    file: str
    line: int


def _scalar_text(node) -> str | None:
    if isinstance(node, StringLiteral):
        return node.value
    if isinstance(node, Identifier):
        return node.name
    return None


def collect_candidates(files: list[tuple[str, Path]], kind: str) -> list[IconCandidate]:
    """`files` is `(source_name, path)` pairs for every technology/ascension-perk definition
    file, in any order (candidate order is stable-sorted by the caller once collected across all
    sources — see `resolve.py`'s docstring on determinism concerns living in `pack.py`)."""
    swap_keyword = SWAP_KEYWORD_BY_KIND[kind]
    candidates: list[IconCandidate] = []
    for source_name, path in files:
        doc = parse_file(path)  # a file-level parse failure is a hard stop, same as elsewhere.
        for item in doc.items:
            if not isinstance(item, Assignment) or not isinstance(item.value, Block):
                continue
            owner_key = item.key_name
            icon_field = None
            for sub in item.value.items:
                if isinstance(sub, Assignment) and sub.key_name == "icon":
                    v = _scalar_text(sub.value)
                    if v:
                        icon_field = v
            owner_resolved = icon_field or owner_key
            owner_channel = "explicit_icon" if icon_field else "filename_convention"
            candidates.append(
                IconCandidate(
                    key=owner_key,
                    kind=kind,
                    resolved_name=owner_resolved,
                    channel=owner_channel,
                    definition_source=source_name,
                    file=str(path),
                    line=item.line,
                )
            )

            for sub in item.value.items:
                if not (isinstance(sub, Assignment) and sub.key_name == swap_keyword and isinstance(sub.value, Block)):
                    continue
                swap_name = swap_icon = inherit_icon = None
                for s in sub.value.items:
                    if isinstance(s, Assignment) and s.key_name == "name":
                        swap_name = _scalar_text(s.value)
                    if isinstance(s, Assignment) and s.key_name == "icon":
                        swap_icon = _scalar_text(s.value)
                    if isinstance(s, Assignment) and s.key_name == "inherit_icon":
                        inherit_icon = _scalar_text(s.value)
                if swap_icon:
                    swap_resolved, swap_channel = swap_icon, "explicit_icon"
                elif inherit_icon == "yes":
                    swap_resolved, swap_channel = owner_resolved, "inherit_icon"
                else:
                    swap_resolved, swap_channel = swap_name, "swap_filename_convention"
                if swap_resolved:
                    candidates.append(
                        IconCandidate(
                            key=f"{owner_key}/swap:{swap_name}",
                            kind=kind,
                            resolved_name=swap_resolved,
                            channel=swap_channel,
                            definition_source=source_name,
                            file=str(path),
                            line=item.line,
                        )
                    )
    return candidates


def resolve_icon_files(configs: list[IconSourceConfig], kind: str) -> dict[str, tuple[str, Path]]:
    """`resolved_name -> (winning_source, path)`, cross-source last-wins on the relative
    filename under `<kind>/` — same load-order rule as everywhere else in this pipeline.
    `configs` must already be in load order (see `sources.default_source_configs`)."""
    result: dict[str, tuple[str, Path]] = {}
    for config in configs:
        for path in config.resolve(kind):
            result[path.stem] = (config.name, path)
    return result


@dataclass
class IconResolutionResult:
    candidates: list[IconCandidate]
    icon_files: dict[str, tuple[str, Path]]
    resolved: list[tuple[IconCandidate, Path, str]]  # (candidate, icon path, channel-or-"override")
    unresolved: list[IconCandidate]
    overridden: list[tuple[IconCandidate, IconOverride]]


def resolve_all(
    candidates: list[IconCandidate],
    icon_files: dict[str, tuple[str, Path]],
    overrides: dict[str, IconOverride],
) -> IconResolutionResult:
    resolved: list[tuple[IconCandidate, Path, str]] = []
    unresolved: list[IconCandidate] = []
    overridden: list[tuple[IconCandidate, IconOverride]] = []

    for c in candidates:
        if c.resolved_name in icon_files:
            _, path = icon_files[c.resolved_name]
            resolved.append((c, path, c.channel))
            continue
        override = overrides.get(c.key)
        if override is not None:
            if override.icon_name not in icon_files:
                raise IconOverrideConfigError(
                    f"config/icon_overrides.txt:{override.line}: override for {c.key!r} points "
                    f"at icon {override.icon_name!r}, which does not exist in any source"
                )
            _, path = icon_files[override.icon_name]
            resolved.append((c, path, "override"))
            overridden.append((c, override))
            continue
        unresolved.append(c)

    return IconResolutionResult(
        candidates=candidates, icon_files=icon_files, resolved=resolved, unresolved=unresolved, overridden=overridden
    )
