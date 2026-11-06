import type { Metadata } from "next";
import { Suspense } from "react";

import { AppNav } from "@/components/app-nav";
import { SiteFooter } from "@/components/site";
import { SetupSteps } from "@/app/setup/setup-steps";
import { verifySession } from "@/lib/session";

export const metadata: Metadata = { title: "Use your own project" };

// Static frame; the login check and the steps stream in behind <Suspense>.
export default function SetupPage() {
  return (
    <>
      <AppNav />
      <main className="mx-auto max-w-2xl px-4 py-12">
        <h1 className="font-display text-5xl leading-tight">Use your own project</h1>
        <p className="mt-3 text-muted">
          Point the team at your Jira and your GitHub repo. Two steps, about five minutes. The demo
          project stays available either way.
        </p>
        <Suspense fallback={<div className="mt-8 h-96 animate-pulse rounded-lg bg-surface" />}>
          <Steps />
        </Suspense>
      </main>
      <SiteFooter />
    </>
  );
}

async function Steps() {
  await verifySession(); // sends visitors who aren't logged in to /login
  return <SetupSteps />;
}
