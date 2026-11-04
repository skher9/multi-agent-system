import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { SignOutButton } from "@/components/sign-out-button";
import { SiteNav } from "@/components/site";
import { verifySession } from "@/lib/session";

export const metadata: Metadata = { title: "Dashboard" };

// The page frame is static and loads at once; the part that reads the login cookie
// streams in behind <Suspense> (required with Cache Components: a cookie read can't
// be prerendered).
export default function DashboardPage() {
  return (
    <>
      <SiteNav>
        <div className="ml-auto flex items-center gap-4">
          <Suspense>
            <UserEmail />
          </Suspense>
          <SignOutButton />
        </div>
      </SiteNav>
      <main className="mx-auto max-w-6xl space-y-8 px-4 py-10">
        <Suspense fallback={<div className="h-9 w-64 animate-pulse rounded bg-surface" />}>
          <Greeting />
        </Suspense>
        <div className="grid gap-6 lg:grid-cols-[1fr_22rem]">
          <RunsList />
          <StartRun />
        </div>
      </main>
    </>
  );
}

async function UserEmail() {
  const { user } = await verifySession(); // sends visitors who aren't logged in to /login
  return <span className="hidden text-sm text-muted sm:inline">{user.email}</span>;
}

async function Greeting() {
  const { user } = await verifySession();
  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight">Hi, {user.name}</h1>
      <p className="mt-1 text-muted">Your agent runs and what they&apos;re doing.</p>
    </div>
  );
}

const EXAMPLE = {
  ticket: "KAN-12",
  title: "Add a contact page",
  outcome: "Ready to merge",
  cost: "₹4.20",
  time: "3m 53s",
};

function RunsList() {
  return (
    <section className="rounded-2xl border border-line bg-surface">
      <header className="flex items-center justify-between border-b border-line px-5 py-4">
        <h2 className="font-medium">Runs</h2>
        <span className="text-xs text-muted">Newest first</span>
      </header>
      <ul className="divide-y divide-line">
        <li>
          <Link
            href="/runs/sample"
            className="flex flex-wrap items-center gap-x-4 gap-y-1 px-5 py-4 transition hover:bg-raised"
          >
            <span className="font-mono text-sm text-muted">{EXAMPLE.ticket}</span>
            <span className="font-medium">{EXAMPLE.title}</span>
            <span className="rounded-full border border-line px-2 py-0.5 text-xs text-muted">
              example
            </span>
            <span className="ml-auto flex items-center gap-4 text-sm text-muted">
              <span className="tabular-nums">{EXAMPLE.cost}</span>
              <span className="tabular-nums">{EXAMPLE.time}</span>
              <span className="flex items-center gap-1.5 text-accent">
                <span className="size-1.5 rounded-full bg-accent" />
                {EXAMPLE.outcome}
              </span>
            </span>
          </Link>
        </li>
      </ul>
      <p className="border-t border-line px-5 py-4 text-sm text-muted">
        Your own runs will show up here once you start one.
      </p>
    </section>
  );
}

function StartRun() {
  return (
    <section className="h-fit rounded-2xl border border-line bg-surface p-5">
      <h2 className="font-medium">Start a run</h2>
      <p className="mt-1 text-sm text-muted">
        Describe a small change to the demo repo. Agents take it from there.
      </p>
      <form className="mt-5 space-y-3">
        <input
          disabled
          placeholder="Title, e.g. Add a dark mode toggle"
          className="h-10 w-full rounded-lg border border-line bg-canvas px-3 text-sm placeholder:text-muted disabled:opacity-60"
        />
        <textarea
          disabled
          rows={4}
          placeholder="What should it do? One criterion per line."
          className="w-full resize-none rounded-lg border border-line bg-canvas px-3 py-2 text-sm placeholder:text-muted disabled:opacity-60"
        />
        <button
          type="button"
          disabled
          className="h-10 w-full rounded-lg bg-accent font-medium text-accent-ink opacity-50"
        >
          Start run
        </button>
      </form>
      <p className="mt-3 text-xs text-muted">Coming soon: the backend is being deployed.</p>
    </section>
  );
}
