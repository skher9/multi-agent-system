"use client";

import { useEffect, useRef, useState } from "react";

import type { FeedItem, FeedTone } from "@/lib/runs/feed";

// Typographic marks, not emoji: quiet in the feed, coloured only where it matters
const ICON: Record<FeedTone, { mark: string; className: string }> = {
  thought: { mark: "~", className: "text-muted" },
  tool: { mark: "→", className: "text-muted" },
  good: { mark: "✓", className: "text-ok" },
  bad: { mark: "!", className: "font-semibold text-bad" },
  info: { mark: "·", className: "text-muted" },
};

const ROLE_CHIP = "bg-raised text-ink";
const RUN_CHIP = "bg-transparent text-muted";

/** What the agents think and do, oldest at the top; keeps the newest line in view. */
export function Feed({
  items,
  thinkingRole = null,
}: {
  items: FeedItem[];
  thinkingRole?: string | null; // live runs: who is working now, shown as typing dots
}) {
  const box = useRef<HTMLOListElement>(null);

  useEffect(() => {
    const el = box.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [items.length, thinkingRole]);

  return (
    <ol
      ref={box}
      aria-label="Live feed"
      aria-live="polite"
      className="h-[28rem] space-y-1 overflow-y-auto rounded-lg border border-line bg-surface p-2"
    >
      {items.length === 0 && <li className="p-2 text-sm text-gray-500">Waiting for the run…</li>}
      {items.map((item) => (
        <li
          key={item.id}
          className={`flex gap-2 rounded px-2 py-1.5 text-sm ${
            item.tone === "thought" ? "bg-raised/60" : ""
          }`}
        >
          <span
            aria-hidden
            className={`w-5 shrink-0 text-center font-mono ${ICON[item.tone].className}`}
          >
            {ICON[item.tone].mark}
          </span>
          <span className="min-w-0 flex-1">
            <span
              className={`mr-2 rounded px-1.5 py-0.5 text-xs font-medium ${item.role === "run" ? RUN_CHIP : ROLE_CHIP}`}
            >
              {item.role}
            </span>
            {item.tone === "thought" ? (
              <Thought text={item.title} />
            ) : (
              <span
                className={item.tone === "tool" ? "break-all font-mono text-xs" : "font-medium"}
              >
                {item.title}
              </span>
            )}
            {item.detail && (
              <span className="block break-words text-xs text-gray-500">{item.detail}</span>
            )}
          </span>
        </li>
      ))}
      {thinkingRole && (
        <li className="flex items-center gap-2 px-2 py-1.5 text-sm text-muted">
          <span aria-hidden className="w-5 shrink-0 text-center font-mono">
            ~
          </span>
          <span
            className={`rounded px-1.5 py-0.5 text-xs font-medium ${thinkingRole === "run" ? RUN_CHIP : ROLE_CHIP}`}
          >
            {thinkingRole}
          </span>
          <span>is working</span>
          <span className="flex gap-0.5" aria-hidden>
            <span className="size-1 animate-bounce rounded-full bg-current [animation-delay:-0.3s]" />
            <span className="size-1 animate-bounce rounded-full bg-current [animation-delay:-0.15s]" />
            <span className="size-1 animate-bounce rounded-full bg-current" />
          </span>
        </li>
      )}
    </ol>
  );
}

/** An agent's reasoning: the first lines, the rest on click. */
function Thought({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  const long = text.length > 280;
  return (
    <span className="block">
      <span
        className={`block whitespace-pre-line italic text-muted ${
          long && !open ? "line-clamp-4" : ""
        }`}
      >
        {text}
      </span>
      {long && (
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          className="text-xs text-accent hover:underline"
        >
          {open ? "Show less" : "Show more"}
        </button>
      )}
    </span>
  );
}
