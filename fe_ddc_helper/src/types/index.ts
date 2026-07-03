/**
 * Shared type contract between the FE Chrome extension and the BE FastAPI.
 *
 * These types must match the BE Pydantic models in `be_ddc_helper`:
 *   - `DOMNode`           ⇄ `domain/models/dom_skeleton.py`
 *   - `DOMSkeleton`       ⇄ `domain/models/dom_skeleton.py`
 *   - `ColumnWidget`      ⇄ `domain/models/section_plan.py`
 *   - `SectionPlanItem`   ⇄ `domain/models/section_plan.py`
 *   - `AnalyzeRequest`    ⇄ `adapters/inbound/http/analyze_router.py`
 *   - `AnalyzeResponse`   ⇄ `adapters/inbound/http/analyze_router.py`
 *   - `ExecuteRequest`    ⇄ `adapters/inbound/http/execute_router.py`
 *   - `ExecuteResponse`   ⇄ `adapters/inbound/http/execute_router.py`
 *
 * When changing either side, change both. The execute side's `ColumnWidgetDTO`
 * also accepts `raw_html` as a backward-compat alias for `html` — included
 * here for completeness.
 */

// ── LLM provider ─────────────────────────────────────────────────────────────

export type LLMProvider = 'anthropic' | 'gemini' | 'deepseek'

// ── Migration step state machine ─────────────────────────────────────────────

export type MigrationStep =
  | 'idle'
  | 'capturing'
  | 'defining_structure'
  | 'conceiving_widgets'
  | 'reviewing'
  | 'executing'
  | 'done'
  | 'error'

// ── DOM skeleton ─────────────────────────────────────────────────────────────

/**
 * A single node in the FE-captured DOM skeleton. Either a real HTML element or
 * a `#text` pseudo-child emitted by the walker for mixed-inline content (see
 * `scripts/extractSkeleton.ts`).
 *
 * Real-element nodes carry the full attribute and geometry set. `#text` nodes
 * carry only `tag === '#text'`, `text`, and an empty `children` array; all
 * other fields are absent.
 */
export interface DOMNode {
  /** Lowercase HTML tag name, or the literal `'#text'` for inline text pseudo-children. */
  tag: string
  /** `class` attribute, lowercase preserved. Empty string when none. */
  cls: string
  /** Layout-relevant inline styles only (display, width, flex, grid family). */
  style?: string
  /** Computed background-color, only present when distinct from parent. */
  bg?: string
  /** Trimmed `textContent` for pure-text leaves. Empty when the element has element children. */
  text: string
  /** Resolved absolute URL — present only on `<img>` elements that have one. */
  src?: string
  /** Resolved absolute URL — present only on `<a>` elements. */
  href?: string
  /** `target` attribute — present only on `<a>` elements. `_self`/`_top`/`_blank`. */
  target?: string
  /** `role` attribute — captured for any element so styled-`<div>` buttons can be detected. */
  role?: string

  // ── Geometry (document-relative, rounded ints) ─────────────────────────────
  /** Document-relative x (viewport x + scrollX). */
  x: number
  /** Document-relative y (viewport y + scrollY). */
  y: number
  /** Width in CSS px. */
  w: number
  /** Height in CSS px. */
  h: number

  // ── Computed-style signals ─────────────────────────────────────────────────
  /** True when `background-image` is set (not `none`). */
  bgImage?: boolean
  /** Resolved background-image URL with query string stripped. */
  bgImageSrc?: string
  /** Computed font-size in px. */
  fontSize?: number

  /** Direct element children + interleaved `#text` pseudo-children, in document order. */
  children: DOMNode[]
}

/** Top-level skeleton emitted by the FE walker for a single captured page. */
export interface DOMSkeleton {
  /** Absolute URL of the captured page (`window.location.href`). */
  url: string
  /** `document.title` at capture time. */
  title: string
  /** Root of the skeleton tree, anchored at the first content-bearing element. */
  structure: DOMNode
  /** First 80,000 chars of `root.innerHTML` — debug/fallback snapshot. */
  raw_html?: string
}

// ── Widgets ──────────────────────────────────────────────────────────────────

/**
 * Valid widget types the BE produces and the execute layer accepts.
 *
 *   - `content`      — HTML chunk, uses `html`
 *   - `image`        — image, uses `source_url`
 *   - `form`         — Contact form marker, no payload (DDC fills server-side)
 *   - `contact_info` — Dealer identity marker, no payload (DDC fills from master record)
 *   - `hours`        — Business hours marker, no payload (DDC fills from master record)
 *   - `links`        — Buttons, uses `buttons`
 */
export type WidgetType =
  | 'content'
  | 'image'
  | 'form'
  | 'contact_info'
  | 'hours'
  | 'links'

/** Button entry for a `links` widget. Mirrors `execute_router.ButtonDTO`. */
export interface ButtonDTO {
  /** Visible button label. */
  text: string
  /** Destination URL or path. */
  href: string
  /** DDC button style preset. Defaults to `primary` when omitted. */
  style?: 'primary' | 'secondary' | 'outline'
  /** Anchor target. Defaults to `_self` when omitted. */
  target?: '_self' | '_top' | '_blank'
  /** DDC-specific class marker (e.g. `BLANK`). Empty string by default. */
  link_class?: string
}

/**
 * A single widget within one DDC slot.
 *
 * Field presence by `widget_type`:
 *   - `content`      → `html` (or `raw_html` as a legacy alias the BE tolerates)
 *   - `image`        → `source_url`
 *   - `links`        → `buttons`
 *   - `form` / `contact_info` / `hours` → no payload (DDC fills server-side)
 */
export interface ColumnWidget {
  widget_type: WidgetType
  /** HTML to inject into a content widget. */
  html?: string
  /** Legacy alias for `html` — execute side accepts either. New code should use `html`. */
  raw_html?: string
  /** Original image URL to upload to the DDC media library. */
  source_url?: string
  /** Buttons for a `links` widget. */
  buttons?: ButtonDTO[]
}

/** One DDC section — a layout type and N column slots, each holding N stacked widgets. */
export interface SectionPlanItem {
  /** DDC layout name, e.g. `empty-one`, `empty-66-33`. Must match a `sectionName` in the catalog. */
  section_type: string
  /** Zero-based index of this section within the page. */
  position: number
  /** One-sentence description of what the section does — written by the LLM enricher. */
  intent: string
  /** One inner array per DDC column slot; each inner array holds N stacked widgets. */
  slots: ColumnWidget[][]
}

// ── Credentials ──────────────────────────────────────────────────────────────

export interface CredentialStatus {
  ready: boolean
  ccIdtToken: string | null
  createdBy: string | null
  hasLLMKey: boolean
  llmProvider: LLMProvider | null
  mediaLibTabId: number | null
  missing: string[]
}

// ── API: configure key ───────────────────────────────────────────────────────

export interface ConfigureKeyRequest {
  provider: LLMProvider
  api_key: string
}

export interface ConfigureKeyResponse {
  valid: boolean
  provider: LLMProvider
  error?: string
}

// ── API: /analyze ────────────────────────────────────────────────────────────

export interface AnalyzeRequest {
  dom_skeleton: DOMSkeleton
  dealer_id: string
  provider: LLMProvider
  extra_prompt?: string
}

export interface AnalyzeResponse {
  section_plan: SectionPlanItem[]
  warnings: string[]
  page_alias: string
  page_title: string
  token_info: TokenInfo
}

// ── Token accounting ────────────────────────────────────────────────────────

export interface TokenUsage {
  provider: string
  model: string
  stage: string
  input_tokens: number
  output_tokens: number
  cost_usd: number
}

export interface TokenInfo {
  total_input_tokens: number
  total_output_tokens: number
  total_cost_usd: number
  by_stage: TokenUsage[]
}

// ── API: /execute ────────────────────────────────────────────────────────────

export interface ExecuteRequest {
  dealer_id: string
  page_alias: string
  page_title: string
  section_plan: SectionPlanItem[]
}

export interface ExecuteResponse {
  ok: boolean
  page_alias: string
  warnings: string[]
  error?: string
}

// ── API: /parse-staff + /execute-staff ───────────────────────────────────────

export type GMOrCMProjectType = 'cm' | 'gm-prebuild'

export interface StaffMember {
  department: string
  name: string
  title: string | null
  phone: string | null
  email: string | null
  bio: string | null
  has_photo: boolean
  original_photo_url: string | null
  photo: string | null
}

export interface ParseStaffRequest {
  dealer_id: string
  project_type: GMOrCMProjectType
  dom_skeleton: DOMSkeleton
  provider: LLMProvider
}

export interface ParseStaffResponse {
  staff: StaffMember[]
  warnings: string[]
  token_info: TokenInfo
  error?: string
}

export interface ExecuteStaffRequest {
  dealer_id: string
  project_type: GMOrCMProjectType
  page_alias?: string
  page_title?: string
  staff: StaffMember[]
}

export interface ExecuteStaffResponse {
  ok: boolean
  warnings: string[]
  error?: string
}

// ── API: /parse-nav ──────────────────────────────────────────────────────────

export interface ParseNavRequest {
  dealer_id: string
  html: string
  base_url: string
  provider: LLMProvider
}

export interface ParseNavPage {
  title: string
  url: string
  category: 'general' | 'model_specific'
}

export interface ParseNavResponse {
  pages: ParseNavPage[]
  warnings: string[]
  error?: string
}

// ── API: /analyze-deterministic ──────────────────────────────────────────────

export interface DeterministicAnalyzeRequest {
  dom_skeleton: DOMSkeleton
}

export interface DeterministicAnalyzeResponse {
  plan: DeterministicSection[]
}

export interface DeterministicSection {
  section: string
  slots: DeterministicWidget[][]
}

/**
 * Internal algo shape returned by `/analyze-deterministic` (no LLM pipeline).
 *
 * Differs from `ColumnWidget` in two ways:
 *   - Uses `type` instead of `widget_type`
 *   - Uses `url` instead of `source_url` for images
 *
 * The `/analyze` endpoint converts these to `ColumnWidget` shape via the
 * `convert_node` step.
 */
export interface DeterministicWidget {
  /** Limited to widget types `editorial_chunk` can emit deterministically. */
  type: 'content' | 'image' | 'links'
  /** Rendered HTML for `content` widgets. */
  html?: string
  /** Plaintext preview of the content for debugging. */
  preview?: string
  /** Source image URL for `image` widgets. */
  url?: string
  /** Number of source DOM nodes that contributed to a content widget. */
  node_count?: number
  /** Buttons for `links` widgets. */
  buttons?: ButtonDTO[]
}

// ── API: /translations/sanitize + /translations/translate ────────────────────

export interface SanitizeAliasesRequest {
  raw: string
}

export interface SanitizeAliasesResponse {
  aliases: string[]
  dropped: string[]
}

export interface TranslateLabelRequest {
  alias: string
  en_html: string
  dealer_name: string
  provider?: LLMProvider
}

export type LabelTranslationStatus = 'ready' | 'error'

export interface TranslateLabelResponse {
  alias: string
  es_html: string
  status: LabelTranslationStatus
  warnings: string[]
  raw?: string | null
  reasoning?: string
}

// ── DDC label fetch/save (extension-side) ────────────────────────────────────

export interface DDCLabelFetchResult {
  /** Existing en_US value for the alias, or null when absent. */
  en: string | null
  /** Existing es_US value for the alias, or null when absent. */
  es: string | null
  /** Populated only when the request failed. */
  error?: string
}

export interface DDCLabelSaveResult {
  success: boolean
  error?: string
}

// ── Salesforce intake ───────────────────────────────────────────────────────
export type {
  Classification,
  DealerBundle,
  DesignChoice,
  IntakeSource,
  SalesforceIntakeRequest,
  SalesforceIntakeResponse,
} from './salesforceIntake'

// ── Errors ───────────────────────────────────────────────────────────────────
export { BackendError } from './errors'

