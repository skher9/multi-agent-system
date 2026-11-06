/** Buttons and button-styled links, in the site's two looks. */

import Link from "next/link";
import type { ComponentProps } from "react";

const BUTTON = {
  primary: "bg-ink text-canvas hover:bg-accent hover:text-accent-ink",
  ghost: "border border-ink/15 bg-transparent text-ink hover:border-ink/40 hover:bg-surface",
  danger: "bg-bad text-canvas hover:brightness-110",
};
const SIZE = { sm: "h-8 px-3 text-sm", md: "h-11 px-5" };

type Look = { variant?: keyof typeof BUTTON; size?: keyof typeof SIZE };

function buttonClass({ variant = "primary", size = "md" }: Look, extra = "") {
  return `inline-flex items-center justify-center gap-2 rounded-md font-medium transition disabled:opacity-50 ${BUTTON[variant]} ${SIZE[size]} ${extra}`;
}

export function ButtonLink({
  variant,
  size,
  className,
  ...props
}: ComponentProps<typeof Link> & Look) {
  return <Link {...props} className={buttonClass({ variant, size }, className)} />;
}

export function Button({ variant, size, className, ...props }: ComponentProps<"button"> & Look) {
  return <button {...props} className={buttonClass({ variant, size }, className)} />;
}
