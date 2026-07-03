/// <reference types="chrome" />
import { injectItemListInjected } from '../../scripts/cmsTools'
import type { ICmsTool } from './ICmsTool'

interface InjectItemListArgs {
  site_id: string
  payload: unknown
}

export class InjectItemListTool implements ICmsTool<InjectItemListArgs> {
  readonly name   = 'inject_itemlist'
  readonly domain = 'cms' as const

  async execute(args: InjectItemListArgs, tabId: number, token: string): Promise<unknown> {
    const res = await chrome.scripting.executeScript({
      target: { tabId },
      func: injectItemListInjected,
      args: [args.site_id, token, args.payload] as [string, string, unknown],
    })
    return res[0]?.result
  }
}
