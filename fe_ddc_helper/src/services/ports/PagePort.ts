import type {
  DDCWidgetSaveResult,
  PageLoadResult,
  PageStreamEvent,
  PageWidgetType,
  TranslatePageRequest,
} from '../../types'

/**
 * Port for the Spanish page-widget translation flow (004-translate-pages).
 *
 *   - `loadPage` and `saveWidget` run inside the active DDC composer tab via
 *     `chrome.scripting.executeScript`, reusing the user's session cookies.
 *   - `translatePageStream` streams NDJSON from the FastAPI backend.
 *
 * Per-widget retranslate reuses `LabelPort.translateLabel` — this port only
 * owns the page-specific DDC + streaming calls.
 */
export interface PagePort {
  /** Fetch one locale's rendered page HTML from DDC (injected script). */
  loadPage(targetPath: string, locale: 'en_US' | 'es_US'): Promise<PageLoadResult>

  /**
   * POST both renders to the backend and receive NDJSON events as they arrive.
   * Resolves when the stream ends (`done`/`error`) or the signal aborts.
   */
  translatePageStream(
    request: TranslatePageRequest,
    onEvent: (event: PageStreamEvent) => void,
    signal?: AbortSignal,
  ): Promise<void>

  /**
   * Save a widget: writes es_US, then re-writes the original en_US (DDC wipes
   * English otherwise). Endpoint + windowId-suffix rule depend on widgetType.
   */
  saveWidget(widget: {
    windowId: string
    widgetType: PageWidgetType
    enHtml: string
    esHtml: string
  }): Promise<DDCWidgetSaveResult>
}
