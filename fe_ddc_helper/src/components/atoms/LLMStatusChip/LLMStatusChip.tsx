import { useEffect, useState } from "react";
import { Cpu } from "lucide-react";
import { useServices } from "@/services/ServicesContext";

/**
 * Per-provider cheap-tier model name shown in the chip.
 *
 * Mirrors the hardcoded model strings in the backend adapters' translate/judge/
 * enrich methods (see e.g. `claude-haiku-4-5` in anthropic_llm_adapter.py).
 * Keep this map in sync if the backend cheap-tier choice changes.
 */
const PROVIDER_DISPLAY: Record<string, { label: string; model: string }> = {
  anthropic: { label: "Anthropic", model: "Haiku 4.5" },
  gemini: { label: "Gemini", model: "Flash 2.0" },
  deepseek: { label: "DeepSeek", model: "Chat" },
};

interface LLMStatusChipProps {
  /** Optional click handler — typically opens the LLM config form. */
  onClick?: () => void;
  /** Show a slightly compact variant for tight headers. */
  compact?: boolean;
}

export function LLMStatusChip({ onClick, compact }: LLMStatusChipProps) {
  const { credentialPort } = useServices();
  const [provider, setProvider] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;

    const load = async () => {
      const stored = await credentialPort.getStoredApiKey();
      if (mounted) setProvider(stored?.provider ?? null);
    };
    load();

    // Reload when chrome.storage.local changes — covers the case where the
    // user reconfigures from elsewhere and we want the chip to reflect it.
    const handler = (changes: { [key: string]: chrome.storage.StorageChange }) => {
      if (changes.llmProvider) load();
    };
    chrome.storage.onChanged.addListener(handler);
    return () => {
      mounted = false;
      chrome.storage.onChanged.removeListener(handler);
    };
  }, [credentialPort]);

  const display = provider ? PROVIDER_DISPLAY[provider] : null;
  const label = display ? `${display.label} · ${display.model}` : "No LLM configured";

  const baseClasses =
    "flex items-center gap-1.5 rounded-md font-medium border transition-colors";
  const sizeClasses = compact ? "px-1.5 py-0.5 text-[10px]" : "px-2 py-1 text-xs";
  const stateClasses = display
    ? "bg-primary/10 text-primary border-primary/20 hover:bg-primary/15"
    : "bg-muted text-muted-foreground border-border hover:bg-muted/80";
  const clickableClasses = onClick ? "cursor-pointer" : "cursor-default";

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={!onClick}
      className={`${baseClasses} ${sizeClasses} ${stateClasses} ${clickableClasses}`}
      title={
        display
          ? `Using ${display.label} (${display.model}) for translations & cheap-tier calls`
          : "No LLM provider configured — click Settings to add one"
      }
    >
      <Cpu size={compact ? 10 : 12} />
      <span>{label}</span>
    </button>
  );
}
