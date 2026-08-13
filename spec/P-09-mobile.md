# P-9 — Mobile support

**Requirement.** The tool MUST be fully functional and usable on mobile devices, including
touch-based panning, zooming, and interaction with technology nodes. No feature available on
desktop may be unavailable on mobile.

## Acceptance criteria

- One-finger drag pans; two-finger pinch zooms; double-tap zooms to a sensible level centred on
  the tap point.
- Tap opens the detail popup; long-press isolates (per P-7).
- All interactive targets meet a minimum 44 × 44 CSS-pixel touch target at default zoom.
- The detail popup is usable on a narrow viewport (≥360 px wide) without horizontal scrolling,
  and is dismissible by swipe and by an explicit close control.
- Filter and search controls are reachable without obscuring the graph, e.g. via a collapsible
  panel or bottom sheet.
- The application is verified on at least one recent iOS Safari and one recent Android Chrome
  device, at a mid-range hardware tier, against the P-10 budgets.
- Browser page zoom, pull-to-refresh and overscroll must not conflict with in-canvas gestures.

## Implied technical decisions

- Input MUST be handled via Pointer Events with unified handling for mouse, touch and pen;
  separate mouse and touch code paths are prohibited to avoid behavioural divergence.
- Memory budget on mobile forces a compact dataset representation (typed arrays / columnar
  structures) and lazy loading of description text and icons (`implementation-notes.md`).
- Hover-only affordances are prohibited; every hover behaviour MUST have a tap or press
  equivalent.
