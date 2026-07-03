import { useState } from "react";
import type { LLMProvider } from "../../../types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Field, FieldLabel, FieldError } from "@/components/ui/field";

interface ApiKeySetupProps {
  onSave: (provider: LLMProvider, apiKey: string) => void;
  isLoading?: boolean;
  error?: string;
}

const PROVIDERS: { value: LLMProvider; label: string; placeholder: string }[] =
  [
    {
      value: "anthropic",
      label: "Anthropic (Claude)",
      placeholder: "sk-ant-…",
    },
    { value: "gemini", label: "Google (Gemini)", placeholder: "AIza…" },
    { value: "deepseek", label: "DeepSeek (V4 Pro)", placeholder: "sk-…" },
  ];

export function ApiKeySetup({ onSave, isLoading, error }: ApiKeySetupProps) {
  const [provider, setProvider] = useState<LLMProvider>("anthropic");
  const [apiKey, setApiKey] = useState("");

  // The fallback to PROVIDERS[0] is safe because PROVIDERS is non-empty, but
  // noUncheckedIndexedAccess types it as possibly-undefined. The non-null
  // assertion is documented here rather than spread through every consumer.
  const selectedProvider =
    PROVIDERS.find((p) => p.value === provider) ?? PROVIDERS[0]!;

  function handleSave() {
    if (apiKey.trim()) onSave(provider, apiKey.trim());
  }

  return (
    <div className="flex flex-col gap-3 p-3 rounded-md bg-card border border-border">
      <p className="text-xs font-medium text-muted-foreground">
        Configure LLM provider
      </p>

      <Field>
        <FieldLabel htmlFor="api-provider" className="text-xs">Provider</FieldLabel>
        <select
          id="api-provider"
          value={provider}
          onChange={(e) => {
            setProvider(e.target.value as LLMProvider);
            setApiKey("");
          }}
          disabled={isLoading}
          className="w-full rounded-md px-3 py-2 text-sm bg-background text-foreground border border-border outline-none focus:border-ring"
        >
          {PROVIDERS.map((p) => (
            <option key={p.value} value={p.value}>
              {p.label}
            </option>
          ))}
        </select>
      </Field>

      <Field>
        <FieldLabel htmlFor="api-key" className="text-xs">API Key</FieldLabel>
        <Input
          id="api-key"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          placeholder={selectedProvider.placeholder}
          disabled={isLoading}
          aria-invalid={!!error}
        />
        {error && <FieldError>{error}</FieldError>}
      </Field>

      <Button
        size="sm"
        onClick={handleSave}
        disabled={!apiKey.trim() || isLoading}
      >
        {isLoading ? "Validating…" : "Validate & Save"}
      </Button>
    </div>
  );
}
