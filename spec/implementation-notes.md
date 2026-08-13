# Implementation notes

## Clausewitz string literals

Double-quoted strings MAY span multiple lines. Confirmed in real, shipped content — e.g. a
parameter value opening `"` at end of line, several lines of ordinary-looking text, then a lone
`"` closing it several lines later. The parser MUST scan a string to its next unescaped `"` or
end of file, never treating a bare newline as a terminator. This matters beyond cosmetics: one
observed real shape is a whole `inline_script = { ... }` invocation embedded as string *data*
inside another `inline_script`'s parameter (passed to a helper that conditionally splices it
back in) — the string's contents look like script but MUST be treated as opaque text at the
parsing stage, not walked or interpreted as if it were live script.

## Clausewitz identifier grammar: scope suffixes and dotted chains

Two shapes attach directly to an identifier with no intervening whitespace, and both parse as
one opaque identifier token rather than being split or requiring a new AST node:

- **Scope suffix.** `flag_name@scope` (e.g. `has_star_flag = ehof_megastructure_system@root`)
  attaches a scope reference to a flag name with `@`. This is unrelated to a scripted-variable
  reference (`cost = @tier1cost1`) even though both use `@` — the distinguishing signal is
  whether the `@` is attached to a preceding identifier character (scope suffix) or starts a
  fresh token after whitespace/an operator/a brace (scripted variable). Getting this wrong is
  worse than an honest parse failure: before the fix, the tokeniser silently split the flag name
  and misread the scope as an unrelated top-level `@variable` reference, corrupting the flag
  value and fabricating a bogus variable usage that would have shown up as a false "undefined
  variable" finding.
- **Dotted chains.** A `.` attached to an identifier, followed immediately by another
  identifier-start character or a digit, chains on one more identifier-shaped segment —
  repeatable, so `crisis.8060.1` and `root.owner.overlord` both parse as a single token. Two
  idioms share this shape: the event-id idiom (`country_event = { id = bio.1 }`, namespace
  followed by a number) and scope-chain references used as plain values (`is_same_species =
  root.owner`). Both are required to parse `common/ascension_perks/` (P-3's gate identities) —
  every file in it across all four sources uses at least one of the two. Requiring an
  identifier-start character or digit immediately after the `.` (never whitespace, EOF, or other
  punctuation) is deliberate: it's what lets the tokeniser consume `root.owner` as one token
  without also swallowing an unrelated trailing `.` elsewhere in the grammar.

These two rules compose: `flag_name@root.owner` (scope suffix whose scope is itself a dotted
chain) parses correctly as one token as a consequence of applying both rules in sequence, without
either rule needing to know about the other.

## Trigger evaluation

This is the highest-risk component of the system and deserves explicit design attention.

Clausewitz triggers are a full conditional language evaluated against live game state.
Determining "is technology X available to empire type Y" is therefore **not decidable in
general** from static analysis. The specified approach is a **partial evaluator**:

- Empire profiles (P-1) supply a set of known facts.
- The evaluator walks the preserved boolean structure of each trigger block and resolves what it
  can.
- Every condition resolves to `true`, `false`, or `unknown`.
- `unknown` MUST propagate: `unknown AND false` is `false`, but `unknown AND true` is `unknown`.
- Technologies whose availability resolves to `unknown` MUST be flagged in the dataset, rendered
  with an "availability uncertain" indicator, and listed in the `/?dev` overlay so that the fact
  registry can be extended over time.

Assuming `unknown` means "available" (or "unavailable") would produce a confidently wrong tree,
which is worse for the user than an honestly uncertain one.

## Stage 2 — Dataset emission

To satisfy both P-1 (per-empire-type correctness) and P-10 (transfer budget), the recommended
structure is:

- **Base dataset** — technology records, layout coordinates, edge geometry, search index, icon
  atlas references. Shared across empire types.
- **Empire overlays** — per-empire-profile availability state (available / locked / uncertain,
  P-13), lock or uncertainty reasons, active edge set, swap mappings, and precomputed research
  paths. Loaded on demand when the user selects a profile.
- **Detail payloads** — descriptions, weight modifier lists, and repository links, chunked and
  lazily fetched when a popup opens.

The dataset MUST carry a `schemaVersion`. The client MUST refuse to render a dataset whose schema
version it does not support, with a clear message, rather than degrading silently.

## Rendering architecture

- **Static layout, dynamic visibility.** All filtering, search and isolation operate as masks
  over fixed geometry. Nothing re-lays-out at runtime. This underpins P-2, P-4, P-6, P-7 and the
  performance budgets.
- **Viewport virtualisation.** Nodes and edges MUST be culled against the viewport, using a
  spatial index (grid or R-tree) computed at build time.
- **Layer separation.** Tier band backgrounds (S-3), connectors (P-8), node cards, and emphasis
  overlays SHOULD be separate render layers so that a filter toggle redraws only the affected
  layers.
- **Level of detail.** A single shared LOD threshold table governs S-1 pattern degradation, S-3
  band emphasis, and node card text/icon shedding.
- **Accessibility.** A canvas renderer is opaque to assistive technology. The application MUST
  maintain a parallel accessible representation — at minimum, keyboard-navigable focus over
  visible nodes, an accessible name for the focused node, and a DOM-based detail popup (which the
  popup already is). Full keyboard equivalence for pan/zoom/filter/search SHOULD be provided.

## Feature registry

A checked-in JSON file (e.g. `feature-registry.json`) enumerating every user-facing feature
identifier the user guide (P-11) is permitted to document — one entry per documented gesture,
control or field, each carrying at minimum an `id` and the requirement it implements (e.g.
`"long-press-isolate": "P-7"`). CI parses the guide content, extracts every feature identifier it
references, and fails the build if any identifier isn't present in this file — catching guide
content that documents a feature which was renamed or removed. Adding a feature to the
application requires adding its entry here in the same change, so the registry cannot silently
drift out of sync with what's actually built.

## `inline_script` expansion

A build-time pass, running after parsing and **before** `@variable` resolution (an invocation's
parameter value, or a script body's own content, can itself be an `@variable` reference — that
reference should reach the variable resolver as ordinary, already-expanded `@variable` syntax,
not as something the expander has to understand). Both bare (`inline_script = path`) and
structured (`inline_script = { script = path  PARAM = value ... }`) invocation forms unify
naturally at the AST level: the bare form is the structured form with zero parameters.

**Expansion is text substitution on the target file's raw source, before tokenising — not
substitution of `ParameterReference` nodes in an already-parsed AST.** Roughly half of real
`$PARAM$` usage is embedded mid-token (e.g. a target file's own top-level key built as
`giga_tech_repeatable_$name$_cap`) rather than standing alone as a whole token, which an AST
node cannot represent. The pass reads the target file's raw text, replaces every `$NAME$` span
with the invoking parameter's raw source text, and only then tokenises and parses the result
with the ordinary parser.

**Expansion is a block splice, not a value substitution.** An `inline_script` invocation
provides some or all of its surrounding block's own members (per the `giga_mega_repeatable`
case, where the invocation's own wrapping technology supplies the tech's real key, and the
target's content becomes that tech's fields). The `inline_script` assignment itself is removed
from its parent block and replaced by the (parameter-substituted, re-parsed) target's items.
This produces a new `Document`/`Block` with the splice applied; the originally parsed AST,
`inline_script` assignment intact, is never mutated — same non-mutation principle as `@variable`
resolution, in service of the same goal (P-15's repository-link and diff provenance stays
meaningful; see P-12.6).

**Parameters:**
- A parameter supplied at the invocation but never referenced by the target body is not an
  error — silently unused. Real, shipped content does this (a static target script invoked with
  an ignored parameter, apparently copy-pasted from a parameterised sibling).
- A parameter the target body references but the invocation never supplies warns, does not fail
  the build — confirmed to occur in real vanilla content (a target script referencing a
  parameter one specific invocation never supplies, on an apparently-unreached branch). Tracked
  with a build-over-build ratchet in S-2, no hard ceiling (see S-2).
- The two aren't reported in isolation from each other: a misspelled parameter name produces
  both a missing parameter (the correctly-spelled name the body wants) and an unused one (the
  misspelled name that was actually supplied) at the same invocation site. Surfacing both,
  logging the unused case at debug level rather than discarding it, is what makes that pairing
  visible enough to actually be diagnosable as a typo.

**Nesting and cycles.** Inline scripts commonly invoke other inline scripts (confirmed to a
depth of 6 in real content, with real parameter pass-through between levels). Cycle detection
runs on the **parsed** AST, after string content has become opaque `StringLiteral` values that
are never walked as script — a real recursive-looking idiom exists where a script passes its
own name as *string data* to a generic helper that conditionally re-splices it; detecting cycles
by scanning raw text for `script = path` occurrences (without excluding string content) produces
false positives against this pattern. Structural DFS cycle detection, same shape as the variable
resolver's, operating on real invocation edges: MUST NOT false-positive on it.

**Depth and size limits.** No structural cycle exists in the corpus today (verified), but cycle
detection alone doesn't bound a future upstream change that introduces runaway breadth without
forming a cycle (e.g. a script that fans out to many large siblings without ever revisiting
itself). Two named, hard-failing constants: a maximum expansion depth and a maximum total
expanded size (bytes or node count). Exceeding either fails the build, naming the full
invocation chain that hit the limit — not a warning, since either condition means the build
cannot know it has produced a complete, correct result.

**Load-order overwrites of the script files themselves.** A relative `script = path` can be
defined in more than one source (confirmed: several vanilla-vs-ACOT and one
vanilla-vs-Gigastructures collision on the same relative path). Resolving `path` to an actual
file goes through its own load-order-ordered, last-source-wins lookup table, keyed by relative
path — structurally the same shape as the `@variable` definition table, but a separate table:
the two namespaces (`@name`, script path) don't share entries and gain nothing from being forced
into one general mechanism.

## Interaction composition semantics

Filters, search and isolation can be active simultaneously. The specified composition, in
precedence order, is:

1. **Empire-profile availability state (P-13)** applies first and is never overridden — a locked
   or uncertain technology is always shown as such when visible.
2. **Isolation (P-7)**, when active, defines the candidate set: only the isolated node and its
   related nodes are eligible for display.
3. **Category and crisis filters (P-4, P-5)** intersect with the candidate set.
4. **Search (P-6)** applies emphasis (highlight mode) or further restriction (isolate mode)
   within the result of steps 1–3.

The UI MUST show all active constraints simultaneously (e.g. as removable chips) and MUST
provide a single "clear all" control, so a user cannot get stuck looking at an empty graph
without understanding why.
