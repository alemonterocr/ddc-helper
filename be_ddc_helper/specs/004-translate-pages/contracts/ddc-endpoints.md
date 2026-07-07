# Contract: FE ↔ DDC endpoints (browser session)

These calls originate from the **DDC composer tab** via `chrome.scripting.executeScript`, reusing the user's session cookies (`credentials:'include'`, `x-coxauto-traffic-group: composer-dynamic-request`). The backend never calls these. Sourced from `UpdateContentExample.har` and `UpdateRAWHTMLContent.har`, plus the specialist's render-URL notes.

`{slug}` = dealer id (composer hostname's first label). `{userId}` = `sub` claim of the `ccIdtToken` JWT.

---

## 1. Page render (read) — `GET`

```
GET https://{slug}.website.dealercenter.coxautoinc.com{targetPath}
      ?_renderer=desktop&buildingPage=false&useAjaxWrap=true
      &locale={en_US|es_US}&_toggleBasePageCache=false
```

- Returns the full rendered page HTML (~0.5–2 MB) for the given locale.
- Called **twice** (both locales), in parallel, then both bodies are POSTed to `/translations/translate-page`.
- Editable widgets appear inside `div.main` as:
  - `div.text-content-container.editable.content` id=`…:contentN-editable` → **content widget**
  - `div.content.editable-raw-content` id=`…:contentN-editable` → **RAW HTML widget**

---

## 2. Save — content widget — `POST SaveContent`

```
POST https://{slug}.website.dealercenter.coxautoinc.com
     /cc-website/as/{slug}/{slug}-admin/cms-configurator/api/commandExecutor/{slug}?cmd=SaveContent
Content-Type: application/json; charset=UTF-8
```

```json
{
  "javaClass": "com.dealer.composer.commands.SaveContent",
  "siteId": "{slug}",
  "windowId": "SITEBUILDER_ALE_MONTERO_1:content1-editable",
  "currentLocale": "es_US",
  "content": "<p>…spanish…</p>",
  "accountId": "{slug}",
  "userId": "{userId}",
  "siteType": "primary"
}
```

- `windowId` **keeps** the `-editable` suffix.
- Success: `200` with `{ contentId, currentLocale, content, windowId, … }`.

---

## 3. Save — RAW HTML widget — `POST sitecontent`

```
POST https://{slug}.website.dealercenter.coxautoinc.com
     /cc-website/as/{slug}/{slug}-admin/cms-configurator/api/sites/{slug}/sitecontent?windowId={id}
Content-Type: application/json
```

```json
{ "es_US": "<p>…spanish…</p>" }
```

- `windowId` query param **strips** the `-editable` suffix (`…:content2-editable` → `…:content2`).
- Body is locale-keyed: `{"es_US": …}` or `{"en_US": …}`.
- No `userId`/`siteType` needed.
- Success: `201` with `{}`.

---

## 4. The two-save dance (both widget types)

DDC wipes the English content when only the Spanish locale is saved. So every save writes **both**, in order:

1. **Spanish** — content: SaveContent `currentLocale:"es_US", content:<es>`. raw: `{"es_US":<es>}`.
2. **English** — content: SaveContent `currentLocale:"en_US", content:<en original>`. raw: `{"en_US":<en original>}`.

The English payload is the **unchanged** original `en_html` from extraction. Encapsulate both writes in one `saveWidget()` so callers cannot forget the second write. If the first (Spanish) write fails, do not attempt the second; surface the error on the card.
