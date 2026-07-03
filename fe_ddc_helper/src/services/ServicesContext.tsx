/**
 * The composition root for service ports.
 *
 * `App.tsx` instantiates all concrete adapters once at startup and passes
 * them through this context. Pages read the ports they need via
 * `useServices()` and forward them down to organisms as props. Organisms
 * never import concrete adapters — they only ever see the port interface.
 *
 * Adapters are split into two categories:
 *   - Stateless singletons (backend, cms, credentials, extractor) are
 *     created once at startup and shared across the app.
 *   - WSClient is per-operation: each analyze/execute cycle needs a fresh
 *     connection lifecycle, so the context exposes a factory
 *     (`createWSClient`) rather than a single instance.
 */

import { createContext, useContext, type ReactNode } from 'react'
import type {
  BackendPort,
  CMSPort,
  CredentialPort,
  DOMExtractorPort,
  LabelPort,
  WSClientPort,
} from './ports'

/** The full bundle of ports the app exposes via context. */
export interface Services {
  backendPort: BackendPort
  cmsPort: CMSPort
  credentialPort: CredentialPort
  extractorPort: DOMExtractorPort
  labelPort: LabelPort
  /** Per-operation factory — call to create a fresh WS connection wrapper. */
  createWSClient: () => WSClientPort
}

const ServicesContext = createContext<Services | null>(null)

interface ServicesProviderProps {
  services: Services
  children: ReactNode
}

export function ServicesProvider({ services, children }: ServicesProviderProps) {
  return (
    <ServicesContext.Provider value={services}>
      {children}
    </ServicesContext.Provider>
  )
}

/**
 * Access the app's service ports.
 *
 * @throws Error when called outside a `<ServicesProvider>` — indicates a
 *         setup mistake at the composition root, never a runtime case
 *         consumers should handle.
 */
export function useServices(): Services {
  const ctx = useContext(ServicesContext)
  if (!ctx) {
    throw new Error(
      'useServices must be used within a <ServicesProvider>. ' +
        'Wrap your app tree at the composition root.',
    )
  }
  return ctx
}
