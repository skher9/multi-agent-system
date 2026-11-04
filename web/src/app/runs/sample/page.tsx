import type { Metadata } from "next";

import { RunWindow } from "@/components/run/run-window";
import { SiteFooter, SiteNav } from "@/components/site";
import { SAMPLE_RUN } from "@/lib/runs/sample";

export const metadata: Metadata = { title: "Watch a run" };

export default function SampleRunPage() {
  return (
    <>
      <SiteNav />
      <main className="mx-auto max-w-6xl space-y-4 px-4 py-10">
        <p className="text-sm text-muted">
          An example run with made-up data, replayed fast, to show what a live run looks like.
        </p>
        <RunWindow run={SAMPLE_RUN} replay />
      </main>
      <SiteFooter />
    </>
  );
}
