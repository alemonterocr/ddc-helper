import type { MigrationPage, PageStatus } from '../../../store/types'
import { Button } from '@/components/ui/button'
import { X } from 'lucide-react'

interface PageListItemProps {
  page: MigrationPage
  isActive: boolean
  onClick: () => void
  onDelete: () => void
}

const STATUS_CONFIG: Record<PageStatus, { label: string; text: string }> = {
  pending:   { label: 'Pending',   text: 'text-muted-foreground' },
  analyzing: { label: 'Analyzing', text: 'text-primary'          },
  reviewing: { label: 'Review',    text: 'text-warning'          },
  executing: { label: 'Running',   text: 'text-primary'          },
  done:      { label: 'Done',      text: 'text-success'          },
  error:     { label: 'Error',     text: 'text-destructive'      },
}

export function PageListItem({ page, isActive, onClick, onDelete }: PageListItemProps) {
  const { text, label } = STATUS_CONFIG[page.status]

  const displayTitle = page.pageTitle
    ?? _slugFromUrl(page.liveSiteUrl)
    ?? page.liveSiteUrl

  return (
    <div
      className={[
        'group relative flex flex-col gap-1 px-3 py-2.5 rounded-md transition-colors cursor-pointer',
        isActive
          ? 'bg-primary/10 border border-primary/30'
          : 'hover:bg-accent/60 border border-transparent',
      ].join(' ')}
      onClick={onClick}
    >
      <div className="flex items-center gap-2 min-w-0 pr-5">
        <span className="text-xs font-medium text-foreground truncate">{displayTitle}</span>
      </div>

      <div className="flex items-center gap-2">
        <span className={`text-xs ${text}`}>{label}</span>
        {page.ddcAlias && (
          <>
            <span className="text-muted-foreground text-xs">·</span>
            <span className="text-xs text-muted-foreground font-mono truncate">{page.ddcAlias}</span>
          </>
        )}
      </div>

      <div className="absolute top-1.5 right-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
        <Button
          variant="ghost"
          size="icon"
          className="h-5 w-5"
          onClick={e => { e.stopPropagation(); onDelete() }}
        >
          <X size={12} />
        </Button>
      </div>
    </div>
  )
}

function _slugFromUrl(url: string): string | null {
  try {
    const path = new URL(url).pathname
    const last = path.split('/').filter(Boolean).pop()
    return last ? decodeURIComponent(last) : null
  } catch {
    return null
  }
}
