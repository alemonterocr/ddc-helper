/// <reference types="chrome" />
import { createMediaFolderInjected } from '../../scripts/mediaLibTools'
import type { ICmsTool } from './ICmsTool'

interface CreateMediaFolderArgs {
  site_id: string
  parent_id: string
  name: string
}

export class CreateMediaFolderTool implements ICmsTool<CreateMediaFolderArgs> {
  readonly name   = 'create_media_folder'
  readonly domain = 'media_lib' as const

  async execute(args: CreateMediaFolderArgs, tabId: number, _token: string): Promise<unknown> {
    const res = await chrome.scripting.executeScript({
      target: { tabId },
      world: 'MAIN',
      func: createMediaFolderInjected,
      args: [args.site_id, `${args.site_id}-admin`, args.parent_id, args.name],
    })
    return res[0]?.result
  }
}
