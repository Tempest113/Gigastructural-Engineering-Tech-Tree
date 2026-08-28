# Client tests

Two tiers, split by whether they need `vendor/` (real, non-redistributable game data) populated:

- **`npm run test`** (Vitest, `src/**/*.test.ts` + `tests/**/*.test.ts`) -- unit tests over pure
  functions (`src/empireProfile.ts`, `src/format.ts`, `src/search.ts`) plus dataset-shape tests
  against the committed fixture at `tests/fixtures/dataset/`. Vendor-independent; runs in CI
  (`.github/workflows/client-tests.yml`).
- **`npm run test:e2e`** (`tests/e2e/check.mjs`) -- a real headless-browser pass against the full
  built dataset. Needs `vendor/` populated locally; **never runs in CI** (same D-15 constraint as
  `tools/build_dataset.py`). See `tests/e2e/README.md`.

## The fixture dataset (`tests/fixtures/dataset/`)

Committed, and regenerable by `python tools/build_client_fixture_dataset.py` (needs `vendor/`
populated to REGENERATE -- the committed output itself needs nothing). It is a small,
real-pipeline-computed slice of the actual corpus (not hand-authored technology data): a curated
technology per shape the client must handle (a gated technology, a repeatable, a technology with
swap variants, one with weight modifiers, one of each `AvailabilityState`, an alternative group),
plus every edge directly touching one of them. `manifest.json`'s `curatedIds` names which
technology plays which role. See that script's own module docstring for why it's a subset of a
real build rather than a synthetic mod corpus.
