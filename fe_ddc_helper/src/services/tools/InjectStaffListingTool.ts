/// <reference types="chrome" />
import { injectStaffListingInjected } from '../../scripts/cmsTools'
import type { ICmsTool } from './ICmsTool'

interface InjectStaffListingArgs {
  site_id: string
  payload: unknown   // built by the backend StaffExecutor
}

export class InjectStaffListingTool implements ICmsTool<InjectStaffListingArgs> {
  readonly name   = 'inject_staff_listing'
  readonly domain = 'cms' as const

  async execute(args: InjectStaffListingArgs, tabId: number, token: string): Promise<unknown> {
    const res = await chrome.scripting.executeScript({
      target: { tabId },
      func: injectStaffListingInjected,
      args: [args.site_id, token, args.payload] as [string, string, unknown],
    })
    return res[0]?.result
  }
}
