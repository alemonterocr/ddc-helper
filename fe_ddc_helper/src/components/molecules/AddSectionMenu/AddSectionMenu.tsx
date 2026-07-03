import { useState, useRef, useEffect } from 'react'
import { slotCountForType } from '../../../services/planEdit'

interface AddSectionMenuProps {
  onSelect: (sectionType: string) => void
}

const SECTION_TYPES: string[] = [
  'empty-one',
  'empty-fifty-fifty',
  'empty-66-33',
  'empty-33-66',
  'empty-thirds',
  'empty-fourths',
  'empty-fifths',
  'map-hours',
]

export function AddSectionMenu({ onSelect }: AddSectionMenuProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [open])

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full py-2 rounded-md border border-dashed border-border text-xs text-muted-foreground hover:text-foreground hover:border-ring transition-colors cursor-pointer"
      >
        + Add section
      </button>
      {open && (
        <div className="absolute bottom-full left-0 mb-1 w-56 rounded-md border border-border bg-card shadow-lg z-10">
          {SECTION_TYPES.map(st => {
            const slots = slotCountForType(st)
            return (
              <button
                key={st}
                onClick={() => { onSelect(st); setOpen(false) }}
                className="w-full text-left px-3 py-2 text-xs text-foreground hover:bg-accent hover:text-accent-foreground first:rounded-t-md last:rounded-b-md cursor-pointer flex justify-between items-center"
              >
                <span className="font-mono">{st}</span>
                <span className="text-muted-foreground">{slots} slot{slots !== 1 ? 's' : ''}</span>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
