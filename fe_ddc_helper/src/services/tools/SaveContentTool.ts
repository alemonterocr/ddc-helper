/// <reference types="chrome" />
import { saveContentInjected } from '../../scripts/cmsTools'
import type { ICmsTool } from './ICmsTool'

const TOKEN_KEY = 'ccIdtToken'

interface SaveContentArgs {
  site_id: string
  window_id: string
  html: string
}

export class SaveContentTool implements ICmsTool<SaveContentArgs> {
  readonly name   = 'save_content'
  readonly domain = 'cms' as const

  async execute(args: SaveContentArgs, tabId: number, _token: string): Promise<unknown> {
    const storage = await chrome.storage.local.get([TOKEN_KEY])
    const userId  = _extractUserId(storage[TOKEN_KEY] as string ?? '')

    const res = await chrome.scripting.executeScript({
      target: { tabId },
      func: saveContentInjected,
      args: [args.site_id, args.window_id, args.html, userId],
    })
    return res[0]?.result
  }
}

function _extractUserId(jwt: string): string {
  try {
    const base64 = jwt.split('.')[1]?.replace(/-/g, '+').replace(/_/g, '/')
    if (!base64) return ''
    const claims = JSON.parse(atob(base64)) as Record<string, unknown>
    return (claims['sub'] as string) ?? ''
  } catch {
    return ''
  }
}
