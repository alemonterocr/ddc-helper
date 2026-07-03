import type { DOMSkeleton } from '../../types'

export interface DOMExtractorPort {
  extract(url: string, signal?: AbortSignal): Promise<DOMSkeleton>
}
