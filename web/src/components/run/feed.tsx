"use client";

import { useEffect, useRef } from "react";

import type { FeedItem, FeedTone } from "@/lib/runs/feed";

const ICON: Record<FeedTone, string> = {
  thought: "💭",
  tool: "🔧",
  good: "✅",
  bad: "⚠️",
  info: "▸",
};

const ROLE_STYLE: Record<string, string> = {
  reader: "bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-200",
  planner: "bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-200",
  developer: "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200",
  fixer: "bg-orange-100 text-orange-800 dark:bg-orange-950 dark:text-orange-200",
  qa: "bg-teal-100 text-teal-800 dark:bg-teal-950 dark:text-teal-200",
  reviewer: "bg-pink-100 text-pink-800 dark:bg-pink-950 dark:text-pink-200",
};
const RUN_STYLE = "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300";

/** What the agents think and do, oldest at the top; keeps the newest line in view. */
export function Feed({ items }: { items: FeedItem[] }) {
  const box = useRef<HTMLOListElement>(null);

  useEffect(() => {
    const el = box.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [items.length]);

  return (
    <ol
      ref={box}
      aria-label="Live feed"
      aria-live="polite"
      className="h-[28rem] space-y-1 overflow-y-auto rounded-lg border border-gray-200 p-2 dark:border-gray-800"
    >
      {items.length === 0 && <li className="p-2 text-sm text-gray-500">Waiting for the run…</li>}
      {items.map((item) => (
        <li
          key={item.id}
          className={`flex gap-2 rounded px-2 py-1.5 text-sm ${
            item.tone === "thought" ? "bg-gray-50 dark:bg-gray-900" : ""
          }`}
        >
          <span aria-hidden className="w-5 shrink-0 text-center">
            {ICON[item.tone]}
          </span>
          <span className="min-w-0 flex-1">
            <span
              className={`mr-2 rounded px-1.5 py-0.5 text-xs font-medium ${ROLE_STYLE[item.role] ?? RUN_STYLE}`}
            >
              {item.role}
            </span>
            <span
              className={
                item.tone === "thought"
                  ? "italic text-gray-700 dark:text-gray-300"
                  : item.tone === "tool"
                    ? "break-all font-mono text-xs"
                    : "font-medium"
              }
            >
              {item.title}
            </span>
            {item.detail && (
              <span className="block break-words text-xs text-gray-500">{item.detail}</span>
            )}
          </span>
        </li>
      ))}
    </ol>
  );
}
