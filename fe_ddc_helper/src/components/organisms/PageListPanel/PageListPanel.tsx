import { useState } from "react";
import type { CustomMigrationProject, GMPrebuildProject } from "../../../store/types";
import { useMigrationStore } from "../../../store/useMigrationStore";
import { PageListItem } from "../../molecules/PageListItem/PageListItem";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Plus } from "lucide-react";

interface PageListPanelProps {
  project: CustomMigrationProject | GMPrebuildProject;
}

export function PageListPanel({ project }: PageListPanelProps) {
  const {
    addPage,
    deletePage,
    setActivePage,
    activePageId,
  } = useMigrationStore();
  const [showAddForm, setShowAddForm] = useState(false);
  const [urlInput, setUrlInput] = useState("");
  const [urlError, setUrlError] = useState<string | undefined>();

  function handleAddPage() {
    const trimmed = urlInput.trim();
    if (!trimmed) {
      setUrlError("URL is required");
      return;
    }
    try {
      const p = new URL(trimmed);
      if (!["http:", "https:"].includes(p.protocol)) throw new Error();
    } catch {
      setUrlError("Enter a valid http/https URL");
      return;
    }

    const newPageId = addPage(project.id, trimmed);
    setActivePage(newPageId);
    setUrlInput("");
    setUrlError(undefined);
    setShowAddForm(false);
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter") handleAddPage();
    if (e.key === "Escape") {
      setShowAddForm(false);
      setUrlInput("");
      setUrlError(undefined);
    }
  }

  return (
    <div className="flex flex-col flex-1 min-h-0">
      {/* Header */}
      <div className="mb-4">
        <p className="text-sm font-semibold text-foreground truncate font-mono">
          {project.dealerId}
        </p>
      </div>

      {/* Add Page form (inline) */}
      {showAddForm && (
        <div className="flex flex-col gap-3 mb-3 p-3 rounded-md bg-card border border-border">
          <div className="flex flex-col gap-1">
            <label htmlFor="add-page-url" className="text-xs font-medium text-muted-foreground">
              Live site page URL
            </label>
            <Input
              id="add-page-url"
              value={urlInput}
              onChange={(e) => {
                setUrlInput(e.target.value);
                setUrlError(undefined);
              }}
              placeholder="https://dealer.example.com/about"
              onKeyDown={handleKeyDown}
              autoFocus
            />
            {urlError && <p className="text-xs text-destructive">{urlError}</p>}
          </div>
          <div className="flex gap-2">
            <Button size="sm" onClick={handleAddPage} disabled={!urlInput.trim()}>
              Add
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setShowAddForm(false);
                setUrlInput("");
                setUrlError(undefined);
              }}
            >
              Cancel
            </Button>
          </div>
        </div>
      )}

      {/* Page list */}
      <div className="flex flex-col gap-1 flex-1 overflow-y-auto scrollbar-thin">
        {project.pages.length === 0 && !showAddForm && (
          <p className="text-xs text-muted-foreground px-1 py-3">
            No pages yet. Add one below.
          </p>
        )}
        {[...project.pages].reverse().map((page) => (
          <PageListItem
            key={page.id}
            page={page}
            isActive={page.id === activePageId}
            onClick={() => setActivePage(page.id)}
            onDelete={() => deletePage(project.id, page.id)}
          />
        ))}
      </div>

      {/* Add Page button — pinned to bottom */}
      {!showAddForm && (
        <Button
          variant="default"
          onClick={() => setShowAddForm(true)}
          className="mt-3 w-full"
        >
          <Plus size={12} /> Add Page
        </Button>
      )}
    </div>
  );
}
