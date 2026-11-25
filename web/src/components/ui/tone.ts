/** The pastels: one per agent, also used for status chips and card shadows. Class names
 * are spelled out in full so Tailwind can find them. */

export type Tone = "butter" | "lilac" | "mint" | "peach" | "sky" | "rose" | "lime" | "plain";

export const TONE_BG: Record<Tone, string> = {
  butter: "bg-butter",
  lilac: "bg-lilac",
  mint: "bg-mint",
  peach: "bg-peach",
  sky: "bg-sky",
  rose: "bg-rose",
  lime: "bg-lime",
  plain: "bg-surface",
};

export const TONE_SHADOW: Record<Tone, string> = {
  butter: "shadow-[6px_6px_0_var(--color-butter)]",
  lilac: "shadow-[6px_6px_0_var(--color-lilac)]",
  mint: "shadow-[6px_6px_0_var(--color-mint)]",
  peach: "shadow-[6px_6px_0_var(--color-peach)]",
  sky: "shadow-[6px_6px_0_var(--color-sky)]",
  rose: "shadow-[6px_6px_0_var(--color-rose)]",
  lime: "shadow-[6px_6px_0_var(--color-lime)]",
  plain: "shadow-hard-sm",
};

/** The same shadows, shown only on hover (rows that lift when pointed at). */
export const TONE_HOVER_SHADOW: Record<Tone, string> = {
  butter: "hover:shadow-[5px_5px_0_var(--color-butter)]",
  lilac: "hover:shadow-[5px_5px_0_var(--color-lilac)]",
  mint: "hover:shadow-[5px_5px_0_var(--color-mint)]",
  peach: "hover:shadow-[5px_5px_0_var(--color-peach)]",
  sky: "hover:shadow-[5px_5px_0_var(--color-sky)]",
  rose: "hover:shadow-[5px_5px_0_var(--color-rose)]",
  lime: "hover:shadow-[5px_5px_0_var(--color-lime)]",
  plain: "hover:shadow-hard",
};
