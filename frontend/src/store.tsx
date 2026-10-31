// Small React helpers: a session store for the active upload_id, an async data
// hook with loading/error state, and a toast system.

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import type { ReactNode } from 'react'

// ---------------------------------------------------------------------------
// Session store: the active upload_id (persisted so page reloads keep context)
// ---------------------------------------------------------------------------
interface Session {
  uploadId: number | null
  setUploadId: (id: number | null) => void
}

const SessionContext = createContext<Session | null>(null)
const UPLOAD_KEY = 'autoscout.uploadId'

export function SessionProvider({ children }: { children: ReactNode }) {
  const [uploadId, setUploadIdState] = useState<number | null>(() => {
    const raw = localStorage.getItem(UPLOAD_KEY)
    return raw ? Number(raw) : null
  })

  const setUploadId = useCallback((id: number | null) => {
    if (id == null) localStorage.removeItem(UPLOAD_KEY)
    else localStorage.setItem(UPLOAD_KEY, String(id))
    setUploadIdState(id)
  }, [])

  const value = useMemo(() => ({ uploadId, setUploadId }), [uploadId, setUploadId])
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}

export function useSession(): Session {
  const ctx = useContext(SessionContext)
  if (!ctx) throw new Error('useSession must be used within SessionProvider')
  return ctx
}

// ---------------------------------------------------------------------------
// Async data hook: loading / error / data + reload
// ---------------------------------------------------------------------------
export interface AsyncState<T> {
  data: T | null
  error: string | null
  loading: boolean
  reload: () => void
}

export function useAsync<T>(
  fn: () => Promise<T>,
  deps: unknown[],
  enabled = true,
): AsyncState<T> {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState<boolean>(enabled)
  const [nonce, setNonce] = useState(0)
  const fnRef = useRef(fn)
  fnRef.current = fn

  useEffect(() => {
    if (!enabled) {
      setLoading(false)
      return
    }
    let cancelled = false
    setLoading(true)
    setError(null)
    fnRef
      .current()
      .then((res) => {
        if (!cancelled) {
          setData(res)
          setLoading(false)
        }
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : String(e))
          setLoading(false)
        }
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce, enabled])

  const reload = useCallback(() => setNonce((n) => n + 1), [])
  return { data, error, loading, reload }
}

// ---------------------------------------------------------------------------
// Toasts
// ---------------------------------------------------------------------------
export interface Toast {
  id: number
  kind: 'success' | 'error' | 'info'
  message: string
}

interface ToastStore {
  toasts: Toast[]
  push: (kind: Toast['kind'], message: string) => void
  dismiss: (id: number) => void
}

const ToastContext = createContext<ToastStore | null>(null)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])

  const dismiss = useCallback((id: number) => {
    setToasts((t) => t.filter((x) => x.id !== id))
  }, [])

  const push = useCallback(
    (kind: Toast['kind'], message: string) => {
      const id = Date.now() + Math.random()
      setToasts((t) => [...t, { id, kind, message }])
      window.setTimeout(() => dismiss(id), 5000)
    },
    [dismiss],
  )

  const value = useMemo(() => ({ toasts, push, dismiss }), [toasts, push, dismiss])
  return <ToastContext.Provider value={value}>{children}</ToastContext.Provider>
}

export function useToasts(): ToastStore {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToasts must be used within ToastProvider')
  return ctx
}
