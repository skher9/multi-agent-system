"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { FormError, INPUT } from "@/components/auth-form";
import { Button } from "@/components/site";
import { api } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

type Project = components["schemas"]["ProjectLinks"];

const POLL_MS = 5000;
// Same shape the API accepts (backend/services/figma.py)
const FIGMA_LINK = /^https:\/\/(www\.)?figma\.com\/(design|file|proto)\/[A-Za-z0-9]{10,64}/;

type Job = { id: string; ticket: string; status: string; result?: unknown };

/** Start a run for a Jira ticket, then open its live run window. */
export function StartRun() {
  const router = useRouter();
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [project, setProject] = useState<Project | null>(null);

  useEffect(() => {
    api.GET("/project").then(({ data }) => data && setProject(data));
  }, []);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setPending(true);
    const form = new FormData(event.currentTarget);
    const ticket = String(form.get("ticket")).trim().toUpperCase();
    const figmaUrl = String(form.get("figma_url") ?? "").trim();
    const { data, response } = await api.POST("/runs", {
      body: { ticket, approve_plan: form.get("approve_plan") === "on", figma_url: figmaUrl },
    });
    setPending(false);
    if (!data) {
      setError(
        response.status === 422
          ? figmaUrl && !FIGMA_LINK.test(figmaUrl)
            ? "That doesn't look like a Figma design link. Copy it from Figma's Share button."
            : "That doesn't look like a ticket key. Use the form KAN-12."
          : response.status === 401
            ? "Your login expired. Refresh the page and try again."
            : "Couldn't start the run. Please try again.",
      );
      return;
    }
    setJob({ id: data.job_id, ticket, status: "PENDING" });
    router.push(`/runs/${ticket}`); // watch it live
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
    <section className="h-fit rounded-lg border border-line bg-surface p-5">
      <h2 className="font-display text-2xl">Start a run</h2>
      <p className="mt-1 text-sm text-muted">
        Enter a Jira ticket. The agents read it, plan, build, test and open a pull request.
      </p>
      {project && <ProjectCard project={project} />}
      <form onSubmit={onSubmit} className="mt-5 space-y-3">
        <input
          name="ticket"
          required
          placeholder="Ticket key, e.g. KAN-12"
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
        <label className="flex items-center gap-2 text-sm text-muted">
          <input type="checkbox" name="approve_plan" className="accent-accent" />
          Pause for me to approve the plan
        </label>
        <FormError message={error} />
        <Button type="submit" disabled={pending || running} className="w-full">
          {pending ? "Starting…" : running ? "Run in progress…" : "Start run"}
        </Button>
      </form>
      {job && (
        <div className="mt-4 rounded-md border border-line bg-canvas p-3 text-sm">
          <p>
            <span className="font-mono">{job.ticket}</span>
            <span className="text-muted"> · {describe(job)}</span>
          </p>
          <a
            href={`/runs/${job.ticket}`}
            className="mt-1 inline-block text-xs text-accent hover:underline"
          >
            Watch it live →
          </a>
        </div>
      )}
    </section>
  );
}

function describe(job: Job): string {
  if (job.status === "FAILURE") return `failed (${String(job.result)})`;
  if (job.status === "SUCCESS") return `finished: ${String(job.result).replaceAll("_", " ")}`;
  if (job.status === "STARTED") return "running…";
  return "queued…";
}

/** Which repo and Jira project runs work on, with links to both. */
function ProjectCard({ project }: { project: Project }) {
  return (
    <dl className="mt-4 grid grid-cols-[4.5rem_1fr] gap-y-1.5 rounded-md border border-line bg-canvas p-3 text-xs">
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
