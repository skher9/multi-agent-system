# Code quality rubric

<!-- DRAFT: in use for building the grader and reviewer; Shra reviews the wording. -->

How good is the code an agent's pull request adds? Five areas, each scored 1 to 10. The
examples come from real agent PRs on the demo repo (skher9/agent-playground).

**The bar:** every area 7 or more. Below 6 in any area, the PR goes back. Above 7 is
taste: say it as a suggestion, never as a reason to send the PR back.

What the numbers mean, in every area:

- **9-10:** a strong senior engineer would approve it as is and learn nothing from
  rewriting it.
- **7-8:** a senior would approve it. Any comments are "could also", not "must".
- **5-6:** works, but a senior would ask for changes before merging.
- **3-4:** works by luck, or only for the happy path. Several things need fixing.
- **1-2:** broken, unsafe, or not what the ticket asked for.

Score only what the PR adds or changes, against this repo's own patterns, not a style
the grader prefers. A small PR can score 9: size is not quality.

---

## 1. Correctness

Does it do what the ticket asks, including the cases a user will hit?

- **4:** The happy path works, but an obvious case doesn't: an empty field submits, a
  second click breaks it, an error isn't handled.
- **7:** Every acceptance criterion works, and so do the obvious edge cases (empty,
  invalid, repeated). A rarer case may be missed.
  *Example: KAN-4's contact form checks the email and shows a thank-you, but name and
  message can be empty, and the error stays once shown until the next submit.*
- **9:** Criteria and edge cases handled, and the code makes wrong states impossible
  rather than checking for them.
  *Example: KAN-13's not-found page: nothing left to go wrong.*

## 2. Tests

Do the tests prove the criteria, and will they catch a regression?

- **4:** Tests exist but check that things render, not that they behave. Or they'd pass
  with the feature broken.
- **7:** Each criterion has a test that fails if the behaviour breaks. Some repetition:
  the same setup copied into every test, or unit and browser tests checking the same
  thing.
  *Example: KAN-11's FAQ tests check each answer is hidden until clicked, but copy the
  four questions and answers into the test instead of sharing them with the page.*
- **9:** Each criterion and edge case tested once, at the right level (logic in unit
  tests, user flows in the browser), with shared setup and data. Test names read like
  the criteria.

## 3. Readability and structure

Can the next engineer understand and change it quickly?

- **4:** One long function or component doing several jobs; unclear names; logic
  repeated; dead code or leftover comments.
- **7:** Clear names, small functions, each file one job. Maybe one piece that could be
  split or simplified.
  *Example: KAN-11 splits the FAQ into a page (data) and an `FaqItem` (one question's
  open/closed state): clear, though the data could live in its own module.*
- **9:** Reads top to bottom with no surprises; the structure matches the problem; no
  line you'd remove.

## 4. Fits the repo

Does it look like the rest of this codebase was written by the same team?

- **4:** New patterns where the repo has one already (another way to style, fetch or
  test); new dependencies without need; files in unexpected places.
- **7:** Follows the repo's layout, naming, styling and test setup. One small
  inconsistency.
  *Example: the agent PRs use the starter's `p-8` / `text-2xl font-semibold` page
  pattern, `@/` imports and Testing Library setup, as the repo does.*
- **9:** Indistinguishable from the best existing code in the repo, and reuses what's
  already there instead of rebuilding it.

## 5. Robustness: errors, accessibility, security

Does it behave well when things go wrong, for every user?

- **4:** Errors swallowed or shown as raw messages; inputs without labels; user input
  trusted; secrets or unsafe HTML.
- **7:** Errors handled and shown in plain words; form fields labelled; keyboard works;
  input validated. A detail missing.
  *Example: KAN-4 labels every field and gives the email error `role="alert"`, but
  doesn't link the error to the field (`aria-describedby`, `aria-invalid`) or mark
  fields `required`.*
- **9:** All of the above, plus the details: errors tied to their fields, focus moved
  to what changed, nothing a user can type that breaks it.

---

## What the grader returns

For each area: a score, one sentence on why, and the change that would raise it by one
point (the most important one, not a list). Then:

- **must fix:** problems that put an area below 6. These go back to the developer.
- **suggestions:** everything else. These go on the PR as comments only.

The grader names the file and line for every point, and quotes the code. A point it
can't tie to a line doesn't count.
