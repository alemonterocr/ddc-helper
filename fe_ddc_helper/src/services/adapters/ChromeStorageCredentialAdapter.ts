import type { CredentialStatus, LLMProvider } from '../../types'
import type { CredentialPort } from '../ports/CredentialPort'
import { credentialService } from '../credentialService'

const TOKEN_KEY = 'ccIdtToken'
const LLM_PROVIDER_KEY = 'llmProvider'
const LLM_API_KEY = 'llmApiKey'

export class ChromeStorageCredentialAdapter implements CredentialPort {
  async getStatus(): Promise<CredentialStatus> {
    return credentialService.check()
  }

  async getToken(): Promise<string> {
    const storage = await chrome.storage.local.get([TOKEN_KEY])
    if (!storage[TOKEN_KEY]) throw new Error('CC-IDT token not found in storage')
    return storage[TOKEN_KEY] as string
  }

  async getStoredProvider(): Promise<LLMProvider | null> {
    const storage = await chrome.storage.local.get([LLM_PROVIDER_KEY])
    return (storage[LLM_PROVIDER_KEY] as LLMProvider) ?? null
  }

  async markLLMKeyConfigured(provider: LLMProvider, apiKey: string): Promise<void> {
    await chrome.storage.local.set({ [LLM_PROVIDER_KEY]: provider, [LLM_API_KEY]: apiKey })
  }

  async getStoredApiKey(): Promise<{ provider: LLMProvider; apiKey: string } | null> {
    const storage = await chrome.storage.local.get([LLM_PROVIDER_KEY, LLM_API_KEY])
    const provider = storage[LLM_PROVIDER_KEY] as LLMProvider | undefined
    const apiKey   = storage[LLM_API_KEY]   as string | undefined
    if (!provider || !apiKey) return null
    return { provider, apiKey }
  }
}
