"""Scans a `LocValue.raw` string for `§`/`£`/`$`/`[...]` markup, producing a position-indexed,
never-resolved view (see nodes.py's `MarkupSpan`).

This is discovery, not evaluation — nothing here decides what a `§` code renders as, what an
`£icon£` looks like, what a `$VARIABLE$` substitutes to, or what a `[...]` command returns.
spec/P-12-detail-popup.md P-12.1's "resolved or safely stripped" is a Stage 2/3 rendering
decision; a Stage 1 parser that already discarded the raw markup would make that decision
unrevisable.

What real corpus evidence says about each, and why the scanning rule follows from it (see the
Step 1 survey for full counts):

- `§CODE` / `§!`: 48,052 opens vs 47,808 closes across the survey corpus — genuinely unbalanced,
  both directions (unclosed opens; closes with no opener on the same string, plausibly closing
  formatting opened by whatever spliced this string in via `$KEY$`). So opens and closes are
  scanned as independent `ColorMarker` events, never paired or validated for balance.
- `£...£`: never found nested (an inner `£` always closes the token, never opens a new one) —
  confirmed variant inner shapes: plain icon name, `$VARIABLE$`-parameterised, pipe-parameterised
  (`name|param`, param optionally itself a `$VARIABLE$`). Scanned to the next `£`, whatever it
  contains.
- `$...$`: also never found nested — confirmed variant inner shapes: plain identifier (referent
  ambiguous between "another loc key" and "engine-injected runtime value" — `$gc_mega$` resolves
  to a real key, `$FLEET_COUNT$` matches no key anywhere in the corpus, and the two are
  syntactically indistinguishable), dotted (`$crisis.2502.name$`), pipe-formatted
  (`$FLEET_COUNT|Y$`), and `@`-prefixed (`$@shield_nullification_high|0%$` — a genuine reference
  into the Clausewitz `@variable` namespace, flagged via `is_scripted_variable` but not resolved).
  Scanned to the next `$`.
- `[...]`: genuinely nests (`['concept_roboticist', [roboticist.GetName]]`) — the one construct
  here that needs a depth-aware scan, same precedent as the Clausewitz tokeniser's `@[...]`
  arithmetic-expression scanner (pipeline/clausewitz/tokenizer.py's `_scan_arithmetic_expression`).
"""

from __future__ import annotations

from .nodes import BracketCommand, ColorMarker, IconToken, MarkupSpan, VariableToken


def parse_markup(raw: str) -> list[MarkupSpan]:
    spans: list[MarkupSpan] = []
    i = 0
    n = len(raw)
    while i < n:
        ch = raw[i]
        if ch == "§":
            span, i = _scan_color(raw, i)
            if span is not None:
                spans.append(span)
        elif ch == "£":
            span, i = _scan_delimited(raw, i, "£", IconToken)
            if span is not None:
                spans.append(span)
        elif ch == "$":
            span, i = _scan_variable(raw, i)
            if span is not None:
                spans.append(span)
        elif ch == "[":
            span = _scan_bracket(raw, i)
            spans.append(span)
            i = span.end
        else:
            i += 1
    return spans


def _scan_color(raw: str, start: int) -> tuple[ColorMarker | None, int]:
    """`raw[start] == '§'`. `§!` is a close (code=None); `§` followed by exactly one
    letter/digit is an open. Neither shape (e.g. `§` at end of string, or followed by
    something else) is not observed in the real corpus — treated as unclassified rather than
    guessed at; `raw` stays authoritative either way, so no span is lost, only left unindexed."""
    if start + 1 >= len(raw):
        return None, start + 1
    nxt = raw[start + 1]
    if nxt == "!":
        return ColorMarker(code=None, start=start, end=start + 2), start + 2
    if nxt.isalnum():
        return ColorMarker(code=nxt, start=start, end=start + 2), start + 2
    return None, start + 1


def _scan_delimited(raw: str, start: int, delim: str, cls):
    """`raw[start] == delim`. Scans to the next occurrence of `delim` (never nests, per this
    module's docstring) and wraps the text between as `cls(inner, start, end)`. If no closing
    delimiter is found, no span is produced (unterminated `£`/`$` not observed in the real
    corpus); `raw` remains authoritative regardless."""
    close = raw.find(delim, start + 1)
    if close == -1:
        return None, start + 1
    inner = raw[start + 1 : close]
    return cls(inner=inner, start=start, end=close + 1), close + 1


def _scan_variable(raw: str, start: int):
    close = raw.find("$", start + 1)
    if close == -1:
        return None, start + 1
    inner = raw[start + 1 : close]
    return (
        VariableToken(inner=inner, is_scripted_variable=inner.startswith("@"), start=start, end=close + 1),
        close + 1,
    )


def _scan_bracket(raw: str, start: int) -> BracketCommand:
    """`raw[start] == '['`. Depth-aware: whenever a nested `[` is encountered, recurses to
    consume that whole nested command (appending it to `children`) before continuing to scan
    for *this* command's own closing `]` — mirrors
    pipeline/clausewitz/tokenizer.py's `_scan_arithmetic_expression`."""
    i = start + 1
    children: list[BracketCommand] = []
    n = len(raw)
    while i < n:
        ch = raw[i]
        if ch == "[":
            child = _scan_bracket(raw, i)
            children.append(child)
            i = child.end
            continue
        if ch == "]":
            return BracketCommand(inner=raw[start + 1 : i], start=start, end=i + 1, children=children)
        i += 1
    return BracketCommand(inner=raw[start + 1 :], start=start, end=n, children=children, unterminated=True)
