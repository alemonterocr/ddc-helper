/**
 * Step 4 of GMIntakeWizard (Prebuild only).
 *
 * Ingests the source dealer site's navigation HTML, sends it to /parse-nav
 * (the existing nav-parsing LangGraph), and returns the distilled general
 * pages. The wizard then attaches these pages to the new project.
 *
 * BuySell projects skip this step. The wizard wires that branching.
 *
 * Controlled by the wizard — baseUrl / navHtml live in the wizard and the
 * action buttons (Back / Create project) render in the wizard's CardFooter.
 */

import { Field, FieldDescription, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { InputGroup, InputGroupTextarea } from "@/components/ui/input-group"

export interface NavStepValues {
  baseUrl: string
  navHtml: string
}

interface IntakeStepNavProps {
  baseUrl: string
  navHtml: string
  onBaseUrlChange: (next: string) => void
  onNavHtmlChange: (next: string) => void
  isLoading: boolean
  error?: string
}

export function IntakeStepNav({
  baseUrl,
  navHtml,
  onBaseUrlChange,
  onNavHtmlChange,
  isLoading,
  error,
}: IntakeStepNavProps) {
  return (
    <div className="flex flex-col gap-5">
      <div className="text-xs text-muted-foreground">
        Paste the source dealer site's navigation HTML. We'll distill it into the
        page list. The base URL resolves any relative hrefs.
      </div>

      <Field>
        <FieldLabel htmlFor="intake-nav-base">Source site base URL</FieldLabel>
        <Input
          id="intake-nav-base"
          value={baseUrl}
          onChange={(e) => onBaseUrlChange(e.target.value)}
          placeholder="https://www.bullgmc.com"
          autoComplete="off"
          disabled={isLoading}
        />
        <FieldDescription>
          Prefilled from the questionnaire's Primary URL if available.
        </FieldDescription>
      </Field>

      <Field>
        <FieldLabel htmlFor="intake-nav-html">Navigation HTML</FieldLabel>
        <InputGroup>
          <InputGroupTextarea
            id="intake-nav-html"
            value={navHtml}
            onChange={(e) => onNavHtmlChange(e.target.value)}
            placeholder='<nav class="main-nav">...</nav>'
            rows={10}
            disabled={isLoading}
            className="min-h-32 max-h-72 resize-none overflow-y-auto scrollbar-thin"
          />
        </InputGroup>
        <FieldDescription>
          Inspect the source site, copy outerHTML on the &lt;nav&gt; element.
        </FieldDescription>
      </Field>

      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  )
}
