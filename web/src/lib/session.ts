/**
 * The one place pages check who is logged in (Next.js's "data access layer" pattern).
 * cache() runs it once per request, however many components ask.
 */
import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { cache } from "react";

import { auth } from "@/lib/auth";

export const verifySession = cache(async () => {
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session) {
    redirect("/login");
  }
  return session;
});
