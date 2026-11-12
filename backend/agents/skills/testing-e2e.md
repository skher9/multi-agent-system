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
- One test per acceptance criterion, named after it.

## Share setup, don't copy it (checked by running it)
What every test in a file needs goes in `test.beforeEach` / `test.afterEach`, once, as
e2e/home.spec.ts does for crashes: it collects `page.on("pageerror", ...)` before each
test and expects none after. A test added to that file gets this for free; a new file
copies those few lines once, at the top, never into each test.
- The same first steps in several tests (open a page, click a button): put them in
  `test.beforeEach`, or in a small function at the top of the file that the tests call.
- Each test then holds only what it alone does and checks.
