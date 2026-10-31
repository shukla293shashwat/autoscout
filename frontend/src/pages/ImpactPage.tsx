// Screen 4 — Impact dashboard: KPI cards, hours/week bar chart, audit log.

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { Card, EmptyState, Skeleton, StatCard } from '../components/ui'
import { useAsync, useSession } from '../store'
import type { AuditEntry } from '../types'

export function ImpactPage() {
  const nav = useNavigate()
  const { uploadId } = useSession()
  const [modeFilter, setModeFilter] = useState<'all' | 'dry_run' | 'executed'>('all')

  const summary = useAsync(
    async () => (uploadId ? api.getSummary(uploadId) : null),
    [uploadId],
    uploadId != null,
  )
  const workflows = useAsync(
    async () => (uploadId ? api.getWorkflows(uploadId) : []),
    [uploadId],
    uploadId != null,
  )
  const audit = useAsync(async () => api.getAudit(), [], true)

  if (uploadId == null) {
    return (
      <EmptyState
        title="No data yet"
        hint="Load sample data first, then discover workflows to see impact."
        action={
          <button
            onClick={() => nav('/')}
            className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-dark"
          >
            Go to Upload
          </button>
        }
      />
    )
  }

  const s = summary.data
  const wfList = workflows.data ?? []
  const maxHours = Math.max(...wfList.map((w) => w.hours_saved_per_week), 0.1)
  const executed = (audit.data ?? []).filter((a) => a.mode === 'executed')
  const approved = new Set(executed.map((a) => a.approved_by).filter(Boolean))
  const entries = (audit.data ?? []).filter(
    (a) => modeFilter === 'all' || a.mode === modeFilter,
  )

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-neutral-900">Impact</h1>
        <p className="text-neutral-500">
          What AutoScout found and what it automated this session.
        </p>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {summary.loading ? (
          Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-28" />)
        ) : (
          <>
            <StatCard label="Workflows found" value={s?.workflow_count ?? 0} />
            <StatCard
              label="Hours/week identified"
              value={`${(s?.total_hours_saved_per_week ?? 0).toFixed(1)}h`}
              accent
            />
            <StatCard label="Automations run" value={executed.length} />
            <StatCard label="Approvals" value={approved.size} sub={`${executed.length} executions`} />
          </>
        )}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Bar chart: hours/week per workflow */}
        <Card>
          <div className="mb-4 text-sm font-medium uppercase tracking-wide text-neutral-500">
            Hours/week by workflow
          </div>
          {workflows.loading ? (
            <Skeleton className="h-48 w-full" />
          ) : wfList.length === 0 ? (
            <EmptyState title="No workflows yet" />
          ) : (
            <div className="space-y-3">
              {wfList.map((w) => {
                const pct = (w.hours_saved_per_week / maxHours) * 100
                return (
                  <div key={w.id}>
                    <div className="flex justify-between text-sm">
                      <span className="truncate pr-2 text-neutral-700">{w.name}</span>
                      <span className="shrink-0 font-medium tabular-nums text-neutral-900">
                        {w.hours_saved_per_week.toFixed(2)}h
                      </span>
                    </div>
                    <div className="mt-1 h-3 w-full rounded-full bg-neutral-100">
                      <div
                        className="h-3 rounded-full bg-accent transition-all duration-700"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </Card>

        {/* Audit log */}
        <Card>
          <div className="mb-3 flex items-center justify-between">
            <div className="text-sm font-medium uppercase tracking-wide text-neutral-500">
              Audit log
            </div>
            <div className="flex gap-1 text-xs">
              {(['all', 'dry_run', 'executed'] as const).map((m) => (
                <button
                  key={m}
                  onClick={() => setModeFilter(m)}
                  className={`rounded-full px-2.5 py-1 capitalize ${
                    modeFilter === m ? 'bg-neutral-900 text-white' : 'text-neutral-500 hover:bg-neutral-100'
                  }`}
                >
                  {m.replace('_', ' ')}
                </button>
              ))}
            </div>
          </div>
          {audit.loading ? (
            <Skeleton className="h-48 w-full" />
          ) : entries.length === 0 ? (
            <EmptyState title="No runs yet" hint="Dry-run or execute a workflow to populate the audit log." />
          ) : (
            <div className="max-h-72 overflow-auto">
              <table className="w-full text-left text-sm">
                <thead className="sticky top-0 bg-white text-xs uppercase text-neutral-400">
                  <tr>
                    <th className="py-2">Time</th>
                    <th>Workflow</th>
                    <th>Mode</th>
                    <th>Approver</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-100">
                  {entries.map((a: AuditEntry) => (
                    <tr key={a.id} className="text-neutral-700">
                      <td className="py-2 pr-2 whitespace-nowrap">
                        {a.started_at ? new Date(a.started_at).toLocaleTimeString() : '—'}
                      </td>
                      <td className="max-w-[10rem] truncate">#{a.workflow_id}</td>
                      <td className="capitalize">{a.mode.replace('_', ' ')}</td>
                      <td>{a.approved_by || '—'}</td>
                      <td
                        className={
                          a.status === 'ok'
                            ? 'text-emerald-600'
                            : a.status === 'partial'
                              ? 'text-amber-600'
                              : 'text-red-600'
                        }
                      >
                        {a.status}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
