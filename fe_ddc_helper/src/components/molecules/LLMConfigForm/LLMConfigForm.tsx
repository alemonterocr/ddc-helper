import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import * as z from "zod";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { CheckCircle2 } from "lucide-react";

const PROVIDERS = [
  { value: "anthropic", label: "Anthropic (Claude)", placeholder: "sk-ant-…" },
  { value: "gemini", label: "Google (Gemini)", placeholder: "AIza…" },
  { value: "deepseek", label: "DeepSeek (V4 Pro)", placeholder: "sk-…" },
] as const;

const formSchema = z.object({
  provider: z.enum(["anthropic", "gemini", "deepseek"]),
  apiKey: z.string().min(1, "API key is required."),
});

interface LLMConfigFormProps {
  onSubmit: (data: z.infer<typeof formSchema>) => void;
  onCancel: () => void;
  isLoading?: boolean;
  error?: string;
  currentProvider?: string | null;
  currentApiKey?: string | null;
}

export function LLMConfigForm({
  onSubmit,
  onCancel,
  isLoading,
  error,
  currentProvider,
  currentApiKey,
}: LLMConfigFormProps) {
  const defaultProvider =
    (currentProvider as (typeof PROVIDERS)[number]["value"] | undefined) ??
    "anthropic";
  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      provider: defaultProvider,
      apiKey: currentApiKey ?? "",
    },
  });

  const isConfigured = !!currentProvider;

  return (
    <Card className="w-full sm:max-w-md px-5 py-10">
      <CardHeader>
        <CardTitle>Configure LLM Provider</CardTitle>
        <CardDescription>
          Set your AI provider and API key for migration analysis.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form id="llm-config-form" onSubmit={form.handleSubmit(onSubmit)}>
          <div className="flex flex-col gap-6">
            {isConfigured && (
              <div className="flex items-center gap-2 px-3 py-2 rounded-md bg-primary/10 text-primary text-xs font-medium">
                <CheckCircle2 size={14} className="shrink-0" />
                <span>{currentProvider} configured</span>

              </div>
            )}
            <Field>
              <FieldLabel>Provider</FieldLabel>
              <Select
                value={form.watch("provider")}
                onValueChange={(v) => {
                  form.setValue(
                    "provider",
                    v as z.infer<typeof formSchema>["provider"],
                  );
                  form.setValue("apiKey", "");
                }}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select provider" />
                </SelectTrigger>
                <SelectContent>
                  {PROVIDERS.map((p) => (
                    <SelectItem key={p.value} value={p.value}>
                      {p.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>

            <Field data-invalid={!!form.formState.errors.apiKey || !!error}>
              <FieldLabel htmlFor="llm-api-key">API Key</FieldLabel>
              <Input
                {...form.register("apiKey")}
                id="llm-api-key"
                type="password"
                placeholder={
                  PROVIDERS.find((p) => p.value === form.watch("provider"))
                    ?.placeholder ?? "sk-…"
                }
                autoComplete="off"
                disabled={isLoading}
              />
              {error && <p className="text-xs text-destructive">{error}</p>}
              {form.formState.errors.apiKey && (
                <FieldError errors={[form.formState.errors.apiKey]} />
              )}
            </Field>
          </div>
        </form>
      </CardContent>
      <CardFooter>
        <div className="flex gap-3 w-full justify-end">
          <Button
            type="button"
            variant="outline"
            onClick={onCancel}
            disabled={isLoading}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            form="llm-config-form"
            disabled={!form.watch("apiKey").trim() || isLoading}
          >
            {isLoading ? "Saving…" : "Validate & Save"}
          </Button>
        </div>
      </CardFooter>
    </Card>
  );
}
