import type {
  DDCWidgetSaveResult,
  PageLoadResult,
  PageStreamEvent,
  PageWidgetType,
  TranslatePageRequest,
} from '../../types'
import type { PagePort } from '../ports/PagePort'
import { extractUserId, findComposerTabId } from './ddcTab'

/**
 * Concrete PagePort (004-translate-pages).
 *
 * DDC calls (render GET, widget saves) run via `chrome.scripting.executeScript`
 * into the composer tab; the injected functions are fully self-contained per
 * the `scripts/` rule. The translate stream is plain `fetch` NDJSON against the
 * backend (`VITE_BACKEND_URL`), same base-URL convention as `LabelAdapter`.
 */
export class PageAdapter implements PagePort {
  private readonly baseUrl: string

  constructor() {
    this.baseUrl = import.meta.env.VITE_BACKEND_URL ?? 'http://localhost:8000'
  }

  // ── DDC render (read) ─────────────────────────────────────────────────────

  async loadPage(
    targetPath: string,
    locale: 'en_US' | 'es_US',
  ): Promise<PageLoadResult> {
    let tabId: number
    try {
      tabId = await findComposerTabId()
    } catch (err) {
      return { html: null, error: (err as Error).message }
    }

    const results = await chrome.scripting.executeScript({
      target: { tabId },
      func: loadPageInjected,
      args: [targetPath, locale],
    })

    return results[0]?.result ?? { html: null, error: 'No result from script' }
  }

  // ── Backend NDJSON stream ─────────────────────────────────────────────────

  async translatePageStream(
    request: TranslatePageRequest,
    onEvent: (event: PageStreamEvent) => void,
    signal?: AbortSignal,
  ): Promise<void> {
    let response: Response
    try {
      response = await fetch(`${this.baseUrl}/translations/translate-page`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
        signal,
      })
    } catch (err) {
      if ((err as Error).name === 'AbortError') return
      onEvent({ type: 'error', message: (err as Error).message })
      return
    }

    if (!response.ok || !response.body) {
      onEvent({ type: 'error', message: `Request failed (${response.status})` })
      return
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    const emitLine = (line: string) => {
      const trimmed = line.trim()
      if (!trimmed) return
      try {
        onEvent(JSON.parse(trimmed) as PageStreamEvent)
      } catch {
        /* ignore a malformed line rather than kill the whole stream */
      }
    }

    try {
      for (;;) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        let newlineIndex = buffer.indexOf('\n')
        while (newlineIndex >= 0) {
          emitLine(buffer.slice(0, newlineIndex))
          buffer = buffer.slice(newlineIndex + 1)
          newlineIndex = buffer.indexOf('\n')
        }
      }
      emitLine(buffer) // any trailing partial line
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        onEvent({ type: 'error', message: (err as Error).message })
      }
    }
  }

  // ── DDC widget save (two-save dance) ──────────────────────────────────────

  async saveWidget(widget: {
    windowId: string
    widgetType: PageWidgetType
    enHtml: string
    esHtml: string
  }): Promise<DDCWidgetSaveResult> {
    let tabId: number
    try {
      tabId = await findComposerTabId()
    } catch (err) {
      return { success: false, error: (err as Error).message }
    }

    const storage = await chrome.storage.local.get(['ccIdtToken'])
    const userId = extractUserId((storage['ccIdtToken'] as string) ?? '')

    const results = await chrome.scripting.executeScript({
      target: { tabId },
      func: saveWidgetInjected,
      args: [widget.windowId, widget.widgetType, widget.enHtml, widget.esHtml, userId],
    })

    return results[0]?.result ?? { success: false, error: 'No result from script' }
  }
}

// ── Injected functions — self-contained, zero imports ────────────────────────

/**
 * GET the fully rendered page for one locale from the site host. Runs inside
 * the composer tab so it inherits the user's session cookies. Returns the raw
 * HTML string (the BE parses it).
 */
async function loadPageInjected(
  targetPath: string,
  locale: string,
): Promise<PageLoadResult> {
  const url =
    `https://${window.location.hostname}${targetPath}` +
    `?_renderer=desktop&buildingPage=false&useAjaxWrap=true` +
    `&locale=${locale}&_toggleBasePageCache=false`

  try {
    const response = await fetch(url, {
      method: 'GET',
      credentials: 'include',
      headers: {
        accept: 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
      },
    })
    if (!response.ok) {
      return { html: null, error: `Status: ${response.status}` }
    }
    return { html: await response.text() }
  } catch (err) {
    return { html: null, error: (err as Error).message }
  }
}

/**
 * Save one widget's Spanish then re-save its original English. Content widgets
 * use the SaveContent command (windowId keeps -editable); RAW widgets use the
 * sitecontent endpoint (windowId strips -editable). If the Spanish write fails,
 * the English write is skipped so we never clobber English with nothing.
 */
async function saveWidgetInjected(
  windowId: string,
  widgetType: string,
  enHtml: string,
  esHtml: string,
  userId: string,
): Promise<DDCWidgetSaveResult> {
  const host = window.location.hostname
  const slug = host.split('.')[0] || ''
  const apiBase = `https://${host}/cc-website/as/${slug}/${slug}-admin/cms-configurator/api`

  async function saveContentWidget(locale: string, content: string): Promise<boolean> {
    const url = `${apiBase}/commandExecutor/${slug}?cmd=SaveContent`
    const body = {
      javaClass: 'com.dealer.composer.commands.SaveContent',
      siteId: slug,
      windowId: windowId,
      currentLocale: locale,
      content: content,
      accountId: slug,
      userId: userId,
      siteType: 'primary',
    }
    const response = await fetch(url, {
      method: 'POST',
      credentials: 'include',
      headers: {
        accept: '*/*',
        'content-type': 'application/json; charset=UTF-8',
        'x-coxauto-traffic-group': 'composer-dynamic-request',
      },
      body: JSON.stringify(body),
    })
    return response.ok
  }

  async function saveRawWidget(locale: string, content: string): Promise<boolean> {
    const strippedId = windowId.endsWith('-editable')
      ? windowId.slice(0, -'-editable'.length)
      : windowId
    const url = `${apiBase}/sites/${slug}/sitecontent?windowId=${encodeURIComponent(strippedId)}`
    const response = await fetch(url, {
      method: 'POST',
      credentials: 'include',
      headers: {
        accept: '*/*',
        'content-type': 'application/json',
        'x-coxauto-traffic-group': 'composer-dynamic-request',
      },
      body: JSON.stringify({ [locale]: content }),
    })
    return response.ok
  }

  const saveOne = widgetType === 'raw' ? saveRawWidget : saveContentWidget

  try {
    const spanishOk = await saveOne('es_US', esHtml)
    if (!spanishOk) {
      return { success: false, error: 'Spanish save failed — English left intact' }
    }
    const englishOk = await saveOne('en_US', enHtml)
    if (!englishOk) {
      return { success: false, error: 'English re-save failed' }
    }
    return { success: true }
  } catch (err) {
    return { success: false, error: (err as Error).message }
  }
}
