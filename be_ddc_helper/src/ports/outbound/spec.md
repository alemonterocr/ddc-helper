---
name: outbound-ports
type: port
status: planned
layer: port
---

## Purpose
Abstract interfaces for everything the pipeline calls out to: LLM provider and
browser bridge. Adapters implement these — swapping Anthropic for another
provider requires only a new adapter, zero application changes.

## Inputs
n/a (interface definitions)

## Outputs

### `LLMPort`
| Method | Purpose | Model tier |
|---|---|---|
| `analyze(skeleton, catalog, rules) → SectionPlan` | Full page layout planning | Main model |
| `clean_html(raw_html, base_url) → SectionPlan` | Standalone HTML cleanup | Main model |
| `enrich_content(sections) → list[dict]` | Batch HTML cleanup + intent writing | Light model |
| `classify_chrome_batch(snippets) → list["KEEP" \| "DROP"]` | Batched chrome-candidate review — same order as input | Light model |
| `classify_image_splits(items) → list[list[bool]]` | Batched per-image promote/keep for residual `<img>` in content widgets | Light model |
| `validate() → bool` | API key health check | Any |

### `BrowserBridgePort`
- `execute_section(cmd: SectionCommand) → SectionResult`

## Contracts
- No Anthropic, LangGraph, or WebSocket imports
- Defined as Python Protocols
- `classify_chrome_batch` returns exactly `"KEEP"` or `"DROP"` per entry (uppercase) — same length and order as input
- `classify_image_splits` returns one inner list per input item, sized to the count of `<img>` in that item's html — adapters pad/truncate to enforce

## Dependencies
- `domain.models`
