# Quickstart: Translate Page Widgets

Validation guide proving the feature works end-to-end. Assumes the BE runs locally (`uvicorn`) and the extension is loaded in Chrome with a DDC composer tab open and logged in.

---

## Prerequisites

- BE deps installed incl. new `beautifulsoup4`, `lxml`: `uv sync` (or `pip install -e .`).
- An LLM provider API key configured through the extension's home screen.
- A DDC composer tab open at `*.website.dealercenter.coxautoinc.com` for the target dealer.
- Two saved HAR/HTML fixtures for offline BE tests (see below).

---

## 1. BE unit tests (offline, no LLM, no DDC)

```bash
cd be_ddc_helper
pytest tests/test_widget_extract.py -q
pytest tests/test_translate_page_graph.py -q
```

**`test_widget_extract.py` asserts:**
- Given a small `div.main` fixture with one content + one raw widget, `extract_widgets` returns two `PageWidget`s with correct `widget_type`, `window_id` (with `-editable`), and inner HTML.
- en/es pairing by `window_id`; missing es id → `es_html == ""`.
- Inner-HTML round-trip: `decode_contents()` on representative widget HTML is byte-stable (or documents the exact normalization).
- No `div.main` → empty list (not an error).

**`test_translate_page_graph.py` asserts (mock `LLMPort`):**
- Check logic: empty es → to_translate; `es==en` → to_translate; distinct es with `judge ok:true` → skipped; `ok:false` → to_translate.
- Fan-out count equals `len(to_translate)`; each produces one `results` entry (order-independent).
- Event sequence from the streaming wrapper: `extracted` → `skipped` → `widget`×N → `done`; a raised error yields a terminal `error` event.

---

## 2. BE endpoint smoke test (LLM live, DDC not needed)

Feed saved page HTML directly (bypasses the browser fetch):

```bash
# both *.html are previously-captured renders trimmed to include div.main
python - <<'PY'
import json, httpx
en = open("tests/fixtures/page_en.html", encoding="utf-8").read()
es = open("tests/fixtures/page_es.html", encoding="utf-8").read()
with httpx.stream("POST", "http://localhost:8000/translations/translate-page",
                  json={"en_page_html": en, "es_page_html": es,
                        "dealer_name": "Go Hyundai Renton", "provider": "anthropic"},
                  timeout=None) as r:
    for line in r.iter_lines():
        if line:
            print(json.loads(line)["type"])
PY
```

**Expected stdout (order):** `extracted`, `skipped`, `widget` (repeated), `done`.

---

## 3. Manual FE walkthrough (full loop, live DDC)

1. Open the extension → a **Spanish** project → **Translate Page** tab.
2. Enter a target path (e.g. `/new-inventory/index.htm`) → **Load Page Widgets**.
3. Expect: placeholder cards appear (from `extracted`), skipped footer populates, cards fill in progressively as translations stream.
4. On one card: verify EN preview, editable ES, `content`/`raw` badge, warnings/reasoning.
5. Click **Save**. In DevTools Network, confirm **two** DDC writes in order:
   - content widget → two `SaveContent` POSTs (`currentLocale` es_US then en_US);
   - raw widget → two `sitecontent` POSTs (`{"es_US":…}` then `{"en_US":…}`), `windowId` **without** `-editable`.
6. Reload the es_US composer → the widget shows the Spanish translation; reload en_US → English is unchanged.
7. In the skipped footer, click **Force translate** on one row → it moves into the board and translates.

---

## Success criteria

- [ ] BE unit tests pass (extraction + graph).
- [ ] Streaming smoke test prints the expected event order.
- [ ] A content widget and a raw widget each save both locales via the correct endpoint + `windowId` suffix.
- [ ] English content is intact after the two-save; Spanish is the translation.
- [ ] Skip detection leaves genuinely-translated widgets untouched; force-translate overrides.
