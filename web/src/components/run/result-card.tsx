import type { RunEvent, RunView } from "@/lib/runs/types";

/** How the run ended, and what to do next. Shown once the run stops. */
export function ResultCard({ run, events }: { run: RunView; events: RunEvent[] }) {
  const end = [...events]
    .reverse()
    .find((e) => ["run_ended", "run_failed", "run_paused"].includes(e.kind));
  if (!end) return null;
  const outcome = String(end.data.outcome ?? "");
  const card =
    end.kind === "run_failed"
      ? { tone: "bad", title: "The run failed", text: `Error: ${String(end.data.error)}` }
      : end.kind === "run_paused"
        ? {
            tone: "warn",
            title: "The plan is waiting for your approval",
            text: "It's posted on the Jira ticket. Approve, revise or reject it there.",
          }
        : outcome === "ready_to_merge"
          ? {
              tone: "good",
              title: "Pull request ready",
              text: "Built, tested and approved by the reviewer. Review it and merge.",
            }
          : outcome === "blocked"
            ? {
                tone: "warn",
                title: "The agents need answers",
                text: "Questions are posted on the Jira ticket. Answer them and run it again.",
              }
            : {
                tone: "warn",
                title: "A person needs to look",
                text: "The details are on the Jira ticket and the pull request.",
              };
  const color = {
    good: "border-accent/40 bg-accent/10",
    warn: "border-warn/40 bg-warn/8",
    bad: "border-bad/40 bg-bad/8",
  }[card.tone];
  return (
    <div className={`flex flex-wrap items-center gap-4 rounded-lg border px-4 py-3 ${color}`}>
      <div className="mr-auto">
        <p className="font-medium text-ink">{card.title}</p>
        <p className="text-sm text-muted">{card.text}</p>
      </div>
      {run.prUrl && (
        <a
          href={run.prUrl}
          target="_blank"
          rel="noreferrer"
          className="rounded-lg bg-accent px-3 py-2 text-sm font-medium text-accent-ink hover:brightness-110"
        >
          Open the pull request ↗
        </a>
      )}
      {run.links?.ticketUrl && (
        <a
          href={run.links.ticketUrl}
          target="_blank"
          rel="noreferrer"
          className="rounded-lg border border-line px-3 py-2 text-sm text-ink hover:border-muted/60"
        >
          Jira ticket ↗
        </a>
      )}
    </div>
  );
}
