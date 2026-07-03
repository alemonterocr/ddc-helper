/// <reference types="chrome" />
import { uploadMediaImageInjected } from '../../scripts/mediaLibTools'
import {
  convertToWebP,
  deriveFilename,
  detectMimeType,
  generateUploadId,
} from '../mediaLibUtils'
import type { ICmsTool } from './ICmsTool'

const TOKEN_KEY  = 'ccIdtToken'
const MAX_UPLOAD_ATTEMPTS = 5

interface UploadMediaImageArgs {
  site_id: string
  image_url: string
  folder_id: string
  filename: string
}

export class UploadMediaImageTool implements ICmsTool<UploadMediaImageArgs> {
  readonly name   = 'upload_media_image'
  readonly domain = 'media_lib' as const

  async execute(args: UploadMediaImageArgs, tabId: number, _token: string): Promise<unknown> {
    // createdBy is the JWT sub claim — read from storage, never sent from the backend.
    const storage   = await chrome.storage.local.get([TOKEN_KEY])
    const createdBy = _extractUserId(storage[TOKEN_KEY] as string ?? '')

    // Fetch the image bytes in the extension context to bypass CORS restrictions.
    const { bytes, mimeType } = await _fetchAndNormalise(args.image_url)
    const filename = deriveFilename(args.filename || args.image_url, mimeType)

    // Convert bytes to base64 in chunks to avoid call-stack overflow on large images.
    const imageB64 = _toBase64(bytes)

    // Retry up to MAX_UPLOAD_ATTEMPTS times; each attempt uses a fresh ULID because
    // DDC may mark a failed uploadId as permanently invalid.
    let lastError = 'Unknown error'
    for (let attempt = 0; attempt < MAX_UPLOAD_ATTEMPTS; attempt++) {
      const uploadId = generateUploadId()
      try {
        const res = await chrome.scripting.executeScript({
          target: { tabId },
          world: 'MAIN',
          func: uploadMediaImageInjected,
          args: [imageB64, args.site_id, `${args.site_id}-admin`, createdBy, args.folder_id, filename, uploadId, mimeType],
        })
        const result = res[0]?.result as { ok: boolean; cdn_url?: string; error?: string } | null
        if (result?.ok) return { ok: true, cdn_url: result.cdn_url }
        lastError = result?.error ?? 'null result from injection'
      } catch (err) {
        lastError = err instanceof Error ? err.message : String(err)
      }
    }

    return { ok: false, error: lastError }
  }
}

// ── Private helpers ───────────────────────────────────────────────────────────

async function _fetchAndNormalise(
  url: string,
): Promise<{ bytes: Uint8Array; mimeType: string }> {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`Image fetch failed (${res.status}): ${url}`)

  const rawBytes = new Uint8Array(await res.arrayBuffer())
  const ctHeader = res.headers.get('content-type') ?? ''
  const detected = detectMimeType(rawBytes, ctHeader)

  // DDC handles WebP natively; convert PNG/AVIF to avoid upload rejections.
  if (detected === 'image/png' || detected === 'image/avif') {
    const webpBytes = await convertToWebP(rawBytes)
    return { bytes: webpBytes, mimeType: 'image/webp' }
  }

  return {
    bytes:    rawBytes,
    mimeType: detected === 'image/webp' ? 'image/webp' : 'image/jpeg',
  }
}

function _toBase64(bytes: Uint8Array): string {
  const CHUNK = 8192
  let binary  = ''
  for (let i = 0; i < bytes.length; i += CHUNK) {
    binary += String.fromCharCode(...bytes.subarray(i, i + CHUNK))
  }
  return btoa(binary)
}

function _extractUserId(jwt: string): string {
  try {
    const base64 = jwt.split('.')[1]?.replace(/-/g, '+').replace(/_/g, '/')
    if (!base64) return ''
    const claims = JSON.parse(atob(base64)) as Record<string, unknown>
    return (claims['sub'] as string) ?? (claims['aid'] as string) ?? ''
  } catch {
    return ''
  }
}
