/** A small pill for a status, a ticket key or a label. */

import type { ComponentProps } from "react";

import { TONE_BG, type Tone } from "./tone";

export function Chip({
  tone = "plain",
  mono = false,
  className = "",
  ...props
}: ComponentProps<"span"> & { tone?: Tone; mono?: boolean }) {
  return (
    <span
      {...props}
      className={`inline-flex items-center gap-1.5 rounded-full border-ink-line px-3 py-0.5 text-[13px] font-medium ${TONE_BG[tone]} ${mono ? "font-mono" : ""} ${className}`}
    />
  );
}
