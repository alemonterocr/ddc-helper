/// <reference types="chrome" />
import type { CredentialStatus, LLMProvider } from '../types'

const TOKEN_KEY = 'ccIdtToken'
const LLM_PROVIDER_KEY = 'llmProvider'

function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const jwt = token.startsWith('CC-IDT ') ? token.slice(7) : token
    const parts = jwt.split('.')
    const payload = parts[1]
    if (!payload) return null
    const padded = payload.replace(/-/g, '+').replace(/_/g, '/')
    return JSON.parse(atob(padded))
  } catch {
    return null
  }
}

export const credentialService = {
  async check(): Promise<CredentialStatus> {
    const storage = await chrome.storage.local.get([TOKEN_KEY, LLM_PROVIDER_KEY])
    const missing: string[] = []

    const ccIdtToken = (storage[TOKEN_KEY] as string) ?? null
    if (!ccIdtToken) missing.push('CC-IDT token missing — click any widget in DDC CMS first')

    const payload = ccIdtToken ? decodeJwtPayload(ccIdtToken) : null
    const createdBy = payload
      ? ((payload.sub as string) ?? (payload.aid as string) ?? null)
      : null

    const llmProvider = (storage[LLM_PROVIDER_KEY] as LLMProvider) ?? null
    const hasLLMKey = Boolean(llmProvider)
    if (!hasLLMKey) missing.push('LLM API key not configured — add one below')

    const { mediaLibTabId } = await credentialService.recheckMediaLibTab()

    return {
      ready: missing.length === 0,
      ccIdtToken,
      createdBy,
      hasLLMKey,
      llmProvider,
      mediaLibTabId,
      missing,
    }
  },

  async recheckCcIdt(): Promise<{ ccIdtToken: string | null; createdBy: string | null }> {
    const storage = await chrome.storage.local.get([TOKEN_KEY])
    const ccIdtToken = (storage[TOKEN_KEY] as string) ?? null
    const payload = ccIdtToken ? decodeJwtPayload(ccIdtToken) : null
    const createdBy = payload
      ? ((payload.sub as string) ?? (payload.aid as string) ?? null)
      : null
    return { ccIdtToken, createdBy }
  },

  async recheckLlmKey(): Promise<{ hasLLMKey: boolean; llmProvider: LLMProvider | null }> {
    const storage = await chrome.storage.local.get([LLM_PROVIDER_KEY])
    const llmProvider = (storage[LLM_PROVIDER_KEY] as LLMProvider) ?? null
    return { hasLLMKey: Boolean(llmProvider), llmProvider }
  },

  async recheckMediaLibTab(): Promise<{ mediaLibTabId: number | null; jwtOk: boolean }> {
    const allTabs  = await chrome.tabs.query({})
    const mediaTab = allTabs.find(t => t.url?.includes('apps.dealercenter.coxautoinc.com'))
    if (!mediaTab?.id) return { mediaLibTabId: null, jwtOk: false }
    const jwtAuth = await chrome.cookies.get({ url: mediaTab.url!, name: 'JWTAuth' })
    return { mediaLibTabId: mediaTab.id, jwtOk: !!jwtAuth }
  },
}
