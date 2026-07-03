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
import { BackendError } from '../../types'
import type { BackendPort } from '../ports/BackendPort'

export class BackendHttpAdapter implements BackendPort {
  private readonly baseUrl: string

  constructor() {
    this.baseUrl = import.meta.env.VITE_BACKEND_URL ?? 'http://localhost:8000'
  }

  async configureApiKey(request: ConfigureKeyRequest): Promise<ConfigureKeyResponse> {
    return this.post<ConfigureKeyResponse>('/config/api-key', request)
  }

  async analyzePage(request: AnalyzeRequest, signal?: AbortSignal): Promise<AnalyzeResponse> {
    return this.post<AnalyzeResponse>('/analyze', request, signal)
  }

  async analyzeDeterministic(request: DeterministicAnalyzeRequest): Promise<DeterministicAnalyzeResponse> {
    return this.post<DeterministicAnalyzeResponse>('/analyze-deterministic', request)
  }

  async executeMigration(request: ExecuteRequest, signal?: AbortSignal): Promise<ExecuteResponse> {
    return this.post<ExecuteResponse>('/execute', request, signal)
  }

  async parseNav(request: ParseNavRequest, signal?: AbortSignal): Promise<ParseNavResponse> {
    return this.post<ParseNavResponse>('/parse-nav', request, signal)
  }

  async parseStaff(request: ParseStaffRequest, signal?: AbortSignal): Promise<ParseStaffResponse> {
    return this.post<ParseStaffResponse>('/parse-staff', request, signal)
  }

  async executeStaff(request: ExecuteStaffRequest, signal?: AbortSignal): Promise<ExecuteStaffResponse> {
    return this.post<ExecuteStaffResponse>('/execute-staff', request, signal)
  }

  async salesforceIntake(
    request: SalesforceIntakeRequest,
    signal?: AbortSignal,
  ): Promise<SalesforceIntakeResponse> {
    return this.post<SalesforceIntakeResponse>('/salesforce/intake', request, signal)
  }

  private async post<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal,
    })

    if (!response.ok) {
      throw new BackendError(`Request to ${path} failed`, response.status)
    }

    return response.json() as Promise<T>
  }
}
