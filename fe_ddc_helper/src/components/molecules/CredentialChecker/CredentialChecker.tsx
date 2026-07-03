import type { CredentialStatus } from "../../../types";
import { StatusDot } from "../../atoms/StatusDot/StatusDot";
import { Button } from "@/components/ui/button";
import { RotateCw } from "lucide-react";

interface CredentialCheckerProps {
  credentials: CredentialStatus | null;
  checking: boolean;
  refreshing: "ccIdt" | "llmKey" | "mediaLib" | null;
  onCheck: () => void;
  onRefreshCcIdt: () => void;
  onRefreshLlmKey: () => void;
  onRefreshMediaLib: () => void;
  onChangeLlmKey?: () => void;
  /**
   * Whether to show the Media Library check row. Defaults to true.
   * Spanish translation projects don't upload images, so we hide it there
   * to avoid asking the specialist to open an irrelevant tab.
   */
  includeMediaLib?: boolean;
}

function CredentialRow({
  label,
  ok,
  onRefresh,
  refreshing,
}: {
  label: string;
  ok: boolean;
  onRefresh: () => void;
  refreshing: boolean;
}) {
  return (
    <div className="flex items-center justify-between">
      <StatusDot status={ok ? "ok" : "error"} label={label} />
      <Button
        variant="ghost"
        size="icon"
        className="h-5 w-5"
        onClick={onRefresh}
        disabled={refreshing}
        title="Re-check"
      >
        <RotateCw size={12} className={refreshing ? "animate-spin" : ""} />
      </Button>
    </div>
  );
}

export function CredentialChecker({
  credentials,
  checking,
  refreshing,
  onCheck,
  onRefreshCcIdt,
  onRefreshLlmKey,
  onRefreshMediaLib,
  onChangeLlmKey,
  includeMediaLib = true,
}: CredentialCheckerProps) {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-3">
        <Button
          variant="outline"
          size="sm"
          onClick={onCheck}
          disabled={checking}
        >
          {checking ? "Checking…" : "Check"}
        </Button>
        <span className="text-sm text-foreground">Verify credentials</span>
      </div>

      {credentials && (
        <div className="flex flex-col gap-2">
          <CredentialRow
            label={`CC-IDT Token${credentials.createdBy ? ` · ${credentials.createdBy}` : ""}`}
            ok={Boolean(credentials.ccIdtToken)}
            onRefresh={onRefreshCcIdt}
            refreshing={refreshing === "ccIdt"}
          />
          <div className="flex items-center gap-2">
            <div className="flex-1 min-w-0">
              <CredentialRow
                label={
                  credentials.hasLLMKey
                    ? `LLM API key configured (${credentials.llmProvider})`
                    : "LLM API key not set"
                }
                ok={credentials.hasLLMKey}
                onRefresh={onRefreshLlmKey}
                refreshing={refreshing === "llmKey"}
              />
            </div>
            {credentials.hasLLMKey && onChangeLlmKey && (
              <Button
                variant="link"
                size="sm"
                onClick={onChangeLlmKey}
                className="text-xs shrink-0"
              >
                Change
              </Button>
            )}
          </div>

          {includeMediaLib && (
            <>
              <CredentialRow
                label={
                  credentials.mediaLibTabId
                    ? "Media Library tab open (JWTAuth)"
                    : "Media Library tab not found"
                }
                ok={Boolean(credentials.mediaLibTabId)}
                onRefresh={onRefreshMediaLib}
                refreshing={refreshing === "mediaLib"}
              />

              {!credentials.mediaLibTabId && (
                <p className="text-xs text-muted-foreground font-mono pl-1">
                  Open{" "}
                  <span className="text-foreground">
                    apps.dealercenter.coxautoinc.com
                  </span>{" "}
                  to enable image uploads.
                </p>
              )}
            </>
          )}

          <div
            className={`mt-1 px-3 py-2 rounded-md text-xs font-medium ${
              credentials.ready
                ? "bg-primary/10 text-primary"
                : "bg-destructive/10 text-destructive"
            }`}
          >
            {credentials.ready
              ? "✓ All credentials ready"
              : `${credentials.missing.length} item${credentials.missing.length > 1 ? "s" : ""} need attention`}
          </div>

          {!credentials.ready && (
            <ul className="flex flex-col gap-1">
              {credentials.missing.map((msg, i) => (
                <li key={i} className="text-xs text-muted-foreground font-mono">
                  • {msg}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
