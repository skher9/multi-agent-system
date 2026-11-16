import type { RunEvent } from "./types";

/** One of QA's test cases, as backend/agents/qa.py (CaseResult) records it. */
export type TestCase = {
  criterion: number;
  title: string;
  steps: string[];
  expected: string;
  passed: boolean;
  seconds: number;
  video: string; // "" = no recording was kept
  error: string;
};

const API_ORIGIN = new URL(process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").origin;

/** A recording's address, only if it really is one of our API's recordings. */
function recording(value: unknown): string {
  if (typeof value !== "string" || !value) return "";
  try {
    const url = new URL(value);
    return url.origin === API_ORIGIN && url.pathname.startsWith("/recordings/") ? url.href : "";
  } catch {
    return "";
  }
}

function testCase(value: unknown): TestCase | null {
  if (typeof value !== "object" || value === null) return null;
  const raw = value as Record<string, unknown>;
  if (typeof raw.title !== "string" || typeof raw.passed !== "boolean") return null;
  return {
    criterion: Number(raw.criterion) || 0,
    title: raw.title,
    steps: Array.isArray(raw.steps)
      ? raw.steps.filter((s): s is string => typeof s === "string")
      : [],
    expected: typeof raw.expected === "string" ? raw.expected : "",
    passed: raw.passed,
    seconds: Number(raw.seconds) || 0,
    video: recording(raw.video),
    error: typeof raw.error === "string" ? raw.error : "",
  };
}

/** The test cases of the run's latest QA pass; empty until QA has tested. */
export function testsFrom(events: RunEvent[]): TestCase[] {
  const latest = events.findLast((event) => Array.isArray(event.data.tests));
  const list = (latest?.data.tests ?? []) as unknown[];
  return list.map(testCase).filter((item): item is TestCase => item !== null);
}
