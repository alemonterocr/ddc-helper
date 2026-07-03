import { useState } from 'react'
import type { SectionPlanItem, ColumnWidget, WidgetType } from '../../../types'
import { useSortable } from '@dnd-kit/sortable'
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable'
import { useDroppable } from '@dnd-kit/core'
import { CSS } from '@dnd-kit/utilities'
import {
  FileText,
  Image as ImageIcon,
  ImageOff,
  MousePointer,
  Phone,
  Clock,
  Send,
  GripVertical,
  Pencil,
  X,
  ChevronDown,
  ChevronRight,
  Check,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { AddWidgetMenu } from '../AddWidgetMenu/AddWidgetMenu'
import { WidgetEditor } from '../WidgetEditor/WidgetEditor'
import { COLUMN_RATIOS } from '../../../services/planEdit'
import {
  WIDGET_PREFIX,
  SLOT_PREFIX,
} from '../../organisms/StructurePlanPreview/StructurePlanPreview'

interface SectionPlanCardProps {
  item: SectionPlanItem
  onRemove?: () => void
  sectionDragId?: string
  onAddWidget?: (slotIndex: number, widgetType: string) => void
  onDeleteWidget?: (slotIndex: number, widgetIndex: number) => void
  onUpdateWidget?: (
    slotIndex: number,
    widgetIndex: number,
    patch: Partial<ColumnWidget>,
  ) => void
  selectedWidgetIds?: Set<string>
  onToggleSelect?: (widgetId: string, shiftKey: boolean) => void
  activePasteTarget?: { sectionPos: number; slotIndex: number } | null
  onFocusSlot?: (sectionPos: number, slotIndex: number) => void
}

const WIDGET_ICON: Record<WidgetType, React.ComponentType<{ size?: number; className?: string }>> = {
  content: FileText,
  image: ImageIcon,
  links: MousePointer,
  contact_info: Phone,
  hours: Clock,
  form: Send,
}

export function SectionPlanCard({
  item,
  onRemove,
  sectionDragId,
  onAddWidget,
  onDeleteWidget,
  onUpdateWidget,
  selectedWidgetIds,
  onToggleSelect,
  activePasteTarget,
  onFocusSlot,
}: SectionPlanCardProps) {
  const [expanded, setExpanded] = useState(false)
  const [editing, setEditing] = useState<{ slotIdx: number; widgetIdx: number } | null>(null)

  const sectionSortable = sectionDragId
    ? // eslint-disable-next-line react-hooks/rules-of-hooks
      useSortable({ id: sectionDragId })
    : null

  const totalWidgets = item.slots.reduce((acc, s) => acc + s.length, 0)
  const allWidgets = item.slots.flat()
  const hasHtml = allWidgets.some(c => c.html)
  const ratios = COLUMN_RATIOS[item.section_type] ?? [1]
  const isMapHours = item.section_type === 'map-hours'
  const multiSlot = ratios.length > 1

  return (
    <div
      ref={sectionSortable?.setNodeRef}
      style={sectionSortable ? {
        transform: CSS.Transform.toString(sectionSortable.transform),
        transition: sectionSortable.transition,
      } : undefined}
      className="flex flex-col gap-2 p-3 rounded-md bg-card border border-border group"
    >
      {/* ── Header row ────────────────────────────────────────────── */}
      <div className="flex items-center gap-2">
        {sectionSortable && (
          <button
            {...sectionSortable.attributes}
            {...sectionSortable.listeners}
            className="shrink-0 text-muted-foreground hover:text-foreground cursor-grab active:cursor-grabbing opacity-0 group-hover:opacity-100 transition-opacity"
            title="Drag to reorder"
          >
            <GripVertical size={14} />
          </button>
        )}
        <span className="text-xs font-mono text-muted-foreground w-5 text-right">
          {item.position}
        </span>
        <Badge variant="secondary">{item.section_type}</Badge>
        {totalWidgets > 0 && (
          <span className="text-xs text-muted-foreground">
            {item.slots.length} slot{item.slots.length !== 1 ? 's' : ''}
            {totalWidgets !== item.slots.length && (
              <span className="ml-1">· {totalWidgets} widget{totalWidgets !== 1 ? 's' : ''}</span>
            )}
          </span>
        )}
        {onRemove && (
          <button
            onClick={(e) => { e.stopPropagation(); onRemove() }}
            title="Remove section"
            className="ml-auto shrink-0 w-5 h-5 flex items-center justify-center rounded text-muted-foreground hover:text-destructive hover:bg-destructive/10 opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer"
          >
            <X size={14} />
          </button>
        )}
      </div>

      {/* ── Visual grid ───────────────────────────────────────────── */}
      {isMapHours ? (
        <div className="rounded-md border border-dashed border-border bg-muted/30 px-3 py-2 text-center">
          <span className="text-xs text-muted-foreground">
            pre-wired by DDC — no widget injection
          </span>
        </div>
      ) : (
        <div className="flex gap-2 overflow-x-auto">
          {ratios.map((flex, slotIdx) => (
            <SlotColumn
              key={slotIdx}
              flex={flex}
              slotIndex={slotIdx}
              slotWidgets={item.slots[slotIdx] ?? []}
              multiSlot={multiSlot}
              sectionPos={item.position}
              editing={editing}
              setEditing={setEditing}
              onAddWidget={onAddWidget}
              onDeleteWidget={onDeleteWidget}
              onUpdateWidget={onUpdateWidget}
              selectedWidgetIds={selectedWidgetIds}
              onToggleSelect={onToggleSelect}
              activePasteTarget={activePasteTarget}
              onFocusSlot={onFocusSlot}
            />
          ))}
        </div>
      )}

      {/* ── Intent + HTML preview ─────────────────────────────────── */}
      {item.intent && (
        <p className="text-xs text-muted-foreground leading-relaxed">{item.intent}</p>
      )}

      {hasHtml && (
        <div className="flex flex-col gap-1">
          <button
            onClick={() => setExpanded(e => !e)}
            className="text-xs text-primary hover:underline cursor-pointer self-start flex items-center gap-1"
          >
            {expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
            {expanded ? 'Hide HTML' : 'Preview HTML'}
          </button>
          {expanded && (
            <div className="flex flex-col gap-2 mt-1">
              {allWidgets.map((col, i) =>
                col.html ? (
                  <pre
                    key={i}
                    className="text-xs text-foreground bg-background border border-border rounded p-2 overflow-x-auto whitespace-pre-wrap font-mono leading-relaxed max-h-40 scrollbar-thin"
                  >
                    {col.html}
                  </pre>
                ) : null,
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Slot column ──────────────────────────────────────────────────────────────

interface SlotColumnProps {
  flex: number
  slotIndex: number
  slotWidgets: ColumnWidget[]
  multiSlot: boolean
  sectionPos: number
  editing: { slotIdx: number; widgetIdx: number } | null
  setEditing: (e: { slotIdx: number; widgetIdx: number } | null) => void
  onAddWidget?: (slotIndex: number, widgetType: string) => void
  onDeleteWidget?: (slotIndex: number, widgetIndex: number) => void
  onUpdateWidget?: (
    slotIndex: number,
    widgetIndex: number,
    patch: Partial<ColumnWidget>,
  ) => void
  selectedWidgetIds?: Set<string>
  onToggleSelect?: (widgetId: string, shiftKey: boolean) => void
  activePasteTarget?: { sectionPos: number; slotIndex: number } | null
  onFocusSlot?: (sectionPos: number, slotIndex: number) => void
}

function SlotColumn({
  flex,
  slotIndex,
  slotWidgets,
  multiSlot,
  sectionPos,
  editing,
  setEditing,
  onAddWidget,
  onDeleteWidget,
  onUpdateWidget,
  selectedWidgetIds,
  onToggleSelect,
  activePasteTarget,
  onFocusSlot,
}: SlotColumnProps) {
  const [collapsed, setCollapsed] = useState(false)
  const slotId = `${SLOT_PREFIX}${sectionPos}-${slotIndex}`
  const widgetIds = slotWidgets.map(
    (_, wi) => `${WIDGET_PREFIX}${sectionPos}-${slotIndex}-${wi}`,
  )
  const { setNodeRef, isOver } = useDroppable({ id: slotId })
  const isEmpty = slotWidgets.length === 0
  const isPasteTarget =
    activePasteTarget?.sectionPos === sectionPos &&
    activePasteTarget?.slotIndex === slotIndex

  return (
    <div
      ref={setNodeRef}
      style={{ flex, minWidth: 80 }}
      className={cn(
        'flex flex-col gap-1.5 rounded-md p-2 transition-colors',
        !collapsed && 'min-h-[100px]',
        isEmpty
          ? 'border border-dashed border-border'
          : 'border border-border bg-background/30',
        isOver && 'bg-primary/10 ring-1 ring-primary',
        isPasteTarget && 'ring-2 ring-primary/40',
      )}
      onClick={(e) => {
        if ((e.target as HTMLElement).closest("button, input, [data-no-focus]")) return;
        onFocusSlot?.(sectionPos, slotIndex);
      }}
    >
      {/* Slot header — chevron + label + widget count */}
      <div className="flex items-center gap-1">
        <button
          onClick={() => setCollapsed(c => !c)}
          className="shrink-0 text-muted-foreground hover:text-foreground cursor-pointer"
          title={collapsed ? 'Expand slot' : 'Collapse slot'}
        >
          {collapsed ? <ChevronRight size={12} /> : <ChevronDown size={12} />}
        </button>
        {multiSlot && (
          <span className="text-[10px] text-muted-foreground font-mono">
            slot {slotIndex + 1}
          </span>
        )}
        <span className="text-[10px] text-muted-foreground font-mono ml-auto">
          {slotWidgets.length} widget{slotWidgets.length !== 1 ? 's' : ''}
        </span>
      </div>

      {!collapsed && (
        <>
          <SortableContext items={widgetIds} strategy={verticalListSortingStrategy}>
            {slotWidgets.map((widget, widgetIdx) => {
              const isEditing =
                editing?.slotIdx === slotIndex &&
                editing.widgetIdx === widgetIdx &&
                !!onUpdateWidget
              return (
                <SortableWidget
                  key={widgetIdx}
                  id={widgetIds[widgetIdx]!}
                  isEditing={isEditing}
                >
                  {isEditing && onUpdateWidget ? (
                    <WidgetEditor
                      widget={widget}
                      onSave={(patch) => {
                        onUpdateWidget(slotIndex, widgetIdx, patch)
                        setEditing(null)
                      }}
                      onCancel={() => setEditing(null)}
                    />
                  ) : (
                    <WidgetChip
                      widget={widget}
                      onEdit={onUpdateWidget ? () => setEditing({ slotIdx: slotIndex, widgetIdx }) : undefined}
                      onDelete={onDeleteWidget ? () => onDeleteWidget(slotIndex, widgetIdx) : undefined}
                      isSelected={selectedWidgetIds?.has(widgetIds[widgetIdx]!) ?? false}
                      onToggleSelect={onToggleSelect ? (sk: boolean) => onToggleSelect(widgetIds[widgetIdx]!, sk) : undefined}
                    />
                  )}
                </SortableWidget>
              )
            })}
          </SortableContext>

          {onAddWidget && (
            <div className="mt-auto">
              <AddWidgetMenu onSelect={(t) => onAddWidget(slotIndex, t)} />
            </div>
          )}
        </>
      )}
    </div>
  )
}

// ── Widget chip ──────────────────────────────────────────────────────────────

interface SortableWidgetProps {
  id: string
  isEditing: boolean
  children: React.ReactNode
}

function SortableWidget({ id, isEditing, children }: SortableWidgetProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id })

  // Don't bind drag listeners while editing — the editor contains inputs/buttons
  // that must receive their own pointer events without being hijacked by dnd-kit.
  const dragProps = isEditing ? {} : { ...attributes, ...listeners }

  return (
    <div
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={cn(isDragging && 'opacity-40 z-50')}
      {...dragProps}
    >
      {children}
    </div>
  )
}

interface WidgetChipProps {
  widget: ColumnWidget
  onEdit?: () => void
  onDelete?: () => void
  isSelected?: boolean
  onToggleSelect?: (shiftKey: boolean) => void
}

function WidgetChip({ widget, onEdit, onDelete, isSelected, onToggleSelect }: WidgetChipProps) {
  const Icon = WIDGET_ICON[widget.widget_type] ?? FileText
  const isImage = widget.widget_type === 'image'

  return (
    <div
      className={cn(
        "group/widget flex items-center gap-1.5 rounded border bg-card px-1.5 py-1 transition-colors",
        isSelected ? "border-primary ring-1 ring-primary/50" : "border-border",
        !isSelected && "cursor-grab active:cursor-grabbing",
      )}
      onClick={(e) => {
        if (e.shiftKey && onToggleSelect) {
          e.stopPropagation();
          onToggleSelect(true);
        }
      }}
    >
      {onToggleSelect && (
        <button
          onPointerDown={(e) => e.stopPropagation()}
          onClick={(e) => { e.stopPropagation(); onToggleSelect(e.shiftKey) }}
          data-no-focus
          title={isSelected ? "Deselect widget" : "Select widget"}
          className={cn(
            "shrink-0 w-3.5 h-3.5 rounded border transition-colors flex items-center justify-center",
            isSelected
              ? "bg-primary border-primary text-primary-foreground opacity-100"
              : "border-muted-foreground/30 opacity-0 group-hover/widget:opacity-100 hover:border-primary",
          )}
        >
          {isSelected && <Check size={8} strokeWidth={2} />}
        </button>
      )}
      {isImage ? <ImageThumb url={widget.source_url} /> : <Icon size={12} className="text-muted-foreground shrink-0" />}
      <span className="text-xs text-foreground font-medium truncate flex-1">
        {widget.widget_type}
      </span>
      {onEdit && (
        <button
          onPointerDown={(e) => e.stopPropagation()}
          onClick={(e) => { e.stopPropagation(); onEdit() }}
          title="Edit widget"
          data-no-focus
          className="shrink-0 w-4 h-4 flex items-center justify-center rounded text-muted-foreground hover:text-primary hover:bg-primary/10 opacity-0 group-hover/widget:opacity-100 transition-opacity"
        >
          <Pencil size={10} />
        </button>
      )}
      {onDelete && (
        <button
          onPointerDown={(e) => e.stopPropagation()}
          onClick={(e) => { e.stopPropagation(); onDelete() }}
          title="Remove widget"
          data-no-focus
          className="shrink-0 w-4 h-4 flex items-center justify-center rounded text-muted-foreground hover:text-destructive hover:bg-destructive/10 opacity-0 group-hover/widget:opacity-100 transition-opacity"
        >
          <X size={10} />
        </button>
      )}
    </div>
  )
}

function ImageThumb({ url }: { url?: string }) {
  const [errored, setErrored] = useState(false)
  if (!url || errored) {
    return <ImageOff size={12} className="text-muted-foreground shrink-0" />
  }
  return (
    <img
      src={url}
      alt=""
      loading="lazy"
      onError={() => setErrored(true)}
      className="w-4 h-4 rounded object-cover shrink-0"
    />
  )
}
