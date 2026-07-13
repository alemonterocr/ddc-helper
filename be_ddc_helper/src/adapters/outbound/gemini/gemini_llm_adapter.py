import json
from typing import Callable

from google import genai
from google.genai import types

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
    build_segment_translation_system_prompt,
    build_segment_translation_user_message,
    build_judge_translation_user_message,
    build_label_translation_system_prompt,
    build_label_translation_system_prompt_v2,
    build_label_translation_user_message,
    build_nav_parser_system_prompt,
    build_nav_parser_user_message,
    build_staff_extraction_system_prompt,
    build_staff_extraction_user_message,
    build_standalone_clean_system_prompt,
    build_standalone_clean_user_message,
    build_system_prompt,
    build_user_message,
    build_widget_type_system_prompt,
    build_widget_type_user_message,
)
from src.domain.errors import LLMAuthError
from src.domain.models import DOMSkeleton, SectionPlan, TokenUsage
from src.domain.pricing import cost_usd

from ._parser import parse_section_plan

_PROVIDER = "gemini"


def _segments_in_order(items: list, originals: list[str]) -> list[str]:
    """Match {id, es} items back to input order by id; fill any dropped id with
    the original English. Empty when no usable items (signals a hard failure)."""
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

_TOOL_LOOP_CAP = 5

_GEMINI_GLOSSARY_TOOL = {
    "name": "glossary_lookup",
    "description": (
        "Look up authoritative Mexican Spanish translations for specific "
        "English terms used in dealership/automotive vocabulary. Returns a "
        "dict mapping each queried term to its MX-Spanish, or null if not "
        "in the glossary."
    ),
    "parameters": {
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

_GEMINI_INTAKE_FIELDS_SCHEMA = {
    "type": "object",
    "properties": {
        "dealership_name": {"type": "string", "nullable": True},
        "new_dealership_name": {"type": "string", "nullable": True},
        "dealership_address": {"type": "string", "nullable": True},
        "leads_email": {"type": "string", "nullable": True},
        "primary_url": {"type": "string", "nullable": True},
        "new_primary_url": {"type": "string", "nullable": True},
        "design_choice": {"type": "string", "nullable": True},
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


def _empty_intake_fields_gemini() -> dict:
    return {k: None for k in _INTAKE_FIELD_KEYS}


def _normalize_intake_payload_gemini(payload: dict) -> dict:
    out: dict = {}
    for key in _INTAKE_FIELD_KEYS:
        raw = payload.get(key)
        if isinstance(raw, str):
            stripped = raw.strip()
            out[key] = stripped or None
        else:
            out[key] = None
    return out


_GEMINI_TRANSLATION_SUBMIT_TOOL = {
    "name": "submit_translation",
    "description": "Submit your final translation. Always use this as your last tool call.",
    "parameters": {
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


class GeminiLLMAdapter:
    def __init__(self, api_key: str, model: str) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self.usage_log: list[TokenUsage] = []

    def reset_usage(self) -> None:
        self.usage_log.clear()

    def _record(self, model: str, stage: str, response) -> None:
        # Gemini reports usage via response.usage_metadata.
        meta = getattr(response, "usage_metadata", None)
        if meta is None:
            return
        try:
            input_tokens = int(getattr(meta, "prompt_token_count", 0) or 0)
            output_tokens = int(getattr(meta, "candidates_token_count", 0) or 0)
        except (TypeError, ValueError):
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
        system_prompt = build_system_prompt(catalog, rules)
        user_message = build_user_message(skeleton)

        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=f"{system_prompt}\n\n{user_message}",
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
        self._record(self._model, "analyze", response)
        return parse_section_plan(response.text)

    async def clean_html(self, raw_html: str, base_url: str) -> SectionPlan:
        system_prompt = build_standalone_clean_system_prompt(base_url)
        user_message = build_standalone_clean_user_message(raw_html)
        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=f"{system_prompt}\n\n{user_message}",
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
        self._record(self._model, "clean_html", response)
        return parse_section_plan(response.text)

    async def enrich_content(self, sections: list[dict]) -> list[dict]:
        import json as _json
        # gemini-2.0-flash is already the light tier — fast and cheap.
        prompt = build_enrich_system_prompt() + "\n\n" + build_enrich_user_message(sections)
        response = await self._client.aio.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
        self._record("gemini-2.0-flash", "enrich", response)
        try:
            data = _json.loads(response.text)
            result = data.get("sections", [])
            if isinstance(result, list):
                return result
        except Exception:
            pass
        return []  # fallback: caller keeps originals

    async def classify_widget_type(self, items: list[dict]) -> list[dict]:
        if not items:
            return []
        import json as _json
        prompt = (
            build_widget_type_system_prompt()
            + "\n\n"
            + build_widget_type_user_message(items)
        )
        response = await self._client.aio.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
        self._record("gemini-2.0-flash", "typify", response)
        try:
            data = _json.loads(response.text or "{}")
            llm_items = data.get("items", [])
            if isinstance(llm_items, list):
                return _widget_types_in_order(llm_items, items)
        except Exception:
            pass
        return _widget_types_in_order([], items)

    async def classify_image_splits(self, items: list[dict]) -> list[list[bool]]:
        if not items:
            return []
        import json as _json
        prompt = (
            build_image_split_system_prompt()
            + "\n\n"
            + build_image_split_user_message(items)
        )
        response = await self._client.aio.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
        self._record("gemini-2.0-flash", "image_split", response)
        try:
            data = _json.loads(response.text or "{}")
            llm_items = data.get("items", [])
            if isinstance(llm_items, list):
                return _image_splits_in_order(llm_items, items)
        except Exception:
            pass
        return _image_splits_in_order([], items)

    async def classify_chrome_batch(self, snippets: list[str]) -> list[str]:
        if not snippets:
            return []
        import json as _json
        prompt = (
            build_chrome_batch_system_prompt()
            + "\n\n"
            + build_chrome_batch_user_message(snippets)
        )
        response = await self._client.aio.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
        self._record("gemini-2.0-flash", "chrome_review", response)
        try:
            data = _json.loads(response.text or "{}")
            items = data.get("verdicts", [])
            if isinstance(items, list):
                return _verdicts_in_order(items, len(snippets))
        except Exception:
            pass
        return ["KEEP"] * len(snippets)

    async def extract_staff(self, html: str, base_url: str) -> list[dict]:
        import json as _json
        prompt = (
            build_staff_extraction_system_prompt()
            + "\n\n"
            + build_staff_extraction_user_message(html, base_url)
        )
        response = await self._client.aio.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
        self._record("gemini-2.0-flash", "extract_staff", response)
        try:
            data = _json.loads(response.text)
            staff = data.get("staff", [])
            if isinstance(staff, list):
                return [s for s in staff if isinstance(s, dict)]
        except Exception:
            pass
        return []

    async def parse_nav(self, html: str, base_url: str) -> list[dict]:
        import json as _json
        prompt = (
            build_nav_parser_system_prompt()
            + "\n\n"
            + build_nav_parser_user_message(html, base_url)
        )
        response = await self._client.aio.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
        self._record("gemini-2.0-flash", "parse_nav", response)
        try:
            data = _json.loads(response.text)
            pages = data.get("pages", [])
            if isinstance(pages, list):
                return [p for p in pages if isinstance(p, dict)]
        except Exception:
            pass
        return []

    async def translate_label(
        self,
        en_html: str,
        dealer_name: str,
        glossary_table: str,
    ) -> str:
        prompt = (
            build_label_translation_system_prompt(dealer_name, glossary_table)
            + "\n\n"
            + build_label_translation_user_message(en_html)
        )
        response = await self._client.aio.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )
        self._record("gemini-2.0-flash", "translate_label", response)
        return (response.text or "").strip()

    async def translate_label_with_tools(
        self,
        en_html: str,
        dealer_name: str,
        glossary_lookup: Callable[[list[str]], dict[str, str | None]],
        extra_hint: str = "",
    ) -> dict:
        model = "gemini-2.0-flash"
        system_prompt = build_label_translation_system_prompt_v2(dealer_name)
        user_msg = build_label_translation_user_message(en_html, extra_hint)

        tool = types.Tool(function_declarations=[
            _GEMINI_GLOSSARY_TOOL,
            _GEMINI_TRANSLATION_SUBMIT_TOOL,
        ])
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            tools=[tool],
            max_output_tokens=16000,
        )

        contents: list = [
            types.Content(role="user", parts=[types.Part.from_text(text=user_msg)])
        ]

        fallback_text = ""
        for _ in range(_TOOL_LOOP_CAP):
            response = await self._client.aio.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )
            self._record(model, "translate_label_with_tools", response)

            text_parts: list[str] = []
            function_calls: list = []
            candidate = response.candidates[0] if response.candidates else None
            parts = candidate.content.parts if (candidate and candidate.content and candidate.content.parts) else []

            for part in parts:
                if getattr(part, "function_call", None):
                    function_calls.append(part.function_call)
                elif getattr(part, "text", None):
                    text_parts.append(part.text)

            if text_parts:
                fallback_text = "".join(text_parts).strip()

            # Check for the structured final answer first.
            for fc in function_calls:
                if fc.name == "submit_translation":
                    args = fc.args or {}
                    return {
                        "translation": str(args.get("translation", "")).strip(),
                        "reasoning": str(args.get("reasoning", "")).strip(),
                    }

            if not function_calls:
                return {"translation": fallback_text, "reasoning": ""}

            contents.append(types.Content(role="model", parts=parts))
            response_parts = []
            for fc in function_calls:
                if fc.name == "glossary_lookup":
                    terms = (fc.args or {}).get("terms", []) or []
                    if not isinstance(terms, list):
                        terms = []
                    result = glossary_lookup(terms)
                    payload = {k: v for k, v in result.items()}
                else:
                    payload = {"error": f"unknown tool: {fc.name}"}
                response_parts.append(types.Part.from_function_response(
                    name=fc.name, response=payload,
                ))
            contents.append(types.Content(role="user", parts=response_parts))

        return {"translation": fallback_text, "reasoning": ""}

    async def translate_text_segments(
        self,
        segments: list[str],
        dealer_name: str,
    ) -> list[str]:
        if not segments:
            return []
        model = "gemini-2.0-flash"
        system_prompt = build_segment_translation_system_prompt(dealer_name)
        user_msg = build_segment_translation_user_message(segments)
        try:
            response = await self._client.aio.models.generate_content(
                model=model,
                contents=f"{system_prompt}\n\n{user_msg}",
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema={
                        "type": "object",
                        "properties": {
                            "items": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "id": {"type": "string"},
                                        "es": {"type": "string"},
                                    },
                                    "required": ["id", "es"],
                                },
                            },
                        },
                        "required": ["items"],
                    },
                ),
            )
            self._record(model, "translate_text_segments", response)
            payload = json.loads(response.text or "{}")
            return _segments_in_order(payload.get("items", []), segments)
        except Exception:
            return []

    async def judge_translation(
        self,
        en_html: str,
        es_html: str,
        dealer_name: str,
    ) -> dict:
        model = "gemini-2.0-flash"
        system_prompt = build_judge_translation_system_prompt(dealer_name)
        user_msg = build_judge_translation_user_message(en_html, es_html)
        try:
            response = await self._client.aio.models.generate_content(
                model=model,
                contents=f"{system_prompt}\n\n{user_msg}",
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema={
                        "type": "object",
                        "properties": {
                            "ok": {"type": "boolean"},
                            "reason": {"type": "string"},
                        },
                        "required": ["ok", "reason"],
                    },
                ),
            )
            self._record(model, "judge_translation", response)
            payload = json.loads(response.text or "{}")
            return {
                "ok": bool(payload.get("ok", True)),
                "reason": str(payload.get("reason", "")),
            }
        except Exception:
            return {"ok": True, "reason": ""}

    async def classify_intake(self, rows: dict[str, str]) -> str:
        prompt = (
            build_intake_classifier_system_prompt()
            + "\n\n"
            + build_intake_classifier_user_message(rows)
        )
        response = await self._client.aio.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
        self._record("gemini-2.0-flash", "classify_intake", response)
        return response.text or ""

    async def extract_intake_fields(
        self,
        rows: dict[str, str],
        classification: str,
    ) -> dict:
        model = "gemini-2.0-flash"
        prompt = (
            build_intake_extractor_system_prompt(classification)
            + "\n\n"
            + build_intake_extractor_user_message(rows)
        )
        try:
            response = await self._client.aio.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=_GEMINI_INTAKE_FIELDS_SCHEMA,
                ),
            )
            self._record(model, "extract_intake_fields", response)
            payload = json.loads(response.text or "{}")
            return _normalize_intake_payload_gemini(payload)
        except Exception:
            return _empty_intake_fields_gemini()

    async def validate(self) -> bool:
        try:
            await self._client.aio.models.generate_content(
                model=self._model,
                contents="hi",
            )
            return True
        except Exception as error:
            if _is_quota_error(error):
                return True
            if _is_auth_error(error):
                raise LLMAuthError(f"Gemini API key is invalid: {error}")
            raise


_WIDGET_TYPES = {"form", "contact_info", "hours", "content", "drop"}


def _widget_types_in_order(items: list, inputs: list[dict]) -> list[dict]:
    """Map [{id, type}, ...] back to positional order. Invalid/missing → 'content'."""
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
    """Map [{id, splits}, ...] back to positional order, sized to each item's
    actual <img> count. Missing/malformed entries default to all-False."""
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
        v = by_id.get(str(i), [])
        if len(v) < n_imgs:
            v = v + [False] * (n_imgs - len(v))
        else:
            v = v[:n_imgs]
        out.append(v)
    return out


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


def _is_quota_error(error: Exception) -> bool:
    message = str(error).lower()
    return "429" in message or "resource_exhausted" in message or "quota" in message


def _is_auth_error(error: Exception) -> bool:
    message = str(error).lower()
    return any(
        kw in message
        for kw in ("api key", "api_key_invalid", "permission", "unauthenticated", "401", "403")
    )
