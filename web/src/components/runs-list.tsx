"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { api } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

type Run = components["schemas"]["RunSummary"];

const REFRESH_MS = 10_000;

// How each feature status reads, and its colour
const STATUS: Record<string, { label: string; tone: "live" | "good" | "warn" | "bad" | "muted" }> =
  {
    running: { label: "Running", tone: "live" },
    in_review: { label: "In review", tone: "live" },
    waiting_for_plan_approval: { label: "Waiting for your approval", tone: "warn" },
    ready_to_merge: { label: "PR ready", tone: "good" },
    needs_human: { label: "Needs you", tone: "warn" },
    blocked: { label: "Questions on Jira", tone: "warn" },
    plan_rejected: { label: "Plan rejected", tone: "muted" },
    failed: { label: "Failed", tone: "bad" },
  };
const TONE = {
  live: "text-accent",
  good: "text-accent",
  warn: "text-amber-300",
  bad: "text-red-400",
  muted: "text-muted",
};

/** The latest runs, newest first, refreshed every 10 seconds. With limit, a short
 * list with a link to all runs (the dashboard); without, the full list (/runs). */
export function RunsList({ limit }: { limit?: number }) {
  const [runs, setRuns] = useState<Run[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      const { data } = await api.GET("/runs");
      if (cancelled) return;
      if (data) {
        setRuns(data);
        setError(false);
      } else setError(true);
    }
    load();
    const timer = setInterval(load, REFRESH_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  return (
    <section className="rounded-2xl border border-line bg-surface">
      <header className="flex items-center justify-between border-b border-line px-5 py-4">
        <h2 className="font-medium">{limit ? "Recent runs" : "All runs"}</h2>
        {limit ? (
          <Link href="/runs" className="text-sm text-muted hover:text-ink">
            View all runs →
          </Link>
        ) : (
          <span className="text-xs text-muted">Newest first</span>
        )}
      </header>
      {runs === null && !error && <p className="px-5 py-4 text-sm text-muted">Loading runs…</p>}
      {error && (
        <p className="px-5 py-4 text-sm text-red-400">Couldn&apos;t load runs. Retrying…</p>
      )}
      {runs?.length === 0 && (
        <p className="px-5 py-4 text-sm text-muted">
          No runs yet. Start one, or{" "}
          <Link href="/runs/sample" className="text-ink underline-offset-4 hover:underline">
            watch an example
          </Link>
          .
        </p>
      )}
      <ul className="divide-y divide-line">
        {runs?.slice(0, limit).map((run) => {
          const status = STATUS[run.status] ?? { label: run.status, tone: "muted" as const };
          return (
            <li
              key={run.ticket}
              className="flex flex-wrap items-center gap-x-4 gap-y-2 px-5 py-4 transition hover:bg-raised"
            >
              <Link href={`/runs/${run.ticket}`} className="flex min-w-0 items-center gap-3">
                <span className="font-mono text-sm text-muted">{run.ticket}</span>
                <span className="truncate font-medium">{run.title || run.ticket}</span>
              </Link>
              <span className="ml-auto flex items-center gap-4 text-sm text-muted">
                <span className="tabular-nums">₹{run.cost_inr.toFixed(2)}</span>
                <span className={`flex items-center gap-1.5 ${TONE[status.tone]}`}>
                  <span
                    className={`size-1.5 rounded-full bg-current ${status.tone === "live" ? "animate-pulse" : ""}`}
                  />
                  {status.label}
                </span>
                <Link href={`/runs/${run.ticket}`} className="hover:text-ink">
                  Watch
                </Link>
                {run.pr_url && (
                  <a
                    href={run.pr_url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-ink hover:underline"
                  >
                    PR ↗
                  </a>
                )}
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
