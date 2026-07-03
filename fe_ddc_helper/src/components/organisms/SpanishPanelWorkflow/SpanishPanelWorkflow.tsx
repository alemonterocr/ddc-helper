import { useCallback, useMemo, useState } from "react";

import { LabelRow } from "@/components/molecules/LabelRow/LabelRow";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { useServices } from "@/services/ServicesContext";
import { useMigrationStore } from "@/store/useMigrationStore";
import type { SpanishMigrationProject } from "@/store/types";
import type { LLMProvider } from "@/types";

interface SpanishPanelWorkflowProps {
  project: SpanishMigrationProject;
}

export function SpanishPanelWorkflow({ project }: SpanishPanelWorkflowProps) {
  const { labelPort, backendPort, credentialPort } = useServices();
  const { setSpanishLabels, updateSpanishLabel } = useMigrationStore();
  const [provider, setProvider] = useState<LLMProvider | null>(null);
  const [credError, setCredError] = useState<string | null>(null);

  /**
   * Read the stored API key, re-push it to the BE (stateless across restarts),
   * and return the provider so subsequent /translate calls can stamp it.
   * Same pattern as MigrationFlowPanel.handleAnalyze.
   */
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

  const [rawInput, setRawInput] = useState("");
  const [dropped, setDropped] = useState<string[]>([]);
  const [busyAlias, setBusyAlias] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const counts = useMemo(() => {
    const acc = {
      queued: 0,
      translating: 0,
      ready: 0,
      saved: 0,
      error: 0,
      skipped: 0,
      not_found: 0,
    };
    for (const row of project.labels) {
      if (row.status === "queued" || row.status === "fetching") acc.queued += 1;
      else if (row.status === "translating") acc.translating += 1;
      else if (row.status === "ready") acc.ready += 1;
      else if (row.status === "saved") acc.saved += 1;
      else if (row.status === "error") acc.error += 1;
      else if (row.status === "skipped") acc.skipped += 1;
      else if (row.status === "not_found") acc.not_found += 1;
    }
    return acc;
  }, [project.labels]);

  /** Fetch EN from DDC then call /translate. Drives one alias through both
   *  network steps and writes the result back to the store. */
  const runTranslation = useCallback(
    async (alias: string) => {
      const activeProvider = await ensureProvider();
      if (!activeProvider) return;

      setBusyAlias(alias);
      try {
        updateSpanishLabel(project.id, alias, {
          status: "fetching",
          error: null,
          warnings: [],
        });

        const ddc = await labelPort.fetchLabel(project.dealerId, alias);
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

        const translation = await labelPort.translateLabel({
          alias,
          en_html: ddc.en,
          dealer_name: project.dealerName,
          provider: activeProvider,
        });

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
      } catch (err) {
        updateSpanishLabel(project.id, alias, {
          status: "error",
          error: err instanceof Error ? err.message : String(err),
        });
      } finally {
        setBusyAlias(null);
      }
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

  /** Walk through the labels list, translating one at a time. Each row pauses
   *  on `ready` so the user can review-and-save before we move to the next. */
  const advanceToNext = useCallback(async () => {
    const next = project.labels.find((row) => row.status === "queued");
    if (!next) return;
    await runTranslation(next.alias);
  }, [project.labels, runTranslation]);

  const handleSubmit = useCallback(async () => {
    if (!rawInput.trim()) return;
    setSubmitting(true);
    try {
      const { aliases, dropped: droppedList } =
        await labelPort.sanitizeAliases(rawInput);
      setDropped(droppedList);
      setSpanishLabels(project.id, aliases);
      // Trigger the first translation immediately so the user sees a row
      // come alive without an extra click.
      const first = aliases[0];
      if (first) {
        await runTranslation(first);
      }
    } catch (err) {
      console.error("sanitize failed", err);
    } finally {
      setSubmitting(false);
    }
  }, [labelPort, project.id, rawInput, runTranslation, setSpanishLabels]);

  const handleSave = useCallback(
    async (alias: string) => {
      const row = project.labels.find((r) => r.alias === alias);
      if (!row || row.enHtml === null) return;

      setBusyAlias(alias);
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
      } finally {
        setBusyAlias(null);
      }

      // Auto-advance to the next queued row.
      await advanceToNext();
    },
    [
      advanceToNext,
      labelPort,
      project.dealerId,
      project.id,
      project.labels,
      updateSpanishLabel,
    ],
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

  const hasLabels = project.labels.length > 0;

  return (
    <div className="flex flex-col gap-6">
      {/* ── Input ────────────────────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle>Paste label aliases</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <Textarea
            value={rawInput}
            onChange={(e) => setRawInput(e.target.value)}
            rows={6}
            placeholder={"ABOUT_PAGE_VERBIAGE\nCONTACT_2\nFEATURED_VEHICLES_4"}
            className="font-mono text-xs"
            disabled={submitting}
          />
          <div className="flex justify-end">
            <Button
              type="button"
              onClick={handleSubmit}
              disabled={submitting || !rawInput.trim()}
            >
              {submitting ? "Sanitizing…" : "Start translation"}
            </Button>
          </div>
          {dropped.length > 0 && (
            <p className="text-xs text-muted-foreground">
              Dropped {dropped.length} invalid entr
              {dropped.length === 1 ? "y" : "ies"}: {dropped.join(", ")}
            </p>
          )}
          {credError && (
            <p className="text-xs text-destructive">{credError}</p>
          )}
        </CardContent>
      </Card>

      {/* ── Counters ─────────────────────────────────────────────────────── */}
      {hasLabels && (
        <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
          <Counter label="Queued" value={counts.queued} />
          <Counter label="Translating" value={counts.translating} />
          <Counter label="Ready" value={counts.ready} />
          <Counter label="Saved" value={counts.saved} />
          <Counter label="Error" value={counts.error} />
          <Counter label="Skipped" value={counts.skipped} />
          <Counter label="Not found" value={counts.not_found} />
        </div>
      )}

      {/* ── Rows ─────────────────────────────────────────────────────────── */}
      <div className="flex flex-col gap-3">
        {project.labels.map((row) => (
          <LabelRow
            key={row.alias}
            row={row}
            busy={busyAlias === row.alias}
            onEsChange={(esHtml) =>
              updateSpanishLabel(project.id, row.alias, { esHtml })
            }
            onSave={() => handleSave(row.alias)}
            onSkip={() => handleSkip(row.alias)}
            onRetranslate={() => handleRetranslate(row.alias)}
          />
        ))}
      </div>
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
