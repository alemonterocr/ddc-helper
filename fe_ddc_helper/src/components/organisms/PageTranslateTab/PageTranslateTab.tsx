import { useCallback, useMemo, useRef, useState } from "react";

import { WidgetRow } from "@/components/molecules/WidgetRow/WidgetRow";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Input } from "@/components/ui/input";
import { useServices } from "@/services/ServicesContext";
import { useMigrationStore } from "@/store/useMigrationStore";
import type { SpanishMigrationProject, SpanishWidgetRow } from "@/store/types";
import type { LLMProvider, PageWidget } from "@/types";
import { ChevronDown } from "lucide-react";

interface PageTranslateTabProps {
  project: SpanishMigrationProject;
}

/** Build a placeholder row (status "translating") from a to-translate widget. */
function toRow(widget: PageWidget): SpanishWidgetRow {
  return {
    windowId: widget.window_id,
    widgetType: widget.widget_type,
    status: "translating",
    enHtml: widget.en_html,
    esHtml: "",
    warnings: [],
    raw: null,
    error: null,
    reasoning: "",
  };
}

export function PageTranslateTab({ project }: PageTranslateTabProps) {
  const { pagePort, labelPort, backendPort, credentialPort } = useServices();
  const { setPageWidgets, updatePageWidget } = useMigrationStore();

  const [provider, setProvider] = useState<LLMProvider | null>(null);
  const [credError, setCredError] = useState<string | null>(null);
  const [targetPath, setTargetPath] = useState("");
  const [skipped, setSkipped] = useState<PageWidget[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const rows = useMemo(() => project.pageWidgets ?? [], [project.pageWidgets]);

  const ensureProvider = useCallback(async (): Promise<LLMProvider | null> => {
    if (provider) return provider;
    const stored = await credentialPort.getStoredApiKey();
    if (!stored) {
      setCredError("No API key configured. Set one on the home screen first.");
      return null;
    }
    await backendPort
      .configureApiKey({ provider: stored.provider, api_key: stored.apiKey })
      .catch(() => {
        /* best-effort: real errors surface via the stream/per-row state */
      });
    setProvider(stored.provider);
    setCredError(null);
    return stored.provider;
  }, [backendPort, credentialPort, provider]);

  const counts = useMemo(() => {
    const acc = { translating: 0, ready: 0, saved: 0, error: 0, skipped: skipped.length };
    for (const row of rows) {
      if (row.status === "queued" || row.status === "translating") acc.translating += 1;
      else if (row.status === "ready") acc.ready += 1;
      else if (row.status === "saved") acc.saved += 1;
      else if (row.status === "error") acc.error += 1;
    }
    return acc;
  }, [rows, skipped.length]);

  /** Translate one widget through the reused label pipeline, patching the row. */
  const translateOne = useCallback(
    async (windowId: string, enHtml: string, activeProvider: LLMProvider) => {
      updatePageWidget(project.id, windowId, {
        status: "translating",
        error: null,
        warnings: [],
      });
      try {
        const t = await labelPort.translateLabel({
          alias: windowId,
          en_html: enHtml,
          dealer_name: project.dealerName,
          provider: activeProvider,
        });
        updatePageWidget(project.id, windowId, {
          status: t.status,
          esHtml: t.es_html,
          warnings: t.warnings,
          raw: t.raw ?? null,
          reasoning: t.reasoning ?? "",
          error: t.status === "error" ? "Translation needs review — see warnings" : null,
        });
      } catch (err) {
        updatePageWidget(project.id, windowId, {
          status: "error",
          error: err instanceof Error ? err.message : String(err),
        });
      }
    },
    [labelPort, project.dealerName, project.id, updatePageWidget],
  );

  const handleLoad = useCallback(async () => {
    if (!targetPath.trim()) return;
    setError(null);
    setSkipped([]);
    setLoading(true);

    const activeProvider = await ensureProvider();
    if (!activeProvider) {
      setLoading(false);
      return;
    }

    const path = targetPath.trim();
    const [en, es] = await Promise.all([
      pagePort.loadPage(path, "en_US"),
      pagePort.loadPage(path, "es_US"),
    ]);
    if (en.error || en.html === null) {
      setError(`Failed to load English page: ${en.error ?? "no HTML"}`);
      setLoading(false);
      return;
    }
    if (es.error || es.html === null) {
      setError(`Failed to load Spanish page: ${es.error ?? "no HTML"}`);
      setLoading(false);
      return;
    }

    setPageWidgets(project.id, path, []);
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    await pagePort.translatePageStream(
      {
        en_page_html: en.html,
        es_page_html: es.html,
        dealer_name: project.dealerName,
        provider: activeProvider,
      },
      (event) => {
        if (event.type === "checked") {
          setSkipped(event.skipped);
          setPageWidgets(project.id, path, event.to_translate.map(toRow));
        } else if (event.type === "widget") {
          const w = event.widget;
          updatePageWidget(project.id, w.window_id, {
            enHtml: w.en_html,
            esHtml: w.es_html,
            status: w.status,
            warnings: w.warnings,
            raw: w.raw ?? null,
            reasoning: w.reasoning ?? "",
            error: w.status === "error" ? "Translation needs review — see warnings" : null,
          });
        } else if (event.type === "error") {
          setError(event.message);
        }
      },
      controller.signal,
    );

    setLoading(false);
  }, [
    ensureProvider,
    pagePort,
    project.dealerName,
    project.id,
    setPageWidgets,
    targetPath,
    updatePageWidget,
  ]);

  const handleSave = useCallback(
    async (windowId: string) => {
      const row = rows.find((r) => r.windowId === windowId);
      if (!row) return;
      setBusyId(windowId);
      try {
        const result = await pagePort.saveWidget({
          windowId: row.windowId,
          widgetType: row.widgetType,
          enHtml: row.enHtml,
          esHtml: row.esHtml,
        });
        updatePageWidget(project.id, windowId, {
          status: result.success ? "saved" : "error",
          error: result.success ? null : (result.error ?? "DDC save failed"),
        });
      } finally {
        setBusyId(null);
      }
    },
    [pagePort, project.id, rows, updatePageWidget],
  );

  const handleSkip = useCallback(
    (windowId: string) => updatePageWidget(project.id, windowId, { status: "skipped" }),
    [project.id, updatePageWidget],
  );

  const handleRetranslate = useCallback(
    async (windowId: string) => {
      const row = rows.find((r) => r.windowId === windowId);
      if (!row) return;
      const activeProvider = await ensureProvider();
      if (!activeProvider) return;
      setBusyId(windowId);
      try {
        await translateOne(windowId, row.enHtml, activeProvider);
      } finally {
        setBusyId(null);
      }
    },
    [ensureProvider, rows, translateOne],
  );

  const handleForceTranslate = useCallback(
    async (widget: PageWidget) => {
      const activeProvider = await ensureProvider();
      if (!activeProvider) return;
      setSkipped((prev) => prev.filter((w) => w.window_id !== widget.window_id));
      const path = project.pageTargetPath ?? targetPath.trim();
      setPageWidgets(project.id, path, [...rows, toRow(widget)]);
      await translateOne(widget.window_id, widget.en_html, activeProvider);
    },
    [ensureProvider, project.id, project.pageTargetPath, rows, setPageWidgets, targetPath, translateOne],
  );

  const hasRows = rows.length > 0;

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle>Load Page Widgets</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <p className="text-xs text-muted-foreground">
            Enter a page path (e.g. <code>/new-inventory/index.htm</code>). The
            page's editable content and RAW HTML widgets are pulled in both
            languages and translated where Spanish is missing or untranslated.
          </p>
          <div className="flex gap-2">
            <Input
              value={targetPath}
              onChange={(e) => setTargetPath(e.target.value)}
              placeholder="/new-inventory/index.htm"
              className="font-mono text-xs"
              disabled={loading}
            />
            <Button
              type="button"
              onClick={handleLoad}
              disabled={loading || !targetPath.trim()}
            >
              {loading ? "Loading…" : "Load Page Widgets"}
            </Button>
          </div>
          {error && <p className="text-xs text-destructive">{error}</p>}
          {credError && <p className="text-xs text-destructive">{credError}</p>}
        </CardContent>
      </Card>

      {hasRows && (
        <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
          <Counter label="Translating" value={counts.translating} />
          <Counter label="Ready" value={counts.ready} />
          <Counter label="Saved" value={counts.saved} />
          <Counter label="Error" value={counts.error} />
          <Counter label="Skipping" value={counts.skipped} />
        </div>
      )}

      <div className="flex flex-col gap-3">
        {rows.map((row) => (
          <WidgetRow
            key={row.windowId}
            row={row}
            busy={busyId === row.windowId}
            onEsChange={(esHtml) =>
              updatePageWidget(project.id, row.windowId, { esHtml })
            }
            onSave={() => handleSave(row.windowId)}
            onSkip={() => handleSkip(row.windowId)}
            onRetranslate={() => handleRetranslate(row.windowId)}
          />
        ))}
      </div>

      {skipped.length > 0 && (
        <Collapsible defaultOpen={false}>
          <CollapsibleTrigger className="group inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-semibold text-muted-foreground hover:text-foreground hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring transition-colors -mx-2">
            {skipped.length} widget{skipped.length === 1 ? "" : "s"} skipped
            (already translated)
            <ChevronDown
              size={12}
              aria-hidden="true"
              className="transition-transform duration-150 group-data-[state=open]:rotate-180"
            />
          </CollapsibleTrigger>
          <CollapsibleContent className="pt-2">
            <div className="flex flex-col gap-1">
              {skipped.map((widget) => (
                <div
                  key={widget.window_id}
                  className="flex items-center justify-between gap-2 rounded-md border border-border px-3 py-1.5 text-xs"
                >
                  <code className="font-mono truncate min-w-0">
                    {widget.window_id}
                  </code>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="text-xs h-auto py-0.5 px-2 shrink-0"
                    onClick={() => handleForceTranslate(widget)}
                  >
                    Force translate
                  </Button>
                </div>
              ))}
            </div>
          </CollapsibleContent>
        </Collapsible>
      )}
    </div>
  );
}

function Counter({ label, value }: { label: string; value: number }) {
  return (
    <span>
      <span className="font-semibold text-foreground">{value}</span> {label}
    </span>
  );
}
