#!/usr/bin/env bash
# Local build + publish step for the deploy model spec/decisions.md's vendoring-automation
# decision settled on: the dataset cannot be built in CI (vanilla Stellaris requires a Steam
# account that owns the game -- see tools/build_dataset.py's module docstring), so it is built
# HERE, where vendor/ already exists, and handed to GitHub Actions only as a pre-built artefact
# to publish -- .github/workflows/deploy.yml never runs the pipeline or the client build itself.
#
# What this script does, in order:
#   1. python tools/build_dataset.py       -- writes client/public/dataset/ (gitignored)
#   2. npm run build (in client/)          -- tsc --noEmit, then vite build -> client/dist/
#      (Vite copies public/ verbatim into dist/, so the dataset -- including integrity.json --
#      ends up inside the built artefact automatically)
#   3. Zips client/dist/ into dist.zip
#   4. Publishes dist.zip as an asset on a GitHub Release (tag: deploy-<UTC timestamp>), via the
#      `gh` CLI -- requires `gh auth login` to have been run once, same as any other `gh` usage.
#   5. Prints the exact `gh workflow run` command (or Actions-tab instructions) to trigger
#      .github/workflows/deploy.yml against that release tag.
#
# This script does NOT trigger the deploy workflow itself -- publishing a release and triggering
# a live deploy are kept as two separate, deliberate steps so a build can be prepared and
# reviewed (its integrity.json, its size) before anything goes live.
#
# Requires: python (with the pipeline's dev dependencies installed), node/npm (client/.nvmrc),
# the `gh` CLI authenticated against this repo, `zip`.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

command -v gh >/dev/null 2>&1 || { echo "error: gh CLI not found -- see https://cli.github.com/" >&2; exit 1; }
command -v zip >/dev/null 2>&1 || { echo "error: zip not found" >&2; exit 1; }
[ -d vendor ] || { echo "error: vendor/ not populated -- see CLAUDE.md's 'Source data' section" >&2; exit 1; }

echo "== Building dataset (python tools/build_dataset.py) =="
python tools/build_dataset.py

echo
echo "== Building client (npm run build) =="
(cd client && npm run build)

echo
echo "== Packaging client/dist/ =="
rm -f dist.zip
(cd client/dist && zip -qr ../../dist.zip .)
echo "  $(du -h dist.zip | cut -f1) -> dist.zip"

TAG="deploy-$(date -u +%Y%m%d-%H%M%S)"
echo
echo "== Publishing release ${TAG} =="
gh release create "$TAG" dist.zip \
  --repo "$(gh repo view --json nameWithOwner -q .nameWithOwner)" \
  --title "Deploy ${TAG}" \
  --notes "Pre-built client artefact for manual Pages deploy. See client/public/dataset/integrity.json (inside dist.zip) for exact provenance. Not a source release -- built artefacts only."

rm -f dist.zip

echo
echo "== Done =="
echo "Release '${TAG}' published with dist.zip attached."
echo "Trigger the deploy workflow against it with:"
echo
echo "  gh workflow run deploy.yml -f release_tag=${TAG}"
echo
echo "...or via the Actions tab: 'Deploy to GitHub Pages' -> Run workflow -> release_tag: ${TAG}"
