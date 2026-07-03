import { useState } from 'react'
import type { ColumnWidget, ButtonDTO } from '../../../types'

interface WidgetEditorProps {
  widget: ColumnWidget
  onSave: (patch: Partial<ColumnWidget>) => void
  onCancel: () => void
}

export function WidgetEditor({ widget, onSave, onCancel }: WidgetEditorProps) {
  const wt = widget.widget_type

  return (
    <div className="flex flex-col gap-2 p-3 rounded-md border border-border bg-background">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-foreground">Edit widget</span>
        <button
          onClick={onCancel}
          className="text-xs text-muted-foreground hover:text-foreground cursor-pointer"
        >
          cancel
        </button>
      </div>

      {wt === 'content' && (
        <ContentEditor widget={widget} onSave={onSave} onCancel={onCancel} />
      )}
      {wt === 'image' && (
        <ImageEditor widget={widget} onSave={onSave} onCancel={onCancel} />
      )}
      {wt === 'links' && (
        <LinksEditor widget={widget} onSave={onSave} onCancel={onCancel} />
      )}
      {(wt === 'form' || wt === 'contact_info' || wt === 'hours') && (
        <ZeroConfigNote wt={wt} />
      )}
    </div>
  )
}

function ZeroConfigNote({ wt }: { wt: string }) {
  return (
    <p className="text-xs text-muted-foreground italic">
      {wt} is pre-wired — DDC fills this automatically from dealer settings.
      No configuration needed.
    </p>
  )
}

// ── Content editor ─────────────────────────────────────────────────────────────

function ContentEditor({ widget, onSave, onCancel }: Pick<WidgetEditorProps, 'widget' | 'onSave' | 'onCancel'>) {
  const [html, setHtml] = useState(widget.html ?? '')

  return (
    <>
      <textarea
        value={html}
        onChange={e => setHtml(e.target.value)}
        className="w-full rounded border border-border bg-card text-xs text-foreground font-mono p-2 resize-y min-h-[80px] focus:outline-none focus:border-ring"
        rows={6}
        placeholder="<p>Edit content HTML here…</p>"
      />
      <div className="flex justify-end gap-2">
        <button onClick={onCancel} className="text-xs text-muted-foreground hover:text-foreground cursor-pointer">
          Cancel
        </button>
        <button
          onClick={() => onSave({ html })}
          className="text-xs px-3 py-1.5 rounded bg-primary hover:bg-primary/90 text-primary-foreground font-medium cursor-pointer"
        >
          Save
        </button>
      </div>
    </>
  )
}

// ── Image editor ───────────────────────────────────────────────────────────────

function ImageEditor({ widget, onSave, onCancel }: Pick<WidgetEditorProps, 'widget' | 'onSave' | 'onCancel'>) {
  const [url, setUrl] = useState(widget.source_url ?? '')

  return (
    <>
      <div className="flex flex-col gap-1">
        <label className="text-xs text-muted-foreground">Image URL</label>
        <input
          type="text"
          value={url}
          onChange={e => setUrl(e.target.value)}
          className="w-full rounded border border-border bg-card text-xs text-foreground font-mono px-2 py-1.5 focus:outline-none focus:border-ring"
          placeholder="https://example.com/photo.jpg"
        />
      </div>
      {url && (
        <div className="rounded border border-border overflow-hidden">
          <img
            src={url}
            alt="preview"
            className="w-full max-h-40 object-contain bg-background"
            onError={e => {
              const t = e.currentTarget
              t.style.display = 'none'
              const p = t.parentElement
              if (p) p.innerHTML = '<p class="text-xs text-destructive p-3">Could not load image preview</p>'
            }}
          />
        </div>
      )}
      <div className="flex justify-end gap-2">
        <button onClick={onCancel} className="text-xs text-muted-foreground hover:text-foreground cursor-pointer">
          Cancel
        </button>
        <button
          onClick={() => onSave({ source_url: url })}
          className="text-xs px-3 py-1.5 rounded bg-primary hover:bg-primary/90 text-primary-foreground font-medium cursor-pointer"
        >
          Save
        </button>
      </div>
    </>
  )
}

// ── Links editor ───────────────────────────────────────────────────────────────

const LINK_STYLES: ButtonDTO['style'][] = ['primary', 'secondary', 'outline']
const LINK_TARGETS: ButtonDTO['target'][] = ['_self', '_top', '_blank']

function LinksEditor({ widget, onSave, onCancel }: Pick<WidgetEditorProps, 'widget' | 'onSave' | 'onCancel'>) {
  const [buttons, setButtons] = useState<ButtonDTO[]>(
    (widget.buttons ?? []).map(b => ({ ...b })),
  )

  function updateButton(idx: number, patch: Partial<ButtonDTO>) {
    setButtons(prev => prev.map((b, i) => (i === idx ? { ...b, ...patch } : b)))
  }

  function addButton() {
    setButtons(prev => [
      ...prev,
      { text: '', href: '', style: 'primary', target: '_self', link_class: '' },
    ])
  }

  function removeButton(idx: number) {
    setButtons(prev => prev.filter((_, i) => i !== idx))
  }

  return (
    <div className="flex flex-col gap-2">
      {buttons.map((btn, idx) => (
        <div key={idx} className="flex flex-col gap-1.5 p-2 rounded border border-border bg-card">
          <div className="flex items-center justify-between">
            <span className="text-xs text-muted-foreground font-mono">Button {idx + 1}</span>
            <button
              onClick={() => removeButton(idx)}
              className="text-xs text-destructive hover:text-destructive/80 cursor-pointer"
            >
              remove
            </button>
          </div>
          <div className="flex gap-2">
            <div className="flex flex-col gap-1 flex-1">
              <label className="text-xs text-muted-foreground">Label</label>
              <input
                type="text"
                value={btn.text}
                onChange={e => updateButton(idx, { text: e.target.value })}
                className="rounded border border-border bg-background text-xs text-foreground px-2 py-1 focus:outline-none focus:border-ring"
                placeholder="Button text"
              />
            </div>
            <div className="flex flex-col gap-1 flex-1">
              <label className="text-xs text-muted-foreground">URL</label>
              <input
                type="text"
                value={btn.href}
                onChange={e => updateButton(idx, { href: e.target.value })}
                className="rounded border border-border bg-background text-xs text-foreground px-2 py-1 font-mono focus:outline-none focus:border-ring"
                placeholder="/path or https://..."
              />
            </div>
          </div>
          <div className="flex gap-2">
            <div className="flex flex-col gap-1">
              <label className="text-xs text-muted-foreground">Style</label>
              <select
                value={btn.style ?? 'primary'}
                onChange={e => updateButton(idx, { style: e.target.value as ButtonDTO['style'] })}
                className="rounded border border-border bg-background text-xs text-foreground px-2 py-1 focus:outline-none"
              >
                {LINK_STYLES.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-muted-foreground">Target</label>
              <select
                value={btn.target ?? '_self'}
                onChange={e => updateButton(idx, { target: e.target.value as ButtonDTO['target'] })}
                className="rounded border border-border bg-background text-xs text-foreground px-2 py-1 focus:outline-none"
              >
                {LINK_TARGETS.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
          </div>
        </div>
      ))}

      <button
        onClick={addButton}
        className="text-xs text-primary hover:underline border border-dashed border-border rounded py-1 cursor-pointer"
      >
        + add button
      </button>

      <div className="flex justify-end gap-2 mt-1">
        <button onClick={onCancel} className="text-xs text-muted-foreground hover:text-foreground cursor-pointer">
          Cancel
        </button>
        <button
          onClick={() => onSave({ buttons })}
          className="text-xs px-3 py-1.5 rounded bg-primary hover:bg-primary/90 text-primary-foreground font-medium cursor-pointer"
        >
          Save
        </button>
      </div>
    </div>
  )
}
