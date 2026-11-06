---
name: figma-design-to-code
description: How to build a screen from the <design> block (a Figma frame): layout, tokens, assets, components, and the checks before finishing. Load before writing any code for a ticket with a design.
when: always
---
# Building a screen from a Figma design

Adapted from Figma's own design-to-code rules (github.com/figma/mcp-server-guide) for the
<design> block. The design is the visual target: match it, in this repo's stack and style.

## Layout: flexbox from auto-layout, never coordinates
- Every "flex row|column ..." layer is a flex container: copy direction, gap, padding,
  justify and align exactly. Don't round or "improve" values: 24 stays 24.
- "w fill" = `flex: 1` (in a row) or `align-self: stretch` / `w-full` (in a column).
  "w hug" = no width. A number = that fixed size; use max-width instead for the outer
  frame of a page so it still works on small screens.
- "positioned" layers had no auto-layout in Figma. Work out the intended row, column or
  grid from their x/y and sizes. Only overlays (a badge on an avatar, a floating button)
  get `position: absolute`. Never absolute-position a whole section or screen.
- Layer names like "Frame 12" or "Group 3" mean nothing: name components by what they are.

## Tokens: one set of values
- Before writing components, map the design's tokens to the repo's theme (Tailwind
  config, CSS variables, theme file). Reuse a repo token when the value matches.
- A design value with no repo token: add it to the theme once, with a name that says what
  it is (e.g. `--color-text-muted`), then use the token. No raw hex or px in components.
- Text styles: one class or component per style in the tokens list, reused everywhere.

## Assets: use them, never redraw
- Every image and icon in "Assets" is already in the repo. Put each one exactly where its
  layer is, at the layer's size. Use the served path (e.g. `/figma/logo.svg`).
- Never redraw an icon as inline SVG paths, swap it for an icon library, or leave it out.
- Images: `next/image` with the layer's width and height when the repo uses Next.js;
  "fit cover" = `object-fit: cover`, "fit contain" = `object-fit: contain`. Give real alt
  text from what the image shows (decorative ones: `alt=""`).

## Components and behaviour
- A layer with (component "Button/Primary") is a reusable component: look for the repo's
  own (search components/, ui/) and use it, with props for the variant, before building
  one. Same component in the design = same component in code.
- The design is a still picture. Decide what is interactive (buttons, links, inputs, tabs)
  and build it as real elements: `<button>`, `<a>`/`Link`, `<input>` with a `<label>`.
  Hover and focus states: follow the repo's existing ones.
- Text in the layers is the content: copy it exactly (case, punctuation). "uppercase"
  means CSS `text-transform`, not rewritten text.

## Before you call finish
- Walk the layer list top to bottom and check each layer has a match in your code: size,
  spacing, colour token, font style, radius, shadow, asset.
- Narrow screens: the page must not scroll sideways at 375px wide. Rows that don't fit
  wrap or stack.
- Mention in the summary anything you couldn't match and why.
