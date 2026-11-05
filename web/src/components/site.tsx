/** The pieces every page shares: logo, top nav, footer, buttons. */

import Link from "next/link";
import type { ReactNode } from "react";

import { NavAuth } from "@/components/nav-auth";

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
              <NavAuth />
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
        <span className="flex gap-4">
          <Link href="/privacy" className="hover:text-ink">
            Privacy
          </Link>
          <Link href="/terms" className="hover:text-ink">
            Terms
          </Link>
        </span>
      </div>
    </footer>
  );
}

export { Button, ButtonLink } from "@/components/button";
