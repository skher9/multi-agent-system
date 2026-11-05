import type { Metadata } from "next";
import { Suspense } from "react";

import { AppNav } from "@/components/app-nav";
import { RunsList } from "@/components/runs-list";
import { StartRun } from "@/components/start-run";
import { verifySession } from "@/lib/session";

export const metadata: Metadata = { title: "Dashboard" };

// The page frame is static and loads at once; the part that reads the login cookie
// streams in behind <Suspense> (required with Cache Components: a cookie read can't
// be prerendered).
export default function DashboardPage() {
  return (
    <>
      <AppNav />
      <main className="mx-auto max-w-6xl space-y-8 px-4 py-10">
        <Suspense fallback={<div className="h-9 w-64 animate-pulse rounded bg-surface" />}>
          <Greeting />
        </Suspense>
        <div className="grid gap-6 lg:grid-cols-[1fr_22rem]">
          <RunsList limit={5} />
          <StartRun />
        </div>
      </main>
    </>
  );
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
