/// <reference types="chrome" />
import { getPageAliasByPathInjected } from '../../scripts/cmsTools'
import type { ICmsTool } from './ICmsTool'

interface GetPageAliasByPathArgs {
  site_id: string
  page_slug: string   // URL slug, e.g. "awards" or "awards.htm"
}

export class GetPageAliasByPathTool implements ICmsTool<GetPageAliasByPathArgs> {
  readonly name   = 'get_page_alias_by_path'
  readonly domain = 'cms' as const

  async execute(args: GetPageAliasByPathArgs, tabId: number, _token: string): Promise<unknown> {
    const res = await chrome.scripting.executeScript({
      target: { tabId },
      func: getPageAliasByPathInjected,
      args: [args.site_id, args.page_slug],
    })
    return res[0]?.result
  }
}
