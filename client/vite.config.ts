import { defineConfig } from "vite";

// `base: "./"` (relative, not absolute) is deliberate -- deploy-spike/README.md's own finding:
// this repo deploys to a GitHub Pages *project* subpath
// (https://tempest113.github.io/Gigastructural-Engineering-Tech-Tree/), not a domain root, and a
// leading-slash absolute base would silently work under local dev/preview at a domain root while
// silently breaking once actually deployed. Relative resolution is the same pattern the spike
// proved end to end and the one this real client keeps.
export default defineConfig({
  base: "./",
  build: {
    outDir: "dist",
    // Content-hashed filenames (Vite's default for build output) are the cache-busting
    // mechanism -- GitHub Pages' cache headers are not configurable, so a changed build must
    // change its filenames, not rely on a cache-control header this host will never send.
    assetsDir: "assets",
  },
  server: {
    port: 5173,
  },
});
