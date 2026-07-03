import type {
  DDCLabelFetchResult,
  DDCLabelSaveResult,
  SanitizeAliasesRequest,
  SanitizeAliasesResponse,
  TranslateLabelRequest,
  TranslateLabelResponse,
} from '../../types'
import { BackendError } from '../../types'
import type { LabelPort } from '../ports/LabelPort'

/**
 * Concrete LabelPort.
 *
 * BE calls go via `fetch` against `VITE_BACKEND_URL` (same convention as
 * `BackendHttpAdapter`). DDC calls go via `chrome.scripting.executeScript`
 * into the active composer tab — the injected functions are fully
 * self-contained (no closures, no external imports) per the project's
 * `scripts/` rule.
 */
export class LabelAdapter implements LabelPort {
  private readonly baseUrl: string

  constructor() {
    this.baseUrl = import.meta.env.VITE_BACKEND_URL ?? 'http://localhost:8000'
  }

  // ── BE ──────────────────────────────────────────────────────────────────

  async sanitizeAliases(raw: string): Promise<SanitizeAliasesResponse> {
    const body: SanitizeAliasesRequest = { raw }
    return this.post<SanitizeAliasesResponse>('/translations/sanitize', body)
  }

  async translateLabel(
    request: TranslateLabelRequest,
    signal?: AbortSignal,
  ): Promise<TranslateLabelResponse> {
    return this.post<TranslateLabelResponse>('/translations/translate', request, signal)
  }

  // ── DDC ─────────────────────────────────────────────────────────────────

  async fetchLabel(dealerSlug: string, alias: string): Promise<DDCLabelFetchResult> {
    let tabId: number
    try {
      tabId = await findComposerTabId()
    } catch (err) {
      return { en: null, es: null, error: (err as Error).message }
    }

    const results = await chrome.scripting.executeScript({
      target: { tabId },
      func: fetchLabelInjected,
      args: [dealerSlug, alias],
    })

    return results[0]?.result ?? { en: null, es: null, error: 'No result from script' }
  }

  async saveLabel(
    dealerSlug: string,
    alias: string,
    enHtml: string,
    esHtml: string,
  ): Promise<DDCLabelSaveResult> {
    let tabId: number
    try {
      tabId = await findComposerTabId()
    } catch (err) {
      return { success: false, error: (err as Error).message }
    }

    const results = await chrome.scripting.executeScript({
      target: { tabId },
      func: saveLabelInjected,
      args: [dealerSlug, alias, enHtml, esHtml],
    })

    return results[0]?.result ?? { success: false, error: 'No result from script' }
  }

  // ── HTTP helper ─────────────────────────────────────────────────────────

  private async post<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal,
    })

    if (!response.ok) {
      throw new BackendError(`Request to ${path} failed`, response.status)
    }

    return response.json() as Promise<T>
  }
}

// ── Composer tab lookup ──────────────────────────────────────────────────────

/**
 * Find the DDC composer tab by URL pattern, not by "active tab in current
 * window" — the latter breaks when the extension page itself is in the
 * foreground (e.g. opened as a standalone tab/window), which produces:
 * `Cannot access contents of url "chrome-extension://...". Extension manifest
 * must request permission to access this host.`
 *
 * Mirrors the lookup used by WSClientAdapter._findCmsTab.
 */
async function findComposerTabId(): Promise<number> {
  const tabs = await chrome.tabs.query({
    url: '*://*.website.dealercenter.coxautoinc.com/*',
  })
  const composer = tabs.find((t) => t.id !== undefined)
  if (composer?.id !== undefined) return composer.id

  throw new Error(
    'No DDC composer tab found — open the composer in a browser tab first',
  )
}

// ── Injected functions — self-contained, zero imports ────────────────────────

/**
 * GET /cc-website/as/{slug}/{slug}-admin/cms-configurator/api/labels/{slug}?alias={alias}
 * Runs inside the active composer tab so it inherits the user's session cookies.
 * Response shape: { en_US: { ALIAS: "..." }, es_US: { ALIAS: "..." } }
 */
async function fetchLabelInjected(
  dealerSlug: string,
  alias: string,
): Promise<DDCLabelFetchResult> {
  const url = [
    `https://${window.location.hostname}`,
    `cc-website/as/${dealerSlug}/${dealerSlug}-admin`,
    `cms-configurator/api/labels/${dealerSlug}?alias=${encodeURIComponent(alias)}`,
  ].join('/')

  try {
    const response = await fetch(url, {
      method: 'GET',
      credentials: 'include',
      headers: {
        accept: '*/*',
        'cache-control': 'no-cache',
        'content-type': 'application/json',
        'x-coxauto-traffic-group': 'composer-dynamic-request',
      },
    })

    if (!response.ok) {
      return { en: null, es: null, error: `Status: ${response.status}` }
    }

    const data = (await response.json()) as {
      en_US?: Record<string, string>
      es_US?: Record<string, string>
    }
    return {
      en: data.en_US?.[alias] ?? null,
      es: data.es_US?.[alias] ?? null,
    }
  } catch (err) {
    return { en: null, es: null, error: (err as Error).message }
  }
}

/**
 * POST /cc-website/as/{slug}/{slug}-admin/cms-configurator/api/labels/{slug}/{alias}
 * Body: { labelToSave: { en_US: "...", es_US: "..." } }. Empty {} on success.
 */
async function saveLabelInjected(
  dealerSlug: string,
  alias: string,
  enHtml: string,
  esHtml: string,
): Promise<DDCLabelSaveResult> {
  const url = [
    `https://${window.location.hostname}`,
    `cc-website/as/${dealerSlug}/${dealerSlug}-admin`,
    `cms-configurator/api/labels/${dealerSlug}/${encodeURIComponent(alias)}`,
  ].join('/')

  try {
    const response = await fetch(url, {
      method: 'POST',
      credentials: 'include',
      headers: {
        accept: '*/*',
        'cache-control': 'no-cache',
        'content-type': 'application/json',
        'x-coxauto-traffic-group': 'composer-dynamic-request',
      },
      body: JSON.stringify({ labelToSave: { en_US: enHtml, es_US: esHtml } }),
    })

    if (response.ok) return { success: true }
    return { success: false, error: `Status: ${response.status}` }
  } catch (err) {
    return { success: false, error: (err as Error).message }
  }
}
