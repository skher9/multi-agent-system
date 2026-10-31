/**
 * Login (Better Auth), on the server. Users and sessions live in our Postgres, in
 * tables created by a backend Alembic migration (backend/db/auth_tables.py).
 *
 * The jwt plugin lets the Python API trust a logged-in user without seeing the session:
 * the browser asks /api/auth/token for a short-lived signed token, and the API checks
 * its signature against the public keys at /api/auth/jwks.
 */
import { betterAuth } from "better-auth";
import { nextCookies } from "better-auth/next-js";
import { jwt } from "better-auth/plugins";
import { Pool } from "pg";

export const auth = betterAuth({
  database: new Pool({ connectionString: process.env.DATABASE_URL }),
  emailAndPassword: { enabled: true, minPasswordLength: 10 },
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
