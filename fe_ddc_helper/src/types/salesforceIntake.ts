/**
 * Shared types for the Salesforce intake flow.
 * Mirrors `be_ddc_helper/src/application/salesforce/bundle_dtos.py`.
 */

export interface SalesforceIntakeRequest {
  board_url: string
  provider?: string | null
}

export type DesignChoice =
  | { kind: 'json'; value: Record<string, unknown> }
  | { kind: 'description'; raw: string; needs_human_input: true }
  | { kind: 'missing' }

export interface Classification {
  value: 'prebuild' | 'buysell'
  confidence: number
  reasoning: string
  source: 'llm' | 'user-override' | 'default'
}

export interface IntakeSource {
  board_id: string
  questionnaire_insight_id: string
  precursive_project_id: string
  fetched_at: string
}

export interface DealerBundle {
  ppr: string
  dealer_id: string
  dealership_name: string
  new_dealership_name: string
  dealership_address: string
  leads_email: string
  primary_url: string
  new_primary_url: string
  design_choice: DesignChoice
  classification: Classification
  source: IntakeSource
  warnings: string[]
}

export interface SalesforceIntakeResponse {
  bundle?: DealerBundle
  error?: string
}
