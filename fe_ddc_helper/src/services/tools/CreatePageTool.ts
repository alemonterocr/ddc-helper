/// <reference types="chrome" />
import { createPageInjected } from '../../scripts/cmsTools'
import type { ICmsTool } from './ICmsTool'

interface CreatePageArgs {
  site_id: string
  path: string
  title: string
}

export class CreatePageTool implements ICmsTool<CreatePageArgs> {
  readonly name = 'create_page'
  readonly domain = 'cms' as const

  async execute(args: CreatePageArgs, tabId: number, token: string): Promise<unknown> {
    const res = await chrome.scripting.executeScript({
      target: { tabId },
      func: createPageInjected,
      args: [args.site_id, token, args.path, args.title],
    })
    return res[0]?.result
  }
}
