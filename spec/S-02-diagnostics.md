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
  and unresolved mod dependencies (P-16, a technology needing ACOT or AoT content that is not in
  the rendering-scope closure of anything rendered) — are browsable in the overlay.
- Dataset metadata (mod commit, vanilla version, build timestamp, schema version) is displayed.
- **Per-empire-profile `unknown` rates (D-10) are displayed as a table of all twelve figures**,
  with the worst-case profile highlighted (the one the 10% hard ceiling and 3% warn threshold are
  evaluated against), plus each profile's delta against its own figure in the previous dataset —
  the exact number the D-10 ratchet fails on. This is the one place a developer can see whether a
  regression is isolated to a specific profile rather than reading it off an average that would
  hide one.
- The overlay is inert unless explicitly enabled, and its code MUST NOT measurably affect the
  P-10 budgets when disabled.

## Implied technical decisions

- `?dev` is a query parameter, not a path segment. The application MUST parse it from the query
  string and MUST preserve it across in-app URL updates (empire type, filters, search, popup deep
  links) so that a developer does not lose the overlay while navigating.
- The diagnostics bundle SHOULD be code-split and loaded on demand to protect the initial
  transfer budget.
