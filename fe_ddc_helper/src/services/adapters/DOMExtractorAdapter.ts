import type { DOMSkeleton } from '../../types'
import { extractSkeleton } from '../../scripts/extractSkeleton'
import type { DOMExtractorPort } from '../ports/DOMExtractorPort'

const TAB_LOAD_TIMEOUT_MS = 60_000

function sanitizeUrl(raw: string): string {
  let url = raw.trim().replace(/^["']|["']$/g, "")
  if (!/^https?:\/\//i.test(url)) {
    throw new Error(`Invalid page URL: ${raw}`)
  }
  return url
}

export class DOMExtractorAdapter implements DOMExtractorPort {
  async extract(url: string, signal?: AbortSignal): Promise<DOMSkeleton> {
    const safeUrl = sanitizeUrl(url)
    const tab = await chrome.tabs.create({ url: safeUrl, active: false })
    const tabId = tab.id!

    try {
      await waitForTabComplete(tabId, signal)
      return await runExtractor(tabId)
    } finally {
      await chrome.tabs.remove(tabId)
    }
  }
}

function waitForTabComplete(tabId: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    let settled = false

    function settle(fn: () => void) {
      if (settled) return
      settled = true
      chrome.tabs.onUpdated.removeListener(onUpdated)
      signal?.removeEventListener('abort', onAbort)
      fn()
    }

    function onAbort() {
      settle(() => reject(new DOMException('Aborted', 'AbortError')))
    }

    const onUpdated: Parameters<typeof chrome.tabs.onUpdated.addListener>[0] =
      (id, info) => {
        if (id === tabId && info.status === 'complete') settle(resolve)
      }

    chrome.tabs.onUpdated.addListener(onUpdated)

    chrome.tabs.get(tabId, tab => {
      if (tab.status === 'complete') settle(resolve)
    })

    signal?.addEventListener('abort', onAbort)

    setTimeout(
      // On timeout, resolve anyway — the DOM is usually available even when
      // third-party scripts (chat, analytics, inventory widgets) haven't finished.
      () => settle(resolve),
      TAB_LOAD_TIMEOUT_MS,
    )
  })
}

async function runExtractor(tabId: number): Promise<DOMSkeleton> {
  const results = await chrome.scripting.executeScript({
    target: { tabId },
    func: extractSkeleton,
  })

  const result = results[0]?.result
  if (!result) throw new Error('Skeleton extractor returned no result')

  return result as DOMSkeleton
}
