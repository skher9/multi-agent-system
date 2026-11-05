"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { api } from "@/lib/api/client";
import type { EventKind, RunEvent, RunView } from "@/lib/runs/types";

import { RunWindow } from "./run-window";

const POLL_MS = 2000;
// After one of these, the run has stopped (for now): no need to keep asking
const STOPPED: EventKind[] = ["run_ended", "run_failed", "run_paused"];

type State =
  | { kind: "loading" }
  | { kind: "waiting" } // started, but the worker hasn't recorded anything yet
  | { kind: "error"; message: string }
  | { kind: "run"; run: RunView; stopped: boolean };

/** A real run, live: asks the API for new events every 2 seconds and plays them in. */
export function LiveRun() {
  const { ticket } = useParams<{ ticket: string }>();
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let current: RunView | null = null;

    async function poll() {
      const after = current?.events.at(-1)?.id ?? 0;
      const { data, response } = await api.GET("/runs/{ticket}/events", {
        params: { path: { ticket }, query: { after } },
      });
      if (cancelled) return;
      if (!data) {
        if (response.status === 404) setState({ kind: "waiting" });
        else if (response.status === 401) {
          setState({ kind: "error", message: "Your login expired. Refresh the page." });
          return;
        } else setState({ kind: "error", message: "Couldn't load the run. Retrying…" });
        timer = setTimeout(poll, POLL_MS);
        return;
      }
      const fresh: RunEvent[] = data.events.map((e) => ({
        id: e.id,
        kind: e.kind as EventKind,
        data: e.data,
        agentRunId: e.agent_run_id ?? null,
        createdAt: e.created_at,
      }));
      current = {
        ticket: data.ticket,
        title: data.title === data.ticket ? "" : data.title,
        prUrl: data.pr_url ?? null,
        links: {
          ticketUrl: data.ticket_url ?? null,
          boardUrl: data.project.board_url ?? null,
          repo: data.project.repo ?? null,
          repoUrl: data.project.repo_url ?? null,
          branchUrl: data.branch_url ?? null,
        },
        costInr: data.cost_inr,
        events: [...(current?.events ?? []), ...fresh],
      };
      // Each run of a ticket starts with run_started: show only the latest one
      const lastStart = current.events.findLastIndex((e) => e.kind === "run_started");
      const latest = current.events.slice(Math.max(lastStart, 0));
      const stopped = latest.some((e) => STOPPED.includes(e.kind));
      setState({ kind: "run", run: { ...current, events: latest }, stopped });
      if (!stopped) timer = setTimeout(poll, POLL_MS);
    }

    poll();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [ticket]);

  // The browser tab says how the run is doing, so it can be watched from another tab
  const tabTitle =
    state.kind !== "run"
      ? `${ticket} · Agent Dev Team`
      : `${state.stopped ? endMark(state.run) : "● Running"} · ${ticket}`;
  useEffect(() => {
    document.title = tabTitle;
  }, [tabTitle]);

  if (state.kind === "loading") return <p className="text-sm text-muted">Loading the run…</p>;
  if (state.kind === "waiting")
    return (
      <p className="text-sm text-muted">
        Waiting for <span className="font-mono text-ink">{ticket}</span> to start… This page updates
        by itself.
      </p>
    );
  if (state.kind === "error") return <p className="text-sm text-red-400">{state.message}</p>;
  return (
    <div className="space-y-3">
      <p className="flex items-center gap-2 text-sm text-muted">
        {state.stopped ? (
          <>Run stopped. Scroll the feed to see every step.</>
        ) : (
          <>
            <span className="size-2 animate-pulse rounded-full bg-accent" /> Live: updates every 2
            seconds
          </>
        )}
        <Link href="/runs" className="ml-auto hover:text-ink">
          All runs
        </Link>
      </p>
      <RunWindow run={state.run} live stopped={state.stopped} />
    </div>
  );
}

function endMark(run: RunView): string {
  const end = [...run.events].reverse().find((e) => STOPPED.includes(e.kind));
  if (end?.kind === "run_failed") return "✗ Failed";
  if (end?.kind === "run_paused") return "⏸ Needs approval";
  return end?.data.outcome === "ready_to_merge" ? "✓ PR ready" : "! Needs you";
}
