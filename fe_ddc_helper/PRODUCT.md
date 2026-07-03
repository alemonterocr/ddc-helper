# Product

## Register

product

## Users

DDC migration specialists at Cox Automotive. Internal tool only. Trained
operators doing repeated migrations from live dealer websites into DDC CMS;
they open the extension alongside a DDC CMS tab in Chrome and drive one
migration at a time. Their context is task-focused, not exploratory — they
know the workflow and want the tool to stay out of the way.

## Product Purpose

Chrome extension (Manifest v3) that lets a specialist clone a dealership's
live-site page into DDC CMS. It captures the page's DOM skeleton, hands it
to a backend LangGraph pipeline for structural analysis, renders the
resulting section plan for review, and executes injection into the active
DDC CMS tab.

Success looks like: a specialist opens the extension, pastes a URL, reviews
the plan without doubt about what will happen, hits Execute, and gets a
correctly-built DDC page — without needing to context-switch to check that
the tool understood them.

## Brand Personality

**Precise, quiet, reliable.**

- **Precise** — every number, status, and label reflects real backend state; nothing decorative that could be mistaken for information.
- **Quiet** — nothing shouts. No decorative motion, no hero moments, no attention-grabbing color use. The specialist is the star; the tool is the surface they work on.
- **Reliable** — visible state transitions during analyze/execute, honest error surfaces, no optimistic UI that later has to backtrack.

## Anti-references

**Vite / React scaffolding demo aesthetic.** Specifically:
- No gradient backgrounds.
- No purple/pink hackathon accents (the leftover `hsl(262.1 83.3% 57.8%)` in `index.css` needs to go — it conflicts with the intended teal primary).
- No hero elements, counter demos, or oversized landing-page typography leaking into a tool surface.
- No marketing-energy micro-copy ("Let's build something great!") — this is an internal tool used by trained specialists, not an onboarding flow.
- No decorative illustrations, animated blob backgrounds, or personality mascots.

Adjacent things to also avoid: Salesforce Lightning density (40 buttons above the fold), and Bootstrap 4 admin-template look (colorful stat cards, gradient sidebar, rounded pill buttons everywhere).

## Design Principles

1. **Clarity over decoration.** If a pixel isn't carrying information or affordance, cut it. Type hierarchy and spacing rhythm carry more weight than color.
2. **State is always visible.** The current phase of the migration (idle / analyzing / reviewing / executing / errored) is legible without clicking. Progress messages arrive from the backend and render in place, not in a toast queue.
3. **One primary action per screen.** The specialist should never have to hunt for what to do next. Secondary actions are visually subordinate, not competing.
4. **Trust the operator.** No confirmations for reversible actions. No hand-holding tooltips on obvious controls. Guardrails only where a mistake destroys work.
5. **Consistent surfaces.** shadcn/ui primitives first; custom components only when shadcn has no fit (see constitution Principle VI). Two competing primaries in `index.css` today is the kind of drift this principle exists to prevent.

## Accessibility & Inclusion

No formal WCAG target — internal-only tool with a known operator base.
Best-effort floor:
- Contrast ratios sensible against the dark theme (avoid low-contrast gray-on-gray).
- Visible focus rings on every interactive element (keyboard-driven review is realistic during long sessions).
- No color-only state signals (pair color with icon or text).

If external audiences (non-specialists) ever start using this, revisit and set a formal target then.
