import { ButtonLink } from "@/components/button";
import { Card } from "@/components/ui/card";
import type { Tone } from "@/components/ui/tone";
import type { RunEvent, RunView } from "@/lib/runs/types";

/** How the run ended, and what to do next. Shown once the run stops. */
export function ResultCard({ run, events }: { run: RunView; events: RunEvent[] }) {
  const end = [...events]
    .reverse()
    .find((e) => ["run_ended", "run_failed", "run_paused"].includes(e.kind));
  if (!end) return null;
  const outcome = String(end.data.outcome ?? "");
  const card: { tone: Tone; title: string; text: string } =
    end.kind === "run_failed"
      ? { tone: "rose", title: "The run failed", text: `Error: ${String(end.data.error)}` }
      : end.kind === "run_paused"
        ? {
            tone: "butter",
            title: "The plan is waiting for your approval",
            text: "It's posted on the Jira ticket. Approve, revise or reject it there.",
          }
        : outcome === "ready_to_merge"
          ? {
              tone: "mint",
              title: "Pull request ready",
              text: "Built, tested and approved by the reviewer. Review it and merge.",
            }
          : outcome === "blocked"
            ? {
                tone: "butter",
                title: "The agents need answers",
                text: "Questions are posted on the Jira ticket. Answer them and run it again.",
              }
            : {
                tone: "butter",
                title: "A person needs to look",
                text: "The details are on the Jira ticket and the pull request.",
              };
  return (
    <Card
      as="aside"
      tone={card.tone}
      aria-label="How the run ended"
      className="flex flex-wrap items-center gap-4 py-5! sm:py-5!"
    >
      <header className="mr-auto">
        <h2 className="font-display text-xl">{card.title}</h2>
        <p className="text-sm text-muted">{card.text}</p>
      </header>
      {run.prUrl && (
        <ButtonLink href={run.prUrl} target="_blank" rel="noreferrer">
          Open the pull request ↗
        </ButtonLink>
      )}
      {run.links?.ticketUrl && (
        <ButtonLink href={run.links.ticketUrl} target="_blank" rel="noreferrer" variant="ghost">
          Jira ticket ↗
        </ButtonLink>
      )}
    </Card>
  );
}
