# Deploy spike — throwaway, delete once Stage 3 lands

**This directory is not part of the tech tree application.** No framework, no build step, no
PixiJS — a static `index.html` plus a tiny script and two dummy artifacts, deployed to GitHub
Pages by `.github/workflows/deploy-spike-pages.yml`. It proves the delivery path end to end
*before* anything depends on it, instead of discovering delivery failure modes while debugging
the real renderer later.

## What it proves

Four things that are silent until they fail, all made visible on the deployed page rather than
assumed:

1. **Base-path resolution under a project subpath.** This repo is not a `<user>.github.io`
   repo, so it deploys at `https://tempest113.github.io/Gigastructural-Engineering-Tech-Tree/`,
   not a domain root. `app.js` fetches both artifacts with plain relative paths
   (`./sample-dataset.json`, `./geometry.f32`) — the same pattern the real client will use — so
   if a leading-slash absolute path had been used by mistake, this would break visibly here
   instead of only under local testing at a domain root (where an absolute path happens to work
   by coincidence).
2. **The MIME type the binary side-file is actually served with.** `spec/00-overview.md`
   specifies typed-array side-files for geometry; nothing in this repo has ever confirmed what
   `Content-Type` GitHub Pages' static hosting actually sends for an unfamiliar extension like
   `.f32`. The page reports the header value it received, not an assumption.
3. **Whether the lazy-fetch pattern behaves against real static hosting**, not just a local dev
   server (which can mask caching, CORS, or path-resolution behaviour that only shows up over
   real HTTP).
4. **Whether the GitHub Actions workflow itself is sound** — permissions, the
   `actions/upload-pages-artifact` + `actions/deploy-pages` pattern, and whether Pages is even
   enabled and configured correctly for this repo (see the root `HANDOFF.md` for the manual
   one-time GitHub UI steps).

## What it deliberately does NOT prove

Nothing about PixiJS, rendering performance, the real dataset schema's actual size, or any
application behaviour — this is delivery-path plumbing only.

## Deleting this

Safe to delete this whole directory and its workflow file (`.github/workflows/deploy-spike-pages.yml`)
once Stage 3 has a real deploy pipeline of its own. It does not appear in `pyproject.toml`,
`tests/`, or any pipeline import — nothing else in the repository references it.
