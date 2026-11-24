/** A panel with an ink outline and a pastel shadow. Renders as the element that fits its
 * content: a section with a heading, an article or list item for one entry in a list. */

import type { HTMLAttributes } from "react";

import { TONE_SHADOW, type Tone } from "./tone";

type CardProps = HTMLAttributes<HTMLElement> & {
  as?: "section" | "article" | "aside" | "header" | "li" | "div";
  tone?: Tone;
};

export function Card({
  as: Element = "section",
  tone = "lilac",
  className = "",
  ...props
}: CardProps) {
  return (
    <Element
      {...props}
      className={`rounded-3xl border-ink-line bg-surface p-6 sm:p-7 ${TONE_SHADOW[tone]} ${className}`}
    />
  );
}
