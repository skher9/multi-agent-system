/**
 * Typed API client. Paths, request bodies, and responses all come from
 * schema.d.ts, which is generated from the FastAPI OpenAPI spec.
 *
 * After changing the backend API, regenerate: pnpm gen:api
 */
import createClient from "openapi-fetch";

import type { components, paths } from "./schema";

export const api = createClient<paths>({
  baseUrl: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
});

export type HealthReport = components["schemas"]["HealthReport"];
export type ServiceStatus = components["schemas"]["ServiceStatus"];
