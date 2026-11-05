/**
 * Typed API client. Paths, request bodies, and responses all come from
 * schema.d.ts, which is generated from the FastAPI OpenAPI spec.
 *
 * Every request carries the logged-in user's API token (`Authorization: Bearer ...`),
 * a 15-minute signed token from Better Auth that the Python API checks (api/auth.py).
 *
 * After changing the backend API, regenerate: pnpm gen:api
 */
import createClient, { type Middleware } from "openapi-fetch";

import type { components, paths } from "./schema";

export const api = createClient<paths>({
  baseUrl: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
});

// Reused for 10 minutes, so most calls don't fetch a new token first
const TOKEN_REUSE_MS = 10 * 60 * 1000;
let cached: { token: string; until: number } | null = null;

async function apiToken(): Promise<string | null> {
  if (cached && cached.until > Date.now()) return cached.token;
  const response = await fetch("/api/auth/token", { credentials: "same-origin" });
  if (!response.ok) return null; // not logged in: the API will answer 401
  const { token } = (await response.json()) as { token: string };
  cached = { token, until: Date.now() + TOKEN_REUSE_MS };
  return token;
}

const withToken: Middleware = {
  async onRequest({ request }) {
    const token = await apiToken();
    if (token) request.headers.set("Authorization", `Bearer ${token}`);
    return request;
  },
};

api.use(withToken);

export type HealthReport = components["schemas"]["HealthReport"];
export type ServiceStatus = components["schemas"]["ServiceStatus"];
