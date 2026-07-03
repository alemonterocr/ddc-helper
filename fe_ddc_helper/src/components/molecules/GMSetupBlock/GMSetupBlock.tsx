/**
 * Read-only dashboard header shared by GMBuySellFlowPanel and
 * GMPrebuildFlowPanel. Shows the dealer identity (classification badge, name),
 * the two field cards (Questionnaire + Project) with verify links, and quick
 * access buttons for the CMS and Dealer Center.
 */

import { ExternalLink } from "lucide-react"

import { BundleFieldCard } from "@/components/molecules/BundleFieldCard/BundleFieldCard"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import type { DealerBundle } from "@/types"

interface GMSetupBlockProps {
  bundle: DealerBundle
}

export function GMSetupBlock({ bundle }: GMSetupBlockProps) {
  const isBuySell = bundle.classification.value === "buysell"
  const displayName = isBuySell ? bundle.new_dealership_name : bundle.dealership_name

  const questionnaireUrl =
    bundle.source.questionnaire_insight_id && bundle.source.questionnaire_insight_id !== "-"
      ? `https://casfx.lightning.force.com/lightning/r/taskfeed1__Board_Insight__c/${bundle.source.questionnaire_insight_id}/view`
      : undefined

  const projectUrl =
    bundle.source.precursive_project_id && bundle.source.precursive_project_id !== "-"
      ? `https://casfx.lightning.force.com/lightning/r/preempt__PrecursiveProject__c/${bundle.source.precursive_project_id}/view`
      : undefined

  const dealerId = bundle.dealer_id
  const dealerIdResolved = dealerId && dealerId !== "-"

  const cmsUrl = dealerIdResolved ? `https://${dealerId}.cms.dealer.com` : undefined
  const dealerCenterUrl = dealerIdResolved
    ? `https://apps.dealercenter.coxautoinc.com/landing/dealer/${dealerId}/dashboard`
    : undefined

  // For BuySell the buyer's NEW URL is the canonical "this dealership's site"
  // for everything downstream (CMS targeting, content cloning). The seller's
  // existing URL is still surfaced for reference (as "Seller's current URL")
  // so the operator can compare during the buy-sell transition.
  const questionnaireFields = [
    { id: "setup-dealer-name", label: "Dealership", value: bundle.dealership_name, readOnly: true },
    ...(isBuySell
      ? [{ id: "setup-new-name", label: "New name (BuySell)", value: bundle.new_dealership_name, readOnly: true }]
      : []),
    { id: "setup-address", label: "Address", value: bundle.dealership_address, readOnly: true },
    { id: "setup-leads-email", label: "Leads email", value: bundle.leads_email, readOnly: true },
    {
      id: "setup-primary-url",
      label: "Primary URL",
      value: isBuySell ? bundle.new_primary_url : bundle.primary_url,
      readOnly: true,
    },
    ...(isBuySell
      ? [{
          id: "setup-seller-url",
          label: "Seller's current URL",
          value: bundle.primary_url,
          readOnly: true,
        }]
      : []),
  ]

  const projectFields = [
    { id: "setup-ppr", label: "PPR", value: bundle.ppr, readOnly: true },
    { id: "setup-dealer-id", label: "Dealer Id", value: bundle.dealer_id, readOnly: true },
  ]

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Badge variant={isBuySell ? "default" : "secondary"}>
            {isBuySell ? "GM BuySell" : "GM Prebuild"}
          </Badge>
          <h2 className="text-lg font-semibold">{displayName || "-"}</h2>
        </div>
        <div className="flex items-center gap-2">
          {cmsUrl && (
            <Button variant="outline" size="sm" asChild>
              <a href={cmsUrl} target="_blank" rel="noreferrer noopener">
                <ExternalLink size={12} className="mr-1" /> CMS
              </a>
            </Button>
          )}
          {dealerCenterUrl && (
            <Button variant="outline" size="sm" asChild>
              <a href={dealerCenterUrl} target="_blank" rel="noreferrer noopener">
                <ExternalLink size={12} className="mr-1" /> Dealer Center
              </a>
            </Button>
          )}
        </div>
      </div>

      <Separator />

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

      <DesignChoiceDisplay bundle={bundle} />
    </div>
  )
}

function DesignChoiceDisplay({ bundle }: { bundle: DealerBundle }) {
  const dc = bundle.design_choice
  return (
    <div className="flex flex-col gap-2">
      <div className="text-xs font-medium text-muted-foreground">
        Design choice
      </div>
      {dc.kind === "json" && (
        <pre className="text-[11px] leading-snug bg-muted/40 p-3 rounded-md overflow-x-auto max-h-60 scrollbar-thin">
          {JSON.stringify(dc.value, null, 2)}
        </pre>
      )}
      {dc.kind === "description" && (
        <div className="text-xs bg-amber-50 dark:bg-amber-950/30 text-amber-700 dark:text-amber-300 rounded-md p-3 flex flex-col gap-1">
          <span className="font-medium">Description (needs human input)</span>
          <span className="italic">"{dc.raw}"</span>
        </div>
      )}
      {dc.kind === "missing" && (
        <p className="text-[11px] text-muted-foreground">No design choice was filled out on the questionnaire.</p>
      )}
    </div>
  )
}
