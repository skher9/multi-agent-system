// End-to-end tests in a real browser. Run: pnpm test:e2e
// The @playwright/test version must match the sandbox image (mcr.microsoft.com/playwright:v1.64.0-noble).
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI, // a leftover test.only fails CI instead of skipping everything else
  retries: process.env.CI ? 1 : 0, // one retry; a pass on retry is reported as flaky
  reporter: [["list"]],
  use: {
    baseURL: "http://localhost:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  // Test the production build, which is what users get
  webServer: {
    command: "pnpm build && pnpm start",
    url: "http://localhost:3000",
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
  },
});
