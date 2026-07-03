import { describe, it, expect } from 'vitest'
import {
  reindexPlan,
  slotCountForType,
  emptySlotsForType,
  defaultWidgetForType,
  makeSection,
  SECTION_SLOT_COUNTS,
} from './planEdit'
import type { SectionPlanItem } from '../types'

function planItem(overrides: Partial<SectionPlanItem> = {}): SectionPlanItem {
  return {
    section_type: 'empty-one',
    position: 0,
    intent: 'test',
    slots: [[]],
    ...overrides,
  }
}

describe('reindexPlan', () => {
  it('assigns contiguous 0-based positions', () => {
    const result = reindexPlan([
      planItem({ position: 5 }),
      planItem({ position: 2 }),
      planItem({ position: 99 }),
    ])
    expect(result.map(p => p.position)).toEqual([0, 1, 2])
  })

  it('preserves item identities when positions are already correct', () => {
    const plan = [
      planItem({ position: 0 }),
      planItem({ position: 1 }),
    ]
    const result = reindexPlan(plan)
    expect(result[0]).toBe(plan[0])
    expect(result[1]).toBe(plan[1])
  })

  it('returns new array when positions need fixing', () => {
    const plan = [planItem({ position: 0 }), planItem({ position: 0 })]
    const result = reindexPlan(plan)
    expect(result).not.toBe(plan)
    expect(result[0]!.position).toBe(0)
    expect(result[1]!.position).toBe(1)
  })

  it('handles empty array', () => {
    expect(reindexPlan([])).toEqual([])
  })
})

describe('slotCountForType', () => {
  it('returns the correct count for each section type', () => {
    expect(slotCountForType('empty-one')).toBe(1)
    expect(slotCountForType('empty-fifty-fifty')).toBe(2)
    expect(slotCountForType('empty-66-33')).toBe(2)
    expect(slotCountForType('empty-33-66')).toBe(2)
    expect(slotCountForType('empty-thirds')).toBe(3)
    expect(slotCountForType('empty-fourths')).toBe(4)
    expect(slotCountForType('empty-fifths')).toBe(5)
    expect(slotCountForType('map-hours')).toBe(0)
  })

  it('returns 0 for unknown types', () => {
    expect(slotCountForType('not-a-type')).toBe(0)
  })
})

describe('emptySlotsForType', () => {
  it('returns correct empty slot arrays', () => {
    expect(emptySlotsForType('empty-one')).toEqual([[]])
    expect(emptySlotsForType('empty-fifty-fifty')).toEqual([[], []])
    expect(emptySlotsForType('map-hours')).toEqual([])
  })
})

describe('defaultWidgetForType', () => {
  it('returns content widget with default HTML', () => {
    const w = defaultWidgetForType('content')
    expect(w.widget_type).toBe('content')
    expect(w.html).toBe('<p>New content</p>')
  })

  it('returns image widget with empty source_url', () => {
    const w = defaultWidgetForType('image')
    expect(w.widget_type).toBe('image')
    expect(w.source_url).toBe('')
  })

  it('returns links widget with empty buttons', () => {
    const w = defaultWidgetForType('links')
    expect(w.widget_type).toBe('links')
    expect(w.buttons).toEqual([])
  })

  it('returns zero-config widget for form/contact_info/hours', () => {
    expect(defaultWidgetForType('form').widget_type).toBe('form')
    expect(defaultWidgetForType('contact_info').widget_type).toBe('contact_info')
    expect(defaultWidgetForType('hours').widget_type).toBe('hours')
  })
})

describe('makeSection', () => {
  it('creates a section with correct defaults', () => {
    const s = makeSection('empty-thirds', 3)
    expect(s.section_type).toBe('empty-thirds')
    expect(s.position).toBe(3)
    expect(s.intent).toBe('User-added section')
    expect(s.slots).toEqual([[], [], []])
  })

  it('map-hours creates 0 slots', () => {
    const s = makeSection('map-hours', 0)
    expect(s.slots).toEqual([])
  })
})

describe('SECTION_SLOT_COUNTS', () => {
  it('covers all DDC layout types', () => {
    expect(Object.keys(SECTION_SLOT_COUNTS).sort()).toEqual([
      'empty-33-66',
      'empty-66-33',
      'empty-fifths',
      'empty-fifty-fifty',
      'empty-fourths',
      'empty-one',
      'empty-thirds',
      'map-hours',
    ])
  })
})
