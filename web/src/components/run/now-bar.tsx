"use client";

import { useEffect, useState } from "react";

import { NODES, feedItem } from "@/lib/runs/feed";
import type { RunEvent } from "@/lib/runs/types";

// No new event for this long: say plainly that waiting is normal
const QUIET_SECONDS = 20;

/** What's happening right now, and how long since the last sign of life. The clock
 * ticks every second, so the page never looks frozen between events. */
export function NowBar({ events }: { events: RunEvent[] }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);

  const { role, doing, latest, since } = current(events);
  const seconds = since ? Math.max(0, Math.round((now - since) / 1000)) : 0;
  const quiet = seconds >= QUIET_SECONDS;

  return (
    <div
      role="status"
      aria-live="polite"
      className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border border-accent/30 bg-accent/5 px-4 py-3 text-sm"
    >
      <span className="relative flex size-2.5">
        <span className="absolute inline-flex size-full animate-ping rounded-full bg-accent opacity-60" />
        <span className="relative inline-flex size-2.5 rounded-full bg-accent" />
      </span>
      <span className="font-medium capitalize text-ink">{role}</span>
      <span className="text-ink">{doing}</span>
      {latest && <span className="truncate text-muted">· {latest}</span>}
      <span className="ml-auto font-mono text-xs tabular-nums text-muted">
        {Math.floor(seconds / 60)}:{String(seconds % 60).padStart(2, "0")} since the last step
      </span>
      {quiet && (
        <span className="w-full text-xs text-muted">
          Still working: the model is thinking or a step is running. This can take up to a minute.
        </span>
      )}
    </div>
  );
}

function current(events: RunEvent[]) {
  const open = new Map<string, number>(); // node -> index of its start
  for (const [i, e] of events.entries()) {
    if (e.kind === "node_started") open.set(String(e.data.node), i);
    if (e.kind === "node_finished") open.delete(String(e.data.node));
  }
  const [node, startedAt] = [...open.entries()].at(-1) ?? ["", -1];
  const info = NODES[node] ?? { role: "run", doing: "Starting the run" };
  const after = events.slice(startedAt + 1);
  const last = [...after]
    .reverse()
    .find((e) => ["step", "tool_call", "agent_thought"].includes(e.kind));
  const latest =
    last?.kind === "agent_thought" ? "thinking" : last ? (feedItem(last)?.title ?? "") : "";
  const role = String(last?.data.role ?? info.role);
  return {
    role: role === "qa" ? "QA" : role,
    doing: info.doing,
    latest: latest.replace(/…$/, ""),
    since: events.at(-1) ? Date.parse(events.at(-1)!.createdAt) : null,
  };
}
