// Every Better Auth endpoint (sign up, sign in, sign out, token, jwks) under /api/auth
import { toNextJsHandler } from "better-auth/next-js";

import { auth } from "@/lib/auth";

export const { GET, POST } = toNextJsHandler(auth);
