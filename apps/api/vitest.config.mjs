import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["tests/worker*.test.mjs"],
    hookTimeout: 120_000,
    testTimeout: 120_000,
  },
});
