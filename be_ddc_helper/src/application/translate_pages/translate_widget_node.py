"""Translate-widget node — the per-widget fan-out branch.

Each Send branch translates one widget's HTML by translating only its text nodes
(see `html_translate`): markup is preserved by construction, so there is nothing
for the LLM to truncate or mangle even on very large widgets. A structural check
still runs as a cheap defensive net; it should stay clean since tags/hrefs never
change.
"""

from src.ports.outbound import LLMPort

from src.application.translate_labels.validator import validate_translation

from .html_translate import translate_widget_html


def build_translate_widget_node(llm: LLMPort):
    async def translate_widget(state: dict) -> dict:
        widget: dict = state["widget"]
        dealer = state.get("dealer_name", "")

        async def translate_batch(segments: list[str]) -> list[str]:
            return await llm.translate_text_segments(segments, dealer)

        base = {
            "window_id": widget["window_id"],
            "widget_type": widget["widget_type"],
            "en_html": widget["en_html"],
        }

        try:
            es_html, total, untranslated = await translate_widget_html(
                widget["en_html"], translate_batch
            )
        except Exception as e:
            return {"results": [{
                **base,
                "es_html": "",
                "status": "error",
                "warnings": [f"Translation failed: {e}"],
                "raw": None,
                "reasoning": "",
            }]}

        # Nothing came back translated → surface a real error, not a silent
        # English save. Some untranslated (partial) → keep going with a warning.
        if total > 0 and untranslated >= total:
            return {"results": [{
                **base,
                "es_html": "",
                "status": "error",
                "warnings": ["Translation service returned nothing — try retranslate."],
                "raw": None,
                "reasoning": "",
            }]}

        warnings = validate_translation(widget["en_html"], es_html)
        if untranslated:
            warnings = warnings + [
                f"{untranslated} of {total} text segment(s) were left in English — "
                "retranslate or edit them."
            ]
        return {"results": [{
            **base,
            "es_html": es_html,
            "status": "ready",
            "warnings": warnings,
            "raw": None,
            "reasoning": f"Translated {total - untranslated} of {total} text segment(s); markup preserved.",
        }]}

    return translate_widget
