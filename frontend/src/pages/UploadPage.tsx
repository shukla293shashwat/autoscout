// Screen 1 — Upload: drag-and-drop / sample data, then discover workflows.

import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { Card } from '../components/ui'
import { useSession, useToasts } from '../store'
import type { UploadResponse } from '../types'

const DISCOVER_STEPS = ['Reading', 'Embedding', 'Clustering', 'Naming patterns']

const KIND_ICON: Record<string, string> = {
  email: '✉️',
  lead: '📊',
  note: '📝',
  task: '☑️',
}

export function UploadPage() {
  const nav = useNavigate()
  const { setUploadId } = useSession()
  const { push } = useToasts()
  const fileRef = useRef<HTMLInputElement>(null)

  const [upload, setUpload] = useState<UploadResponse | null>(null)
  const [busy, setBusy] = useState<'upload' | 'discover' | null>(null)
  const [dragging, setDragging] = useState(false)
  const [discoverStep, setDiscoverStep] = useState(0)

  const counts = upload ? Object.entries(upload.counts) : []

  async function handleSample() {
    setBusy('upload')
    try {
      const res = await api.uploadSample()
      setUpload(res)
      setUploadId(res.upload_id)
      push('success', 'Sample data loaded.')
    } catch (e) {
      push('error', e instanceof Error ? e.message : 'Failed to load sample')
    } finally {
      setBusy(null)
    }
  }

  async function handleFiles(files: FileList | null) {
    if (!files || files.length === 0) return
    setBusy('upload')
    try {
      const res = await api.uploadFiles(Array.from(files))
      setUpload(res)
      setUploadId(res.upload_id)
      push('success', `Loaded ${res.upload_id} upload.`)
    } catch (e) {
      push('error', e instanceof Error ? e.message : 'Upload failed')
    } finally {
      setBusy(null)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  async function handleDiscover() {
    if (!upload) return
    setBusy('discover')
    try {
      // Animate through the pipeline stages while the request runs.
      for (let i = 0; i < DISCOVER_STEPS.length; i++) {
        setDiscoverStep(i + 1)
        await new Promise((r) => setTimeout(r, 350))
      }
      const res = await api.discover(upload.upload_id)
      push('success', `Found ${res.count} repetitive workflows.`)
      nav('/discovery')
    } catch (e) {
      push('error', e instanceof Error ? e.message : 'Discovery failed')
    } finally {
      setBusy(null)
      setDiscoverStep(0)
    }
  }

  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-8 text-center">
        <h1 className="text-3xl font-bold tracking-tight text-neutral-900">
          Turn a messy week into a plan
        </h1>
        <p className="mt-2 text-neutral-500">
          Drop in your emails, spreadsheets, and meeting notes. AutoScout finds the repetitive
          work hiding in them — then automates the top one, safely.
        </p>
      </div>

      {!upload ? (
        <>
          <div
            onDragOver={(e) => {
              e.preventDefault()
              setDragging(true)
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault()
              setDragging(false)
              void handleFiles(e.dataTransfer.files)
            }}
            className={`flex h-56 flex-col items-center justify-center rounded-3xl border-2 border-dashed transition ${
              dragging
                ? 'border-accent bg-accent/5'
                : 'border-neutral-300 bg-white hover:border-neutral-400'
            }`}
          >
            <div className="text-4xl">📂</div>
            <div className="mt-3 font-medium text-neutral-700">
              Drag & drop files here
            </div>
            <div className="mt-1 text-sm text-neutral-500">CSV or TXT, up to several files</div>
            <button
              onClick={() => fileRef.current?.click()}
              disabled={busy === 'upload'}
              className="mt-4 rounded-lg border border-neutral-300 px-4 py-2 text-sm font-medium text-neutral-700 hover:bg-neutral-50 disabled:opacity-50"
            >
              {busy === 'upload' ? 'Uploading…' : 'Browse files'}
            </button>
            <input
              ref={fileRef}
              type="file"
              multiple
              accept=".csv,.txt"
              className="hidden"
              onChange={(e) => void handleFiles(e.target.files)}
            />
          </div>

          <div className="my-6 flex items-center gap-4" aria-hidden="true">
            <div className="h-px flex-1 bg-neutral-200" />
            <span className="text-xs uppercase tracking-wide text-neutral-400">or</span>
            <div className="h-px flex-1 bg-neutral-200" />
          </div>

          <button
            onClick={() => void handleSample()}
            disabled={busy === 'upload'}
            className="w-full rounded-2xl bg-accent px-6 py-4 text-center font-semibold text-white shadow-sm transition hover:bg-accent-dark disabled:opacity-60"
          >
            {busy === 'upload' ? 'Loading sample data…' : '▶  Try sample data'}
          </button>
        </>
      ) : (
        <Card>
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-neutral-900">Ingested</h2>
            <button
              onClick={() => setUpload(null)}
              className="text-sm text-neutral-500 hover:text-neutral-800"
            >
              Clear
            </button>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {counts.map(([kind, n]) => (
              <div
                key={kind}
                className="flex items-center gap-3 rounded-xl border border-neutral-200 p-4"
              >
                <span className="text-2xl">{KIND_ICON[kind] ?? '📄'}</span>
                <div>
                  <div className="text-xl font-bold tabular-nums">{n}</div>
                  <div className="text-xs capitalize text-neutral-500">{kind}s</div>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-6">
            <button
              onClick={() => void handleDiscover()}
              disabled={busy === 'discover'}
              className="w-full rounded-xl bg-neutral-900 px-5 py-3.5 font-semibold text-white transition hover:bg-neutral-800 disabled:opacity-60"
            >
              {busy === 'discover' ? 'Discovering…' : '🔍  Discover workflows'}
            </button>

            {busy === 'discover' && (
              <ol className="mt-4 space-y-2" aria-live="polite">
                {DISCOVER_STEPS.map((s, i) => {
                  const state = discoverStep > i ? 'done' : 'active'
                  return (
                    <li
                      key={s}
                      className={`flex items-center gap-3 text-sm ${
                        state === 'done' ? 'text-emerald-600' : 'text-neutral-700'
                      }`}
                    >
                      <span
                        className={`grid h-5 w-5 place-items-center rounded-full text-[11px] ${
                          state === 'done'
                            ? 'bg-emerald-500 text-white'
                            : 'bg-accent text-white animate-pulse'
                        }`}
                      >
                        {state === 'done' ? '✓' : i + 1}
                      </span>
                      {s}
                    </li>
                  )
                })}
              </ol>
            )}
          </div>
        </Card>
      )}
    </div>
  )
}
