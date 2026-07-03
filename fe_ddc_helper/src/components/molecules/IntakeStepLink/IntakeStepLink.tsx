/**
 * Step 1 of GMIntakeWizard. Single URL field.
 *
 * Controlled by the wizard — the URL value and the Continue button live in
 * the wizard's CardFooter so the action row is always pinned at the bottom of
 * the modal regardless of content height.
 */

import { Field, FieldDescription, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"

interface IntakeStepLinkProps {
  url: string
  onUrlChange: (next: string) => void
  error?: string
  onSubmit: () => void
}

export function IntakeStepLink({ url, onUrlChange, error, onSubmit }: IntakeStepLinkProps) {
  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!url.trim()) return
    onSubmit()
  }

  return (
    <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
      <Field>
        <FieldLabel htmlFor="intake-board-url">Salesforce Board URL</FieldLabel>
        <Input
          id="intake-board-url"
          value={url}
          onChange={(e) => onUrlChange(e.target.value)}
          placeholder="https://casfx.lightning.force.com/lightning/r/taskfeed1__Board__c/a9CPe.../view"
          autoComplete="off"
          autoFocus
        />
        <FieldDescription>
          The same link you receive from the project manager. We never close the tab.
        </FieldDescription>
      </Field>

      {error && <p className="text-xs text-destructive">{error}</p>}

      {/* Submit on Enter — invisible button. Actual visible Continue button
          lives in the wizard's CardFooter. */}
      <button type="submit" className="sr-only" tabIndex={-1} aria-hidden>
        Submit
      </button>
    </form>
  )
}
