# End-to-end check (local only)

`check.mjs` is the committed form of the headless-Playwright verification pass that had been run
by hand every session and never checked in: 0 browser console errors, 0 failed network requests,
and 0 violations across the six numeric invariant checks `client/src/main.ts`'s own
`window.__tt` test-hook API exposes (name-bounds, indicator-bounds, gate-label-bounds,
edge-containment, min-stub, tier-badge).

## Why this can't run in CI

Same reason as `tools/build_dataset.py` (see D-15, CLAUDE.md's "Locked decisions"): it needs the
**full real dataset** served at `client/public/dataset/`, which needs `vendor/` populated, which
needs a Steam account that owns Stellaris. This is a permanent local-only check, not a gap to
close later -- there is deliberately no CI workflow that runs it.

## Prerequisites (one-time)

```
python tools/collect_vanilla.py        # populates vendor/ (needs Steam)
pip install -e ".[dev]"
cd client && npm install
npm install -D playwright && npx playwright install chromium
```

## Running it

```
python tools/build_dataset.py          # builds client/public/dataset/ from vendor/
cd client
npm run dev &                          # or: npm run build && npm run preview
node tests/e2e/check.mjs               # defaults to http://localhost:5173
```

Exits non-zero (and prints every violation, capped at 10 per check) if anything failed; exits 0
and prints "OK" otherwise.
