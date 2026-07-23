# `application/staff_migration/`

Staff-page workflow. Two flows:

## Extract (analyze)
One-node LangGraph: takes raw page HTML + base URL → `StaffMember[]`.

- `html_clean.py` — `strip_noise(html)` drops `<script>`/`<style>`/`<svg>`/
  head-junk and inline `style=` attributes (bs4). Helps token-heavy templates;
  on a clean roster page it barely reduces size (the content *is* the staff).
  Fail-safe: returns input unchanged on parse error.
- `extract_staff_node.py` — `strip_noise` -> **single** `llm.extract_staff` over
  the whole page -> filter. The page fits the context easily (~18-27k input vs a
  200k window), and one call keeps department names consistent (chunking made
  independent calls that re-invented departments). The node reports input size
  over the progress channel.
- `staff_graph.py` — graph wiring
- Triggered by `POST /parse-staff` — returns `token_info` on every path,
  including failure.
- Anthropic `extract_staff` output `max_tokens=32000` — real room for a large
  roster's JSON, still under Haiku's 64k output ceiling (8192 truncated big
  rosters; the constraint is output, not input).

## Execute
Sequential async class (not LangGraph) — same reasoning as `MigrationExecutor`.

Unlike regular pages, staff data is injected as widget data into the existing
`ws-staff-listing` widget on `/dealership/staff.htm` — no page is created.
This matches the cms-auto-builder pattern.

Steps:
1. **resolve_staff_folder** — `Do Not Delete / {project_root} / Staff` via
   `staff_folder_service.resolve_staff_folder(project_type, ...)`
2. **upload_photos** — per-staff, reuses the existing `upload_media_image` tool;
   fills `photo` field with CDN URL; failures leave `photo=""`
3. **create_departments** — registers department labels (via `update_site_labels`)
   and department entries (via `inject_itemlist` → `department-info-list`) in
   DDC, one at a time with cumulative payloads since both endpoints replace the
   full set. Then remaps staff members' `department` from human-readable names
   to DDC department IDs.
4. **inject_staff_listing** — POSTs a `ws-staff-listing` itemlist payload to
   DDC via a new `inject_staff_listing` injected tool

Triggered by `POST /execute-staff`.

## Folder convention by project type
| project_type | root folder | leaf |
|---|---|---|
| `cm`          | `Custom Migration` | `Staff` |
| `gm-prebuild` | `Prebuild`         | `Staff` |
| `gm-buysell`  | N/A — Buysell projects don't migrate pages | — |

## State shape
`StaffExtractState` for the analyze graph:
```py
{ html, base_url, dealer_id, staff, warnings }
```

For execute we use a `StaffExecutor` class with instance state (no LangGraph).

## Fail-safe
LLM exceptions → empty staff list + warning. The frontend can then offer "retry"
or a manual JSON paste fallback (sibling project pattern).
