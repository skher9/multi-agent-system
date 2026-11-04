"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";

import { AuthShell, Field, FormError, INPUT } from "@/components/auth-form";
import { Button } from "@/components/site";
import { authClient } from "@/lib/auth-client";

export function ForgotPasswordForm() {
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setPending(true);
    const email = String(new FormData(event.currentTarget).get("email"));
    const { error } = await authClient.requestPasswordReset({
      email,
      redirectTo: "/reset-password",
    });
    setPending(false);
    if (error) {
      setError(error.message ?? "Something went wrong. Please try again.");
      return;
    }
    setSent(true);
  }

  const back = (
    <Link href="/login" className="text-ink underline-offset-4 hover:underline">
      Back to log in
    </Link>
  );

  if (sent) {
    return (
      <AuthShell title="Check your email" footer={back}>
        {/* Same message whether or not the account exists, so emails can't be probed */}
        <p className="mt-4 text-sm text-muted">
          If an account uses that email, a reset link is on its way. It works for 1 hour.
        </p>
      </AuthShell>
    );
  }

  return (
    <AuthShell title="Forgot your password?" footer={back}>
      <p className="mt-2 text-sm text-muted">We&apos;ll email you a link to set a new one.</p>
      <form onSubmit={onSubmit} className="mt-6 flex flex-col gap-4">
        <Field label="Email">
          <input name="email" type="email" required autoComplete="email" className={INPUT} />
        </Field>
        <FormError message={error} />
        <Button type="submit" disabled={pending} className="mt-2 w-full">
          {pending ? "Sending…" : "Send reset link"}
        </Button>
      </form>
    </AuthShell>
  );
}
