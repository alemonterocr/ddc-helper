---
name: StaffMemberCard
type: molecule
status: built
atomic-layer: molecule
---

# StaffMemberCard

Per-member review card for the staff-migration review step (rendered by
`StaffFlowPanel`, grouped by department). Shows one extracted `StaffMember` and
lets the reviewer correct it before `/execute-staff` runs.

## Purpose

Two modes in one component:

- **Read view** — round avatar (photo or fallback icon), name, a `no photo`
  badge when absent, title, phone, email, bio, plus hover Edit / Remove actions.
- **Edit view** — a draft form over name, title, phone, email, bio, and
  **photo URL**, with a live avatar preview, Cancel, and Save.

The photo-URL field exists because the LLM sometimes extracts the wrong
`original_photo_url` (or misses one). Without it a bad photo could not be fixed
before execution.

## Props / Inputs

- `member: StaffMember` — the row to display / edit.
- `index: number` — position inside its department array; passed back on every
  callback so the parent can locate the row in the store.
- `onEdit(index, patch: Partial<StaffMember>)` — commit an edit.
- `onDelete(index)` — remove the member.

## Outputs / Emits

- `onEdit` fires on Save with a patch of `{ name, title, phone, email, bio,
  original_photo_url, has_photo }`, plus `photo: null` **only when the source
  URL changed** (see Contracts).
- `onDelete` fires from the read-view Remove action.
- No direct store or `chrome.*` access — all mutation flows through the props.

## Contracts

- **Photo normalization on Save:** `original_photo_url` is trimmed; empty → `null`.
  `has_photo` is derived as `!!original_photo_url` (never trusted from input).
- **Re-upload on source change:** when the saved `original_photo_url` differs
  from the member's previous one, the already-uploaded CDN `photo` is cleared
  (`photo: null`) so execution re-uploads from the corrected source. Unchanged
  URL leaves `photo` intact (no needless re-upload).
- **Clear (×) button** sets both `original_photo_url` and `photo` to `null` →
  member renders with the fallback avatar and the `no photo` badge.
- **Avatar** falls back to a `User` icon when the URL is absent or fails to load;
  it is keyed by URL so the load-error state resets when the URL changes.
- Save is disabled while `draft.name` is blank.

## Dependencies

- shadcn `Button`, `Input`, `Textarea`, `Badge`, `Field` / `FieldLabel`.
- `lucide-react` icons (`Pencil`, `X`, `User`, `Check`).
- `StaffMember` type (`src/types`).
