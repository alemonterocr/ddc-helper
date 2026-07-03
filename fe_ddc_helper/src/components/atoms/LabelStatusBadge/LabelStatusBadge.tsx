import { Badge } from "@/components/ui/badge";
import type { LabelRowStatus } from "@/store/types";

const LABELS: Record<LabelRowStatus, string> = {
  queued: "Queued",
  fetching: "Fetching",
  translating: "Translating",
  ready: "Ready",
  error: "Error",
  saved: "Saved",
  skipped: "Skipped",
  not_found: "Not found",
};

const VARIANTS: Record<
  LabelRowStatus,
  "default" | "secondary" | "destructive" | "outline" | "ghost"
> = {
  queued: "outline",
  fetching: "secondary",
  translating: "secondary",
  ready: "default",
  error: "destructive",
  saved: "default",
  skipped: "ghost",
  not_found: "destructive",
};

interface LabelStatusBadgeProps {
  status: LabelRowStatus;
}

export function LabelStatusBadge({ status }: LabelStatusBadgeProps) {
  return <Badge variant={VARIANTS[status]}>{LABELS[status]}</Badge>;
}
