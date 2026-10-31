// Shared presentational primitives: skeletons, toasts, badges, empty states.

import type { ReactNode } from 'react'
import { useToasts } from '../store'

export function Skeleton({ className = '' }: { className?: string }) {
  return (
    <div
      className={`animate-pulse rounded-lg bg-neutral-200/70 ${className}`}
      aria-hidden="true"
    />
  )
}

export function Card({
  children,
  className = '',
  ...rest
}: {
  children: ReactNode
  className?: string
} & React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={`rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm ${className}`}
      {...rest}
    >
      {children}
    </div>
  )
}

const FEASIBILITY_STYLE: Record<string, string> = {
  high: 'bg-emerald-100 text-emerald-700 border-emerald-200',
  medium: 'bg-amber-100 text-amber-700 border-amber-200',
  low: 'bg-neutral-100 text-neutral-600 border-neutral-200',
}

export function FeasibilityBadge({ value }: { value: string }) {
  const cls = FEASIBILITY_STYLE[value] ?? FEASIBILITY_STYLE.low
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium capitalize ${cls}`}
    >
      {value}
    </span>
  )
}

export function StatCard({
  label,
  value,
  sub,
  accent = false,
}: {
  label: string
  value: ReactNode
  sub?: string
  accent?: boolean
}) {
  return (
    <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
      <div className="text-xs font-medium uppercase tracking-wide text-neutral-500">
        {label}
      </div>
      <div
        className={`mt-2 text-3xl font-bold tabular-nums ${
          accent ? 'text-accent' : 'text-neutral-900'
        }`}
      >
        {value}
      </div>
      {sub && <div className="mt-1 text-sm text-neutral-500">{sub}</div>}
    </div>
  )
}

export function EmptyState({
  title,
  hint,
  action,
}: {
  title: string
  hint?: string
  action?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-neutral-300 bg-neutral-50 p-10 text-center">
      <div className="text-base font-semibold text-neutral-700">{title}</div>
      {hint && <div className="mt-1 max-w-md text-sm text-neutral-500">{hint}</div>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

export function Toasts() {
  const { toasts, dismiss } = useToasts()
  if (toasts.length === 0) return null
  const style: Record<string, string> = {
    success: 'border-emerald-300 bg-emerald-50 text-emerald-800',
    error: 'border-red-300 bg-red-50 text-red-800',
    info: 'border-sky-300 bg-sky-50 text-sky-800',
  }
  return (
    <div className="pointer-events-none fixed bottom-5 right-5 z-50 flex w-80 flex-col gap-2">
      {toasts.map((t) => (
        <div
          key={t.id}
          role="status"
          className={`pointer-events-auto flex items-start justify-between gap-3 rounded-xl border px-4 py-3 text-sm shadow-lg ${style[t.kind]}`}
        >
          <span className="break-words">{t.message}</span>
          <button
            onClick={() => dismiss(t.id)}
            className="shrink-0 rounded p-1 text-current/60 hover:bg-black/5"
            aria-label="Dismiss"
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  )
}
