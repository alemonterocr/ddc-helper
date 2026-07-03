import type { DealerBundle, SectionPlanItem, TokenInfo } from "../types";

// ── Domain models ──────────────────────────────────────────────────────────────

export type PageStatus =
  | "pending"
  | "analyzing"
  | "reviewing"
  | "executing"
  | "done"
  | "error";

/** Page migration flow type — defaults to 'regular' for all existing/new
 *  pages. The user explicitly flips a page to 'staff' to opt into the staff
 *  migration workflow (different DDC API target, different review UX). */
export type PageType = "regular" | "staff";

/** A single staff member extracted by /parse-staff. Mirrors the backend's
 *  StaffMemberDTO. */
export interface StaffMember {
  department: string;
  name: string;
  title: string | null;
  phone: string | null;
  email: string | null;
  bio: string | null;
  has_photo: boolean;
  original_photo_url: string | null;
  /** CDN URL filled after photo upload — set by the backend executor. */
  photo: string | null;
}

export interface MigrationPage {
  id: string;
  liveSiteUrl: string;
  /** Human-readable page title returned by the LLM */
  pageTitle: string | null;
  /** URL slug e.g. "awards.htm" */
  pageAlias: string | null;
  /** DDC internal alias e.g. "SITEBUILDER_AWARDS_3" */
  ddcAlias: string | null;
  status: PageStatus;
  sectionPlan: SectionPlanItem[];
  progressLog: string[];
  warnings: string[];
  error: string | null;
  tokenInfo: TokenInfo | null;
  createdAt: number;
  completedAt: number | null;
  /**
   * User-supplied link replacements: original href → DDC replacement URL.
   * Applied to all content widget HTML before execution.
   * Replacements starting with "/" are treated as internal (no target);
   * everything else gets target="_blank".
   */
  linkReplacements: Record<string, string>;
  /** Migration flow type. Defaults to 'regular'. Toggling to 'staff' makes
   *  ProjectPage render StaffFlowPanel instead of MigrationFlowPanel. */
  pageType: PageType;
  /** Extracted staff members for the staff flow. Null until /parse-staff
   *  completes. Edited by the user during the reviewing step. */
  staffPlan: StaffMember[] | null;
}

export type ProjectType = "cm" | "gm-prebuild" | "gm-buysell" | "spanish";

// ── Spanish (label translation) flow ─────────────────────────────────────────

/** Lifecycle of one label inside a Spanish migration project. */
export type LabelRowStatus =
  | "queued"        // sanitized, waiting to start
  | "fetching"      // GET-label from DDC in flight
  | "translating"   // /translations/translate in flight
  | "ready"         // translation came back clean, awaiting user save
  | "error"         // fetch failed, or translation failed validation
  | "saved"         // POST-label to DDC succeeded
  | "skipped"       // user opted to skip this alias
  | "not_found";    // DDC returned no en_US for the alias

/** One label inside a Spanish migration project. */
export interface SpanishLabelRow {
  alias: string;
  status: LabelRowStatus;
  /** EN value pulled from DDC. Null until fetched. */
  enHtml: string | null;
  /** ES value — model output, possibly user-edited before save. */
  esHtml: string;
  /** Warnings from the translation validator (tag mismatch, etc.). */
  warnings: string[];
  /** Raw model output when validation failed and the user needs to hand-edit. */
  raw: string | null;
  /** Last error message from any failed step. */
  error: string | null;
  /** Translator's brief reasoning (translation choices). Empty when absent. */
  reasoning: string;
}

export interface BaseProject {
  id: string;
  dealerId: string;
  type: ProjectType;
  createdAt: number;
  finishedDate?: number;
  status: "Finished" | "In Progress";
}

export interface CustomMigrationProject extends BaseProject {
  type: "cm";
  pages: MigrationPage[];
}

export interface GMBuySellProject extends BaseProject {
  type: "gm-buysell";
  /** Set when the project was created via the Salesforce intake wizard.
   *  Drives the dashboard header (GMSetupBlock). May be undefined for projects
   *  created before the wizard shipped. */
  dealerBundle?: DealerBundle;
}

export interface GMPrebuildProject extends BaseProject {
  type: "gm-prebuild";
  pages: MigrationPage[];
  /** Same as GMBuySellProject.dealerBundle. */
  dealerBundle?: DealerBundle;
}

/**
 * Spanish label-translation project — no pages, just a list of label rows.
 * `dealerName` is required so the translation prompt can keep brand names
 * (e.g. "Orange Buick GMC") untranslated.
 */
export interface SpanishMigrationProject extends BaseProject {
  type: "spanish";
  dealerName: string;
  labels: SpanishLabelRow[];
}

// ── Router ─────────────────────────────────────────────────────────────────────

export type AppView = "projects" | "project";

export interface RouterState {
  view: AppView;
  activeProjectId: string | null;
  activePageId: string | null;
}
