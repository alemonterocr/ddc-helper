/// <reference types="chrome" />
import { getMediaFoldersInjected } from '../../scripts/mediaLibTools'
import type { ICmsTool } from './ICmsTool'

interface GetMediaFoldersArgs {
  site_id: string
}

export class GetMediaFoldersTool implements ICmsTool<GetMediaFoldersArgs> {
  readonly name   = 'get_media_folders'
  readonly domain = 'media_lib' as const

  async execute(args: GetMediaFoldersArgs, tabId: number, _token: string): Promise<unknown> {
    // accountId === site_id; userId is always {accountId}-admin for media library reads.
    // The injected script also tries to read these values from the tab URL as a
    // belt-and-suspenders fallback, but we supply them explicitly here.
    const res = await chrome.scripting.executeScript({
      target: { tabId },
      world: 'MAIN',
      func: getMediaFoldersInjected,
      args: [args.site_id, `${args.site_id}-admin`],
    })
    return res[0]?.result
  }
}
