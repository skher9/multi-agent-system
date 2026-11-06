import { TONE, type Run, statusOf } from "@/lib/runs/use-runs";

/** A run's status in words, with a dot that pulses while it's live. */
export function StatusLabel({ run }: { run: Run }) {
  const status = statusOf(run);
  return (
    <span className={`inline-flex items-center gap-1.5 ${TONE[status.tone]}`}>
      <span
        aria-hidden
        className={`size-1.5 rounded-full bg-current ${status.tone === "live" ? "animate-pulse" : ""}`}
      />
      {status.label}
    </span>
  );
}
