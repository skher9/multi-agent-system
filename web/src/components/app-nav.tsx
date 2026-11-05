"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Suspense } from "react";

import { Button } from "@/components/button";
import { authClient } from "@/lib/auth-client";

const LINKS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/runs", label: "Runs" },
  { href: "/settings", label: "Settings" },
];

/** The top bar on every logged-in page: the same links everywhere, the current one lit.
 * It reads the address (usePathname), which on dynamic pages exists only per request,
 * so it renders inside <Suspense> with a plain bar until then. */
export function AppNav() {
  return (
    <Suspense
      fallback={<header className="sticky top-0 z-10 h-14 border-b border-line/60 bg-canvas/80" />}
    >
      <AppNavBar />
    </Suspense>
  );
}

function AppNavBar() {
  const pathname = usePathname();
  const router = useRouter();
  const { data: session } = authClient.useSession();

  const active = (href: string) =>
    href === "/runs"
      ? pathname === "/runs" || /^\/runs\/(?!sample$)/.test(pathname)
      : pathname === href;

  return (
    <header className="sticky top-0 z-10 border-b border-line/60 bg-canvas/80 backdrop-blur">
      <nav className="mx-auto flex h-14 max-w-6xl items-center gap-4 px-4 sm:gap-6">
        <Link href="/dashboard" className="flex items-center gap-2 font-semibold tracking-tight">
          <span
            aria-hidden
            className="grid size-6 place-items-center rounded-md bg-accent font-mono text-xs text-accent-ink"
          >
            ▲
          </span>
          <span className="hidden sm:inline">Agent Dev Team</span>
        </Link>
        <div className="flex gap-1 text-sm">
          {LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              aria-current={active(link.href) ? "page" : undefined}
              className={`rounded-md px-2.5 py-1.5 transition ${
                active(link.href) ? "bg-raised text-ink" : "text-muted hover:text-ink"
              }`}
            >
              {link.label}
            </Link>
          ))}
        </div>
        <div className="ml-auto flex items-center gap-3">
          {session && (
            <span className="hidden max-w-48 truncate text-sm text-muted md:inline">
              {session.user.email}
            </span>
          )}
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={async () => {
              await authClient.signOut();
              router.push("/");
              router.refresh();
            }}
          >
            Log out
          </Button>
        </div>
      </nav>
    </header>
  );
}
