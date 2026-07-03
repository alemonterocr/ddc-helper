import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import { chromeStorageAdapter } from "./chromeStorageAdapter";
import type {
  MigrationPage,
  RouterState,
  PageStatus,
  CustomMigrationProject,
  GMBuySellProject,
  GMPrebuildProject,
  SpanishMigrationProject,
  SpanishLabelRow,
} from "./types";
import type { ColumnWidget, DealerBundle, SectionPlanItem } from "../types";
import {
  reindexPlan,
  makeSection,
  slotCountForType,
} from "../services/planEdit";

// ── State + actions ───────────────────────────────────────────────────────────

interface AppState extends RouterState {
  migrationProjects: CustomMigrationProject[];
  buySellProjects: GMBuySellProject[];
  prebuildProjects: GMPrebuildProject[];
  spanishProjects: SpanishMigrationProject[];

  // ── Router actions ──────────────────────────────────────────────────────────
  goToProjects: () => void;
  goToProject: (projectId: string) => void;
  setActivePage: (pageId: string | null) => void;

  // ── Project actions ─────────────────────────────────────────────────────────
  createCMProject: (dealerId: string) => string; // returns new project id
  createGMPrebuildProject: (dealerId: string, bundle?: DealerBundle) => string;
  createGMBuySellProject: (dealerId: string, bundle?: DealerBundle) => string;
  createSpanishProject: (dealerId: string, dealerName: string) => string;
  deleteProject: (projectId: string) => void;
  toggleProjectStatus: (projectId: string) => void;

  // ── Spanish project actions ────────────────────────────────────────────────
  /** Replace the project's label list — used right after /sanitize returns. */
  setSpanishLabels: (projectId: string, aliases: string[]) => void;
  /** Patch one label row (status / EN / ES / warnings / error). */
  updateSpanishLabel: (
    projectId: string,
    alias: string,
    patch: Partial<SpanishLabelRow>,
  ) => void;

  // ── Page actions ────────────────────────────────────────────────────────────
  addPage: (projectId: string, liveSiteUrl: string) => string; // returns new page id
  deletePage: (projectId: string, pageId: string) => void;
  updatePage: (
    projectId: string,
    pageId: string,
    patch: Partial<MigrationPage>,
  ) => void;
  appendProgressLog: (projectId: string, pageId: string, entry: string) => void;
  setPageStatus: (
    projectId: string,
    pageId: string,
    status: PageStatus,
  ) => void;

  // ── Plan editor actions ─────────────────────────────────────────────────────
  addSection: (
    projectId: string,
    pageId: string,
    atIndex: number,
    sectionType: string,
  ) => void;
  moveSection: (
    projectId: string,
    pageId: string,
    fromIndex: number,
    toIndex: number,
  ) => void;
  addWidget: (
    projectId: string,
    pageId: string,
    sectionPos: number,
    slotIndex: number,
    widget: ColumnWidget,
  ) => void;
  deleteWidget: (
    projectId: string,
    pageId: string,
    sectionPos: number,
    slotIndex: number,
    widgetIndex: number,
  ) => void;
  updateWidget: (
    projectId: string,
    pageId: string,
    sectionPos: number,
    slotIndex: number,
    widgetIndex: number,
    patch: Partial<ColumnWidget>,
  ) => void;
  moveWidget: (
    projectId: string,
    pageId: string,
    from: { sectionPos: number; slotIndex: number; widgetIndex: number },
    to: { sectionPos: number; slotIndex: number; widgetIndex: number },
  ) => void;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function makeId(): string {
  return crypto.randomUUID();
}

function makeCMProject(dealerId: string): CustomMigrationProject {
  return {
    id: makeId(),
    dealerId,
    type: "cm",
    createdAt: Date.now(),
    finishedDate: undefined,
    status: "In Progress",
    pages: [],
  };
}

function makeGMPrebuildProject(
  dealerId: string,
  bundle?: DealerBundle,
): GMPrebuildProject {
  return {
    id: makeId(),
    dealerId,
    type: "gm-prebuild",
    createdAt: Date.now(),
    finishedDate: undefined,
    status: "In Progress",
    pages: [],
    dealerBundle: bundle,
  };
}

function makeGMBuySellProject(
  dealerId: string,
  bundle?: DealerBundle,
): GMBuySellProject {
  return {
    id: makeId(),
    dealerId,
    type: "gm-buysell",
    createdAt: Date.now(),
    finishedDate: undefined,
    status: "In Progress",
    dealerBundle: bundle,
  };
}

function makeSpanishProject(
  dealerId: string,
  dealerName: string,
): SpanishMigrationProject {
  return {
    id: makeId(),
    dealerId,
    type: "spanish",
    createdAt: Date.now(),
    finishedDate: undefined,
    status: "In Progress",
    dealerName,
    labels: [],
  };
}

function makeLabelRow(alias: string): SpanishLabelRow {
  return {
    alias,
    status: "queued",
    enHtml: null,
    esHtml: "",
    warnings: [],
    raw: null,
    error: null,
    reasoning: "",
  };
}

function makePage(liveSiteUrl: string): MigrationPage {
  return {
    id: makeId(),
    liveSiteUrl,
    pageTitle: null,
    pageAlias: null,
    ddcAlias: null,
    status: "pending",
    sectionPlan: [],
    progressLog: [],
    warnings: [],
    error: null,
    tokenInfo: null,
    createdAt: Date.now(),
    completedAt: null,
    linkReplacements: {},
    pageType: "regular",
    staffPlan: null,
  };
}

/** Immutably update a single page inside the projects array.
 * Works for any project type that has a `pages` field (CM, Prebuild). */
function patchPage<T extends { id: string; pages: Array<{ id: string }> }>(
  projects: T[],
  projectId: string,
  pageId: string,
  patch: Partial<MigrationPage>,
): T[] {
  return projects.map((project) =>
    project.id !== projectId
      ? project
      : {
          ...project,
          pages: project.pages.map((page) =>
            page.id !== pageId ? page : { ...page, ...patch },
          ),
        },
  );
}

/** Read the section plan from a page — returns null if the page is not found. */
function getPlan(
  state: AppState,
  projectId: string,
  pageId: string,
): SectionPlanItem[] | null {
  for (const arr of [state.migrationProjects, state.prebuildProjects]) {
    const project = (
      arr as Array<{ id: string; pages?: MigrationPage[] }>
    ).find((p) => p.id === projectId);
    const page = project?.pages?.find((p) => p.id === pageId);
    if (page?.sectionPlan) return [...page.sectionPlan];
  }
  return null;
}

function insertAt(
  state: AppState,
  projectId: string,
  pageId: string,
  atIndex: number,
  section: SectionPlanItem,
): SectionPlanItem[] {
  for (const arr of [state.migrationProjects, state.prebuildProjects]) {
    const project = (
      arr as Array<{ id: string; pages?: MigrationPage[] }>
    ).find((p) => p.id === projectId);
    const page = project?.pages?.find((p) => p.id === pageId);
    if (page) {
      const plan = [...(page.sectionPlan || [])];
      plan.splice(atIndex, 0, section);
      return plan;
    }
  }
  return [];
}

// ── Store ─────────────────────────────────────────────────────────────────────

export const useMigrationStore = create<AppState>()(
  persist(
    (set) => ({
      // ── Initial router state ─────────────────────────────────────────────
      view: "projects",
      activeProjectId: null,
      activePageId: null,

      // ── Initial data ─────────────────────────────────────────────────────
      migrationProjects: [],
      buySellProjects: [],
      prebuildProjects: [],
      spanishProjects: [],

      // ── Router ────────────────────────────────────────────────────────────
      goToProjects: () =>
        set({ view: "projects", activeProjectId: null, activePageId: null }),

      goToProject: (projectId) =>
        set({
          view: "project",
          activeProjectId: projectId,
          activePageId: null,
        }),

      setActivePage: (pageId) => set({ activePageId: pageId }),

      // ── Projects ──────────────────────────────────────────────────────────
      createCMProject: (dealerId) => {
        const project = makeCMProject(dealerId);
        set((state) => ({
          migrationProjects: [...state.migrationProjects, project],
        }));
        return project.id;
      },

      createGMPrebuildProject: (dealerId, bundle) => {
        const project = makeGMPrebuildProject(dealerId, bundle);
        set((state) => ({
          prebuildProjects: [...state.prebuildProjects, project],
        }));
        return project.id;
      },

      createGMBuySellProject: (dealerId, bundle) => {
        const project = makeGMBuySellProject(dealerId, bundle);
        set((state) => ({
          buySellProjects: [...state.buySellProjects, project],
        }));
        return project.id;
      },

      createSpanishProject: (dealerId, dealerName) => {
        const project = makeSpanishProject(dealerId, dealerName);
        set((state) => ({
          spanishProjects: [...state.spanishProjects, project],
        }));
        return project.id;
      },

      // ── Spanish label actions ─────────────────────────────────────────────
      setSpanishLabels: (projectId, aliases) =>
        set((state) => ({
          spanishProjects: state.spanishProjects.map((proj) =>
            proj.id !== projectId
              ? proj
              : { ...proj, labels: aliases.map(makeLabelRow) },
          ),
        })),

      updateSpanishLabel: (projectId, alias, patch) =>
        set((state) => ({
          spanishProjects: state.spanishProjects.map((proj) =>
            proj.id !== projectId
              ? proj
              : {
                  ...proj,
                  labels: proj.labels.map((row) =>
                    row.alias !== alias ? row : { ...row, ...patch },
                  ),
                },
          ),
        })),

      deleteProject: (projectId) =>
        set((state) => ({
          migrationProjects: state.migrationProjects.filter(
            (migrationProject) => migrationProject.id !== projectId,
          ),
          buySellProjects: state.buySellProjects.filter(
            (buySellProject) => buySellProject.id !== projectId,
          ),
          prebuildProjects: state.prebuildProjects.filter(
            (prebuildProject) => prebuildProject.id !== projectId,
          ),
          spanishProjects: state.spanishProjects.filter(
            (spanishProject) => spanishProject.id !== projectId,
          ),
          ...(state.activeProjectId === projectId
            ? { view: "projects", activeProjectId: null, activePageId: null }
            : {}),
        })),

      toggleProjectStatus: (projectId) =>
        set((state) => {
          const toggleProject = <
            T extends
              | CustomMigrationProject
              | GMPrebuildProject
              | GMBuySellProject
              | SpanishMigrationProject,
          >(
            project: T,
          ): T => {
            if (project.id !== projectId) return project;
            const isFinished = project.status === "Finished";
            return {
              ...project,
              status: (isFinished ? "In Progress" : "Finished") as T["status"],
              finishedDate: isFinished ? undefined : Date.now(),
            };
          };

          return {
            migrationProjects: state.migrationProjects.map(toggleProject),
            buySellProjects: state.buySellProjects.map(toggleProject),
            prebuildProjects: state.prebuildProjects.map(toggleProject),
            spanishProjects: state.spanishProjects.map(toggleProject),
          };
        }),

      // ── Pages ─────────────────────────────────────────────────────────────
      addPage: (projectId, liveSiteUrl) => {
        const page = makePage(liveSiteUrl);
        set((state) => ({
          migrationProjects: state.migrationProjects.map((project) =>
            project.id !== projectId
              ? project
              : { ...project, pages: [...project.pages, page] },
          ),
          prebuildProjects: state.prebuildProjects.map((project) =>
            project.id !== projectId
              ? project
              : { ...project, pages: [...project.pages, page] },
          ),
        }));
        return page.id;
      },

      deletePage: (projectId, pageId) =>
        set((state) => ({
          migrationProjects: state.migrationProjects.map((project) =>
            project.id !== projectId
              ? project
              : {
                  ...project,
                  pages: project.pages.filter((p) => p.id !== pageId),
                },
          ),
          prebuildProjects: state.prebuildProjects.map((project) =>
            project.id !== projectId
              ? project
              : {
                  ...project,
                  pages: project.pages.filter((page) => page.id !== pageId),
                },
          ),
          ...(state.activePageId === pageId ? { activePageId: null } : {}),
        })),

      updatePage: (projectId, pageId, patch) =>
        set((state) => ({
          migrationProjects: patchPage(
            state.migrationProjects,
            projectId,
            pageId,
            patch,
          ),
          prebuildProjects: patchPage(
            state.prebuildProjects,
            projectId,
            pageId,
            patch,
          ),
        })),

      appendProgressLog: (projectId, pageId, entry) =>
        set((state) => ({
          migrationProjects: state.migrationProjects.map((proj) =>
            proj.id !== projectId
              ? proj
              : {
                  ...proj,
                  pages: proj.pages.map((page) =>
                    page.id !== pageId
                      ? page
                      : { ...page, progressLog: [...page.progressLog, entry] },
                  ),
                },
          ),
          prebuildProjects: state.prebuildProjects.map((proj) =>
            proj.id !== projectId
              ? proj
              : {
                  ...proj,
                  pages: proj.pages.map((page) =>
                    page.id !== pageId
                      ? page
                      : { ...page, progressLog: [...page.progressLog, entry] },
                  ),
                },
          ),
        })),

      setPageStatus: (projectId, pageId, status) =>
        set((state) => ({
          migrationProjects: patchPage(
            state.migrationProjects,
            projectId,
            pageId,
            { status },
          ),
          prebuildProjects: patchPage(
            state.prebuildProjects,
            projectId,
            pageId,
            { status },
          ),
        })),

      // ── Plan editor ───────────────────────────────────────────────────────────
      addSection: (projectId, pageId, atIndex, sectionType) =>
        set((state) => {
          const section = makeSection(sectionType, atIndex);
          return {
            migrationProjects: patchPage(
              state.migrationProjects,
              projectId,
              pageId,
              {
                sectionPlan: reindexPlan(
                  insertAt(state, projectId, pageId, atIndex, section),
                ),
              },
            ),
            prebuildProjects: patchPage(
              state.prebuildProjects,
              projectId,
              pageId,
              {
                sectionPlan: reindexPlan(
                  insertAt(state, projectId, pageId, atIndex, section),
                ),
              },
            ),
          };
        }),

      moveSection: (projectId, pageId, fromIndex, toIndex) =>
        set((state) => {
          const plan = getPlan(state, projectId, pageId);
          if (!plan || fromIndex === toIndex) return state;
          const next = [...plan];
          const [moved] = next.splice(fromIndex, 1);
          if (moved) next.splice(toIndex, 0, moved);
          return {
            migrationProjects: patchPage(
              state.migrationProjects,
              projectId,
              pageId,
              {
                sectionPlan: reindexPlan(next),
              },
            ),
            prebuildProjects: patchPage(
              state.prebuildProjects,
              projectId,
              pageId,
              {
                sectionPlan: reindexPlan(next),
              },
            ),
          };
        }),

      addWidget: (projectId, pageId, sectionPos, slotIndex, widget) =>
        set((state) => {
          const plan = getPlan(state, projectId, pageId);
          if (!plan) return state;
          const item = plan.find((s) => s.position === sectionPos);
          if (!item) return state;
          const slotCount = slotCountForType(item.section_type);
          if (slotIndex < 0 || slotIndex >= slotCount) return state;
          const nextPlan = plan.map((s) => {
            if (s.position !== sectionPos) return s;
            return {
              ...s,
              slots: s.slots.map((slot, si) =>
                si === slotIndex ? [...slot, { ...widget }] : slot,
              ),
            };
          });
          return {
            migrationProjects: patchPage(
              state.migrationProjects,
              projectId,
              pageId,
              {
                sectionPlan: nextPlan,
              },
            ),
            prebuildProjects: patchPage(
              state.prebuildProjects,
              projectId,
              pageId,
              {
                sectionPlan: nextPlan,
              },
            ),
          };
        }),

      deleteWidget: (projectId, pageId, sectionPos, slotIndex, widgetIndex) =>
        set((state) => {
          const plan = getPlan(state, projectId, pageId);
          if (!plan) return state;
          const nextPlan = plan.map((s) => {
            if (s.position !== sectionPos) return s;
            return {
              ...s,
              slots: s.slots.map((slot, si) => {
                if (si !== slotIndex) return slot;
                const next = [...slot];
                next.splice(widgetIndex, 1);
                return next;
              }),
            };
          });
          return {
            migrationProjects: patchPage(
              state.migrationProjects,
              projectId,
              pageId,
              {
                sectionPlan: nextPlan,
              },
            ),
            prebuildProjects: patchPage(
              state.prebuildProjects,
              projectId,
              pageId,
              {
                sectionPlan: nextPlan,
              },
            ),
          };
        }),

      updateWidget: (
        projectId,
        pageId,
        sectionPos,
        slotIndex,
        widgetIndex,
        patch,
      ) =>
        set((state) => {
          const plan = getPlan(state, projectId, pageId);
          if (!plan) return state;
          const nextPlan = plan.map((s) => {
            if (s.position !== sectionPos) return s;
            return {
              ...s,
              slots: s.slots.map((slot, si) => {
                if (si !== slotIndex) return slot;
                return slot.map((w, wi) =>
                  wi === widgetIndex ? { ...w, ...patch } : w,
                );
              }),
            };
          });
          return {
            migrationProjects: patchPage(
              state.migrationProjects,
              projectId,
              pageId,
              {
                sectionPlan: nextPlan,
              },
            ),
            prebuildProjects: patchPage(
              state.prebuildProjects,
              projectId,
              pageId,
              {
                sectionPlan: nextPlan,
              },
            ),
          };
        }),

      moveWidget: (projectId, pageId, from, to) =>
        set((state) => {
          const plan = getPlan(state, projectId, pageId);
          if (!plan) return state;

          let moved: import("../types").ColumnWidget | null = null;
          let nextPlan = plan.map((s) => {
            if (s.position !== from.sectionPos) return s;
            return {
              ...s,
              slots: s.slots.map((slot, si) => {
                if (si !== from.slotIndex) return slot;
                const next = [...slot];
                const [item] = next.splice(from.widgetIndex, 1);
                if (item) moved = item;
                return next;
              }),
            };
          });

          if (!moved) return state;

          nextPlan = nextPlan.map((s) => {
            if (s.position !== to.sectionPos) return s;
            return {
              ...s,
              slots: s.slots.map((slot, si) => {
                if (si !== to.slotIndex) return slot;
                const next = [...slot];
                next.splice(to.widgetIndex, 0, moved!);
                return next;
              }),
            };
          });

          return {
            migrationProjects: patchPage(
              state.migrationProjects,
              projectId,
              pageId,
              {
                sectionPlan: nextPlan,
              },
            ),
            prebuildProjects: patchPage(
              state.prebuildProjects,
              projectId,
              pageId,
              {
                sectionPlan: nextPlan,
              },
            ),
          };
        }),
    }),
    {
      name: "ddc-migration-store",
      // createJSONStorage wraps the async chrome.storage adapter into the
      // PersistStorage<S> shape Zustand expects (handles JSON serialisation).
      storage: createJSONStorage(() => chromeStorageAdapter),
      // Only persist project data — router state always resets to projects list.
      partialize: (state) => ({
        migrationProjects: state.migrationProjects,
        buySellProjects: state.buySellProjects,
        prebuildProjects: state.prebuildProjects,
        spanishProjects: state.spanishProjects,
      }),
    },
  ),
);

// ── Selectors (stable references, use in components) ─────────────────────────

export const selectActiveProject = (
  state: AppState,
):
  | CustomMigrationProject
  | GMPrebuildProject
  | GMBuySellProject
  | SpanishMigrationProject
  | null => {
  return (
    state.migrationProjects.find((p) => p.id === state.activeProjectId) ??
    state.prebuildProjects.find((p) => p.id === state.activeProjectId) ??
    state.buySellProjects.find((p) => p.id === state.activeProjectId) ??
    state.spanishProjects.find((p) => p.id === state.activeProjectId) ??
    null
  );
};

export const selectActivePage = (state: AppState): MigrationPage | null => {
  const project = selectActiveProject(state);
  if (!project || !state.activePageId || !("pages" in project)) return null;
  return project.pages.find((p) => p.id === state.activePageId) ?? null;
};
