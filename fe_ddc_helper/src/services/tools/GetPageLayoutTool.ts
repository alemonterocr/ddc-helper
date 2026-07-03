/// <reference types="chrome" />
import { getPageLayoutInjected } from '../../scripts/cmsTools'
import type { ICmsTool } from './ICmsTool'

interface GetPageLayoutArgs {
  site_id: string
  page_alias: string
  page_slug: string   // URL slug without .htm, e.g. "awards"
}

export class GetPageLayoutTool implements ICmsTool<GetPageLayoutArgs> {
  readonly name   = 'get_page_layout'
  readonly domain = 'cms' as const

  async execute(args: GetPageLayoutArgs, tabId: number, _token: string): Promise<unknown> {
    const res = await chrome.scripting.executeScript({
      target: { tabId },
      func: getPageLayoutInjected,
      args: [args.site_id, args.page_alias, args.page_slug],
    })
    return res[0]?.result
  }
}
