import type {
  AnalyzeRequest,
  AnalyzeResponse,
  ConfigureKeyRequest,
  ConfigureKeyResponse,
  DeterministicAnalyzeRequest,
  DeterministicAnalyzeResponse,
  ExecuteRequest,
  ExecuteResponse,
  ExecuteStaffRequest,
  ExecuteStaffResponse,
  ParseNavRequest,
  ParseNavResponse,
  ParseStaffRequest,
  ParseStaffResponse,
  SalesforceIntakeRequest,
  SalesforceIntakeResponse,
} from '../../types'

export interface BackendPort {
  configureApiKey(request: ConfigureKeyRequest): Promise<ConfigureKeyResponse>
  analyzePage(request: AnalyzeRequest, signal?: AbortSignal): Promise<AnalyzeResponse>
  analyzeDeterministic(request: DeterministicAnalyzeRequest): Promise<DeterministicAnalyzeResponse>
  executeMigration(request: ExecuteRequest, signal?: AbortSignal): Promise<ExecuteResponse>
  parseNav(request: ParseNavRequest, signal?: AbortSignal): Promise<ParseNavResponse>
  parseStaff(request: ParseStaffRequest, signal?: AbortSignal): Promise<ParseStaffResponse>
  executeStaff(request: ExecuteStaffRequest, signal?: AbortSignal): Promise<ExecuteStaffResponse>
  salesforceIntake(request: SalesforceIntakeRequest, signal?: AbortSignal): Promise<SalesforceIntakeResponse>
}
