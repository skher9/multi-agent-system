/** Buttons and button-styled links: an ink outline with a hard shadow that presses in. */

import Link from "next/link";
import type { ComponentProps } from "react";

const VARIANT = {
  primary: "bg-ink text-canvas hover:bg-ink/85",
  ghost: "bg-surface text-ink hover:bg-raised",
  danger: "bg-rose text-ink hover:brightness-95",
};
const SIZE = { sm: "min-h-9 px-3 text-sm", md: "min-h-11 px-5" };

type Look = { variant?: keyof typeof VARIANT; size?: keyof typeof SIZE };

function buttonClass({ variant = "primary", size = "md" }: Look, extra = "") {
  return [
    "inline-flex items-center justify-center gap-2 rounded-[14px] border-ink-line font-semibold",
    "shadow-hard-sm transition hover:-translate-px hover:shadow-hard",
    "active:translate-0.75 active:shadow-none disabled:pointer-events-none disabled:opacity-45",
    VARIANT[variant],
    SIZE[size],
    extra,
  ].join(" ");
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
