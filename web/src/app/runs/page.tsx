import type { Metadata } from "next";

import { AppNav } from "@/components/app-nav";
import { RunsList } from "@/components/runs-list";
import { SiteFooter } from "@/components/site";

export const metadata: Metadata = { title: "Runs" };

export default function RunsPage() {
  return (
    <>
      <AppNav />
      <main className="mx-auto max-w-6xl space-y-8 px-4 py-12">
        <div>
          <h1 className="font-display text-5xl leading-tight">Runs</h1>
          <p className="mt-1 text-muted">
            Every ticket the agents worked on: watch one, or open its pull request.
          </p>
        </div>
        <RunsList />
      </main>
      <SiteFooter />
    </>
  );
}
