import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Textarea } from "@/components/ui/textarea";
import type { SpanishWidgetRow } from "@/store/types";
import { ChevronDown } from "lucide-react";

interface WidgetRowProps {
  row: SpanishWidgetRow;
  onEsChange: (esHtml: string) => void;
  onSave: () => void;
  onSkip: () => void;
  onRetranslate: () => void;
  busy: boolean;
}

export function WidgetRow({
  row,
  onEsChange,
  onSave,
  onSkip,
  onRetranslate,
  busy,
}: WidgetRowProps) {
  const isLocked = row.status === "saved" || row.status === "skipped";
  const isPending = row.status === "queued" || row.status === "translating";
  const canSave =
    !busy && !isLocked && (row.status === "ready" || row.status === "error");

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-2 pb-2">
        <div className="flex items-center gap-2 min-w-0">
          <Badge variant={row.widgetType === "raw" ? "secondary" : "outline"}>
            {row.widgetType === "raw" ? "RAW HTML" : "Content"}
          </Badge>
          <code className="text-xs font-mono truncate">{row.windowId}</code>
          <span className="text-xs text-muted-foreground">{row.status}</span>
        </div>
        {row.error && (
          <span className="text-xs text-destructive truncate max-w-[40%]">
            {row.error}
          </span>
        )}
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <Collapsible defaultOpen={!isPending}>
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

        {!isPending && (
          <div className="flex flex-col gap-1">
            <span className="text-xs font-semibold text-muted-foreground">
              Spanish (editable)
            </span>
            <Textarea
              value={row.esHtml}
              onChange={(e) => onEsChange(e.target.value)}
              rows={8}
              disabled={isLocked || busy}
              className="font-mono text-xs"
            />
          </div>
        )}

        {isPending && (
          <p className="text-xs text-muted-foreground italic">Translating…</p>
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

        {!isLocked && !isPending && (
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
              disabled={busy}
            >
              Retranslate
            </Button>
            <Button type="button" size="sm" onClick={onSave} disabled={!canSave}>
              Save
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
