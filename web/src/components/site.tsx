/** The pieces every page shares: wordmark, top nav, footer, buttons. */

import Link from "next/link";
import type { ReactNode } from "react";

import { NavAuth } from "@/components/nav-auth";

const REPO_URL = "https://github.com/skher9/multi-agent-system";

/** The wordmark: set in the serif, with the accent on the one word that matters. */
export function Logo({ href = "/", short = false }: { href?: string; short?: boolean }) {
  return (
    <Link href={href} className="font-display text-xl leading-none whitespace-nowrap">
      {short ? (
        <span aria-label="Agent Dev Team">
          a<span className="text-accent">d</span>t
        </span>
      ) : (
        <>
          Agent <span className="text-accent italic">Dev</span> Team
        </>
      )}
    </Link>
  );
}

export function SiteNav({ children }: { children?: ReactNode }) {
  return (
    <header className="sticky top-0 z-10 border-b border-line bg-canvas/85 backdrop-blur">
      <nav className="mx-auto flex h-14 max-w-6xl items-center gap-6 px-4">
        <Logo />
        {children ?? (
          <>
            <div className="ml-4 hidden gap-6 text-sm text-muted sm:flex">
              <Link href="/#how" className="hover:text-ink">
                How it works
              </Link>
              <Link href="/#results" className="hover:text-ink">
                Results
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
    <footer className="mt-auto border-t border-line">
      <div className="mx-auto grid max-w-6xl gap-8 px-4 py-12 text-sm sm:grid-cols-[1fr_auto_auto]">
        <div>
          <Logo />
          <p className="mt-3 max-w-xs text-muted">
            A portfolio project by Shravani Kher: seven AI agents that turn tickets into tested pull
            requests.
          </p>
        </div>
        <ul className="space-y-2 text-muted">
          <li>
            <a href={REPO_URL} target="_blank" rel="noreferrer" className="hover:text-ink">
              Source code ↗
            </a>
          </li>
          <li>
            <Link href="/runs/sample" className="hover:text-ink">
              Watch a run
            </Link>
          </li>
          <li>
            <Link href="/status" className="hover:text-ink">
              System status
            </Link>
          </li>
        </ul>
        <ul className="space-y-2 text-muted">
          <li>
            <Link href="/privacy" className="hover:text-ink">
              Privacy
            </Link>
          </li>
          <li>
            <Link href="/terms" className="hover:text-ink">
              Terms
            </Link>
          </li>
        </ul>
      </div>
    </footer>
  );
}

export { Button, ButtonLink } from "@/components/button";
