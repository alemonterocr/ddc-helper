import type { CustomMigrationProject, GMPrebuildProject } from "../../../store/types";

interface ProjectCardProps {
  project: CustomMigrationProject | GMPrebuildProject;
  onOpen: () => void;
  onDelete: () => void;
}

export function ProjectCard({ project, onOpen, onDelete }: ProjectCardProps) {
  const pageCount = project.pages.length;
  const doneCount = project.pages.filter((p) => p.status === "done").length;
  const lastActivity =
    project.pages.length > 0
      ? Math.max(...project.pages.map((p) => p.completedAt ?? p.createdAt))
      : project.createdAt;

  return (
    <div
      className="group flex items-center justify-between p-4 rounded-lg border border-border bg-card/60 hover:border-primary/60 hover:bg-card transition-colors cursor-pointer"
      onClick={onOpen}
    >
      <div className="flex flex-col gap-1 min-w-0">
        <span className="text-sm font-semibold text-foreground truncate font-mono">
          {project.dealerId}
        </span>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span>
            {pageCount} page{pageCount !== 1 ? "s" : ""}
          </span>
          {pageCount > 0 && (
            <>
              <span className="text-muted-foreground">·</span>
              <span className="text-success">{doneCount} done</span>
            </>
          )}
          <span className="text-muted-foreground">·</span>
          <span>{formatDate(lastActivity)}</span>
        </div>
      </div>

      <div className="flex items-center gap-2 shrink-0">
        <button
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
          title="Delete project"
          className="opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-destructive transition-all text-xs px-1.5 py-0.5 rounded cursor-pointer"
        >
          ✕
        </button>
        <span className="text-muted-foreground group-hover:text-primary transition-colors text-sm">
          →
        </span>
      </div>
    </div>
  );
}

function formatDate(ts: number): string {
  const d = new Date(ts);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffDays === 0) return "today";
  if (diffDays === 1) return "yesterday";
  if (diffDays < 7) return `${diffDays}d ago`;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}
