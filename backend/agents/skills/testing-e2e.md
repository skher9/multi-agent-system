---
name: testing-e2e
description: Playwright browser tests in this repo: where they go, how they run, the patterns to follow. Load before writing browser tests (e2e/).
when: "@playwright/test" in package.json
---
# Browser tests here (Playwright 1.64)

- Files: `e2e/*.spec.ts`; `import { expect, test } from "@playwright/test"`.
- Run: `run_e2e` (QA only). It builds and starts the production app itself
  (`webServer` in playwright.config.ts): never start a server yourself.
- `baseURL` is set: `await page.goto("/about")`.

## Patterns (follow e2e/home.spec.ts)
- Query by role and accessible name: `page.getByRole("heading", { level: 1 })`,
  `page.getByRole("link", { name: "About" })`, `page.getByRole("button", { name: "Like (0)" })`.
- Assert with auto-waiting matchers: `await expect(locator).toHaveText(...)`,
  `toBeVisible()`, `await expect(page).toHaveURL("/about")`.
- Navigation: `await page.getByRole("link", { name: "About" }).click()` then `toHaveURL`.
- Catch crashes: collect `page.on("pageerror", ...)` and expect none, as the home test does.
- One test per acceptance criterion, named after it.
