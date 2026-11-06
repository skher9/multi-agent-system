"use client";

import { useCallback, useEffect, useState } from "react";

import { api, type HealthReport } from "@/lib/api/client";

type State =
  | { kind: "loading" }
  | { kind: "loaded"; report: HealthReport; checkedAt: Date }
  | { kind: "unreachable"; message: string };

const BADGE: Record<string, string> = {
  ok: "bg-ok/10 text-ok",
  error: "bg-bad/10 text-bad",
  not_configured: "bg-warn/10 text-warn",
};

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
      <div className="flex items-center gap-4">
        <button
          type="button"
          onClick={check}
          disabled={state.kind === "loading"}
          className="rounded border px-3 py-1 text-sm disabled:opacity-50"
        >
          {state.kind === "loading" ? "Checking…" : "Check again"}
        </button>
        {state.kind === "loaded" && (
          <span className="text-sm text-gray-500">
            Overall: <strong>{state.report.status}</strong> · checked{" "}
            {state.checkedAt.toLocaleTimeString()}
          </span>
        )}
      </div>

      {state.kind === "unreachable" && <p className="text-bad">{state.message}</p>}

      {state.kind === "loaded" && (
        <ul className="divide-y rounded border">
          {Object.entries(state.report.services).map(([name, service]) => (
            <li key={name} className="flex items-start justify-between gap-4 p-3">
              <span className="font-mono">{name}</span>
              <span className="text-right">
                <span className={`rounded px-2 py-0.5 text-sm ${BADGE[service.status] ?? ""}`}>
                  {service.status}
                </span>
                {service.detail && (
                  <span className="mt-1 block text-xs text-gray-500">{service.detail}</span>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
