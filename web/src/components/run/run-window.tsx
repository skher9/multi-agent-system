"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";

import { feedItem, type FeedItem } from "@/lib/runs/feed";
import { stagesFrom } from "@/lib/runs/stages";
import type { RunView } from "@/lib/runs/types";

import { CodePanel } from "./code-panel";
import { Feed } from "./feed";
import { NowBar } from "./now-bar";
import { ResultCard } from "./result-card";
import { Pipeline } from "./pipeline";

// Replay pacing: real gaps are minutes long, so squeeze each into this range.
const MIN_STEP_MS = 250;
const MAX_STEP_MS = 1400;
const SPEEDUP = 20;

function delayBefore(run: RunView, index: number): number {
  const event = run.events[index];
  const previous = run.events[index - 1];
  if (!event || !previous) return MIN_STEP_MS;
  const gap = (Date.parse(event.createdAt) - Date.parse(previous.createdAt)) / SPEEDUP;
  return Math.min(MAX_STEP_MS, Math.max(MIN_STEP_MS, gap));
}

function duration(run: RunView, shown: number): string {
  const first = run.events[0];
  const last = run.events[shown - 1];
  if (!first || !last) return "0s";
  const seconds = Math.round((Date.parse(last.createdAt) - Date.parse(first.createdAt)) / 1000);
  return seconds < 60 ? `${seconds}s` : `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}

/**
 * The run window: the pipeline on the left, the live feed on the right, the run's
 * numbers on top. With replay, it plays the events one by one as if live. With live,
 * events arriving later play in the same way, and cost and PR show as they come.
 */
export function RunWindow({
  run,
  replay = false,
  live = false,
  stopped = false,
}: {
  run: RunView;
  replay?: boolean;
  live?: boolean;
  stopped?: boolean; // live runs: it ended, failed or paused
}) {
  const total = run.events.length;
  const [shown, setShown] = useState(replay ? 0 : total);

  useEffect(() => {
    if (shown >= total) return;
    // Live: show what arrived at once (a short stagger keeps it readable); replay: paced
    const wait = live ? 60 : delayBefore(run, shown);
    const timer = setTimeout(() => setShown((n) => n + 1), wait);
    return () => clearTimeout(timer);
  }, [run, shown, total, live]);

  const events = useMemo(() => run.events.slice(0, shown), [run, shown]);
  const stages = useMemo(() => stagesFrom(events), [events]);
  const items = useMemo(
    () => events.map(feedItem).filter((item): item is FeedItem => item !== null),
    [events],
  );
  const finished = shown >= total;
  const working = live && !stopped;
  const thinkingRole = working ? lastRole(events) : null;
  const showNumbers = finished || live;

  return (
    <section className="space-y-4">
      <header className="flex flex-wrap items-center gap-x-6 gap-y-2 rounded-lg border border-line bg-surface px-4 py-3">
        <div className="mr-auto min-w-0">
          <h1 className="font-display text-2xl">
            <span className="font-mono text-gray-500">{run.ticket}</span>{" "}
            {run.title || (live ? "Fetching the ticket…" : "")}
          </h1>
          {run.links && <RunLinksRow run={run} />}
        </div>
        <Stat label="Cost">{showNumbers ? `₹${run.costInr.toFixed(2)}` : "…"}</Stat>
        <Stat label="Time">{duration(run, shown)}</Stat>
        <Stat label="PR">
          {showNumbers && run.prUrl ? (
            <a href={run.prUrl} className="underline" target="_blank" rel="noreferrer">
              Open
            </a>
          ) : (
            "—"
          )}
        </Stat>
        {replay && (
          <span className="flex gap-2">
            <button
              type="button"
              onClick={() => setShown(0)}
              className="rounded-md border border-line px-2.5 py-1 text-sm hover:bg-raised"
            >
              Replay
            </button>
            {!finished && (
              <button
                type="button"
                onClick={() => setShown(total)}
                className="rounded-md border border-line px-2.5 py-1 text-sm hover:bg-raised"
              >
                Skip to end
              </button>
            )}
          </span>
        )}
      </header>

      {working && <NowBar events={events} />}
      {live && stopped && <ResultCard run={run} events={events} />}

      <div className="grid gap-4 md:grid-cols-[15rem_minmax(0,1fr)] xl:grid-cols-[14rem_minmax(0,1fr)_minmax(0,1.2fr)]">
        <Pipeline stages={stages} />
        <Feed items={items} thinkingRole={thinkingRole} />
        <div className="md:col-span-2 xl:col-span-1">
          <CodePanel events={events} />
        </div>
      </div>
    </section>
  );
}

function Stat({ label, children }: { label: string; children: ReactNode }) {
  return (
    <span className="text-sm">
      <span className="text-gray-500">{label} </span>
      <span className="font-medium tabular-nums">{children}</span>
    </span>
  );
}

function lastRole(events: RunView["events"]): string {
  for (let i = events.length - 1; i >= 0; i--) {
    const role = events[i]?.data.role;
    if (typeof role === "string") return role;
  }
  return "reader";
}

/** Where the work lives: the Jira ticket and board, the repo, the agent's branch. */
function RunLinksRow({ run }: { run: RunView }) {
  const links = run.links;
  if (!links) return null;
  const items = [
    { label: "Jira ticket", href: links.ticketUrl },
    { label: "Board", href: links.boardUrl },
    { label: links.repo ?? "Repo", href: links.repoUrl },
    { label: `Branch agent/${run.ticket}`, href: links.branchUrl },
    { label: "Pull request", href: run.prUrl },
  ].filter((item): item is { label: string; href: string } => Boolean(item.href));
  return (
    <p className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs">
      {items.map((item) => (
        <a
          key={item.label}
          href={item.href}
          target="_blank"
          rel="noreferrer"
          className="text-muted underline-offset-4 hover:text-ink hover:underline"
        >
          {item.label} ↗
        </a>
      ))}
    </p>
  );
}
