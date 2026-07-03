/**
 * Self-contained DOM extractor. Injected into live site tabs via
 * chrome.scripting.executeScript — zero imports, zero external closures.
 *
 * Pruning policy is intentionally narrow: tag + computed style only. Class-name
 * heuristics live entirely on the backend (`deterministic_migrate.py` +
 * `chrome_review` LLM node) so there is one source of truth for chrome
 * decisions and so the LLM can second-guess ambiguous cases.
 */
export function extractSkeleton(): { url: string; title: string; structure: object; raw_html: string } {
  // ── Tags that are never content ──────────────────────────────────────────────
  const SKIP_TAGS = new Set([
    'script', 'style', 'svg', 'noscript', 'link', 'meta', 'head', 'iframe',
  ])

  // ── Chrome pruning ────────────────────────────────────────────────────────────
  // These semantic tags are always site chrome — skip entire subtree.
  const CHROME_TAGS = new Set(['header', 'footer', 'nav', 'aside'])

  // ── Hidden / chrome-by-position pruning ──────────────────────────────────────
  // Returns true when the element should be skipped entirely.
  // Accepts a pre-computed rect to avoid calling getBoundingClientRect twice.
  function isHidden(el: Element, rect: DOMRect): boolean {
    const cs = window.getComputedStyle(el as HTMLElement)
    if (cs.display === 'none') return true
    if (cs.visibility === 'hidden') return true
    // position:fixed is always chrome (chat widgets, cookie banners, sticky CTAs).
    // position:sticky / absolute may be used for legitimate in-flow layout — keep.
    if (cs.position === 'fixed') return true
    if (rect.width === 0 || rect.height === 0) return true
    return false
  }

  // ── Root finder ───────────────────────────────────────────────────────────────
  function findRoot(): Element {
    const main =
      document.querySelector('main') ||
      document.querySelector('[role="main"]') ||
      document.querySelector('#main-content') ||
      document.querySelector('.page-content')
    if (!main) return document.body

    // Bootstrap-style layouts often put <main> in a `col-*` next to a sibling
    // `col-*` with `role="complementary"` (dealer hours/phones, related links).
    // The geometry classifier needs to see both columns, so widen to the lowest
    // common ancestor when a complementary sibling exists outside <main>.
    // Any chrome (header/footer/nav/aside) the widening sweeps in is pruned
    // by CHROME_TAGS during the walk.
    const aside = document.querySelector('[role="complementary"]')
    if (aside && !main.contains(aside)) {
      let ancestor: Element | null = main.parentElement
      while (ancestor && !ancestor.contains(aside)) {
        ancestor = ancestor.parentElement
      }
      if (ancestor) return ancestor
    }

    // Also widen for Bootstrap multi-column layouts — dealer pages commonly
    // place <main> inside a col-8 next to a col-4 sidebar (hours, phones,
    // map). Without this the sidebar never reaches the skeleton or the backend.
    const COL_RE = /\bcol-(xs|sm|md|lg|xl)-\d{1,2}\b/
    let cursor: Element | null = main.parentElement
    while (cursor && cursor !== document.body) {
      let colCount = 0
      for (let i = 0; i < cursor.children.length; i++) {
        const cls = ((cursor.children[i] as Element).className || '').toString()
        if (COL_RE.test(cls)) colCount++
      }
      if (colCount >= 2) return cursor
      cursor = cursor.parentElement
    }

    return main
  }

  // ── Layout-relevant inline styles ────────────────────────────────────────────
  function extractLayoutStyle(el: Element): string {
    const raw = (el as HTMLElement).style
    if (!raw || raw.length === 0) return ''
    const LAYOUT_PROPS = [
      'display', 'flex-direction', 'flex-wrap', 'flex',
      'grid-template-columns', 'grid-template-rows',
      'width', 'max-width', 'min-width',
      'float', 'columns',
    ]
    const parts: string[] = []
    for (const prop of LAYOUT_PROPS) {
      const val = raw.getPropertyValue(prop)
      if (val) parts.push(`${prop}:${val}`)
    }
    return parts.join(';')
  }

  // ── Background-color signal ───────────────────────────────────────────────────
  // Returns the element's computed background-color only when it differs from its
  // parent — i.e. this node introduces a new visual background break.
  function getOwnBackground(el: Element): string {
    const TRANSPARENT = ['transparent', 'rgba(0, 0, 0, 0)']
    const computed = window.getComputedStyle(el as HTMLElement).backgroundColor
    if (!computed || TRANSPARENT.includes(computed)) return ''
    const parentBg = el.parentElement
      ? window.getComputedStyle(el.parentElement).backgroundColor
      : ''
    if (computed === parentBg) return ''
    return computed
  }

  // ── Image source resolution ───────────────────────────────────────────────────
  // Handles lazy-loaded images: data-src, data-lazy-src, srcset, <picture>.
  const PLACEHOLDER_RE = /^data:image\/(gif|png|svg\+xml)/

  function resolveImageSrc(el: HTMLImageElement): string {
    // 1. .src — skip 1×1 transparent placeholders
    if (el.src && !PLACEHOLDER_RE.test(el.src)) return el.src

    // 2. data-src (common lazy-load attribute)
    const dataSrc = el.getAttribute('data-src')
    if (dataSrc) return dataSrc

    // 3. data-lazy-src (WP/Jetpack lazy load)
    const dataLazySrc = el.getAttribute('data-lazy-src')
    if (dataLazySrc) return dataLazySrc

    // 4. srcset — pick the entry with the largest width descriptor
    const srcsetAttr = el.getAttribute('srcset') || el.srcset
    if (srcsetAttr) {
      const best = srcsetAttr
        .split(',')
        .map(s => s.trim().split(/\s+/))
        .filter(parts => parts.length >= 1 && parts[0])
        .map(parts => ({ url: parts[0], w: parseInt(parts[1] || '0') || 0 }))
        .sort((a, b) => b.w - a.w)[0]
      if (best?.url) return best.url
    }

    // 5. <picture> — largest width descriptor across ALL <source> elements,
    //    consistent with how the bare-img srcset fallback is resolved above.
    const picture = el.closest('picture')
    if (picture) {
      let bestUrl = ''
      let bestW = -1
      picture.querySelectorAll('source[srcset]').forEach(source => {
        const picSrcset = source.getAttribute('srcset') || ''
        picSrcset.split(',').forEach(entry => {
          const parts = entry.trim().split(/\s+/)
          const url = parts[0]
          const w = parseInt(parts[1] || '0') || 0
          if (url && w > bestW) { bestW = w; bestUrl = url }
        })
      })
      if (bestUrl) return bestUrl
    }

    return el.src  // fallback — whatever .src resolved to
  }

  // ── Node walker ───────────────────────────────────────────────────────────────
  // No depth limit — chrome pruning + hidden pruning naturally cap the tree.
  function walkNode(el: Element): object | null {
    const tag = el.tagName.toLowerCase()
    const cls = el.getAttribute('class') || ''

    if (SKIP_TAGS.has(tag)) return null
    if (CHROME_TAGS.has(tag)) return null

    // Compute rect once; reuse for hidden check and for output fields.
    const rect = el.getBoundingClientRect()
    if (isHidden(el, rect)) return null

    const style = extractLayoutStyle(el)
    const bg = getOwnBackground(el)
    // Text capture has two modes depending on whether this element has
    // element children:
    //   * No element children (pure-text leaf, e.g. <span>Mazda</span>) →
    //     `text` holds the textContent; `children` stays empty. Cheapest
    //     path, unchanged from original behavior.
    //   * Element children present (mixed inline content, e.g.
    //     <p>Hello <strong>x</strong> tail</p>) → text-node siblings get
    //     emitted as `{tag: '#text', text}` pseudo-children below so order
    //     is preserved. `text` here stays empty and the inline text is
    //     reconstructed in the children walk.
    const hasElementChildren = el.children.length > 0
    const text = hasElementChildren ? '' : (el.textContent || '').trim()
    const src = tag === 'img' ? resolveImageSrc(el as HTMLImageElement) : ''
    // Capture href for <a> tags. Use .href (not getAttribute) so the browser
    // resolves relative paths to absolute URLs automatically.
    const href = tag === 'a' ? ((el as HTMLAnchorElement).href || '') : ''
    // target on <a> — needed by DDC's Links widget (ButtonDTO.target).
    const target = tag === 'a' ? ((el as HTMLAnchorElement).target || '') : ''
    // role attribute — `role="button"` lets us detect <div>/<span> styled
    // buttons that don't use <a>/<button> tags.
    const role = el.getAttribute('role') || ''

    // Geometry — document-relative (viewport + scroll offset), rounded to int.
    // getBoundingClientRect() is viewport-relative; adding scrollX/Y makes y-gap
    // analysis correct for elements below the fold.
    const x = Math.round(rect.x + window.scrollX)
    const y = Math.round(rect.y + window.scrollY)
    const w = Math.round(rect.width)
    const h = Math.round(rect.height)

    // Additional computed-style signals (two properties, not a full dump).
    const cs = window.getComputedStyle(el as HTMLElement)
    const bgImage = cs.backgroundImage !== 'none'
    const fontSize = parseInt(cs.fontSize) || 0

    // Extract background-image URL when present.
    // getComputedStyle returns an absolute URL so no manual resolution needed.
    // Format: url("https://...") or url('...') — strip the wrapper.
    let bgImageSrc = ''
    if (bgImage) {
      const m = cs.backgroundImage.match(/url\(['"]?(.*?)['"]?\)/)
      if (m && m[1]) bgImageSrc = m[1].split('?')[0] ?? ''  // drop query-string size hints
    }

    // Walk childNodes (not just children) so we can pick up text-node
    // siblings of element children. Text-only nodes become `#text` pseudo-
    // children that preserve the inline order of mixed content like
    // <p>Hello <strong>x</strong> tail</p>. For pure-text leaves we skip
    // this — the textContent is already captured in `text` above.
    const children = hasElementChildren
      ? Array.from(el.childNodes)
          .map(child => {
            if (child.nodeType === Node.TEXT_NODE) {
              const raw = child.textContent || ''
              // Skip whitespace-only nodes (HTML formatting indentation).
              if (raw.trim() === '') return null
              // Collapse internal whitespace runs but PRESERVE significant
              // leading/trailing spaces — the single space between
              // "deciding" and the following <strong> is real content.
              const t = raw.replace(/\s+/g, ' ')
              return { tag: '#text', cls: '', text: t, children: [] as object[] }
            }
            if (child.nodeType === Node.ELEMENT_NODE) {
              return walkNode(child as Element)
            }
            return null
          })
          .filter(Boolean)
      : []

    return {
      tag,
      cls,
      ...(style       && { style }),
      ...(bg          && { bg }),
      text,
      ...(src         && { src }),
      ...(href        && { href }),
      ...(target      && { target }),
      ...(role        && { role }),
      x, y, w, h,
      ...(bgImage     && { bgImage: true }),
      ...(bgImageSrc  && { bgImageSrc }),
      ...(fontSize > 0 && { fontSize }),
      children,
    }
  }

  const root = findRoot()
  return {
    url: window.location.href,
    title: document.title,
    structure: walkNode(root) ?? { tag: 'body', cls: '', text: '', children: [] },
    raw_html: root.innerHTML.substring(0, 80_000),
  }
}
