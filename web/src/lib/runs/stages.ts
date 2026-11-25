/**
 * The five boxes on the left of the run window, worked out from the events.
 *
 * Each box covers some graph nodes (backend/orchestrator/graph.py). A box is running
 * while one of its nodes has started and not finished, done once its nodes finished
 * and a later box started (or the run ended), and failed if the run failed in it.
 */

import type { RunEvent } from "./types";

export type StageStatus = "waiting" | "running" | "done" | "failed" | "paused";

export type Stage = {
  name: string;
  role: string; // the agent that owns the box, for its colour (lib/agents.ts)
  nodes: string[];
  status: StageStatus;
  note: string; // short live detail, e.g. "agent 2" or "waiting for your OK"
};

export const STAGES: { name: string; role: string; nodes: string[] }[] = [
  {
    name: "Reader",
    role: "ticket_reader",
    nodes: ["fetch_ticket", "read_ticket", "post_questions"],
  },
  {
    name: "Planner",
    role: "planner",
    nodes: ["plan", "post_conflicts", "post_plan", "await_plan_approval", "create_subtasks"],
  },
  { name: "Developer", role: "developer", nodes: ["develop"] },
  { name: "Checks and QA", role: "qa", nodes: ["verify"] },
  { name: "PR and review", role: "reviewer", nodes: ["open_pr", "review", "fix", "post_review"] },
];

/** Which box a graph node belongs to; -1 for nodes outside the boxes. */
export function stageOf(node: unknown): number {
  return STAGES.findIndex((s) => s.nodes.includes(String(node)));
}

export function stagesFrom(events: RunEvent[]): Stage[] {
  const stages: Stage[] = STAGES.map((s) => ({ ...s, status: "waiting", note: "" }));
  let current = -1;
  const developerRuns = new Set<number>();

  for (const event of events) {
    if (event.kind === "node_started") {
      const index = stageOf(event.data.node);
      if (index < 0) continue; // post_problem: not a box of its own
      for (let i = 0; i < index; i++) {
        const earlier = stages[i];
        if (earlier && earlier.status === "running") earlier.status = "done";
      }
      const stage = stages[index];
      if (stage) {
        stage.status = "running";
        stage.note = "";
      }
      current = index;
    } else if (event.kind === "tool_call" && event.data.role === "developer") {
      if (event.agentRunId !== null) developerRuns.add(event.agentRunId);
      const dev = stages[2];
      if (dev) dev.note = `subtask ${developerRuns.size}`;
    } else if (event.kind === "run_paused" && stages[current]) {
      stages[current]!.status = "paused";
      stages[current]!.note = "waiting for plan approval";
    } else if (event.kind === "run_ended") {
      for (const stage of stages) if (stage.status === "running") stage.status = "done";
    } else if (event.kind === "run_failed" && stages[current]) {
      stages[current]!.status = "failed";
      stages[current]!.note = String(event.data.error ?? "failed");
    }
  }
  return stages;
}
