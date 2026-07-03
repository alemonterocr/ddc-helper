/**
 * Tiny structured logger for the extension.
 *
 * Replaces direct `console.*` calls and silent `.catch(() => {})` patterns.
 * Three levels — `info`, `warn`, `error` — each takes a message plus an
 * optional context object. The error variant also accepts an `unknown`
 * thrown value (typed as the catch-clause default) and preserves its stack
 * by logging the Error instance separately at the end.
 *
 * Routes to `console.*` for now. The shape is stable enough that we can
 * swap the transport later (chrome.runtime message to a background page,
 * remote log endpoint, etc.) without touching call sites.
 *
 * Chrome extension debugging is hard enough — every log emits a timestamp
 * + level prefix so the DevTools console becomes scannable.
 */

type LogContext = Record<string, unknown>

function ts(): string {
  // ISO time-of-day to ms — e.g. "14:23:07.456".
  return new Date().toISOString().slice(11, 23)
}

function tag(level: string): string {
  return `[${level} ${ts()}]`
}

function errorToContext(err: unknown): LogContext {
  if (err instanceof Error) {
    return { errorName: err.name, errorMessage: err.message }
  }
  if (err !== undefined) {
    return { error: err }
  }
  return {}
}

export const log = {
  info(message: string, context?: LogContext): void {
    console.log(tag('INFO '), message, ...(context ? [context] : []))
  },

  warn(message: string, context?: LogContext): void {
    console.warn(tag('WARN '), message, ...(context ? [context] : []))
  },

  /**
   * Log an error with an optional thrown value and extra context. Preserves
   * the Error's stack by logging the instance separately after the structured
   * line.
   */
  error(message: string, err?: unknown, context?: LogContext): void {
    const merged = { ...errorToContext(err), ...context }
    const hasMeta = Object.keys(merged).length > 0
    console.error(tag('ERROR'), message, ...(hasMeta ? [merged] : []))
    if (err instanceof Error) console.error(err)
  },
} as const
