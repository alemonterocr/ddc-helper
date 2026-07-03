/// <reference types="chrome" />
import { sfUiApiGetInjected, type SfUiApiGetResult } from '../../scripts/salesforceTools'
import type { ICmsTool } from './ICmsTool'

interface SfUiApiGetArgs {
  path: string
}

/**
 * Backend-driven Salesforce UI API GET.
 *
 * Backend builds the full UI API path (e.g.
 * `/services/data/v66.0/ui-api/records/{id}?fields=...`); we just dispatch
 * the fetch from the Lightning origin so cookies + same-origin policy work.
 *
 * Returns the SfUiApiGetResult untouched - the backend orchestrator owns the
 * field-extraction logic (see `application/salesforce/sf_uiapi_client.py`).
 */
export class SfUiApiGetTool implements ICmsTool<SfUiApiGetArgs, SfUiApiGetResult> {
  readonly name   = 'sf_ui_api_get'
  readonly domain = 'salesforce' as const

  async execute(args: SfUiApiGetArgs, tabId: number, _token: string): Promise<SfUiApiGetResult> {
    const res = await chrome.scripting.executeScript({
      target: { tabId },
      world: 'MAIN',
      func: sfUiApiGetInjected,
      args: [args.path],
    })
    const out = res[0]?.result
    if (!out) {
      return { ok: false, status: 0, error: 'sf_ui_api_get injection returned no result' }
    }
    return out
  }
}
