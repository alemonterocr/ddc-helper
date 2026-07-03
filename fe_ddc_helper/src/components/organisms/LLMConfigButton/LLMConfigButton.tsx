import { useCallback, useEffect, useState } from "react";
import { Settings2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogTitle,
} from "@/components/ui/dialog";
import { LLMConfigForm } from "@/components/molecules/LLMConfigForm/LLMConfigForm";
import { useServices } from "@/services/ServicesContext";
import type { LLMProvider } from "@/types";

/**
 * Settings-icon button that opens the LLM provider configuration modal.
 *
 * Owns its own dialog state and save flow — both pages just render the
 * component and get an icon + modal for free. The small status dot on the
 * icon reflects whether an LLM is currently configured (teal = yes, red =
 * no), so the specialist can tell at a glance without opening the modal.
 */
export function LLMConfigButton() {
  const { backendPort, credentialPort } = useServices();

  const [open, setOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | undefined>();
  const [currentProvider, setCurrentProvider] = useState<string | null>(null);
  const [currentApiKey, setCurrentApiKey] = useState<string | null>(null);
  const [configured, setConfigured] = useState<boolean | null>(null);

  // Track configured state for the status dot. Reloads when chrome.storage
  // changes so if the modal saves elsewhere the icon still reflects reality.
  useEffect(() => {
    let mounted = true;

    const load = async () => {
      const stored = await credentialPort.getStoredApiKey();
      if (mounted) setConfigured(Boolean(stored?.provider));
    };
    load();

    const handler = (changes: { [key: string]: chrome.storage.StorageChange }) => {
      if (changes.llmProvider) load();
    };
    chrome.storage.onChanged.addListener(handler);
    return () => {
      mounted = false;
      chrome.storage.onChanged.removeListener(handler);
    };
  }, [credentialPort]);

  const openConfig = useCallback(async () => {
    const stored = await credentialPort.getStoredApiKey();
    setCurrentProvider(stored?.provider ?? null);
    setCurrentApiKey(stored?.apiKey ?? null);
    setError(undefined);
    setOpen(true);
  }, [credentialPort]);

  async function handleSave(data: { provider: string; apiKey: string }) {
    setIsSaving(true);
    setError(undefined);
    try {
      const result = await backendPort.configureApiKey({
        provider: data.provider as LLMProvider,
        api_key: data.apiKey,
      });
      if (result.valid) {
        await credentialPort.markLLMKeyConfigured(
          data.provider as LLMProvider,
          data.apiKey,
        );
        setCurrentProvider(data.provider);
        setConfigured(true);
        setOpen(false);
      } else {
        setError(result.error ?? "Invalid API key");
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Unexpected error saving API key",
      );
    } finally {
      setIsSaving(false);
    }
  }

  const dotColor =
    configured === null
      ? "bg-muted-foreground"
      : configured
        ? "bg-primary"
        : "bg-destructive";

  return (
    <>
      <Button
        variant="ghost"
        size="icon-sm"
        onClick={openConfig}
        aria-label={
          configured ? "Configure AI provider" : "Configure AI provider (not set)"
        }
        title={
          configured
            ? "AI provider configured — click to change"
            : "No AI provider configured — click to set one"
        }
        className="relative text-muted-foreground hover:text-foreground"
      >
        <Settings2 size={14} />
        <span
          aria-hidden="true"
          className={`absolute top-0.5 right-0.5 h-1.5 w-1.5 rounded-full ${dotColor}`}
        />
      </Button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent
          className="p-0 gap-0 bg-transparent shadow-none ring-0 border-0 max-w-none w-auto sm:max-w-none"
          showCloseButton={false}
        >
          <DialogTitle className="sr-only">Configure AI provider</DialogTitle>
          <LLMConfigForm
            onSubmit={handleSave}
            onCancel={() => setOpen(false)}
            isLoading={isSaving}
            error={error}
            currentProvider={currentProvider}
            currentApiKey={currentApiKey}
          />
        </DialogContent>
      </Dialog>
    </>
  );
}
