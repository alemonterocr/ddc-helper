import json
from typing import Callable

from openai import APIError, AsyncOpenAI, AuthenticationError

from src.adapters.outbound.gemini._parser import parse_section_plan
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

_DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
_PROVIDER = "deepseek"

_TOOL_LOOP_CAP = 5

_DEEPSEEK_GLOSSARY_TOOL = {
    "type": "function",
    "function": {
        "name": "glossary_lookup",
        "description": (
            "Look up authoritative Mexican Spanish translations for specific "
            "English terms used in dealership/automotive vocabulary. Returns "
            "a dict mapping each queried term to its MX-Spanish, or null if "
            "not in the glossary."
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


def _empty_intake_fields_deepseek() -> dict:
    return {k: None for k in _INTAKE_FIELD_KEYS}


def _normalize_intake_payload_deepseek(payload: dict) -> dict:
    out: dict = {}
    for key in _INTAKE_FIELD_KEYS:
        raw = payload.get(key)
        if isinstance(raw, str):
            stripped = raw.strip()
            out[key] = stripped or None
        else:
            out[key] = None
    return out


_DEEPSEEK_TRANSLATION_SUBMIT_TOOL = {
    "type": "function",
    "function": {
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
    },
}


class DeepSeekLLMAdapter:
    def __init__(self, api_key: str, model: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key, base_url=_DEEPSEEK_BASE_URL)
        self._model = model
        self.usage_log: list[TokenUsage] = []

    def reset_usage(self) -> None:
        """Clear the usage log — call at the start of each analyze request."""
        self.usage_log.clear()

    def _record(self, model: str, stage: str, response) -> None:
        """Capture token usage from a completion response."""
        try:
            input_tokens = int(response.usage.prompt_tokens)
            output_tokens = int(response.usage.completion_tokens)
        except (AttributeError, TypeError, ValueError):
            return  # usage unavailable; skip silently
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
        response = await self._client.chat.completions.create(
            model=self._model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": build_system_prompt(catalog, rules)},
                {"role": "user", "content": build_user_message(skeleton)},
            ],
        )
        self._record(self._model, "analyze", response)
        text = response.choices[0].message.content or ""
        return parse_section_plan(text)

    async def clean_html(self, raw_html: str, base_url: str) -> SectionPlan:
        response = await self._client.chat.completions.create(
            model=self._model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": build_standalone_clean_system_prompt(base_url)},
                {"role": "user", "content": build_standalone_clean_user_message(raw_html)},
            ],
        )
        self._record(self._model, "clean_html", response)
        text = response.choices[0].message.content or ""
        return parse_section_plan(text)

    async def enrich_content(self, sections: list[dict]) -> list[dict]:
        # deepseek-chat = DeepSeek V3 standard model — fast, cheap, more than
        # capable enough for HTML enrichment + one-sentence intent writing.
        response = await self._client.chat.completions.create(
            model="deepseek-chat",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": build_enrich_system_prompt()},
                {"role": "user", "content": build_enrich_user_message(sections)},
            ],
        )
        self._record("deepseek-chat", "enrich", response)
        text = response.choices[0].message.content or ""
        try:
            data = json.loads(text)
            result = data.get("sections", [])
            if isinstance(result, list):
                return result
        except Exception:
            pass
        return []  # fallback: caller keeps originals

    async def classify_widget_type(self, items: list[dict]) -> list[dict]:
        if not items:
            return []
        response = await self._client.chat.completions.create(
            model="deepseek-chat",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": build_widget_type_system_prompt()},
                {"role": "user", "content": build_widget_type_user_message(items)},
            ],
        )
        self._record("deepseek-chat", "typify", response)
        text = response.choices[0].message.content or "{}"
        try:
            data = json.loads(text)
            llm_items = data.get("items", [])
            if isinstance(llm_items, list):
                return _widget_types_in_order(llm_items, items)
        except Exception:
            pass
        return _widget_types_in_order([], items)

    async def classify_image_splits(self, items: list[dict]) -> list[list[bool]]:
        if not items:
            return []
        response = await self._client.chat.completions.create(
            model="deepseek-chat",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": build_image_split_system_prompt()},
                {"role": "user", "content": build_image_split_user_message(items)},
            ],
        )
        self._record("deepseek-chat", "image_split", response)
        text = response.choices[0].message.content or "{}"
        try:
            data = json.loads(text)
            llm_items = data.get("items", [])
            if isinstance(llm_items, list):
                return _image_splits_in_order(llm_items, items)
        except Exception:
            pass
        return _image_splits_in_order([], items)

    async def classify_chrome_batch(self, snippets: list[str]) -> list[str]:
        if not snippets:
            return []
        response = await self._client.chat.completions.create(
            model="deepseek-chat",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": build_chrome_batch_system_prompt()},
                {"role": "user", "content": build_chrome_batch_user_message(snippets)},
            ],
        )
        self._record("deepseek-chat", "chrome_review", response)
        text = response.choices[0].message.content or "{}"
        try:
            data = json.loads(text)
            items = data.get("verdicts", [])
            if isinstance(items, list):
                return _verdicts_in_order(items, len(snippets))
        except Exception:
            pass
        return ["KEEP"] * len(snippets)

    async def extract_staff(self, html: str, base_url: str) -> list[dict]:
        response = await self._client.chat.completions.create(
            model="deepseek-chat",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": build_staff_extraction_system_prompt()},
                {"role": "user", "content": build_staff_extraction_user_message(html, base_url)},
            ],
        )
        self._record("deepseek-chat", "extract_staff", response)
        text = response.choices[0].message.content or ""
        try:
            data = json.loads(text)
            staff = data.get("staff", [])
            if isinstance(staff, list):
                return [s for s in staff if isinstance(s, dict)]
        except Exception:
            pass
        return []

    async def parse_nav(self, html: str, base_url: str) -> list[dict]:
        response = await self._client.chat.completions.create(
            model="deepseek-chat",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": build_nav_parser_system_prompt()},
                {"role": "user", "content": build_nav_parser_user_message(html, base_url)},
            ],
        )
        self._record("deepseek-chat", "parse_nav", response)
        text = response.choices[0].message.content or ""
        try:
            data = json.loads(text)
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
        response = await self._client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "system",
                    "content": build_label_translation_system_prompt(
                        dealer_name, glossary_table
                    ),
                },
                {
                    "role": "user",
                    "content": build_label_translation_user_message(en_html),
                },
            ],
        )
        self._record("deepseek-chat", "translate_label", response)
        return (response.choices[0].message.content or "").strip()

    async def translate_label_with_tools(
        self,
        en_html: str,
        dealer_name: str,
        glossary_lookup: Callable[[list[str]], dict[str, str | None]],
        extra_hint: str = "",
    ) -> dict:
        model = "deepseek-chat"
        messages: list[dict] = [
            {"role": "system", "content": build_label_translation_system_prompt_v2(dealer_name)},
            {"role": "user", "content": build_label_translation_user_message(en_html, extra_hint)},
        ]

        fallback_text = ""
        for _ in range(_TOOL_LOOP_CAP):
            response = await self._client.chat.completions.create(
                model=model,
                messages=messages,
                tools=[_DEEPSEEK_GLOSSARY_TOOL, _DEEPSEEK_TRANSLATION_SUBMIT_TOOL],
            )
            self._record(model, "translate_label_with_tools", response)

            choice = response.choices[0]
            msg = choice.message
            text = (msg.content or "").strip()
            tool_calls = msg.tool_calls or []

            if text:
                fallback_text = text

            # Check for the structured final answer first.
            for tc in tool_calls:
                if tc.function.name == "submit_translation":
                    try:
                        args = json.loads(tc.function.arguments or "{}")
                    except Exception:
                        args = {}
                    return {
                        "translation": str(args.get("translation", "")).strip(),
                        "reasoning": str(args.get("reasoning", "")).strip(),
                    }

            if not tool_calls:
                return {"translation": fallback_text, "reasoning": ""}

            messages.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in tool_calls
                ],
            })
            for tc in tool_calls:
                if tc.function.name == "glossary_lookup":
                    try:
                        args = json.loads(tc.function.arguments or "{}")
                    except Exception:
                        args = {}
                    terms = args.get("terms", []) or []
                    if not isinstance(terms, list):
                        terms = []
                    result = glossary_lookup(terms)
                    payload = result
                else:
                    payload = {"error": f"unknown tool: {tc.function.name}"}
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(payload, ensure_ascii=False),
                })

        return {"translation": fallback_text, "reasoning": ""}

    async def judge_translation(
        self,
        en_html: str,
        es_html: str,
        dealer_name: str,
    ) -> dict:
        model = "deepseek-chat"
        try:
            response = await self._client.chat.completions.create(
                model=model,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": (
                            build_judge_translation_system_prompt(dealer_name)
                            + "\n\nOUTPUT FORMAT: JSON object with keys "
                              "`ok` (boolean) and `reason` (string)."
                        ),
                    },
                    {
                        "role": "user",
                        "content": build_judge_translation_user_message(en_html, es_html),
                    },
                ],
            )
            self._record(model, "judge_translation", response)
            payload = json.loads(response.choices[0].message.content or "{}")
            return {
                "ok": bool(payload.get("ok", True)),
                "reason": str(payload.get("reason", "")),
            }
        except Exception:
            return {"ok": True, "reason": ""}

    async def classify_intake(self, rows: dict[str, str]) -> str:
        response = await self._client.chat.completions.create(
            model="deepseek-chat",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": build_intake_classifier_system_prompt()},
                {"role": "user", "content": build_intake_classifier_user_message(rows)},
            ],
        )
        self._record("deepseek-chat", "classify_intake", response)
        return response.choices[0].message.content or ""

    async def extract_intake_fields(
        self,
        rows: dict[str, str],
        classification: str,
    ) -> dict:
        model = "deepseek-chat"
        try:
            response = await self._client.chat.completions.create(
                model=model,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": (
                            build_intake_extractor_system_prompt(classification)
                            + "\n\nOUTPUT FORMAT: JSON object with EXACTLY these keys "
                              "(use null for missing): dealership_name, new_dealership_name, "
                              "dealership_address, leads_email, primary_url, new_primary_url, "
                              "design_choice."
                        ),
                    },
                    {
                        "role": "user",
                        "content": build_intake_extractor_user_message(rows),
                    },
                ],
            )
            self._record(model, "extract_intake_fields", response)
            payload = json.loads(response.choices[0].message.content or "{}")
            return _normalize_intake_payload_deepseek(payload)
        except Exception:
            return _empty_intake_fields_deepseek()

    async def validate(self) -> bool:
        try:
            await self._client.chat.completions.create(
                model=self._model,
                max_tokens=1,
                messages=[{"role": "user", "content": "hi"}],
            )
            return True
        except AuthenticationError as e:
            raise LLMAuthError("DeepSeek API key is invalid") from e
        except APIError as e:
            raise LLMAuthError(f"DeepSeek API error: {e.message}") from e


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
