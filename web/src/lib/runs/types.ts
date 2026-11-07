/**
 * What the run window shows: one ticket's run and its timeline of events.
 *
 * Event kinds and data match backend/db/models/runs.py (EventKind) and what
 * backend/orchestrator/runner.py and backend/agents/loop.py record. "agent_thought"
 * is not recorded by the backend yet: the window is ready for it.
 */

export type EventKind =
  | "run_started"
  | "node_started"
  | "node_finished"
  | "tool_call"
  | "finish_rejected"
  | "agent_finished"
  | "agent_thought"
  | "step"
  | "run_paused"
  | "plan_decided"
  | "run_ended"
  | "run_failed";

export type RunEvent = {
  id: number;
  kind: EventKind;
  data: Record<string, unknown>;
  agentRunId: number | null;
  createdAt: string; // ISO time
};

export type RunLinks = {
  ticketUrl: string | null;
  boardUrl: string | null;
  repo: string | null;
  repoUrl: string | null;
  branchUrl: string | null;
};

export type RunView = {
  ticket: string; // Jira key, e.g. KAN-12
  title: string;
  prUrl: string | null;
  links?: RunLinks; // live runs only; the sample has none
  events: RunEvent[];
};
