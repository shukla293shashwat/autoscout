// Screen 2 — Discovery map (hero): bubble map + ranked list, synced hover.

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { BubbleMap } from '../components/BubbleMap'
import { Card, EmptyState, FeasibilityBadge, Skeleton } from '../components/ui'
import { useAsync, useSession } from '../store'

export function DiscoveryPage() {
  const nav = useNavigate()
  const { uploadId } = useSession()
  const [hovered, setHovered] = useState<number | null>(null)

  const { data, loading, error } = useAsync(
    async () => (uploadId ? api.getWorkflows(uploadId) : null),
    [uploadId],
    uploadId != null,
  )

  if (uploadId == null) {
    return (
      <EmptyState
        title="No data yet"
        hint="Load sample data (or upload files) first to discover workflows."
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

  if (loading) {
    return (
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1.2fr_1fr]">
        <Skeleton className="h-[440px] w-full" />
        <div className="space-y-3">
          <Skeleton className="h-8 w-2/3" />
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      </div>
    )
  }

  if (error) {
    return <EmptyState title="Could not load workflows" hint={error} />
  }

  const workflows = data ?? []
  const totalHours = workflows.reduce((s, w) => s + w.hours_saved_per_week, 0)

  if (workflows.length === 0) {
    return (
      <EmptyState
        title="No workflows discovered"
        hint="Run discovery on your upload to see the repetitive work AutoScout found."
        action={
          <button
            onClick={() => nav('/')}
            className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-dark"
          >
            Back to Upload
          </button>
        }
      />
    )
  }

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-neutral-900">
            We found {workflows.length} repetitive workflows
          </h1>
          <p className="text-accent text-lg font-semibold">
            costing you about {totalHours.toFixed(1)} hours/week
          </p>
        </div>
        <div className="text-sm text-neutral-500">
          size = hours/week · color = feasibility
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1.2fr_1fr]">
        {/* Hero: bubble map */}
        <Card className="p-3 h-[440px]">
          <BubbleMap
            workflows={workflows}
            hovered={hovered}
            onHover={setHovered}
            onSelect={(id) => nav(`/workflow/${id}`)}
          />
        </Card>

        {/* Ranked list */}
        <div className="flex flex-col">
          <div className="mb-2 text-sm font-medium uppercase tracking-wide text-neutral-500">
            Ranked by hours saved
          </div>
          <ul className="space-y-3">
            {workflows.map((w, i) => {
              const isHover = hovered === w.id
              return (
                <li key={w.id}>
                  <button
                    onMouseEnter={() => setHovered(w.id)}
                    onMouseLeave={() => setHovered(null)}
                    onFocus={() => setHovered(w.id)}
                    onBlur={() => setHovered(null)}
                    onClick={() => nav(`/workflow/${w.id}`)}
                    className={`flex w-full items-center gap-4 rounded-xl border p-4 text-left transition ${
                      isHover
                        ? 'border-accent bg-accent/5 shadow-sm'
                        : 'border-neutral-200 bg-white hover:border-neutral-300'
                    }`}
                  >
                    <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-neutral-100 text-sm font-bold text-neutral-500">
                      {i + 1}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-medium text-neutral-900">
                        {w.name}
                      </span>
                      <span className="block text-sm tabular-nums text-neutral-500">
                        {w.hours_saved_per_week.toFixed(2)} h/week · {w.occurrences}×
                      </span>
                    </span>
                    <FeasibilityBadge value={w.feasibility} />
                  </button>
                </li>
              )
            })}
          </ul>

          <div className="mt-auto pt-5">
            <button
              onClick={() => nav('/impact')}
              className="w-full rounded-xl border border-neutral-300 px-4 py-3 text-sm font-medium text-neutral-700 hover:bg-white"
            >
              See impact dashboard →
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
