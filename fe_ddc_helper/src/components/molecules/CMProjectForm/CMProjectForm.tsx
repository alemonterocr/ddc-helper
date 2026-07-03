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
import { InputGroup, InputGroupTextarea } from "@/components/ui/input-group";

const formSchema = z.object({
  dealerId: z
    .string()
    .min(1, "Dealer ID is required.")
    .min(3, "Dealer ID must be at least 3 characters."),
  links: z.string().min(1, "At least one link is required."),
});

interface CMProjectFormProps {
  onSubmit: (data: z.infer<typeof formSchema>) => void;
  onCancel: () => void;
}

export function CMProjectForm({ onSubmit, onCancel }: CMProjectFormProps) {
  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      dealerId: "",
      links: "",
    },
  });

  return (
    <Card className="w-full sm:max-w-md px-5 py-10">
      <CardHeader>
        <CardTitle>New CM Project</CardTitle>
        <CardDescription>
          Create a Custom Migration project to clone pages into DDC CMS.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form id="cm-project-form" onSubmit={form.handleSubmit(onSubmit)}>
          <div className="flex flex-col gap-6">
            <Field data-invalid={!!form.formState.errors.dealerId}>
              <FieldLabel htmlFor="cm-dealer-id">Dealer ID</FieldLabel>
              <Input
                {...form.register("dealerId")}
                id="cm-dealer-id"
                placeholder="buttetoyotasilverbowmt"
                autoComplete="off"
              />
              {form.formState.errors.dealerId && (
                <FieldError errors={[form.formState.errors.dealerId]} />
              )}
            </Field>

            <Field data-invalid={!!form.formState.errors.links}>
              <FieldLabel htmlFor="cm-links">Page links to migrate</FieldLabel>
              <InputGroup>
                <InputGroupTextarea
                  {...form.register("links")}
                  id="cm-links"
                  placeholder="https://dealer.example.com/about-us"
                  rows={8}
                  className="min-h-24 max-h-64 resize-none overflow-y-auto"
                />
              </InputGroup>
              <FieldDescription>
                Paste one URL per line. Each will become a page in this project.
              </FieldDescription>
              {form.formState.errors.links && (
                <FieldError errors={[form.formState.errors.links]} />
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
          <Button type="submit" form="cm-project-form">
            Create Project
          </Button>
        </div>
      </CardFooter>
    </Card>
  );
}
