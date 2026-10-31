/** Login, in the browser: sign up, sign in, sign out, and API tokens. */
import { jwtClient } from "better-auth/client/plugins";
import { createAuthClient } from "better-auth/react";

export const authClient = createAuthClient({ plugins: [jwtClient()] });
