/// <reference types="chrome" />
import { updateSiteLabelsInjected } from '../../scripts/cmsTools'
import type { ICmsTool } from './ICmsTool'

const TOKEN_KEY = 'ccIdtToken'

interface UpdateSiteLabelsArgs {
  site_id: string
  /** Array of { key, value } label pairs to register. */
  labels: Array<{ key: string; value: string }>
}

export class UpdateSiteLabelsTool implements ICmsTool<UpdateSiteLabelsArgs> {
  readonly name   = 'update_site_labels'
  readonly domain = 'cms' as const

  async execute(args: UpdateSiteLabelsArgs, tabId: number, _token: string): Promise<unknown> {
    const storage = await chrome.storage.local.get([TOKEN_KEY])
    const userId  = _extractUserId(storage[TOKEN_KEY] as string ?? '')

    const res = await chrome.scripting.executeScript({
      target: { tabId },
      func: updateSiteLabelsInjected,
      args: [args.site_id, args.labels, userId],
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
