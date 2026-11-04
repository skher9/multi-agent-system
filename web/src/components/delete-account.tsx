"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { FormError } from "@/components/auth-form";
import { Button } from "@/components/site";
import { authClient } from "@/lib/auth-client";

/** Deletes the account after a second click. Better Auth wants a login from the last day. */
export function DeleteAccount() {
  const router = useRouter();
  const [confirming, setConfirming] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  async function remove() {
    setError("");
    setPending(true);
    const { error } = await authClient.deleteUser();
    setPending(false);
    if (error?.code === "SESSION_EXPIRED") {
      setError("For safety, log out and log in again, then delete your account.");
      return;
    }
    if (error) {
      setError(error.message ?? "Couldn't delete your account. Please try again.");
      return;
    }
    router.push("/");
    router.refresh();
  }

  if (!confirming) {
    return (
      <Button type="button" variant="ghost" size="sm" onClick={() => setConfirming(true)}>
        Delete account
      </Button>
    );
  }

  return (
    <div className="space-y-3">
      <p className="text-sm text-ink">
        This deletes your account and logins for good. It can&apos;t be undone.
      </p>
      <div className="flex gap-2">
        <Button type="button" variant="danger" size="sm" disabled={pending} onClick={remove}>
          {pending ? "Deleting…" : "Yes, delete my account"}
        </Button>
        <Button type="button" variant="ghost" size="sm" onClick={() => setConfirming(false)}>
          Cancel
        </Button>
      </div>
      <FormError message={error} />
    </div>
  );
}
