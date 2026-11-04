"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";

import { AuthShell, Field, FormError, INPUT } from "@/components/auth-form";
import { Button } from "@/components/site";
import { authClient } from "@/lib/auth-client";

export function ResetPasswordForm() {
  const router = useRouter();
  const params = useSearchParams();
  const token = params.get("token");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  // Better Auth sends people here with ?error=INVALID_TOKEN when the link is bad or old
  if (!token || params.get("error")) {
    return (
      <AuthShell
        title="This link doesn't work"
        footer={
          <Link href="/forgot-password" className="text-ink underline-offset-4 hover:underline">
            Get a new link
          </Link>
        }
      >
        <p className="mt-4 text-sm text-muted">
          Reset links work once, for 1 hour. Ask for a new one.
        </p>
      </AuthShell>
    );
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const newPassword = String(form.get("password"));
    if (newPassword !== String(form.get("confirm"))) {
      setError("The two passwords don't match.");
      return;
    }
    setError("");
    setPending(true);
    const { error } = await authClient.resetPassword({ newPassword, token: token ?? "" });
    setPending(false);
    if (error) {
      setError(error.message ?? "Something went wrong. Please try again.");
      return;
    }
    router.push("/login");
  }

  return (
    <AuthShell title="Set a new password">
      <form onSubmit={onSubmit} className="mt-6 flex flex-col gap-4">
        <Field label="New password">
          <input
            name="password"
            type="password"
            required
            minLength={10}
            autoComplete="new-password"
            className={INPUT}
          />
        </Field>
        <Field label="Type it again">
          <input
            name="confirm"
            type="password"
            required
            minLength={10}
            autoComplete="new-password"
            className={INPUT}
          />
        </Field>
        <FormError message={error} />
        <Button type="submit" disabled={pending} className="mt-2 w-full">
          {pending ? "Saving…" : "Save password"}
        </Button>
      </form>
    </AuthShell>
  );
}
