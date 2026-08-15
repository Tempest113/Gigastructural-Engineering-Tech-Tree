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
`pipeline/icons/build.py`'s `filter_result_to_rendered_scope`/`pipeline/icons/pack.py`'s
`MAX_TOTAL_ATLAS_BYTES`. All future budget measurements and the CI ratchet against this figure
measure the compressed base-dataset transfer size as defined here.

**MEASURED (Stage 2 dataset-emission session): the real compressed base-dataset transfer is
~64 KB (65,585 bytes) against the ≤2 MB budget — roughly 30x headroom.** The budget itself is
unchanged (still the acceptance criterion, still worth ratcheting against as the corpus grows),
but **dataset size is no longer a binding constraint on Stage 3's loading design** the way it was
when the only figure available was a ~275-305 KB pre-build projection (itself ~7x headroom, but
close enough to be a real design input at the time). At 30x headroom, a corpus doubling in size
would still land comfortably inside the budget — Stage 3 does not need to design around this
number as a scarce resource.

**The lazy-artefact split (separate empire overlays, detail payloads, search index) stays, but
its justification is no longer "the base dataset must fit the budget."** With this much headroom,
folding a modest amount of overlay/detail content into the base dataset would not itself breach
≤2 MB. The split's real, still-live reasons: **responsiveness** (a 64 KB payload parses and
renders before an all-profiles/all-details bundle would finish downloading, even though the
latter might also technically clear 2 MB — time-to-interactive has its own ≤2.0 s/≤5.0 s budgets
above, independent of the transfer-size budget); **memory** (holding twelve empire overlays' full
per-technology reason text and research paths, plus 980 detail payloads' descriptions and weight
modifiers, resident in the browser simultaneously costs real heap even after the network transfer
is done); and **cache granularity** (a single profile switch or a single popup open should
invalidate/refetch only what changed, not force a full-dataset re-fetch or re-parse). Record these
as the operative reasons going forward — a future session must not re-derive "we split these out
because of the size budget" from this file's history and treat a since-resolved constraint as
still binding.

**Real measured compression ratio: 14.29x, materially above the 6-9x range an earlier projection
assumed — a divergence worth recording, not a coincidence to note in passing.** The deploy-spike
(see HANDOFF.md) measured a 9.34x ratio on a synthetic ~1,878-record blob and explicitly caveated
that real content, carrying more entropy than synthetic filler, should compress *worse* — hence
the 6-9x projected range. The real build compresses *better* instead, and the reason is structural,
not a fluke: the deploy-spike's synthetic blob was dominated by free-text name/description-shaped
content, but the real base dataset's size is dominated by small, highly-repetitive structured JSON
— 980 near-identically-shaped technology records, each carrying a 12-slot enum array
(`availabilityMatrix`), mostly-empty arrays (`gates`, `requiresMods` for 95%+ of nodes), and
frequent `null`s (`crisisFaction` for 925/980) — exactly the shape gzip compresses far better than
prose. Real free-text description content isn't even in the base dataset; it lives in the lazy
detail payloads, outside this budget entirely. **The lesson for future estimation work**: a
compression ratio measured against synthetic content is not a reliable proxy for real structured-
JSON compression, in either direction — measure against the real artefact shape once it exists,
rather than extrapolating from a differently-shaped stand-in.

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
