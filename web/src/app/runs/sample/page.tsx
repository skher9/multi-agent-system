import type { Metadata } from "next";

import { RunWindow } from "@/components/run/run-window";
import { SiteFooter, SiteNav } from "@/components/site";
import { REPLAY_RUN } from "@/lib/runs/replay";

export const metadata: Metadata = { title: "Watch a run" };

export default function SampleRunPage() {
  return (
    <>
      <SiteNav />
      <main className="mx-auto max-w-6xl space-y-4 px-4 py-10">
        <p className="text-sm text-muted">
          A real run of the agents on a benchmark ticket, replayed fast. Every step, every line of
          code and every test video is what they actually did.
        </p>
        <RunWindow run={REPLAY_RUN} replay />
      </main>
      <SiteFooter />
    </>
  );
}
