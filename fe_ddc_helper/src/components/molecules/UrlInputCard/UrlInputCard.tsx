import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Field, FieldLabel, FieldError } from "@/components/ui/field";

interface UrlInputCardProps {
  onCapture: (url: string) => void;
  disabled?: boolean;
}

export function UrlInputCard({ onCapture, disabled }: UrlInputCardProps) {
  const [url, setUrl] = useState("");
  const [error, setError] = useState<string | undefined>();

  function handleCapture() {
    const validationError = validateUrl(url);
    if (validationError) {
      setError(validationError);
      return;
    }
    setError(undefined);
    onCapture(url.trim());
  }

  function handleUrlChange(value: string) {
    setUrl(value);
    if (error) setError(undefined);
  }

  return (
    <div className="flex flex-col gap-3">
      <Field>
        <FieldLabel htmlFor="ls-url">Live site page URL</FieldLabel>
        <Input
          id="ls-url"
          value={url}
          onChange={(e) => handleUrlChange(e.target.value)}
          placeholder="https://dealer.example.com/about-us"
          disabled={disabled}
          aria-invalid={!!error}
        />
        {error && <FieldError>{error}</FieldError>}
      </Field>
      <Button onClick={handleCapture} disabled={disabled || !url.trim()}>
        Capture Page
      </Button>
    </div>
  );
}

function validateUrl(raw: string): string | undefined {
  const trimmed = raw.trim();
  if (!trimmed) return "URL is required";
  try {
    const parsed = new URL(trimmed);
    if (!["http:", "https:"].includes(parsed.protocol)) {
      return "URL must start with http:// or https://";
    }
    return undefined;
  } catch {
    return "Enter a valid URL";
  }
}
