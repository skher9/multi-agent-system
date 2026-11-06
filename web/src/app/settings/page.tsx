import type { Metadata } from "next";
import { headers } from "next/headers";
import { Suspense } from "react";

import { AppNav } from "@/components/app-nav";
import { type Connection, Connections } from "@/components/connections";
import { DeleteAccount } from "@/components/delete-account";
import { auth, enabledProviders } from "@/lib/auth";
import { verifySession } from "@/lib/session";

export const metadata: Metadata = { title: "Settings" };

// Same shape as the dashboard: a static frame, the session-reading part behind <Suspense>.
export default function SettingsPage() {
  return (
    <>
      <AppNav />
      <main className="mx-auto max-w-2xl space-y-6 px-4 py-10">
        <h1 className="font-display text-5xl leading-tight">Settings</h1>
        <Suspense fallback={<div className="h-28 animate-pulse rounded-lg bg-surface" />}>
          <Account />
        </Suspense>
        <Suspense fallback={<div className="h-40 animate-pulse rounded-lg bg-surface" />}>
          <ConnectedAccounts />
        </Suspense>
        <section className="rounded-lg border border-bad/30 bg-surface p-6">
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
    <section className="rounded-lg border border-line bg-surface p-6">
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

/** The ways this user logs in, and what they've let us access. */
async function ConnectedAccounts() {
  await verifySession();
  const accounts = await auth.api.listUserAccounts({ headers: await headers() });
  const connections: Connection[] = enabledProviders().map((provider) => {
    const account = accounts.find((a) => a.providerId === provider);
    return {
      provider,
      accountId: account?.id ?? null,
      since: account ? new Date(account.createdAt).toISOString() : null,
    };
  });
  return (
    <section className="rounded-lg border border-line bg-surface p-6">
      <h2 className="font-medium">Connected accounts</h2>
      <p className="mt-1 mb-4 text-sm text-muted">
        How you log in. Disconnecting removes our access at Google or GitHub too, not just here.
      </p>
      <Connections
        connections={connections}
        hasPassword={accounts.some((a) => a.providerId === "credential")}
      />
    </section>
  );
}
