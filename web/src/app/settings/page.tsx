import type { Metadata } from "next";
import { headers } from "next/headers";
import { Suspense } from "react";

import { AppNav } from "@/components/app-nav";
import { type Connection, Connections } from "@/components/connections";
import { DeleteAccount } from "@/components/delete-account";
import { OwnProject } from "@/components/own-project";
import { Card } from "@/components/ui/card";
import { auth, enabledProviders } from "@/lib/auth";
import { verifySession } from "@/lib/session";

export const metadata: Metadata = { title: "Settings" };

// Same shape as the dashboard: a static frame, the session-reading part behind <Suspense>.
export default function SettingsPage() {
  return (
    <>
      <AppNav />
      <main className="mx-auto max-w-3xl space-y-8 px-4 py-12">
        <header>
          <h1 className="font-display text-5xl leading-tight sm:text-6xl">Settings</h1>
          <p className="mt-2 text-muted">Who you are, how you log in, and where the agents work.</p>
        </header>
        <Suspense fallback={<div className="h-28 animate-pulse rounded-3xl bg-raised" />}>
          <Account />
        </Suspense>
        <Suspense fallback={<div className="h-40 animate-pulse rounded-3xl bg-raised" />}>
          <ConnectedAccounts />
        </Suspense>
        <Card id="project" tone="mint" className="scroll-mt-24">
          <h2 className="font-display text-2xl">Your project</h2>
          <p className="mt-1 mb-4 text-sm text-muted">
            The Jira and GitHub agents work on when you pick your own project. Tokens are checked,
            then stored encrypted; nobody else can see your runs.
          </p>
          <OwnProject />
        </Card>
        <Card tone="rose">
          <h2 className="font-display text-2xl">Delete account</h2>
          <p className="mt-1 mb-4 text-sm text-muted">
            Removes your account, your logins, your sessions and your Jira and GitHub tokens from
            our database.
          </p>
          <DeleteAccount />
        </Card>
      </main>
    </>
  );
}

async function Account() {
  const { user } = await verifySession(); // sends visitors who aren't logged in to /login
  return (
    <Card tone="lilac">
      <h2 className="font-display text-2xl">Account</h2>
      <dl className="mt-4 grid grid-cols-[6rem_1fr] gap-y-2 text-sm">
        <dt className="text-muted">Name</dt>
        <dd>{user.name}</dd>
        <dt className="text-muted">Email</dt>
        <dd className="break-all">{user.email}</dd>
      </dl>
    </Card>
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
    <Card tone="sky">
      <h2 className="font-display text-2xl">Connected accounts</h2>
      <p className="mt-1 mb-4 text-sm text-muted">
        How you log in. Disconnecting removes our access at Google or GitHub too, not just here.
      </p>
      <Connections
        connections={connections}
        hasPassword={accounts.some((a) => a.providerId === "credential")}
      />
    </Card>
  );
}
