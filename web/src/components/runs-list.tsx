"use client";

import Link from "next/link";

import { StatusLabel } from "@/components/status-label";
import { Card } from "@/components/ui/card";
import { Chip } from "@/components/ui/chip";
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
      <p className="rounded-3xl border-[1.5px] border-dashed border-ink/30 px-5 py-10 text-center text-muted">
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
    <Card as="div" tone="lilac" className="overflow-hidden p-0! sm:p-0!">
      <table className="w-full text-sm">
        <thead className="hidden border-b-[1.5px] border-ink text-left text-xs font-semibold tracking-wider text-muted uppercase sm:table-header-group">
          <tr>
            <th className="px-5 py-3">Ticket</th>
            <th className="px-3 py-3">Status</th>
            <th className="px-3 py-3 text-right">Time</th>
            <th className="px-3 py-3">Started</th>
            <th className="px-5 py-3">
              <span className="sr-only">Links</span>
            </th>
          </tr>
        </thead>
        <tbody className="divide-y-[1.5px] divide-dashed divide-ink/20">
          {runs.map((run) => (
            <tr
              key={runKey(run)}
              className="flex flex-wrap items-center gap-x-4 gap-y-2 px-5 py-4 transition hover:bg-raised/60 sm:table-row sm:p-0"
            >
              <td className="w-full sm:w-auto sm:px-5 sm:py-4">
                <Link href={runHref(run)} className="group flex min-w-0 items-center gap-3">
                  <Chip tone="butter" mono className="shrink-0">
                    {run.ticket}
                  </Chip>
                  {!run.demo && (
                    <Chip tone="lime" className="shrink-0">
                      your project
                    </Chip>
                  )}
                  <span className="truncate font-semibold group-hover:underline group-hover:underline-offset-4">
                    {run.title || run.ticket}
                  </span>
                </Link>
              </td>
              <td className="sm:px-3 sm:py-4">
                <StatusLabel run={run} />
              </td>
              <td className="text-muted tabular-nums sm:px-3 sm:py-4 sm:text-right">
                {duration(run)}
              </td>
              <td className="hidden text-muted sm:table-cell sm:px-3 sm:py-4">
                {day(run.started_at)}
              </td>
              <td className="ml-auto sm:px-5 sm:py-4 sm:text-right">
                <span className="inline-flex gap-4">
                  <Link href={runHref(run)} className="font-semibold hover:text-accent">
                    Watch
                  </Link>
                  {run.pr_url && (
                    <a
                      href={run.pr_url}
                      target="_blank"
                      rel="noreferrer"
                      className="font-semibold hover:text-accent"
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
    </Card>
  );
}

function TableSkeleton() {
  return (
    <div className="space-y-3" aria-label="Loading runs">
      {[0, 1, 2].map((i) => (
        <div key={i} className="h-14 animate-pulse rounded-2xl bg-raised" />
      ))}
    </div>
  );
}
