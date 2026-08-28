#!/usr/bin/env python3
"""Field-consumption invariant (Item 3, client test-infrastructure task): every schema field is
either consumed somewhere in `client/src/` or explicitly, reviewedly annotated as not needing to
be. This is the check whose absence let six real fields (`.weight`, `.variants`, `.source`,
`.repositoryLink`, `.repeatableCostProgression`, `.overwriteDiff`) go unread indefinitely -- a
survey found them only by hand.

**Direction, deliberately**: walks `schema/generated/dataset-types.ts` for the field list, then
greps `client/src/` for each field NAME. Never the other direction (walk the client, check the
schema) -- that would only prove the client references real fields, not that it references EVERY
field, which is the actual gap this exists to close.

**Annotation file**: `config/consumed_field_annotations.txt`, in the same reviewed,
one-entry-per-line, `#`-justified format as `config/icon_overrides.txt`. Every field that this
script cannot find a real `client/src/` reference for MUST have a matching annotation entry, or
the check fails. An annotation for a field name that no longer appears in the schema also fails
the check (stale-entry rot -- CLAUDE.md's own standing complaint about exactly this file shape).

Run: `python tools/check_field_consumption.py` (no vendor/ dependency -- pure schema + client
source, works everywhere, wired into a real CI job).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TYPES_FILE = REPO_ROOT / "schema" / "generated" / "dataset-types.ts"
CLIENT_SRC = REPO_ROOT / "client" / "src"
ANNOTATIONS_FILE = REPO_ROOT / "config" / "consumed_field_annotations.txt"

FIELD_LINE_RE = re.compile(r"^(?P<indent>\s*)(?P<name>[A-Za-z_][A-Za-z0-9_]*)\??:\s*(?P<rest>.*)$")


def _strip_doc_comment_lines(lines: list[str]) -> list[str]:
    """Drops `/** ... */` doc-comment lines (always their own whole line in this generated file --
    confirmed by inspection, `tools/generate_typescript_types.py`'s own output convention) so they
    can't be mistaken for field declarations or thrown off the brace-depth count below."""
    return [ln for ln in lines if not ln.strip().startswith("/**")]


def parse_interfaces(text: str) -> dict[str, list[str]]:
    """Returns {interface_name: [dotted field paths]}. A brace-depth walk, not a real TS parser --
    sound for THIS generated file's consistent style (one field per line, doc comments on their
    own line, an object-typed field's `{` opens on the same line as its name) because
    `tests/schema/test_typescript_drift.py` already pins that style byte-for-byte; a hand-written
    dataset-types.ts could defeat this, but nothing hand-writes it (CLAUDE.md: generated,
    DO NOT EDIT BY HAND)."""
    lines = _strip_doc_comment_lines(text.splitlines())
    interfaces: dict[str, list[str]] = {}

    i = 0
    n = len(lines)
    while i < n:
        m = re.match(r"^export interface (\w+) \{\s*$", lines[i])
        if not m:
            i += 1
            continue
        interface_name = m.group(1)
        fields: list[str] = []
        stack: list[str] = []
        depth = 0
        i += 1
        while i < n:
            line = lines[i]
            stripped = line.strip()
            if stripped in ("}", "};") and depth == 0:
                i += 1
                break
            field_match = FIELD_LINE_RE.match(line)
            delta = line.count("{") - line.count("}")
            if field_match:
                name = field_match.group("name")
                path = ".".join([interface_name, *stack, name])
                fields.append(path)
                if delta > 0:
                    stack.append(name)
                    depth += delta
                elif delta < 0:
                    # Closed on the same line it opened (rare, e.g. an inline `{}`) -- net no push.
                    pass
            elif delta < 0:
                for _ in range(-delta):
                    if stack:
                        stack.pop()
                depth += delta
            elif delta > 0:
                # A brace opened on a line with no field name attached to it (shouldn't happen in
                # this generator's style, but fail loudly rather than silently mis-nesting).
                raise ValueError(f"{interface_name}: unexpected bare '{{' at line {i}: {line!r}")
            i += 1
        interfaces[interface_name] = fields
    return interfaces


def leaf_field_names(paths: list[str]) -> set[str]:
    """Just the final segment of each dotted path -- what a grep for `.fieldName` can actually
    check for. Two different interfaces sharing a leaf name (e.g. `label`) are intentionally
    collapsed together: curation here is at the FIELD-NAME level, same posture as
    `pipeline/gate_patterns.py`'s own "curation is at the MECHANISM level, not per-technology"."""
    return {p.rsplit(".", 1)[-1] for p in paths}


def load_client_source() -> str:
    texts = []
    for path in sorted(CLIENT_SRC.glob("*.ts")):
        if path.name.endswith(".test.ts"):
            continue
        texts.append(path.read_text())
    return "\n".join(texts)


def is_consumed(field_name: str, client_text: str) -> bool:
    return re.search(rf"\.{re.escape(field_name)}\b", client_text) is not None


ANNOTATION_LINE_RE = re.compile(
    r"^(?P<path>[A-Za-z_][\w.]*)\s*\|\s*(?P<usage>displayed|key-only|not-needed)\s*#\s*(?P<justification>.+)$"
)


def load_annotations() -> dict[str, tuple[str, str]]:
    """Each non-comment, non-blank line: `Interface.field | usage # justification`. `usage` is
    one of:
      - `key-only`   -- consumed only as a map/cache/lookup key (e.g. `technologyId`), never
                        DISPLAYED -- a real, reviewed distinction from a value the user actually
                        sees, since a naive grep for `.fieldName` calls both "consumed" alike.
      - `displayed`  -- reaches the user, but NOT through a literal `.fieldName` grep hit (e.g. a
                        gate's `negated`/`kind`/`refId`/`alternative` fields reach the user through
                        pre-rendered label text or `groupId`-derived equivalence -- correct design,
                        not a gap; see the module docstring's known-false-positives list).
      - `not-needed` -- a genuine KNOWN GAP: not consumed today, not display-relevant to any
                        shipped feature, tracked for follow-up work (the justification MUST name
                        it) -- e.g. the six survey-found unconsumed fields this whole task exists
                        because of.
    A line failing this shape is a hard error (same discipline as a malformed
    `config/icon_overrides.txt` entry) -- this file rots exactly the way CLAUDE.md warns about if
    a bad entry can silently no-op."""
    entries: dict[str, tuple[str, str]] = {}
    for lineno, raw in enumerate(ANNOTATIONS_FILE.read_text().splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = ANNOTATION_LINE_RE.match(line)
        if not m:
            raise ValueError(f"{ANNOTATIONS_FILE}:{lineno}: malformed annotation line: {raw!r}")
        entries[m.group("path")] = (m.group("usage"), m.group("justification"))
    return entries


def main() -> int:
    interfaces = parse_interfaces(TYPES_FILE.read_text())
    all_paths = sorted({p for paths in interfaces.values() for p in paths})
    client_text = load_client_source()
    annotations = load_annotations()

    schema_paths = set(all_paths)
    stale = sorted(p for p in annotations if p not in schema_paths)
    if stale:
        print("STALE annotation entries (field no longer exists in dataset-types.ts):")
        for p in stale:
            print(f"  {p}")
        return 1

    consumed: list[str] = []
    annotated: dict[str, list[str]] = {"key-only": [], "displayed": [], "not-needed": []}
    unaccounted: list[str] = []

    for path in all_paths:
        field_name = path.rsplit(".", 1)[-1]
        if path in annotations:
            usage, _just = annotations[path]
            annotated[usage].append(path)
            continue
        if is_consumed(field_name, client_text):
            consumed.append(path)
        else:
            unaccounted.append(path)

    total = len(all_paths)
    print(f"Total fields: {total}")
    print(f"  Consumed (grep-verified `.fieldName` reference in client/src/): {len(consumed)}")
    print(f"  Annotated displayed (reaches user, not via a literal grep hit): {len(annotated['displayed'])}")
    print(f"  Annotated key-only (map/cache key, never displayed):           {len(annotated['key-only'])}")
    print(f"  Annotated KNOWN GAP (not-needed today, tracked as debt):       {len(annotated['not-needed'])}")

    if unaccounted:
        print("\nUNACCOUNTED fields -- neither consumed nor annotated:")
        for p in unaccounted:
            print(f"  {p}")
        print(
            f"\n{len(unaccounted)} field(s) need either real client/src/ consumption or a reviewed "
            f"entry in {ANNOTATIONS_FILE.relative_to(REPO_ROOT)}."
        )
        return 1

    print("\nOK -- every schema field is consumed or reviewedly annotated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
