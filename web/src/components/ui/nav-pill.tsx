/** A pill-shaped nav link; the current page is lit and raised. */

import Link from "next/link";
import type { ComponentProps } from "react";

export function NavPill({
  current = false,
  className = "",
  ...props
}: ComponentProps<typeof Link> & { current?: boolean }) {
  return (
    <Link
      {...props}
      aria-current={current ? "page" : undefined}
      className={`inline-flex min-h-11 items-center rounded-full border-ink-line px-4 text-sm font-semibold transition hover:-translate-y-0.5 ${
        current ? "bg-lilac shadow-hard-sm" : "bg-surface"
      } ${className}`}
    />
  );
}
