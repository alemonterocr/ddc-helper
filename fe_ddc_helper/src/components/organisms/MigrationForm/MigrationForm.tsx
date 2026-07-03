import { useState } from "react";
import type { CredentialStatus, LLMProvider } from "../../../types";
import type { BackendPort } from "../../../services/ports/BackendPort";
import type { CredentialPort } from "../../../services/ports/CredentialPort";
import { credentialService } from "../../../services/credentialService";
import { ApiKeySetup } from "../../molecules/ApiKeySetup/ApiKeySetup";
import { CredentialChecker } from "../../molecules/CredentialChecker/CredentialChecker";
import { UrlInputCard } from "../../molecules/UrlInputCard/UrlInputCard";
import { Input } from "@/components/ui/input";
import { Field, FieldLabel } from "@/components/ui/field";

interface MigrationFormProps {
  backendPort: BackendPort;
  credentialPort: CredentialPort;
  onStartMigration: (
    url: string,
    dealerId: string,
    provider: LLMProvider,
  ) => void;
  disabled?: boolean;
}

export function MigrationForm({
  backendPort,
  credentialPort,
  onStartMigration,
  disabled,
}: MigrationFormProps) {
  const [credentials, setCredentials] = useState<CredentialStatus | null>(null);
  const [checking, setChecking] = useState(false);
  const [checkError, setCheckError] = useState<string | undefined>();
  const [refreshing, setRefreshing] = useState<
    "ccIdt" | "llmKey" | "mediaLib" | null
  >(null);

  const [dealerId, setDealerId] = useState("");
  const [selectedProvider, setSelectedProvider] =
    useState<LLMProvider>("anthropic");
  const [apiKeyError, setApiKeyError] = useState<string | undefined>();
  const [isSavingKey, setIsSavingKey] = useState(false);
  const [showKeySetup, setShowKeySetup] = useState(false);

  const handleCheckCredentials = async () => {
    setChecking(true);
    setCheckError(undefined);
    try {
      const result = await credentialService.check();
      setCredentials(result);
      if (result.llmProvider) setSelectedProvider(result.llmProvider);
    } catch (err) {
      setCheckError(
        err instanceof Error
          ? err.message
          : "Failed to read credentials from storage",
      );
    } finally {
      setChecking(false);
    }
  };

  const handleRefreshCcIdt = async () => {
    if (!credentials) return;
    setRefreshing("ccIdt");
    try {
      const { ccIdtToken, createdBy } = await credentialService.recheckCcIdt();
      setCredentials((prev) => {
        if (!prev) return prev;
        const missing = prev.missing.filter((m) => !m.includes("CC-IDT"));
        if (!ccIdtToken)
          missing.push(
            "CC-IDT token missing — click any widget in DDC CMS first",
          );
        return {
          ...prev,
          ccIdtToken,
          createdBy,
          ready: missing.length === 0,
          missing,
        };
      });
    } finally {
      setRefreshing(null);
    }
  };

  const handleRefreshLlmKey = async () => {
    if (!credentials) return;
    setRefreshing("llmKey");
    try {
      const { hasLLMKey, llmProvider } =
        await credentialService.recheckLlmKey();
      setCredentials((prev) => {
        if (!prev) return prev;
        const missing = prev.missing.filter((m) => !m.includes("LLM API key"));
        if (!hasLLMKey)
          missing.push("LLM API key not configured — add one below");
        return {
          ...prev,
          hasLLMKey,
          llmProvider,
          ready: missing.length === 0,
          missing,
        };
      });
      if (llmProvider) setSelectedProvider(llmProvider);
    } finally {
      setRefreshing(null);
    }
  };

  const handleRefreshMediaLib = async () => {
    if (!credentials) return;
    setRefreshing("mediaLib");
    try {
      const { mediaLibTabId, jwtOk } =
        await credentialService.recheckMediaLibTab();
      setCredentials((prev) => {
        if (!prev) return prev;
        return { ...prev, mediaLibTabId: jwtOk ? mediaLibTabId : null };
      });
    } finally {
      setRefreshing(null);
    }
  };

  async function handleSaveApiKey(provider: LLMProvider, apiKey: string) {
    setIsSavingKey(true);
    setApiKeyError(undefined);

    try {
      const result = await backendPort.configureApiKey({
        provider,
        api_key: apiKey,
      });

      if (result.valid) {
        await credentialPort.markLLMKeyConfigured(provider, apiKey);
        setSelectedProvider(provider);
        setShowKeySetup(false);
        await handleRefreshLlmKey();
      } else {
        setApiKeyError(result.error ?? "Invalid API key");
      }
    } catch (err) {
      setApiKeyError(
        err instanceof Error ? err.message : "Unexpected error saving API key",
      );
    } finally {
      setIsSavingKey(false);
    }
  }

  function handleCapture(url: string) {
    if (!dealerId.trim()) return;
    onStartMigration(url, dealerId.trim(), selectedProvider);
  }

  const canCapture = Boolean(credentials?.ready && dealerId.trim());

  return (
    <div className="flex flex-col gap-5">
      <CredentialChecker
        credentials={credentials}
        checking={checking}
        refreshing={refreshing}
        onCheck={handleCheckCredentials}
        onRefreshCcIdt={handleRefreshCcIdt}
        onRefreshLlmKey={handleRefreshLlmKey}
        onRefreshMediaLib={handleRefreshMediaLib}
        onChangeLlmKey={() => {
          setShowKeySetup(true);
          setApiKeyError(undefined);
        }}
      />

      {checkError && (
        <p className="text-xs text-destructive font-mono px-1">⚠ {checkError}</p>
      )}

      {credentials && (!credentials.hasLLMKey || showKeySetup) && (
        <ApiKeySetup
          onSave={handleSaveApiKey}
          isLoading={isSavingKey}
          error={apiKeyError}
        />
      )}

      <Field>
        <FieldLabel htmlFor="dealer-id">Dealer ID</FieldLabel>
        <Input
          id="dealer-id"
          value={dealerId}
          onChange={(e) => setDealerId(e.target.value)}
          placeholder="e.g. dealer123"
          disabled={disabled}
        />
      </Field>

      <div className="flex flex-col gap-3">
        <h2 className="text-sm font-semibold text-foreground">Live Site Page</h2>
        <UrlInputCard
          onCapture={handleCapture}
          disabled={disabled || !canCapture}
        />

        {!canCapture && credentials && (
          <p className="text-xs text-muted-foreground">
            {!credentials.ccIdtToken && "Log in to DDC CMS first. "}
            {!credentials.hasLLMKey && "Configure an LLM API key. "}
            {!dealerId.trim() && "Enter a dealer ID."}
          </p>
        )}
      </div>
    </div>
  );
}
