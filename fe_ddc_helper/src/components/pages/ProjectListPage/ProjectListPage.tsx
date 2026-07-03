import { useCallback, useMemo, useState } from "react";
import { useMigrationStore } from "../../../store/useMigrationStore";
import { Button } from "@/components/ui/button";
import { Plus } from "lucide-react";
import { LLMConfigButton } from "@/components/organisms/LLMConfigButton/LLMConfigButton";
import { CMProjectForm } from "@/components/molecules/CMProjectForm/CMProjectForm";
import { SpanishProjectForm } from "@/components/molecules/SpanishProjectForm/SpanishProjectForm";
import { GMIntakeWizard } from "@/components/organisms/GMIntakeWizard/GMIntakeWizard";
import ProjectsList from "@/components/organisms/ProjectsList/ProjectsList";
import { parseLinksToPages } from "@/services/linkParser";
import {
  Dialog,
  DialogContent,
  DialogTitle,
} from "@/components/ui/dialog";

type ProjectKind = "cm" | "gm" | "spanish";

export function ProjectListPage() {
  const {
    migrationProjects,
    prebuildProjects,
    buySellProjects,
    spanishProjects,
    createCMProject,
    createSpanishProject,
    addPage,
    updatePage,
    goToProject,
  } = useMigrationStore();

  const gmProjects = useMemo(
    () => [...prebuildProjects, ...buySellProjects],
    [prebuildProjects, buySellProjects],
  );

  const [openForm, setOpenForm] = useState<ProjectKind | null>(null);

  const onSearchCMProjects = useCallback(
    (query: string) =>
      migrationProjects.filter((project) =>
        project.dealerId.toLowerCase().includes(query.toLowerCase()),
      ),
    [migrationProjects],
  );

  const onSearchGMProjects = useCallback(
    (query: string) =>
      gmProjects.filter((project) =>
        project.dealerId.toLowerCase().includes(query.toLowerCase()),
      ),
    [gmProjects],
  );

  const onSearchSpanishProjects = useCallback(
    (query: string) =>
      spanishProjects.filter((project) =>
        project.dealerId.toLowerCase().includes(query.toLowerCase()),
      ),
    [spanishProjects],
  );

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col">
      <header className="py-4 flex items-center gap-3 justify-between px-6 lg:px-10 border-b border-border">
        <h1 className="text-2xl font-semibold text-foreground">
          DDC Helper
        </h1>
        <LLMConfigButton />
      </header>

      <main className="flex-1 flex flex-col w-full px-6 lg:px-10 py-6 gap-6">
        {/* New-project toolbar. Three ghost buttons, one row, no hero cards. */}
        <section
          aria-label="Create new project"
          className="flex flex-wrap items-center gap-2"
        >
          <Button
            variant="outline"
            size="sm"
            onClick={() => setOpenForm("gm")}
          >
            <Plus />
            GM Prebuild / BuySell
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setOpenForm("cm")}
          >
            <Plus />
            CM Project
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setOpenForm("spanish")}
          >
            <Plus />
            Spanish Translation
          </Button>
        </section>

        {/* Project lists: 1 col on narrow, 3 cols from md+. */}
        <div className="flex-1 grid grid-cols-1 md:grid-cols-3 gap-6">
          <ProjectsList
            projectList={gmProjects}
            onSearch={onSearchGMProjects}
            onItemClick={(project) => goToProject(project.id)}
            title="GM Projects"
            searchLabel="Search GM projects..."
            notFoundMessage="No GM projects found."
          />
          <ProjectsList
            projectList={migrationProjects}
            onSearch={onSearchCMProjects}
            onItemClick={(project) => goToProject(project.id)}
            title="CM Projects"
            searchLabel="Search CM projects..."
            notFoundMessage="No CM projects found."
          />
          <ProjectsList
            projectList={spanishProjects}
            onSearch={onSearchSpanishProjects}
            onItemClick={(project) => goToProject(project.id)}
            title="Spanish Projects"
            searchLabel="Search Spanish projects..."
            notFoundMessage="No Spanish projects found."
          />
        </div>
      </main>

      <Dialog
        open={openForm === "cm"}
        onOpenChange={(open) => !open && setOpenForm(null)}
      >
        <DialogContent
          className="p-0 gap-0 bg-transparent shadow-none ring-0 border-0 max-w-none w-auto sm:max-w-none"
          showCloseButton={false}
        >
          <DialogTitle className="sr-only">Create CM project</DialogTitle>
          <CMProjectForm
            onSubmit={(data) => {
              const parsed = parseLinksToPages(data.links);
              if (parsed.length === 0) return;
              const projectId = createCMProject(data.dealerId);
              parsed.forEach(({ url, title }) => {
                const pageId = addPage(projectId, url);
                if (title)
                  updatePage(projectId, pageId, {
                    pageTitle: title,
                    pageAlias: `${title}.htm`,
                  });
              });
              goToProject(projectId);
              setOpenForm(null);
            }}
            onCancel={() => setOpenForm(null)}
          />
        </DialogContent>
      </Dialog>

      <Dialog
        open={openForm === "gm"}
        onOpenChange={(open) => !open && setOpenForm(null)}
      >
        <DialogContent
          className="p-0 gap-0 bg-transparent shadow-none ring-0 border-0 max-w-none w-auto sm:max-w-none"
          showCloseButton={false}
        >
          <DialogTitle className="sr-only">GM intake wizard</DialogTitle>
          <GMIntakeWizard onCancel={() => setOpenForm(null)} />
        </DialogContent>
      </Dialog>

      <Dialog
        open={openForm === "spanish"}
        onOpenChange={(open) => !open && setOpenForm(null)}
      >
        <DialogContent
          className="p-0 gap-0 bg-transparent shadow-none ring-0 border-0 max-w-none w-auto sm:max-w-none"
          showCloseButton={false}
        >
          <DialogTitle className="sr-only">Create Spanish project</DialogTitle>
          <SpanishProjectForm
            onSubmit={(data) => {
              const projectId = createSpanishProject(
                data.dealerId,
                data.dealerName,
              );
              goToProject(projectId);
              setOpenForm(null);
            }}
            onCancel={() => setOpenForm(null)}
          />
        </DialogContent>
      </Dialog>
    </div>
  );
}
