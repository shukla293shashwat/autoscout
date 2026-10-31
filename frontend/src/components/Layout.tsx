// Slim top navigation with a 4-step progress indicator.

import { NavLink, useLocation } from 'react-router-dom'

const STEPS = [
  { to: '/', label: 'Upload', n: 1 },
  { to: '/discovery', label: 'Discovery', n: 2 },
  { to: '/impact', label: 'Impact', n: 3 },
]

// The detail page is a sub-view of Discovery.
function activeIndex(pathname: string): number {
  if (pathname.startsWith('/workflow')) return 2
  if (pathname.startsWith('/discovery')) return 2
  if (pathname.startsWith('/impact')) return 3
  return 1
}

export function Layout({ children }: { children: React.ReactNode }) {
  const { pathname } = useLocation()
  const active = activeIndex(pathname)

  return (
    <div className="min-h-screen bg-neutral-50">
      <header className="sticky top-0 z-40 border-b border-neutral-200 bg-white/85 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-5">
          <NavLink to="/" className="flex items-center gap-2 font-semibold tracking-tight">
            <span className="grid h-7 w-7 place-items-center rounded-lg bg-accent text-sm font-bold text-white">
              A
            </span>
            <span className="text-neutral-900">
              Auto<span className="text-accent">Scout</span>
            </span>
          </NavLink>

          <nav aria-label="Steps" className="flex items-center gap-1 text-sm">
            {STEPS.map((s) => {
              const state = active > s.n ? 'done' : active === s.n ? 'current' : 'todo'
              return (
                <NavLink
                  key={s.n}
                  to={s.to}
                  className="group flex items-center gap-2 rounded-full px-3 py-1.5 transition hover:bg-neutral-100"
                >
                  <span
                    className={`grid h-5 w-5 place-items-center rounded-full text-[11px] font-semibold ${
                      state === 'current'
                        ? 'bg-accent text-white'
                        : state === 'done'
                          ? 'bg-emerald-500 text-white'
                          : 'bg-neutral-200 text-neutral-500'
                    }`}
                    aria-hidden="true"
                  >
                    {state === 'done' ? '✓' : s.n}
                  </span>
                  <span
                    className={
                      state === 'current'
                        ? 'font-medium text-neutral-900'
                        : 'text-neutral-500 group-hover:text-neutral-800'
                    }
                  >
                    {s.label}
                  </span>
                </NavLink>
              )
            })}
          </nav>

          <NavLink
            to="/"
            className="rounded-lg border border-neutral-200 px-3 py-1.5 text-xs font-medium text-neutral-600 hover:bg-neutral-100"
          >
            Reset demo
          </NavLink>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-5 py-8">{children}</main>
    </div>
  )
}
