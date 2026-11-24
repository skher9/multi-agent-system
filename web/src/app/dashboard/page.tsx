import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { AppNav } from "@/components/app-nav";
import { Card } from "@/components/ui/card";
import { Chip } from "@/components/ui/chip";
import { Overview, OwnProjectCard } from "@/components/dashboard";
import { SiteFooter } from "@/components/site";
import { StartRun } from "@/components/start-run";
import { AGENTS } from "@/lib/agents";
import { verifySession } from "@/lib/session";

export const metadata: Metadata = { title: "Dashboard" };

const TIPS = [
  "One change per ticket: a page, a component, an endpoint.",
  "List what must be true when it's done, as acceptance criteria.",
  'Say what to reuse ("use the existing Button") and what not to touch.',
  "Building a screen? Add the Figma frame link.",
];

// The page frame is static and loads at once; the part that reads the login cookie
// streams in behind <Suspense> (required with Cache Components: a cookie read can't
// be prerendered).
export default function DashboardPage() {
  return (
    <>
      <AppNav />
      <main className="mx-auto max-w-6xl px-4 py-12">
        <Suspense fallback={<div className="h-20 w-80 animate-pulse rounded-2xl bg-raised" />}>
          <Greeting />
        </Suspense>
        {/* Phones: runs, then Start run, then the team. Wide screens: the aside spans
            both rows on the right. */}
        <div className="mt-10 grid gap-10 lg:grid-cols-[1fr_22rem] lg:grid-rows-[auto_1fr] lg:items-start">
          <Overview />
          <aside className="space-y-6 lg:col-start-2 lg:row-span-2 lg:row-start-1">
            <StartRun />
            <OwnProjectCard />
            <Card tone="lime">
              <h2 className="font-display text-xl">Writing a good ticket</h2>
              <ul className="mt-3 space-y-2 text-sm text-muted">
                {TIPS.map((tip) => (
                  <li key={tip} className="flex gap-2">
                    <span aria-hidden className="font-bold">
                      ✓
                    </span>
                    {tip}
                  </li>
                ))}
              </ul>
            </Card>
          </aside>
          <Team />
        </div>
      </main>
      <SiteFooter />
    </>
  );
}

async function Greeting() {
  const { user } = await verifySession();
  const first = user.name.trim().split(/\s+/)[0] || "there";
  return (
    <div>
      <h1 className="font-display text-5xl leading-tight sm:text-6xl">Welcome back, {first}.</h1>
      <p className="mt-2 max-w-2xl text-muted">
        Your AI dev team turns Jira tickets into tested, reviewed pull requests. Try it on the demo
        repo, or connect your own Jira and GitHub, then give it a ticket and watch it work.
      </p>
    </div>
  );
}

/** What happens to a ticket, at a glance. */
function Team() {
  return (
    <section className="lg:col-start-1">
      <h2 className="font-display text-2xl">How your team works</h2>
      <ol className="mt-5 flex flex-wrap items-center gap-x-3 gap-y-3 text-sm">
        {AGENTS.map((agent, i) => (
          <li key={agent.role} className="flex items-center gap-3">
            <Chip tone={agent.tone} className="text-sm">
              {agent.name}
            </Chip>
            {i < AGENTS.length - 1 && (
              <span aria-hidden className="text-muted">
                →
              </span>
            )}
          </li>
        ))}
      </ol>
      <p className="mt-4 max-w-2xl text-sm text-muted">
        Each agent has one job and only the tools for it. Checks run in code between them, so no
        agent can skip a failing test.{" "}
        <Link href="/#how" className="text-ink underline underline-offset-4">
          What each one does
        </Link>
      </p>
    </section>
  );
}
