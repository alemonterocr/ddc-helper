/// <reference types="chrome" />
import { checkPageExistsInjected } from '../../scripts/cmsTools'
import type { ICmsTool } from './ICmsTool'

interface CheckPageExistsArgs {
  site_id: string
  page_alias: string
}

export class CheckPageExistsTool implements ICmsTool<CheckPageExistsArgs> {
  readonly name = 'check_page_exists'
  readonly domain = 'cms' as const

  async execute(args: CheckPageExistsArgs, tabId: number, _token: string): Promise<unknown> {
    const res = await chrome.scripting.executeScript({
      target: { tabId },
      func: checkPageExistsInjected,
      args: [args.site_id, args.page_alias],
    })
    return res[0]?.result
  }
}
