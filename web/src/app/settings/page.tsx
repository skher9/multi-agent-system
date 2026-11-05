import type { Metadata } from "next";
import { Suspense } from "react";

import { AppNav } from "@/components/app-nav";
import { DeleteAccount } from "@/components/delete-account";
import { verifySession } from "@/lib/session";

export const metadata: Metadata = { title: "Settings" };

// Same shape as the dashboard: a static frame, the session-reading part behind <Suspense>.
export default function SettingsPage() {
  return (
    <>
      <AppNav />
      <main className="mx-auto max-w-2xl space-y-6 px-4 py-10">
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <Suspense fallback={<div className="h-28 animate-pulse rounded-2xl bg-surface" />}>
          <Account />
        </Suspense>
        <section className="rounded-2xl border border-red-500/30 bg-surface p-6">
          <h2 className="font-medium">Delete account</h2>
          <p className="mt-1 mb-4 text-sm text-muted">
            Removes your account, your logins and your sessions from our database.
          </p>
          <DeleteAccount />
        </section>
      </main>
    </>
  );
}

async function Account() {
  const { user } = await verifySession(); // sends visitors who aren't logged in to /login
  return (
    <section className="rounded-2xl border border-line bg-surface p-6">
      <h2 className="font-medium">Account</h2>
      <dl className="mt-4 grid grid-cols-[6rem_1fr] gap-y-2 text-sm">
        <dt className="text-muted">Name</dt>
        <dd>{user.name}</dd>
        <dt className="text-muted">Email</dt>
        <dd className="break-all">{user.email}</dd>
      </dl>
    </section>
  );
}
