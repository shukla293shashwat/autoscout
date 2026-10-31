// Typed API client for the AutoScout backend.
// Uses relative paths; the Vite dev server proxies /api and /health.

import type {
  Artifact,
  AuditEntry,
  AutomationPlan,
  DryRunResult,
  ExecuteResult,
  Summary,
  UploadResponse,
  Workflow,
} from './types'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let resp: Response
  try {
    resp = await fetch(path, {
      headers: { Accept: 'application/json' },
      ...init,
    })
  } catch {
    throw new ApiError(0, 'Could not reach the AutoScout backend. Is it running?')
  }
  const text = await resp.text()
  let data: unknown
  try {
    data = text ? JSON.parse(text) : null
  } catch {
    data = { detail: text }
  }
  if (!resp.ok) {
    const detail =
      (data as { detail?: unknown })?.detail ??
      (typeof data === 'string' ? data : 'Request failed')
    throw new ApiError(resp.status, typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  return data as T
}

export const api = {
  health: () => request<{ status: string }>('/health'),

  uploadSample: () => request<UploadResponse>('/api/uploads/sample', { method: 'POST' }),

  uploadFiles: async (files: File[]) => {
    const form = new FormData()
    files.forEach((f) => form.append('files', f))
    return request<UploadResponse>('/api/uploads', { method: 'POST', body: form })
  },

  discover: (uploadId: number) =>
    request<{ upload_id: number; workflows: Workflow[]; count: number }>(
      `/api/uploads/${uploadId}/discover`,
      { method: 'POST' },
    ),

  getWorkflows: (uploadId: number) =>
    request<Workflow[]>(`/api/workflows?upload_id=${uploadId}`),

  getWorkflow: (id: number) => request<Workflow>(`/api/workflows/${id}`),

  getSummary: (uploadId: number) => request<Summary>(`/api/summary?upload_id=${uploadId}`),

  getArtifacts: (uploadId: number) =>
    request<Artifact[]>(`/api/artifacts?upload_id=${uploadId}`),

  generatePlan: (workflowId: number) =>
    request<AutomationPlan>(`/api/workflows/${workflowId}/plan`, { method: 'POST' }),

  dryRun: (workflowId: number) =>
    request<DryRunResult>(`/api/workflows/${workflowId}/dry-run`, { method: 'POST' }),

  execute: (workflowId: number, approver: string) =>
    request<ExecuteResult>(`/api/workflows/${workflowId}/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ approved: true, approver }),
    }),

  getAudit: (workflowId?: number) =>
    request<AuditEntry[]>(
      workflowId != null ? `/api/audit?workflow_id=${workflowId}` : '/api/audit',
    ),
}
