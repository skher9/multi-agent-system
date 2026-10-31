import type { Metadata } from "next";
import { Suspense } from "react";

import { SignOutButton } from "@/components/sign-out-button";
import { verifySession } from "@/lib/session";

export const metadata: Metadata = { title: "Dashboard" };

// The page frame is static and loads at once; the part that reads the login cookie
// streams in behind <Suspense> (required with Cache Components: a cookie read can't
// be prerendered).
export default function DashboardPage() {
  return (
    <main className="mx-auto max-w-2xl space-y-6 p-8">
      <Suspense fallback={<p className="text-gray-500">Loading your dashboard…</p>}>
        <Welcome />
      </Suspense>
    </main>
  );
}

async function Welcome() {
  const { user } = await verifySession(); // sends visitors who aren't logged in to /login
  return (
    <>
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Hi, {user.name}</h1>
        <SignOutButton />
      </header>
      <p className="text-gray-600">
        You&apos;re logged in as {user.email}. Next: connect Jira and GitHub.
      </p>
    </>
  );
}
