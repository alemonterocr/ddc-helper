---
name: WidgetRow
type: molecule
status: built
atomic-layer: molecule
---

# WidgetRow

Per-widget review card for the Translate Page tab. Sibling of `LabelRow`, shaped
for `SpanishWidgetRow` (page widgets) instead of `SpanishLabelRow` (labels).

## Purpose

Show one editable page widget under translation: a `content`/`raw` type badge,
its `windowId`, a collapsible English preview, an editable Spanish textarea,
warnings, the translator's reasoning, and Save / Skip / Retranslate actions.

## Inputs

- `row: SpanishWidgetRow`
- `onEsChange(esHtml)`, `onSave()`, `onSkip()`, `onRetranslate()`
- `busy: boolean` — disables actions during a save/retranslate call.

## Behaviour

- `queued`/`translating` → shows "Translating…", hides the editor + actions.
- `saved`/`skipped` → locked (no editor, no actions).
- `ready`/`error` → editor + Save enabled (error rows are still hand-saveable).

## Dependencies

- shadcn `Card`, `Badge`, `Button`, `Textarea`, `Collapsible`.
