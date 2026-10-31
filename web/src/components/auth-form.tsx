"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

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
    <main className="mx-auto flex min-h-screen max-w-sm flex-col justify-center gap-6 p-6">
      <h1 className="text-2xl font-semibold">{copy.title}</h1>
      <form onSubmit={onSubmit} className="flex flex-col gap-4">
        {mode === "signup" && (
          <label className="flex flex-col gap-1 text-sm">
            Name
            <input name="name" required autoComplete="name" className="rounded border px-3 py-2" />
          </label>
        )}
        <label className="flex flex-col gap-1 text-sm">
          Email
          <input
            name="email"
            type="email"
            required
            autoComplete="email"
            className="rounded border px-3 py-2"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Password
          <input
            name="password"
            type="password"
            required
            minLength={10}
            autoComplete={mode === "signup" ? "new-password" : "current-password"}
            className="rounded border px-3 py-2"
          />
        </label>
        {error && (
          <p role="alert" className="text-sm text-red-600">
            {error}
          </p>
        )}
        <button
          type="submit"
          disabled={pending}
          className="rounded bg-black px-4 py-2 text-white disabled:opacity-50"
        >
          {pending ? "Please wait…" : copy.button}
        </button>
      </form>
      <p className="text-sm text-gray-600">
        {copy.other.text}{" "}
        <Link href={copy.other.href} className="underline">
          {copy.other.link}
        </Link>
      </p>
    </main>
  );
}
