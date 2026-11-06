import type { Stage, StageStatus } from "@/lib/runs/stages";

const ICON: Record<StageStatus, string> = {
  waiting: "○",
  running: "●",
  done: "✓",
  failed: "✕",
  paused: "❚❚",
};

const STYLE: Record<StageStatus, string> = {
  waiting: "border-line text-muted/70",
  running: "border-accent bg-accent/8 text-ink",
  done: "border-ok/40 text-ink",
  failed: "border-bad/50 bg-bad/8 text-ink",
  paused: "border-warn/50 bg-warn/8 text-ink",
};

const ICON_STYLE: Record<StageStatus, string> = {
  waiting: "",
  running: "animate-pulse text-accent",
  done: "text-ok",
  failed: "text-bad",
  paused: "text-warn",
};

/** The five boxes, top to bottom, each lit by how far the run got. */
export function Pipeline({ stages }: { stages: Stage[] }) {
  return (
    <ol className="space-y-2" aria-label="Pipeline">
      {stages.map((stage) => (
        <li
          key={stage.name}
          className={`flex items-center gap-3 rounded-lg border px-3 py-2.5 transition-colors ${STYLE[stage.status]}`}
        >
          <span aria-hidden className={`w-5 text-center text-sm ${ICON_STYLE[stage.status]}`}>
            {ICON[stage.status]}
          </span>
          <span className="flex-1">
            <span className="block text-sm font-medium">{stage.name}</span>
            {stage.note && <span className="block text-xs opacity-75">{stage.note}</span>}
          </span>
          <span className="sr-only">{stage.status}</span>
        </li>
      ))}
    </ol>
  );
}
