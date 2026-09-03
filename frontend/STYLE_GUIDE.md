# Congress Tracker Frontend Style Guide

## Goal
Create an editorial civics UI that feels deliberate and readable, not dashboard-generic.

## Visual Direction
- Tone: archival + contemporary civic interface.
- Personality: structured, warm paper surface, strong data accents.
- Contrast: prioritize legibility over ornamental effects.

## Foundations

### Color Tokens
- `--bg`: page background wash.
- `--surface`: card and panel base.
- `--ink`: main text.
- `--muted`: secondary text.
- `--line`: separators and strokes.
- `--brand` / `--brand-strong`: primary action + emphasis.

### Typography
- Base family: Public Sans.
- Heading style: compact with high contrast and tighter spacing.
- Body style: calm line-height with muted secondary copy.

### Shape + Elevation
- Radius: use consistent rounded corners (`--radius`).
- Shadow: one soft elevation system (`--shadow`) across cards/panels.

## Layout Principles
- Keep page sections in clear stacked blocks with consistent gap rhythm.
- Use two-column only where content naturally separates (map + inspector, portrait + metadata).
- Favor cards/panels for semantic grouping.

## Component Patterns

### Member Hero Card
- Large portrait on left (desktop) with title + metadata chips.
- Short subtitle line with party/state/bioguide.
- Keep immediate profile context visible above activity lists.

### Vertical Timeline
- Use a single left rail with nodes and card events.
- Event cards should include a compact status row and readable title.
- Party dots are supportive cues, not primary color blocks.

### Badges + Chips
- Use chips for metadata tags and quick filters.
- Keep chip palette quiet; reserve saturated color for key interactions.

## Interaction Rules
- Hover states should increase clarity (border, text, fill) not add motion noise.
- Keep transitions short (120-180ms).
- Preserve keyboard focus clarity on interactive map states and links.

## Accessibility Baseline
- Ensure text/background contrast remains readable in all panels.
- Keep semantic headings in order (`h1` -> `h2` -> `h3`).
- Avoid color-only meaning for party or status indicators.

## References
- Radix primitives overview: https://www.radix-ui.com/primitives/docs/overview/introduction
- shadcn card patterns: https://ui.shadcn.com/docs/components/card
- shadcn avatar patterns: https://ui.shadcn.com/docs/components/avatar
- shadcn badge patterns: https://ui.shadcn.com/docs/components/badge
