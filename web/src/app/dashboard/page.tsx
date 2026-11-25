import type { Metadata } from "next";
import { Suspense } from "react";

import { AppNav } from "@/components/app-nav";
import { Connected, Overview } from "@/components/dashboard";
import { SiteFooter } from "@/components/site";
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
      <main className="mx-auto max-w-6xl space-y-10 px-4 py-12">
        <header>
          <h1 className="font-display text-5xl leading-tight sm:text-6xl">Your runs</h1>
          <Suspense fallback={<p className="mt-2 h-6 w-96 animate-pulse rounded-lg bg-raised" />}>
            <Greeting />
          </Suspense>
        </header>
        <Overview start={<StartRun />} />
        <Connected />
      </main>
      <SiteFooter />
    </>
  );
}

async function Greeting() {
  const { user } = await verifySession();
  const first = user.name.trim().split(/\s+/)[0] || "there";
  return (
    <p className="mt-2 max-w-2xl text-muted">
      Welcome back, {first}. Every ticket you hand to the agents, and where it stands.
    </p>
  );
}
