/**
 * Step 3 of GMIntakeWizard. Editable bundle in two field cards, classification
 * pill with override switch, then Confirm to create the project.
 *
 * BuySell-only fields (new_dealership_name) are only rendered when the
 * effective classification is "buysell".
 */

import { AlertCircle } from "lucide-react"

import { BundleFieldCard, type BundleField } from "@/components/molecules/BundleFieldCard/BundleFieldCard"
import { Badge } from "@/components/ui/badge"
import { Field, FieldLabel } from "@/components/ui/field"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"
import type { DealerBundle } from "@/types"

interface IntakeStepReviewProps {
  bundle: DealerBundle
  onBundleChange: (next: DealerBundle) => void
}

export function IntakeStepReview({
  bundle,
  onBundleChange,
}: IntakeStepReviewProps) {
  const isBuySell = bundle.classification.value === "buysell"

  function patch(partial: Partial<DealerBundle>) {
    onBundleChange({ ...bundle, ...partial })
  }

  function patchClassification(value: "prebuild" | "buysell") {
    onBundleChange({
      ...bundle,
      classification: {
        ...bundle.classification,
        value,
        source: value === bundle.classification.value ? bundle.classification.source : "user-override",
      },
    })
  }

  const questionnaireUrl =
    bundle.source.questionnaire_insight_id && bundle.source.questionnaire_insight_id !== "-"
      ? `https://casfx.lightning.force.com/lightning/r/taskfeed1__Board_Insight__c/${bundle.source.questionnaire_insight_id}/view`
      : undefined

  const projectUrl =
    bundle.source.precursive_project_id && bundle.source.precursive_project_id !== "-"
      ? `https://casfx.lightning.force.com/lightning/r/preempt__PrecursiveProject__c/${bundle.source.precursive_project_id}/view`
      : undefined

  const questionnaireFields: BundleField[] = [
    {
      id: "review-dealer-name",
      label: "Dealership",
      value: bundle.dealership_name,
      onChange: (v) => patch({ dealership_name: v }),
    },
    ...(isBuySell
      ? [{
          id: "review-new-name",
          label: "New name (BuySell)",
          value: bundle.new_dealership_name,
          onChange: (v: string) => patch({ new_dealership_name: v }),
        }]
      : []),
    {
      id: "review-address",
      label: "Address",
      value: bundle.dealership_address,
      onChange: (v) => patch({ dealership_address: v }),
    },
    {
      id: "review-leads-email",
      label: "Leads email",
      value: bundle.leads_email,
      onChange: (v) => patch({ leads_email: v }),
    },
    {
      id: "review-primary-url",
      label: isBuySell ? "Primary URL (seller / current)" : "Primary URL",
      value: bundle.primary_url,
      onChange: (v) => patch({ primary_url: v }),
    },
    ...(isBuySell
      ? [{
          id: "review-new-primary-url",
          label: "New primary URL (buyer)",
          value: bundle.new_primary_url,
          onChange: (v: string) => patch({ new_primary_url: v }),
        }]
      : []),
  ]

  const projectFields: BundleField[] = [
    {
      id: "review-ppr",
      label: "PPR",
      value: bundle.ppr,
      onChange: (v) => patch({ ppr: v }),
    },
    {
      id: "review-dealer-id",
      label: "Dealer Id",
      value: bundle.dealer_id,
      onChange: (v) => patch({ dealer_id: v }),
    },
  ]

  const showLowConfidenceBanner =
    bundle.classification.source === "default" || bundle.classification.confidence < 0.5

  return (
    <div className="flex flex-col gap-5">
      {/* ── Classification header + override ─────────────────────────── */}
      <div className="flex flex-col gap-3">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-2">
            <Badge variant={isBuySell ? "default" : "secondary"}>
              {isBuySell ? "GM BuySell" : "GM Prebuild"}
            </Badge>
            <span className="text-xs text-muted-foreground">
              confidence {bundle.classification.confidence.toFixed(2)} · source {bundle.classification.source}
            </span>
          </div>
          <Field className="w-44">
            <FieldLabel htmlFor="review-class-override" className="text-[10px] text-muted-foreground">
              Override classification
            </FieldLabel>
            <Select value={bundle.classification.value} onValueChange={(v) => patchClassification(v as "prebuild" | "buysell")}>
              <SelectTrigger id="review-class-override" className="h-8 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="prebuild">Prebuild</SelectItem>
                <SelectItem value="buysell">BuySell</SelectItem>
              </SelectContent>
            </Select>
          </Field>
        </div>

        {showLowConfidenceBanner && (
          <div className="flex items-start gap-2 text-[11px] text-amber-600 bg-amber-50 dark:bg-amber-950/30 rounded-md px-3 py-2">
            <AlertCircle size={14} className="shrink-0 mt-0.5" />
            <span>
              {bundle.classification.source === "default"
                ? "Classifier could not run. Please confirm the project type manually."
                : "Low confidence classification. Double-check before continuing."}
            </span>
          </div>
        )}

        {bundle.classification.reasoning && (
          <p className="text-[11px] text-muted-foreground italic">
            "{bundle.classification.reasoning}"
          </p>
        )}
      </div>

      <Separator />

      {/* ── Two editable cards ───────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <BundleFieldCard
          title="Questionnaire"
          verifyUrl={questionnaireUrl}
          fields={questionnaireFields}
        />
        <BundleFieldCard
          title="Precursive Project"
          verifyUrl={projectUrl}
          fields={projectFields}
        />
      </div>

      {/* ── Design choice surface ────────────────────────────────────── */}
      <Separator />
      <DesignChoiceBlock bundle={bundle} />

      {/* ── Warnings ─────────────────────────────────────────────────── */}
      {bundle.warnings.length > 0 && (
        <>
          <Separator />
          <div className="text-xs">
            <div className="font-medium mb-1">Warnings</div>
            <ul className="list-disc pl-4 text-muted-foreground flex flex-col gap-0.5">
              {bundle.warnings.map((w, i) => <li key={i}>{w}</li>)}
            </ul>
          </div>
        </>
      )}

      {/* Footer actions live in the wizard's CardFooter — see GMIntakeWizard. */}
    </div>
  )
}

function DesignChoiceBlock({ bundle }: { bundle: DealerBundle }) {
  const dc = bundle.design_choice
  if (dc.kind === "json") {
    return (
      <div className="flex flex-col gap-2">
        <div className="text-xs font-medium text-muted-foreground">Design choice (JSON)</div>
        <pre className="text-[10px] leading-tight bg-muted/40 p-3 rounded-md overflow-x-auto max-h-40">
          {JSON.stringify(dc.value, null, 2)}
        </pre>
      </div>
    )
  }
  if (dc.kind === "description") {
    return (
      <div className="flex items-start gap-2 text-[11px] text-amber-600 bg-amber-50 dark:bg-amber-950/30 rounded-md px-3 py-2">
        <AlertCircle size={14} className="shrink-0 mt-0.5" />
        <div className="flex flex-col gap-1">
          <span className="font-medium">Design choice needs human input</span>
          <span>The dealer pasted a description, not JSON. After Create project, paste a real design JSON in the next screen.</span>
          <span className="italic">"{dc.raw}"</span>
        </div>
      </div>
    )
  }
  return <p className="text-[11px] text-muted-foreground">No design choice was filled out on the questionnaire.</p>
}
