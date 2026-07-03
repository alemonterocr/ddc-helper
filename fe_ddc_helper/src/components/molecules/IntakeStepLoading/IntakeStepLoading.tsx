/**
 * Step 2 of GMIntakeWizard. Live progress log streamed from the backend
 * LangGraph via WS. The Cancel button lives in the wizard's CardFooter.
 */

import { Loader2 } from "lucide-react"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

interface IntakeStepLoadingProps {
  progress: string[]
}

export function IntakeStepLoading({ progress }: IntakeStepLoadingProps) {
  const lastLine = progress[progress.length - 1] ?? "Connecting to backend"

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center gap-3 text-sm">
        <Loader2 size={16} className="animate-spin text-muted-foreground" />
        <span>{lastLine}</span>
      </div>

      <Card className="bg-muted/30 border-none shadow-none">
        <CardHeader className="pb-2">
          <CardTitle className="text-[11px] text-muted-foreground">
            Steps
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          {progress.length === 0 ? (
            <p className="text-xs text-muted-foreground">Waiting for the first event.</p>
          ) : (
            <ul className="text-xs flex flex-col gap-1">
              {progress.map((line, i) => (
                <li key={i}>· {line}</li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
