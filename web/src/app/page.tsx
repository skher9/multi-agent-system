import { ButtonLink, SiteFooter, SiteNav } from "@/components/site";

const STEPS = [
  {
    n: "01",
    title: "Write a Jira ticket",
    text: "Plain words and acceptance criteria. Vague ticket? The reader agent asks questions on it instead of guessing.",
  },
  {
    n: "02",
    title: "Agents plan the work",
    text: "The planner reads the repo, splits the ticket into subtasks in Jira, and can wait for your OK first.",
  },
  {
    n: "03",
    title: "They build and prove it",
    text: "A developer agent codes each subtask in a sandbox. Lint, types, unit tests and real browser tests must pass.",
  },
  {
    n: "04",
    title: "You get a reviewed PR",
    text: "A reviewer agent checks every criterion, a fixer handles its comments, and the PR shows the evidence.",
  },
];

const FEATURES = [
  {
    title: "Verify box",
    text: "A gate no model can talk past: lint, typecheck, unit tests, placeholder and secret scans, then Playwright tests per criterion.",
  },
  {
    title: "Live window",
    text: "Watch each agent think, read files, edit code and run tests as it happens.",
  },
  {
    title: "Plan approval",
    text: "Approve, revise or reject the plan before any code is written.",
  },
  {
    title: "Learns from reviews",
    text: "Comments you leave on merged PRs become repo rules every agent follows next time.",
  },
  {
    title: "Asks a senior",
    text: "Stuck agents can ask a stronger model for advice, at most twice per task.",
  },
  {
    title: "Cost in ₹",
    text: "Every model call is metered. A typical ticket costs about ₹5 to ₹15.",
  },
];

export default function Home() {
  return (
    <>
      <SiteNav />
      <main>
        <Hero />
        <section id="how" className="mx-auto max-w-6xl scroll-mt-20 px-4 py-24">
          <SectionTitle kicker="How it works" title="From ticket to pull request, on its own" />
          <ol className="mt-12 grid gap-px overflow-hidden rounded-2xl border border-line bg-line sm:grid-cols-2 lg:grid-cols-4">
            {STEPS.map((step) => (
              <li key={step.n} className="bg-surface p-6">
                <span className="font-mono text-sm text-accent">{step.n}</span>
                <h3 className="mt-3 font-medium">{step.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-muted">{step.text}</p>
              </li>
            ))}
          </ol>
        </section>

        <section className="mx-auto max-w-6xl px-4 pb-24">
          <SectionTitle kicker="What's inside" title="Built so the output can be trusted" />
          <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((feature) => (
              <div
                key={feature.title}
                className="rounded-2xl border border-line bg-surface p-6 transition hover:border-muted/50"
              >
                <h3 className="font-medium">{feature.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-muted">{feature.text}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-4 pb-24">
          <div className="relative overflow-hidden rounded-3xl border border-line bg-surface px-6 py-16 text-center">
            <Glow />
            <h2 className="relative text-3xl font-semibold tracking-tight sm:text-4xl">
              Give it a ticket. Watch it ship.
            </h2>
            <p className="relative mx-auto mt-4 max-w-md text-muted">
              Sign up, write a small ticket for the demo repo, and follow the agents live.
            </p>
            <div className="relative mt-8 flex justify-center gap-3">
              <ButtonLink href="/signup">Try it live →</ButtonLink>
              <ButtonLink href="/runs/sample" variant="ghost">
                Watch a run
              </ButtonLink>
            </div>
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}

function Hero() {
  return (
    <section className="relative overflow-hidden">
      <Glow />
      <div className="relative mx-auto grid max-w-6xl items-center gap-12 px-4 pt-20 pb-24 lg:grid-cols-[1.1fr_1fr] lg:pt-28">
        <div>
          <p className="inline-flex items-center gap-2 rounded-full border border-line bg-surface px-3 py-1 text-xs text-muted">
            <span className="size-1.5 rounded-full bg-accent" /> Seven AI agents, one pipeline
          </p>
          <h1 className="mt-6 text-4xl font-semibold tracking-tight text-balance sm:text-6xl">
            An AI dev team that turns tickets into <span className="text-accent">tested PRs</span>
          </h1>
          <p className="mt-6 max-w-xl text-lg leading-relaxed text-muted">
            Write a Jira ticket. Agents read it, plan it, write the code, prove it with real browser
            tests, and open a reviewed pull request.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <ButtonLink href="/signup">Try it live →</ButtonLink>
            <ButtonLink href="/runs/sample" variant="ghost">
              Watch a run
            </ButtonLink>
          </div>
        </div>
        <RunPreview />
      </div>
    </section>
  );
}

const PREVIEW_STAGES: [string, "done" | "running" | "waiting"][] = [
  ["Reader", "done"],
  ["Planner", "done"],
  ["Developer", "running"],
  ["Verify", "waiting"],
  ["PR + review", "waiting"],
];

const PREVIEW_FEED = [
  ["planner", "💭", "No form library here. Two subtasks: page, then form."],
  ["developer", "🔧", "Created src/app/contact/page.tsx"],
  ["developer", "🔧", "Ran the unit tests"],
  ["developer", "⚠️", "Tests failed: 'Thanks!' not visible. Fixing."],
  ["developer", "💭", "Show the thank-you from state."],
];

/** A still picture of the run window, so the hero shows the product at a glance. */
function RunPreview() {
  return (
    <div className="rounded-2xl border border-line bg-surface shadow-2xl shadow-black/50">
      <div className="flex items-center gap-2 border-b border-line px-4 py-3">
        <span className="size-2.5 rounded-full bg-line" />
        <span className="size-2.5 rounded-full bg-line" />
        <span className="size-2.5 rounded-full bg-line" />
        <span className="ml-3 font-mono text-xs text-muted">KAN-12 · Add a contact page</span>
        <span className="ml-auto font-mono text-xs text-accent">● live</span>
      </div>
      <div className="grid gap-4 p-4 sm:grid-cols-[9rem_1fr]">
        <ol className="space-y-1.5 text-sm">
          {PREVIEW_STAGES.map(([name, status]) => (
            <li
              key={name}
              className={`flex items-center gap-2 rounded-md border px-2.5 py-1.5 ${
                status === "running"
                  ? "border-accent/60 bg-accent/10 text-ink"
                  : status === "done"
                    ? "border-line text-ink"
                    : "border-line/60 text-muted/60"
              }`}
            >
              <span
                className={
                  status === "running"
                    ? "animate-pulse text-accent"
                    : status === "done"
                      ? "text-accent"
                      : ""
                }
              >
                {status === "done" ? "✓" : status === "running" ? "●" : "○"}
              </span>
              {name}
            </li>
          ))}
        </ol>
        <ul className="space-y-2 font-mono text-xs">
          {PREVIEW_FEED.map(([role, icon, text]) => (
            <li key={text} className="flex gap-2">
              <span aria-hidden>{icon}</span>
              <span>
                <span className="text-accent">{role}</span>{" "}
                <span className="text-muted">{text}</span>
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function SectionTitle({ kicker, title }: { kicker: string; title: string }) {
  return (
    <div className="max-w-2xl">
      <p className="font-mono text-sm text-accent">{kicker}</p>
      <h2 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">{title}</h2>
    </div>
  );
}

function Glow() {
  return (
    <div
      aria-hidden
      className="pointer-events-none absolute inset-x-0 -top-40 mx-auto h-80 max-w-3xl rounded-full bg-accent/15 blur-3xl"
    />
  );
}
