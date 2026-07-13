/**
 * Shared helpers for DDC-composer-tab access.
 *
 * These run in the extension context (not injected into the page), so they may
 * be imported normally. Injected scripts — the functions passed to
 * `chrome.scripting.executeScript` — must still stay self-contained per the
 * `scripts/` rule; those live in each adapter, not here.
 *
 * Extracted from `LabelAdapter` so `PageAdapter` can reuse the exact same
 * composer-tab lookup and userId derivation.
 */

/**
 * Find the DDC composer tab by URL pattern, not by "active tab in current
 * window" — the latter breaks when the extension page itself is in the
 * foreground. Mirrors WSClientAdapter._findCmsTab.
 */
export async function findComposerTabId(): Promise<number> {
  const tabs = await chrome.tabs.query({
    url: '*://*.website.dealercenter.coxautoinc.com/*',
  })
  const composer = tabs.find((t) => t.id !== undefined)
  if (composer?.id !== undefined) return composer.id

  throw new Error(
    'No DDC composer tab found — open the composer in a browser tab first',
  )
}

/** Derive the DDC userId from the stored `ccIdtToken` JWT (`sub` claim). */
export function extractUserId(jwt: string): string {
  try {
    const base64 = jwt.split('.')[1]?.replace(/-/g, '+').replace(/_/g, '/')
    if (!base64) return ''
    const claims = JSON.parse(atob(base64)) as Record<string, unknown>
    return (claims['sub'] as string) ?? ''
  } catch {
    return ''
  }
}
