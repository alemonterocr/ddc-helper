---
name: PageTranslateTab
type: organism
status: built
atomic-layer: organism
---

# PageTranslateTab

Third tab of the Spanish project view (`[Simple Labels] [Translate Nav] [Translate Page]`).
Feature: `specs/004-translate-pages/spec.md`.

## Purpose

Translate a page's editable content + RAW HTML widgets. The user enters a target
path; the tab fetches both locale renders (via `PagePort.loadPage`, in parallel),
streams them to the backend, and renders a live-filling review board.

## Inputs

- `project: SpanishMigrationProject` — supplies `dealerId`, `dealerName`, and the
  persisted `pageWidgets` / `pageTargetPath`.

## Behaviour

1. `ensureProvider()` pushes the stored API key to the BE (`configureApiKey`).
2. `Promise.all([loadPage(en_US), loadPage(es_US)])`.
3. `PagePort.translatePageStream` — NDJSON events:
   - `checked` → lay out placeholder rows (`to_translate`) + skipped footer.
   - `widget` → resolve the matching row by `windowId`.
   - `error` → surface inline.
4. Per row: **Save** (two-save via `saveWidget`), **Skip**, **Retranslate**
   (reuses `LabelPort.translateLabel`). Skipped footer offers **Force translate**.

## Dependencies

- `PagePort` (loadPage, translatePageStream, saveWidget), `LabelPort.translateLabel`,
  `BackendPort.configureApiKey`, `CredentialPort`, `useMigrationStore`
  (`setPageWidgets`, `updatePageWidget`), `WidgetRow`.
