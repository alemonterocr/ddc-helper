---
name: service-ports
type: port
status: built
---

## Purpose
TypeScript interfaces that define the service contracts. Organisms depend on
these — never on the adapters. Enables testing with mock implementations
and keeps the composition root the only place that knows about concrete
implementations.

## Contracts
- Pure TypeScript interfaces — no implementation, no imports beyond types
- Every method returns a Promise (all operations are async)
- Each port lives in its own file, re-exported from `index.ts`
- Naming: `XPort` for the interface; matching adapter is `XAdapter`

## Dependencies
- `types/` (request/response shapes shared with the BE)

## Ports

| Port | File | Methods |
|---|---|---|
| `BackendPort` | `BackendPort.ts` | `configureApiKey`, `analyzePage`, `analyzeDeterministic`, `executeMigration` |
| `CMSPort` | `CMSPort.ts` | `injectSection` (returns `SectionInjectionResult`) |
| `CredentialPort` | `CredentialPort.ts` | `getStoredApiKey`, `markLLMKeyConfigured` |
| `DOMExtractorPort` | `DOMExtractorPort.ts` | `extract(url): Promise<DOMSkeleton>` |
| `WSClientPort` | `WSClientPort.ts` | `connect(dealerId, onMessage?)`, `disconnect()` — per-operation lifecycle, exposed via the `createWSClient` factory in the services bundle |
