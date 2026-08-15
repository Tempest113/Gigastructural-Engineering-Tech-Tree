# S-2 — Developer branch / diagnostics build

**Requirement.** A developer-accessible build MUST be available by appending `/?dev` to the URL.
It MUST display page performance metrics and any runtime errors.

## Acceptance criteria

- Appending `?dev` to any application URL enables the diagnostics overlay without altering graph
  state or requiring a different deployment.
- The overlay displays, at minimum: current and rolling-average frame rate, frame time, node/edge
  counts (total and currently drawn), dataset load time and size, memory usage where the browser
  exposes it, and time-to-interactive.
- All runtime errors and unhandled promise rejections are captured and displayed in the overlay
  with message and stack, rather than being visible only in the browser console.
- Build-time warnings carried in the dataset — tier promotions (P-2), unrecognised gate patterns
  (P-3), missing lock reasons (P-13), unresolved triggers (P-14), the overwrite report (P-15),
  unresolved mod dependencies (P-16, a technology needing ACOT or AoT content that is not in
  the rendering-scope closure of anything rendered), and missing `inline_script` parameters (an
  invocation that doesn't supply a `$PARAM$` the target script body references — confirmed to
  occur in real, shipped vanilla content, so this warns rather than fails the build; see
  `implementation-notes.md`) — are browsable in the overlay.
- Dataset metadata (mod commit, vanilla version, build timestamp, schema version) is displayed.
- **Per-empire-profile profile-dependent-uncertain rates (D-10) are displayed as a table of all
  twelve figures**, with the worst-case profile highlighted (the one the 10% hard ceiling and 3%
  warn threshold are evaluated against), plus each profile's delta against its own figure in the
  previous dataset — the exact number the D-10 ratchet fails on. This is the one place a
  developer can see whether a regression is isolated to a specific profile rather than reading it
  off an average that would hide one. **Unconditional-uncertain count is shown as a separate,
  single figure alongside the table, not a thirteenth column of it** — it is not evaluated
  against the 10%/3% thresholds and has its own ratchet delta, and rendering it inside the same
  table would visually imply it is profile-scoped when it is, by construction, identical for
  every profile. See D-10 in `spec/decisions.md` for why the two are split.
- **The missing-`inline_script`-parameter count is displayed with the same build-over-build
  ratchet shape as D-10's**, so a growing count doesn't quietly become normal: CI fails if the
  count rises against the previous dataset. Unlike D-10 there is no hard ceiling — a missing
  parameter has already been observed in working vanilla content (a code path the invocation
  never reaches), so a nonzero count isn't itself a build-blocking condition, only an upward
  trend is.
- The overlay is inert unless explicitly enabled, and its code MUST NOT measurably affect the
  P-10 budgets when disabled.

## Implied technical decisions

- `?dev` is a query parameter, not a path segment. The application MUST parse it from the query
  string and MUST preserve it across in-app URL updates (empire type, filters, search, popup deep
  links) so that a developer does not lose the overlay while navigating.
- The diagnostics bundle SHOULD be code-split and loaded on demand to protect the initial
  transfer budget.
