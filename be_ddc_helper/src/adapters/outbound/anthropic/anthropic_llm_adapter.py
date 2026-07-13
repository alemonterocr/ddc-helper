import json

import anthropic

from typing import Callable

_TOOL_LOOP_CAP = 5


def _json_dumps(value) -> str:
    return json.dumps(value, ensure_ascii=False)


_GLOSSARY_LOOKUP_TOOL = {
    "name": "glossary_lookup",
    "description": (
        "Look up authoritative Mexican Spanish translations for specific "
        "English terms used in dealership/automotive vocabulary. Use for "
        "domain terms you're uncertain about. Returns a dict mapping each "
        "queried term to its MX-Spanish, or null if not in the glossary."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "terms": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of English words or short phrases to look up.",
            },
        },
        "required": ["terms"],
    },
}


_INTAKE_FIELDS_TOOL = {
    "name": "submit_intake_fields",
    "description": "Submit the extracted typed fields from the questionnaire.",
    "input_schema": {
        "type": "object",
        "properties": {
            "dealership_name": {"type": ["string", "null"]},
            "new_dealership_name": {"type": ["string", "null"]},
            "dealership_address": {"type": ["string", "null"]},
            "leads_email": {"type": ["string", "null"]},
            "primary_url": {"type": ["string", "null"]},
            "new_primary_url": {"type": ["string", "null"]},
            "design_choice": {"type": ["string", "null"]},
        },
        "required": [
            "dealership_name",
            "new_dealership_name",
            "dealership_address",
            "leads_email",
            "primary_url",
            "new_primary_url",
            "design_choice",
        ],
    },
}


_INTAKE_FIELD_KEYS = (
    "dealership_name",
    "new_dealership_name",
    "dealership_address",
    "leads_email",
    "primary_url",
    "new_primary_url",
    "design_choice",
)


def _empty_intake_fields() -> dict:
    return {k: None for k in _INTAKE_FIELD_KEYS}


def _normalize_intake_payload(payload: dict) -> dict:
    """Coerce the raw tool payload into the contract shape: keys present,
    values either non-empty stripped string or None."""
    out: dict = {}
    for key in _INTAKE_FIELD_KEYS:
        raw = payload.get(key)
        if isinstance(raw, str):
            stripped = raw.strip()
            out[key] = stripped or None
        else:
            out[key] = None
    return out


_TRANSLATION_SUBMIT_TOOL = {
    "name": "submit_translation",
    "description": "Submit your final translation. Always use this as your last tool call.",
    "input_schema": {
        "type": "object",
        "properties": {
            "reasoning": {
                "type": "string",
                "description": "1-3 short sentences on translation choices. Concise.",
            },
            "translation": {
                "type": "string",
                "description": "The final es_US string. Preserves HTML, hrefs, brackets, entities exactly.",
            },
        },
        "required": ["reasoning", "translation"],
    },
}


_SEGMENT_TRANSLATIONS_TOOL = {
    "name": "submit_translations",
    "description": "Submit the Spanish translation for every input fragment, addressed by id.",
    "input_schema": {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "The fragment's input id."},
                        "es": {"type": "string", "description": "es_US translation of that fragment."},
                    },
                    "required": ["id", "es"],
                },
                "description": "One {id, es} entry per input id (any order).",
            },
        },
        "required": ["items"],
    },
}


def _segments_in_order(items: list, originals: list[str]) -> list[str]:
    """Match {id, es} items back to input order by id; fill any dropped id with
    the original English. Guarantees one entry per input. Empty when the model
    returned no usable items (signals a hard failure to the caller)."""
    by_id: dict[str, str] = {}
    for entry in items or []:
        if not isinstance(entry, dict):
            continue
        key = str(entry.get("id", ""))
        value = entry.get("es")
        if key and isinstance(value, str):
            by_id[key] = value
    if not by_id:
        return []
    return [by_id.get(str(i), originals[i]) for i in range(len(originals))]


_JUDGE_VERDICT_TOOL = {
    "name": "submit_verdict",
    "description": "Submit your evaluation of the candidate Spanish translation.",
    "input_schema": {
        "type": "object",
        "properties": {
            "ok": {
                "type": "boolean",
                "description": "True if naturalness AND meaning fidelity are both acceptable.",
            },
            "reason": {
                "type": "string",
                "description": "1-2 short sentences when ok=false; empty string when ok=true.",
            },
        },
        "required": ["ok", "reason"],
    },
}

from src.adapters.outbound.prompts import (
    build_chrome_batch_system_prompt,
    build_chrome_batch_user_message,
    build_enrich_system_prompt,
    build_enrich_user_message,
    build_image_split_system_prompt,
    build_image_split_user_message,
    build_intake_classifier_system_prompt,
    build_intake_classifier_user_message,
    build_intake_extractor_system_prompt,
    build_intake_extractor_user_message,
    build_judge_translation_system_prompt,
    build_judge_translation_user_message,
    build_label_translation_system_prompt,
    build_label_translation_system_prompt_v2,
    build_label_translation_user_message,
    build_nav_parser_system_prompt,
    build_nav_parser_user_message,
    build_segment_translation_system_prompt,
    build_segment_translation_user_message,
    build_staff_extraction_system_prompt,
    build_staff_extraction_user_message,
    build_standalone_clean_system_prompt,
    build_standalone_clean_user_message,
    build_system_prompt,
    build_user_message,
    build_widget_type_system_prompt,
    build_widget_type_user_message,
)
from src.domain.errors import LLMAuthError, LLMOutputParseError
from src.domain.models import DOMSkeleton, SectionPlan, TokenUsage
from src.domain.pricing import cost_usd

from ._parser import parse_section_plan

_PROVIDER = "anthropic"

_SECTION_PLAN_TOOL = {
    "name": "submit_section_plan",
    "description": "Submit the ordered DDC section plan with per-column widget assignments.",
    "input_schema": {
        "type": "object",
        "properties": {
            "sections": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "section_type": {"type": "string"},
                        "position": {"type": "integer"},
                        "intent": {"type": "string"},
                        "columns": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "widget_type": {
                                        "type": "string",
                                        "enum": ["content", "image"],
                                    },
                                    "html": {
                                        "type": "string",
                                        "description": "Bootstrap 4 HTML to inject into a content widget. Include heading, body copy, and any CTAs found in the original section. Omit for image widgets.",
                                    },
                                    "source_url": {
                                        "type": "string",
                                        "description": "Absolute URL of the primary image found in this column. Omit for content widgets.",
                                    },
                                },
                                "required": ["widget_type"],
                            },
                        },
                    },
                    "required": ["section_type", "position", "intent", "columns"],
                },
            }
        },
        "required": ["sections"],
    },
}


class AnthropicLLMAdapter:
    def __init__(self, api_key: str, model: str) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model
        self.usage_log: list[TokenUsage] = []

    def reset_usage(self) -> None:
        self.usage_log.clear()

    def _record(self, model: str, stage: str, response) -> None:
        try:
            input_tokens = int(response.usage.input_tokens)
            output_tokens = int(response.usage.output_tokens)
        except (AttributeError, TypeError, ValueError):
            return
        self.usage_log.append(TokenUsage(
            provider=_PROVIDER,
            model=model,
            stage=stage,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd(_PROVIDER, model, input_tokens, output_tokens),
        ))

    async def analyze(
        self,
        skeleton: DOMSkeleton,
        catalog: list[dict],
        rules: str,
    ) -> SectionPlan:
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            system=build_system_prompt(catalog, rules),
            tools=[_SECTION_PLAN_TOOL],
            tool_choice={"type": "tool", "name": "submit_section_plan"},
            messages=[{"role": "user", "content": build_user_message(skeleton)}],
        )
        self._record(self._model, "analyze", response)
        for block in response.content:
            if block.type == "tool_use" and block.name == "submit_section_plan":
                return parse_section_plan(block.input)
        raise LLMOutputParseError("No submit_section_plan tool call found in response")

    async def clean_html(self, raw_html: str, base_url: str) -> SectionPlan:
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=8192,
            system=build_standalone_clean_system_prompt(base_url),
            tools=[_SECTION_PLAN_TOOL],
            tool_choice={"type": "tool", "name": "submit_section_plan"},
            messages=[{"role": "user", "content": build_standalone_clean_user_message(raw_html)}],
        )
        self._record(self._model, "clean_html", response)
        for block in response.content:
            if block.type == "tool_use" and block.name == "submit_section_plan":
                return parse_section_plan(block.input)
        raise LLMOutputParseError("No submit_section_plan tool call found in response")

    async def enrich_content(self, sections: list[dict]) -> list[dict]:
        # Lighter model — Haiku is fast, cheap, and plenty capable for
        # HTML cleanup + one-sentence intent writing.
        _ENRICH_TOOL = {
            "name": "submit_enriched_content",
            "description": "Submit enriched HTML and intent strings for all sections.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "sections": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id":       {"type": "string"},
                                "intent":   {"type": "string"},
                                "snippets": {"type": "array", "items": {"type": "string"}},
                            },
                            "required": ["id", "intent", "snippets"],
                        },
                    }
                },
                "required": ["sections"],
            },
        }
        response = await self._client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=8192,
            system=build_enrich_system_prompt(),
            tools=[_ENRICH_TOOL],
            tool_choice={"type": "tool", "name": "submit_enriched_content"},
            messages=[{"role": "user", "content": build_enrich_user_message(sections)}],
        )
        self._record("claude-haiku-4-5", "enrich", response)
        for block in response.content:
            if block.type == "tool_use" and block.name == "submit_enriched_content":
                result = block.input.get("sections", [])
                if isinstance(result, list):
                    return result
        return []  # fallback: caller keeps originals

    async def classify_widget_type(self, items: list[dict]) -> list[dict]:
        if not items:
            return []
        _TOOL = {
            "name": "submit_widget_types",
            "description": "Classify each candidate widget into one of the five types.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "type": {
                                    "type": "string",
                                    "enum": ["form", "contact_info", "hours", "content", "drop"],
                                },
                            },
                            "required": ["id", "type"],
                        },
                    }
                },
                "required": ["items"],
            },
        }
        response = await self._client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1024,
            system=build_widget_type_system_prompt(),
            tools=[_TOOL],
            tool_choice={"type": "tool", "name": "submit_widget_types"},
            messages=[{"role": "user", "content": build_widget_type_user_message(items)}],
        )
        self._record("claude-haiku-4-5", "typify", response)
        for block in response.content:
            if block.type == "tool_use" and block.name == "submit_widget_types":
                return _widget_types_in_order(block.input.get("items", []), items)
        return _widget_types_in_order([], items)

    async def classify_image_splits(self, items: list[dict]) -> list[list[bool]]:
        if not items:
            return []
        _TOOL = {
            "name": "submit_image_splits",
            "description": "Submit promote/keep verdicts per <img> for each content widget.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "splits": {
                                    "type": "array",
                                    "items": {"type": "boolean"},
                                },
                            },
                            "required": ["id", "splits"],
                        },
                    }
                },
                "required": ["items"],
            },
        }
        response = await self._client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=2048,
            system=build_image_split_system_prompt(),
            tools=[_TOOL],
            tool_choice={"type": "tool", "name": "submit_image_splits"},
            messages=[{"role": "user", "content": build_image_split_user_message(items)}],
        )
        self._record("claude-haiku-4-5", "image_split", response)
        for block in response.content:
            if block.type == "tool_use" and block.name == "submit_image_splits":
                return _image_splits_in_order(block.input.get("items", []), items)
        return _image_splits_in_order([], items)

    async def classify_chrome_batch(self, snippets: list[str]) -> list[str]:
        if not snippets:
            return []
        _BATCH_TOOL = {
            "name": "submit_chrome_verdicts",
            "description": "Submit KEEP/DROP verdicts for all candidates.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "verdicts": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "verdict": {"type": "string", "enum": ["KEEP", "DROP"]},
                            },
                            "required": ["id", "verdict"],
                        },
                    }
                },
                "required": ["verdicts"],
            },
        }
        response = await self._client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=512,
            system=build_chrome_batch_system_prompt(),
            tools=[_BATCH_TOOL],
            tool_choice={"type": "tool", "name": "submit_chrome_verdicts"},
            messages=[{"role": "user", "content": build_chrome_batch_user_message(snippets)}],
        )
        self._record("claude-haiku-4-5", "chrome_review", response)
        for block in response.content:
            if block.type == "tool_use" and block.name == "submit_chrome_verdicts":
                return _verdicts_in_order(block.input.get("verdicts", []), len(snippets))
        return ["KEEP"] * len(snippets)

    async def extract_staff(self, html: str, base_url: str) -> list[dict]:
        _TOOL = {
            "name": "submit_staff",
            "description": "Submit the parsed list of staff members from the source HTML.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "staff": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "department":         {"type": "string"},
                                "name":               {"type": "string"},
                                "title":              {"type": ["string", "null"]},
                                "phone":              {"type": ["string", "null"]},
                                "email":              {"type": ["string", "null"]},
                                "bio":                {"type": ["string", "null"]},
                                "has_photo":          {"type": "boolean"},
                                "original_photo_url": {"type": ["string", "null"]},
                            },
                            "required": ["department", "name", "has_photo"],
                        },
                    }
                },
                "required": ["staff"],
            },
        }
        response = await self._client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=16000,
            system=build_staff_extraction_system_prompt(),
            tools=[_TOOL],
            tool_choice={"type": "tool", "name": "submit_staff"},
            messages=[{"role": "user", "content": build_staff_extraction_user_message(html, base_url)}],
        )
        self._record("claude-haiku-4-5", "extract_staff", response)
        for block in response.content:
            if block.type == "tool_use" and block.name == "submit_staff":
                staff = block.input.get("staff", [])
                if isinstance(staff, list):
                    return [s for s in staff if isinstance(s, dict)]
        return []

    async def parse_nav(self, html: str, base_url: str) -> list[dict]:
        _TOOL = {
            "name": "submit_nav_pages",
            "description": "Submit the deduplicated list of navigation pages with title, URL, and category.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "pages": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "url":   {"type": "string"},
                                "category": {
                                    "type": "string",
                                    "enum": ["general", "model_specific"],
                                },
                            },
                            "required": ["title", "url", "category"],
                        },
                    }
                },
                "required": ["pages"],
            },
        }
        response = await self._client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=8192,
            system=build_nav_parser_system_prompt(),
            tools=[_TOOL],
            tool_choice={"type": "tool", "name": "submit_nav_pages"},
            messages=[{"role": "user", "content": build_nav_parser_user_message(html, base_url)}],
        )
        self._record("claude-haiku-4-5", "parse_nav", response)
        for block in response.content:
            if block.type == "tool_use" and block.name == "submit_nav_pages":
                pages = block.input.get("pages", [])
                if isinstance(pages, list):
                    return [p for p in pages if isinstance(p, dict)]
        return []

    async def classify_intake(self, rows: dict[str, str]) -> str:
        response = await self._client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=512,
            system=build_intake_classifier_system_prompt(),
            messages=[{"role": "user", "content": build_intake_classifier_user_message(rows)}],
        )
        self._record("claude-haiku-4-5", "classify_intake", response)
        # Concatenate any text blocks. Anthropic returns content as a list of blocks;
        # for a non-tool plain-completion the first block is text.
        parts: list[str] = []
        for block in response.content:
            if getattr(block, "type", None) == "text":
                parts.append(block.text)
        return "".join(parts)

    async def extract_intake_fields(
        self,
        rows: dict[str, str],
        classification: str,
    ) -> dict:
        model = "claude-haiku-4-5"
        try:
            response = await self._client.messages.create(
                model=model,
                max_tokens=1024,
                system=build_intake_extractor_system_prompt(classification),
                tools=[_INTAKE_FIELDS_TOOL],
                tool_choice={"type": "tool", "name": "submit_intake_fields"},
                messages=[{
                    "role": "user",
                    "content": build_intake_extractor_user_message(rows),
                }],
            )
            self._record(model, "extract_intake_fields", response)
        except Exception:
            return _empty_intake_fields()

        for block in response.content:
            if getattr(block, "type", None) == "tool_use" and block.name == "submit_intake_fields":
                payload = block.input or {}
                return _normalize_intake_payload(payload)
        return _empty_intake_fields()

    async def translate_label(
        self,
        en_html: str,
        dealer_name: str,
        glossary_table: str,
    ) -> str:
        response = await self._client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=4096,
            system=build_label_translation_system_prompt(dealer_name, glossary_table),
            messages=[{"role": "user", "content": build_label_translation_user_message(en_html)}],
        )
        self._record("claude-haiku-4-5", "translate_label", response)
        parts: list[str] = []
        for block in response.content:
            if getattr(block, "type", None) == "text":
                parts.append(block.text)
        return "".join(parts).strip()

    async def translate_label_with_tools(
        self,
        en_html: str,
        dealer_name: str,
        glossary_lookup: Callable[[list[str]], dict[str, str | None]],
        extra_hint: str = "",
    ) -> dict:
        model = "claude-haiku-4-5"
        system = build_label_translation_system_prompt_v2(dealer_name)
        messages: list[dict] = [{
            "role": "user",
            "content": build_label_translation_user_message(en_html, extra_hint),
        }]

        fallback_text = ""
        for _ in range(_TOOL_LOOP_CAP):
            response = await self._client.messages.create(
                model=model,
                max_tokens=16000,
                system=system,
                tools=[_GLOSSARY_LOOKUP_TOOL, _TRANSLATION_SUBMIT_TOOL],
                messages=messages,
            )

            text_parts: list[str] = []
            tool_uses: list = []
            for block in response.content:
                btype = getattr(block, "type", None)
                if btype == "text":
                    text_parts.append(block.text)
                elif btype == "tool_use":
                    tool_uses.append(block)

            if text_parts:
                fallback_text = "".join(text_parts).strip()

            # Check for the structured final answer first.
            for tu in tool_uses:
                if tu.name == "submit_translation":
                    payload = tu.input or {}
                    return {
                        "translation": str(payload.get("translation", "")).strip(),
                        "reasoning": str(payload.get("reasoning", "")).strip(),
                    }

            # No tool calls and no submit → degenerate "plain text" answer.
            if not tool_uses:
                return {"translation": fallback_text, "reasoning": ""}

            # Echo assistant turn (text + tool_use blocks) and append tool_results.
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for tu in tool_uses:
                if tu.name == "glossary_lookup":
                    terms = (tu.input or {}).get("terms", []) or []
                    if not isinstance(terms, list):
                        terms = []
                    result = glossary_lookup(terms)
                    payload = {k: (v if v is not None else None) for k, v in result.items()}
                else:
                    payload = {"error": f"unknown tool: {tu.name}"}
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tu.id,
                    "content": _json_dumps(payload),
                })
            messages.append({"role": "user", "content": tool_results})

        # Hit the cap — return whatever text we last captured, no reasoning.
        return {"translation": fallback_text, "reasoning": ""}

    async def translate_text_segments(
        self,
        segments: list[str],
        dealer_name: str,
    ) -> list[str]:
        if not segments:
            return []
        model = "claude-haiku-4-5"
        try:
            response = await self._client.messages.create(
                model=model,
                max_tokens=8192,
                system=build_segment_translation_system_prompt(dealer_name),
                tools=[_SEGMENT_TRANSLATIONS_TOOL],
                tool_choice={"type": "tool", "name": "submit_translations"},
                messages=[{
                    "role": "user",
                    "content": build_segment_translation_user_message(segments),
                }],
            )
            self._record(model, "translate_text_segments", response)
        except Exception:
            return []

        for block in response.content:
            if getattr(block, "type", None) == "tool_use" and block.name == "submit_translations":
                return _segments_in_order((block.input or {}).get("items", []), segments)
        return []

    async def judge_translation(
        self,
        en_html: str,
        es_html: str,
        dealer_name: str,
    ) -> dict:
        model = "claude-haiku-4-5"
        try:
            response = await self._client.messages.create(
                model=model,
                max_tokens=512,
                system=build_judge_translation_system_prompt(dealer_name),
                tools=[_JUDGE_VERDICT_TOOL],
                tool_choice={"type": "tool", "name": "submit_verdict"},
                messages=[{
                    "role": "user",
                    "content": build_judge_translation_user_message(en_html, es_html),
                }],
            )
            self._record(model, "judge_translation", response)
        except Exception:
            return {"ok": True, "reason": ""}

        for block in response.content:
            if getattr(block, "type", None) == "tool_use" and block.name == "submit_verdict":
                payload = block.input or {}
                return {
                    "ok": bool(payload.get("ok", True)),
                    "reason": str(payload.get("reason", "")),
                }
        # Fall-through: if no tool_use block came back, treat as pass.
        return {"ok": True, "reason": ""}

    async def validate(self) -> bool:
        try:
            await self._client.messages.create(
                model=self._model,
                max_tokens=1,
                messages=[{"role": "user", "content": "hi"}],
            )
            return True
        except anthropic.AuthenticationError:
            raise LLMAuthError("Anthropic API key is invalid")


def _verdicts_in_order(items: list, expected_len: int) -> list[str]:
    """Map [{id, verdict}, ...] back into positional order. Missing ids default
    to KEEP — over-including is safer than over-dropping."""
    by_id: dict[str, str] = {}
    for it in items or []:
        if isinstance(it, dict):
            iid = str(it.get("id", ""))
            v = str(it.get("verdict", "")).upper()
            if iid and v in ("KEEP", "DROP"):
                by_id[iid] = v
    return [by_id.get(str(i), "KEEP") for i in range(expected_len)]


_WIDGET_TYPES = {"form", "contact_info", "hours", "content", "drop"}


def _widget_types_in_order(items: list, inputs: list[dict]) -> list[dict]:
    """Map [{id, type}, ...] back to positional order. Missing or invalid
    entries default to 'content' — safe fallback (no widget change)."""
    by_id: dict[str, str] = {}
    for it in items or []:
        if not isinstance(it, dict):
            continue
        iid = str(it.get("id", ""))
        t = str(it.get("type", "")).lower()
        if iid and t in _WIDGET_TYPES:
            by_id[iid] = t
    return [
        {"id": str(i), "type": by_id.get(str(i), "content")}
        for i, _ in enumerate(inputs)
    ]


def _image_splits_in_order(items: list, inputs: list[dict]) -> list[list[bool]]:
    """Map [{id, splits}, ...] back to positional order. Missing or malformed
    entries default to all-False (no splits) for that item — preserves current
    widget structure on any parse failure."""
    import re as _re
    img_re = _re.compile(r"<img\b[^>]*>", _re.IGNORECASE)

    by_id: dict[str, list[bool]] = {}
    for it in items or []:
        if not isinstance(it, dict):
            continue
        iid = str(it.get("id", ""))
        raw = it.get("splits", [])
        if iid and isinstance(raw, list):
            by_id[iid] = [bool(x) for x in raw]

    out: list[list[bool]] = []
    for i, inp in enumerate(inputs):
        n_imgs = len(img_re.findall(inp.get("html", "")))
        verdicts = by_id.get(str(i), [])
        # Pad with False if LLM returned too few; truncate if too many.
        if len(verdicts) < n_imgs:
            verdicts = verdicts + [False] * (n_imgs - len(verdicts))
        else:
            verdicts = verdicts[:n_imgs]
        out.append(verdicts)
    return out
