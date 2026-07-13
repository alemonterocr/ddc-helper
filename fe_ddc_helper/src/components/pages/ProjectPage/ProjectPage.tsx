import { useEffect, useState } from "react";
import {
  useMigrationStore,
  selectActiveProject,
  selectActivePage,
} from "../../../store/useMigrationStore";
import type {
  CustomMigrationProject,
  GMPrebuildProject,
  SpanishMigrationProject,
} from "../../../store/types";
import { useServices } from "../../../services/ServicesContext";
import { PageListPanel } from "../../organisms/PageListPanel/PageListPanel";
import { MigrationFlowPanel } from "../../organisms/MigrationFlowPanel/MigrationFlowPanel";
import { StaffFlowPanel } from "../../organisms/StaffFlowPanel/StaffFlowPanel";
import { SpanishPanelWorkflow } from "../../organisms/SpanishPanelWorkflow/SpanishPanelWorkflow";
import { NavTranslateTab } from "../../organisms/NavTranslateTab/NavTranslateTab";
import { PageTranslateTab } from "../../organisms/PageTranslateTab/PageTranslateTab";
import { SettingsPanel } from "../../organisms/SettingsPanel/SettingsPanel";
import { LinkReplacementsPanel } from "../../organisms/LinkReplacementsPanel/LinkReplacementsPanel";
import { ProjectStatusPanel } from "../../organisms/ProjectStatusPanel/ProjectStatusPanel";
import { GMSetupBlock } from "@/components/molecules/GMSetupBlock/GMSetupBlock";
import { Separator } from "@/components/ui/separator";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { LLMConfigButton } from "@/components/organisms/LLMConfigButton/LLMConfigButton";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { ArrowLeft, ChevronRight, FileText, Trash2 } from "lucide-react";

export function ProjectPage() {
  const project = useMigrationStore(selectActiveProject);
  const activePage = useMigrationStore(selectActivePage);
  const { goToProjects, deleteProject } = useMigrationStore();
  const { backendPort, credentialPort, extractorPort, createWSClient } =
    useServices();

  // GM Prebuild tabs. Controlled so selecting a page from the left snaps the
  // user back to the Page Migration tab even if they were on Setup Data.
  const [gmPrebuildTab, setGmPrebuildTab] = useState<"migration" | "setup">(
    "migration",
  );
  const activePageId = activePage?.id ?? null;
  useEffect(() => {
    if (activePageId) setGmPrebuildTab("migration");
  }, [activePageId]);

  const [spanishTab, setSpanishTab] = useState<"simple" | "nav" | "page">(
    "simple",
  );

  if (!project) return null;

  const hasPages = project.type !== "gm-buysell" && project.type !== "spanish";
  const isGm = project.type === "gm-prebuild" || project.type === "gm-buysell";
  const gmBundle = isGm ? project.dealerBundle : undefined;
  const isSpanish = project.type === "spanish";

  function renderPageFlow() {
    if (!activePage || !project) return <EmptyState />;
    if (
      activePage.pageType === "staff" &&
      (project.type === "cm" || project.type === "gm-prebuild")
    ) {
      return (
        <StaffFlowPanel
          key={`staff-${activePage.id}`}
          projectId={project.id}
          projectType={project.type}
          page={activePage}
          backendPort={backendPort}
          credentialPort={credentialPort}
          extractorPort={extractorPort}
          createWSClient={createWSClient}
        />
      );
    }
    return (
      <MigrationFlowPanel
        key={activePage.id}
        projectId={project.id}
        page={activePage}
        backendPort={backendPort}
        credentialPort={credentialPort}
        extractorPort={extractorPort}
        createWSClient={createWSClient}
      />
    );
  }

  return (
    <div className="h-screen bg-background text-foreground flex flex-col">
      {/* ── Top bar — dashboard header, 56px. Breadcrumb "← Projects › {id}"
             renders as ONE flex row on a single baseline; back arrow is part
             of the breadcrumb, not a separate icon button. ─── */}
      <header className="h-14 shrink-0 border-b border-border px-4 flex items-center justify-between gap-4">
        <nav
          aria-label="Breadcrumb"
          className="flex items-center gap-2 min-w-0 text-sm"
        >
          <button
            type="button"
            onClick={goToProjects}
            className="flex items-center gap-1.5 text-muted-foreground hover:text-foreground transition-colors shrink-0"
          >
            <ArrowLeft size={14} aria-hidden="true" />
            Projects
          </button>
          <ChevronRight
            size={14}
            className="text-muted-foreground/60 shrink-0"
            aria-hidden="true"
          />
          <span
            className="font-medium text-foreground truncate"
            title={project.dealerId}
          >
            {project.dealerId}
          </span>
        </nav>

        <div className="flex items-center gap-1 shrink-0">
          <LLMConfigButton />
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => deleteProject(project.id)}
            className="text-muted-foreground hover:text-destructive"
            aria-label="Delete project"
            title="Delete project"
          >
            <Trash2 size={14} />
          </Button>
        </div>
      </header>

      <main className="flex flex-1 overflow-hidden">
        {/* ── Left: page list ──────────────────────────────────────────── */}
        <aside
          aria-label="Pages in this project"
          className="w-64 shrink-0 border-r border-border p-4 overflow-hidden hidden md:flex flex-col"
        >
          {hasPages && (
            <PageListPanel
              project={project as CustomMigrationProject | GMPrebuildProject}
            />
          )}
        </aside>

        {/* ── Center: migration flow ─────────────────────────────────── */}
        <section className="flex-1 min-w-0 p-5 overflow-y-auto scrollbar-thin">
          {isSpanish ? (
            <Tabs
              value={spanishTab}
              onValueChange={(v) =>
                setSpanishTab(v as "simple" | "nav" | "page")
              }
              className="h-full"
            >
              <TabsList>
                <TabsTrigger value="simple">Simple Labels</TabsTrigger>
                <TabsTrigger value="nav">Translate Nav</TabsTrigger>
                <TabsTrigger value="page">Translate Page</TabsTrigger>
              </TabsList>
              <TabsContent value="simple">
                <SpanishPanelWorkflow
                  project={project as SpanishMigrationProject}
                />
              </TabsContent>
              <TabsContent value="nav">
                <NavTranslateTab
                  project={project as SpanishMigrationProject}
                />
              </TabsContent>
              <TabsContent value="page">
                <PageTranslateTab
                  project={project as SpanishMigrationProject}
                />
              </TabsContent>
            </Tabs>
          ) : project.type === "gm-buysell" && gmBundle ? (
            <GmBuySellDashboard bundle={gmBundle} />
          ) : project.type === "gm-prebuild" && gmBundle ? (
            <Tabs
              value={gmPrebuildTab}
              onValueChange={(v) =>
                setGmPrebuildTab(v as "migration" | "setup")
              }
              className="h-full"
            >
              <TabsList>
                <TabsTrigger value="migration">Page Migration</TabsTrigger>
                <TabsTrigger value="setup">Setup Data</TabsTrigger>
              </TabsList>
              <TabsContent value="migration">
                {activePage ? renderPageFlow() : <EmptyState />}
              </TabsContent>
              <TabsContent value="setup">
                <GMSetupBlock bundle={gmBundle} />
              </TabsContent>
            </Tabs>
          ) : activePage ? (
            renderPageFlow()
          ) : (
            <EmptyState />
          )}
        </section>

        {/* ── Right: settings + links (collapsible) + project status (pinned) ── */}
        <aside
          aria-label="Project settings and status"
          className="w-72 shrink-0 border-l border-border p-4 overflow-y-auto scrollbar-thin hidden xl:flex flex-col gap-4"
        >
          <Accordion
            type="multiple"
            defaultValue={["settings", "links"]}
            className="rounded-lg border-border"
          >
            <AccordionItem value="settings">
              <AccordionTrigger className="p-3 text-sm font-medium hover:no-underline">
                Credentials
              </AccordionTrigger>
              <AccordionContent className="px-3 pb-3">
                <SettingsPanel
                  backendPort={backendPort}
                  credentialPort={credentialPort}
                  includeMediaLib={project.type !== "spanish"}
                />
              </AccordionContent>
            </AccordionItem>

            <AccordionItem value="links">
              <AccordionTrigger className="p-3 text-sm font-medium hover:no-underline">
                Link replacements
              </AccordionTrigger>
              <AccordionContent className="px-3 pb-3">
                {activePage ? (
                  <LinkReplacementsPanel
                    projectId={project.id}
                    page={activePage}
                  />
                ) : (
                  <p className="text-xs text-muted-foreground">
                    Select a page to see link replacements.
                  </p>
                )}
              </AccordionContent>
            </AccordionItem>
          </Accordion>

          <section
            aria-labelledby="ps-heading"
            className="rounded-lg border border-border p-4 flex flex-col gap-3"
          >
            <h2
              id="ps-heading"
              className="text-sm font-medium text-foreground"
            >
              Project status
            </h2>
            <ProjectStatusPanel />
          </section>
        </aside>
      </main>
    </div>
  );
}

function GmBuySellDashboard({
  bundle,
}: {
  bundle: import("@/types").DealerBundle;
}) {
  return (
    <div className="flex flex-col gap-6">
      <GMSetupBlock bundle={bundle} />
      <Separator />
      <p className="text-xs text-muted-foreground self-end">
        BuySell automation is not implemented yet. Use the data above to drive
        the manual flow.
      </p>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-3 text-center">
      <FileText
        size={32}
        strokeWidth={1.5}
        className="text-muted-foreground"
        aria-hidden="true"
      />
      <p className="text-sm text-muted-foreground font-medium">
        No page selected
      </p>
      <p className="text-xs text-muted-foreground">
        Pick a page from the left or add a new one.
      </p>
    </div>
  );
}
