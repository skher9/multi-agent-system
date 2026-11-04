"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent, type ReactNode } from "react";

import { Button, Logo } from "@/components/site";
import { authClient } from "@/lib/auth-client";

type Mode = "signup" | "login";

const COPY = {
  signup: {
    title: "Create your account",
    button: "Sign up",
    other: { text: "Already have an account?", link: "Log in", href: "/login" },
  },
  login: {
    title: "Log in",
    button: "Log in",
    other: { text: "New here?", link: "Create an account", href: "/signup" },
  },
} as const;

export function AuthForm({ mode }: { mode: Mode }) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const copy = COPY[mode];

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setPending(true);
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email"));
    const password = String(form.get("password"));
    const { error } =
      mode === "signup"
        ? await authClient.signUp.email({ name: String(form.get("name")), email, password })
        : await authClient.signIn.email({ email, password });
    setPending(false);
    if (error) {
      setError(error.message ?? "Something went wrong. Please try again.");
      return;
    }
    router.push("/dashboard");
    router.refresh();
  }

  return (
    <main className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden px-4">
      <div
        aria-hidden
        className="pointer-events-none absolute -top-40 h-80 w-full max-w-2xl rounded-full bg-accent/10 blur-3xl"
      />
      <div className="relative w-full max-w-sm">
        <div className="mb-8 flex justify-center">
          <Logo />
        </div>
        <div className="rounded-2xl border border-line bg-surface p-6 shadow-2xl shadow-black/40">
          <h1 className="text-xl font-semibold">{copy.title}</h1>
          <form onSubmit={onSubmit} className="mt-6 flex flex-col gap-4">
            {mode === "signup" && (
              <Field label="Name">
                <input name="name" required autoComplete="name" className={INPUT} />
              </Field>
            )}
            <Field label="Email">
              <input name="email" type="email" required autoComplete="email" className={INPUT} />
            </Field>
            <Field label="Password">
              <input
                name="password"
                type="password"
                required
                minLength={10}
                autoComplete={mode === "signup" ? "new-password" : "current-password"}
                className={INPUT}
              />
            </Field>
            {error && (
              <p role="alert" className="text-sm text-red-400">
                {error}
              </p>
            )}
            <Button type="submit" disabled={pending} className="mt-2 w-full">
              {pending ? "Please wait…" : copy.button}
            </Button>
          </form>
        </div>
        <p className="mt-6 text-center text-sm text-muted">
          {copy.other.text}{" "}
          <Link href={copy.other.href} className="text-ink underline-offset-4 hover:underline">
            {copy.other.link}
          </Link>
        </p>
      </div>
    </main>
  );
}

const INPUT =
  "h-10 rounded-lg border border-line bg-canvas px-3 text-sm text-ink outline-none transition placeholder:text-muted focus:border-accent focus:ring-2 focus:ring-accent/20";

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-1.5 text-sm text-muted">
      {label}
      {children}
    </label>
  );
}
