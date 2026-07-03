import {
  useMigrationStore,
  selectActiveProject,
} from "../../../store/useMigrationStore";
import type {
  CustomMigrationProject,
  GMPrebuildProject,
} from "../../../store/types";
import { Button } from "@/components/ui/button";
import { CheckCircle2, MinusCircle } from "lucide-react";

export function ProjectStatusPanel() {
  const project = useMigrationStore(selectActiveProject);
  const toggleProjectStatus = useMigrationStore((s) => s.toggleProjectStatus);

  if (!project) return null;

  const isFinished = project.status === "Finished";
  const pages =
    "pages" in project
      ? (project as CustomMigrationProject | GMPrebuildProject).pages
      : [];
  const doneCount = pages.filter((p) => p.status === "done").length;
  const totalCount = pages.length;
  const hasPages = totalCount > 0;
  const pct = hasPages ? Math.round((doneCount / totalCount) * 100) : 0;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        {isFinished ? (
          <CheckCircle2 size={16} className="text-success shrink-0" />
        ) : (
          <MinusCircle size={16} className="text-muted-foreground shrink-0" />
        )}
        <span
          className={`text-sm font-medium ${isFinished ? "text-success" : "text-foreground"}`}
        >
          {isFinished ? "Finished" : "In Progress"}
        </span>
      </div>

      <Button
        variant="default"
        className="w-full"
        size="sm"
        onClick={() => toggleProjectStatus(project.id)}
      >
        {isFinished ? "Mark In Progress" : "Mark Finished"}
      </Button>

      {hasPages && (
        <div className="flex flex-col gap-2">
          <p className="text-xs text-muted-foreground">
            {doneCount} / {totalCount} pages completed
          </p>
          <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
            <div
              className="h-full rounded-full bg-primary transition-all duration-300"
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
