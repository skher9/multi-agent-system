/** Form pieces every form shares: the input look, a labelled field, an error line. */

import type { ReactNode } from "react";

export const INPUT =
  "min-h-11 rounded-[14px] border-ink-line bg-surface px-3.5 text-[15px] text-ink transition placeholder:text-muted";

export function Field({
  label,
  aside,
  children,
}: {
  label: string;
  aside?: ReactNode;
  children: ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1.5 text-sm font-semibold">
      <span className="flex items-center justify-between">
        {label}
        {aside}
      </span>
      {children}
    </label>
  );
}

export function FormError({ message }: { message: string }) {
  if (!message) return null;
  return (
    <p role="alert" className="rounded-xl border-ink-line bg-rose px-3 py-2 text-sm">
      {message}
    </p>
  );
}
