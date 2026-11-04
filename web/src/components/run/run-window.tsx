"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";

import { feedItem, type FeedItem } from "@/lib/runs/feed";
import { stagesFrom } from "@/lib/runs/stages";
import type { RunView } from "@/lib/runs/types";

import { Feed } from "./feed";
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
 * numbers on top. With replay, it plays the events one by one as if live.
 */
export function RunWindow({ run, replay = false }: { run: RunView; replay?: boolean }) {
  const total = run.events.length;
  const [shown, setShown] = useState(replay ? 0 : total);

  useEffect(() => {
    if (shown >= total) return;
    const timer = setTimeout(() => setShown((n) => n + 1), delayBefore(run, shown));
    return () => clearTimeout(timer);
  }, [run, shown, total]);

  const events = useMemo(() => run.events.slice(0, shown), [run, shown]);
  const stages = useMemo(() => stagesFrom(events), [events]);
  const items = useMemo(
    () => events.map(feedItem).filter((item): item is FeedItem => item !== null),
    [events],
  );
  const finished = shown >= total;

  return (
    <section className="space-y-4">
      <header className="flex flex-wrap items-center gap-x-6 gap-y-2 rounded-lg border border-gray-200 px-4 py-3 dark:border-gray-800">
        <h1 className="mr-auto text-lg font-semibold">
          <span className="font-mono text-gray-500">{run.ticket}</span> {run.title}
        </h1>
        <Stat label="Cost">{finished ? `₹${run.costInr.toFixed(2)}` : "…"}</Stat>
        <Stat label="Time">{duration(run, shown)}</Stat>
        <Stat label="PR">
          {finished && run.prUrl ? (
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
              className="rounded border border-gray-300 px-2.5 py-1 text-sm dark:border-gray-700"
            >
              Replay
            </button>
            {!finished && (
              <button
                type="button"
                onClick={() => setShown(total)}
                className="rounded border border-gray-300 px-2.5 py-1 text-sm dark:border-gray-700"
              >
                Skip to end
              </button>
            )}
          </span>
        )}
      </header>

      <div className="grid gap-4 md:grid-cols-[15rem_1fr]">
        <Pipeline stages={stages} />
        <Feed items={items} />
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
