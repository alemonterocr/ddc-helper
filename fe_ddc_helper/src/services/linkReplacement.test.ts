import { describe, it, expect } from 'vitest'
import { applyLinkReplacements } from './linkReplacement'
import type { SectionPlanItem } from '../types'

function makeSection(html: string): SectionPlanItem {
  return {
    section_type: 'empty-one',
    position: 0,
    intent: 'test',
    slots: [[{ widget_type: 'content', html }]],
  }
}

describe('applyLinkReplacements', () => {
  it('returns the same plan when no replacements are provided', () => {
    const plan = [makeSection('<a href="/old">x</a>')]
    expect(applyLinkReplacements(plan, {})).toBe(plan)
  })

  it('ignores empty/whitespace-only replacements', () => {
    const plan = [makeSection('<a href="/old">x</a>')]
    const result = applyLinkReplacements(plan, { '/old': '   ' })
    expect(result).toBe(plan)
  })

  it('replaces an internal link without adding target', () => {
    const plan = [makeSection('<a href="/searchnew.aspx">Cars</a>')]
    const result = applyLinkReplacements(plan, { '/searchnew.aspx': '/new-inventory/index.htm' })
    expect(result[0]!.slots[0]![0]!.html).toBe('<a href="/new-inventory/index.htm">Cars</a>')
  })

  it('adds target="_blank" for external replacements', () => {
    const plan = [makeSection('<a href="/promo">Promo</a>')]
    const result = applyLinkReplacements(plan, { '/promo': 'https://example.com/promo' })
    expect(result[0]!.slots[0]![0]!.html).toBe('<a href="https://example.com/promo" target="_blank">Promo</a>')
  })

  it('strips an existing target before replacing', () => {
    const plan = [makeSection('<a href="/x" target="_blank" class="btn">go</a>')]
    const result = applyLinkReplacements(plan, { '/x': '/y' })
    expect(result[0]!.slots[0]![0]!.html).toBe('<a href="/y" class="btn">go</a>')
  })

  it('replaces every occurrence (regex /g)', () => {
    const plan = [makeSection('<a href="/x">a</a> | <a href="/x">b</a>')]
    const result = applyLinkReplacements(plan, { '/x': '/y' })
    expect(result[0]!.slots[0]![0]!.html).toBe('<a href="/y">a</a> | <a href="/y">b</a>')
  })

  it('escapes regex-special characters in the original href', () => {
    const plan = [makeSection('<a href="/path.aspx?id=1">x</a>')]
    const result = applyLinkReplacements(plan, { '/path.aspx?id=1': '/new' })
    expect(result[0]!.slots[0]![0]!.html).toBe('<a href="/new">x</a>')
  })

  it('does not mutate the input plan', () => {
    const original = '<a href="/x">go</a>'
    const plan = [makeSection(original)]
    applyLinkReplacements(plan, { '/x': '/y' })
    expect(plan[0]!.slots[0]![0]!.html).toBe(original)
  })

  it('leaves non-content widgets untouched', () => {
    const plan: SectionPlanItem[] = [{
      section_type: 'empty-one',
      position: 0,
      intent: 'img',
      slots: [[{ widget_type: 'image', source_url: 'https://cdn/img.jpg' }]],
    }]
    const result = applyLinkReplacements(plan, { '/x': '/y' })
    expect(result[0]!.slots[0]![0]).toEqual(plan[0]!.slots[0]![0])
  })

  it('preserves widgets without an html field', () => {
    const plan: SectionPlanItem[] = [{
      section_type: 'empty-one',
      position: 0,
      intent: 'empty content',
      slots: [[{ widget_type: 'content' }]],
    }]
    const result = applyLinkReplacements(plan, { '/x': '/y' })
    expect(result[0]!.slots[0]![0]).toEqual(plan[0]!.slots[0]![0])
  })
})
