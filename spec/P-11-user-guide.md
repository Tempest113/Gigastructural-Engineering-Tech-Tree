# P-11 — User guide

**Requirement.** A clear, comprehensive user guide MUST be included, covering all interactive
features and explaining filtering, search, isolation and navigation.

**English only for v1.** The pipeline is language-parameterised, so additional languages are a
build flag rather than a rewrite.

## Acceptance criteria

- The guide is reachable from the main UI in one interaction and does not require leaving the
  site.
- It documents, at minimum: empire-type selection; reading the tier columns; the meaning of every
  colour, pattern and badge (cross-referencing S-1); gate indicators; the ACOT/AoT mod-requirement
  badge and why some ACOT/AoT technologies appear on the tree (P-16); category filtering; crisis
  filtering; search modes; isolation (both middle-click and long-press); the detail popup fields;
  and pan/zoom on both desktop and touch.
- Every documented gesture lists both its desktop and its mobile form.
- The guide includes a compact legend that can be opened alongside the graph without losing view
  state.
- Guide content is versioned in the repository alongside the code, and CI fails if a documented
  feature identifier no longer exists in the checked-in feature registry (`implementation-notes.md`).
