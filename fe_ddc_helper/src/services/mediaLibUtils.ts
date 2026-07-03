/**
 * Pure utility functions for media library operations.
 *
 * Nothing here touches Chrome APIs or network — all functions are side-effect-free
 * except convertToWebP which uses OffscreenCanvas (available in extension context).
 *
 * Ported and adapted from cms-auto-builder/photoMigrationService.ts.
 */

// ── ULID generator ────────────────────────────────────────────────────────────

const _CROCKFORD = '0123456789ABCDEFGHJKMNPQRSTVWXYZ'

/** Generate a Crockford base32 ULID (26 chars, uppercase). DDC requires this format. */
export function generateUploadId(): string {
  const now = Date.now()
  let ts = ''
  let t = now
  for (let i = 9; i >= 0; i--) {
    ts = _CROCKFORD[t % 32] + ts
    t = Math.floor(t / 32)
  }
  let rnd = ''
  for (let i = 0; i < 16; i++) rnd += _CROCKFORD[Math.floor(Math.random() * 32)]
  return ts + rnd
}

// ── Folder tree traversal ─────────────────────────────────────────────────────

export interface FolderNode {
  value: string
  label: string
  children: FolderNode[]
}

/**
 * Recursive depth-first search over a DDC media library folder tree.
 *
 * DDC uses inconsistent field names across API versions.
 * This function handles all observed variants for both the node identifier and
 * the display name, as well as all observed children field names.
 */
export function findNode(
  nodes: unknown[],
  matcher: (label: string) => boolean,
): FolderNode | null {
  for (const raw of nodes) {
    if (!raw || typeof raw !== 'object') continue
    const n = raw as Record<string, unknown>

    const label = String(
      n['description'] ?? n['libraryName'] ?? n['folderName'] ??
      n['label'] ?? n['name'] ?? n['title'] ?? ''
    )
    const value = String(n['value'] ?? n['id'] ?? n['folderId'] ?? n['libraryId'] ?? '')

    const children = (
      n['children'] ?? n['subFolders'] ?? n['subfolders'] ?? n['folders'] ?? n['items'] ?? []
    ) as unknown[]

    if (matcher(label)) return { label, value, children: children as FolderNode[] }

    const found = findNode(children, matcher)
    if (found) return found
  }
  return null
}

// ── Image format helpers ──────────────────────────────────────────────────────

/**
 * Detect the real MIME type of an image from its magic bytes,
 * falling back to the Content-Type header when the signature is ambiguous.
 */
export function detectMimeType(bytes: Uint8Array, ctHeader: string): string {
  // WebP: RIFF????WEBP
  if (
    bytes[0] === 0x52 && bytes[1] === 0x49 && bytes[2] === 0x46 && bytes[3] === 0x46 &&
    bytes[8] === 0x57 && bytes[9] === 0x45 && bytes[10] === 0x42 && bytes[11] === 0x50
  ) return 'image/webp'

  // PNG: \x89PNG
  if (bytes[0] === 0x89 && bytes[1] === 0x50 && bytes[2] === 0x4E && bytes[3] === 0x47)
    return 'image/png'

  // AVIF: ????ftypavif or ????ftypavi(s)
  if (
    bytes[4] === 0x66 && bytes[5] === 0x74 && bytes[6] === 0x79 && bytes[7] === 0x70 &&
    bytes[8] === 0x61 && bytes[9] === 0x76 && bytes[10] === 0x69 &&
    (bytes[11] === 0x66 || bytes[11] === 0x73)
  ) return 'image/avif'

  // Header fallback
  const ct = ctHeader.toLowerCase()
  if (ct.includes('webp')) return 'image/webp'
  if (ct.includes('png'))  return 'image/png'
  if (ct.includes('avif')) return 'image/avif'
  return 'image/jpeg'
}

/**
 * Convert raw image bytes to WebP using OffscreenCanvas.
 * Available in extension popup/sidepanel and service worker contexts.
 */
export async function convertToWebP(bytes: Uint8Array): Promise<Uint8Array> {
  // Cast to Uint8Array<ArrayBuffer> — TS 5.x widened the generic to ArrayBufferLike,
  // but Blob's constructor requires the narrower ArrayBuffer variant.
  const bitmap = await createImageBitmap(new Blob([bytes as Uint8Array<ArrayBuffer>]))
  const canvas = new OffscreenCanvas(bitmap.width, bitmap.height)
  const ctx = canvas.getContext('2d')!
  ctx.drawImage(bitmap, 0, 0)
  bitmap.close()
  const blob = await canvas.convertToBlob({ type: 'image/webp', quality: 0.92 })
  return new Uint8Array(await blob.arrayBuffer())
}

// ── Filename helpers ──────────────────────────────────────────────────────────

/** Derive a clean filename from a URL.  Renames the extension to .webp when applicable. */
export function deriveFilename(url: string, mimeType: string): string {
  const rawName = url.split('?')[0]?.split('/').pop() ?? `photo-${Date.now()}`
  const hasExt  = /\.\w{2,5}$/.test(rawName)
  const base    = hasExt ? rawName : `${rawName}.jpg`
  return mimeType === 'image/webp' ? base.replace(/\.\w+$/, '.webp') : base
}
