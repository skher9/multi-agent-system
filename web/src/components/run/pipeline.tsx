import type { Stage, StageStatus } from "@/lib/runs/stages";

const ICON: Record<StageStatus, string> = {
  waiting: "○",
  running: "●",
  done: "✓",
  failed: "✕",
  paused: "❚❚",
};

const STYLE: Record<StageStatus, string> = {
  waiting: "border-gray-200 text-gray-400 dark:border-gray-800 dark:text-gray-600",
  running:
    "border-blue-500 bg-blue-50 text-blue-900 dark:border-blue-400 dark:bg-blue-950 dark:text-blue-100",
  done: "border-green-300 text-gray-800 dark:border-green-800 dark:text-gray-200",
  failed:
    "border-red-400 bg-red-50 text-red-900 dark:border-red-700 dark:bg-red-950 dark:text-red-100",
  paused:
    "border-amber-400 bg-amber-50 text-amber-900 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-100",
};

const ICON_STYLE: Record<StageStatus, string> = {
  waiting: "",
  running: "animate-pulse text-blue-600 dark:text-blue-300",
  done: "text-green-600 dark:text-green-400",
  failed: "text-red-600 dark:text-red-400",
  paused: "text-amber-600 dark:text-amber-400",
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
