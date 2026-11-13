---
name: testing-unit
description: How unit tests work in this repo (Vitest + Testing Library, jsdom): cleanup, queries, next/link, what's not installed. Load before writing or fixing unit tests.
when: vitest in package.json
---
# Unit tests here (verified by running them)

- Run: `run_tests` (Vitest, `pnpm test`). Config: `vitest.config.mts`, jsdom, `e2e/` excluded.
- Tests live in `__tests__/` next to the code (e.g. `src/app/__tests__/page.test.tsx`)
  and import `test`, `expect` from `vitest` explicitly.

## Cleanup is NOT automatic
Vitest globals are off, so Testing Library doesn't unmount between tests. Without
cleanup, the second test sees the first test's DOM ("found multiple elements").
Every test file that renders needs:
```tsx
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";
afterEach(cleanup);
```

## Share setup, don't copy it
- The same `render(...)` and first clicks in several tests: a small function at the top
  of the file (e.g. `function renderForm() { render(<Contact />); return screen; }`),
  or `beforeEach`. Each test holds only what it alone does and checks.
- Data the page shows (a list of questions, labels): export it from the code and import
  it in the test, instead of typing it again.

## next/link needs no mock
`<Link>` renders as a plain `<a href>` in jsdom, no router needed (checked). Don't mock
`next/link` and don't add a router provider:
```tsx
expect(screen.getByRole("link", { name: "About" }).getAttribute("href")).toBe("/about");
```

## No jest-dom
`@testing-library/jest-dom` isn't installed: `toBeInTheDocument`, `toHaveTextContent`
don't exist. Use what's there:
- presence: `screen.getByRole(...)` throws if missing; `expect(el).toBeDefined()`
- absence: `expect(screen.queryByText("Old")).toBeNull()`
- text: `expect(el.textContent).toBe("Like (2)")`
- attributes: `el.getAttribute("href")`

## Interactions
`fireEvent.click(button)` from `@testing-library/react` (user-event isn't installed).

## Server components
A synchronous server component renders directly: `render(<Home />)`. Layouts render
`<html><body>`: test the parts (e.g. a `Footer` component) instead of the whole layout.
