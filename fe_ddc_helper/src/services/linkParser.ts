export interface ParsedLink {
  url: string
  title: string
}

export function parseLinksToPages(raw: string): ParsedLink[] {
  const seen = new Set<string>()
  const results: ParsedLink[] = []

  for (const line of raw.split("\n")) {
    const trimmed = line.trim()
    if (!trimmed) continue

    let url = trimmed.replace(/^["']|["']$/g, "")
    // Strip trailing slash and query/hash for dedup, keep original for storage
    const dedupKey = url.replace(/[?#].*$/, "").replace(/\/$/, "")
    if (seen.has(dedupKey)) continue
    seen.add(dedupKey)

    const title = extractTitle(url)
    results.push({ url, title })
  }

  return results
}

function extractTitle(url: string): string {
  try {
    const parsed = new URL(url)
    // Get path, strip leading/trailing slashes, take last segment
    const segments = parsed.pathname.replace(/^\/|\/$/g, "").split("/")
    const last = segments[segments.length - 1]
    return last || url.replace(/^https?:\/\//, "").split("/")[0] || "page"
  } catch {
    // Fallback for invalid URLs — take last segment after final /
    const parts = url.replace(/\/$/, "").split("/")
    return parts[parts.length - 1] || "page"
  }
}
