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
import {
  Field,
  FieldDescription,
  FieldError,
  FieldLabel,
} from "@/components/ui/field";
import { Input } from "@/components/ui/input";

const formSchema = z.object({
  dealerId: z
    .string()
    .min(1, "Dealer ID is required.")
    .min(3, "Dealer ID must be at least 3 characters."),
  dealerName: z
    .string()
    .min(1, "Dealer name is required.")
    .min(2, "Dealer name must be at least 2 characters."),
});

interface SpanishProjectFormProps {
  onSubmit: (data: z.infer<typeof formSchema>) => void;
  onCancel: () => void;
}

export function SpanishProjectForm({ onSubmit, onCancel }: SpanishProjectFormProps) {
  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      dealerId: "",
      dealerName: "",
    },
  });

  return (
    <Card className="w-full sm:max-w-md px-5 py-10">
      <CardHeader>
        <CardTitle>New Spanish Translation Project</CardTitle>
        <CardDescription>
          Translate a batch of DDC labels from English to Spanish.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form id="spanish-project-form" onSubmit={form.handleSubmit(onSubmit)}>
          <div className="flex flex-col gap-6">
            <Field data-invalid={!!form.formState.errors.dealerId}>
              <FieldLabel htmlFor="es-dealer-id">Dealer ID (slug)</FieldLabel>
              <Input
                {...form.register("dealerId")}
                id="es-dealer-id"
                placeholder="mojix"
                autoComplete="off"
              />
              <FieldDescription>
                Matches the DDC path slug, e.g. <code>mojix</code> in
                <code> /labels/mojix/&hellip;</code>.
              </FieldDescription>
              {form.formState.errors.dealerId && (
                <FieldError errors={[form.formState.errors.dealerId]} />
              )}
            </Field>

            <Field data-invalid={!!form.formState.errors.dealerName}>
              <FieldLabel htmlFor="es-dealer-name">Dealer name</FieldLabel>
              <Input
                {...form.register("dealerName")}
                id="es-dealer-name"
                placeholder="Orange Buick GMC"
                autoComplete="off"
              />
              <FieldDescription>
                Used by the translator so the dealership&rsquo;s own name is
                never translated.
              </FieldDescription>
              {form.formState.errors.dealerName && (
                <FieldError errors={[form.formState.errors.dealerName]} />
              )}
            </Field>
          </div>
        </form>
      </CardContent>
      <CardFooter>
        <div className="flex gap-3 w-full justify-end">
          <Button type="button" variant="outline" onClick={onCancel}>
            Cancel
          </Button>
          <Button type="submit" form="spanish-project-form">
            Create Project
          </Button>
        </div>
      </CardFooter>
    </Card>
  );
}
