import { useCallback, useMemo, useState } from "react";

import { LabelRow } from "@/components/molecules/LabelRow/LabelRow";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { useServices } from "@/services/ServicesContext";
import { useMigrationStore } from "@/store/useMigrationStore";
import type { SpanishMigrationProject } from "@/store/types";
import type { LLMProvider, NavCheckItem } from "@/types";
import { ChevronDown } from "lucide-react";

interface NavTranslateTabProps {
  project: SpanishMigrationProject;
}

export function NavTranslateTab({ project }: NavTranslateTabProps) {
  const { labelPort, backendPort, credentialPort } = useServices();
  const { setSpanishLabels, updateSpanishLabel } = useMigrationStore();
  const [provider, setProvider] = useState<LLMProvider | null>(null);
  const [credError, setCredError] = useState<string | null>(null);

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
        /* best-effort: surface real errors via the per-row error state */
      });
    setProvider(stored.provider);
    setCredError(null);
    return stored.provider;
  }, [backendPort, credentialPort, provider]);

  const [skipped, setSkipped] = useState<NavCheckItem[]>([]);
  const [navError, setNavError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const counts = useMemo(() => {
    const acc = {
      queued: 0,
      translating: 0,
      ready: 0,
      saved: 0,
      error: 0,
      skipped: skipped.length,
      not_found: 0,
    };
    for (const row of project.labels) {
      if (row.status === "queued" || row.status === "fetching") acc.queued += 1;
      else if (row.status === "translating") acc.translating += 1;
      else if (row.status === "ready") acc.ready += 1;
      else if (row.status === "saved") acc.saved += 1;
      else if (row.status === "error") acc.error += 1;
      else if (row.status === "not_found") acc.not_found += 1;
    }
    return acc;
  }, [project.labels, skipped.length]);

  const runTranslation = useCallback(
    async (alias: string) => {
      const activeProvider = await ensureProvider();
      if (!activeProvider) return;

      updateSpanishLabel(project.id, alias, {
        status: "fetching",
        error: null,
        warnings: [],
      });

      let ddc;
      try {
        ddc = await labelPort.fetchLabel(project.dealerId, alias);
      } catch (err) {
        updateSpanishLabel(project.id, alias, {
          status: "error",
          error: `DDC fetch failed: ${err instanceof Error ? err.message : String(err)}`,
        });
        return;
      }

      if (ddc.error) {
        updateSpanishLabel(project.id, alias, {
          status: "error",
          error: `DDC fetch failed: ${ddc.error}`,
        });
        return;
      }
      if (!ddc.en) {
        updateSpanishLabel(project.id, alias, {
          status: "not_found",
          enHtml: null,
          error: "DDC returned no en_US value for this alias",
        });
        return;
      }

      updateSpanishLabel(project.id, alias, {
        enHtml: ddc.en,
        status: "translating",
      });

      let translation;
      try {
        translation = await labelPort.translateLabel({
          alias,
          en_html: ddc.en,
          dealer_name: project.dealerName,
          provider: activeProvider,
        });
      } catch (err) {
        updateSpanishLabel(project.id, alias, {
          status: "error",
          error: err instanceof Error ? err.message : String(err),
        });
        return;
      }

      updateSpanishLabel(project.id, alias, {
        status: translation.status,
        esHtml: translation.es_html,
        warnings: translation.warnings,
        raw: translation.raw ?? null,
        reasoning: translation.reasoning ?? "",
        error:
          translation.status === "error"
            ? "Translation needs review — see warnings"
            : null,
      });
    },
    [
      ensureProvider,
      labelPort,
      project.dealerId,
      project.dealerName,
      project.id,
      updateSpanishLabel,
    ],
  );

  const advanceToNext = useCallback(async () => {
    const next = project.labels.find((row) => row.status === "queued");
    if (!next) return;
    await runTranslation(next.alias);
  }, [project.labels, runTranslation]);

  const handleLoadNav = useCallback(async () => {
    setNavError(null);
    setSkipped([]);
    setLoading(true);

    const activeProvider = await ensureProvider();
    if (!activeProvider) {
      setLoading(false);
      return;
    }

    let navResult;
    try {
      navResult = await labelPort.loadNav();
    } catch (err) {
      setNavError(
        err instanceof Error ? err.message : "Failed to load navigation",
      );
      setLoading(false);
      return;
    }

    if (navResult.error || !navResult.raw) {
      setNavError(navResult.error ?? "Failed to load navigation");
      setLoading(false);
      return;
    }

    let checkResult;
    try {
      checkResult = await labelPort.navCheck({
        nav_json: navResult.raw,
        dealer_name: project.dealerName,
      });
    } catch (err) {
      setNavError(
        err instanceof Error ? err.message : "Nav check failed",
      );
      setLoading(false);
      return;
    }

    setSkipped(checkResult.skipped);

    const aliases = checkResult.to_translate.map((item) => item.alias);
    setSpanishLabels(project.id, aliases);

    if (aliases.length > 0 && aliases[0]) {
      await runTranslation(aliases[0]);
    }

    setLoading(false);
  }, [
    ensureProvider,
    labelPort,
    project.dealerId,
    project.dealerName,
    project.id,
    runTranslation,
    setSpanishLabels,
  ]);

  const handleSave = useCallback(
    async (alias: string) => {
      const row = project.labels.find((r) => r.alias === alias);
      if (!row || row.enHtml === null) return;

      try {
        const result = await labelPort.saveLabel(
          project.dealerId,
          alias,
          row.enHtml,
          row.esHtml,
        );
        if (!result.success) {
          updateSpanishLabel(project.id, alias, {
            status: "error",
            error: result.error ?? "DDC save failed",
          });
          return;
        }
        updateSpanishLabel(project.id, alias, {
          status: "saved",
          error: null,
        });
      } catch (err) {
        updateSpanishLabel(project.id, alias, {
          status: "error",
          error: err instanceof Error ? err.message : String(err),
        });
        return;
      }

      await advanceToNext();
    },
    [labelPort, project.dealerId, project.id, project.labels, updateSpanishLabel, advanceToNext],
  );

  const handleSkip = useCallback(
    async (alias: string) => {
      updateSpanishLabel(project.id, alias, { status: "skipped" });
      await advanceToNext();
    },
    [advanceToNext, project.id, updateSpanishLabel],
  );

  const handleRetranslate = useCallback(
    async (alias: string) => {
      await runTranslation(alias);
    },
    [runTranslation],
  );

  const handleForceTranslate = useCallback(
    async (alias: string) => {
      setSpanishLabels(project.id, [alias]);
      setSkipped((prev) => prev.filter((item) => item.alias !== alias));
      await runTranslation(alias);
    },
    [project.id, runTranslation, setSpanishLabels],
  );

  const hasLabels = project.labels.length > 0;

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle>Load Navigation Labels</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <p className="text-xs text-muted-foreground">
            Load the navigation tree from the DDC composer and translate any
            labels that are still in English or missing Spanish text.
          </p>
          <div className="flex justify-end">
            <Button type="button" onClick={handleLoadNav} disabled={loading}>
              {loading ? "Loading…" : "Load Navigation"}
            </Button>
          </div>
          {navError && (
            <p className="text-xs text-destructive">{navError}</p>
          )}
          {credError && (
            <p className="text-xs text-destructive">{credError}</p>
          )}
        </CardContent>
      </Card>

      {hasLabels && (
        <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
          <Counter label="Queued" value={counts.queued} />
          <Counter label="Translating" value={counts.translating} />
          <Counter label="Ready" value={counts.ready} />
          <Counter label="Saved" value={counts.saved} />
          <Counter label="Error" value={counts.error} />
          <Counter label="Not found" value={counts.not_found} />
          <Counter label="Skipping" value={counts.skipped} />
        </div>
      )}

      <div className="flex flex-col gap-3">
        {project.labels.map((row) => (
          <LabelRow
            key={row.alias}
            row={row}
            busy={false}
            onEsChange={(esHtml) =>
              updateSpanishLabel(project.id, row.alias, { esHtml })
            }
            onSave={() => handleSave(row.alias)}
            onSkip={() => handleSkip(row.alias)}
            onRetranslate={() => handleRetranslate(row.alias)}
          />
        ))}
      </div>

      {skipped.length > 0 && (
        <Collapsible defaultOpen={false}>
          <CollapsibleTrigger className="group inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-semibold text-muted-foreground hover:text-foreground hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring transition-colors -mx-2">
            {skipped.length} label{skipped.length === 1 ? "" : "s"} skipped
            (already have Spanish text)
            <ChevronDown
              size={12}
              aria-hidden="true"
              className="transition-transform duration-150 group-data-[state=open]:rotate-180"
            />
          </CollapsibleTrigger>
          <CollapsibleContent className="pt-2">
            <div className="flex flex-col gap-1">
              {skipped.map((item) => (
                <div
                  key={item.alias}
                  className="flex items-center justify-between gap-2 rounded-md border border-border px-3 py-1.5 text-xs"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <code className="font-mono truncate">{item.alias}</code>
                    <span className="text-muted-foreground truncate">
                      &mdash; {item.label_es}
                    </span>
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="text-xs h-auto py-0.5 px-2 shrink-0"
                    onClick={() => handleForceTranslate(item.alias)}
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
