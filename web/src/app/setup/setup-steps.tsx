"use client";

import { ButtonLink } from "@/components/button";
import { OwnProject, type OwnProjectState } from "@/components/own-project";

/** Jira, then GitHub, then a way back to the dashboard once both are in. */
export function SetupSteps() {
  return (
    <div className="mt-8 space-y-6">
      <OwnProject numbered after={(project) => <Done project={project} />} />
      <section className="border-t border-line pt-6 text-sm text-muted">
        <h2 className="font-medium text-ink">What agents can do with these</h2>
        <ul className="mt-2 list-disc space-y-1 pl-5">
          <li>Read the ticket you start a run on, comment on it, and add subtasks under it.</li>
          <li>Clone the repo, push one branch per ticket and open a pull request.</li>
          <li>Nothing is merged for you: every pull request waits for your review.</li>
        </ul>
        <p className="mt-3">
          Disconnect any time in Settings. We delete our copy of the token at once.
        </p>
      </section>
    </div>
  );
}

function Done({ project }: { project: OwnProjectState }) {
  if (!project.ready) return null;
  return (
    <div className="flex flex-wrap items-center gap-4 rounded-lg border border-ok/40 bg-surface p-5">
      <p className="text-sm">
        You&apos;re set up. Start a run on{" "}
        <span className="font-mono text-xs">{project.github?.repo}</span> from the dashboard.
      </p>
      <ButtonLink href="/dashboard" size="sm" className="ml-auto">
        Go to the dashboard
      </ButtonLink>
    </div>
  );
}
