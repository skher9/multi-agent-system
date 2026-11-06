"use client";

import { useEffect, useState, type FormEvent, type ReactNode } from "react";

import { Field, FormError, INPUT } from "@/components/auth-form";
import { Button } from "@/components/button";
import { api } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

export type OwnProjectState = components["schemas"]["OwnProject"];
type Kind = "jira" | "github";

const JIRA_TOKENS = "https://id.atlassian.com/manage-profile/security/api-tokens";
const GITHUB_NEW_TOKEN = "https://github.com/settings/personal-access-tokens/new";
const GITHUB_TOKENS = "https://github.com/settings/personal-access-tokens";

/** The user's own Jira and GitHub, from the API. null while loading. */
export function useOwnProject() {
  const [project, setProject] = useState<OwnProjectState | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let cancelled = false;
    async function load() {
      const { data } = await api.GET("/me/project");
      if (cancelled) return;
      if (data) setProject(data);
      else setFailed(true);
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);
  return { project, setProject, failed };
}

/** Connect, check and disconnect the user's own Jira and GitHub. `numbered` shows
 * them as steps 1 and 2 (the setup page); `after` renders below, from the same state. */
export function OwnProject({
  numbered = false,
  after,
}: {
  numbered?: boolean;
  after?: (project: OwnProjectState) => ReactNode;
}) {
  const { project, setProject, failed } = useOwnProject();

  if (failed && !project)
    return (
      <p className="text-sm text-bad">Couldn&apos;t load your connections. Refresh to retry.</p>
    );
  if (!project) return <div className="h-48 animate-pulse rounded-lg bg-raised" />;
  if (!project.available)
    return (
      <p className="text-sm text-muted">
        Connecting your own project isn&apos;t switched on here yet. The demo project works as
        usual.
      </p>
    );

  return (
    <div className="space-y-4">
      <Card step={numbered ? 1 : undefined} title="Jira" done={!!project.jira}>
        {project.jira ? (
          <Connected
            kind="jira"
            rows={[
              ["Site", new URL(project.jira.site).hostname],
              ["Project", project.jira.project_key],
              ["Signed in as", project.jira.email],
            ]}
            revoke={{ href: JIRA_TOKENS, label: "revoke the token at Atlassian" }}
            onGone={setProject}
          />
        ) : (
          <JiraForm onSaved={setProject} />
        )}
      </Card>
      <Card step={numbered ? 2 : undefined} title="GitHub" done={!!project.github}>
        {project.github ? (
          <Connected
            kind="github"
            rows={[
              ["Repo", project.github.repo],
              ["Signed in as", project.github.login],
            ]}
            revoke={{ href: GITHUB_TOKENS, label: "revoke the token at GitHub" }}
            onGone={setProject}
          />
        ) : (
          <GitHubForm onSaved={setProject} />
        )}
      </Card>
      {after?.(project)}
    </div>
  );
}

function Card({
  step,
  title,
  done,
  children,
}: {
  step?: number;
  title: string;
  done: boolean;
  children: ReactNode;
}) {
  return (
    <section className="rounded-lg border border-line bg-canvas p-5">
      <h3 className="flex items-center gap-3 font-medium">
        {step !== undefined && (
          <span
            aria-hidden
            className={`grid size-6 place-items-center rounded-full text-xs ${
              done ? "bg-ok text-canvas" : "border border-line text-muted"
            }`}
          >
            {done ? "✓" : step}
          </span>
        )}
        {title}
        <span className={`ml-auto text-xs font-normal ${done ? "text-ok" : "text-muted"}`}>
          {done ? "Connected" : "Not connected"}
        </span>
      </h3>
      <div className="mt-4">{children}</div>
    </section>
  );
}

/** What's connected, and a Disconnect that asks once before deleting our copy. */
function Connected({
  kind,
  rows,
  revoke,
  onGone,
}: {
  kind: Kind;
  rows: [string, string][];
  revoke: { href: string; label: string };
  onGone: (project: OwnProjectState) => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function remove() {
    setBusy(true);
    setError("");
    const { response } = await api.DELETE("/me/{kind}", { params: { path: { kind } } });
    if (response.ok || response.status === 404) {
      const { data } = await api.GET("/me/project");
      if (data) onGone(data);
    } else setError("Couldn't disconnect. Please try again.");
    setBusy(false);
  }

  return (
    <div className="space-y-4">
      <dl className="grid grid-cols-[7rem_1fr] gap-y-1.5 text-sm">
        {rows.map(([label, value]) => (
          <div key={label} className="contents">
            <dt className="text-muted">{label}</dt>
            <dd className="truncate font-mono text-xs leading-5">{value}</dd>
          </div>
        ))}
      </dl>
      {confirming ? (
        <div className="rounded-md border border-bad/30 p-3 text-sm">
          <p>
            We delete our copy of the token, so agents can&apos;t use it. Your run history stays. To
            end the token everywhere,{" "}
            <a
              href={revoke.href}
              target="_blank"
              rel="noreferrer"
              className="text-accent underline underline-offset-2"
            >
              {revoke.label} ↗
            </a>
            .
          </p>
          <div className="mt-3 flex gap-2">
            <Button variant="danger" size="sm" disabled={busy} onClick={remove}>
              {busy ? "Disconnecting…" : "Disconnect"}
            </Button>
            <Button variant="ghost" size="sm" disabled={busy} onClick={() => setConfirming(false)}>
              Keep it
            </Button>
          </div>
        </div>
      ) : (
        <Button variant="ghost" size="sm" onClick={() => setConfirming(true)}>
          Disconnect
        </Button>
      )}
      <FormError message={error} />
    </div>
  );
}

function JiraForm({ onSaved }: { onSaved: (project: OwnProjectState) => void }) {
  const { pending, error, submit } = useSave();

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const text = (name: string) => String(form.get(name) ?? "").trim();
    submit(
      () =>
        api.PUT("/me/jira", {
          body: {
            site: text("site"),
            email: text("email"),
            api_token: text("api_token"),
            project_key: text("project_key"),
          },
        }),
      onSaved,
    );
  }

  return (
    <form onSubmit={onSubmit} className="space-y-3">
      <p className="text-sm text-muted">
        Agents read tickets from one Jira Cloud project, post their questions and plan there, and
        add subtasks. Use an{" "}
        <a
          href={JIRA_TOKENS}
          target="_blank"
          rel="noreferrer"
          className="text-accent underline underline-offset-2"
        >
          API token ↗
        </a>
        , not your password.
      </p>
      <Field label="Jira site">
        <input
          name="site"
          required
          placeholder="https://acme.atlassian.net"
          autoComplete="off"
          className={INPUT}
        />
      </Field>
      <div className="grid gap-3 sm:grid-cols-[1fr_8rem]">
        <Field label="Your Jira email">
          <input name="email" type="email" required autoComplete="email" className={INPUT} />
        </Field>
        <Field label="Project key">
          <input
            name="project_key"
            required
            placeholder="KAN"
            autoComplete="off"
            className={`${INPUT} uppercase`}
          />
        </Field>
      </div>
      <Field label="API token">
        <input
          name="api_token"
          type="password"
          required
          minLength={10}
          autoComplete="off"
          className={INPUT}
        />
      </Field>
      <FormError message={error} />
      <Button type="submit" disabled={pending}>
        {pending ? "Checking with Jira…" : "Connect Jira"}
      </Button>
    </form>
  );
}

function GitHubForm({ onSaved }: { onSaved: (project: OwnProjectState) => void }) {
  const { pending, error, submit } = useSave();

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const text = (name: string) => String(form.get(name) ?? "").trim();
    submit(
      () => api.PUT("/me/github", { body: { repo: text("repo"), token: text("token") } }),
      onSaved,
    );
  }

  return (
    <form onSubmit={onSubmit} className="space-y-3">
      <div className="text-sm text-muted">
        <p>
          Agents push a branch named <span className="font-mono text-xs">agent/&lt;ticket&gt;</span>{" "}
          and open a pull request. They never push to your main branch. Make a{" "}
          <a
            href={GITHUB_NEW_TOKEN}
            target="_blank"
            rel="noreferrer"
            className="text-accent underline underline-offset-2"
          >
            fine-grained token ↗
          </a>{" "}
          for this one repo:
        </p>
        <ul className="mt-2 list-disc space-y-0.5 pl-5">
          <li>Repository access: only select repositories, then your repo</li>
          <li>Contents: read and write</li>
          <li>Pull requests: read and write</li>
        </ul>
      </div>
      <Field label="Repo">
        <input
          name="repo"
          required
          placeholder="owner/name or a github.com link"
          autoComplete="off"
          className={INPUT}
        />
      </Field>
      <Field label="Token">
        <input
          name="token"
          type="password"
          required
          minLength={10}
          placeholder="github_pat_…"
          autoComplete="off"
          className={INPUT}
        />
      </Field>
      <FormError message={error} />
      <Button type="submit" disabled={pending}>
        {pending ? "Checking with GitHub…" : "Connect GitHub"}
      </Button>
    </form>
  );
}

type Saved = { data?: OwnProjectState; error?: unknown; response: Response };

/** Sends a connect form; shows the API's reason when it's refused. */
function useSave() {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  async function submit(send: () => Promise<Saved>, onSaved: (p: OwnProjectState) => void) {
    setPending(true);
    setError("");
    const { data, error, response } = await send();
    setPending(false);
    if (data) onSaved(data);
    else setError(reason(error, response.status));
  }

  return { pending, error, submit };
}

function reason(error: unknown, status: number): string {
  const detail = (error as { detail?: unknown } | undefined)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail[0]?.msg)
    return String(detail[0].msg).replace(/^Value error, /, "");
  if (status === 401) return "Your login expired. Refresh the page and try again.";
  return "Couldn't connect. Please try again.";
}
