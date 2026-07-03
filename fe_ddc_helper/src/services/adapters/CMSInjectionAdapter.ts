import type { CMSPort, SectionInjectionResult } from '../ports/CMSPort'

export class CMSInjectionAdapter implements CMSPort {
  async injectSection(
    dealerId: string,
    token: string,
    pageAlias: string,
    sectionType: string,
  ): Promise<SectionInjectionResult> {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
    if (!tab?.id) return { success: false, error: 'No active tab found' }

    const results = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: injectSectionInjected,
      args: [dealerId, token, pageAlias, sectionType],
    })

    return results[0]?.result ?? { success: false, error: 'No result from script' }
  }
}

/**
 * Self-contained — injected into the active DDC CMS tab.
 * Zero imports, zero external closures.
 */
async function injectSectionInjected(
  siteId: string,
  token: string,
  pageAlias: string,
  sectionType: string,
): Promise<SectionInjectionResult> {
  const url = [
    `https://${window.location.hostname}`,
    `cc-website/as/${siteId}/${siteId}-admin`,
    `cms-configurator/api/pages/${siteId}/alias/${pageAlias}/section/0`,
  ].join('/')

  try {
    const response = await fetch(url, {
      method: 'POST',
      credentials: 'include',
      headers: {
        accept: '*/*',
        authorization: token,
        'cache-control': 'no-cache',
        'content-type': 'application/json',
        'x-coxauto-traffic-group': 'composer-dynamic-request',
      },
      body: JSON.stringify({ version: 1, sectionType }),
    })

    if (response.ok) return { success: true }
    return { success: false, error: `Status: ${response.status}` }
  } catch (err) {
    return { success: false, error: (err as Error).message }
  }
}
