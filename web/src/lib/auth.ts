/**
 * Login (Better Auth), on the server. Users and sessions live in our Postgres, in
 * tables created by a backend Alembic migration (backend/db/auth_tables.py).
 *
 * Ways in: email + password, Google, GitHub. A provider is on only when its keys are
 * set, so local dev works without them. New email accounts must confirm their address,
 * and forgotten passwords get a reset link, both by email.
 *
 * The jwt plugin lets the Python API trust a logged-in user without seeing the session:
 * the browser asks /api/auth/token for a short-lived signed token, and the API checks
 * its signature against the public keys at /api/auth/jwks.
 */
import { betterAuth } from "better-auth";
import { nextCookies } from "better-auth/next-js";
import { jwt } from "better-auth/plugins";
import { after } from "next/server";
import { Pool } from "pg";

import { sendEmail } from "@/lib/email";

export type SocialProvider = "google" | "github";

const google = keys("GOOGLE");
const github = keys("GITHUB");

function keys(prefix: string) {
  const clientId = process.env[`${prefix}_CLIENT_ID`];
  const clientSecret = process.env[`${prefix}_CLIENT_SECRET`];
  return clientId && clientSecret ? { clientId, clientSecret } : undefined;
}

/** The social logins whose keys are set, for the login page's buttons. */
export function enabledProviders(): SocialProvider[] {
  return [google && "google", github && "github"].filter(Boolean) as SocialProvider[];
}

export const auth = betterAuth({
  database: new Pool({ connectionString: process.env.DATABASE_URL }),
  // Better Auth's own limits (e.g. 3 sign-in tries per 10 s, 3 reset emails a minute),
  // counted in Postgres: in memory, each Vercel instance would keep its own count.
  rateLimit: { storage: "database" },
  emailVerification: {
    sendOnSignUp: true,
    sendOnSignIn: true, // an unverified login gets a fresh link
    autoSignInAfterVerification: true,
    sendVerificationEmail: async ({ user, url }) => {
      after(() =>
        sendEmail({
          to: user.email,
          subject: "Confirm your Agent Dev Team email",
          text: `Confirm your email with this link (valid for 1 hour):\n${url}\n\nDidn't sign up? Ignore this email.`,
          html: `<p>Confirm your email with this link (valid for 1 hour):</p><p><a href="${url}">Confirm email</a></p><p>Didn't sign up? Ignore this email.</p>`,
        }),
      );
    },
  },
  user: {
    // Deletes the user; their sessions and linked logins go with them (on delete cascade).
    // Needs a recent login (Better Auth's freshAge, 1 day) or the account password.
    deleteUser: { enabled: true },
  },
  emailAndPassword: {
    enabled: true,
    requireEmailVerification: true, // no session until the email link is clicked
    minPasswordLength: 10,
    revokeSessionsOnPasswordReset: true,
    resetPasswordTokenExpiresIn: 60 * 60, // seconds
    sendResetPassword: async ({ user, url }) => {
      // Sent after the response, so the reply takes the same time whether or not the
      // email exists (Better Auth's advice); after() keeps Vercel running until it's sent.
      after(() =>
        sendEmail({
          to: user.email,
          subject: "Reset your Agent Dev Team password",
          text: `Reset your password with this link (valid for 1 hour):\n${url}\n\nDidn't ask for this? Ignore this email.`,
          html: `<p>Reset your password with this link (valid for 1 hour):</p><p><a href="${url}">Reset password</a></p><p>Didn't ask for this? Ignore this email.</p>`,
        }),
      );
    },
  },
  socialProviders: {
    ...(google && { google: { ...google, prompt: "select_account" as const } }),
    ...(github && { github }),
  },
  plugins: [
    jwt({
      jwt: {
        // Only what the API needs; the default puts the whole user in the token
        definePayload: ({ user }) => ({ email: user.email, name: user.name }),
      },
    }),
    nextCookies(), // must stay last: sets cookies from server actions
  ],
});
