/**
 * Self-contained functions injected into the active DDC CMS tab via
 * chrome.scripting.executeScript. Zero imports, zero external closures —
 * Chrome serialises these with .toString() so they must be fully standalone.
 */

export async function checkPageExistsInjected(
  siteId: string,
  pageAlias: string,   // URL slug, e.g. "awards" or "awards.htm"
): Promise<{ exists: boolean; error?: string }> {
  // DDC validate endpoint returns 406 when the path is already taken (page exists),
  // 200 when the path is available (page does not exist).
  const slug = pageAlias.replace(/^\//, '').replace(/\.htm$/, '')
  const pagePath = `/${slug}.htm`
  const url = [
    `https://${window.location.hostname}`,
    `cc-website/as/${siteId}/${siteId}-admin`,
    `cms-configurator/api/pages/${siteId}/validate?pagePath=${encodeURIComponent(pagePath)}`,
  ].join('/')

  try {
    const res = await fetch(url, {
      method: 'GET',
      credentials: 'include',
      headers: {
        accept: '*/*',
        'cache-control': 'no-cache',
        'content-type': 'application/json',
        'x-coxauto-traffic-group': 'composer-dynamic-request',
      },
    })
    if (res.status === 406) return { exists: true }   // path taken
    if (res.ok)             return { exists: false }  // path available
    return { exists: false, error: `Status: ${res.status}` }
  } catch (err) {
    return { exists: false, error: (err as Error).message }
  }
}

/**
 * Look up a page's DDC internal alias (e.g. SITEBUILDER_AWARDS_3) by its URL path.
 * Calls GET /api/sites/{siteId}/pages — the symmetric counterpart to the POST that creates pages.
 * The response is expected to be an array (or wrapped list) of page objects, each with
 * { alias, path } fields matching the structure returned by the create-page endpoint.
 */
export async function getPageAliasByPathInjected(
  siteId: string,
  pageSlug: string,   // e.g. "awards" or "awards.htm"
): Promise<{ found: boolean; alias?: string; error?: string }> {
  const slug = pageSlug.replace(/^\//, '').replace(/\.htm$/, '')
  const normalizedPath = `/${slug}.htm`

  const url = [
    `https://${window.location.hostname}`,
    `cc-website/as/${siteId}/${siteId}-admin`,
    `cms-configurator/api/sites/${siteId}/pages`,
  ].join('/')

  try {
    const res = await fetch(url, {
      method: 'GET',
      credentials: 'include',
      headers: {
        accept: 'application/json',
        'x-coxauto-traffic-group': 'composer-dynamic-request',
      },
    })
    if (!res.ok) return { found: false, error: `Status ${res.status}` }

    const raw = await res.json()
    // Response may be a plain array or wrapped: { list: [...] } / { map: {...} }
    let pages: unknown[]
    if (Array.isArray(raw)) {
      pages = raw
    } else if (raw && typeof raw === 'object') {
      const obj = raw as Record<string, unknown>
      pages = (
        Array.isArray(obj['list'])  ? obj['list']  as unknown[] :
        Array.isArray(obj['pages']) ? obj['pages'] as unknown[] :
        obj['map'] && typeof obj['map'] === 'object'
          ? Object.values(obj['map'] as object)
          : []
      )
    } else {
      return { found: false, error: 'Unexpected response shape' }
    }

    for (const page of pages) {
      const p = page as Record<string, unknown>
      const path  = p['path']  as string | undefined
      const alias = p['alias'] as string | undefined
      if (path === normalizedPath && alias) return { found: true, alias }
    }
    return { found: false }
  } catch (err) {
    return { found: false, error: (err as Error).message }
  }
}

export async function getPageLayoutInjected(
  _siteId: string,
  _pageAlias: string,
  pageSlug: string,   // URL slug, e.g. "awards" (no .htm)
): Promise<{ success: boolean; groups?: Record<string, unknown[]>; error?: string }> {
  // DDC has no REST endpoint for page layout — groups are embedded in the
  // rendered HTML.  Fetch the page with the composer renderer params and
  // parse [data-group-id] / .pref[id][portlet] from the DOM.
  const url = `https://${window.location.hostname}/${pageSlug}.htm?_renderer=desktop&buildingPage=false&useAjaxWrap=true&locale=en_US&_toggleBasePageCache=false`

  try {
    const res = await fetch(url, {
      method: 'GET',
      credentials: 'include',
      headers: {
        accept: 'text/html',
        'x-coxauto-traffic-group': 'composer-dynamic-request',
      },
    })
    if (!res.ok) return { success: false, error: `Status ${res.status}` }

    const html = await res.text()
    const parser = new DOMParser()
    const doc = parser.parseFromString(html, 'text/html')

    const result: Record<string, unknown[]> = {}
    const groupEls = doc.querySelectorAll('[data-group-id]')
    for (const el of Array.from(groupEls)) {
      const groupId = el.getAttribute('data-group-id')
      if (!groupId) continue
      const widgets: unknown[] = []
      const prefEls = el.querySelectorAll('.pref[id][portlet]')
      for (const pref of Array.from(prefEls)) {
        const windowId = pref.getAttribute('id') ?? ''
        const portlet  = pref.getAttribute('portlet') ?? ''
        if (windowId && portlet) {
          widgets.push({
            javaClass: 'com.dealer.cms.apps.composer.model.WidgetDTO',
            windowId,
            portlet,
            editable: true,
            preferences: null,
            overrides: null,
          })
        }
      }
      if (widgets.length) result[groupId] = widgets
    }
    return { success: true, groups: result }
  } catch (err) {
    return { success: false, error: (err as Error).message }
  }
}

export async function createPageInjected(
  siteId: string,
  _token: string,
  path: string,
  title: string,
): Promise<{ success: boolean; pageAlias?: string; error?: string }> {
  const url = [
    `https://${window.location.hostname}`,
    `cc-website/as/${siteId}/${siteId}-admin`,
    `cms-configurator/api/sites/${siteId}/pages`,
  ].join('/')

  // DDC requires path to be "/<slug>.htm" — normalise regardless of what the backend sent
  const slug = path.replace(/^\//, '').replace(/\.htm$/, '')
  const normalizedPath = `/${slug}.htm`

  try {
    const res = await fetch(url, {
      method: 'POST',
      credentials: 'include',           // session cookies handle auth — no Authorization header needed
      headers: {
        accept: '*/*',
        'cache-control': 'no-cache',
        'content-type': 'application/json',
        'x-coxauto-traffic-group': 'composer-dynamic-request',
      },
      body: JSON.stringify({
        localeData: { en_US: { title, path: normalizedPath } },
        primaryLocale: 'en_US',
        externalEditable: true,
        sections: [{ sectionType: 'title' }],
        templatePageId: null,
        templateSiteId: null,
      }),
    })
    if (!res.ok) {
      const body = await res.text().catch(() => '')
      return { success: false, error: `Status ${res.status}: ${body.slice(0, 200)}` }
    }
    const data = await res.json()
    // DDC returns the internal alias (e.g. "SITEBUILDER_AWARDS_3") — required for section injection
    if (!data.alias) return { success: false, error: 'No alias in DDC response' }
    return { success: true, pageAlias: data.alias as string }
  } catch (err) {
    return { success: false, error: (err as Error).message }
  }
}

export async function injectSectionInjected(
  siteId: string,
  _token: string,
  pageAlias: string,
  sectionType: string,
): Promise<{ success: boolean; error?: string }> {
  const url = [
    `https://${window.location.hostname}`,
    `cc-website/as/${siteId}/${siteId}-admin`,
    `cms-configurator/api/pages/${siteId}/alias/${pageAlias}/section/0`,
  ].join('/')

  try {
    const res = await fetch(url, {
      method: 'POST',
      credentials: 'include',           // session cookies handle auth
      headers: {
        accept: '*/*',
        'cache-control': 'no-cache',
        'content-type': 'application/json',
        'x-coxauto-traffic-group': 'composer-dynamic-request',
      },
      body: JSON.stringify({ version: 1, sectionType }),
    })
    if (res.ok) return { success: true }
    const body = await res.text().catch(() => '')
    return { success: false, error: `Status ${res.status}: ${body.slice(0, 200)}` }
  } catch (err) {
    return { success: false, error: (err as Error).message }
  }
}

export async function savePageLayoutInjected(
  siteId: string,
  pageAlias: string,   // DDC internal alias e.g. SITEBUILDER_AWARDS_2
  pageTitle: string,
  pagePath: string,    // URL path e.g. /awards.htm
  groups: Record<string, unknown[]>,
  userId: string,
): Promise<{ success: boolean; groups?: Record<string, unknown[]>; error?: string }> {
  const url = [
    `https://${window.location.hostname}`,
    `cc-website/as/${siteId}/${siteId}-admin`,
    `cms-configurator/api/commandExecutor/${siteId}?cmd=SavePage`,
  ].join('/')

  // Each slot value must be wrapped in the java.util.List shape DDC expects.
  const wrappedGroups: Record<string, unknown> = {}
  for (const [slotKey, windows] of Object.entries(groups)) {
    wrappedGroups[slotKey] = { javaClass: 'java.util.List', list: windows }
  }

  // Body shape confirmed from savePageExample.har.
  const body = {
    siteId,
    locale: 'en_US',
    javaClass: 'com.dealer.composer.commands.sitebuilder.SavePage',
    groups: { javaClass: 'java.util.HashMap', map: wrappedGroups },
    externalEditable: true,
    pageId: `${siteId}_${pageAlias}`,
    pageAlias,
    pageTitle,
    groupPage: false,
    isCreator: false,
    pagePath,
    accountId: siteId,
    userId,
    siteType: 'primary',
  }

  try {
    const res = await fetch(url, {
      method: 'POST',
      credentials: 'include',
      headers: {
        accept: 'application/json',
        'cache-control': 'no-cache',
        'content-type': 'application/json; charset=UTF-8',
        'x-coxauto-traffic-group': 'composer-dynamic-request',
        'x-requested-with': 'XMLHttpRequest',
      },
      body: JSON.stringify(body),
    })

    if (!res.ok) {
      const text = await res.text().catch(() => '')
      return { success: false, error: `Status ${res.status}: ${text.slice(0, 200)}` }
    }

    const data = await res.json() as Record<string, unknown>
    // Inlined unwrap — must not reference any module-level name (Vite minifies them).
    // SavePage returns plain { groups: { slot: [] } }; GET returns wrapped { map: { slot: { list: [] } } }.
    let responseGroups: Record<string, unknown[]> | null = null
    try {
      const gw = data['groups'] as Record<string, unknown> | null
      if (gw) {
        const entries = (gw['map'] ?? gw) as Record<string, unknown>
        const parsed: Record<string, unknown[]> = {}
        for (const [k, v] of Object.entries(entries)) {
          if (k === 'javaClass') continue
          if (Array.isArray(v)) { parsed[k] = v as unknown[]; continue }
          const lw = v as Record<string, unknown>
          const list = lw['list'] ?? lw
          if (Array.isArray(list)) parsed[k] = list as unknown[]
        }
        responseGroups = parsed
      }
    } catch { /* fall back to input groups */ }
    return { success: true, groups: responseGroups ?? groups }
  } catch (err) {
    return { success: false, error: (err as Error).message }
  }
}

export async function saveContentInjected(
  siteId: string,
  windowId: string,
  html: string,
  userId: string,
): Promise<{ success: boolean; error?: string }> {
  // windowId for content editing requires the "-editable" suffix
  const editableWindowId = windowId.endsWith('-editable') ? windowId : `${windowId}-editable`

  const url = [
    `https://${window.location.hostname}`,
    `cc-website/as/${siteId}/${siteId}-admin`,
    `cms-configurator/api/commandExecutor/${siteId}?cmd=SaveContent`,
  ].join('/')

  const body = {
    javaClass: 'com.dealer.composer.commands.SaveContent',
    siteId,
    windowId: editableWindowId,
    currentLocale: 'en_US',
    content: html,
    accountId: siteId,
    userId,
    siteType: 'primary',
  }

  try {
    const res = await fetch(url, {
      method: 'POST',
      credentials: 'include',
      headers: {
        accept: 'application/json',
        'cache-control': 'no-cache',
        'content-type': 'application/json',
        'x-coxauto-traffic-group': 'composer-dynamic-request',
      },
      body: JSON.stringify(body),
    })
    if (!res.ok) {
      const text = await res.text().catch(() => '')
      return { success: false, error: `Status ${res.status}: ${text.slice(0, 200)}` }
    }
    return { success: true }
  } catch (err) {
    return { success: false, error: (err as Error).message }
  }
}

export async function updateSiteLabelsInjected(
  siteId: string,
  labels: Array<{ key: string; value: string }>,
  userId: string,
): Promise<{ success: boolean; error?: string }> {
  const url = [
    `https://${window.location.hostname}`,
    `cc-website/as/${siteId}/${siteId}-admin`,
    `cms-configurator/api/commandExecutor/${siteId}?cmd=UpdateSiteLabels`,
  ].join('/')

  const body = {
    javaClass: 'com.dealer.composer.commands.config.UpdateSiteLabels',
    siteId,
    locale: 'en_US',
    labels: labels.map(l => ({
      key: l.key,
      value: l.value,
      javaClass: 'com.dealer.cms.apps.composer.model.SiteLabelDTO',
    })),
    accountId: siteId,
    userId,
    siteType: 'primary',
  }

  try {
    const res = await fetch(url, {
      method: 'POST',
      credentials: 'include',
      headers: {
        accept: '*/*',
        'cache-control': 'no-cache',
        'content-type': 'application/json; charset=UTF-8',
        'x-coxauto-traffic-group': 'composer-dynamic-request',
        'x-requested-with': 'XMLHttpRequest',
      },
      body: JSON.stringify(body),
    })
    if (!res.ok) {
      const text = await res.text().catch(() => '')
      return { success: false, error: `Status ${res.status}: ${text.slice(0, 200)}` }
    }
    return { success: true }
  } catch (err) {
    return { success: false, error: (err as Error).message }
  }
}

export async function setWindowPreferencesInjected(
  siteId: string,
  windowId: string,
  imagePath: string,
  userId: string,
): Promise<{ success: boolean; error?: string }> {
  // SetWindowPreferences uses a different base URL than the REST CMS configurator.
  // windowId does NOT get an "-editable" suffix here.
  const url = `https://${window.location.hostname}/composer/views/CommandExecutor?cmd=SetWindowPreferences`

  const payload = {
    javaClass: 'com.dealer.cms.apps.composer.commands.prefs.SetWindowPreferences',
    preferences: [
      {
        windowId,
        javaClass: 'com.dealer.cms.apps.composer.model.WindowPreferenceDTO',
        preferenceName: 'imagePath',
        preferenceValue: imagePath,
      },
      {
        windowId,
        javaClass: 'com.dealer.cms.apps.composer.model.WindowPreferenceDTO',
        preferenceName: 'imageTagClasses',
        preferenceValue: '',
      },
    ],
    siteId,
    windowId,
    accountId: siteId,
    userId,
    siteType: 'primary',
  }

  try {
    const res = await fetch(url, {
      method: 'POST',
      credentials: 'include',
      headers: {
        accept: '*/*',
        'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'x-coxauto-traffic-group': 'composer-dynamic-request',
        'x-requested-with': 'XMLHttpRequest',
      },
      body: `json=${encodeURIComponent(JSON.stringify(payload))}`,
    })
    if (!res.ok) {
      const text = await res.text().catch(() => '')
      return { success: false, error: `Status ${res.status}: ${text.slice(0, 200)}` }
    }
    return { success: true }
  } catch (err) {
    return { success: false, error: (err as Error).message }
  }
}


/**
 * Inject a staff-listing itemlist payload into DDC's CMS.
 *
 * Same pattern as cms-auto-builder/src/services/cmsApiService.ts → injectItemListPayload:
 * runs inside the active CMS tab so it inherits the session cookies (JWTAuth)
 * required by the /api/itemlist endpoint.
 *
 * The payload shape (built by the backend's StaffExecutor):
 *   { id: "ws-staff-listing", siteId, items: [...] }
 * where each item already has: department, name, title, phone, email, bio,
 * photo (CDN URL after upload), status, deviceOverrides, entityComponentClassName.
 *
 * Self-contained — zero external references because chrome.scripting.executeScript
 * serializes via .toString().
 */
export async function injectStaffListingInjected(
  siteId: string,
  token: string,
  payload: unknown,
): Promise<{ success: boolean; status?: number; error?: string }> {
  try {
    const targetUrl = `https://${window.location.hostname}/cc-website/as/${siteId}/${siteId}-admin/cms-configurator/api/itemlist?siteId=${siteId}`
    const res = await fetch(targetUrl, {
      method: 'POST',
      credentials: 'include',
      headers: {
        'accept': 'application/json',
        'content-type': 'application/json',
        'authorization': token,
        'x-coxauto-traffic-group': 'composer-dynamic-request',
      },
      body: JSON.stringify(payload),
    })
    if (res.status < 200 || res.status >= 300) {
      const text = await res.text().catch(() => '')
      return { success: false, status: res.status, error: `Status ${res.status}: ${text.slice(0, 200)}` }
    }
    return { success: true, status: res.status }
  } catch (err) {
    return { success: false, error: (err as Error).message }
  }
}

export async function injectItemListInjected(
  siteId: string,
  token: string,
  payload: unknown,
): Promise<{ success: boolean; status?: number; error?: string }> {
  try {
    const targetUrl = `https://${window.location.hostname}/cc-website/as/${siteId}/${siteId}-admin/cms-configurator/api/itemlist?siteId=${siteId}`
    const res = await fetch(targetUrl, {
      method: 'POST',
      credentials: 'include',
      headers: {
        'accept': 'application/json',
        'content-type': 'application/json',
        'authorization': token,
        'x-coxauto-traffic-group': 'composer-dynamic-request',
      },
      body: JSON.stringify(payload),
    })
    if (res.status < 200 || res.status >= 300) {
      const text = await res.text().catch(() => '')
      return { success: false, status: res.status, error: `Status ${res.status}: ${text.slice(0, 200)}` }
    }
    return { success: true, status: res.status }
  } catch (err) {
    return { success: false, error: (err as Error).message }
  }
}
