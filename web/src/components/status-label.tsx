import { Chip } from "@/components/ui/chip";
import { type Run, statusOf } from "@/lib/runs/use-runs";

/** A run's status as a coloured pill, with a dot that pulses while it's live. */
export function StatusLabel({ run }: { run: Run }) {
  const status = statusOf(run);
  return (
    <Chip tone={status.tone}>
      {status.live && <span aria-hidden className="size-2 animate-pulse rounded-full bg-ink" />}
      {status.label}
    </Chip>
  );
}
