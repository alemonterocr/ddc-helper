import { describe, it, expect } from "vitest"
import { parseLinksToPages } from "./linkParser"

describe("parseLinksToPages", () => {
  it("extracts title from last path segment", () => {
    const result = parseLinksToPages(
      "https://www.example.com/research/corolla-cross/",
    )
    expect(result).toEqual([
      { url: "https://www.example.com/research/corolla-cross/", title: "corolla-cross" },
    ])
  })

  it("handles trailing slashes", () => {
    const result = parseLinksToPages(
      "https://www.example.com/finance/buy-vs-lease/",
    )
    expect(result[0]!.title).toBe("buy-vs-lease")
  })

  it("strips query params from title extraction", () => {
    const result = parseLinksToPages(
      "https://www.example.com/search?q=foo",
    )
    expect(result[0]!.title).toBe("search")
  })

  it("handles hashes", () => {
    const result = parseLinksToPages(
      "https://www.example.com/page#section",
    )
    expect(result[0]!.title).toBe("page")
  })

  it("deduplicates URLs", () => {
    const result = parseLinksToPages(
      "https://www.example.com/a/\nhttps://www.example.com/a/",
    )
    expect(result).toHaveLength(1)
  })

  it("deduplicates URLs with query params", () => {
    const result = parseLinksToPages(
      "https://www.example.com/a?x=1\nhttps://www.example.com/a?x=2",
    )
    expect(result).toHaveLength(1)
  })

  it("skips blank lines", () => {
    const result = parseLinksToPages(
      "\nhttps://www.example.com/a/\n\n",
    )
    expect(result).toHaveLength(1)
  })

  it("handles empty input", () => {
    expect(parseLinksToPages("")).toEqual([])
    expect(parseLinksToPages("   \n  \n  ")).toEqual([])
  })

  it("uses fallback title for URLs without path", () => {
    const result = parseLinksToPages("https://www.example.com")
    expect(result[0]!.title).toBe("www.example.com")
  })

  it("handles multiple links", () => {
    const result = parseLinksToPages(
      "https://www.example.com/a/\nhttps://www.example.com/b/",
    )
    expect(result).toEqual([
      { url: "https://www.example.com/a/", title: "a" },
      { url: "https://www.example.com/b/", title: "b" },
    ])
  })

  it("handles multi-segment paths", () => {
    const result = parseLinksToPages(
      "https://www.example.com/finance/buy-vs-lease/",
    )
    expect(result[0]!.title).toBe("buy-vs-lease")
  })
})
