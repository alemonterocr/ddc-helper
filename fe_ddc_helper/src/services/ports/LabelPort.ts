import type {
  DDCLabelFetchResult,
  DDCLabelSaveResult,
  SanitizeAliasesResponse,
  TranslateLabelRequest,
  TranslateLabelResponse,
} from '../../types'

/**
 * Single port for the Spanish migration flow.
 *
 * Wraps both sides of the round-trip:
 *   - `sanitizeAliases` and `translateLabel` go to the FastAPI backend.
 *   - `fetchLabel` and `saveLabel` run inside the active DDC composer tab via
 *     `chrome.scripting.executeScript`, reusing the user's existing session
 *     cookies (no separate auth flow — same pattern as `CMSPort`).
 *
 * Keeping all four behind one port (rather than reusing `BackendPort` for the
 * BE half) makes the workflow easier to swap or mock, and the DDC calls are
 * cohesive with the BE ones at the use-case layer.
 */
export interface LabelPort {
  sanitizeAliases(raw: string): Promise<SanitizeAliasesResponse>

  translateLabel(
    request: TranslateLabelRequest,
    signal?: AbortSignal,
  ): Promise<TranslateLabelResponse>

  /** Read the current en_US / es_US values for one label from DDC. */
  fetchLabel(dealerSlug: string, alias: string): Promise<DDCLabelFetchResult>

  /** Persist both en_US and es_US for one label back to DDC. */
  saveLabel(
    dealerSlug: string,
    alias: string,
    enHtml: string,
    esHtml: string,
  ): Promise<DDCLabelSaveResult>
}
