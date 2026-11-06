"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

export type Run = components["schemas"]["RunSummary"];

const REFRESH_MS = 10_000;

/** The latest runs, newest first, refreshed every 10 seconds. null while loading. */
export function useRuns(): { runs: Run[] | null; error: boolean } {
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

  return { runs, error };
}

// How each feature status reads, and its colour
export const STATUS: Record<string, { label: string; tone: Tone }> = {
  running: { label: "Running", tone: "live" },
  in_review: { label: "In review", tone: "live" },
  waiting_for_plan_approval: { label: "Waiting for your approval", tone: "warn" },
  ready_to_merge: { label: "PR ready", tone: "good" },
  needs_human: { label: "Needs you", tone: "warn" },
  blocked: { label: "Questions on Jira", tone: "warn" },
  plan_rejected: { label: "Plan rejected", tone: "muted" },
  failed: { label: "Failed", tone: "bad" },
};
export type Tone = "live" | "good" | "warn" | "bad" | "muted";
export const TONE: Record<Tone, string> = {
  live: "text-accent",
  good: "text-ok",
  warn: "text-warn",
  bad: "text-bad",
  muted: "text-muted",
};

/** A run's page. Runs on the user's own project name it, since ticket keys can repeat
 * across Jira sites. */
export function runHref(run: { ticket: string; project_id: number; demo: boolean }): string {
  return run.demo ? `/runs/${run.ticket}` : `/runs/${run.ticket}?project=${run.project_id}`;
}

/** A stable key for lists: the same ticket key can exist on the demo and on your project. */
export function runKey(run: Run): string {
  return `${run.project_id}-${run.ticket}`;
}

export function statusOf(run: Run) {
  return STATUS[run.status] ?? { label: run.status.replaceAll("_", " "), tone: "muted" as const };
}

/** How long a run took (or has taken so far), e.g. "9 min". */
export function duration(run: Run): string {
  const ms = new Date(run.updated_at).getTime() - new Date(run.started_at).getTime();
  const minutes = Math.max(1, Math.round(ms / 60_000));
  return minutes < 60 ? `${minutes} min` : `${Math.floor(minutes / 60)} h ${minutes % 60} min`;
}

export function day(iso: string): string {
  return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}
