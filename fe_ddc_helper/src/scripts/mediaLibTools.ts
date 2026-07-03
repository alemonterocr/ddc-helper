/**
 * Self-contained functions injected into the DDC Media Library tab via
 * chrome.scripting.executeScript with world: 'MAIN'.
 *
 * MAIN world is required — the DDC media library API validates the JWTAuth cookie
 * and the Sec-Fetch-Site header. Both are only present when the fetch runs inside
 * the page's own JavaScript context. Isolated world requests receive 403.
 *
 * Zero imports, zero external closures — Chrome serialises these with .toString().
 * IMPORTANT: Do NOT use module-level constants — Vite minifies them and the
 * minified names don't exist in the injected page's scope.
 */

// ── Folder operations ─────────────────────────────────────────────────────────

export async function getMediaFoldersInjected(
  accountId: string,
  userId: string,
): Promise<{ ok: boolean; tree?: unknown[]; error?: string }> {
  const MEDIA_API = 'https://apps.dealercenter.coxautoinc.com/medialibrary-services/client'
  try {
    const url = `${MEDIA_API}/media/getFolders?accountId=${accountId}&userId=${userId}`
    const res = await fetch(url, { credentials: 'include' })
    const text = await res.text()
    if (!res.ok) {
      const hint = res.status === 401 || res.status === 403
        ? ' — reload the Media Library tab and re-check credentials'
        : ''
      return { ok: false, error: `getFolders HTTP ${res.status}${hint}: ${text.slice(0, 200)}` }
    }
    const data = JSON.parse(text)
    return { ok: true, tree: Array.isArray(data) ? data : [data] }
  } catch (e) {
    return { ok: false, error: String(e) }
  }
}

export async function createMediaFolderInjected(
  accountId: string,
  userId: string,
  parentId: string,
  name: string,
): Promise<{ ok: boolean; folder_id?: string; error?: string }> {
  const MEDIA_API = 'https://apps.dealercenter.coxautoinc.com/medialibrary-services/client'
  try {
    const url = `${MEDIA_API}/write/folders?accountId=${accountId}&userId=${userId}`
    const res = await fetch(url, {
      method: 'POST',
      credentials: 'include',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ parentId, accountId, libraryName: name }),
    })
    if (!res.ok) {
      const text = await res.text().catch(() => '')
      return { ok: false, error: `createFolder HTTP ${res.status}: ${text.slice(0, 200)}` }
    }
    const data = await res.json() as Record<string, unknown>
    const folder_id = String(data['folderId'] ?? data['id'] ?? '')
    if (!folder_id) return { ok: false, error: 'createFolder: no folderId in response' }
    return { ok: true, folder_id }
  } catch (e) {
    return { ok: false, error: String(e) }
  }
}

// ── Image upload (3-step: presign → S3 PUT → register + poll) ─────────────────

export async function uploadMediaImageInjected(
  imageB64: string,
  accountId: string,
  userId: string,
  createdBy: string,
  folderId: string,
  filename: string,
  uploadId: string,
  mimeType: string,
): Promise<{ ok: boolean; cdn_url?: string; error?: string }> {
  const MEDIA_API   = 'https://apps.dealercenter.coxautoinc.com/medialibrary-services/client'
  const ROUTING_API = 'https://apps.dealercenter.coxautoinc.com/media-asset-routing-system'
  // Wrap in try/catch — Chrome scripting converts unhandled async throws to null
  try {
    // Decode base64 → ArrayBuffer
    const raw   = atob(imageB64)
    const bytes = new Uint8Array(raw.length)
    for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i)
    const imageBuffer = bytes.buffer
    const fileSize    = imageBuffer.byteLength

    // Step 1 — get pre-signed S3 URL
    const presignRes = await fetch(`${ROUTING_API}/presignedUrlV2`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'content-type': 'text/plain;charset=UTF-8' },
      body: JSON.stringify({
        routingKey: 'web',
        accountId,
        uploadGroupId: uploadId,
        assetInfo: {
          asset: {
            libraryId:       folderId,
            filename,
            contentType:     mimeType,
            shouldResize:    false,
            pdfConvertToPng: false,
          },
        },
      }),
    })
    const presignText = await presignRes.text()
    if (!presignRes.ok) return { ok: false, error: `Presign ${presignRes.status}: ${presignText.slice(0, 200)}` }

    const presignData = JSON.parse(presignText) as Record<string, unknown>
    const s3Entry = (presignData['urls'] as Record<string, unknown>[] | undefined)?.[0]
    const s3Url    = s3Entry?.['url']      as string | undefined
    const s3FileId = s3Entry?.['uploadId'] as string | undefined
    if (!s3Url)    return { ok: false, error: 'presignedUrlV2: no presigned URL in response' }
    if (!s3FileId) return { ok: false, error: 'presignedUrlV2: no uploadId in response' }

    // Step 2 — PUT image bytes to S3 (no credentials: 'include' — direct S3, no cookies)
    const s3Res = await fetch(s3Url, {
      method: 'PUT',
      headers: {
        'content-type':               mimeType,
        'x-amz-meta-accountid':       accountId,
        'x-amz-meta-contenttype':     mimeType,
        'x-amz-meta-createdby':       createdBy,
        'x-amz-meta-filename':        filename,
        'x-amz-meta-libraryid':       folderId,
        'x-amz-meta-pdfconverttopng': 'false',
        'x-amz-meta-routingkey':      'web',
        'x-amz-meta-shouldresize':    'false',
        'x-amz-meta-uploadgroupid':   uploadId,
        'x-amz-meta-uploadid':        s3FileId,
      },
      body: imageBuffer,
    })
    if (!s3Res.ok) return { ok: false, error: `S3 PUT failed: ${s3Res.status}` }

    // Step 3 — register upload and poll until status === 'UPLOADED'
    const regUrl  = `${MEDIA_API}/write/uploads?accountId=${accountId}&userId=${userId}`
    const regBody = JSON.stringify({
      accountId,
      fileSize,
      routingKey:        'MARS',
      originalFileName:  filename,
      destinationFolder: folderId,
      createdBy,
      uploadId,
    })

    const MAX_POLLS = 10
    for (let attempt = 0; attempt < MAX_POLLS; attempt++) {
      if (attempt > 0) await new Promise(r => setTimeout(r, 2000))

      const regRes = await fetch(regUrl, {
        method: 'POST',
        credentials: 'include',
        headers: { 'content-type': 'application/json;charset=UTF-8' },
        body: regBody,
      })
      if (!regRes.ok) return { ok: false, error: `Register upload failed: ${regRes.status}` }

      const regData = await regRes.json() as Record<string, unknown>
      if (regData['status'] === 'UPLOADED') {
        const cdnUrl = String((regData['assetInfo'] as Record<string, unknown> | undefined)?.['name'] ?? '')
        if (cdnUrl.startsWith('http')) return { ok: true, cdn_url: cdnUrl }
        return { ok: false, error: `Upload reached UPLOADED but CDN URL is unexpected: "${cdnUrl}"` }
      }
    }

    return { ok: false, error: 'Upload never reached UPLOADED status after 10 polls' }
  } catch (e) {
    return { ok: false, error: String(e) }
  }
}
