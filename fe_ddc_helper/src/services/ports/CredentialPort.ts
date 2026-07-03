import type { CredentialStatus, LLMProvider } from '../../types'

export interface CredentialPort {
  getStatus(): Promise<CredentialStatus>
  getToken(): Promise<string>
  getStoredProvider(): Promise<LLMProvider | null>
  /** Persist both provider name AND the raw API key to chrome.storage. */
  markLLMKeyConfigured(provider: LLMProvider, apiKey: string): Promise<void>
  /** Return the stored provider + key, or null if never configured. */
  getStoredApiKey(): Promise<{ provider: LLMProvider; apiKey: string } | null>
}
