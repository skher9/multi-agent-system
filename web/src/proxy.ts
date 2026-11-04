/**
 * Optimistic login check (Next.js auth guide): runs before a protected page and sends
 * visitors with no session cookie straight to /login, instead of loading the page frame
 * first. It only looks for the cookie; the real check is still verifySession() in the
 * page, which asks the database.
 */
import { getSessionCookie } from "better-auth/cookies";
import { NextResponse, type NextRequest } from "next/server";

export function proxy(request: NextRequest) {
  if (!getSessionCookie(request)) {
    return NextResponse.redirect(new URL("/login", request.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/dashboard/:path*", "/settings/:path*"],
};
