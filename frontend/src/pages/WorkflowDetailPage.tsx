// Screen 3 — Workflow detail: evidence, plan timeline, dry-run, approval bar.

import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '../api'
import { Card, EmptyState, FeasibilityBadge, Skeleton } from '../components/ui'
import { useAsync, useToasts } from '../store'
import type { AutomationPlan, DryRunResult, ExecuteResult } from '../types'

function EvidenceItem({ artifact }: { artifact: { title: string; text: string; kind: string } }) {
  const [open, setOpen] = useState(false)
  const snippet = artifact.text.length > 160 ? artifact.text.slice(0, 160) + '…' : artifact.text
  return (
    <li className="rounded-lg border border-neutral-200 bg-neutral-50 p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <span className="mr-2 rounded bg-neutral-200 px-1.5 py-0.5 text-[10px] font-medium uppercase text-neutral-600">
            {artifact.kind}
          </span>
          <span className="font-medium text-neutral-800">{artifact.title}</span>
          <p className="mt-1 text-sm text-neutral-500">
            {open ? artifact.text : snippet}
          </p>
        </div>
        <button
          onClick={() => setOpen((o) => !o)}
          className="shrink-0 text-xs font-medium text-accent hover:underline"
        >
          {open ? 'Show less' : 'Show full'}
        </button>
      </div>
    </li>
  )
}

export function WorkflowDetailPage() {
  const { id } = useParams<{ id: string }>()
  const wid = Number(id)
  const { push } = useToasts()

  const wf = useAsync(() => api.getWorkflow(wid), [wid], Number.isFinite(wid))
  const artifacts = useAsync(
    () => (wf.data ? api.getArtifacts(wf.data.upload_id) : Promise.resolve([])),
    [wf.data?.upload_id],
    wf.data != null,
  )

  const [plan, setPlan] = useState<AutomationPlan | null>(null)
  const [dry, setDry] = useState<DryRunResult | null>(null)
  const [exec, setExec] = useState<ExecuteResult | null>(null)
  const [busy, setBusy] = useState<'plan' | 'dry' | 'exec' | null>(null)
  const [reviewed, setReviewed] = useState(false)
  const [approver, setApprover] = useState('')

  if (wf.loading) return <Skeleton className="h-64 w-full" />
  if (wf.error || !wf.data)
    return <EmptyState title="Workflow not found" hint={wf.error ?? undefined} />
  const w = wf.data

  async function genPlan() {
    setBusy('plan')
    try {
      setPlan(await api.generatePlan(wid))
      setDry(null)
      setExec(null)
      setReviewed(false)
      push('info', 'Automation plan generated.')
    } catch (e) {
      push('error', e instanceof Error ? e.message : 'Plan failed')
    } finally {
      setBusy(null)
    }
  }

  async function runDry() {
    setBusy('dry')
    try {
      setDry(await api.dryRun(wid))
      push('success', 'Dry run complete — no side effects.')
    } catch (e) {
      push('error', e instanceof Error ? e.message : 'Dry run failed')
    } finally {
      setBusy(null)
    }
  }

  async function runExec() {
    setBusy('exec')
    try {
      const res = await api.execute(wid, approver)
      setExec(res)
      push('success', `Executed by ${approver}. ${res.outputs.length} output(s).`)
    } catch (e) {
      push('error', e instanceof Error ? e.message : 'Execution failed')
    } finally {
      setBusy(null)
    }
  }

  const evArts = (artifacts.data ?? []).filter((a) => w.evidence.includes(a.source_ref))

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1.3fr_1fr]">
      {/* LEFT: workflow info + evidence */}
      <div className="space-y-5">
        <Card>
          <div className="flex items-start justify-between gap-3">
            <div>
              <h1 className="text-xl font-bold text-neutral-900">{w.name}</h1>
              <div className="mt-1 flex items-center gap-2 text-sm">
                <FeasibilityBadge value={w.feasibility} />
                <span className="text-neutral-500">{w.feasibility_reason || w.trigger}</span>
              </div>
            </div>
            <div className="text-right">
              <div className="text-2xl font-bold tabular-nums text-accent">
                {w.hours_saved_per_week.toFixed(2)}
              </div>
              <div className="text-xs text-neutral-500">hours/week</div>
            </div>
          </div>
          <p className="mt-3 text-sm text-neutral-600">{w.description}</p>

          <div className="mt-4 rounded-xl bg-neutral-50 p-3 text-sm text-neutral-700">
            <div className="font-medium text-neutral-800">Trigger</div>
            <div>{w.trigger}</div>
            <div className="mt-2 font-medium text-neutral-800">ROI</div>
            <div>{w.roi_explanation}</div>
          </div>

          <div className="mt-4">
            <div className="mb-2 text-sm font-medium uppercase tracking-wide text-neutral-500">
              Detected manual steps
            </div>
            <ol className="space-y-1.5">
              {w.steps.map((s, i) => (
                <li key={i} className="flex gap-3 text-sm text-neutral-700">
                  <span className="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-neutral-200 text-[11px] font-semibold">
                    {i + 1}
                  </span>
                  {s}
                </li>
              ))}
            </ol>
          </div>
        </Card>

        <Card>
          <div className="mb-3 flex items-center justify-between">
            <div className="text-sm font-medium uppercase tracking-wide text-neutral-500">
              Evidence ({evArts.length})
            </div>
            <span className="text-xs text-neutral-400">backed by real source items</span>
          </div>
          {artifacts.loading ? (
            <Skeleton className="h-16 w-full" />
          ) : (
            <ul className="space-y-2">
              {evArts.slice(0, 8).map((a) => (
                <EvidenceItem key={a.id} artifact={a} />
              ))}
              {evArts.length > 8 && (
                <li className="text-center text-xs text-neutral-400">
                  + {evArts.length - 8} more
                </li>
              )}
            </ul>
          )}
        </Card>
      </div>

      {/* RIGHT: automation build + approval */}
      <div className="space-y-5">
        <Card>
          <div className="mb-3 text-sm font-medium uppercase tracking-wide text-neutral-500">
            Automation
          </div>
          {!plan && (
            <button
              onClick={() => void genPlan()}
              disabled={busy === 'plan'}
              className="w-full rounded-xl bg-accent px-4 py-3 font-semibold text-white hover:bg-accent-dark disabled:opacity-60"
            >
              {busy === 'plan' ? 'Generating…' : '⚙  Generate automation'}
            </button>
          )}

          {plan && (
            <>
              {/* Plan timeline */}
              <div className="relative space-y-4 border-l-2 border-neutral-200 pl-5">
                {plan.steps.map((s, i) => (
                  <div key={i} className="relative">
                    <span className="absolute -left-[27px] grid h-5 w-5 place-items-center rounded-full bg-accent text-[11px] font-bold text-white">
                      {i + 1}
                    </span>
                    <div className="rounded-lg border border-neutral-200 p-3">
                      <div className="font-medium text-neutral-900">{s.description || s.tool}</div>
                      <code className="text-xs text-neutral-500">{s.tool}</code>
                      <pre className="mt-1 max-h-24 overflow-auto rounded bg-neutral-50 p-2 text-[11px] text-neutral-600">
                        {JSON.stringify(s.args_template, null, 2)}
                      </pre>
                    </div>
                  </div>
                ))}
              </div>

              {!dry && !exec && (
                <button
                  onClick={() => void runDry()}
                  disabled={busy === 'dry'}
                  className="mt-4 w-full rounded-xl border border-neutral-300 px-4 py-3 font-medium text-neutral-800 hover:bg-neutral-50 disabled:opacity-60"
                >
                  {busy === 'dry' ? 'Running dry run…' : '▶  Run dry run'}
                </button>
              )}
            </>
          )}

          {/* Dry-run previews */}
          {dry && !exec && (
            <div className="mt-4">
              <div className="mb-2 flex items-center justify-between">
                <span className="text-sm font-medium text-emerald-600">
                  ✓ Dry run ready (no files written)
                </span>
                <button onClick={() => void runDry()} className="text-xs text-neutral-500 hover:underline">
                  Re-run
                </button>
              </div>
              <div className="space-y-2">
                {dry.step_results.map((r, i) => (
                  <div key={i} className="rounded-lg border border-neutral-200 bg-neutral-50 p-3">
                    <div className="text-xs font-medium text-neutral-500">
                      Step {i + 1} · {r.tool} · {r.status}
                    </div>
                    <pre className="mt-1 max-h-32 overflow-auto whitespace-pre-wrap text-[11px] text-neutral-700">
                      {r.preview}
                    </pre>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Success state */}
          {exec && (
            <div className="mt-4 rounded-xl border border-emerald-300 bg-emerald-50 p-4">
              <div className="font-semibold text-emerald-800">
                ✓ Executed by {exec.approver}
              </div>
              <div className="mt-1 text-sm text-emerald-700">Outputs written:</div>
              <ul className="mt-1 space-y-1 text-xs text-emerald-900">
                {exec.outputs.map((p, i) => (
                  <li key={i} className="font-mono">{p}</li>
                ))}
              </ul>
            </div>
          )}
        </Card>

        {/* Sticky approval bar */}
        {plan && dry && !exec && (
          <Card className="sticky bottom-4">
            <label className="flex items-center gap-2 text-sm text-neutral-700">
              <input
                type="checkbox"
                checked={reviewed}
                onChange={(e) => setReviewed(e.target.checked)}
                className="h-4 w-4 rounded border-neutral-300 text-accent"
              />
              I reviewed the preview
            </label>
            <input
              type="text"
              value={approver}
              onChange={(e) => setApprover(e.target.value)}
              placeholder="Your name"
              className="mt-3 w-full rounded-lg border border-neutral-300 px-3 py-2 text-sm focus:border-accent focus:outline-none"
            />
            <button
              onClick={() => void runExec()}
              disabled={!reviewed || !approver.trim() || busy === 'exec'}
              className="mt-3 w-full rounded-xl bg-neutral-900 px-4 py-3 font-semibold text-white hover:bg-neutral-800 disabled:opacity-40"
            >
              {busy === 'exec' ? 'Executing…' : '✓  Approve & execute'}
            </button>
            {(!reviewed || !approver.trim()) && (
              <p className="mt-2 text-center text-xs text-neutral-400">
                Check the box and enter your name to enable execution.
              </p>
            )}
          </Card>
        )}
      </div>
    </div>
  )
}
