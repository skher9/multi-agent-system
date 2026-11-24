"use client";

import Link from "next/link";

import { ButtonLink } from "@/components/button";
import { Card } from "@/components/ui/card";
import { Chip } from "@/components/ui/chip";
import type { Tone } from "@/components/ui/tone";
import { useOwnProject } from "@/components/own-project";
import { StatusLabel } from "@/components/status-label";
import { duration, type Run, runHref, runKey, useRuns } from "@/lib/runs/use-runs";

/** Your numbers, the latest run, and the few before it. */
export function Overview() {
  const { runs, error } = useRuns();

  if (error && runs === null)
    return <p className="text-sm text-bad">Couldn&apos;t load your runs. Retrying…</p>;
  if (runs === null) return <div className="h-72 animate-pulse rounded-3xl bg-raised" />;
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
          <ul className="mt-4 space-y-3">
            {earlier.slice(0, 3).map((run) => (
              <li
                key={runKey(run)}
                className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-2xl border-ink-line bg-surface px-4 py-3 text-sm transition hover:-translate-px hover:shadow-hard-sm"
              >
                <Link href={runHref(run)} className="flex min-w-0 items-center gap-3">
                  <Chip tone="butter" mono>
                    {run.ticket}
                  </Chip>
                  <span className="truncate font-semibold">{run.title || run.ticket}</span>
                </Link>
                <span className="ml-auto flex gap-4 text-muted">
                  <StatusLabel run={run} />
                  <span className="tabular-nums">{duration(run)}</span>
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
  const middle = median(runs.filter((r) => r.pr_url));
  const typical = middle ? duration(middle) : "–";
  const items: [value: string, label: string, tone: Tone][] = [
    [String(runs.length), runs.length === 1 ? "run" : "runs", "lilac"],
    [String(prs), prs === 1 ? "pull request" : "pull requests", "mint"],
    [typical, "typical run to PR", "butter"],
  ];
  return (
    <dl className="grid gap-5 sm:grid-cols-3">
      {items.map(([value, label, tone]) => (
        <Card as="div" key={label} tone={tone} className="animate-rise py-5! sm:py-5!">
          <dt className="text-xs font-semibold tracking-wider text-muted uppercase">{label}</dt>
          <dd className="mt-1 font-display text-4xl">{value}</dd>
        </Card>
      ))}
    </dl>
  );
}

function Latest({ run }: { run: Run }) {
  return (
    <Card tone="sky">
      <p className="flex items-center justify-between gap-3 text-sm">
        <Chip tone="butter" mono>
          Latest · {run.ticket}
        </Chip>
        <StatusLabel run={run} />
      </p>
      <h2 className="mt-3 font-display text-3xl leading-tight">{run.title || run.ticket}</h2>
      <p className="mt-2 text-sm text-muted">{duration(run)}</p>
      <p className="mt-5 flex flex-wrap gap-3">
        <ButtonLink href={runHref(run)}>Open the run</ButtonLink>
        {run.pr_url && (
          <ButtonLink href={run.pr_url} target="_blank" rel="noreferrer" variant="ghost">
            See the pull request ↗
          </ButtonLink>
        )}
      </p>
    </Card>
  );
}

function FirstRun() {
  return (
    <Card tone="butter" className="px-6 py-12 text-center">
      <h2 className="font-display text-3xl">Your team is ready.</h2>
      <p className="mx-auto mt-3 max-w-md text-muted">
        Start a run with a ticket on the right. Not sure what to try?{" "}
        <Link href="/runs/sample" className="text-ink underline underline-offset-4">
          Watch a finished run
        </Link>{" "}
        first.
      </p>
    </Card>
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

/** Setting up your own project: an invitation until it's done, then what it points at. */
export function OwnProjectCard() {
  const { project } = useOwnProject();
  if (!project?.available) return null;
  if (project.ready)
    return (
      <Card tone="mint" className="text-sm">
        <h2 className="font-display text-xl">Your project</h2>
        <p className="mt-2 text-muted">
          <span className="font-mono text-xs text-ink">{project.github?.repo}</span> with Jira{" "}
          <span className="font-mono text-xs text-ink">{project.jira?.project_key}</span>. Only you
          see its runs.
        </p>
        <ButtonLink href="/settings#project" size="sm" variant="ghost" className="mt-4">
          Manage or disconnect
        </ButtonLink>
      </Card>
    );
  return (
    <Card tone="peach" className="text-sm">
      <h2 className="font-display text-xl">Use your own project</h2>
      <p className="mt-2 text-muted">
        Connect your Jira and a GitHub repo, and the same team works on your tickets. Pull requests
        wait for your review; nothing is merged for you.
      </p>
      <ButtonLink href="/setup" size="sm" variant="ghost" className="mt-4">
        Set it up · 5 min
      </ButtonLink>
    </Card>
  );
}
