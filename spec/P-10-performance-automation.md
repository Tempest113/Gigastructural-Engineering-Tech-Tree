# P-10 — High performance and automated maintenance

**Requirement.** The tool MUST be high-performance and MUST support automation via scripts and
GitHub Actions CI/CD pipelines. Manual maintenance burden MUST be minimised: data MUST be
parseable and updatable programmatically from mod source files.

## Acceptance criteria — performance

| Metric | Budget |
| --- | --- |
| Time to interactive (desktop, warm cache) | ≤ 2.0 s |
| Time to interactive (mid-range mobile, cold cache, 4G) | ≤ 5.0 s |
| Sustained frame rate during pan/zoom (desktop) | ≥ 60 fps |
| Sustained frame rate during pan/zoom (mid-range mobile) | ≥ 30 fps |
| Search input → results rendered | ≤ 100 ms |
| Filter toggle → view updated | ≤ 100 ms |
| Initial dataset transfer (compressed) | ≤ 2 MB |

**"Initial dataset transfer" is the base dataset only — the JSON (technology records, edges,
adjacency, layout/geometry references) plus its typed-array geometry side-files, measured
compressed, over the wire.** It excludes empire overlays, detail payloads, the search index
(all lazy, fetched after the initial load), and icon atlas image bytes (lazy per P-9 and
`implementation-notes.md`; `00-overview.md` treats atlas *references* — not atlas images — as
the base-dataset item). Icon atlas bytes have their own separate cap — see
`pipeline/icons/resolve.py`'s Stage 2 TODO. All future budget measurements and the CI ratchet
against this figure measure the compressed base-dataset transfer size as defined here.

## Acceptance criteria — automation

- A single command (e.g. `npm run build:data`) regenerates the entire dataset from source with no
  manual editing steps.
- A scheduled GitHub Actions workflow checks the upstream mod for changes, regenerates the
  dataset, runs validation, and opens a pull request (or auto-deploys on a protected branch) when
  the output changes. This scheduled sync covers **Gigastructural Engineering only**. ACOT and
  AoT are Steam Workshop only and cannot be pinned to a commit; they are vendored manually, and
  their versions are recorded by hand in dataset metadata. The collector hashes each vendored
  tree so CI can at least detect that a local copy changed, even though it cannot fetch updates
  for them.
- CI runs on every pull request: parser tests, dataset schema validation, DAG validation
  (acyclicity, tier consistency), link validation (P-12.6), and a bundle-size check against the
  budget above.
- Deployment to the production static host is fully automated from the default branch.
- **Zero technology data is hand-authored.** The only hand-maintained files are configuration:
  empire profiles (P-1), gate patterns (P-3), crisis classification rules (P-5),
  overwrite-resolution overrides (P-15), icon overrides (P-3 — `config/icon_overrides.txt`, for
  the rare case where an upstream source ships a technology/swap referencing an icon it never
  shipped, with no local fix available; never a silent fallback, always a reviewed, justified
  entry), the lock-reason override table (P-13 — used when a locked technology's reason string
  cannot be derived automatically from its trigger; the build MUST warn when an override is
  missing rather than rendering a blank or guessed reason), and ACOT/AoT version metadata (P-16),
  which cannot be pinned by the scheduled sync above and so is recorded by hand.

## Implied technical decisions

- Upstream mod sources MUST be pinned to a specific commit or release, recorded in the dataset,
  and displayed in the UI as a "data as of" marker. Un-pinned fetching makes builds
  non-reproducible.
- The build MUST fail rather than emit a partial dataset when validation fails, and MUST produce
  a human-readable diff summary of what changed between dataset versions.
