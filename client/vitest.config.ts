import { defineConfig } from "vitest/config";

// Separate from vite.config.ts (which is build/dev-server config only) -- vitest's own config
// merging with a `base: "./"` build config has caused surprising path resolution before in other
// projects, and this project's test needs (Node environment, no dev-server concerns) are simple
// enough not to need whatever vite.config.ts grows in the future.
export default defineConfig({
  test: {
    environment: "node",
    include: ["src/**/*.test.ts", "tests/**/*.test.ts"],
  },
});
