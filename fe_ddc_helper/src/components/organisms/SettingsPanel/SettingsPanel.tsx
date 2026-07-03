import { useState } from 'react'
import type { CredentialStatus } from '../../../types'
import type { BackendPort } from '../../../services/ports/BackendPort'
import type { CredentialPort } from '../../../services/ports/CredentialPort'
import { credentialService } from '../../../services/credentialService'
import { log } from '../../../log'
import { CredentialChecker } from '../../molecules/CredentialChecker/CredentialChecker'

interface SettingsPanelProps {
  backendPort: BackendPort
  credentialPort: CredentialPort
  /**
   * Whether to include the Media Library check. Defaults to true. Spanish
   * translation projects don't upload images, so they pass false.
   */
  includeMediaLib?: boolean
}

export function SettingsPanel({ backendPort, credentialPort, includeMediaLib = true }: SettingsPanelProps) {
  const [credentials, setCredentials] = useState<CredentialStatus | null>(null)
  const [checking, setChecking] = useState(false)
  const [checkError, setCheckError] = useState<string | undefined>()
  const [refreshing, setRefreshing] = useState<'ccIdt' | 'llmKey' | 'mediaLib' | null>(null)

  async function handleCheck() {
    setChecking(true)
    setCheckError(undefined)
    try {
      const stored = await credentialPort.getStoredApiKey()
      if (stored) {
        // Best-effort re-push of the API key — backend is stateless and loses
        // it on restart, but the credential check should still proceed if the
        // re-push fails (e.g. backend isn't running yet).
        await backendPort
          .configureApiKey({ provider: stored.provider, api_key: stored.apiKey })
          .catch(err => log.warn('Failed to re-push API key to backend; continuing credential check', { errorMessage: err instanceof Error ? err.message : String(err) }))
      }
      setCredentials(await credentialService.check())
    } catch (err) {
      setCheckError(err instanceof Error ? err.message : 'Failed to read credentials')
    } finally {
      setChecking(false)
    }
  }

  async function handleRefreshCcIdt() {
    setRefreshing('ccIdt')
    try {
      const { ccIdtToken, createdBy } = await credentialService.recheckCcIdt()
      setCredentials(prev => {
        if (!prev) return prev
        const missing = prev.missing.filter(m => !m.includes('CC-IDT'))
        if (!ccIdtToken) missing.push('CC-IDT token missing — click any widget in DDC CMS first')
        return { ...prev, ccIdtToken, createdBy, ready: missing.length === 0, missing }
      })
    } finally {
      setRefreshing(null)
    }
  }

  async function handleRefreshLlmKey() {
    setRefreshing('llmKey')
    try {
      const { hasLLMKey, llmProvider } = await credentialService.recheckLlmKey()
      setCredentials(prev => {
        if (!prev) return prev
        const missing = prev.missing.filter(m => !m.includes('LLM API key'))
        if (!hasLLMKey) missing.push('LLM API key not configured — add one on the home screen')
        return { ...prev, hasLLMKey, llmProvider, ready: missing.length === 0, missing }
      })
    } finally {
      setRefreshing(null)
    }
  }

  async function handleRefreshMediaLib() {
    setRefreshing('mediaLib')
    try {
      const { mediaLibTabId, jwtOk } = await credentialService.recheckMediaLibTab()
      setCredentials(prev => {
        if (!prev) return prev
        return { ...prev, mediaLibTabId: jwtOk ? mediaLibTabId : null }
      })
    } finally {
      setRefreshing(null)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <CredentialChecker
        credentials={credentials}
        checking={checking}
        refreshing={refreshing}
        onCheck={handleCheck}
        onRefreshCcIdt={handleRefreshCcIdt}
        onRefreshLlmKey={handleRefreshLlmKey}
        onRefreshMediaLib={handleRefreshMediaLib}
        includeMediaLib={includeMediaLib}
      />

      {checkError && (
        <p className="text-xs text-destructive font-mono px-1">⚠ {checkError}</p>
      )}
    </div>
  )
}
