/** Where a run stands: one pip per pipeline box, filled in that box's agent colour, the
 * current one blinking while the run works on it. */

import { agentTone } from "@/lib/agents";
import { STAGES, stageOf } from "@/lib/runs/stages";

import { TONE_BG } from "./tone";

export function StagePips({
  node,
  finished,
  live,
}: {
  node: string | null;
  finished: boolean;
  live: boolean;
}) {
  const current = finished ? STAGES.length : Math.max(stageOf(node), 0);
  return (
    <ol
      className="flex gap-1"
      aria-label={`Stage ${Math.min(current + 1, STAGES.length)} of ${STAGES.length}`}
    >
      {STAGES.map((stage, i) => {
        const done = i < current;
        const now = i === current && !finished;
        return (
          <li
            key={stage.name}
            title={stage.name}
            className={`h-2.5 w-6 rounded-full border-ink-line ${
              done || now ? TONE_BG[agentTone(stage.role)] : "bg-surface"
            } ${now && live ? "animate-blink" : ""}`}
          />
        );
      })}
    </ol>
  );
}
