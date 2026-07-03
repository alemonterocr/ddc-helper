/**
 * Shared sub-components used by both MigrationFlowPanel (regular page
 * migration) and StaffFlowPanel (staff page migration). Lifted here so the
 * two flow panels stay consistent in styling and behavior without
 * duplicating render code.
 */

import { useState } from "react";
import { Loader2, AlertTriangle, ChevronDown, ChevronRight } from "lucide-react";
import type { TokenInfo } from "../../../types";

// ── Token badge ──────────────────────────────────────────────────────────────

function formatCost(usd: number): string {
  if (usd === 0) return "$0.00";
  if (usd < 0.001) return `$${usd.toFixed(5)}`;
  if (usd < 0.01) return `$${usd.toFixed(4)}`;
  return `$${usd.toFixed(3)}`;
}

export function TokenBadge({ info }: { info: TokenInfo }) {
  const [open, setOpen] = useState(false);
  const totalTokens = info.total_input_tokens + info.total_output_tokens;
  const isDeterministic = totalTokens === 0;

  if (isDeterministic) {
    return (
      <div className="flex items-center gap-2 rounded-md border border-border bg-card px-3 py-2">
        <span className="text-xs text-success font-mono font-semibold">$0.00</span>
        <span className="text-muted-foreground">·</span>
        <span className="text-xs text-muted-foreground">
          deterministic — no LLM calls
        </span>
      </div>
    );
  }

  return (
    <div className="rounded-md border border-border bg-card">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-3 px-3 py-2 cursor-pointer hover:bg-accent/40 transition-colors rounded-md"
        title={open ? "Hide stage breakdown" : "Show stage breakdown"}
      >
        <span className="text-xs text-muted-foreground font-mono">
          <span className="text-foreground font-semibold">
            {totalTokens.toLocaleString()}
          </span>{" "}
          tokens
        </span>
        <span className="text-muted-foreground">·</span>
        <span className="text-xs text-muted-foreground font-mono">
          <span className="text-primary font-semibold">
            {formatCost(info.total_cost_usd)}
          </span>
        </span>
        <span className="ml-auto text-muted-foreground">
          {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        </span>
      </button>
      {open && info.by_stage.length > 0 && (
        <div className="border-t border-border px-3 py-2 flex flex-col gap-1">
          {info.by_stage.map((u, i) => (
            <div
              key={i}
              className="flex items-center gap-2 text-[11px] font-mono text-muted-foreground"
            >
              <span className="text-foreground min-w-[80px]">{u.stage}</span>
              <span className="text-muted-foreground/70">{u.model}</span>
              <span className="ml-auto">
                {u.input_tokens.toLocaleString()} in ·{" "}
                {u.output_tokens.toLocaleString()} out
              </span>
              <span className="text-primary min-w-[60px] text-right">
                {formatCost(u.cost_usd)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Latest step indicator ────────────────────────────────────────────────────

export function LatestStepIndicator({
  entries,
  initialMessage = "Capturing page…",
}: {
  entries: string[];
  initialMessage?: string;
}) {
  if (entries.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center gap-4 px-6 text-center">
        <Loader2 size={32} className="animate-spin text-primary" />
        <p className="text-sm text-muted-foreground">{initialMessage}</p>
      </div>
    );
  }

  const latest = entries[entries.length - 1]!;
  const earlier = entries.slice(0, -1);
  const isWarning = /^[⚠❌]/.test(latest);
  const stripped = (s: string) => s.replace(/^[✓⚠❌]\s*/, "").trim();

  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-6 px-6 text-center">
      {isWarning ? (
        <AlertTriangle size={32} className="text-warning" />
      ) : (
        <Loader2 size={32} className="animate-spin text-primary" />
      )}
      <p className="text-base font-medium text-foreground max-w-md">
        {stripped(latest)}
      </p>
      {earlier.length > 0 && (
        <p className="text-xs text-muted-foreground max-w-md leading-relaxed">
          {earlier.map(stripped).join(" · ")}
        </p>
      )}
    </div>
  );
}

// ── Execution log ────────────────────────────────────────────────────────────

export function ExecutionLog({
  entries,
  isLive = false,
}: {
  entries: string[];
  isLive?: boolean;
}) {
  return (
    <div className="rounded-lg border border-border bg-card p-3 flex flex-col gap-1.5 overflow-y-auto max-h-80 scrollbar-thin">
      {entries.length === 0 ? (
        <p className="text-xs text-muted-foreground animate-pulse">
          Waiting for backend…
        </p>
      ) : (
        entries.map((entry, i) => {
          const isLast = i === entries.length - 1;
          return (
            <p
              key={i}
              className={[
                "text-xs font-mono",
                entry.startsWith("❌")
                  ? "text-destructive"
                  : entry.startsWith("⚠")
                    ? "text-warning"
                    : entry.startsWith("✓")
                      ? "text-success"
                      : "text-muted-foreground",
                isLive && isLast ? "animate-pulse" : "",
              ].join(" ")}
            >
              {entry}
            </p>
          );
        })
      )}
    </div>
  );
}
