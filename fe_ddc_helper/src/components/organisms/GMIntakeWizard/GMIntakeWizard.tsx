/**
 * GMIntakeWizard. Replaces the old GMProjectForm with a 3-step breadcrumb
 * stepper that uses the Salesforce intake pipeline.
 *
 *   Step 1: paste the SF Board URL
 *   Step 2: live progress while backend runs the LangGraph + LLM classifier
 *   Step 3: editable review card, then Confirm to create the project
 *
 * Wizard owns the WS lifecycle: opens on submit (key = boardId), tears down on
 * close, success, or reset. AbortController cancels in-flight intake.
 *
 * On Confirm: dispatches to createGMBuySellProject or createGMPrebuildProject
 * based on classification, attaches the (possibly edited) bundle, navigates
 * into the project.
 */

import { useEffect, useRef, useState } from "react"
import { Check, Loader2, X } from "lucide-react"
// Loader2 used in CardFooter for the nav step's "Parsing nav" indicator.

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { useServices } from "@/services/ServicesContext"
import { useMigrationStore } from "@/store/useMigrationStore"
import type { DealerBundle } from "@/types"

import { IntakeStepLink } from "@/components/molecules/IntakeStepLink/IntakeStepLink"
import { IntakeStepLoading } from "@/components/molecules/IntakeStepLoading/IntakeStepLoading"
import { IntakeStepNav } from "@/components/molecules/IntakeStepNav/IntakeStepNav"
import { IntakeStepReview } from "@/components/molecules/IntakeStepReview/IntakeStepReview"

type WizardStep = "link" | "loading" | "review" | "nav"

const BOARD_URL_RE =
  /^https:\/\/casfx\.lightning\.force\.com\/lightning\/r\/taskfeed1__Board__c\/([A-Za-z0-9]+)\/view$/

interface GMIntakeWizardProps {
  onCancel: () => void
}

export function GMIntakeWizard({ onCancel }: GMIntakeWizardProps) {
  const { backendPort, credentialPort, createWSClient } = useServices()
  const {
    createGMPrebuildProject,
    createGMBuySellProject,
    addPage,
    updatePage,
    goToProject,
  } = useMigrationStore()

  const [step, setStep] = useState<WizardStep>("link")
  const [url, setUrl] = useState("")
  const [progress, setProgress] = useState<string[]>([])
  const [error, setError] = useState<string | undefined>()
  const [bundle, setBundle] = useState<DealerBundle | null>(null)
  const [navBaseUrl, setNavBaseUrl] = useState("")
  const [navHtmlValue, setNavHtmlValue] = useState("")
  const [navError, setNavError] = useState<string | undefined>()
  const [isNavLoading, setIsNavLoading] = useState(false)

  const wsRef = useRef<ReturnType<typeof createWSClient> | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => () => { cleanup() }, [])

  // Lock body scroll while the wizard modal is open. Restores prior overflow
  // value on unmount so we don't fight other modals' overflow management.
  useEffect(() => {
    const prev = document.body.style.overflow
    document.body.style.overflow = "hidden"
    return () => { document.body.style.overflow = prev }
  }, [])

  function cleanup() {
    abortRef.current?.abort()
    abortRef.current = null
    wsRef.current?.disconnect()
    wsRef.current = null
  }

  async function handleStart() {
    setError(undefined)
    setProgress([])
    setBundle(null)

    const trimmed = url.trim()
    const match = trimmed.match(BOARD_URL_RE)
    const boardId = match?.[1]
    if (!match || !boardId) {
      setError("URL doesn't match the Salesforce Board pattern.")
      return
    }

    setUrl(trimmed)
    setStep("loading")

    const ws = createWSClient()
    wsRef.current = ws
    const abort = new AbortController()
    abortRef.current = abort

    try {
      await ws.connect(boardId, (msg) => setProgress((p) => [...p, msg]))

      // BE drops LLM keys on restart. Re-push the stored key so the classifier
      // node has a provider available. Best-effort: intake still runs without
      // it (verdict defaults to prebuild + confidence:0 and the FE banner
      // asks the user to confirm).
      const stored = await credentialPort.getStoredApiKey()
      if (stored) {
        await backendPort
          .configureApiKey({ provider: stored.provider, api_key: stored.apiKey })
          .catch(() => { /* surfaced via classifier warning below */ })
      }

      const res = await backendPort.salesforceIntake(
        { board_url: trimmed, provider: stored?.provider ?? null },
        abort.signal,
      )
      if (res.error) {
        setError(res.error)
        setStep("link")
      } else if (res.bundle) {
        setBundle(res.bundle)
        setStep("review")
      } else {
        setError("Backend returned no bundle and no error.")
        setStep("link")
      }
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") {
        // User cancelled. Reset to step 1 quietly.
        setStep("link")
      } else {
        setError(e instanceof Error ? e.message : String(e))
        setStep("link")
      }
    } finally {
      ws.disconnect()
      wsRef.current = null
      abortRef.current = null
    }
  }

  function handleCancelLoading() {
    abortRef.current?.abort()
  }

  function handleBackToLink() {
    setStep("link")
    setBundle(null)
  }

  function dealerIdFor(edited: DealerBundle): string {
    return edited.dealer_id && edited.dealer_id !== "-" ? edited.dealer_id : "unknown"
  }

  function handleConfirm() {
    if (!bundle) return
    if (bundle.classification.value === "buysell") {
      // BuySells skip the nav step. No pages to migrate.
      const projectId = createGMBuySellProject(dealerIdFor(bundle), bundle)
      goToProject(projectId)
      onCancel()
      return
    }
    // Prebuild path. Advance to nav HTML step. Seed nav base URL from the
    // bundle's primary URL if available.
    const defaultBase = bundle.primary_url && bundle.primary_url !== "-" ? bundle.primary_url : ""
    setNavBaseUrl(defaultBase)
    setNavHtmlValue("")
    setNavError(undefined)
    setStep("nav")
  }

  async function handleNavSubmit() {
    if (!bundle) return
    const baseUrl = navBaseUrl.trim()
    const navHtml = navHtmlValue
    setNavError(undefined)
    setIsNavLoading(true)
    try {
      const stored = await credentialPort.getStoredApiKey()
      if (!stored) {
        setNavError("No LLM API key configured. Configure one in Settings first.")
        return
      }

      // Re-push the key (BE drops on restart) like the existing CM flow.
      await backendPort
        .configureApiKey({ provider: stored.provider, api_key: stored.apiKey })
        .catch(() => { /* parseNav will surface its own error */ })

      const dealerId = dealerIdFor(bundle)
      const response = await backendPort.parseNav({
        dealer_id: dealerId,
        html: navHtml,
        base_url: baseUrl,
        provider: stored.provider,
      })

      if (response.error) {
        setNavError(response.error)
        return
      }

      const generalPages = response.pages.filter((p) => p.category === "general")
      if (generalPages.length === 0) {
        setNavError(
          response.pages.length > 0
            ? `Found ${response.pages.length} page(s), but all were model-specific. Paste a wider nav HTML?`
            : "No pages found in the navigation HTML.",
        )
        return
      }

      const projectId = createGMPrebuildProject(dealerId, bundle)
      generalPages.forEach((page) => {
        const pageId = addPage(projectId, page.url)
        updatePage(projectId, pageId, {
          pageTitle: page.title,
          pageAlias: `${page.title.toLowerCase().replace(/\s+/g, "-")}.htm`,
        })
      })

      goToProject(projectId)
      onCancel()
    } catch (e) {
      setNavError(e instanceof Error ? e.message : String(e))
    } finally {
      setIsNavLoading(false)
    }
  }

  function handleNavBack() {
    setStep("review")
    setNavError(undefined)
  }

  const stepIndex =
    step === "link" ? 0 :
    step === "loading" ? 1 :
    step === "review" ? 2 :
    3 // "nav"

  // Breadcrumb length depends on classification:
  //   - Before bundle arrives → 3 steps (assume the simpler BuySell path).
  //   - Once classified Prebuild → extend to 4 (Nav HTML step appears).
  //   - BuySell → stays at 3, no nav step.
  const isPrebuild = bundle?.classification.value === "prebuild"
  const breadcrumbSteps = isPrebuild
    ? [
        { label: "Salesforce link" },
        { label: "Fetching" },
        { label: "Review" },
        { label: "Nav HTML" },
      ]
    : [
        { label: "Salesforce link" },
        { label: "Fetching" },
        { label: "Review" },
      ]

  return (
    <Card className="w-[min(92vw,900px)] h-[min(90vh,640px)] flex flex-col overflow-hidden">
      {/* Header — sticky at top of the wizard card */}
      <CardHeader className="gap-3 shrink-0 px-8 py-6 border-b border-border bg-card">
        <div className="flex items-center justify-between gap-2">
          <CardTitle>New GM Project</CardTitle>
          <Button variant="ghost" size="icon-sm" onClick={onCancel}>
            <X size={14} />
          </Button>
        </div>
        <CardDescription>
          Paste the Salesforce Board link. We'll read the questionnaire and project record,
          classify Prebuild vs. BuySell, and prefill the project.
        </CardDescription>
        <Breadcrumb activeIndex={stepIndex} steps={breadcrumbSteps} />
      </CardHeader>

      {/* Scrollable body — only this region scrolls. Action buttons live
          in the footer below, OUTSIDE this scrollable region, so they're
          always pinned at the bottom of the wizard with zero overlap. */}
      <CardContent className="flex-1 overflow-y-auto scrollbar-thin px-8 py-6">
        {step === "link" && (
          <IntakeStepLink
            url={url}
            onUrlChange={setUrl}
            error={error}
            onSubmit={handleStart}
          />
        )}
        {step === "loading" && (
          <IntakeStepLoading progress={progress} />
        )}
        {step === "review" && bundle && (
          <IntakeStepReview
            bundle={bundle}
            onBundleChange={setBundle}
          />
        )}
        {step === "nav" && bundle && (
          <IntakeStepNav
            baseUrl={navBaseUrl}
            navHtml={navHtmlValue}
            onBaseUrlChange={setNavBaseUrl}
            onNavHtmlChange={setNavHtmlValue}
            isLoading={isNavLoading}
            error={navError}
          />
        )}
      </CardContent>

      {/* Footer — sticky at bottom by being shrink-0 outside the scroll
          region. Buttons vary per step. */}
      <div className="shrink-0 px-8 py-4 border-t border-border bg-card flex items-center justify-between gap-3">
        {step === "link" && (
          <>
            <span />
            <Button onClick={handleStart} disabled={url.trim().length === 0}>
              Continue
            </Button>
          </>
        )}
        {step === "loading" && (
          <>
            <span />
            <Button variant="outline" size="sm" onClick={handleCancelLoading}>
              Cancel
            </Button>
          </>
        )}
        {step === "review" && bundle && (
          <>
            <Button variant="outline" onClick={handleBackToLink}>Back</Button>
            <Button onClick={handleConfirm}>Create project</Button>
          </>
        )}
        {step === "nav" && bundle && (
          <>
            <Button variant="outline" onClick={handleNavBack} disabled={isNavLoading}>
              Back
            </Button>
            <Button
              onClick={handleNavSubmit}
              disabled={isNavLoading || navBaseUrl.trim().length === 0 || navHtmlValue.trim().length < 30}
            >
              {isNavLoading ? (
                <>
                  <Loader2 size={14} className="animate-spin mr-2" />
                  Parsing nav
                </>
              ) : (
                "Create project"
              )}
            </Button>
          </>
        )}
      </div>
    </Card>
  )
}

function Breadcrumb({
  activeIndex,
  steps,
}: {
  activeIndex: number
  steps: { label: string }[]
}) {
  return (
    <div className="flex items-center gap-2 text-xs">
      {steps.map((s, i) => {
        const isDone = i < activeIndex
        const isActive = i === activeIndex
        return (
          <div key={s.label} className="flex items-center gap-2">
            <Badge
              variant={isActive ? "default" : isDone ? "secondary" : "outline"}
              className="h-5 px-2 gap-1"
            >
              {isDone ? <Check size={10} /> : i === 1 && isActive ? <Loader2 size={10} className="animate-spin" /> : <span>{i + 1}</span>}
              {s.label}
            </Badge>
            {i < steps.length - 1 && <span className="text-muted-foreground">/</span>}
          </div>
        )
      })}
    </div>
  )
}

