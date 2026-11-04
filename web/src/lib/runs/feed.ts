/**
 * Turns one event into one line of the live feed on the right of the run window.
 * Returns null for events the feed doesn't show (box starts and finishes: the
 * pipeline on the left shows those).
 */

import type { RunEvent } from "./types";

export type FeedTone = "thought" | "tool" | "good" | "bad" | "info";

export type FeedItem = {
  id: number;
  role: string; // which agent, e.g. "developer"; "run" for the run itself
  tone: FeedTone;
  title: string;
  detail: string;
  at: string;
};

// Tool names and their main argument, from backend/agents/repo_tools.py and loop.py
const TOOLS: Record<string, { label: string; argument?: string }> = {
  list_files: { label: "Looked at files in", argument: "path" },
  search: { label: "Searched for", argument: "text" },
  read_file: { label: "Read", argument: "path" },
  edit_file: { label: "Edited", argument: "path" },
  create_file: { label: "Created", argument: "path" },
  delete_file: { label: "Deleted", argument: "path" },
  run: { label: "Ran", argument: "command" },
  run_tests: { label: "Ran the unit tests" },
  run_e2e: { label: "Ran the browser tests" },
  ask_senior: { label: "Asked the senior model:", argument: "question" },
};

// Final outcomes, from backend/orchestrator/graph.py
const OUTCOMES: Record<string, string> = {
  ready_to_merge: "Done: PR reviewed and ready to merge",
  needs_human: "Stopped: a human needs to look",
  blocked: "Stopped: questions posted on the ticket",
  plan_rejected: "Stopped: plan rejected",
  waiting_for_plan_approval: "Waiting for plan approval",
};

/** One argument's value, from tool-call JSON the backend may have cut short. */
function argument(raw: unknown, key: string | undefined): string {
  if (!key) return "";
  const match = new RegExp(`"${key}"\\s*:\\s*"([^"]*)`).exec(String(raw ?? ""));
  return match?.[1] ?? "";
}

export function feedItem(event: RunEvent): FeedItem | null {
  const role = String(event.data.role ?? "run");
  const base = { id: event.id, role, at: event.createdAt };
  switch (event.kind) {
    case "agent_thought":
      return { ...base, tone: "thought", title: String(event.data.text ?? ""), detail: "" };
    case "tool_call": {
      const name = String(event.data.tool);
      const tool = TOOLS[name] ?? { label: name };
      return {
        ...base,
        tone: "tool",
        title: `${tool.label} ${argument(event.data.arguments, tool.argument)}`.trim(),
        detail: `tool call ${event.data.n}/${event.data.limit}`,
      };
    }
    case "finish_rejected":
      return {
        ...base,
        tone: "bad",
        title: "Tried to finish, our checks said not yet",
        detail: String(event.data.error ?? ""),
      };
    case "agent_finished":
      return {
        ...base,
        tone: "good",
        title: "Finished",
        detail: event.data.tool_calls === 1 ? "1 tool call" : `${event.data.tool_calls} tool calls`,
      };
    case "run_started":
      return {
        ...base,
        tone: "info",
        title: event.data.resumed ? "Run resumed" : "Run started",
        detail: "",
      };
    case "run_paused":
      return { ...base, tone: "info", title: "Paused for plan approval", detail: "" };
    case "plan_decided":
      return {
        ...base,
        tone: "info",
        title: `Plan ${event.data.decision}d`,
        detail: String(event.data.feedback ?? ""),
      };
    case "run_ended": {
      const outcome = String(event.data.outcome);
      return { ...base, tone: "good", title: OUTCOMES[outcome] ?? outcome, detail: "" };
    }
    case "run_failed":
      return { ...base, tone: "bad", title: "Run failed", detail: String(event.data.error) };
    default:
      return null;
  }
}
