import { useState, useCallback, useEffect, useRef } from "react";
import type { SectionPlanItem, ColumnWidget } from "../../../types";
import {
  DndContext,
  closestCenter,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SectionPlanCard } from "../../molecules/SectionPlanCard/SectionPlanCard";
import { AddSectionMenu } from "../../molecules/AddSectionMenu/AddSectionMenu";

const SECTION_PREFIX = "section-";
const WIDGET_PREFIX = "widget-";
const SLOT_PREFIX = "slot-";

interface WidgetClipboard {
  widgets: ColumnWidget[];
  sourceSectionPos: number;
}

interface StructurePlanPreviewProps {
  plan: SectionPlanItem[];
  warnings: string[];
  onExecute: () => void;
  onRemoveSection?: (position: number) => void;
  onAddSection?: (atIndex: number, sectionType: string) => void;
  onMoveSection?: (fromIndex: number, toIndex: number) => void;
  onAddWidget?: (
    sectionPos: number,
    slotIndex: number,
    widgetType: string,
  ) => void;
  onDeleteWidget?: (
    sectionPos: number,
    slotIndex: number,
    widgetIndex: number,
  ) => void;
  onUpdateWidget?: (
    sectionPos: number,
    slotIndex: number,
    widgetIndex: number,
    patch: Partial<ColumnWidget>,
  ) => void;
  onMoveWidget?: (
    from: { sectionPos: number; slotIndex: number; widgetIndex: number },
    to: { sectionPos: number; slotIndex: number; widgetIndex: number },
  ) => void;
  onPasteWidgets?: (sectionPos: number, slotIndex: number, widgets: ColumnWidget[]) => void;
  isExecuting?: boolean;
}

export function StructurePlanPreview({
  plan,
  warnings,
  onExecute,
  onRemoveSection,
  onAddSection,
  onMoveSection,
  onAddWidget,
  onDeleteWidget,
  onUpdateWidget,
  onMoveWidget,
  onPasteWidgets,
  isExecuting,
}: StructurePlanPreviewProps) {
  const [confirmed, setConfirmed] = useState(false);

  const [selectedWidgetIds, setSelectedWidgetIds] = useState<Set<string>>(new Set());
  const [clipboard, setClipboard] = useState<WidgetClipboard | null>(null);
  const [activePasteTarget, setActivePasteTarget] = useState<{ sectionPos: number; slotIndex: number } | null>(null);
  const [pasteConfirm, setPasteConfirm] = useState<{ sectionPos: number; slotIndex: number; widgets: ColumnWidget[] } | null>(null);

  const selectionAnchorRef = useRef<string | null>(null);
  const onDeleteWidgetRef = useRef(onDeleteWidget);
  onDeleteWidgetRef.current = onDeleteWidget;

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
  );

  const sortedPlan = [...plan].sort((a, b) => a.position - b.position);
  const sortedPlanRef = useRef(sortedPlan);
  sortedPlanRef.current = sortedPlan;

  const sectionIds = sortedPlan.map((s) => `${SECTION_PREFIX}${s.position}`);

  const toggleSelect = useCallback((widgetId: string, shiftKey: boolean) => {
    if (shiftKey && selectionAnchorRef.current) {
      const range = getRangeInSlot(selectionAnchorRef.current, widgetId, sortedPlanRef.current);
      setSelectedWidgetIds((prev) => {
        const next = new Set(prev);
        for (const id of range) next.add(id);
        return next;
      });
      return;
    }

    setSelectedWidgetIds((prev) => {
      const next = new Set(prev);
      if (next.has(widgetId)) next.delete(widgetId);
      else next.add(widgetId);
      return next;
    });
    selectionAnchorRef.current = widgetId;
  }, []);

  const focusSlot = useCallback((sectionPos: number, slotIndex: number) => {
    setActivePasteTarget({ sectionPos, slotIndex });
  }, []);

  const clearSelection = useCallback(() => {
    setSelectedWidgetIds(new Set());
    setClipboard(null);
  }, []);

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      const tag = (document.activeElement?.tagName ?? "").toLowerCase();
      if (tag === "input" || tag === "textarea" || (document.activeElement as HTMLElement)?.isContentEditable) return;

      if (e.ctrlKey && e.key === "c" && selectedWidgetIds.size > 0) {
        e.preventDefault();
        const widgets: ColumnWidget[] = [];
        let sourceSectionPos: number | null = null;
        for (const item of sortedPlanRef.current) {
          for (let si = 0; si < item.slots.length; si++) {
            const slot = item.slots[si] ?? [];
            for (let wi = 0; wi < slot.length; wi++) {
              const id = `${WIDGET_PREFIX}${item.position}-${si}-${wi}`;
              if (selectedWidgetIds.has(id)) {
                widgets.push(structuredClone(slot[wi]!));
                if (sourceSectionPos === null) sourceSectionPos = item.position;
              }
            }
          }
        }
        if (widgets.length > 0 && sourceSectionPos !== null) {
          const clip: WidgetClipboard = { widgets, sourceSectionPos };
          setClipboard(clip);
          navigator.clipboard.writeText(JSON.stringify(clip)).catch(() => {});
        }
        return;
      }

      if (e.ctrlKey && e.key === "x" && selectedWidgetIds.size > 0) {
        e.preventDefault();
        const widgets: ColumnWidget[] = [];
        let sourceSectionPos: number | null = null;
        const deletions: { sectionPos: number; slotIndex: number; widgetIndex: number }[] = [];
        for (const item of sortedPlanRef.current) {
          for (let si = 0; si < item.slots.length; si++) {
            const slot = item.slots[si] ?? [];
            for (let wi = 0; wi < slot.length; wi++) {
              const id = `${WIDGET_PREFIX}${item.position}-${si}-${wi}`;
              if (selectedWidgetIds.has(id)) {
                widgets.push(structuredClone(slot[wi]!));
                if (sourceSectionPos === null) sourceSectionPos = item.position;
                deletions.push({ sectionPos: item.position, slotIndex: si, widgetIndex: wi });
              }
            }
          }
        }
        if (widgets.length > 0 && sourceSectionPos !== null) {
          const clip: WidgetClipboard = { widgets, sourceSectionPos };
          setClipboard(clip);
          navigator.clipboard.writeText(JSON.stringify(clip)).catch(() => {});
          deletions.sort((a, b) => {
            if (a.sectionPos !== b.sectionPos) return b.sectionPos - a.sectionPos;
            if (a.slotIndex !== b.slotIndex) return b.slotIndex - a.slotIndex;
            return b.widgetIndex - a.widgetIndex;
          });
          for (const d of deletions) {
            onDeleteWidgetRef.current?.(d.sectionPos, d.slotIndex, d.widgetIndex);
          }
        }
        clearSelection();
        return;
      }

      if (e.ctrlKey && e.key === "v" && clipboard && activePasteTarget && onPasteWidgets) {
        e.preventDefault();
        if (activePasteTarget.sectionPos === clipboard.sourceSectionPos) {
          setPasteConfirm({ sectionPos: activePasteTarget.sectionPos, slotIndex: activePasteTarget.slotIndex, widgets: clipboard.widgets });
        } else {
          onPasteWidgets(activePasteTarget.sectionPos, activePasteTarget.slotIndex, clipboard.widgets);
        }
        return;
      }

      if (e.key === "Escape") {
        clearSelection();
      }
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [selectedWidgetIds, clipboard, activePasteTarget, onPasteWidgets, clearSelection]);

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      const { active, over } = event;
      if (!over || active.id === over.id) return;

      const activeId = String(active.id);
      const overId = String(over.id);

      // Section reorder
      if (
        activeId.startsWith(SECTION_PREFIX) &&
        overId.startsWith(SECTION_PREFIX)
      ) {
        const fromIdx = parseInt(activeId.slice(SECTION_PREFIX.length));
        const toIdx = parseInt(overId.slice(SECTION_PREFIX.length));
        if (!isNaN(fromIdx) && !isNaN(toIdx)) {
          onMoveSection?.(fromIdx, toIdx);
        }
        return;
      }

      // Widget move
      if (activeId.startsWith(WIDGET_PREFIX)) {
        const from = parseWidgetId(activeId);
        if (!from) return;

        let to: { sectionPos: number; slotIndex: number; widgetIndex: number };

        if (overId.startsWith(WIDGET_PREFIX)) {
          const parsed = parseWidgetId(overId);
          if (!parsed) return;
          to = parsed;
        } else if (overId.startsWith(SLOT_PREFIX)) {
          const parsed = parseSlotId(overId);
          if (!parsed) return;
          // Append to end of target slot
          const targetSection = sortedPlan.find(
            (s) => s.position === parsed.sectionPos,
          );
          const endIdx = targetSection?.slots[parsed.slotIndex]?.length ?? 0;
          to = { ...parsed, widgetIndex: endIdx };
        } else {
          return;
        }

        onMoveWidget?.(from, to);
      }
    },
    [sortedPlan, onMoveSection, onMoveWidget],
  );

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      onDragEnd={handleDragEnd}
    >
      <div className="flex flex-col gap-4 h-full min-h-0">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-foreground">
            Section Plan
            <span className="ml-2 text-muted-foreground font-normal">
              ({plan.length} sections)
            </span>
          </h2>
          {warnings.length > 0 && (
            <Badge className="bg-warning/10 text-warning border-transparent">
              {warnings.length} warning{warnings.length > 1 ? "s" : ""}
            </Badge>
          )}
        </div>

        {warnings.length > 0 && (
          <ul className="flex flex-col gap-1">
            {warnings.map((w) => (
              <li
                key={w}
                className="text-xs text-warning bg-warning/10 px-3 py-2 rounded-md"
              >
                ⚠ {w}
              </li>
            ))}
          </ul>
        )}

        <SortableContext
          items={sectionIds}
          strategy={verticalListSortingStrategy}
        >
          <div className="flex flex-col gap-2 overflow-y-auto flex-1 min-h-0 pr-1 scrollbar-thin">
            {sortedPlan.map((item) => (
              <SectionPlanCard
                key={item.position}
                item={item}
                sectionDragId={
                  onMoveSection
                    ? `${SECTION_PREFIX}${item.position}`
                    : undefined
                }
                onRemove={
                  onRemoveSection
                    ? () => onRemoveSection(item.position)
                    : undefined
                }
                onAddWidget={
                  onAddWidget
                    ? (slotIdx, widgetType) =>
                        onAddWidget(item.position, slotIdx, widgetType)
                    : undefined
                }
                onDeleteWidget={
                  onDeleteWidget
                    ? (slotIdx, widgetIdx) =>
                        onDeleteWidget(item.position, slotIdx, widgetIdx)
                    : undefined
                }
                onUpdateWidget={
                  onUpdateWidget
                    ? (slotIdx, widgetIdx, patch) =>
                        onUpdateWidget(item.position, slotIdx, widgetIdx, patch)
                    : undefined
                }
                selectedWidgetIds={selectedWidgetIds}
                onToggleSelect={toggleSelect}
                activePasteTarget={activePasteTarget}
                onFocusSlot={focusSlot}
              />
            ))}
            {onAddSection && (
              <AddSectionMenu
                onSelect={(sectionType) =>
                  onAddSection(sortedPlan.length, sectionType)
                }
              />
            )}
          </div>
        </SortableContext>

        {pasteConfirm && (
          <div className="flex flex-col gap-3 p-4 rounded-lg border border-warning/40 bg-warning/5">
            <p className="text-xs text-foreground">
              Paste {pasteConfirm.widgets.length} widget{pasteConfirm.widgets.length !== 1 ? "s" : ""} into the same section they were copied from?
            </p>
            <div className="flex gap-2 self-end">
              <Button variant="outline" size="sm" onClick={() => setPasteConfirm(null)}>
                Cancel
              </Button>
              <Button size="sm" onClick={() => {
                onPasteWidgets?.(pasteConfirm.sectionPos, pasteConfirm.slotIndex, pasteConfirm.widgets);
                setPasteConfirm(null);
              }}>
                Paste
              </Button>
            </div>
          </div>
        )}

        <div className="flex flex-col gap-3 pt-3 border-t border-border shrink-0">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(e) => setConfirmed(e.target.checked)}
              className="accent-primary"
            />
            <span className="text-xs text-muted-foreground">
              I have reviewed the plan
            </span>
          </label>
          <Button onClick={onExecute} disabled={!confirmed || isExecuting}>
            {isExecuting ? "Executing…" : "Execute Migration"}
          </Button>
        </div>
      </div>
    </DndContext>
  );
}

// ── ID parsing helpers ─────────────────────────────────────────────────────────

function parseWidgetId(
  id: string,
): { sectionPos: number; slotIndex: number; widgetIndex: number } | null {
  const parts = id.split("-");
  if (parts.length !== 4 || parts[0] !== "widget") return null;
  const [sectionPos, slotIndex, widgetIndex] = [
    parseInt(parts[1]!),
    parseInt(parts[2]!),
    parseInt(parts[3]!),
  ];
  if (isNaN(sectionPos) || isNaN(slotIndex) || isNaN(widgetIndex)) return null;
  return { sectionPos, slotIndex, widgetIndex };
}

function parseSlotId(
  id: string,
): { sectionPos: number; slotIndex: number } | null {
  const parts = id.split("-");
  if (parts.length !== 3 || parts[0] !== "slot") return null;
  const [sectionPos, slotIndex] = [parseInt(parts[1]!), parseInt(parts[2]!)];
  if (isNaN(sectionPos) || isNaN(slotIndex)) return null;
  return { sectionPos, slotIndex };
}

function getRangeInSlot(
  anchorId: string,
  clickedId: string,
  plan: SectionPlanItem[],
): string[] {
  const a = parseWidgetId(anchorId);
  const b = parseWidgetId(clickedId);
  if (!a || !b || a.sectionPos !== b.sectionPos || a.slotIndex !== b.slotIndex) {
    return [clickedId];
  }
  const section = plan.find((s) => s.position === a.sectionPos);
  const slotLen = section?.slots[a.slotIndex]?.length ?? 0;
  const start = Math.min(a.widgetIndex, b.widgetIndex);
  const end = Math.min(Math.max(a.widgetIndex, b.widgetIndex), slotLen - 1);
  const ids: string[] = [];
  for (let wi = start; wi <= end; wi++) {
    ids.push(`${WIDGET_PREFIX}${a.sectionPos}-${a.slotIndex}-${wi}`);
  }
  return ids;
}

export { WIDGET_PREFIX, SLOT_PREFIX };
