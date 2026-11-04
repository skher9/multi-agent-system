/**
 * A sample run for the run window, shaped like real run_events rows. It is made up
 * (the thoughts especially: the backend doesn't record them yet), so the page that
 * shows it says so. Swap for real runs once the backend has a read endpoint.
 */

import type { EventKind, RunEvent, RunView } from "./types";

const START = Date.parse("2026-11-04T10:00:00Z");

type Step = [seconds: number, kind: EventKind, data?: Record<string, unknown>, run?: number];

const node = (s: number, kind: "node_started" | "node_finished", name: string): Step => [
  s,
  kind,
  { node: name },
];
const think = (s: number, role: string, run: number, text: string): Step => [
  s,
  "agent_thought",
  { role, text },
  run,
];
const tool = (
  s: number,
  role: string,
  run: number,
  n: number,
  limit: number,
  name: string,
  args: Record<string, string> = {},
): Step => [s, "tool_call", { role, tool: name, n, limit, arguments: JSON.stringify(args) }, run];
const done = (s: number, role: string, run: number, calls: number): Step => [
  s,
  "agent_finished",
  { role, tool_calls: calls },
  run,
];

const STEPS: Step[] = [
  [0, "run_started", { resumed: false }],
  node(1, "node_started", "fetch_ticket"),
  node(2, "node_finished", "fetch_ticket"),
  node(2, "node_started", "read_ticket"),
  think(6, "reader", 1, "Clear ticket: a /contact page with name, email, message and a thank-you."),
  done(9, "reader", 1, 0),
  node(9, "node_finished", "read_ticket"),

  node(10, "node_started", "plan"),
  think(13, "planner", 2, "Need to see how pages and forms are built here before planning."),
  tool(15, "planner", 2, 1, 25, "list_files", { path: "src/app" }),
  tool(18, "planner", 2, 2, 25, "read_file", { path: "src/app/page.tsx" }),
  tool(21, "planner", 2, 3, 25, "search", { text: "useState" }),
  think(26, "planner", 2, "No form library in use. Two subtasks: the page, then the form."),
  done(30, "planner", 2, 3),
  node(30, "node_finished", "plan"),
  node(31, "node_started", "create_subtasks"),
  node(33, "node_finished", "create_subtasks"),

  node(34, "node_started", "develop"),
  think(37, "developer", 3, "Subtask 1: the page and a link in the header."),
  tool(40, "developer", 3, 1, 40, "read_file", { path: "src/app/layout.tsx" }),
  tool(46, "developer", 3, 2, 40, "create_file", { path: "src/app/contact/page.tsx" }),
  tool(51, "developer", 3, 3, 40, "edit_file", { path: "src/app/layout.tsx" }),
  tool(58, "developer", 3, 4, 40, "run_tests"),
  done(70, "developer", 3, 4),
  think(73, "developer", 4, "Subtask 2: the form. Email needs checking before submit."),
  tool(76, "developer", 4, 1, 40, "create_file", { path: "src/app/contact/contact-form.tsx" }),
  tool(83, "developer", 4, 2, 40, "create_file", {
    path: "src/app/contact/contact-form.test.tsx",
  }),
  tool(90, "developer", 4, 3, 40, "run_tests"),
  [
    101,
    "finish_rejected",
    { role: "developer", error: "unit tests failed: expected 'Thanks!' to be visible" },
    4,
  ],
  think(104, "developer", 4, "The thank-you only shows after a re-render. Show it from state."),
  tool(108, "developer", 4, 4, 40, "edit_file", { path: "src/app/contact/contact-form.tsx" }),
  tool(113, "developer", 4, 5, 40, "run_tests"),
  done(125, "developer", 4, 5),
  node(125, "node_finished", "develop"),

  node(126, "node_started", "verify"),
  think(150, "qa", 5, "One browser test per acceptance criterion, using labels on the form."),
  tool(153, "qa", 5, 1, 40, "read_file", { path: "playwright.config.ts" }),
  tool(158, "qa", 5, 2, 40, "create_file", { path: "e2e/contact.spec.ts" }),
  tool(164, "qa", 5, 3, 40, "run_e2e"),
  done(205, "qa", 5, 3),
  node(206, "node_finished", "verify"),

  node(207, "node_started", "open_pr"),
  node(210, "node_finished", "open_pr"),
  node(211, "node_started", "review"),
  think(215, "reviewer", 6, "Checking each criterion against the diff and the test evidence."),
  tool(218, "reviewer", 6, 1, 30, "read_file", { path: "src/app/contact/contact-form.tsx" }),
  think(226, "reviewer", 6, "All three criteria met and tested. Approve."),
  done(230, "reviewer", 6, 1),
  node(230, "node_finished", "review"),
  node(231, "node_started", "post_review"),
  node(233, "node_finished", "post_review"),
  [233, "run_ended", { outcome: "ready_to_merge" }],
];

export const SAMPLE_RUN: RunView = {
  ticket: "KAN-12",
  title: "Add a contact page",
  prUrl: "https://github.com/skher9/agent-playground/pulls",
  costInr: 4.2,
  events: STEPS.map(([seconds, kind, data = {}, run]): RunEvent => ({
    id: 0,
    kind,
    data,
    agentRunId: run ?? null,
    createdAt: new Date(START + seconds * 1000).toISOString(),
  })).map((event, index) => ({ ...event, id: index + 1 })),
};
