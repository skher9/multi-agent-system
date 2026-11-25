"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { Button, ButtonLink } from "@/components/button";
import { useOwnProject, type OwnProjectState } from "@/components/own-project";
import { Card } from "@/components/ui/card";
import { Chip } from "@/components/ui/chip";
import { FormError, INPUT } from "@/components/ui/field";
import { api } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";
import { runHref } from "@/lib/runs/use-runs";

type Project = components["schemas"]["ProjectLinks"];

const POLL_MS = 5000;
// Same shape the API accepts (backend/services/figma.py)
const FIGMA_LINK = /^https:\/\/(www\.)?figma\.com\/(design|file|proto)\/[A-Za-z0-9]{10,64}/;

type Job = { id: string; ticket: string; status: string; result?: unknown; href: string };
type Credits = components["schemas"]["Credits"];

/** Start a run for a Jira ticket, on the demo project or the user's own, then open its
 * live run window. */
export function StartRun() {
  const router = useRouter();
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [demo, setDemo] = useState<Project | null>(null);
  const { project: own } = useOwnProject();
  const [choice, setChoice] = useState<"own" | "demo" | null>(null); // null = not picked yet
  const useOwn = own?.ready === true && choice !== "demo"; // your project once it's set up
  const project = useOwn && own ? ownLinks(own) : demo;
  const [credits, setCredits] = useState<Credits | null>(null);
  const outOfRuns = credits?.left === 0;

  useEffect(() => {
    api.GET("/project").then(({ data }) => data && setDemo(data));
    api.GET("/me/credits").then(({ data }) => data && setCredits(data));
  }, []);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setPending(true);
    const form = new FormData(event.currentTarget);
    const ticket = String(form.get("ticket")).trim().toUpperCase();
    const figmaUrl = String(form.get("figma_url") ?? "").trim();
    const projectId = useOwn ? (own?.project_id ?? null) : null;
    const { data, error, response } = await api.POST("/runs", {
      body: {
        ticket,
        approve_plan: form.get("approve_plan") === "on",
        figma_url: figmaUrl,
        project_id: projectId,
      },
    });
    setPending(false);
    if (!data) {
      const detail = (error as { detail?: unknown } | undefined)?.detail;
      setError(
        typeof detail === "string" // our own checks: wrong project, not set up, daily limit
          ? `${detail[0]?.toUpperCase()}${detail.slice(1)}.`
          : response.status === 422
            ? figmaUrl && !FIGMA_LINK.test(figmaUrl)
              ? "That doesn't look like a Figma design link. Copy it from Figma's Share button."
              : `That doesn't look like a ticket key. Use the form ${keyHint(project)}.`
            : response.status === 401
              ? "Your login expired. Refresh the page and try again."
              : "Couldn't start the run. Please try again.",
      );
      return;
    }
    setCredits((c) => (c?.left ? { ...c, left: c.left - 1 } : c));
    const href = runHref({ ticket, project_id: projectId ?? 0, demo: projectId === null });
    setJob({ id: data.job_id, ticket, status: "PENDING", href });
    router.push(href); // watch it live
  }

  const running = job !== null && !["SUCCESS", "FAILURE"].includes(job.status);
  const jobId = job?.id;

  useEffect(() => {
    if (!jobId || !running) return;
    const timer = setInterval(async () => {
      const { data } = await api.GET("/jobs/{job_id}", { params: { path: { job_id: jobId } } });
      if (data)
        setJob((current) => current && { ...current, status: data.status, result: data.result });
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [jobId, running]);

  return (
    <Card tone="sky" className="h-fit">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-display text-2xl">Start a run</h2>
        {credits?.left != null && (
          <Chip tone={outOfRuns ? "rose" : "mint"}>
            {credits.left} of {credits.total} free runs left
          </Chip>
        )}
      </header>
      <p className="mt-1 text-sm text-muted">
        Enter a Jira ticket. The agents read it, plan, build, test and open a pull request.
      </p>
      {own?.ready && (
        <fieldset className="mt-4 grid grid-cols-2 gap-1 rounded-2xl border-ink-line bg-canvas p-1 text-sm">
          <legend className="sr-only">Project</legend>
          {(["own", "demo"] as const).map((value) => (
            <label
              key={value}
              className={`flex min-h-10 cursor-pointer items-center justify-center rounded-xl px-3 font-semibold transition has-focus-visible:outline-3 has-focus-visible:outline-accent ${
                (value === "own") === useOwn ? "bg-ink text-canvas" : "text-muted hover:text-ink"
              }`}
            >
              <input
                type="radio"
                name="project"
                value={value}
                checked={(value === "own") === useOwn}
                onChange={() => setChoice(value)}
                className="sr-only"
              />
              {value === "own" ? "Your project" : "Demo"}
            </label>
          ))}
        </fieldset>
      )}
      {project && <ProjectCard project={project} />}
      <form onSubmit={onSubmit} className="mt-5 space-y-3">
        <input
          name="ticket"
          required
          placeholder={`Ticket key, e.g. ${keyHint(project)}`}
          autoComplete="off"
          className={`${INPUT} w-full`}
        />
        <div>
          <input
            name="figma_url"
            type="url"
            placeholder="Figma design link (optional)"
            autoComplete="off"
            aria-describedby="figma-help"
            className={`${INPUT} w-full`}
          />
          <p id="figma-help" className="mt-1 text-xs text-muted">
            For screens: the agents build the page to match this frame. Share the file as
            &ldquo;Anyone with the link can view&rdquo;.
          </p>
        </div>
        <label className="flex min-h-11 items-center gap-2 text-sm">
          <input type="checkbox" name="approve_plan" className="size-5 accent-ink" />
          Pause for me to approve the plan
        </label>
        <FormError message={error} />
        {outOfRuns && (
          <p className="text-sm text-muted">
            You&apos;ve used your free runs. You can still watch any run, and the{" "}
            <Link
              href="/runs/sample"
              className="font-semibold text-ink underline underline-offset-2"
            >
              replay
            </Link>
            .
          </p>
        )}
        <Button type="submit" disabled={pending || running || outOfRuns} className="w-full">
          {pending ? "Starting…" : running ? "Run in progress…" : "Start run"}
        </Button>
      </form>
      {job && (
        <aside
          aria-live="polite"
          className="mt-4 rounded-2xl border-ink-line bg-canvas p-3 text-sm"
        >
          <p className="flex flex-wrap items-center gap-2">
            <Chip tone="butter" mono>
              {job.ticket}
            </Chip>
            <span className="text-muted">{describe(job)}</span>
          </p>
          <ButtonLink href={job.href} size="sm" className="mt-3">
            Watch it live →
          </ButtonLink>
        </aside>
      )}
    </Card>
  );
}

function describe(job: Job): string {
  if (job.status === "FAILURE") return `failed (${String(job.result)})`;
  if (job.status === "SUCCESS") return `finished: ${String(job.result).replaceAll("_", " ")}`;
  if (job.status === "STARTED") return "running…";
  return "queued…";
}

function keyHint(project: Project | null): string {
  return `${project?.jira_project ?? "KAN"}-12`;
}

/** The same links as the API gives for the demo, for the user's own project. */
function ownLinks(own: OwnProjectState): Project {
  const repo = own.github?.repo ?? null;
  const site = own.jira?.site ?? null;
  const key = own.jira?.project_key ?? null;
  return {
    repo,
    repo_url: repo ? `https://github.com/${repo}` : null,
    jira_site: site,
    jira_project: key,
    board_url: site && key ? `${site}/jira/software/projects/${key}/boards` : null,
  };
}

/** Which repo and Jira project runs work on, with links to both. */
function ProjectCard({ project }: { project: Project }) {
  return (
    <dl className="mt-4 grid grid-cols-[4.5rem_1fr] gap-y-1.5 rounded-2xl border-ink-line bg-canvas p-3 text-xs">
      <dt className="text-muted">GitHub</dt>
      <dd className="truncate">
        {project.repo_url ? (
          <a
            href={project.repo_url}
            target="_blank"
            rel="noreferrer"
            className="text-ink hover:underline"
          >
            {project.repo} ↗
          </a>
        ) : (
          "not set"
        )}
      </dd>
      <dt className="text-muted">Jira</dt>
      <dd className="truncate">
        {project.board_url ? (
          <a
            href={project.board_url}
            target="_blank"
            rel="noreferrer"
            className="text-ink hover:underline"
          >
            {project.jira_project} board ↗
          </a>
        ) : (
          (project.jira_project ?? "not set")
        )}
        {project.jira_site && (
          <span className="text-muted"> · {new URL(project.jira_site).hostname}</span>
        )}
      </dd>
    </dl>
  );
}
