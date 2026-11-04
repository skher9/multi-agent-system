/** The pieces every page shares: logo, top nav, footer, buttons. */

import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";

export function Logo() {
  return (
    <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
      <span
        aria-hidden
        className="grid size-6 place-items-center rounded-md bg-accent font-mono text-xs text-accent-ink"
      >
        ▲
      </span>
      Agent Dev Team
    </Link>
  );
}

export function SiteNav({ children }: { children?: ReactNode }) {
  return (
    <header className="sticky top-0 z-10 border-b border-line/60 bg-canvas/80 backdrop-blur">
      <nav className="mx-auto flex h-14 max-w-6xl items-center gap-6 px-4">
        <Logo />
        {children ?? (
          <>
            <div className="ml-6 hidden gap-6 text-sm text-muted sm:flex">
              <Link href="/#how" className="hover:text-ink">
                How it works
              </Link>
              <Link href="/runs/sample" className="hover:text-ink">
                Watch a run
              </Link>
            </div>
            <div className="ml-auto flex items-center gap-3">
              <Link href="/login" className="text-sm text-muted hover:text-ink">
                Log in
              </Link>
              <ButtonLink href="/signup" size="sm">
                Try it
              </ButtonLink>
            </div>
          </>
        )}
      </nav>
    </header>
  );
}

export function SiteFooter() {
  return (
    <footer className="border-t border-line/60">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-4 py-8 text-sm text-muted">
        <span>Built by Shravani Kher</span>
        <span className="font-mono text-xs">LangGraph · FastAPI · Next.js · Playwright</span>
      </div>
    </footer>
  );
}

const BUTTON = {
  primary: "bg-accent text-accent-ink hover:brightness-110",
  ghost: "border border-line bg-surface text-ink hover:border-muted/60",
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
