/**
 * The public replay: one real run of the agents on a benchmark ticket, exported from the
 * database by backend/experiments/replay.py (to refresh it, run that script). Visitors
 * watch it without logging in.
 */

import replay from "./replay.json";
import type { RunEvent, RunView } from "./types";

export const REPLAY_RUN: RunView = {
  ticket: replay.ticket,
  title: replay.title,
  prUrl: replay.prUrl,
  events: replay.events as RunEvent[],
};
