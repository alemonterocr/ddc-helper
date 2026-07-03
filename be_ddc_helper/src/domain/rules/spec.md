---
name: planning-rules
type: domain-rule
status: planned
layer: domain
---

## Purpose
Human-readable + LLM-readable rules the Planner must follow when mapping a DOM
skeleton to a DDC section plan. Grows after every migration where the Verifier
catches a planning mistake.

## Inputs
n/a (static Markdown asset, inlined into Planner system prompt)

## Outputs
- `planning_rules.md` — the rules file itself

## Contracts
- Each rule must have a number, a statement, and a rationale
- New rules are appended (never remove old ones without explicit review)
- Rules are ordered by priority (earlier = higher priority)

## Dependencies
None

## Notes

### Planning rules (planning_rules.md)
1. Prefer `content` widget over `raw_html` whenever visually achievable.
2. Collapse adjacent same-type sections with no semantic separation.
3. Never recreate `map-hours` manually — it is pre-wired.
4. Order sections top-to-bottom by visual position.

### Chrome detection tiers (`src/domain/migration/chrome.py`)
The deterministic algo classifies nodes into three tiers before the LLM sees anything:

| Tier | Trigger | Action |
|---|---|---|
| Definite chrome | `header`, `footer`, `nav`, `aside` tags | Hard-pruned by `strip_chrome` |
| Content-anchored | Chrome class word + form/phone/hours in subtree | Rescued — kept as normal content |
| Chrome candidate | Chrome class word, no content anchor | Kept with `_chrome_candidate: True` for LLM review |

Content anchors checked by `has_content_anchor()`:
- `<form>`, `<input>`, `<textarea>`, `<select>` anywhere in subtree
- Phone number pattern `\d{3}[-.\s]?\d{3}[-.\s]?\d{4}` in text
- `<table>` containing day-of-week text (hours tables)

Chrome candidates are reviewed by `LLMPort.classify_chrome_batch()` in the
`chrome_review` node of the migration graph — one batched call covers all
candidates collected from the tree. DROP removes the subtree before
`build_node` runs; KEEP clears the flag.
