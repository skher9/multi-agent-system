import { expect, test } from "@playwright/test";

// Shared by every test in this file: collect uncaught browser errors and expect none.
// New tests need no setup of their own.
let errors: string[];

test.beforeEach(({ page }) => {
  errors = [];
  page.on("pageerror", (err) => errors.push(err.message));
});

test.afterEach(() => {
  expect(errors).toEqual([]);
});

test("home page loads with its heading", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Hello from the starter app");
});
