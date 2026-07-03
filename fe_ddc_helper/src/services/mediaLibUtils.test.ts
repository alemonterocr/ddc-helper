import { describe, it, expect } from 'vitest'
import { generateUploadId, findNode, detectMimeType, deriveFilename } from './mediaLibUtils'

describe('generateUploadId', () => {
  it('produces a 26-char Crockford base32 ULID', () => {
    const id = generateUploadId()
    expect(id).toHaveLength(26)
    expect(id).toMatch(/^[0123456789ABCDEFGHJKMNPQRSTVWXYZ]{26}$/)
  })

  it('returns a different value on consecutive calls', () => {
    expect(generateUploadId()).not.toBe(generateUploadId())
  })
})

describe('findNode', () => {
  it('finds a node at the root via label matcher', () => {
    const tree = [{ label: 'Photos', value: 'p1', children: [] }]
    const node = findNode(tree, label => label === 'Photos')
    expect(node?.value).toBe('p1')
  })

  it('descends into children to find a match', () => {
    const tree = [{
      label: 'root',
      value: 'r',
      children: [{ label: 'inner', value: 'i', children: [] }],
    }]
    const node = findNode(tree, label => label === 'inner')
    expect(node?.value).toBe('i')
  })

  it('returns null when no match exists', () => {
    expect(findNode([{ label: 'a', value: '1', children: [] }], () => false)).toBeNull()
  })

  it('handles DDC label aliases (description, libraryName, folderName)', () => {
    const tree = [
      { description: 'desc-label', value: '1', children: [] },
      { libraryName: 'lib-label', value: '2', children: [] },
      { folderName: 'fld-label', value: '3', children: [] },
    ]
    expect(findNode(tree, l => l === 'desc-label')?.value).toBe('1')
    expect(findNode(tree, l => l === 'lib-label')?.value).toBe('2')
    expect(findNode(tree, l => l === 'fld-label')?.value).toBe('3')
  })

  it('handles DDC children aliases (subFolders, folders)', () => {
    const tree = [{
      label: 'root',
      value: 'r',
      subFolders: [{ label: 'child', value: 'c', children: [] }],
    }]
    expect(findNode(tree, l => l === 'child')?.value).toBe('c')
  })

  it('skips null/non-object entries gracefully', () => {
    const tree = [null, undefined, { label: 'x', value: '1', children: [] }] as unknown[]
    expect(findNode(tree, l => l === 'x')?.value).toBe('1')
  })
})

describe('detectMimeType', () => {
  it('detects WebP from magic bytes', () => {
    // RIFF????WEBP
    const bytes = new Uint8Array(12)
    bytes.set([0x52, 0x49, 0x46, 0x46], 0)
    bytes.set([0x57, 0x45, 0x42, 0x50], 8)
    expect(detectMimeType(bytes, '')).toBe('image/webp')
  })

  it('detects PNG from magic bytes', () => {
    const bytes = new Uint8Array([0x89, 0x50, 0x4E, 0x47, 0, 0, 0, 0, 0, 0, 0, 0])
    expect(detectMimeType(bytes, '')).toBe('image/png')
  })

  it('detects AVIF from ftypavif box', () => {
    const bytes = new Uint8Array(12)
    bytes.set([0x66, 0x74, 0x79, 0x70], 4)
    bytes.set([0x61, 0x76, 0x69, 0x66], 8)
    expect(detectMimeType(bytes, '')).toBe('image/avif')
  })

  it('falls back to content-type header when magic bytes are unknown', () => {
    const bytes = new Uint8Array(12)
    expect(detectMimeType(bytes, 'image/webp')).toBe('image/webp')
    expect(detectMimeType(bytes, 'image/png')).toBe('image/png')
  })

  it('defaults to JPEG when nothing matches', () => {
    expect(detectMimeType(new Uint8Array(12), 'application/octet-stream')).toBe('image/jpeg')
  })
})

describe('deriveFilename', () => {
  it('keeps the original filename when it has an extension', () => {
    expect(deriveFilename('https://cdn/foo/bar.jpg', 'image/jpeg')).toBe('bar.jpg')
  })

  it('strips query strings', () => {
    expect(deriveFilename('https://cdn/foo/bar.jpg?v=2', 'image/jpeg')).toBe('bar.jpg')
  })

  it('appends .jpg when the URL has no extension', () => {
    expect(deriveFilename('https://cdn/foo/bar', 'image/jpeg')).toBe('bar.jpg')
  })

  it('renames the extension to .webp when the mime type is webp', () => {
    expect(deriveFilename('https://cdn/foo/bar.jpg', 'image/webp')).toBe('bar.webp')
  })

  it('renames an added .jpg fallback to .webp for webp content', () => {
    expect(deriveFilename('https://cdn/foo/bar', 'image/webp')).toBe('bar.webp')
  })
})
