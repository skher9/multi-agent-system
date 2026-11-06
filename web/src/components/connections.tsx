"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { disconnect } from "@/app/settings/actions";
import { Button } from "@/components/button";
import { authClient } from "@/lib/auth-client";
import type { SocialProvider } from "@/lib/auth";

export type Connection = {
  provider: SocialProvider;
  accountId: string | null; // our account row; null = not connected
  since: string | null;
};

const NAME: Record<SocialProvider, string> = { google: "Google", github: "GitHub" };

/** Google and GitHub logins: connect one, or disconnect it (which also revokes our
 * access at the provider). `logins` counts every way in, password included, so the
 * last one can't be removed. */
export function Connections({
  connections,
  hasPassword,
}: {
  connections: Connection[];
  hasPassword: boolean;
}) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<SocialProvider | null>(null);
  const [, startTransition] = useTransition();
  const logins = connections.filter((c) => c.accountId).length + (hasPassword ? 1 : 0);

  async function connect(provider: SocialProvider) {
    setError("");
    setBusy(provider);
    const { error } = await authClient.linkSocial({ provider, callbackURL: "/settings" });
    if (error) {
      setBusy(null);
      setError(error.message ?? `Couldn't connect ${NAME[provider]}. Please try again.`);
    } // on success the browser goes to the provider and comes back here
  }

  function remove(connection: Connection) {
    if (!connection.accountId) return;
    const accountId = connection.accountId;
    setError("");
    setBusy(connection.provider);
    startTransition(async () => {
      const result = await disconnect(accountId);
      setBusy(null);
      if (result.error) setError(result.error);
      else router.refresh();
    });
  }

  return (
    <div>
      <ul className="divide-y divide-line border-y border-line">
        <li className="flex items-center gap-4 py-3 text-sm">
          <span className="w-20 font-medium">Password</span>
          <span className="text-muted">{hasPassword ? "Set" : "Not set"}</span>
        </li>
        {connections.map((c) => (
          <li key={c.provider} className="flex items-center gap-4 py-3 text-sm">
            <span className="w-20 font-medium">{NAME[c.provider]}</span>
            <span className="text-muted">
              {c.accountId
                ? `Connected${c.since ? ` since ${new Date(c.since).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}` : ""}`
                : "Not connected"}
            </span>
            <span className="ml-auto">
              {c.accountId ? (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  disabled={busy !== null || logins <= 1}
                  title={logins <= 1 ? "Your only way to log in" : undefined}
                  onClick={() => remove(c)}
                >
                  {busy === c.provider ? "Disconnecting…" : "Disconnect"}
                </Button>
              ) : (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  disabled={busy !== null}
                  onClick={() => connect(c.provider)}
                >
                  {busy === c.provider ? "Opening…" : "Connect"}
                </Button>
              )}
            </span>
          </li>
        ))}
      </ul>
      {logins <= 1 && connections.some((c) => c.accountId) && (
        <p className="mt-3 text-xs text-muted">
          This is your only way to log in, so it can&apos;t be disconnected yet.
        </p>
      )}
      {error && (
        <p role="alert" className="mt-3 text-sm text-bad">
          {error}
        </p>
      )}
    </div>
  );
}
