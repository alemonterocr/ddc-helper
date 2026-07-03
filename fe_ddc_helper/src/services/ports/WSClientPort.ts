/**
 * Port for streaming progress + tool calls between the FE and the BE over
 * WebSocket. Each migration run opens a fresh connection (one per
 * analyze/execute cycle), so the composition root injects a factory
 * (`createWSClient`) rather than a singleton — see `ServicesContext.tsx`.
 */
export type WSMessageHandler = (message: string) => void

export interface WSClientPort {
  /**
   * Open the WebSocket and start streaming progress messages. Resolves once
   * the connection is established. The `onMessage` callback fires for every
   * progress message the BE sends during the run.
   */
  connect(dealerId: string, onMessage?: WSMessageHandler): Promise<void>

  /** Close the connection. Safe to call multiple times. */
  disconnect(): void
}
