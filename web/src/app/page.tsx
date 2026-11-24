import { ButtonLink, SiteFooter, SiteNav } from "@/components/site";
import { Card } from "@/components/ui/card";
import { Chip } from "@/components/ui/chip";
import type { Tone } from "@/components/ui/tone";
import { AGENTS, agentTone } from "@/lib/agents";

// Benchmark: the same 6 tickets on the same repo, before and after (docs in the repo)
const RESULTS: [before: string, after: string, label: string, tone: Tone][] = [
  ["5 of 6", "6 of 6", "tickets built correctly", "mint"],
  ["~50%", "~20%", "of tool calls wasted", "butter"],
  ["~15 min", "~4 min", "per ticket, before browser tests", "sky"],
];

const TRUST: [title: string, text: string, tone: Tone][] = [
  [
    "Checks no model can talk past",
    "Lint, typecheck, unit tests, placeholder and secret scans run in code. An agent can't finish until they pass.",
    "lilac",
  ],
  [
    "You stay in charge",
    "Pause any run to approve, revise or reject the plan before a line of code is written.",
    "peach",
  ],
  [
    "Locked-down sandbox",
    "Agent code runs in a throwaway machine with none of our keys and no internet except the npm registry.",
    "mint",
  ],
  [
    "Every step on the record",
    "Each agent's tool calls, reasoning and code are saved as it works, so you can watch a run live or replay it later.",
    "sky",
  ],
];

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
        <Chip tone="butter">Portfolio project · live demo</Chip>
        <h1 className="mt-6 font-display text-5xl leading-[1.02] text-balance sm:text-7xl">
          Seven AI agents that turn a ticket into a{" "}
          <mark className="rounded-xl bg-lilac px-2 text-ink">tested</mark> pull request.
        </h1>
        <p className="mt-6 max-w-xl text-lg leading-relaxed text-muted">
          Write a Jira ticket in plain words. The agents read it, plan it, write the code, prove it
          with real browser tests and open a reviewed pull request. You can watch every step.
        </p>
        <p className="mt-9 flex flex-wrap gap-3">
          <ButtonLink href="/signup">Try it with a ticket</ButtonLink>
          <ButtonLink href="/runs/sample" variant="ghost">
            Watch a real run
          </ButtonLink>
        </p>
      </div>
      <RunExcerpt />
    </section>
  );
}

const EXCERPT: [role: string, mark: string, text: string][] = [
  ["ticket_reader", "✓", "Spec ready: 4 acceptance criteria"],
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
    <Card as="aside" tone="sky" className="p-0! sm:p-0!" aria-label="A real run, as it happened">
      <header className="flex items-center justify-between gap-3 border-b-[1.5px] border-dashed border-ink/20 px-5 py-4">
        <h2 className="font-display text-lg">KAN-11 · Add an FAQ page</h2>
        <Chip tone="mint">
          <span aria-hidden className="size-2 animate-pulse rounded-full bg-ink" /> live
        </Chip>
      </header>
      <ol className="space-y-3 px-5 py-4 text-sm leading-snug">
        {EXCERPT.map(([role, mark, text]) => (
          <li key={text} className="grid grid-cols-[6.5rem_1rem_1fr] items-baseline gap-2">
            <Chip tone={agentTone(role)} className="justify-center">
              {AGENTS.find((agent) => agent.role === role)?.name}
            </Chip>
            <span
              aria-hidden
              className={mark === "✓" ? "text-ok" : mark === "!" ? "text-bad" : "text-muted"}
            >
              {mark}
            </span>
            <span className={mark === "~" ? "text-muted italic" : "font-mono text-[13px]"}>
              {text}
            </span>
          </li>
        ))}
      </ol>
    </Card>
  );
}

function Agents() {
  return (
    <section id="how" className="mx-auto max-w-6xl scroll-mt-24 px-4 py-20">
      <header className="max-w-2xl">
        <h2 className="font-display text-4xl leading-tight sm:text-5xl">
          One ticket, seven specialists.
        </h2>
        <p className="mt-4 leading-relaxed text-muted">
          Each agent does one job, gets only the tools that job needs, and hands its work to the
          next with the evidence attached.
        </p>
      </header>
      <ol className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {AGENTS.map((agent, i) => (
          <Card as="li" key={agent.role} tone={agent.tone} className="animate-rise">
            <p className="flex items-center gap-3">
              <span className="font-display text-2xl text-muted">{i + 1}</span>
              <Chip tone={agent.tone}>{agent.name}</Chip>
            </p>
            <p className="mt-4 leading-relaxed text-muted">{agent.job}</p>
          </Card>
        ))}
      </ol>
    </section>
  );
}

function Results() {
  return (
    <section id="results" className="mx-auto max-w-6xl scroll-mt-24 px-4 py-20">
      <header className="flex flex-wrap items-end justify-between gap-6">
        <h2 className="max-w-xl font-display text-4xl leading-tight sm:text-5xl">
          Measured, not promised.
        </h2>
        <p className="max-w-sm text-sm leading-relaxed text-muted">
          The same six tickets on the same repo, before and after the work on context, guardrails
          and model choice. The method and every round are in the repo.
        </p>
      </header>
      <dl className="mt-12 grid gap-6 sm:grid-cols-3">
        {RESULTS.map(([before, after, label, tone]) => (
          <Card as="div" key={label} tone={tone}>
            <dt className="text-xs font-semibold tracking-wider text-muted uppercase">{label}</dt>
            <dd className="mt-3 flex items-baseline gap-3">
              <span className="font-mono text-sm text-muted line-through">{before}</span>
              <span className="font-display text-5xl">{after}</span>
            </dd>
          </Card>
        ))}
      </dl>
    </section>
  );
}

function Trust() {
  return (
    <section className="mx-auto max-w-6xl px-4 py-20">
      <h2 className="max-w-2xl font-display text-4xl leading-tight sm:text-5xl">
        Built so the output can be trusted.
      </h2>
      <ul className="mt-12 grid gap-6 sm:grid-cols-2">
        {TRUST.map(([title, text, tone]) => (
          <Card as="li" key={title} tone={tone}>
            <h3 className="font-display text-xl">{title}</h3>
            <p className="mt-2 leading-relaxed text-muted">{text}</p>
          </Card>
        ))}
      </ul>
    </section>
  );
}

function Closing() {
  return (
    <section className="mx-auto max-w-6xl px-4 py-24">
      <Card tone="butter" className="px-6 py-14 text-center sm:px-12">
        <h2 className="font-display text-5xl leading-tight text-balance sm:text-6xl">
          Give it a ticket. Watch it ship.
        </h2>
        <p className="mx-auto mt-5 max-w-md text-muted">
          Sign up, pick a ticket for the demo repo and follow the agents live, from first read to
          pull request.
        </p>
        <p className="mt-9 flex flex-wrap justify-center gap-3">
          <ButtonLink href="/signup">Try it with a ticket</ButtonLink>
          <ButtonLink href="/runs/sample" variant="ghost">
            Watch a real run
          </ButtonLink>
        </p>
      </Card>
    </section>
  );
}
