"use client";

import { useState } from "react";

import { Button } from "@/components/button";
import { TONE_SHADOW } from "@/components/ui/tone";

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
      className={`rounded-3xl border-ink-line bg-surface ${TONE_SHADOW[allPassed ? "mint" : "peach"]}`}
    >
      <div className="flex flex-wrap items-center gap-4 px-6 py-5">
        <div className="mr-auto">
          <p className="font-display text-xl">
            Tested in a real browser: {passed} of {tests.length} test cases passed
          </p>
          <p className="text-sm text-muted">
            {recorded
              ? "Each test case was recorded. Watch the browser click through it."
              : "The test cases and their steps. No recordings were kept for this run."}
          </p>
        </div>
        <Button type="button" aria-expanded={open} onClick={() => setOpen((value) => !value)}>
          {open ? "Hide the testing" : recorded ? "▶ Watch the testing" : "See the test cases"}
        </Button>
      </div>

      {open && current && (
        <div className="grid gap-5 border-t-[1.5px] border-dashed border-ink/20 p-6 lg:grid-cols-[18rem_minmax(0,1fr)]">
          <ol className="space-y-1.5" aria-label="Test cases">
            {tests.map((test, index) => (
              <li key={test.title}>
                <button
                  type="button"
                  aria-current={index === picked}
                  onClick={() => setPicked(index)}
                  className={`flex min-h-11 w-full items-start gap-2 rounded-xl border-ink-line px-3 py-2 text-left text-sm transition ${
                    index === picked ? "bg-sky shadow-hard-sm" : "bg-surface hover:-translate-y-0.5"
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
                className="aspect-video w-full rounded-2xl border-ink-line bg-ink"
              >
                Your browser can&apos;t play this recording.
              </video>
            ) : (
              <p className="rounded-2xl border-[1.5px] border-dashed border-ink/30 px-3 py-6 text-center text-sm text-muted">
                No recording for this test case.
              </p>
            )}
            <div className="text-sm">
              <p className="font-semibold">
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
                <pre className="mt-2 overflow-x-auto rounded-xl border-ink-line bg-rose p-3 font-mono text-xs whitespace-pre-wrap">
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
