import type { SectionPlanItem, ColumnWidget } from '../types'

export const SECTION_SLOT_COUNTS: Record<string, number> = {
  'empty-one': 1,
  'empty-fifty-fifty': 2,
  'empty-66-33': 2,
  'empty-33-66': 2,
  'empty-thirds': 3,
  'empty-fourths': 4,
  'empty-fifths': 5,
  'map-hours': 0,
}

export const COLUMN_RATIOS: Record<string, number[]> = {
  'empty-one': [1],
  'empty-fifty-fifty': [1, 1],
  'empty-66-33': [2, 1],
  'empty-33-66': [1, 2],
  'empty-thirds': [1, 1, 1],
  'empty-fourths': [1, 1, 1, 1],
  'empty-fifths': [1, 1, 1, 1, 1],
  'map-hours': [],
}

export function slotCountForType(sectionType: string): number {
  return SECTION_SLOT_COUNTS[sectionType] ?? 0
}

export function emptySlotsForType(sectionType: string): ColumnWidget[][] {
  const n = slotCountForType(sectionType)
  return Array.from({ length: n }, () => [])
}

export function reindexPlan(plan: SectionPlanItem[]): SectionPlanItem[] {
  return plan.map((item, idx) =>
    item.position === idx ? item : { ...item, position: idx },
  )
}

export const DEFAULT_CONTENT_WIDGET: ColumnWidget = {
  widget_type: 'content',
  html: '<p>New content</p>',
}

export const DEFAULT_IMAGE_WIDGET: ColumnWidget = {
  widget_type: 'image',
  source_url: '',
}

export function defaultWidgetForType(widgetType: string): ColumnWidget {
  switch (widgetType) {
    case 'content': return { ...DEFAULT_CONTENT_WIDGET }
    case 'image':   return { ...DEFAULT_IMAGE_WIDGET }
    case 'links':   return { widget_type: 'links', buttons: [] }
    default:        return { widget_type: widgetType as ColumnWidget['widget_type'] }
  }
}

export function makeSection(sectionType: string, position: number): SectionPlanItem {
  return {
    section_type: sectionType,
    position,
    intent: 'User-added section',
    slots: emptySlotsForType(sectionType),
  }
}
