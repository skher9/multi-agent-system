"use client";

import { useEffect, useState } from "react";

import type { Tone } from "@/components/ui/tone";

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

// How each feature status reads, its colour, and whether work is still going on
export const STATUS: Record<string, { label: string; tone: Tone; live?: boolean }> = {
  running: { label: "Running", tone: "sky", live: true },
  in_review: { label: "In review", tone: "sky", live: true },
  waiting_for_plan_approval: { label: "Waiting for your approval", tone: "peach" },
  ready_to_merge: { label: "PR ready", tone: "mint" },
  needs_human: { label: "Needs you", tone: "peach" },
  blocked: { label: "Questions on Jira", tone: "butter" },
  plan_rejected: { label: "Plan rejected", tone: "plain" },
  failed: { label: "Failed", tone: "rose" },
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
  return STATUS[run.status] ?? { label: run.status.replaceAll("_", " "), tone: "plain" as const };
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
