/** Thrown by `BackendHttpAdapter` when the BE returns a non-2xx response or the fetch itself fails. `status` is undefined for transport errors. */
export class BackendError extends Error {
  readonly status: number | undefined

  constructor(message: string, status?: number) {
    super(message)
    this.name = 'BackendError'
    this.status = status
  }
}
