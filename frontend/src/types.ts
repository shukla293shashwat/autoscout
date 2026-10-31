// Shared TypeScript types mirroring the backend API responses.

export type ArtifactKind = 'email' | 'lead' | 'note' | 'task'

export interface Artifact {
  id: number
  upload_id: number
  kind: ArtifactKind
  source_ref: string
  timestamp: string | null
  title: string
  text: string
  raw_json: string
}

export type Feasibility = 'high' | 'medium' | 'low'

export interface Workflow {
  id: number
  upload_id: number
  name: string
  description: string
  trigger: string
  steps: string[]
  inputs: string[]
  outputs: string[]
  minutes_per_occurrence: number
  occurrences: number
  feasibility: Feasibility
  evidence: string[]
  status: string
  low_confidence: boolean
  time_rationale: string
  feasibility_reason: string
  // ROI fields (added by the scoring layer)
  occurrences_per_week: number
  hours_saved_per_week: number
  priority_score: number
  roi_explanation: string
}

export interface Summary {
  upload_id: number
  workflow_count: number
  total_hours_saved_per_week: number
  total_occurrences_per_week: number
  by_feasibility: Record<string, number>
  top_workflow: string | null
}

export interface UploadResponse {
  upload_id: number
  counts: Record<string, number>
  skipped: number
  errors: string[]
}

export interface AutomationStep {
  tool: string
  args_template: Record<string, unknown>
  description: string
  capture_as?: string | null
  capture_key?: string
}

export interface AutomationPlan {
  name: string
  trigger: string
  steps: AutomationStep[]
}

export interface StepResult {
  step: number
  tool: string
  dry_run: boolean
  status: string
  action: string
  preview: string
  path?: string
  output?: string
}

export interface DryRunResult {
  workflow_id: number
  mode: 'dry_run'
  plan: AutomationPlan
  step_results: StepResult[]
  status: string
}

export interface ExecuteResult {
  workflow_id: number
  mode: 'executed'
  plan: AutomationPlan
  step_results: StepResult[]
  status: string
  approver: string
  outputs: string[]
}

export interface AuditEntry {
  id: number
  workflow_id: number
  mode: 'dry_run' | 'executed'
  approved_by: string
  started_at: string | null
  finished_at: string | null
  step_results: StepResult[]
  status: string
}
