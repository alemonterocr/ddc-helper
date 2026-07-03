/**
 * Self-contained functions injected into a logged-in Salesforce Lightning tab
 * via chrome.scripting.executeScript with world: 'MAIN'.
 *
 * MAIN world is required so the `sid` session cookie is sent automatically
 * (the Lightning page is same-origin and `credentials: 'include'` does the
 * rest). Isolated-world requests miss the cookie context.
 *
 * Zero imports, zero external closures - Chrome serialises these with
 * .toString(). IMPORTANT: define all constants as local `const` inside the
 * function body, NEVER at module level (Vite minifies module-level constants
 * and the minified names don't exist in the injected page's scope).
 *
 * Backend builds the path; this script just GETs it and returns the body.
 */

export interface SfUiApiGetResult {
  ok: boolean
  status: number
  body?: unknown
  error?: string
}

export async function sfUiApiGetInjected(path: string): Promise<SfUiApiGetResult> {
  try {
    const origin = window.location.origin // https://casfx.lightning.force.com
    const url = `${origin}${path}`
    const res = await fetch(url, {
      credentials: 'include',
      headers: { accept: 'application/json' },
    })
    const text = await res.text()
    let body: unknown = text
    try { body = JSON.parse(text) } catch { /* keep as text */ }
    if (!res.ok) {
      const hint = res.status === 401 || res.status === 403
        ? ' - make sure you are logged in to Salesforce in this browser'
        : ''
      return {
        ok: false,
        status: res.status,
        body,
        error: `UI API HTTP ${res.status}${hint}`,
      }
    }
    return { ok: true, status: res.status, body }
  } catch (e) {
    return { ok: false, status: 0, error: String(e) }
  }
}
