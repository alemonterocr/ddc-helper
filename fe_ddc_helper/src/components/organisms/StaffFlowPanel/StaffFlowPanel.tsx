import { useMemo, useRef, useState } from "react";
import type { MigrationPage } from "../../../store/types";
import type {
  DOMSkeleton,
  StaffMember,
  GMOrCMProjectType,
} from "../../../types";
import type {
  BackendPort,
  CredentialPort,
  DOMExtractorPort,
  WSClientPort,
} from "../../../services/ports";
import { useMigrationStore } from "../../../store/useMigrationStore";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { InputGroup, InputGroupTextarea } from "@/components/ui/input-group";
import { Users, Play, RotateCcw, UserPlus, ArrowLeft, AlertTriangle, Wand2, FileCode } from "lucide-react";
import { log } from "../../../log";
import {
  TokenBadge,
  LatestStepIndicator,
  ExecutionLog,
} from "../_flowShared/flowShared";
import { StaffMemberCard } from "../../molecules/StaffMemberCard/StaffMemberCard";

interface StaffFlowPanelProps {
  projectId: string;
  projectType: GMOrCMProjectType;
  page: MigrationPage;
  backendPort: BackendPort;
  credentialPort: CredentialPort;
  extractorPort: DOMExtractorPort;
  createWSClient: () => WSClientPort;
}

/**
 * Staff-page migration center panel.
 *
 * Mirrors MigrationFlowPanel's status-driven rendering but talks to the
 * staff endpoints (/parse-staff + /execute-staff) and uses a flat
 * StaffMember[] instead of a section plan.
 */
export function StaffFlowPanel({
  projectId,
  projectType,
  page,
  backendPort,
  credentialPort,
  extractorPort,
  createWSClient,
}: StaffFlowPanelProps) {
  const { updatePage, appendProgressLog, setPageStatus } = useMigrationStore();
  const wsRef = useRef<WSClientPort | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  function patch(p: Partial<MigrationPage>) {
    updatePage(projectId, page.id, p);
  }
  function appendLog(entry: string) {
    appendProgressLog(projectId, page.id, entry);
  }
  function dealerId(): string {
    const state = useMigrationStore.getState();
    const project =
      state.migrationProjects.find((p) => p.id === projectId) ??
      state.prebuildProjects.find((p) => p.id === projectId);
    return project?.dealerId ?? "";
  }

  // ── Extract ──────────────────────────────────────────────────────────────

  /** Auto path: capture skeleton from the live tab and parse. */
  async function handleExtract() {
    await runExtraction((abortSignal) =>
      extractorPort.extract(page.liveSiteUrl, abortSignal),
    );
  }

  /** Manual path: build a stub skeleton around the user-pasted HTML.
   *  parse-staff only consumes `dom_skeleton.raw_html` and `dom_skeleton.url`,
   *  so the rest of the skeleton can be a no-op stub. */
  async function handleExtractFromHtml(rawHtml: string) {
    await runExtraction(async () => ({
      url: page.liveSiteUrl,
      title: page.pageTitle ?? "",
      structure: {
        tag: "body",
        cls: "",
        text: "",
        x: 0,
        y: 0,
        w: 0,
        h: 0,
        children: [],
      },
      raw_html: rawHtml,
    }));
  }

  /** Shared analyze pipeline. `produceSkeleton` returns the DOMSkeleton to
   *  send to /parse-staff — auto path calls the extractor; manual path
   *  returns a stub built from pasted HTML. */
  async function runExtraction(
    produceSkeleton: (abortSignal: AbortSignal) => Promise<DOMSkeleton>,
  ) {
    const stored = await credentialPort.getStoredApiKey();
    if (!stored) {
      patch({ status: "error", error: "No LLM API key configured." });
      return;
    }

    patch({
      status: "analyzing",
      error: null,
      progressLog: [],
      warnings: [],
      staffPlan: null,
    });

    const abort = new AbortController();
    abortRef.current = abort;
    const ws = createWSClient();
    wsRef.current = ws;

    try {
      await backendPort
        .configureApiKey({ provider: stored.provider, api_key: stored.apiKey })
        .catch((err) =>
          log.warn("Failed to re-push API key", {
            errorMessage: err instanceof Error ? err.message : String(err),
          }),
        );

      await ws.connect(dealerId(), (msg) => appendLog(msg));

      const skeleton = await produceSkeleton(abort.signal);

      const response = await backendPort.parseStaff(
        {
          dealer_id: dealerId(),
          project_type: projectType,
          dom_skeleton: skeleton,
          provider: stored.provider,
        },
        abort.signal,
      );

      if (response.error) {
        patch({ status: "error", error: response.error });
        return;
      }

      patch({
        status: "reviewing",
        staffPlan: response.staff,
        warnings: response.warnings,
        tokenInfo: response.token_info ?? null,
      });
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      patch({
        status: "error",
        error: err instanceof Error ? err.message : "Staff extraction failed",
      });
    } finally {
      ws.disconnect();
      wsRef.current = null;
      abortRef.current = null;
    }
  }

  // ── Execute ──────────────────────────────────────────────────────────────

  async function handleExecute() {
    if (!page.staffPlan || page.staffPlan.length === 0) return;

    setPageStatus(projectId, page.id, "executing");
    patch({ error: null });

    const abort = new AbortController();
    abortRef.current = abort;
    const ws = createWSClient();
    wsRef.current = ws;

    try {
      await ws.connect(dealerId(), (msg) => appendLog(msg));

      const result = await backendPort.executeStaff(
        {
          dealer_id: dealerId(),
          project_type: projectType,
          staff: page.staffPlan,
        },
        abort.signal,
      );

      if (!result.ok) throw new Error(result.error ?? "Staff execution failed");

      patch({
        status: "done",
        warnings: [...page.warnings, ...(result.warnings ?? [])],
        completedAt: Date.now(),
      });
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      patch({
        status: "error",
        error: err instanceof Error ? err.message : "Staff execution failed",
      });
    } finally {
      ws.disconnect();
      wsRef.current = null;
      abortRef.current = null;
    }
  }

  // ── Reset / edit handlers ───────────────────────────────────────────────

  function handleReset() {
    abortRef.current?.abort();
    abortRef.current = null;
    wsRef.current?.disconnect();
    wsRef.current = null;
    patch({
      status: "pending",
      error: null,
      staffPlan: null,
      warnings: [],
      progressLog: [],
      tokenInfo: null,
      completedAt: null,
    });
  }

  function updateMemberAt(deptIdx: number, memberInDept: number, patchMember: Partial<StaffMember>) {
    if (!page.staffPlan) return;
    const grouped = groupByDepartment(page.staffPlan);
    const entry = grouped[deptIdx];
    if (!entry) return;
    const member = entry.members[memberInDept];
    if (!member) return;
    const next = page.staffPlan.map((m) => (m === member ? { ...m, ...patchMember } : m));
    patch({ staffPlan: next });
  }

  function deleteMemberAt(deptIdx: number, memberInDept: number) {
    if (!page.staffPlan) return;
    const grouped = groupByDepartment(page.staffPlan);
    const entry = grouped[deptIdx];
    if (!entry) return;
    const member = entry.members[memberInDept];
    if (!member) return;
    patch({ staffPlan: page.staffPlan.filter((m) => m !== member) });
  }

  // ── Render ──────────────────────────────────────────────────────────────

  const { status, error, progressLog, warnings, staffPlan, tokenInfo } = page;

  if (status === "pending") {
    return (
      <PendingView
        url={page.liveSiteUrl}
        onStartAuto={handleExtract}
        onStartManual={handleExtractFromHtml}
        onMarkRegular={() => patch({ pageType: "regular" })}
      />
    );
  }

  if (status === "analyzing") {
    return (
      <div className="flex flex-col gap-4 h-full">
        <LatestStepIndicator entries={progressLog} initialMessage="Capturing staff page…" />
      </div>
    );
  }

  if (status === "reviewing") {
    return (
      <ReviewView
        staff={staffPlan ?? []}
        warnings={warnings}
        tokenInfo={tokenInfo}
        onExecute={handleExecute}
        onReset={handleReset}
        onUpdateMember={updateMemberAt}
        onDeleteMember={deleteMemberAt}
      />
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
            Staff page complete
          </p>
          <p className="text-sm text-foreground">
            {staffPlan?.length ?? 0} staff member(s) injected
          </p>
          {warnings.length > 0 && (
            <ul className="mt-2 space-y-1">
              {warnings.map((w, i) => (
                <li key={i} className="text-xs text-warning flex items-start gap-1"><AlertTriangle size={12} className="shrink-0 mt-0.5" /> {w}</li>
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

// ── Sub-views ──────────────────────────────────────────────────────────────

function PendingView({
  url,
  onStartAuto,
  onStartManual,
  onMarkRegular,
}: {
  url: string;
  onStartAuto: () => void;
  onStartManual: (html: string) => void;
  onMarkRegular: () => void;
}) {
  const [mode, setMode] = useState<"auto" | "manual">("auto");
  const [pastedHtml, setPastedHtml] = useState("");

  const manualReady = pastedHtml.trim().length >= 30;

  return (
    <div className="flex flex-col items-center justify-center h-full gap-6 max-w-2xl mx-auto w-full px-4">
      <div className="flex flex-col items-center gap-2 text-center">
        <Badge className="bg-primary/10 text-primary border-transparent">
          <Users size={12} className="mr-1" /> Staff Page
        </Badge>
        <p className="text-xs text-muted-foreground font-medium mt-2">Page URL</p>
        <p className="text-sm text-foreground font-mono break-all max-w-md">{url}</p>
      </div>

      {/* Mode picker */}
      <div className="flex gap-2 w-full max-w-md">
        <Button
          type="button"
          variant={mode === "auto" ? "default" : "outline"}
          className="flex-1"
          onClick={() => setMode("auto")}
        >
          <Wand2 size={14} className="mr-2" /> Capture automatically
        </Button>
        <Button
          type="button"
          variant={mode === "manual" ? "default" : "outline"}
          className="flex-1"
          onClick={() => setMode("manual")}
        >
          <FileCode size={14} className="mr-2" /> Paste HTML manually
        </Button>
      </div>

      {/* Mode body */}
      {mode === "auto" ? (
        <div className="flex flex-col items-center gap-2">
          <Button onClick={onStartAuto}>
            <Play size={14} className="mr-2" /> Extract Staff
          </Button>
          <p className="text-[11px] text-muted-foreground text-center max-w-sm">
            Opens the live page in a background tab and walks the DOM. Use this when the source site loads normally.
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-3 w-full max-w-md">
          <InputGroup>
            <InputGroupTextarea
              value={pastedHtml}
              onChange={(e) => setPastedHtml(e.target.value)}
              placeholder='Paste the staff page HTML. Open the source page, view-source or copy outerHTML on the main content element, paste here.'
              rows={10}
              className="min-h-32 max-h-72 resize-none overflow-y-auto scrollbar-thin font-mono text-xs"
            />
          </InputGroup>
          <Button onClick={() => onStartManual(pastedHtml)} disabled={!manualReady}>
            <Play size={14} className="mr-2" /> Extract from pasted HTML
          </Button>
          <p className="text-[11px] text-muted-foreground text-center">
            Use this when the automatic capture fails (lazy loading, auth gates, etc.).
          </p>
        </div>
      )}

      <Button
        variant="link"
        size="sm"
        onClick={onMarkRegular}
        className="text-xs"
        title="Switch back to regular page migration"
      >
        <ArrowLeft size={12} className="mr-1" /> This is a regular page
      </Button>
    </div>
  );
}

function ReviewView({
  staff,
  warnings,
  tokenInfo,
  onExecute,
  onReset,
  onUpdateMember,
  onDeleteMember,
}: {
  staff: StaffMember[];
  warnings: string[];
  tokenInfo: MigrationPage["tokenInfo"];
  onExecute: () => void;
  onReset: () => void;
  onUpdateMember: (deptIdx: number, memberInDept: number, patch: Partial<StaffMember>) => void;
  onDeleteMember: (deptIdx: number, memberInDept: number) => void;
}) {
  const grouped = useMemo(() => groupByDepartment(staff), [staff]);
  const totalWithPhoto = staff.filter((m) => m.has_photo).length;

  return (
    <div className="flex flex-col gap-4 h-full min-h-0">
      {tokenInfo && <TokenBadge info={tokenInfo} />}

      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-foreground">
          Staff Plan
          <span className="ml-2 text-muted-foreground font-normal">
            ({staff.length} member{staff.length !== 1 ? "s" : ""} · {totalWithPhoto} with photos)
          </span>
        </h2>
        {warnings.length > 0 && (
          <Badge className="bg-warning/10 text-warning border-transparent">
            {warnings.length} warning{warnings.length > 1 ? "s" : ""}
          </Badge>
        )}
      </div>

      {warnings.length > 0 && (
        <ul className="flex flex-col gap-1">
          {warnings.map((w) => (
              <li key={w} className="text-xs text-warning bg-warning/10 px-3 py-2 rounded-md flex items-start gap-1.5">
                <AlertTriangle size={12} className="shrink-0 mt-0.5" /> {w}
              </li>
          ))}
        </ul>
      )}

      <div className="flex flex-col gap-4 overflow-y-auto flex-1 min-h-0 pr-1 scrollbar-thin">
        {grouped.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center gap-2 text-center py-12">
            <UserPlus size={32} className="text-muted-foreground" />
            <p className="text-sm text-muted-foreground">No staff members extracted.</p>
            <Button variant="outline" size="sm" onClick={onReset}>
              Try again
            </Button>
          </div>
        ) : (
          grouped.map((dept, deptIdx) => (
            <div key={dept.name} className="flex flex-col gap-2">
              <div className="flex items-center gap-2">
                <h3 className="text-xs font-mono text-muted-foreground">
                  {dept.name}
                </h3>
                <span className="text-xs text-muted-foreground/70">
                  {dept.members.length}
                </span>
              </div>
              <div className="flex flex-col gap-2">
                {dept.members.map((member, memberIdx) => (
                  <StaffMemberCard
                    key={`${dept.name}-${memberIdx}-${member.name}`}
                    member={member}
                    index={memberIdx}
                    onEdit={(i, patch) => onUpdateMember(deptIdx, i, patch)}
                    onDelete={(i) => onDeleteMember(deptIdx, i)}
                  />
                ))}
              </div>
            </div>
          ))
        )}
      </div>

      <div className="flex gap-2 pt-3 border-t border-border shrink-0">
        <Button variant="outline" onClick={onReset}>
          Reset
        </Button>
        <Button onClick={onExecute} disabled={staff.length === 0} className="flex-1">
          <Play size={14} className="mr-2" /> Execute Staff Migration
        </Button>
      </div>
    </div>
  );
}

// ── Utils ──────────────────────────────────────────────────────────────────

interface DepartmentGroup {
  name: string;
  members: StaffMember[];
}

function groupByDepartment(staff: StaffMember[]): DepartmentGroup[] {
  const map = new Map<string, StaffMember[]>();
  for (const m of staff) {
    const dept = m.department || "Other";
    if (!map.has(dept)) map.set(dept, []);
    map.get(dept)!.push(m);
  }
  return Array.from(map.entries()).map(([name, members]) => ({ name, members }));
}

