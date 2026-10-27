import { useEffect, useState } from 'react'

type Health = { status: string } | null

export default function App() {
  const [health, setHealth] = useState<Health>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch('/health')
      .then((r) => r.json())
      .then((data: Health) => setHealth(data))
      .catch(() => setError('backend unreachable'))
  }, [])

  return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-4 p-8">
      <div className="text-3xl font-bold tracking-tight">
        Auto<span className="text-accent">Scout</span>
      </div>
      <p className="text-neutral-500 text-sm">
        Find the repetitive work hiding in your files — automate the top one, safely.
      </p>

      <div className="mt-4 rounded-xl border border-neutral-200 bg-white px-5 py-3 shadow-sm text-sm">
        {error && <span className="text-red-500">API: {error}</span>}
        {!error && !health && <span className="text-neutral-400">checking API…</span>}
        {health && (
          <span className="text-neutral-700">
            API <span className="text-accent font-semibold">{health.status}</span>
          </span>
        )}
      </div>
    </div>
  )
}
