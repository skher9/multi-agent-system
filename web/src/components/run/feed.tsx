"use client";

import { useEffect, useRef, useState } from "react";

import { Chip } from "@/components/ui/chip";
import { TONE_SHADOW } from "@/components/ui/tone";
import { agentTone } from "@/lib/agents";
import type { FeedItem, FeedTone } from "@/lib/runs/feed";

// Typographic marks, not emoji: quiet in the feed, coloured only where it matters
const ICON: Record<FeedTone, { mark: string; className: string }> = {
  thought: { mark: "~", className: "text-muted" },
  tool: { mark: "→", className: "text-muted" },
  good: { mark: "✓", className: "text-ok" },
  bad: { mark: "!", className: "font-semibold text-bad" },
  info: { mark: "·", className: "text-muted" },
};

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
      className={`h-[28rem] space-y-1 overflow-y-auto rounded-3xl border-ink-line bg-surface p-3 ${TONE_SHADOW.lilac}`}
    >
      {items.length === 0 && <li className="p-2 text-sm text-muted">Waiting for the run…</li>}
      {items.map((item) => (
        <li
          key={item.id}
          className={`flex gap-2 rounded-xl px-2 py-1.5 text-sm ${
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
            <Chip tone={agentTone(item.role)} className="mr-2 py-0 text-xs">
              {item.role}
            </Chip>
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
              <span className="block break-words text-xs text-muted">{item.detail}</span>
            )}
          </span>
        </li>
      ))}
      {thinkingRole && (
        <li className="flex items-center gap-2 px-2 py-1.5 text-sm text-muted">
          <span aria-hidden className="w-5 shrink-0 text-center font-mono">
            ~
          </span>
          <Chip tone={agentTone(thinkingRole)} className="py-0 text-xs">
            {thinkingRole}
          </Chip>
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
          className="text-xs font-semibold text-accent underline-offset-2 hover:underline"
        >
          {open ? "Show less" : "Show more"}
        </button>
      )}
    </span>
  );
}
