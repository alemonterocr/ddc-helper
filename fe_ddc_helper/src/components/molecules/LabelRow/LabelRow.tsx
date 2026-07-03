import { LabelStatusBadge } from "@/components/atoms/LabelStatusBadge/LabelStatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Textarea } from "@/components/ui/textarea";
import type { SpanishLabelRow } from "@/store/types";
import { ChevronDown } from "lucide-react";

interface LabelRowProps {
  row: SpanishLabelRow;
  /** User edited the ES textarea. The workflow lifts this into the store. */
  onEsChange: (esHtml: string) => void;
  onSave: () => void;
  onSkip: () => void;
  onRetranslate: () => void;
  /** Controls in-row buttons: disabled while a network call is mid-flight. */
  busy: boolean;
}

export function LabelRow({
  row,
  onEsChange,
  onSave,
  onSkip,
  onRetranslate,
  busy,
}: LabelRowProps) {
  const isLocked = row.status === "saved" || row.status === "skipped";
  const canSave =
    !busy && !isLocked && (row.status === "ready" || row.status === "error");

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-2 pb-2">
        <div className="flex items-center gap-2 min-w-0">
          <code className="text-xs font-mono truncate">{row.alias}</code>
          <LabelStatusBadge status={row.status} />
        </div>
        {row.error && (
          <span className="text-xs text-destructive truncate max-w-[40%]">
            {row.error}
          </span>
        )}
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {row.enHtml !== null && (
          <Collapsible defaultOpen>
            <CollapsibleTrigger className="group inline-flex items-center gap-1.5 rounded-md -mx-2 px-2 py-1 text-xs font-semibold text-muted-foreground hover:text-foreground hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring transition-colors">
              English
              <ChevronDown
                size={12}
                aria-hidden="true"
                className="transition-transform duration-150 group-data-[state=open]:rotate-180"
              />
            </CollapsibleTrigger>
            <CollapsibleContent className="pt-2">
              <pre className="text-xs whitespace-pre-wrap bg-muted/40 rounded-md p-2 max-h-48 overflow-y-auto">
                {row.enHtml}
              </pre>
            </CollapsibleContent>
          </Collapsible>
        )}

        {row.status !== "queued" &&
          row.status !== "fetching" &&
          row.status !== "translating" &&
          row.status !== "not_found" && (
            <div className="flex flex-col gap-1">
              <span className="text-xs font-semibold text-muted-foreground">
                Spanish (editable)
              </span>
              <Textarea
                value={row.esHtml}
                onChange={(e) => onEsChange(e.target.value)}
                rows={6}
                disabled={isLocked || busy}
                className="font-mono text-xs"
              />
            </div>
          )}

        {row.warnings.length > 0 && (
          <ul className="text-xs text-destructive list-disc pl-5">
            {row.warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        )}

        {row.reasoning && (
          <Collapsible>
            <CollapsibleTrigger className="group inline-flex items-center gap-1.5 rounded-md -mx-2 px-2 py-1 text-xs font-semibold text-muted-foreground hover:text-foreground hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring transition-colors">
              Translator's reasoning
              <ChevronDown
                size={12}
                aria-hidden="true"
                className="transition-transform duration-150 group-data-[state=open]:rotate-180"
              />
            </CollapsibleTrigger>
            <CollapsibleContent className="pt-2">
              <p className="text-xs whitespace-pre-wrap bg-muted/40 rounded-md p-2 italic">
                {row.reasoning}
              </p>
            </CollapsibleContent>
          </Collapsible>
        )}

        {!isLocked && (
          <div className="flex gap-2 justify-end">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={onSkip}
              disabled={busy}
            >
              Skip
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={onRetranslate}
              disabled={busy || row.enHtml === null}
            >
              Retranslate
            </Button>
            <Button
              type="button"
              size="sm"
              onClick={onSave}
              disabled={!canSave}
            >
              Save
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
