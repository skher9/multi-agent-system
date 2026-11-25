# Results: what the agents cost, how good their code is, what broke

Measured on a fixed benchmark of real tickets against a Next.js starter repo
([`backend/experiments`](backend/experiments)). Every number below comes from a logged run;
where a number is from a single run, it says so.

**Headline:** cost per benchmark round fell from ₹102 to ₹5.73 (−94%) while correct
outcomes rose from 5/6 to 6/6. With the quality work added on top, 9 of 9 tickets reach a
pull request ready to merge, and an outside model rates 8 of the 9 at 7 or more out of 10
in every area.

## 1. Cost: ₹102 → ₹5.73 for the same six tickets

Same six tickets, same repo, one change at a time (QA off in these rounds, to measure the
other agents).

| Round         | What changed                                              | Correct | Cost    | Wasted tool calls (developer / planner / reviewer) |
| ------------- | --------------------------------------------------------- | ------- | ------- | -------------------------------------------------- |
| base-1        | Starting point: MiniMax M3, every agent starts blank      | 5/6     | ₹102.26 | 48% / 61% / 57%                                    |
| ctx-2         | Shared project context, guardrails in code                | 5/6     | ₹56.44  | 14% / 51% / 59%                                    |
| ds-v4.1-flash | Switched every agent to DeepSeek V4.1 Flash               | 6/6     | ₹10.59  | 26% / 45% / 50%                                    |
| final-2       | Repo skills, reasoning effort per role, given-files guard | 6/6     | ₹5.73   | 11% / 19% / 29%                                    |

A "wasted" call is one that bought nothing: re-reading an unchanged file, browsing library
docs, reading config the change doesn't touch, a shell `cat` instead of the read tool. The
report script classifies every call ([`experiments/report.py`](backend/experiments/report.py)).

Caveat: one run per setup. Model output varies between runs; repeated runs would give a
spread, not just a point.

## 2. Quality: graded by an outside model

Lint, tests and SonarQube said every pull request was fine: SonarQube Cloud gave all 8
DeepSeek PRs A/A/A with 0 issues. That can't tell a 7 from a 9, so a grader from another
model family (Claude Opus 5.5) scores each change 1–10 in five areas against a written
rubric ([`agents/rubric.md`](backend/agents/rubric.md)). Every point it makes must quote
real code, and our code checks the quote exists. The bar is 7 in every area.

| Ticket           | Correctness | Tests   | Readability | Fits the repo | Robustness | Meets bar  |
| ---------------- | ----------- | ------- | ----------- | ------------- | ---------- | ---------- |
| about-page       | 9           | 7       | 9           | 9             | 8          | ✅         |
| footer           | 8           | 7       | 8           | 8             | 7          | ✅         |
| heading-text     | 9           | 8       | 9           | 9             | 9          | ✅         |
| like-button      | 9           | 7       | 9           | 8             | 8          | ✅         |
| contact-api      | 7           | 8       | 8           | 8             | 6          | ❌         |
| todo-page        | 8           | 7       | 7           | 8             | 7          | ✅         |
| heading-refactor | 9           | 7       | 9           | 8             | 9          | ✅         |
| health-api       | 9           | 7       | 9           | 8             | 8          | ✅         |
| theme-toggle     | 8           | 8       | 8           | 8             | 7          | ✅         |
| **Average**      | **8.4**     | **7.3** | **8.4**     | **8.2**       | **7.7**    | **8 of 9** |

Round quality-3, 12 Nov 2026: 9 of 9 tickets ended ready to merge, ₹69.38 to build
(about ₹7.70 a ticket, QA on). Grading cost more than building: about ₹14 a ticket.

**Before the quality work** (rounds sonar-1/2, 8 tickets): 6 of 8 met the bar; averages
correctness 8.0, tests 7.1, readability 8.3, fits 7.8, robustness 7.5. The biggest single
change: health-api went from correctness 3 (a build break, below) to 9. Tests stay the
weakest area. contact-api misses on robustness: the happy path works, but a network
failure isn't handled and a malformed request returns 500.

## 3. What broke, and what fixed it

**The planner invented a login system.** The ticket said "use the existing login"; there
was none. The planner planned one and the developer wrote custom auth until the ₹50
budget ran out, with the prompt grown to ~100k tokens. The prompt already said "flag what
doesn't exist"; the model didn't apply it. Fix: the plan must list everything it relies on,
each with a file that proves it, checked in code. Now it stops at the planner for ₹1.15.
Lesson: structure beats instructions.

**Every agent started blank.** The same ~10 config files were read by the planner,
developer and reviewer on every ticket (~100 reads a round), plus ~110 reads of library
docs. Fix: one shared project context (code graph, repo facts, rules) and guardrails in
code. Developer waste fell from 48% to 11%.

**A "best practice" that backfired.** Clearing old tool results at ~20k tokens made the
developer re-read its own files and hit its budget. With 90%+ of the history cached,
resending it was cheap. Fix: clear only past ~60k tokens. Lesson: measure; advice depends
on caching.

**Hidden reasoning was the hidden cost.** Output was ~41% of spend, mostly reasoning
tokens. DeepSeek ignores a reasoning token limit but honours an effort setting: low effort
cut reasoning by 67% with an equally complete answer. Fix: effort set per role.

**A build break three checks missed.** One change added `export const dynamic =
"force-dynamic"`, which breaks the build in this repo. SonarQube gave it A/A/A, our gate
passed it (it didn't build the app then), and the reviewer approved it. The outside grader
scored correctness 3, and `pnpm build` failed exactly as it said. Fix: the gate now runs a
production build, and the reviewer moved to a stronger model with the same rubric.

**Tests copied their setup.** Graders kept marking tests down for repeated setup. Root
cause: agents imitate the repo's example test, and ours had its crash check written inside
the one test. Moving it into shared setup fixed what they copy, which beat telling them in
a prompt.

**The agent wasn't dumb, it was blind.** In the cloud sandbox, installed packages lived
only inside the sandbox, so the agent's file tools couldn't see them. The planner posted a
fake question on Jira because it couldn't confirm a library existed. Fix: library reads go
into the sandbox. Lesson: read the agent's thoughts before blaming the model.

**QA marked its own homework.** The QA agent used to report which tests passed. Fix: it
plans test cases first, writes one browser test per case, and pass or fail is read from
Playwright's own report. Every test is recorded on video, linked from the pull request.

**Laptops sleep.** A grading run hung for 4 hours on a socket when the Mac slept; a
benchmark sat for 3.5 hours with the lid closed on battery. Fix: save results after every
ticket, run under `caffeinate`, keep the charger in.

## 4. Real runs on the production path

Real Jira tickets, real GitHub pull requests, the production database and the cloud
sandbox, with QA testing each ticket on video.

| Ticket | What                      | Outcome                                                         | Notes                                                                            |
| ------ | ------------------------- | --------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| KAN-10 | Add a site footer         | ✅ PR [#13](https://github.com/skher9/agent-playground/pull/13) | 5 test cases, all passing, each with a video; QA added two edge cases on its own |
| KAN-13 | Add a page-not-found page | ✅ PR [#4](https://github.com/skher9/agent-playground/pull/4)   | Cloud sandbox end to end; the reviewer sent it back once                         |

What broke on the way: the first cloud-sandbox attempts stopped at planning with
`mkdir: cannot create directory '/graph': Permission denied`. Commands there never run as
root, and nothing created the folder the code graph is copied to. The sandbox image now
creates every folder the pipeline mounts, and a test fails if one is missing.

Two runs is a start, not a reliability number. The next step is a longer series.

## How to reproduce

```bash
cd backend
uv run python -m experiments.bench --round my-round        # all tickets, QA off
uv run python -m experiments.bench --round my-round --qa   # with QA and recordings
uv run python -m experiments.report my-round               # cost and waste per agent
uv run python -m experiments.grade my-round                # rubric grades
```

Needs the services in the README's "Run it locally" section and an OpenRouter key.
