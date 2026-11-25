"use client";

import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/button";
import { Card } from "@/components/ui/card";
import { Chip } from "@/components/ui/chip";
import type { Tone } from "@/components/ui/tone";
import { api, type HealthReport } from "@/lib/api/client";

type State =
  | { kind: "loading" }
  | { kind: "loaded"; report: HealthReport; checkedAt: Date }
  | { kind: "unreachable"; message: string };

const BADGE: Record<string, Tone> = { ok: "mint", error: "rose", not_configured: "butter" };

async function fetchHealth(): Promise<State> {
  try {
    // 200 = all ok -> data. 503 = degraded -> error (same HealthReport shape).
    const { data, error } = await api.GET("/health");
    const report = data ?? error;
    if (!report) return { kind: "unreachable", message: "Empty response from API" };
    return { kind: "loaded", report, checkedAt: new Date() };
  } catch {
    return { kind: "unreachable", message: "Can't reach the API. Is the backend running?" };
  }
}

export function StatusBoard() {
  const [state, setState] = useState<State>({ kind: "loading" });

  const check = useCallback(async () => {
    setState({ kind: "loading" });
    setState(await fetchHealth());
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetchHealth().then((next) => {
      if (!cancelled) setState(next);
    });
    return () => {
      cancelled = true; // ignore a late response if the page was left
    };
  }, []);

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center gap-4">
        <Button type="button" variant="ghost" onClick={check} disabled={state.kind === "loading"}>
          {state.kind === "loading" ? "Checking…" : "Check again"}
        </Button>
        {state.kind === "loaded" && (
          <span className="text-sm text-muted">
            Overall: <strong>{state.report.status}</strong> · checked{" "}
            {state.checkedAt.toLocaleTimeString()}
          </span>
        )}
      </div>

      {state.kind === "unreachable" && (
        <p role="alert" className="rounded-2xl border-ink-line bg-rose p-3">
          {state.message}
        </p>
      )}

      {state.kind === "loaded" && (
        <Card as="div" tone="sky" className="p-0! sm:p-0!">
          <ul className="divide-y-[1.5px] divide-dashed divide-ink/20">
            {Object.entries(state.report.services).map(([name, service]) => (
              <li key={name} className="flex items-start justify-between gap-4 px-5 py-4">
                <span className="font-mono">{name}</span>
                <span className="text-right">
                  <Chip tone={BADGE[service.status] ?? "plain"}>
                    {service.status.replace("_", " ")}
                  </Chip>
                  {service.detail && (
                    <span className="mt-1 block text-xs text-muted">{service.detail}</span>
                  )}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </section>
  );
}
