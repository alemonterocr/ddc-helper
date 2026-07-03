---
name: templates
type: template
status: planned
atomic-layer: template
---

## Purpose
Layout wrappers that define the visual structure of a page without knowing
what content fills it. No logic, no state, no service references.

## Contracts
- Zero business logic
- Zero service imports
- Pure layout/spacing
- One template per folder, folder name matches the export

## Dependencies
- atoms (for layout primitives if needed)

## Status

**No templates currently exist.** The folder is preserved as a layer slot in
the atomic taxonomy. `MigrationLayout` lived here until it was deleted
alongside the dead `MigrationPage` it was paired with — the two live pages
(`ProjectListPage`, `ProjectPage`) each define their own outer chrome
inline because their layouts diverge significantly and abstracting them
would have produced a single-use template each.

Add a template here when two pages start sharing the same layout chrome.
