import { resolve } from "path";
import { defineConfig } from "vitest/config";

const projectRootDir = resolve(__dirname);

export default defineConfig({
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    globalSetup: "./src/test/globalSetup.ts",
    clearMocks: true,
    coverage: {
      provider: "istanbul",
      include: ["src/**/*.ts", "src/**/*.tsx"],
      exclude: ["src/test/*.ts", "src/**/*.test.ts", "src/**/*.test.tsx"],
      thresholds: {
        branches: 75,
        functions: 75,
        lines: 70,
        statements: 70,
      },
    },
  },
  resolve: {
    alias: [
      {
        find: "/libs/content_roles.js",
        replacement: resolve(
          projectRootDir,
          "src/test/fixtures/content_roles.js"
        ),
      },
      {
        find: "@dashlive/routemap",
        replacement: resolve(projectRootDir, "src/test/fixtures/routemap.js"),
      },
      {
        find: "/libs/options.js",
        replacement: resolve(projectRootDir, "src/test/fixtures/options.js"),
      },
    ],
  },
});
