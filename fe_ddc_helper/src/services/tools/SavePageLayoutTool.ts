/// <reference types="chrome" />
import { savePageLayoutInjected } from '../../scripts/cmsTools'
import type { ICmsTool } from './ICmsTool'

const TOKEN_KEY = 'ccIdtToken'

interface SavePageLayoutArgs {
  site_id: string
  page_alias: string
  page_title: string
  /** URL path, e.g. /awards.htm */
  page_path: string
  /** Slot-key → portlet-window array (the full groups map, including pre-existing widgets) */
  groups: Record<string, unknown[]>
}

export class SavePageLayoutTool implements ICmsTool<SavePageLayoutArgs> {
  readonly name = 'save_page_layout'
  readonly domain = 'cms' as const

  async execute(args: SavePageLayoutArgs, tabId: number, _token: string): Promise<unknown> {
    // Decode userId from the JWT stored in chrome.storage.local.
    // The JWT payload is base64url-encoded — atob handles standard base64;
    // we replace URL-safe chars first.
    const storage = await chrome.storage.local.get([TOKEN_KEY])
    const jwt = (storage[TOKEN_KEY] as string) ?? ''
    const userId = _extractUserIdFromJwt(jwt)

    const res = await chrome.scripting.executeScript({
      target: { tabId },
      func: savePageLayoutInjected,
      args: [args.site_id, args.page_alias, args.page_title, args.page_path, args.groups, userId],
    })
    return res[0]?.result
  }
}

/**
 * Extract the `sub` claim (userId) from a JWT without any library.
 * Returns an empty string if the token is missing or malformed.
 */
function _extractUserIdFromJwt(jwt: string): string {
  try {
    const payloadB64 = jwt.split('.')[1]
    if (!payloadB64) return ''
    // base64url → base64
    const base64 = payloadB64.replace(/-/g, '+').replace(/_/g, '/')
    const json = atob(base64)
    const claims = JSON.parse(json) as Record<string, unknown>
    return (claims['sub'] as string) ?? ''
  } catch {
    return ''
  }
}
