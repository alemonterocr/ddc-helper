import {
  FileText,
  Image as ImageIcon,
  MousePointer,
  Phone,
  Clock,
  Send,
} from 'lucide-react'
import type { WidgetType } from '../../../types'
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
} from '@/components/ui/dropdown-menu'

interface AddWidgetMenuProps {
  onSelect: (widgetType: string) => void
}

const WIDGET_TYPES: Array<{ type: WidgetType; label: string }> = [
  { type: 'content', label: 'Content' },
  { type: 'image', label: 'Image' },
  { type: 'links', label: 'Links (buttons)' },
  { type: 'form', label: 'Form' },
  { type: 'contact_info', label: 'Contact Info' },
  { type: 'hours', label: 'Hours' },
]

const WIDGET_ICON: Record<WidgetType, React.ComponentType<{ size?: number; className?: string }>> = {
  content: FileText,
  image: ImageIcon,
  links: MousePointer,
  contact_info: Phone,
  hours: Clock,
  form: Send,
}

export function AddWidgetMenu({ onSelect }: AddWidgetMenuProps) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="text-xs text-muted-foreground hover:text-foreground border border-dashed border-border hover:border-ring rounded px-2 py-0.5 cursor-pointer transition-colors">
        + widget
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" sideOffset={4} className="w-44">
        {WIDGET_TYPES.map(({ type, label }) => {
          const Icon = WIDGET_ICON[type]
          return (
            <DropdownMenuItem
              key={type}
              onClick={() => onSelect(type)}
            >
              <Icon size={12} className="text-muted-foreground shrink-0" />
              <span className="font-mono text-muted-foreground">{type}</span>
              <span className="ml-auto text-muted-foreground">{label}</span>
            </DropdownMenuItem>
          )
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
