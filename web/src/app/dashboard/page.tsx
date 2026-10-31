import type { Metadata } from "next";

import { SignOutButton } from "@/components/sign-out-button";
import { verifySession } from "@/lib/session";

export const metadata: Metadata = { title: "Dashboard" };

export default async function DashboardPage() {
  const { user } = await verifySession(); // sends visitors who aren't logged in to /login
  return (
    <main className="mx-auto max-w-2xl space-y-6 p-8">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Hi, {user.name}</h1>
        <SignOutButton />
      </header>
      <p className="text-gray-600">
        You&apos;re logged in as {user.email}. Next: connect Jira and GitHub.
      </p>
    </main>
  );
}
