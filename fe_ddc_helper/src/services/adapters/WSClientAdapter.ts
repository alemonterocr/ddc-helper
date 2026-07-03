/// <reference types="chrome" />
import { toolRegistry } from '../tools'
import { log } from '../../log'

const TOKEN_KEY = 'ccIdtToken'

interface ToolCallMessage {
  type: 'tool_call'
  id: string
  tool: string
  args: Record<string, unknown>
}

interface ToolResultMessage {
  type: 'tool_result'
  id: string
  ok: boolean
  result?: unknown
  error?: string
}

interface ProgressMessage {
  type: 'progress'
  message: string
}

type InboundMessage = ToolCallMessage | ProgressMessage

export class WSClientAdapter {
  private ws: WebSocket | null = null
  private readonly baseWsUrl: string

  constructor() {
    const http = import.meta.env.VITE_BACKEND_URL ?? 'http://localhost:8000'
    this.baseWsUrl = http.replace(/^http/, 'ws')
  }

  connect(dealerId: string, onProgress?: (message: string) => void): Promise<void> {
    return new Promise((resolve, reject) => {
      const ws = new WebSocket(`${this.baseWsUrl}/ws/${dealerId}`)

      ws.onopen = () => {
        this.ws = ws
        resolve()
      }

      ws.onerror = () => reject(new Error('WebSocket connection failed'))

      ws.onmessage = async (event: MessageEvent) => {
        try {
          const msg = JSON.parse(event.data as string) as InboundMessage
          if (msg.type === 'tool_call') {
            await this._handleToolCall(msg)
          } else if (msg.type === 'progress') {
            onProgress?.(msg.message)
          }
        } catch (err) {
          log.error('WSClient: failed to handle inbound message', err)
        }
      }
    })
  }

  disconnect(): void {
    this.ws?.close()
    this.ws = null
  }

  private async _handleToolCall(msg: ToolCallMessage): Promise<void> {
    let result: unknown
    let ok = true
    let error: string | undefined

    try {
      result = await this._dispatch(msg.tool, msg.args)
    } catch (err) {
      ok = false
      error = err instanceof Error ? err.message : String(err)
    }

    this._send({ type: 'tool_result', id: msg.id, ok, result, error })
  }

  private async _findCmsTab(): Promise<chrome.tabs.Tab> {
    const tabs = await chrome.tabs.query({ url: '*://*.website.dealercenter.coxautoinc.com/*' })
    const tab  = tabs.find(t => t.id)
    if (tab) return tab

    // Fallback: any active http/https tab (avoids picking up the extension popup)
    const activeTabs = await chrome.tabs.query({ active: true })
    const httpTab = activeTabs.find(t => t.url?.startsWith('http') && t.id)
    if (httpTab) return httpTab

    throw new Error('No CMS tab found — open the DDC composer in a browser tab first')
  }

  private async _findMediaLibTab(): Promise<chrome.tabs.Tab> {
    // The medialibrary-services API rejects requests whose Referer is not the
    // medialibrary page itself (403 with no body). We MUST inject from the
    // tab that's actually on medialibrary3/index, not just any tab on
    // apps.dealercenter.coxautoinc.com — users often have a Dealer Center tab
    // open too (we link to it from GMSetupBlock), and Chrome can return that
    // one first from a broad query.
    const mediaLibTabs = await chrome.tabs.query({
      url: '*://apps.dealercenter.coxautoinc.com/promotions/as/*/*/medialibrary*/*',
    })
    const tab = mediaLibTabs.find(t => t.id)
    if (tab) return tab

    // Diagnostic fallback: if nothing matched, surface what tabs WERE open on
    // the origin so the error is actionable.
    const fallback = await chrome.tabs.query({ url: '*://apps.dealercenter.coxautoinc.com/*' })
    const urls = fallback.map(t => t.url).filter(Boolean).join(', ')
    throw new Error(
      urls
        ? `No Media Library tab found. Open the Media Library page (medialibrary3/index) and log in. Tabs currently on apps.dealercenter.coxautoinc.com: ${urls}`
        : 'No Media Library tab found. Open apps.dealercenter.coxautoinc.com Media Library and log in first.',
    )
  }

  private async _findSalesforceTab(): Promise<chrome.tabs.Tab> {
    const tabs = await chrome.tabs.query({ url: '*://casfx.lightning.force.com/*' })
    const tab  = tabs.find(t => t.id)
    if (!tab) {
      throw new Error(
        'No Salesforce tab found — open the Board link in Salesforce and log in first'
      )
    }
    return tab
  }

  private async _dispatch(toolName: string, args: Record<string, unknown>): Promise<unknown> {
    const tool = toolRegistry.get(toolName)
    if (!tool) throw new Error(`Unknown tool: ${toolName}`)

    let tab: chrome.tabs.Tab
    if (tool.domain === 'media_lib') {
      tab = await this._findMediaLibTab()
    } else if (tool.domain === 'salesforce') {
      tab = await this._findSalesforceTab()
    } else {
      tab = await this._findCmsTab()
    }

    if (!tab?.id) throw new Error(`No tab found for domain '${tool.domain}'`)

    const storage = await chrome.storage.local.get([TOKEN_KEY])
    const token   = (storage[TOKEN_KEY] as string) ?? ''

    return tool.execute(args as never, tab.id, token)
  }

  private _send(msg: ToolResultMessage): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg))
    }
  }
}
