import { TONE_BG } from "@/components/ui/tone";
import { agentTone } from "@/lib/agents";
import type { Stage, StageStatus } from "@/lib/runs/stages";

const ICON: Record<StageStatus, string> = {
  waiting: "○",
  running: "●",
  done: "✓",
  failed: "✕",
  paused: "❚❚",
};

/** The five boxes, top to bottom: the one at work wears its agent's colour and lifts. */
export function Pipeline({ stages }: { stages: Stage[] }) {
  return (
    <ol className="space-y-3" aria-label="Pipeline">
      {stages.map((stage) => (
        <li
          key={stage.name}
          className={`flex items-center gap-3 rounded-2xl px-4 py-3 transition ${look(stage)}`}
        >
          <span
            aria-hidden
            className={`w-5 text-center text-sm ${stage.status === "running" ? "animate-pulse" : ""} ${
              stage.status === "done" ? "text-ok" : ""
            }`}
          >
            {ICON[stage.status]}
          </span>
          <span className="flex-1">
            <span className="block font-semibold">{stage.name}</span>
            {stage.note && <span className="block text-xs text-muted">{stage.note}</span>}
          </span>
          <span className="sr-only">{stage.status}</span>
        </li>
      ))}
    </ol>
  );
}

function look(stage: Stage): string {
  switch (stage.status) {
    case "running":
      return `border-ink-line shadow-hard-sm -translate-px ${TONE_BG[agentTone(stage.role)]}`;
    case "paused":
      return "border-ink-line bg-butter";
    case "failed":
      return "border-ink-line bg-rose";
    case "done":
      return "border-ink-line bg-surface";
    default:
      return "border-[1.5px] border-dashed border-ink/30 text-muted";
  }
}
