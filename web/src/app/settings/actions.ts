"use server";

import { APIError } from "better-auth/api";
import { headers } from "next/headers";

import { auth, providerKeys, type SocialProvider } from "@/lib/auth";

/** Disconnect a Google or GitHub login: delete our copy of its tokens, then revoke the
 * grant at the provider so the access is really given back, not just forgotten here.
 * Better Auth refuses to remove the last way to log in, and asks for a recent login. */
export async function disconnect(accountId: string): Promise<{ error?: string }> {
  const requestHeaders = await headers();
  const accounts = await auth.api.listUserAccounts({ headers: requestHeaders });
  const account = accounts.find((a) => a.id === accountId);
  if (!account || (account.providerId !== "google" && account.providerId !== "github"))
    return { error: "That connection doesn't exist any more. Refresh the page." };
  const provider = account.providerId as SocialProvider;

  // Read the token before the row holding it is deleted
  let token: string | undefined;
  try {
    token = (await auth.api.getAccessToken({ body: { accountId }, headers: requestHeaders }))
      .accessToken;
  } catch {
    token = undefined; // expired and not refreshable: nothing left to revoke
  }

  try {
    await auth.api.unlinkAccount({ body: { accountId }, headers: requestHeaders });
  } catch (error) {
    if (error instanceof APIError && error.body?.code === "FAILED_TO_UNLINK_LAST_ACCOUNT")
      return { error: "This is your only way to log in. Connect another one first." };
    if (error instanceof APIError && error.body?.code === "SESSION_NOT_FRESH")
      return { error: "For your safety, log out and back in, then try again." };
    return { error: "Couldn't disconnect it. Please try again." };
  }

  if (token) await revoke(provider, token); // best effort: our copy is already gone
  return {};
}

async function revoke(provider: SocialProvider, token: string): Promise<void> {
  const keys = providerKeys(provider);
  try {
    if (provider === "google") {
      // https://developers.google.com/identity/protocols/oauth2/web-server#tokenrevoke
      await fetch("https://oauth2.googleapis.com/revoke", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({ token }),
      });
    } else if (keys) {
      // Deletes the whole grant, so GitHub lists the app as no longer authorised.
      // https://docs.github.com/en/rest/apps/oauth-applications#delete-an-app-authorization
      await fetch(`https://api.github.com/applications/${keys.clientId}/grant`, {
        method: "DELETE",
        headers: {
          Accept: "application/vnd.github+json",
          Authorization: `Basic ${Buffer.from(`${keys.clientId}:${keys.clientSecret}`).toString("base64")}`,
        },
        body: JSON.stringify({ access_token: token }),
      });
    }
  } catch {
    // Network trouble: the login is already removed here; the user can also revoke it
    // in their Google or GitHub settings
  }
}
