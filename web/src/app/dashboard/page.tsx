import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { SignOutButton } from "@/components/sign-out-button";
import { RunsList } from "@/components/runs-list";
import { StartRun } from "@/components/start-run";
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
          <Link href="/settings" className="text-sm text-muted hover:text-ink">
            Settings
          </Link>
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
