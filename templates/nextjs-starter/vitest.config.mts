// Unit tests (from the official Next.js Vitest guide). Run: pnpm test
import react from "@vitejs/plugin-react";
import tsconfigPaths from "vite-tsconfig-paths";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [tsconfigPaths(), react()],
  test: {
    environment: "jsdom",
    exclude: ["e2e/**", "node_modules/**"], // e2e/ belongs to Playwright
  },
});
