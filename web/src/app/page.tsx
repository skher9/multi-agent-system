import { ButtonLink, SiteFooter, SiteNav } from "@/components/site";

// The seven agents, in the order a ticket meets them
const AGENTS = [
  [
    "Reader",
    "Turns the ticket into a spec. If it's vague, asks questions on Jira instead of guessing.",
  ],
  [
    "Planner",
    "Reads the repo through a code map and plans every file change, criterion by criterion.",
  ],
  [
    "Developer",
    "Builds each subtask in a sandbox. Lint, types and unit tests must pass before it can stop.",
  ],
  ["Fixer", "Takes whatever the final checks still catch and fixes exactly that."],
  ["QA", "Writes real browser tests, one or more per acceptance criterion, and runs them."],
  [
    "Reviewer",
    "Reads the diff like a senior engineer and sends it back with comments when it isn't right.",
  ],
  ["Learner", "Turns your comments on merged PRs into rules every agent follows next time."],
] as const;

// Benchmark: the same 6 tickets on the same repo, before and after (docs in the repo)
const RESULTS = [
  ["5 of 6", "6 of 6", "tickets built correctly"],
  ["~50%", "~20%", "of tool calls wasted"],
  ["~15 min", "~4 min", "per ticket, before browser tests"],
] as const;

const TRUST = [
  [
    "Checks no model can talk past",
    "Lint, typecheck, unit tests, placeholder and secret scans run in code. An agent can't finish until they pass.",
  ],
  [
    "You stay in charge",
    "Pause any run to approve, revise or reject the plan before a line of code is written.",
  ],
  [
    "Locked-down sandbox",
    "Agent code runs in a throwaway machine with none of our keys and no internet except the npm registry.",
  ],
  [
    "Every step on the record",
    "Each agent's tool calls, reasoning and code are saved as it works, so you can watch a run live or replay it later.",
  ],
] as const;

export default function Home() {
  return (
    <>
      <SiteNav />
      <main>
        <Hero />
        <Agents />
        <Results />
        <Trust />
        <Closing />
      </main>
      <SiteFooter />
    </>
  );
}

function Hero() {
  return (
    <section className="mx-auto grid max-w-6xl gap-14 px-4 pt-16 pb-24 lg:grid-cols-[1.15fr_1fr] lg:items-end lg:pt-24">
      <div>
        <p className="font-mono text-xs tracking-wide text-muted uppercase">
          Portfolio project · live demo
        </p>
        <h1 className="mt-6 font-display text-5xl leading-[1.02] text-balance sm:text-7xl">
          Seven AI agents that turn a ticket into a <em className="text-accent">tested</em> pull
          request.
        </h1>
        <p className="mt-6 max-w-xl text-lg leading-relaxed text-muted">
          Write a Jira ticket in plain words. The agents read it, plan it, write the code, prove it
          with real browser tests and open a reviewed pull request. You can watch every step.
        </p>
        <div className="mt-9 flex flex-wrap gap-3">
          <ButtonLink href="/signup">Try it with a ticket</ButtonLink>
          <ButtonLink href="/runs/sample" variant="ghost">
            Watch a real run
          </ButtonLink>
        </div>
      </div>
      <RunExcerpt />
    </section>
  );
}

const EXCERPT: [string, string, string][] = [
  ["reader", "✓", "Spec ready: 4 acceptance criteria"],
  ["planner", "~", "No accordion component here. One page, one test file, a home link."],
  ["developer", "→", "Created src/app/faq/page.tsx"],
  ["developer", "!", "Test failed: answer still visible after second click"],
  ["developer", "~", "Track the open question in state; clicking it again closes it."],
  ["developer", "✓", "Lint, types and 9 unit tests pass"],
  ["qa", "✓", "4 browser tests pass, one per criterion"],
];

/** A page from a real run's log, so the hero shows the product, not a promise. */
function RunExcerpt() {
  return (
    <figure className="rounded-lg border border-line bg-surface shadow-[0_24px_60px_-30px_rgb(27_25_21/0.35)]">
      <figcaption className="flex items-baseline justify-between border-b border-line px-5 py-3">
        <span className="font-display text-lg">KAN-11 · Add an FAQ page</span>
        <span className="flex items-center gap-1.5 font-mono text-xs text-accent">
          <span className="size-1.5 animate-pulse rounded-full bg-current" /> live
        </span>
      </figcaption>
      <ol className="space-y-2.5 px-5 py-4 font-mono text-[13px] leading-snug">
        {EXCERPT.map(([role, mark, text]) => (
          <li key={text} className="grid grid-cols-[5.5rem_1rem_1fr] gap-2">
            <span className="text-muted">{role}</span>
            <span
              aria-hidden
              className={mark === "✓" ? "text-ok" : mark === "!" ? "text-bad" : "text-muted"}
            >
              {mark}
            </span>
            <span className={mark === "~" ? "text-muted italic" : ""}>{text}</span>
          </li>
        ))}
      </ol>
    </figure>
  );
}

function Agents() {
  return (
    <section id="how" className="scroll-mt-20 border-t border-line">
      <div className="mx-auto grid max-w-6xl gap-12 px-4 py-20 lg:grid-cols-[1fr_1.6fr]">
        <div>
          <h2 className="font-display text-4xl leading-tight sm:text-5xl">
            One ticket, <em>seven</em> specialists.
          </h2>
          <p className="mt-5 max-w-sm leading-relaxed text-muted">
            Each agent does one job, gets only the tools that job needs, and hands its work to the
            next with the evidence attached.
          </p>
        </div>
        <ol className="divide-y divide-line border-y border-line">
          {AGENTS.map(([name, text], i) => (
            <li
              key={name}
              className="grid grid-cols-[2rem_1fr] items-baseline gap-x-4 gap-y-1 py-5 sm:grid-cols-[2.5rem_7rem_1fr]"
            >
              <span className="font-display text-2xl text-muted">{i + 1}</span>
              <span className="font-medium">{name}</span>
              <span className="col-start-2 leading-relaxed text-muted sm:col-start-3">{text}</span>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

function Results() {
  return (
    <section id="results" className="scroll-mt-20 border-t border-line bg-surface">
      <div className="mx-auto max-w-6xl px-4 py-20">
        <div className="flex flex-wrap items-end justify-between gap-6">
          <h2 className="max-w-xl font-display text-4xl leading-tight sm:text-5xl">
            Measured, not promised.
          </h2>
          <p className="max-w-sm text-sm leading-relaxed text-muted">
            The same six tickets on the same repo, before and after the work on context, guardrails
            and model choice. One run per setup so far; the method and every round are in the repo.
          </p>
        </div>
        <dl className="mt-14 grid gap-px overflow-hidden rounded-lg border border-line bg-line sm:grid-cols-3">
          {RESULTS.map(([before, after, label]) => (
            <div key={label} className="bg-canvas p-6">
              <dt className="text-sm text-muted">{label}</dt>
              <dd className="mt-4 flex items-baseline gap-3">
                <span className="font-mono text-sm text-muted line-through decoration-muted/60">
                  {before}
                </span>
                <span className="font-display text-5xl">{after}</span>
              </dd>
            </div>
          ))}
        </dl>
      </div>
    </section>
  );
}

function Trust() {
  return (
    <section className="border-t border-line">
      <div className="mx-auto max-w-6xl px-4 py-20">
        <h2 className="max-w-2xl font-display text-4xl leading-tight sm:text-5xl">
          Built so the output can be <em>trusted</em>.
        </h2>
        <div className="mt-12 grid gap-x-12 gap-y-10 sm:grid-cols-2">
          {TRUST.map(([title, text]) => (
            <div key={title} className="border-t border-ink/80 pt-5">
              <h3 className="font-medium">{title}</h3>
              <p className="mt-2 leading-relaxed text-muted">{text}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function Closing() {
  return (
    <section className="border-t border-line">
      <div className="mx-auto max-w-6xl px-4 py-24 text-center">
        <h2 className="font-display text-5xl leading-tight text-balance sm:text-6xl">
          Give it a ticket. <em className="text-accent">Watch it ship.</em>
        </h2>
        <p className="mx-auto mt-5 max-w-md text-muted">
          Sign up, pick a ticket for the demo repo and follow the agents live, from first read to
          pull request.
        </p>
        <div className="mt-9 flex justify-center gap-3">
          <ButtonLink href="/signup">Try it with a ticket</ButtonLink>
          <ButtonLink href="/runs/sample" variant="ghost">
            Watch a real run
          </ButtonLink>
        </div>
      </div>
    </section>
  );
}
