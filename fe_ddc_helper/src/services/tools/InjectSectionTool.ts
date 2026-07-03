/// <reference types="chrome" />
import { injectSectionInjected } from '../../scripts/cmsTools'
import type { ICmsTool } from './ICmsTool'

interface InjectSectionArgs {
  site_id: string
  page_alias: string
  section_type: string
}

export class InjectSectionTool implements ICmsTool<InjectSectionArgs> {
  readonly name = 'inject_section'
  readonly domain = 'cms' as const

  async execute(args: InjectSectionArgs, tabId: number, token: string): Promise<unknown> {
    const res = await chrome.scripting.executeScript({
      target: { tabId },
      func: injectSectionInjected,
      args: [args.site_id, token, args.page_alias, args.section_type],
    })
    return res[0]?.result
  }
}
