"use client";

import { useEffect, useState, type FormEvent } from "react";

import { FormError, INPUT } from "@/components/auth-form";
import { Button } from "@/components/site";
import { api } from "@/lib/api/client";

const POLL_MS = 5000;

type Job = { id: string; ticket: string; status: string; result?: unknown };

/** Start a run for a Jira ticket and follow it until it ends. */
export function StartRun() {
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setPending(true);
    const form = new FormData(event.currentTarget);
    const ticket = String(form.get("ticket")).trim().toUpperCase();
    const { data, response } = await api.POST("/runs", {
      body: { ticket, approve_plan: form.get("approve_plan") === "on" },
    });
    setPending(false);
    if (!data) {
      setError(
        response.status === 422
          ? "That doesn't look like a ticket key. Use the form KAN-12."
          : response.status === 401
            ? "Your login expired. Refresh the page and try again."
            : "Couldn't start the run. Please try again.",
      );
      return;
    }
    setJob({ id: data.job_id, ticket, status: "PENDING" });
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
    <section className="h-fit rounded-2xl border border-line bg-surface p-5">
      <h2 className="font-medium">Start a run</h2>
      <p className="mt-1 text-sm text-muted">
        Enter a Jira ticket. The agents read it, plan, build, test and open a pull request.
      </p>
      <form onSubmit={onSubmit} className="mt-5 space-y-3">
        <input
          name="ticket"
          required
          placeholder="Ticket key, e.g. KAN-12"
          autoComplete="off"
          className={`${INPUT} w-full`}
        />
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
        <div className="mt-4 rounded-lg border border-line bg-canvas p-3 text-sm">
          <p>
            <span className="font-mono">{job.ticket}</span>
            <span className="text-muted"> · {describe(job)}</span>
          </p>
          <p className="mt-1 font-mono text-xs text-muted">job {job.id}</p>
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
