"use client";

import Link from "next/link";

import { StatusLabel } from "@/components/status-label";
import { day, duration, runHref, runKey, useRuns } from "@/lib/runs/use-runs";

/** Every run, newest first, refreshed every 10 seconds: a table on wide screens, a
 * stack of rows on phones. */
export function RunsList() {
  const { runs, error } = useRuns();

  if (error && runs === null)
    return <p className="text-sm text-bad">Couldn&apos;t load runs. Retrying…</p>;
  if (runs === null) return <TableSkeleton />;
  if (runs.length === 0)
    return (
      <p className="rounded-lg border border-dashed border-line px-5 py-10 text-center text-muted">
        No runs yet. Start one from the{" "}
        <Link href="/dashboard" className="text-ink underline underline-offset-4">
          dashboard
        </Link>
        , or{" "}
        <Link href="/runs/sample" className="text-ink underline underline-offset-4">
          watch an example
        </Link>
        .
      </p>
    );

  return (
    <div className="overflow-hidden rounded-lg border border-line bg-surface">
      <table className="w-full text-sm">
        <thead className="hidden border-b border-line text-left text-xs text-muted sm:table-header-group">
          <tr>
            <th className="px-5 py-3 font-normal">Ticket</th>
            <th className="px-3 py-3 font-normal">Status</th>
            <th className="px-3 py-3 text-right font-normal">Cost</th>
            <th className="px-3 py-3 text-right font-normal">Time</th>
            <th className="px-3 py-3 font-normal">Started</th>
            <th className="px-5 py-3">
              <span className="sr-only">Links</span>
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {runs.map((run) => (
            <tr
              key={runKey(run)}
              className="flex flex-wrap items-center gap-x-4 gap-y-1 px-5 py-4 transition hover:bg-raised/60 sm:table-row sm:p-0"
            >
              <td className="w-full sm:w-auto sm:px-5 sm:py-4">
                <Link href={runHref(run)} className="group flex min-w-0 items-baseline gap-3">
                  <span className="font-mono text-xs text-muted">{run.ticket}</span>
                  {!run.demo && (
                    <span className="shrink-0 rounded-sm border border-line px-1.5 text-xs text-muted">
                      your project
                    </span>
                  )}
                  <span className="truncate font-medium group-hover:underline group-hover:underline-offset-4">
                    {run.title || run.ticket}
                  </span>
                </Link>
              </td>
              <td className="sm:px-3 sm:py-4">
                <StatusLabel run={run} />
              </td>
              <td className="text-muted tabular-nums sm:px-3 sm:py-4 sm:text-right">
                ₹{run.cost_inr.toFixed(2)}
              </td>
              <td className="text-muted tabular-nums sm:px-3 sm:py-4 sm:text-right">
                {duration(run)}
              </td>
              <td className="hidden text-muted sm:table-cell sm:px-3 sm:py-4">
                {day(run.started_at)}
              </td>
              <td className="ml-auto sm:px-5 sm:py-4 sm:text-right">
                <span className="inline-flex gap-4">
                  <Link href={runHref(run)} className="text-muted hover:text-ink">
                    Watch
                  </Link>
                  {run.pr_url && (
                    <a
                      href={run.pr_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-ink hover:text-accent"
                    >
                      PR ↗
                    </a>
                  )}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TableSkeleton() {
  return (
    <div
      className="space-y-px overflow-hidden rounded-lg border border-line"
      aria-label="Loading runs"
    >
      {[0, 1, 2].map((i) => (
        <div key={i} className="h-14 animate-pulse bg-surface" />
      ))}
    </div>
  );
}
