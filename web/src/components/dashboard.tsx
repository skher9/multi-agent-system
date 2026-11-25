"use client";

import Link from "next/link";
import { type ReactNode, useEffect, useState } from "react";

import { ButtonLink } from "@/components/button";
import { useOwnProject } from "@/components/own-project";
import { StatusLabel } from "@/components/status-label";
import { Card } from "@/components/ui/card";
import { Chip } from "@/components/ui/chip";
import { StagePips } from "@/components/ui/stage-pips";
import { TONE_HOVER_SHADOW, type Tone } from "@/components/ui/tone";
import { api } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";
import { useCredits } from "@/lib/runs/use-credits";
import {
  day,
  duration,
  type Run,
  type RunGroup,
  runHref,
  runKey,
  statusOf,
  useRuns,
} from "@/lib/runs/use-runs";

const FILTERS: [RunGroup | "all", string][] = [
  ["all", "All"],
  ["needs", "Needs you"],
  ["running", "Running"],
  ["done", "Done"],
  ["stopped", "Stopped"],
];

const RISE_STEP_S = 0.07; // each card and row rises in a beat after the one before

/** Your numbers, the start-run form beside the run that needs you, then every run with
 * where it stands. One runs feed for all of it. */
export function Overview({ start }: { start: ReactNode }) {
  const { runs, error } = useRuns();

  if (error && runs === null)
    return <p className="text-sm text-bad">Couldn&apos;t load your runs. Retrying…</p>;
  if (runs === null) return <div className="h-72 animate-pulse rounded-3xl bg-raised" />;
  return (
    <div className="space-y-10">
      <Stats runs={runs} />
      <div className="grid items-start gap-8 lg:grid-cols-2">
        {start}
        <NeedsYou runs={runs} />
      </div>
      {runs.length === 0 ? <FirstRun /> : <AllRuns runs={runs} />}
    </div>
  );
}

function Stats({ runs }: { runs: Run[] }) {
  const { credits } = useCredits();
  const prs = runs.filter((r) => r.pr_url).length;
  const middle = median(runs.filter((r) => r.pr_url));
  const items: [label: string, value: string, note: string, tone: Tone][] = [
    ["Runs", String(runs.length), "Demo and your own project", "lilac"],
    ["Pull requests", String(prs), "You decide what merges", "mint"],
    ["Typical run", middle ? duration(middle) : "–", "From ticket to pull request", "butter"],
    [
      "Free runs left",
      credits ? (credits.left === null ? "No limit" : String(credits.left)) : "–",
      credits?.left === null ? "Owner account" : `Of ${credits?.total ?? "–"} per account`,
      "peach",
    ],
  ];
  return (
    <dl className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
      {items.map(([label, value, note, tone], i) => (
        <Card
          as="div"
          key={label}
          tone={tone}
          className="animate-rise py-5! sm:py-5!"
          style={{ animationDelay: `${i * RISE_STEP_S}s` }}
        >
          <dt className="text-xs font-semibold tracking-wider text-muted uppercase">{label}</dt>
          <dd className="mt-1 font-display text-4xl">{value}</dd>
          <dd className="text-sm text-muted">{note}</dd>
        </Card>
      ))}
    </dl>
  );
}

/** The newest run waiting on a person, wobbling gently until they act. */
function NeedsYou({ runs }: { runs: Run[] }) {
  const run = runs.find((r) => statusOf(r).group === "needs");
  if (!run) return null;
  const plan = run.status === "waiting_for_plan_approval";
  return (
    <Card as="aside" tone="peach" aria-labelledby="needs-you" className="animate-wobble">
      <Chip tone="peach">Needs you</Chip>
      <h2 id="needs-you" className="mt-3 font-display text-2xl">
        {run.ticket} {plan ? "has a plan waiting" : "has questions for you"}
      </h2>
      <p className="mt-2 max-w-prose text-muted">
        {plan
          ? "The planner finished. Nothing gets written until you approve, revise or reject it on the Jira ticket."
          : "The agents stopped to ask rather than guess. Answer on the Jira ticket and start it again."}
      </p>
      <ButtonLink href={runHref(run)} className="mt-5">
        {plan ? "Review the plan" : "See the questions"}
      </ButtonLink>
    </Card>
  );
}

function AllRuns({ runs }: { runs: Run[] }) {
  const [filter, setFilter] = useState<RunGroup | "all">("all");
  const shown = filter === "all" ? runs : runs.filter((r) => statusOf(r).group === filter);
  return (
    <section aria-labelledby="all-runs" className="space-y-5">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <h2 id="all-runs" className="font-display text-3xl">
          All runs
        </h2>
        <ul className="flex flex-wrap gap-2" aria-label="Filter runs">
          {FILTERS.map(([value, label]) => (
            <li key={value}>
              <button
                type="button"
                aria-pressed={filter === value}
                onClick={() => setFilter(value)}
                className={`min-h-11 rounded-full border-ink-line px-4 text-sm font-semibold transition hover:-translate-y-0.5 ${
                  filter === value ? "bg-ink text-canvas" : "bg-surface"
                }`}
              >
                {label}
              </button>
            </li>
          ))}
        </ul>
      </header>
      {shown.length === 0 ? (
        <p className="rounded-3xl border-[1.5px] border-dashed border-ink/30 px-5 py-8 text-center text-muted">
          No runs here.
        </p>
      ) : (
        <ol className="space-y-4">
          {shown.map((run, i) => (
            <RunRow key={runKey(run)} run={run} delay={i * RISE_STEP_S} />
          ))}
        </ol>
      )}
    </section>
  );
}

function RunRow({ run, delay }: { run: Run; delay: number }) {
  const status = statusOf(run);
  return (
    <li className="animate-rise" style={{ animationDelay: `${delay}s` }}>
      <Link
        href={runHref(run)}
        className={`grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-5 gap-y-3 rounded-[20px] border-ink-line bg-surface px-5 py-4 transition hover:-translate-0.5 ${TONE_HOVER_SHADOW[status.tone]}`}
      >
        <span className="flex min-w-0 flex-col gap-2.5">
          <span className="flex flex-wrap items-center gap-2">
            <Chip tone="butter" mono>
              {run.ticket}
            </Chip>
            <StatusLabel run={run} />
            {!run.demo && <Chip tone="lime">your project</Chip>}
          </span>
          <span className="truncate font-display text-xl">{run.title || run.ticket}</span>
          <StagePips
            node={run.node ?? null}
            finished={status.group === "done"}
            live={Boolean(status.live)}
          />
        </span>
        <span className="flex flex-col items-end gap-0.5 text-right">
          <span className="font-mono text-lg">{duration(run)}</span>
          <span className="text-sm text-muted">{day(run.started_at)}</span>
          {run.pr_url && <span className="font-mono text-sm">PR ↗</span>}
        </span>
      </Link>
    </li>
  );
}

function FirstRun() {
  return (
    <Card tone="butter" className="px-6 py-12 text-center">
      <h2 className="font-display text-3xl">Your team is ready.</h2>
      <p className="mx-auto mt-3 max-w-md text-muted">
        Start a run with a ticket above. Not sure what to try?{" "}
        <Link href="/runs/sample" className="font-semibold text-ink underline underline-offset-4">
          Watch a real run
        </Link>{" "}
        first.
      </p>
    </Card>
  );
}

/** Where the agents work: the demo project, or the user's own once it's set up. */
export function Connected() {
  const { project } = useOwnProject();
  const own = project?.ready ? project : null;
  const [demo, setDemo] = useState<components["schemas"]["ProjectLinks"] | null>(null);
  useEffect(() => {
    api.GET("/project").then(({ data }) => data && setDemo(data));
  }, []);
  const jira = own?.jira?.project_key ?? demo?.jira_project;
  const repo = own?.github?.repo ?? demo?.repo;
  return (
    <Card
      tone="lime"
      aria-labelledby="connected"
      className="grid items-center gap-5 md:grid-cols-[1fr_auto_auto]"
    >
      <header>
        <h2 id="connected" className="font-display text-2xl">
          Connected
        </h2>
        <p className="mt-1 text-muted">
          {own ? "Your own Jira and GitHub." : "The demo project. Connect yours any time."}
        </p>
      </header>
      <p className="flex flex-wrap gap-3">
        {jira && (
          <Chip tone="mint" className="min-h-10 px-4">
            Jira · project {jira}
          </Chip>
        )}
        {repo && (
          <Chip tone="mint" className="min-h-10 px-4">
            GitHub · {repo}
          </Chip>
        )}
      </p>
      <ButtonLink href={own ? "/settings#project" : "/setup"} variant="ghost">
        {own ? "Manage in Settings" : "Use your own project"}
      </ButtonLink>
    </Card>
  );
}

function median(runs: Run[]): Run | undefined {
  const length = (r: Run) => new Date(r.updated_at).getTime() - new Date(r.started_at).getTime();
  return [...runs].sort((a, b) => length(a) - length(b))[Math.floor(runs.length / 2)];
}
