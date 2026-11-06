"use client";

import Link from "next/link";

import { StatusLabel } from "@/components/status-label";
import { duration, type Run, useRuns } from "@/lib/runs/use-runs";

/** Your numbers, the latest run, and the few before it. */
export function Overview() {
  const { runs, error } = useRuns();

  if (error && runs === null)
    return <p className="text-sm text-bad">Couldn&apos;t load your runs. Retrying…</p>;
  if (runs === null) return <div className="h-72 animate-pulse rounded-lg bg-surface" />;
  if (runs.length === 0) return <FirstRun />;

  const [latest, ...earlier] = runs as [Run, ...Run[]]; // not empty: checked above
  return (
    <div className="space-y-8">
      <Stats runs={runs} />
      <Latest run={latest} />
      {earlier.length > 0 && (
        <section>
          <div className="flex items-baseline justify-between">
            <h2 className="font-display text-2xl">Earlier runs</h2>
            <Link href="/runs" className="text-sm text-muted hover:text-ink">
              All runs →
            </Link>
          </div>
          <ul className="mt-3 divide-y divide-line border-y border-line">
            {earlier.slice(0, 3).map((run) => (
              <li
                key={run.ticket}
                className="flex flex-wrap items-baseline gap-x-4 gap-y-1 py-3 text-sm"
              >
                <Link
                  href={`/runs/${run.ticket}`}
                  className="flex min-w-0 items-baseline gap-3 hover:underline hover:underline-offset-4"
                >
                  <span className="font-mono text-xs text-muted">{run.ticket}</span>
                  <span className="truncate">{run.title || run.ticket}</span>
                </Link>
                <span className="ml-auto flex gap-4 text-muted">
                  <StatusLabel run={run} />
                  <span className="tabular-nums">₹{run.cost_inr.toFixed(2)}</span>
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function Stats({ runs }: { runs: Run[] }) {
  const prs = runs.filter((r) => r.pr_url).length;
  const spent = runs.reduce((sum, r) => sum + r.cost_inr, 0);
  const middle = median(runs.filter((r) => r.pr_url));
  const typical = middle ? duration(middle) : "–";
  const items = [
    [String(runs.length), runs.length === 1 ? "run" : "runs"],
    [String(prs), prs === 1 ? "pull request" : "pull requests"],
    [`₹${spent.toFixed(0)}`, "spent on models"],
    [typical, "typical run to PR"],
  ];
  return (
    <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-line bg-line sm:grid-cols-4">
      {items.map(([value, label]) => (
        <div key={label} className="bg-surface px-5 py-4">
          <dd className="font-display text-4xl leading-none">{value}</dd>
          <dt className="mt-2 text-xs text-muted">{label}</dt>
        </div>
      ))}
    </dl>
  );
}

function Latest({ run }: { run: Run }) {
  return (
    <section className="rounded-lg border border-line bg-surface p-6">
      <p className="flex items-center justify-between text-xs text-muted">
        <span className="font-mono">Latest · {run.ticket}</span>
        <StatusLabel run={run} />
      </p>
      <h2 className="mt-3 font-display text-3xl leading-tight">{run.title || run.ticket}</h2>
      <p className="mt-2 text-sm text-muted">
        ₹{run.cost_inr.toFixed(2)} · {duration(run)}
      </p>
      <div className="mt-5 flex flex-wrap gap-3 text-sm">
        <Link
          href={`/runs/${run.ticket}`}
          className="rounded-md bg-ink px-4 py-2 font-medium text-canvas transition hover:bg-accent hover:text-accent-ink"
        >
          Open the run
        </Link>
        {run.pr_url && (
          <a
            href={run.pr_url}
            target="_blank"
            rel="noreferrer"
            className="rounded-md border border-ink/15 px-4 py-2 font-medium transition hover:border-ink/40"
          >
            See the pull request ↗
          </a>
        )}
      </div>
    </section>
  );
}

function FirstRun() {
  return (
    <section className="rounded-lg border border-dashed border-line px-6 py-12 text-center">
      <h2 className="font-display text-3xl">Your team is ready.</h2>
      <p className="mx-auto mt-3 max-w-md text-muted">
        Start a run with a ticket on the right. Not sure what to try?{" "}
        <Link href="/runs/sample" className="text-ink underline underline-offset-4">
          Watch a finished run
        </Link>{" "}
        first.
      </p>
    </section>
  );
}

function median(runs: Run[]): Run | undefined {
  const sorted = [...runs].sort(
    (a, b) =>
      new Date(a.updated_at).getTime() -
      new Date(a.started_at).getTime() -
      (new Date(b.updated_at).getTime() - new Date(b.started_at).getTime()),
  );
  return sorted[Math.floor(sorted.length / 2)];
}
