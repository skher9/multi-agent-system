"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent, type ReactNode } from "react";

import { Button, Logo } from "@/components/site";
import { authClient } from "@/lib/auth-client";
import type { SocialProvider } from "@/lib/auth";

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

const PROVIDERS: Record<SocialProvider, { label: string; icon: ReactNode }> = {
  google: { label: "Continue with Google", icon: <GoogleIcon /> },
  github: { label: "Continue with GitHub", icon: <GitHubIcon /> },
};

export function AuthForm({ mode, providers }: { mode: Mode; providers: SocialProvider[] }) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [verifyEmail, setVerifyEmail] = useState(""); // set once a confirm link is sent
  const copy = COPY[mode];

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setPending(true);
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email"));
    const password = String(form.get("password"));
    // The confirm link lands here once clicked, already logged in
    const callbackURL = "/dashboard";
    const { error } =
      mode === "signup"
        ? await authClient.signUp.email({ name: String(form.get("name")), email, password, callbackURL })
        : await authClient.signIn.email({ email, password, callbackURL });
    setPending(false);
    if (error?.code === "EMAIL_NOT_VERIFIED") {
      setVerifyEmail(email); // Better Auth has sent a fresh link (sendOnSignIn)
      return;
    }
    if (error) {
      setError(error.message ?? "Something went wrong. Please try again.");
      return;
    }
    if (mode === "signup") {
      setVerifyEmail(email); // no session until the email is confirmed
      return;
    }
    router.push("/dashboard");
    router.refresh();
  }

  if (verifyEmail) {
    return (
      <AuthShell
        title="Check your email"
        footer={
          <Link href="/login" className="text-ink underline-offset-4 hover:underline">
            Back to log in
          </Link>
        }
      >
        <p className="mt-4 text-sm text-muted">
          We sent a confirmation link to <span className="text-ink">{verifyEmail}</span>. Click
          it to finish setting up your account. It works for 1 hour.
        </p>
      </AuthShell>
    );
  }

  async function social(provider: SocialProvider) {
    setError("");
    setPending(true);
    // Leaves for Google/GitHub; they send the visitor back to /dashboard
    const { error } = await authClient.signIn.social({ provider, callbackURL: "/dashboard" });
    if (error) {
      setPending(false);
      setError(error.message ?? "Couldn't reach the login provider. Please try again.");
    }
  }

  return (
    <AuthShell
      title={copy.title}
      footer={
        <>
          {copy.other.text}{" "}
          <Link href={copy.other.href} className="text-ink underline-offset-4 hover:underline">
            {copy.other.link}
          </Link>
        </>
      }
    >
      {providers.length > 0 && (
        <>
          <div className="mt-6 flex flex-col gap-2">
            {providers.map((provider) => (
              <Button
                key={provider}
                type="button"
                variant="ghost"
                disabled={pending}
                onClick={() => social(provider)}
                className="w-full"
              >
                {PROVIDERS[provider].icon}
                {PROVIDERS[provider].label}
              </Button>
            ))}
          </div>
          <div className="my-5 flex items-center gap-3 text-xs text-muted">
            <span className="h-px flex-1 bg-line" />
            or with email
            <span className="h-px flex-1 bg-line" />
          </div>
        </>
      )}
      <form onSubmit={onSubmit} className={`flex flex-col gap-4 ${providers.length ? "" : "mt-6"}`}>
        {mode === "signup" && (
          <Field label="Name">
            <input name="name" required autoComplete="name" className={INPUT} />
          </Field>
        )}
        <Field label="Email">
          <input name="email" type="email" required autoComplete="email" className={INPUT} />
        </Field>
        <Field
          label="Password"
          aside={
            mode === "login" && (
              <Link href="/forgot-password" className="text-xs hover:text-ink">
                Forgot password?
              </Link>
            )
          }
        >
          <input
            name="password"
            type="password"
            required
            minLength={10}
            autoComplete={mode === "signup" ? "new-password" : "current-password"}
            className={INPUT}
          />
        </Field>
        <FormError message={error} />
        <Button type="submit" disabled={pending} className="mt-2 w-full">
          {pending ? "Please wait…" : copy.button}
        </Button>
      </form>
    </AuthShell>
  );
}

/** The centered card every login page uses. */
export function AuthShell({
  title,
  footer,
  children,
}: {
  title: string;
  footer?: ReactNode;
  children: ReactNode;
}) {
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
          <h1 className="text-xl font-semibold">{title}</h1>
          {children}
        </div>
        {footer && <p className="mt-6 text-center text-sm text-muted">{footer}</p>}
      </div>
    </main>
  );
}

export const INPUT =
  "h-10 rounded-lg border border-line bg-canvas px-3 text-sm text-ink outline-none transition placeholder:text-muted focus:border-accent focus:ring-2 focus:ring-accent/20";

export function Field({
  label,
  aside,
  children,
}: {
  label: string;
  aside?: ReactNode;
  children: ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1.5 text-sm text-muted">
      <span className="flex items-center justify-between">
        {label}
        {aside}
      </span>
      {children}
    </label>
  );
}

export function FormError({ message }: { message: string }) {
  if (!message) return null;
  return (
    <p role="alert" className="text-sm text-red-400">
      {message}
    </p>
  );
}

function GoogleIcon() {
  return (
    <svg aria-hidden viewBox="0 0 24 24" className="size-4">
      <path
        fill="#EA4335"
        d="M12 10.2v3.9h5.5c-.24 1.4-1.7 4.1-5.5 4.1-3.3 0-6-2.7-6-6.1s2.7-6.1 6-6.1c1.9 0 3.1.8 3.8 1.5l2.6-2.5C16.8 3.5 14.6 2.5 12 2.5 6.8 2.5 2.6 6.7 2.6 12s4.2 9.5 9.4 9.5c5.4 0 9-3.8 9-9.2 0-.6-.1-1.1-.2-1.6H12z"
      />
    </svg>
  );
}

function GitHubIcon() {
  return (
    <svg aria-hidden viewBox="0 0 24 24" className="size-4 fill-current">
      <path d="M12 .5C5.7.5.5 5.7.5 12c0 5.1 3.3 9.4 7.9 10.9.6.1.8-.3.8-.6v-2c-3.2.7-3.9-1.5-3.9-1.5-.5-1.3-1.3-1.7-1.3-1.7-1-.7.1-.7.1-.7 1.2.1 1.8 1.2 1.8 1.2 1 1.8 2.7 1.3 3.4 1 .1-.8.4-1.3.7-1.6-2.6-.3-5.3-1.3-5.3-5.7 0-1.3.5-2.3 1.2-3.1-.1-.3-.5-1.5.1-3.1 0 0 1-.3 3.2 1.2a11 11 0 0 1 5.8 0c2.2-1.5 3.2-1.2 3.2-1.2.6 1.6.2 2.8.1 3.1.8.8 1.2 1.9 1.2 3.1 0 4.4-2.7 5.4-5.3 5.7.4.4.8 1.1.8 2.2v3.3c0 .3.2.7.8.6 4.6-1.5 7.9-5.8 7.9-10.9C23.5 5.7 18.3.5 12 .5z" />
    </svg>
  );
}
