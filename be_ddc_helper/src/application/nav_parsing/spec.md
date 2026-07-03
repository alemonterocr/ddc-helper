# `application/nav_parsing/`

GM-project navigation-menu parser. One-node LangGraph.

## What it does
Takes raw navigation-menu HTML + a base URL → returns a deduplicated list of
`{title, url, category}` dicts, where `category` is `general` or `model_specific`.

Used by `POST /parse-nav` (see `adapters/inbound/http/parse_nav_router.py`).
Called when a user creates a new GM Prebuild project; the parsed pages become
the project's initial page list.

## Why a graph for one node?
Architectural consistency with the analyze flow. Likely additions later:
- Validation (probe URLs for 200)
- Dedup against existing pages
- Cache (same dealer + same HTML → skip the LLM call)

## State shape
`NavParseState` in `parse_nav_node.py`:
```py
{ html, base_url, dealer_id, pages, warnings }
```

## LLM contract
`LLMPort.parse_nav(html, base_url) -> list[{title, url, category}]`

Prompt in `adapters/outbound/prompts.py:build_nav_parser_system_prompt()`.

## Fail-safe
Any exception → empty list + warning. Frontend handles "no pages" as a soft
error (user can retry with cleaner HTML).
