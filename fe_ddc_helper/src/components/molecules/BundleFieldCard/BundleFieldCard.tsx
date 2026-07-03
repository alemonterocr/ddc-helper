/**
 * Reusable card for one group of dealer-bundle fields. Used twice in the
 * intake review step (Questionnaire + Precursive Project) and again in the
 * read-only `GMSetupBlock` on the BuySell / Prebuild dashboards.
 *
 * Each field is rendered as a label + editable Input. The card carries one
 * "Verify in Salesforce" link in its header rather than per-field links.
 */

import { ExternalLink } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Field, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"

export interface BundleField {
  /** Stable id, used as React key + for the input. */
  id: string
  label: string
  value: string
  onChange?: (next: string) => void
  /** Render value read-only (no Input). */
  readOnly?: boolean
  placeholder?: string
}

interface BundleFieldCardProps {
  title: string
  /** Salesforce verify URL. Omit to hide the link. */
  verifyUrl?: string
  fields: BundleField[]
}

export function BundleFieldCard({ title, verifyUrl, fields }: BundleFieldCardProps) {
  return (
    <Card className="gap-3 px-4 py-4">
      <CardHeader className="p-0 flex flex-row items-center justify-between gap-2">
        <CardTitle className="text-xs text-muted-foreground">
          {title}
        </CardTitle>
        {verifyUrl && (
          <Button
            variant="ghost"
            size="sm"
            className="h-6 px-2 text-[11px] text-muted-foreground hover:text-foreground"
            asChild
          >
            <a href={verifyUrl} target="_blank" rel="noreferrer noopener">
              <ExternalLink size={11} className="mr-1" />
              Verify in Salesforce
            </a>
          </Button>
        )}
      </CardHeader>
      <CardContent className="p-0 flex flex-col gap-3">
        {fields.map((f) => (
          <Field key={f.id}>
            <FieldLabel htmlFor={f.id} className="text-[11px] text-muted-foreground">
              {f.label}
            </FieldLabel>
            {f.readOnly ? (
              <div
                id={f.id}
                className="text-xs px-2 py-1.5 rounded-md bg-muted/40 break-all"
              >
                {f.value || "-"}
              </div>
            ) : (
              <Input
                id={f.id}
                value={f.value}
                onChange={(e) => f.onChange?.(e.target.value)}
                placeholder={f.placeholder ?? "-"}
                className="h-8 text-xs"
              />
            )}
          </Field>
        ))}
      </CardContent>
    </Card>
  )
}
