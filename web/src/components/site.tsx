/** The pieces every page shares: wordmark, top nav, footer, buttons. */

import Link from "next/link";
import type { ReactNode } from "react";

import { NavAuth } from "@/components/nav-auth";
import { NavPill } from "@/components/ui/nav-pill";

const REPO_URL = "https://github.com/skher9/multi-agent-system";

const DOTS = ["bg-butter", "bg-lilac", "bg-mint"];

/** The mark: three overlapping dots, one per kind of work, then the name. */
export function Logo({ href = "/", short = false }: { href?: string; short?: boolean }) {
  return (
    <Link
      href={href}
      aria-label={short ? "Agent Dev Team" : undefined}
      className="inline-flex items-center gap-3 font-display text-xl whitespace-nowrap"
    >
      <span aria-hidden className="flex">
        {DOTS.map((dot) => (
          <span
            key={dot}
            className={`-ml-2 size-6 rounded-full border-ink-line first:ml-0 ${dot}`}
          />
        ))}
      </span>
      {!short && "Agent Dev Team"}
    </Link>
  );
}

const PUBLIC_LINKS = [
  { href: "/#how", label: "How it works" },
  { href: "/#results", label: "Results" },
  { href: "/runs/sample", label: "Watch a run" },
];

export function SiteNav({ children }: { children?: ReactNode }) {
  return (
    <header className="sticky top-0 z-10 bg-canvas/90 backdrop-blur">
      <nav className="mx-auto flex max-w-6xl flex-wrap items-center gap-4 px-4 py-3">
        <Logo />
        {children ?? (
          <>
            <ul className="ml-4 hidden gap-2 md:flex">
              {PUBLIC_LINKS.map((link) => (
                <li key={link.href}>
                  <NavPill href={link.href}>{link.label}</NavPill>
                </li>
              ))}
            </ul>
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
    <footer className="mt-auto border-t-[1.5px] border-dashed border-ink/20">
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
