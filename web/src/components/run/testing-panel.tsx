"use client";

import { useState } from "react";

import type { TestCase } from "@/lib/runs/tests";

/**
 * How QA tested the ticket: every test case with its result, and a recording of the
 * browser doing the steps. Closed at first; "Watch the testing" opens the player.
 */
export function TestingPanel({ tests }: { tests: TestCase[] }) {
  const [open, setOpen] = useState(false);
  const [picked, setPicked] = useState(0);
  if (tests.length === 0) return null;

  const passed = tests.filter((test) => test.passed).length;
  const recorded = tests.some((test) => test.video);
  const current = tests[Math.min(picked, tests.length - 1)];
  const allPassed = passed === tests.length;

  return (
    <section
      aria-label="Browser testing"
      className={`rounded-lg border bg-surface ${allPassed ? "border-ok/40" : "border-warn/50"}`}
    >
      <div className="flex flex-wrap items-center gap-4 px-4 py-3">
        <div className="mr-auto">
          <p className="font-medium text-ink">
            Tested in a real browser: {passed} of {tests.length} test cases passed
          </p>
          <p className="text-sm text-muted">
            {recorded
              ? "Each test case was recorded. Watch the browser click through it."
              : "The test cases and their steps. No recordings were kept for this run."}
          </p>
        </div>
        <button
          type="button"
          aria-expanded={open}
          onClick={() => setOpen((value) => !value)}
          className="rounded-lg bg-accent px-3 py-2 text-sm font-medium text-accent-ink hover:brightness-110"
        >
          {open ? "Hide the testing" : recorded ? "▶ Watch the testing" : "See the test cases"}
        </button>
      </div>

      {open && current && (
        <div className="grid gap-4 border-t border-line p-4 lg:grid-cols-[18rem_minmax(0,1fr)]">
          <ol className="space-y-1.5" aria-label="Test cases">
            {tests.map((test, index) => (
              <li key={test.title}>
                <button
                  type="button"
                  aria-current={index === picked}
                  onClick={() => setPicked(index)}
                  className={`flex w-full items-start gap-2 rounded-lg border px-3 py-2 text-left text-sm transition-colors ${
                    index === picked
                      ? "border-accent bg-accent/8 text-ink"
                      : "border-line text-muted hover:border-muted/60 hover:text-ink"
                  }`}
                >
                  <span aria-hidden className={test.passed ? "text-ok" : "text-bad"}>
                    {test.passed ? "✓" : "✕"}
                  </span>
                  <span className="flex-1">{test.title}</span>
                  <span className="sr-only">{test.passed ? "passed" : "failed"}</span>
                </button>
              </li>
            ))}
          </ol>

          <div className="min-w-0 space-y-3">
            {current.video ? (
              // key: a new case loads its own video instead of keeping the old one playing
              <video
                key={current.video}
                src={current.video}
                controls
                autoPlay
                muted
                playsInline
                preload="metadata"
                className="aspect-video w-full rounded-lg border border-line bg-black"
              >
                Your browser can&apos;t play this recording.
              </video>
            ) : (
              <p className="rounded-lg border border-line px-3 py-6 text-center text-sm text-muted">
                No recording for this test case.
              </p>
            )}
            <div className="text-sm">
              <p className="font-medium text-ink">
                <span className={current.passed ? "text-ok" : "text-bad"}>
                  {current.passed ? "Passed" : "Failed"}
                </span>{" "}
                · checks acceptance criterion {current.criterion}
              </p>
              <ol className="mt-2 list-decimal space-y-0.5 pl-5 text-muted">
                {current.steps.map((step) => (
                  <li key={step}>{step}</li>
                ))}
              </ol>
              <p className="mt-2 text-muted">
                <span className="text-ink">Should see:</span> {current.expected}
              </p>
              {!current.passed && current.error && (
                <pre className="mt-2 overflow-x-auto rounded-lg border border-bad/40 bg-bad/8 p-2 text-xs whitespace-pre-wrap text-ink">
                  {current.error}
                </pre>
              )}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
