import type { Metadata } from "next";
import { Suspense } from "react";

import { LiveRun } from "@/components/run/live-run";
import { AppNav } from "@/components/app-nav";
import { SiteFooter } from "@/components/site";

export const metadata: Metadata = { title: "Live run" };

// The ticket comes from the address, so the live part renders in the browser.
export default function LiveRunPage() {
  return (
    <>
      <AppNav />
      <main className="mx-auto max-w-6xl space-y-4 px-4 py-10">
        <Suspense fallback={<p className="text-sm text-muted">Loading the run…</p>}>
          <LiveRun />
        </Suspense>
      </main>
      <SiteFooter />
    </>
  );
}
