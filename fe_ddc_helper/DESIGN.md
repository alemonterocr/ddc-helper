---
name: fe_ddc_helper
description: Design system for the DDC Agentic Page Cloner Chrome extension — a quiet, precise console for migration specialists.
colors:
  primary: "oklch(0.45 0.085 224.283)"
  primary-foreground: "oklch(0.984 0.019 200.873)"
  background: "oklch(0.145 0 0)"
  foreground: "oklch(0.985 0 0)"
  card: "oklch(0.205 0 0)"
  card-foreground: "oklch(0.985 0 0)"
  muted: "oklch(0.269 0 0)"
  muted-foreground: "oklch(0.708 0 0)"
  border: "oklch(1 0 0 / 10%)"
  input: "oklch(1 0 0 / 15%)"
  ring: "oklch(0.556 0 0)"
  destructive: "oklch(0.704 0.191 22.216)"
  warning: "oklch(0.85 0.16 85)"
  warning-foreground: "oklch(0.15 0 0)"
  success: "oklch(0.7 0.18 145)"
  success-foreground: "oklch(0.985 0 0)"
  chart-1: "oklch(0.809 0.105 251.813)"
  chart-2: "oklch(0.623 0.214 259.815)"
  chart-3: "oklch(0.546 0.245 262.881)"
  chart-4: "oklch(0.488 0.243 264.376)"
  chart-5: "oklch(0.424 0.199 265.638)"
  sidebar: "oklch(0.205 0 0)"
  sidebar-primary: "oklch(0.715 0.143 215.221)"
typography:
  display:
    fontFamily: "Inter Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-0.01em"
  headline:
    fontFamily: "Inter Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.125rem"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "-0.005em"
  title:
    fontFamily: "Inter Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: "normal"
  body:
    fontFamily: "Inter Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
  label:
    fontFamily: "Inter Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 500
    lineHeight: 1.3
    letterSpacing: "0.02em"
rounded:
  sm: "0.3rem"
  md: "0.4rem"
  lg: "0.5rem"
  xl: "0.7rem"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.primary-foreground}"
    rounded: "{rounded.md}"
    padding: "0.5rem 0.875rem"
  button-primary-hover:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.primary-foreground}"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.foreground}"
    rounded: "{rounded.md}"
    padding: "0.5rem 0.75rem"
  button-ghost-hover:
    backgroundColor: "{colors.muted}"
    textColor: "{colors.foreground}"
  input:
    backgroundColor: "{colors.input}"
    textColor: "{colors.foreground}"
    rounded: "{rounded.md}"
    padding: "0.5rem 0.75rem"
  card:
    backgroundColor: "{colors.card}"
    textColor: "{colors.card-foreground}"
    rounded: "{rounded.lg}"
    padding: "1rem"
  sidebar-item:
    backgroundColor: "transparent"
    textColor: "{colors.foreground}"
    rounded: "{rounded.md}"
    padding: "0.375rem 0.625rem"
  sidebar-item-active:
    backgroundColor: "{colors.muted}"
    textColor: "{colors.foreground}"
---

# Design System: fe_ddc_helper

## 1. Overview

**Creative North Star: "The Quiet Console"**

This is a dark-mode operator surface, not a marketing page and not a
consumer app. The specialist opens it beside a DDC CMS tab in Chrome and
works through one migration at a time — sometimes for an hour, sometimes
for a full shift. The design serves the task: state is legible without
squinting, primary actions are obvious without shouting, and nothing
decorative competes with information.

The system explicitly rejects the Vite / React scaffolding aesthetic:
gradient backgrounds, purple/pink accents, hero counters, oversized landing
typography, and marketing energy leaking into a tool surface. It also
rejects the Bootstrap admin-template look (colorful stat cards, rounded
pill everything) and the Salesforce Lightning density (40 buttons above
the fold).

**Key Characteristics:**
- Dark-mode only; a single palette, no theme toggle.
- One accent hue (Steady Teal) reserved for the primary action and active state.
- Type carries hierarchy — color does not.
- Flat surfaces layered by tonal shift; no shadows.
- Motion only signals state, never decorates.

## 2. Colors

A restrained near-black surface layered with muted slates. Color earns its keep — used only to communicate state, never to decorate.

### Primary
- **Steady Teal** (`oklch(0.45 0.085 224.283)`): the one accent. Reserved for the primary action per screen, the active sidebar item, and the focus ring on interactive elements. Never used decoratively.

### Neutral
- **Console Ink** (`oklch(0.145 0 0)`): the base background. Near-black, no hue cast.
- **Console Slate** (`oklch(0.205 0 0)`): raised surfaces — cards, sidebar, popovers.
- **Muted Slate** (`oklch(0.269 0 0)`): hover state on ghost surfaces; secondary panels.
- **Console Ivory** (`oklch(0.985 0 0)`): primary text and iconography.
- **Slate Foreground** (`oklch(0.708 0 0)`): secondary text, timestamps, meta.
- **Border Hairline** (`oklch(1 0 0 / 10%)`): every border, always 1px, always this token.

### State Signals
- **Signal Red** (`oklch(0.704 0.191 22.216)`): destructive actions, hard errors.
- **Signal Amber** (`oklch(0.85 0.16 85)`): warnings, non-blocking issues.
- **Signal Green** (`oklch(0.7 0.18 145)`): success confirmations, healthy status.

### Data
- **Data Blues** (`chart-1` → `chart-5`, `oklch(0.809 0.105 251.813)` stepping to `oklch(0.424 0.199 265.638)`): sequential blues for the (future) analysis dashboard. Never used for interactive elements.

### Named Rules
**The One Accent Rule.** Steady Teal is used on ≤10% of any given screen. Its rarity is what makes the primary action findable. If two elements on the same screen both use teal, one of them is wrong.

**The Signal-Only Color Rule.** Red / Amber / Green are used *only* to signal state (error, warning, success). They are never used as brand color, decoration, or category tags.

**The No Purple Rule.** The dead `hsl(262.1 83.3% 57.8%)` in `src/index.css` (line ~55) is a leftover from shadcn's default template and must be removed. Purple has no role in this system.

## 3. Typography

**Body Font:** Inter Variable (with `ui-sans-serif, system-ui, sans-serif` fallback).
**Display Font:** same — Inter carries the whole scale.
**Label/Mono Font:** none currently. If code / URL snippets need mono treatment, add `ui-monospace, SFMono-Regular, Consolas` later; do not introduce a display serif.

**Character:** Inter is chosen because it is quiet, legible at small sizes, and instantly recognizable as "software product" rather than "brand". The whole scale sits within it — hierarchy comes from weight and size, not from a second family.

### Hierarchy
- **Display** (600, 1.5rem / 24px, line-height 1.2): screen title (`ProjectPage` header). One per screen, no exceptions.
- **Headline** (600, 1.125rem / 18px, line-height 1.3): section headings inside a screen (panel titles).
- **Title** (500, 0.9375rem / 15px, line-height 1.4): card / row primary labels; list item titles.
- **Body** (400, 0.875rem / 14px, line-height 1.5): default reading text, form values, description text. Max line length ~75ch.
- **Label** (500, 0.75rem / 12px, letter-spacing 0.02em): form field labels, table headers, sidebar item labels. Sentence case, not uppercase.

### Named Rules
**The One Display Rule.** Each screen has exactly one Display-sized element — the screen title. Never two.

**The No Uppercase Rule.** Labels are sentence case. No `text-transform: uppercase` anywhere. Uppercase reads as marketing shout, not tool label.

## 4. Elevation

The system is **flat**. There are no drop shadows. Depth comes from tonal layering: `background` (Console Ink) → `card` (Console Slate) → `muted` (Muted Slate). Each step is a small lightness lift on the same near-neutral, so the surface reads as *layered paper* rather than *floating chips*.

Focus state is the only "elevated" moment — a 2px teal ring (`--ring`) offset from the element edge, no glow, no shadow.

### Named Rules
**The Flat-By-Default Rule.** Surfaces are flat at rest. No `box-shadow` on cards, panels, or popovers. Depth is tonal, not lit.

**The Focus-Is-The-Only-Glow Rule.** The only moment a ring appears around an element is when it receives keyboard focus. Never on hover, never on selected, never as decorative highlight.

## 5. Components

### Buttons
- **Shape:** medium radius (`rounded.md` = ~0.4rem / 6.4px). Not pill-round, not square.
- **Primary:** background Steady Teal, text Ivory, padding 0.5rem 0.875rem. One per screen. `hover` darkens the teal slightly by lowering `L`; no shadow.
- **Ghost:** transparent background, text Ivory, same padding. `hover` fills with Muted Slate. Used for secondary and toolbar actions.
- **Destructive:** background Signal Red only for irreversible actions (delete project, reset migration). Never for cancel.
- **Focus:** 2px Steady Teal ring, offset 2px. Visible on keyboard focus only.

### Cards / Containers
- **Corner Style:** large radius (`rounded.lg` = 0.5rem / 8px).
- **Background:** Console Slate on Console Ink surface.
- **Shadow Strategy:** none (see Elevation).
- **Border:** 1px Border Hairline on all sides — the only visual boundary.
- **Internal Padding:** 1rem base; tighter (0.75rem) inside compact list rows.

### Inputs / Fields
- **Style:** semi-opaque white background (`--input` at 15% alpha over Console Ink), Ivory text, `rounded.md`.
- **Focus:** 2px Steady Teal ring, offset 2px. Border does NOT change color on focus (avoids double-signal).
- **Error:** border shifts to Signal Red; error text below in Signal Red at Label size.
- **Disabled:** 50% opacity; no state color.

### Sidebar / Navigation
- **Style:** Console Slate panel, 1px Border Hairline separating from main surface.
- **Item shape:** `rounded.md`, padding 0.375rem 0.625rem.
- **Default:** transparent background, Ivory text.
- **Hover:** Muted Slate background.
- **Active:** Muted Slate background + Steady Teal accent on the left edge (2px bar) OR Steady Teal text — never both.

### Status / Progress
- **Idle / neutral:** Slate Foreground text, no icon color.
- **Analyzing / executing:** Steady Teal small spinner + label. No pulsing background.
- **Success:** Signal Green icon + label.
- **Error:** Signal Red icon + label + one-line reason.
- Backend progress messages render *in place* below the primary action, not as toasts.

### Charts (future)
- Sequential Data Blues (`chart-1` → `chart-5`) for ordered categories. Never re-mapped as UI accent color.
- Axis and gridlines in Border Hairline.
- No 3D, no gradients, no animated entrances.

## 6. Do's and Don'ts

### Do:
- **Do** reserve Steady Teal for the primary action per screen and the active sidebar item. Nothing else.
- **Do** use type weight and size to build hierarchy. Color changes are reserved for state.
- **Do** render backend progress messages in place, next to the action that triggered them.
- **Do** keep every border at 1px and use `Border Hairline` for all of them.
- **Do** show a visible focus ring on every keyboard-focusable element.
- **Do** ship one Display-sized element per screen — the screen title.

### Don't:
- **Don't** introduce gradients anywhere. Not in backgrounds, not in buttons, not in charts.
- **Don't** use purple or pink accents. Delete the `hsl(262.1 83.3% 57.8%)` block in `src/index.css` — it's a Vite scaffolding leftover.
- **Don't** leak Vite / React scaffolding aesthetics into the tool: no hero counter, no oversized landing typography, no "Let's build something great!" micro-copy.
- **Don't** use `box-shadow` on cards, panels, popovers, or toolbars. Depth is tonal.
- **Don't** use `text-transform: uppercase` on labels. Sentence case only.
- **Don't** add a colorful stat-card row across the top of any screen (Bootstrap admin-template tell).
- **Don't** put more than one Steady Teal element on the same screen. If two look right, one is wrong.
- **Don't** pair color with color for state signals — pair color with an icon or explicit text. Color-blind operators must still read state.
- **Don't** add decorative motion. Motion signals state changes and nothing else.
- **Don't** add a "confirm?" dialog on reversible actions. Trust the operator; only guard against destructive irreversibles.
