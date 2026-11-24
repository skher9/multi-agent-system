"use client";

import { useEffect, useMemo, useState } from "react";

import { Chip } from "@/components/ui/chip";
import { TONE_SHADOW } from "@/components/ui/tone";
import type { RunEvent } from "@/lib/runs/types";

// Typing speed: fast enough that a 100-line file appears in a few seconds
const CHARS_PER_TICK = 24;
const TICK_MS = 16;

type CodeWrite = {
  id: number;
  role: string;
  path: string;
  content?: string; // create_file
  oldText?: string; // edit_file
  newText?: string;
};

/** File writes in the events so far: the tool calls that carry their code. */
export function codeWrites(events: RunEvent[]): CodeWrite[] {
  const writes: CodeWrite[] = [];
  for (const event of events) {
    if (event.kind !== "tool_call") continue;
    const code = event.data.code as Record<string, unknown> | undefined;
    if (!code || typeof code.path !== "string") continue;
    writes.push({
      id: event.id,
      role: String(event.data.role ?? ""),
      path: code.path,
      content: typeof code.content === "string" ? code.content : undefined,
      oldText: typeof code.old_text === "string" ? code.old_text : undefined,
      newText: typeof code.new_text === "string" ? code.new_text : undefined,
    });
  }
  return writes;
}

/** The code the agents are writing: the latest file write, typed in as it arrives. */
export function CodePanel({ events }: { events: RunEvent[] }) {
  const writes = useMemo(() => codeWrites(events), [events]);
  const latest = writes.at(-1);
  const files = useMemo(() => [...new Set(writes.map((w) => w.path))], [writes]);

  return (
    <section
      aria-label="Code being written"
      className={`flex h-[28rem] flex-col overflow-hidden rounded-3xl border-ink-line bg-surface ${TONE_SHADOW.mint}`}
    >
      <header className="flex items-center gap-2 border-b-[1.5px] border-dashed border-ink/20 px-4 py-3 text-xs">
        <span className="size-2.5 rounded-full border-ink-line bg-mint" aria-hidden />
        {latest ? (
          <>
            <span className="truncate font-mono text-ink">{latest.path}</span>
            <span className="ml-auto shrink-0 text-muted">
              {latest.content !== undefined ? "new file" : "edit"} · {latest.role}
            </span>
          </>
        ) : (
          <span className="text-muted">Code</span>
        )}
      </header>
      {latest ? (
        <Typed key={latest.id} write={latest} />
      ) : (
        <p className="p-4 text-sm text-muted">Code appears here when an agent writes a file.</p>
      )}
      {files.length > 0 && (
        <footer className="flex gap-1.5 overflow-x-auto border-t-[1.5px] border-dashed border-ink/20 px-4 py-2.5">
          {files.map((path) => (
            <Chip
              key={path}
              mono
              tone={path === latest?.path ? "mint" : "plain"}
              className="shrink-0 py-0 text-[11px]"
            >
              {path.split("/").at(-1)}
            </Chip>
          ))}
        </footer>
      )}
    </section>
  );
}

/** One write, typed in character by character (the removed part of an edit shows at once). */
function Typed({ write }: { write: CodeWrite }) {
  const target = write.content ?? write.newText ?? "";
  const [shown, setShown] = useState(0);

  useEffect(() => {
    if (shown >= target.length) return;
    const timer = setTimeout(() => setShown((n) => n + CHARS_PER_TICK), TICK_MS);
    return () => clearTimeout(timer);
  }, [shown, target.length]);

  const typed = target.slice(0, shown);
  return (
    <pre className="flex-1 overflow-auto p-3 font-mono text-[12.5px] leading-5">
      {write.oldText !== undefined && (
        <Lines text={write.oldText} sign="-" className="bg-bad/10 text-bad" />
      )}
      <Lines
        text={typed}
        sign={write.oldText !== undefined ? "+" : " "}
        className={write.oldText !== undefined ? "bg-mint/60 text-ink" : "text-ink"}
      />
      {shown < target.length && <span className="animate-pulse">▍</span>}
    </pre>
  );
}

function Lines({ text, sign, className }: { text: string; sign: string; className: string }) {
  if (!text) return null;
  return (
    <code className="block">
      {text.split("\n").map((line, i) => (
        <span key={i} className={`block whitespace-pre ${className}`}>
          <span className="mr-3 inline-block w-3 select-none text-muted">{sign}</span>
          {line || " "}
        </span>
      ))}
    </code>
  );
}
