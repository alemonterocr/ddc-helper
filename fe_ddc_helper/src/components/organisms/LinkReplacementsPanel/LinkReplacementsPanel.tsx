import { useMemo } from 'react'
import type { MigrationPage } from '../../../store/types'
import type { SectionPlanItem } from '../../../types'
import { useMigrationStore } from '../../../store/useMigrationStore'
import { Input } from '@/components/ui/input'

interface LinkReplacementsPanelProps {
  projectId: string
  page: MigrationPage
}

export function LinkReplacementsPanel({ projectId, page }: LinkReplacementsPanelProps) {
  const { updatePage } = useMigrationStore()
  const replacements = page.linkReplacements ?? {}

  const hrefs = useMemo(
    () => extractHrefs(page.sectionPlan),
    [page.sectionPlan],
  )

  function handleChange(original: string, value: string) {
    updatePage(projectId, page.id, {
      linkReplacements: { ...replacements, [original]: value },
    })
  }

  return (
    <div className="flex flex-col gap-3">
      {hrefs.length > 0 && (
        <p className="text-xs text-muted-foreground">
          {hrefs.length} unique link{hrefs.length !== 1 ? 's' : ''}
        </p>
      )}

      {hrefs.length === 0 ? (
        <p className="text-xs text-muted-foreground">No links found in this plan.</p>
      ) : (
        <div className="flex flex-col gap-4 max-h-[320px] overflow-y-auto scrollbar-thin pr-1">
          {hrefs.map(({ href, count }) => (
            <div key={href} className="flex flex-col gap-1">
              {/* Original URL + occurrence count */}
              <div className="flex items-start justify-between gap-1">
                <span
                  className="text-xs font-mono text-muted-foreground break-all min-w-0 flex-1 leading-relaxed"
                  title={href}
                >
                  {href}
                </span>
                <span className="text-xs text-muted-foreground shrink-0 ml-1.5 pt-0.5">×{count}</span>
              </div>

              {/* Replacement input */}
              <Input
                value={replacements[href] ?? ''}
                onChange={e => handleChange(href, e.target.value)}
                placeholder={
                  href.startsWith('/')
                    ? '/new-inventory/index.htm'
                    : 'https://replacement-url.com'
                }
              />

              {/* Target indicator */}
              {replacements[href] && (
                <span className="text-xs text-muted-foreground">
                  {replacements[href].startsWith('/')
                    ? '↳ internal — same tab'
                    : '↳ external — target="_blank"'}
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Utilities ─────────────────────────────────────────────────────────────────

interface HrefEntry {
  href: string
  count: number
}

/** Extract all unique hrefs from content widget HTML across the full plan.
 *  Skips fragment-only anchors (#), mailto:, tel:, and javascript: hrefs. */
function extractHrefs(plan: SectionPlanItem[]): HrefEntry[] {
  const counts = new Map<string, number>()
  const re = /href="([^"]+)"/g

  for (const item of plan) {
    for (const slot of item.slots) {
      for (const widget of slot) {
        if (widget.widget_type !== 'content' || !widget.html) continue

        re.lastIndex = 0
        let m: RegExpExecArray | null
        while ((m = re.exec(widget.html)) !== null) {
          const href = m[1]
          if (!href) continue
          if (
            href.startsWith('#') ||
            href.startsWith('mailto:') ||
            href.startsWith('tel:') ||
            href.startsWith('javascript:')
          ) continue
          counts.set(href, (counts.get(href) ?? 0) + 1)
        }
      }
    }
  }

  return Array.from(counts.entries())
    .map(([href, count]) => ({ href, count }))
    .sort((a, b) => a.href.localeCompare(b.href))
}
