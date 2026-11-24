"use client";

import { usePathname, useRouter } from "next/navigation";
import { Suspense } from "react";

import { Button } from "@/components/button";
import { Logo } from "@/components/site";
import { NavPill } from "@/components/ui/nav-pill";
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
    <Suspense fallback={<header className="sticky top-0 z-10 h-17 bg-canvas/90" />}>
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
    <header className="sticky top-0 z-10 bg-canvas/90 backdrop-blur">
      <nav className="mx-auto flex max-w-6xl flex-wrap items-center gap-4 px-4 py-3">
        <span className="sm:hidden">
          <Logo href="/dashboard" short />
        </span>
        <span className="hidden sm:inline">
          <Logo href="/dashboard" />
        </span>
        <ul className="flex flex-wrap gap-2">
          {LINKS.map((link) => (
            <li key={link.href}>
              <NavPill href={link.href} current={active(link.href)}>
                {link.label}
              </NavPill>
            </li>
          ))}
        </ul>
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
