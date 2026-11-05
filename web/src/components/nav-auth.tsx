"use client";

import Link from "next/link";

import { ButtonLink } from "@/components/button";
import { authClient } from "@/lib/auth-client";

/** The public top bar's right side: Log in / Try it, or Go to dashboard when logged in. */
export function NavAuth() {
  const { data: session, isPending } = authClient.useSession();
  if (isPending) return <span className="h-8 w-28" aria-hidden />;
  if (session) {
    return (
      <ButtonLink href="/dashboard" size="sm">
        Go to dashboard
      </ButtonLink>
    );
  }
  return (
    <>
      <Link href="/login" className="text-sm text-muted hover:text-ink">
        Log in
      </Link>
      <ButtonLink href="/signup" size="sm">
        Try it
      </ButtonLink>
    </>
  );
}
