import type { SectionPlanItem } from '../types'

function escapeRegex(str: string): string {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/**
 * Apply user-supplied link replacements to a copy of the section plan.
 * - Replacement starts with "/" → internal DDC link, no target attribute
 * - Anything else → external link, adds target="_blank"
 * - Empty replacement → original href kept untouched
 * The original plan is never mutated.
 */
export function applyLinkReplacements(
  plan: SectionPlanItem[],
  replacements: Record<string, string>,
): SectionPlanItem[] {
  const entries = Object.entries(replacements).filter(([, v]) => v.trim())
  if (entries.length === 0) return plan

  function processHtml(html: string): string {
    let result = html
    for (const [original, replacement] of entries) {
      const trimmed = replacement.trim()
      if (!trimmed) continue

      const isInternal = trimmed.startsWith('/')
      const targetAttr = isInternal ? '' : ' target="_blank"'
      const esc = escapeRegex(original)

      // Match the full opening <a> tag: capture attrs before and after href="..."
      result = result.replace(
        new RegExp(`<a\\b([^>]*)href="${esc}"([^>]*)>`, 'g'),
        (_match, before: string, after: string) => {
          // Strip any existing target from both captured attribute strings
          const cleanBefore = before.replace(/\s*\btarget="[^"]*"\s*/g, ' ').trim()
          const cleanAfter  = after.replace( /\s*\btarget="[^"]*"\s*/g, ' ').trim()
          const bStr = cleanBefore ? ` ${cleanBefore}` : ''
          const aStr = cleanAfter  ? ` ${cleanAfter}`  : ''
          return `<a${bStr} href="${trimmed}"${aStr}${targetAttr}>`
        },
      )
    }
    return result
  }

  return plan.map(item => ({
    ...item,
    slots: item.slots.map(slot =>
      slot.map(widget => {
        if (widget.widget_type !== 'content' || !widget.html) return widget
        return { ...widget, html: processHtml(widget.html) }
      }),
    ),
  }))
}
