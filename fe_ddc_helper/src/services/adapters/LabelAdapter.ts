import type {
  DDCLabelFetchResult,
  DDCLabelSaveResult,
  NavCheckRequest,
  NavCheckResponse,
  NavLoadResult,
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

  async navCheck(request: NavCheckRequest): Promise<NavCheckResponse> {
    return this.post<NavCheckResponse>('/translations/nav-check', request)
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

  async loadNav(): Promise<NavLoadResult> {
    let tabId: number
    try {
      tabId = await findComposerTabId()
    } catch (err) {
      return { items: [], raw: null, error: (err as Error).message }
    }

    const storage = await chrome.storage.local.get(['ccIdtToken'])
    const jwt = (storage['ccIdtToken'] as string) ?? ''
    const userId = _extractUserId(jwt)

    const results = await chrome.scripting.executeScript({
      target: { tabId },
      func: loadNavInjected,
      args: [userId],
    })

    return results[0]?.result ?? { items: [], raw: null, error: 'No result from script' }
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

// ── Helpers ───────────────────────────────────────────────────────────────────

function _extractUserId(jwt: string): string {
  try {
    const base64 = jwt.split('.')[1]?.replace(/-/g, '+').replace(/_/g, '/')
    if (!base64) return ''
    const claims = JSON.parse(atob(base64)) as Record<string, unknown>
    return (claims['sub'] as string) ?? ''
  } catch {
    return ''
  }
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

/**
 * POST /composer/views/CommandExecutor?cmd=LoadNavigation with es_US locale.
 * userId comes from the FE side (extracted from JWT). navId is discovered from
 * page state or via a preferences call.
 */
async function loadNavInjected(
  userId: string,
): Promise<NavLoadResult> {
  async function discoverNavId(): Promise<string> {
    let pageUrl = `https://${window.location.hostname}/?_renderer=desktop&buildingPage=false&useAjaxWrap=true&locale=es_US&_toggleBasePageCache=false`;
    try {
      let res = await fetch(pageUrl, {
        method: 'GET',
        credentials: 'include',
        headers: {
          accept: 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        },
      });
      if (!res.ok) return '';
      let text = await res.text();
      let match = text.match(/"navigation\.id"\s*:\s*"([^"]+)"/);
      if (match?.[1]) return match[1];
    } catch (_) { /* page fetch may fail */ }
    return '';
  }

  function extractItems(dto: Record<string, unknown>): { alias: string; label_es: string }[] {
    let result: { alias: string; label_es: string }[] = [];
    let navItems = dto.navigationItems as Record<string, unknown> | undefined;
    if (!navItems) { return result; }
    let list = navItems.list as Array<Record<string, unknown>> | undefined;
    if (!list) { return result; }

    function walk(items: Array<Record<string, unknown>>) {
      for (let i = 0; i < items.length; i++) {
        let item = items[i];
        if (!item) continue;
        let alias = (item.labelAlias as string || '').trim();
        let label = (item.label as string || '').trim();
        if (alias) {
          result.push({ alias: alias, label_es: label });
        }
        let children = item.navigationItems as Record<string, unknown> | undefined;
        if (children) {
          let childList = children.list as Array<Record<string, unknown>> | undefined;
          if (childList) { walk(childList); }
        }
      }
    }

    walk(list);
    return result;
  }

  let navId = await discoverNavId();

  let siteId = window.location.hostname.split('.')[0] || '';

  if (!userId) {
    return { items: [], raw: null, error: 'No userId available' };
  }
  if (!navId) {
    return { items: [], raw: null, error: 'Could not discover navId from page context' };
  }

  let url = `https://${window.location.hostname}/composer/views/CommandExecutor?cmd=LoadNavigation`;

  let payload = {
    javaClass: 'com.dealer.cms.apps.composer.commands.nav.LoadNavigation',
    navId: navId,
    siteId: siteId,
    locale: 'es_US',
    accountId: siteId,
    userId: userId,
    siteType: 'primary',
  };

  try {
    let res = await fetch(url, {
      method: 'POST',
      credentials: 'include',
      headers: {
        accept: '*/*',
        'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'x-coxauto-traffic-group': 'composer-dynamic-request',
        'x-requested-with': 'XMLHttpRequest',
      },
      body: `json=${encodeURIComponent(JSON.stringify(payload))}`,
    });

    if (!res.ok) {
      return { items: [], raw: null, error: `Status: ${res.status}` };
    }

    let data = await res.json() as Record<string, unknown>;
    let result = data.result as Record<string, unknown> | undefined;
    let dto = result?.dto as Record<string, unknown> | undefined;
    if (!dto) {
      let resultNavId = (result?.navId as string) || '';
      return {
        items: [], raw: null,
        error: `Nav '${resultNavId}' returned no data for dealer '${siteId}'. Make sure the composer tab matches this project's dealer.`,
      };
    }

    return { items: extractItems(dto), raw: data };
  } catch (err) {
    return { items: [], raw: null, error: (err as Error).message };
  }
}
