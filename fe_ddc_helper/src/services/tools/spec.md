---
name: cms-tools
type: adapter
status: built
layer: adapter
---

## Purpose

CMS tool classes that the `WSClientAdapter` dispatches when the backend sends a
`tool_call` message. Each tool wraps one injected function from `scripts/cmsTools.ts`
and bridges the WebSocket command into a `chrome.scripting.executeScript` call
against the active DDC CMS tab.

All tools implement `ICmsTool<TArgs>`:
- `domain: 'cms'` → injects into `*.website.dealercenter.coxautoinc.com` (JSESSIONID auth)
- `domain: 'media_lib'` → injects into `apps.dealercenter.coxautoinc.com` (JWTAuth cookie)

---

## Widget injection sequence

This is the end-to-end flow for placing and populating a widget inside a DDC section.
Steps must run in order — each step depends on data produced by the previous one.

```
1. inject_section       — create the empty section shell on the page
2. get_page_layout      — read current slot keys and existing windowIds
2b. update_site_labels  — register button text labels (button widgets only, before SavePage)
3. save_page_layout     — place WidgetDTOs into slots (windowIds generated client-side)
4. get_page_layout      — re-fetch to confirm windowIds were persisted
5a. save_content        — write HTML into a content widget   (content widgets only)
5b. set_window_prefs    — set imagePath on an image widget   (image widgets only)
(no step 5 for button widgets — text is stored in site labels, not the widget itself)
(no step 5 for form widgets — source label is derived from page title, no further calls needed)
(no step 5 for contact_info widgets — DDC auto-populates from dealership profile, zero config)
(no step 5 for hours widgets — DDC auto-populates from dealership profile, zero config)
```

---

## Slot key formula

DDC addresses each widget position with a slot key string.

```
page-title row  →  "1-1"                        (pre-wired by DDC, never written manually)
content rows    →  "{position + 2}-1-1-{col}-1"  (1-indexed col)

Examples:
  position=0, col=1  →  "2-1-1-1-1"
  position=0, col=2  →  "2-1-1-2-1"
  position=1, col=1  →  "3-1-1-1-1"
  position=1, col=2  →  "3-1-1-2-1"
```

`position` is the 0-based index of the section in the page's section plan.
`col` is the 1-based column index within the section layout.

The slot key source of truth is `be_ddc_helper/src/domain/catalog/section_slots.py`.

---

## WindowId generation

DDC does NOT auto-assign windowIds. The real DDC composer generates them
client-side before calling SavePage. The pattern is:

```
{pageAlias}:{widgetType}{n}

Examples:
  SITEBUILDER_AWARDS_1:content1
  SITEBUILDER_AWARDS_1:content2
  SITEBUILDER_AWARDS_1:image1
  SITEBUILDER_AWARDS_1:page-title1
```

- `pageAlias` is the DDC internal alias returned by `create_page` (e.g. `SITEBUILDER_AWARDS_1`)
- `widgetType` is the portlet short name (`content`, `image`, `page-title`, …)
- `n` is a 1-based counter per type, seeded from widgets already present in `current_groups`

The placement loop in `execute_router.py` is responsible for generating these before
each `save_page_layout` call and carrying them forward into the content/image injection steps.

---

## Tool reference

### `inject_section`
Creates an empty section shell on the DDC page.

| | |
|---|---|
| Injected fn | `injectSectionInjected` |
| DDC endpoint | `POST /cms-configurator/api/pages/{siteId}/alias/{pageAlias}/section/0` |
| Body | `{ version: 1, sectionType }` |
| Args | `site_id`, `page_alias`, `section_type` |
| Returns | `{ success: boolean, error?: string }` |

---

### `get_page_layout`
Reads the current slot/widget state by fetching the rendered page HTML and
parsing `[data-group-id]` / `.pref[id][portlet]` nodes. Used both before
placement (to seed windowId counters) and after (to confirm persistence).

| | |
|---|---|
| Injected fn | `getPageLayoutInjected` |
| DDC endpoint | `GET /{pageSlug}.htm?_renderer=desktop&buildingPage=false&useAjaxWrap=true&locale=en_US` |
| Args | `site_id`, `page_alias`, `page_slug` |
| Returns | `{ success: boolean, groups?: Record<slotKey, WidgetDTO[]> }` |

---

### `save_page_layout`
Places `WidgetDTO` objects into slot keys. Sends the full groups map (existing
widgets + new widgets) so DDC does not lose pre-wired widgets like `page-title`.

| | |
|---|---|
| Injected fn | `savePageLayoutInjected` |
| DDC endpoint | `POST /cms-configurator/api/commandExecutor/{siteId}?cmd=SavePage` |
| Args | `site_id`, `page_alias`, `page_title`, `page_path`, `groups` |
| Returns | `{ success: boolean, groups?: Record<slotKey, WidgetDTO[]> }` |

**WidgetDTO shape (new widget):**
```json
{
  "javaClass": "com.dealer.cms.apps.composer.model.WidgetDTO",
  "portlet": "v9.widgets.content.default.v1",
  "windowId": "SITEBUILDER_AWARDS_1:content1",
  "type": "Content",
  "editable": true,
  "preferences": null,
  "overrides": null,
  "hiddenDeviceDefaults": { "tablet": "false", "desktop": "false", "mobile": "false" }
}
```

**Groups wrapper shape:**
```json
{
  "javaClass": "java.util.HashMap",
  "map": {
    "1-1":       { "javaClass": "java.util.List", "list": [ /* page-title widget */ ] },
    "2-1-1-1-1": { "javaClass": "java.util.List", "list": [ /* new content widget */ ] }
  }
}
```

---

### `save_content`
Writes HTML into a content widget. The windowId must have the `-editable` suffix —
`saveContentInjected` appends it automatically if missing.

| | |
|---|---|
| Injected fn | `saveContentInjected` |
| DDC endpoint | `POST /cms-configurator/api/commandExecutor/{siteId}?cmd=SaveContent` |
| Args | `site_id`, `window_id`, `html` |
| Returns | `{ success: boolean, error?: string }` |

**Body shape:**
```json
{
  "javaClass": "com.dealer.composer.commands.content.SaveContent",
  "siteId": "vindemo3",
  "windowId": "SITEBUILDER_AWARDS_1:content1-editable",
  "currentLocale": "en_US",
  "content": "<div class=\"container\">...</div>",
  "accountId": "vindemo3",
  "userId": "...",
  "siteType": "primary"
}
```

---

### `update_site_labels`
Registers button text strings as named site labels before placing a button widget.
Must be called **before** `save_page_layout` for any section that contains a
`v9.widgets.links.list.v1` widget.

| | |
|---|---|
| Injected fn | `updateSiteLabelsInjected` |
| DDC endpoint | `POST /cms-configurator/api/commandExecutor/{siteId}?cmd=UpdateSiteLabels` |
| Content-Type | `application/json; charset=UTF-8` |
| Args | `site_id`, `labels: Array<{ key: string, value: string }>` |
| Returns | `{ success: boolean, error?: string }` |

**Label key format:**
```
SITEBUILDER_BUTTONBLOCK_{uniqueTimestamp}_{fieldName}

Examples:
  SITEBUILDER_BUTTONBLOCK_1780274638960_LINKTEXT1
  SITEBUILDER_BUTTONBLOCK_1780274638960_LINKTEXT2
```
`uniqueTimestamp` is generated with `Date.now()` before calling this tool.
Each button block on a page must have its own unique timestamp.

**Body shape:**
```json
{
  "javaClass": "com.dealer.composer.commands.config.UpdateSiteLabels",
  "siteId": "mojix",
  "locale": "en_US",
  "labels": [
    { "key": "SITEBUILDER_BUTTONBLOCK_1780274638960_LINKTEXT1", "value": "New Inventory", "javaClass": "com.dealer.cms.apps.composer.model.SiteLabelDTO" },
    { "key": "SITEBUILDER_BUTTONBLOCK_1780274638960_LINKTEXT2", "value": "Pre-Owned",     "javaClass": "com.dealer.cms.apps.composer.model.SiteLabelDTO" }
  ],
  "accountId": "mojix",
  "userId": "...",
  "siteType": "primary"
}
```

---

### Button widget DTO (for `save_page_layout`)
Button widgets use `overrides` instead of `preferences`. The text values
reference site labels via `$i18n.getLabel(...)` — never inline strings.
`windowId` is `""` for Links-type widgets (DDC does not assign one).

```json
{
  "javaClass": "com.dealer.cms.apps.composer.model.WidgetDTO",
  "portlet": "v9.widgets.links.list.v1",
  "type": "Links",
  "windowId": "",
  "editable": true,
  "preferences": null,
  "overrides": {
    "javaClass": "java.util.ArrayList",
    "list": [
      "linkText1:$i18n.getLabel('SITEBUILDER_BUTTONBLOCK_{timestamp}_LINKTEXT1')",
      "linkStyle1:primary",
      "linkHref1:/new-inventory/index.htm",
      "linkTarget1:_top",
      "linkAttrs1:",
      "linkClass1:BLANK",
      "linkText2:$i18n.getLabel('SITEBUILDER_BUTTONBLOCK_{timestamp}_LINKTEXT2')",
      "linkStyle2:primary",
      "linkHref2:/used-inventory/index.htm",
      "linkTarget2:_self",
      "linkAttrs2:",
      "linkClass2:",
      "listSize:2"
    ]
  },
  "hiddenDeviceDefaults": { "tablet": "false", "desktop": "false", "mobile": "false" }
}
```

**Override fields per button:**

| Field | Values |
|---|---|
| `linkText{n}` | `$i18n.getLabel('...')` — always a label reference |
| `linkStyle{n}` | `primary` \| `secondary` \| `outline` |
| `linkHref{n}` | URL or path |
| `linkTarget{n}` | `_top` (same window) \| `_self` (same frame) \| `_blank` (new tab) |
| `linkAttrs{n}` | Extra HTML attributes — usually `""` |
| `linkClass{n}` | `BLANK` or `""` |
| `listSize` | Total number of buttons as a string |

---

### Form widget DTO (for `save_page_layout`)
Form widgets require only a `SavePage` call — no pre-step, no post-step.
`windowId` is `""` and stays empty (same behavior as links widgets).
The only override is the lead source label, derived automatically from the page title.

```json
{
  "javaClass": "com.dealer.cms.apps.composer.model.WidgetDTO",
  "portlet": "v9.widgets.contact.form.v1",
  "type": "Contact",
  "windowId": "",
  "editable": true,
  "preferences": null,
  "overrides": {
    "javaClass": "java.util.List",
    "list": ["source:{page_title} - Dealer.Com Website"]
  },
  "hiddenDeviceDefaults": { "tablet": "false", "desktop": "false", "mobile": "false" }
}
```

Note: form overrides use `java.util.List`, not `java.util.ArrayList` (unlike links widgets).

---

### Contact info widget DTO (for `save_page_layout`)
The simplest widget — no pre-step, no post-step, no overrides, no configuration.
DDC auto-populates address and phone numbers from the dealership's profile.
`windowId` is `""` and stays empty.

```json
{
  "javaClass": "com.dealer.cms.apps.composer.model.WidgetDTO",
  "portlet": "v9.widgets.contact.info.v1",
  "type": "Contact",
  "windowId": "",
  "editable": true,
  "preferences": null,
  "overrides": null,
  "hiddenDeviceDefaults": { "tablet": "false", "desktop": "false", "mobile": "false" }
}
```

---

### Hours widget DTO (for `save_page_layout`)
No pre-step, no post-step, no overrides. DDC auto-populates hours from the
dealership's profile. Identical structure to contact_info.

`portlet` is `"ws-hours"` — a legacy name with no `v9.widgets.*` equivalent.
Do not "fix" this to match the v9 naming convention; it will break.

```json
{
  "javaClass": "com.dealer.cms.apps.composer.model.WidgetDTO",
  "portlet": "ws-hours",
  "type": "Hours",
  "windowId": "",
  "editable": true,
  "preferences": null,
  "overrides": null,
  "hiddenDeviceDefaults": { "tablet": "false", "desktop": "false", "mobile": "false" }
}
```

---

### `set_window_preferences`
Sets the `imagePath` preference on an image widget. Uses a different base URL
than the REST configurator endpoints (`/composer/views/CommandExecutor`).
The windowId does **not** get an `-editable` suffix here.

| | |
|---|---|
| Injected fn | `setWindowPreferencesInjected` |
| DDC endpoint | `POST /composer/views/CommandExecutor?cmd=SetWindowPreferences` |
| Content-Type | `application/x-www-form-urlencoded` (body: `json=<encoded JSON>`) |
| Args | `site_id`, `window_id`, `image_path` |
| Returns | `{ success: boolean, error?: string }` |

**Preferences set:**
- `imagePath` — absolute path to the media library image
- `imageTagClasses` — always `""` (reset to default)

---

## Critical gotchas

- **Never send `windowId: ""`** — DDC echoes back whatever you send. An empty windowId
  gets stored as empty, and `save_content` will silently skip that widget.
  **Exception: `links` (button) widgets always use `windowId: ""`** — DDC does not
  assign one for Links-type widgets, and they have no post-placement step that needs it.
- **Always include pre-existing widgets** in the `groups` map when calling `save_page_layout`.
  Omitting `"1-1"` (page-title) will wipe it from the page.
- **`save_content` requires `-editable` suffix; `set_window_preferences` does not.**
- **`setWindowPreferencesInjected` uses form-encoded body**, not JSON — different from
  every other CMS tool. Do not change the `content-type` header.
- **Portlet name for content widgets:** `v9.widgets.content.default.v1`
- **Portlet name for image widgets:** check `ddc_catalog.json` — varies by section type.
