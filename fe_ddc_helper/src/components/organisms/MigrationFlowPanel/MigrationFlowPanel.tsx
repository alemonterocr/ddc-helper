import { useRef } from "react";
import type { MigrationPage } from "../../../store/types";
import { TokenBadge, LatestStepIndicator, ExecutionLog } from "../_flowShared/flowShared";
import { Users } from "lucide-react";
import type {
  BackendPort,
  CredentialPort,
  DOMExtractorPort,
  WSClientPort,
} from "../../../services/ports";
import { useMigrationStore } from "../../../store/useMigrationStore";
import { Button } from "@/components/ui/button";
import { InputGroup, InputGroupInput } from "@/components/ui/input-group";
import { log } from "../../../log";
import { applyLinkReplacements } from "../../../services/linkReplacement";
import { reindexPlan, defaultWidgetForType } from "../../../services/planEdit";
import type { ColumnWidget } from "../../../types";
import { StructurePlanPreview } from "../StructurePlanPreview/StructurePlanPreview";
import { Play, RotateCcw } from "lucide-react";

interface MigrationFlowPanelProps {
  projectId: string;
  page: MigrationPage;
  backendPort: BackendPort;
  credentialPort: CredentialPort;
  extractorPort: DOMExtractorPort;
  /** Factory — call to create a fresh WS connection wrapper per operation. */
  createWSClient: () => WSClientPort;
}

/**
 * Center panel — drives the full analyze → review → execute flow for a single
 * MigrationPage. Reads page state from the Zustand store; writes back via
 * updatePage / appendProgressLog / setPageStatus.
 *
 * Ports come in as props from the composition root (see App.tsx) — this
 * organism never imports concrete adapters.
 */
export function MigrationFlowPanel({
  projectId,
  page,
  backendPort,
  credentialPort,
  extractorPort,
  createWSClient,
}: MigrationFlowPanelProps) {
  const {
    updatePage,
    appendProgressLog,
    setPageStatus,
    addSection,
    addWidget,
    deleteWidget,
    updateWidget,
    moveSection,
    moveWidget,
  } = useMigrationStore();
  const wsRef = useRef<WSClientPort | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  // ── Helpers that write to store ───────────────────────────────────────────

  function patch(p: Partial<MigrationPage>) {
    updatePage(projectId, page.id, p);
  }

  function appendLog(entry: string) {
    appendProgressLog(projectId, page.id, entry);
  }

  // ── Analyze ───────────────────────────────────────────────────────────────

  async function handleAnalyze() {
    const stored = await credentialPort.getStoredApiKey();
    if (!stored) {
      patch({
        status: "error",
        error: "No API key configured. Please set one on the home screen.",
      });
      return;
    }

    patch({
      status: "analyzing",
      error: null,
      progressLog: [],
      warnings: [],
      sectionPlan: [],
    });

    const abort = new AbortController();
    abortRef.current = abort;

    const ws = createWSClient();
    wsRef.current = ws;

    try {
      // Re-push the stored API key — backend is stateless and loses it on
      // restart. Best-effort: if it fails (e.g. backend not running yet) we
      // still want the analyze attempt to proceed and surface its own error.
      await backendPort
        .configureApiKey({ provider: stored.provider, api_key: stored.apiKey })
        .catch((err) =>
          log.warn("Failed to re-push API key to backend; continuing analyze", {
            errorMessage: err instanceof Error ? err.message : String(err),
          }),
        );

      // Open WS so the backend can stream segmentation + per-block progress.
      await ws.connect(_dealerId(), (msg) => appendLog(msg));

      const skeleton = await extractorPort.extract(
        page.liveSiteUrl,
        abort.signal,
      );

      // No pre-flight token estimate. The skeleton length is a misleading
      // proxy for actual LLM input (most of it never reaches the LLM —
      // deterministic algo handles it). Real numbers come back in the
      // response's token_info, computed from each LLM call's reported usage.

      const response = await backendPort.analyzePage(
        {
          dom_skeleton: skeleton,
          dealer_id: _dealerId(),
          provider: stored.provider,
        },
        abort.signal,
      );

      patch({
        status: "reviewing",
        sectionPlan: response.section_plan,
        warnings: response.warnings,
        pageAlias: response.page_alias,
        pageTitle: response.page_title,
        tokenInfo: response.token_info ?? null,
      });
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      patch({
        status: "error",
        error: err instanceof Error ? err.message : "Analysis failed",
      });
    } finally {
      ws.disconnect();
      wsRef.current = null;
      abortRef.current = null;
    }
  }

  // ── Execute ───────────────────────────────────────────────────────────────

  async function handleExecute() {
    setPageStatus(projectId, page.id, "executing");
    patch({ error: null });

    const abort = new AbortController();
    abortRef.current = abort;

    const ws = createWSClient();
    wsRef.current = ws;

    try {
      await ws.connect(_dealerId(), (msg) => appendLog(msg));

      // Apply user-supplied link replacements to a copy of the plan before
      // sending — original sectionPlan in the store is never mutated.
      const finalPlan = applyLinkReplacements(
        page.sectionPlan,
        page.linkReplacements ?? {},
      );

      const result = await backendPort.executeMigration(
        {
          dealer_id: _dealerId(),
          page_alias: page.pageAlias ?? "",
          page_title: page.pageTitle ?? "",
          section_plan: finalPlan,
        },
        abort.signal,
      );

      if (!result.ok) throw new Error(result.error ?? "Execution failed");

      patch({
        status: "done",
        ddcAlias: result.page_alias,
        warnings: [...page.warnings, ...(result.warnings ?? [])],
        completedAt: Date.now(),
      });
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      patch({
        status: "error",
        error: err instanceof Error ? err.message : "Execution failed",
      });
    } finally {
      ws.disconnect();
      wsRef.current = null;
      abortRef.current = null;
    }
  }

  // ── Reset ─────────────────────────────────────────────────────────────────

  function handleRemoveSection(position: number) {
    const filtered = page.sectionPlan.filter((s) => s.position !== position);
    patch({ sectionPlan: reindexPlan(filtered) });
  }

  function handleAddSection(atIndex: number, sectionType: string) {
    addSection(projectId, page.id, atIndex, sectionType);
  }

  function handleAddWidget(
    sectionPos: number,
    slotIndex: number,
    widgetType: string,
  ) {
    addWidget(
      projectId,
      page.id,
      sectionPos,
      slotIndex,
      defaultWidgetForType(widgetType),
    );
  }

  function handleDeleteWidget(
    sectionPos: number,
    slotIndex: number,
    widgetIndex: number,
  ) {
    deleteWidget(projectId, page.id, sectionPos, slotIndex, widgetIndex);
  }

  function handleUpdateWidget(
    sectionPos: number,
    slotIndex: number,
    widgetIndex: number,
    patch: Partial<import("../../../types").ColumnWidget>,
  ) {
    updateWidget(projectId, page.id, sectionPos, slotIndex, widgetIndex, patch);
  }

  function handleMoveSection(fromIndex: number, toIndex: number) {
    moveSection(projectId, page.id, fromIndex, toIndex);
  }

  function handleMoveWidget(
    from: { sectionPos: number; slotIndex: number; widgetIndex: number },
    to: { sectionPos: number; slotIndex: number; widgetIndex: number },
  ) {
    moveWidget(projectId, page.id, from, to);
  }

  function handlePasteWidgets(sectionPos: number, slotIndex: number, widgets: ColumnWidget[]) {
    for (const widget of widgets) {
      addWidget(projectId, page.id, sectionPos, slotIndex, widget);
    }
  }

  function handleReset() {
    abortRef.current?.abort();
    abortRef.current = null;
    wsRef.current?.disconnect();
    wsRef.current = null;
    patch({
      status: "pending",
      error: null,
      sectionPlan: [],
      warnings: [],
      progressLog: [],
      tokenInfo: null,
      pageAlias: null,
      pageTitle: null,
      ddcAlias: null,
      completedAt: null,
      linkReplacements: {},
    });
  }

  // ── Helpers ───────────────────────────────────────────────────────────────

  // Dealer ID is stored on the project — reach into the store once.
  // Search all project type buckets (CM + GM Prebuild + GM Buysell) because
  // the active project can live in any of them.
  function _dealerId(): string {
    const state = useMigrationStore.getState();
    const project =
      state.migrationProjects.find((p) => p.id === projectId) ??
      state.prebuildProjects.find((p) => p.id === projectId) ??
      state.buySellProjects.find((p) => p.id === projectId);
    return project?.dealerId ?? "";
  }

  // ── Render ────────────────────────────────────────────────────────────────

  const {
    status,
    error,
    progressLog,
    warnings,
    sectionPlan,
    ddcAlias,
    tokenInfo,
  } = page;

  if (status === "pending") {
    return (
      <PendingView
        url={page.liveSiteUrl}
        onStart={handleAnalyze}
        onMarkStaff={() => patch({ pageType: "staff" })}
      />
    );
  }

  if (status === "analyzing") {
    return (
      <div className="flex flex-col gap-4 h-full">
        {tokenInfo && <TokenBadge info={tokenInfo} />}
        <LatestStepIndicator entries={progressLog} />
      </div>
    );
  }

  if (status === "reviewing") {
    return (
      <div className="flex flex-col gap-4 h-full">
        {tokenInfo && <TokenBadge info={tokenInfo} />}
        <div className="flex flex-col gap-2">
          <InputGroup>
            <InputGroupInput
              value={page.pageTitle ?? ""}
              onChange={(e) => patch({ pageTitle: e.target.value })}
              placeholder="Page title"
              className="text-sm"
            />
          </InputGroup>
          <InputGroup>
            <InputGroupInput
              value={page.pageAlias ?? ""}
              onChange={(e) => patch({ pageAlias: e.target.value })}
              placeholder="e.g. about-us.htm"
              className="text-sm font-mono"
            />
          </InputGroup>
          <p className="text-[11px] text-muted-foreground px-1">
            Title and URL path for the page in DDC. Edit before executing if the defaults look wrong.
          </p>
        </div>
        <StructurePlanPreview
          plan={sectionPlan}
          warnings={warnings}
          onExecute={handleExecute}
          onRemoveSection={handleRemoveSection}
          onAddSection={handleAddSection}
          onAddWidget={handleAddWidget}
          onDeleteWidget={handleDeleteWidget}
          onUpdateWidget={handleUpdateWidget}
          onMoveSection={handleMoveSection}
          onMoveWidget={handleMoveWidget}
          onPasteWidgets={handlePasteWidgets}
          isExecuting={false}
        />
      </div>
    );
  }

  if (status === "executing") {
    return (
      <div className="flex flex-col gap-3 h-full">
        {tokenInfo && <TokenBadge info={tokenInfo} />}
        <ExecutionLog entries={progressLog} isLive />
      </div>
    );
  }

  if (status === "done") {
    return (
      <div className="flex flex-col gap-4 h-full">
        {tokenInfo && <TokenBadge info={tokenInfo} />}
        <ExecutionLog entries={progressLog} />
        <div className="rounded-lg border border-border bg-card p-4 flex flex-col gap-1">
          <p className="text-xs font-semibold text-success">
            Migration complete
          </p>
          {ddcAlias && (
            <p className="text-sm text-foreground font-mono break-all">
              {ddcAlias}
            </p>
          )}
          {warnings.length > 0 && (
            <ul className="mt-2 space-y-1">
              {warnings.map((w, i) => (
                <li key={i} className="text-xs text-warning">
                  ⚠ {w}
                </li>
              ))}
            </ul>
          )}
        </div>
        <Button variant="link" size="sm" onClick={handleReset} className="self-start">
          <RotateCcw size={12} className="mr-1" /> Re-run migration
        </Button>
      </div>
    );
  }

  // error
  return (
    <div className="flex flex-col items-center justify-center h-full gap-6">
      {tokenInfo && <TokenBadge info={tokenInfo} />}
      {progressLog.length > 0 && <ExecutionLog entries={progressLog} />}
      <div className="flex flex-col items-center gap-4">
        <p className="text-sm text-destructive break-words text-center">{error}</p>
        <Button variant="link" size="sm" onClick={handleReset}>
          <RotateCcw size={12} className="mr-1" /> Try again
        </Button>
      </div>
    </div>
  );
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function PendingView({
  url,
  onStart,
  onMarkStaff,
}: {
  url: string;
  onStart: () => void;
  onMarkStaff: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-6">
      <div className="flex flex-col items-center gap-2 text-center">
        <p className="text-xs text-muted-foreground font-medium">Page URL</p>
        <p className="text-sm text-foreground font-mono break-all max-w-md">{url}</p>
      </div>
      <Button onClick={onStart}>
        <Play size={14} className="mr-2" /> Start Migration
      </Button>
      <button
        onClick={onMarkStaff}
        className="text-xs text-muted-foreground hover:text-primary flex items-center gap-1.5 cursor-pointer transition-colors"
        title="Switch to the staff migration workflow"
      >
        <Users size={12} /> This is a Staff Page
      </button>
    </div>
  );
}

// Shared sub-components (TokenBadge, LatestStepIndicator, ExecutionLog) moved
// to ../_flowShared/flowShared.tsx — both flow panels import them from there.
