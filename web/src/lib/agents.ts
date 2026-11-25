import type { Tone } from "@/components/ui/tone";

/** The seven agents in the order a ticket meets them. `role` matches the backend's
 * Role values (backend/llm_router/models.py); `tone` is the agent's colour everywhere. */
export const AGENTS = [
  {
    role: "ticket_reader",
    name: "Reader",
    tone: "butter",
    job: "Turns the ticket into a spec. If it's vague, asks questions on Jira instead of guessing.",
  },
  {
    role: "planner",
    name: "Planner",
    tone: "lilac",
    job: "Reads the repo through a code map and plans every file change, criterion by criterion.",
  },
  {
    role: "developer",
    name: "Developer",
    tone: "mint",
    job: "Builds each subtask in a sandbox. Lint, types and unit tests must pass before it can stop.",
  },
  {
    role: "fixer",
    name: "Fixer",
    tone: "peach",
    job: "Takes whatever the final checks still catch, the build included, and fixes exactly that.",
  },
  {
    role: "qa",
    name: "QA",
    tone: "sky",
    job: "Writes test cases from the ticket, then clicks through each one in a real browser, on video.",
  },
  {
    role: "reviewer",
    name: "Reviewer",
    tone: "rose",
    job: "Scores the change in five areas like a senior engineer and sends it back when one falls short.",
  },
  {
    role: "learner",
    name: "Learner",
    tone: "lime",
    job: "Turns your comments on merged PRs into rules every agent follows next time.",
  },
] as const satisfies readonly { role: string; name: string; tone: Tone; job: string }[];

export type AgentRole = (typeof AGENTS)[number]["role"];

/** An agent's colour from a role name as events record it; unknown roles stay plain. */
export function agentTone(role: string): Tone {
  return (
    AGENTS.find((agent) => agent.role === role || agent.name.toLowerCase() === role)?.tone ??
    "plain"
  );
}
