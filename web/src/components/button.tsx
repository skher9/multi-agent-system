/** Buttons and button-styled links, in the site's two looks. */

import Link from "next/link";
import type { ComponentProps } from "react";

const BUTTON = {
  primary: "bg-accent text-accent-ink hover:brightness-110",
  ghost: "border border-line bg-surface text-ink hover:border-muted/60",
  danger: "bg-red-500 text-white hover:bg-red-400",
};
const SIZE = { sm: "h-8 px-3 text-sm", md: "h-11 px-5" };

type Look = { variant?: keyof typeof BUTTON; size?: keyof typeof SIZE };

function buttonClass({ variant = "primary", size = "md" }: Look, extra = "") {
  return `inline-flex items-center justify-center gap-2 rounded-lg font-medium transition disabled:opacity-50 ${BUTTON[variant]} ${SIZE[size]} ${extra}`;
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
