// Discovery hero: an animated bubble map (one bubble per workflow).
//   size  -> hours saved per week
//   color -> feasibility
// Bubbles settle via a lightweight force simulation; hovering syncs with the
// ranked list (via the shared `hovered` id).

import { useMemo } from 'react'
import type { Workflow } from '../types'

interface Positioned extends Workflow {
  x: number
  y: number
  r: number
}

const FEAS_COLOR: Record<string, string> = {
  high: '#10b981',
  medium: '#f59e0b',
  low: '#9ca3af',
}

function hexToRgba(hex: string, alpha: number): string {
  const n = parseInt(hex.slice(1), 16)
  const r = (n >> 16) & 255
  const g = (n >> 8) & 255
  const b = n & 255
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

// Tiny deterministic force simulation: repulsion + weak centering, so bubbles
// spread without overlapping and stay stable across reloads (seeded init).
function layout(
  workflows: Workflow[],
  width: number,
  height: number,
  iterations = 180,
): Positioned[] {
  const maxHours = Math.max(...workflows.map((w) => w.hours_saved_per_week), 0.1)
  const minR = 30
  const maxR = 78

  const nodes = workflows.map((w, i) => {
    const t = w.hours_saved_per_week / maxHours
    const r = minR + Math.sqrt(Math.max(t, 0)) * (maxR - minR)
    // deterministic pseudo-random start on a circle
    const angle = (i / Math.max(workflows.length, 1)) * Math.PI * 2
    return {
      ...w,
      r,
      x: width / 2 + Math.cos(angle) * (width / 4),
      y: height / 2 + Math.sin(angle) * (height / 4),
    }
  })

  for (let it = 0; it < iterations; it++) {
    const alpha = 1 - it / iterations // cooling
    for (let i = 0; i < nodes.length; i++) {
      const a = nodes[i]
      // centering
      a.x += (width / 2 - a.x) * 0.02
      a.y += (height / 2 - a.y) * 0.04
      for (let j = i + 1; j < nodes.length; j++) {
        const b = nodes[j]
        let dx = b.x - a.x
        let dy = b.y - a.y
        let dist = Math.hypot(dx, dy) || 0.01
        const overlap = a.r + b.r + 8 - dist
        if (overlap > 0) {
          const force = overlap * 0.5 * alpha
          const ux = dx / dist
          const uy = dy / dist
          a.x -= ux * force
          a.y -= uy * force
          b.x += ux * force
          b.y += uy * force
        }
      }
    }
    // clamp to bounds with padding
    for (const n of nodes) {
      n.x = Math.min(width - n.r, Math.max(n.r, n.x))
      n.y = Math.min(height - n.r, Math.max(n.r, n.y))
    }
  }
  return nodes
}

export function BubbleMap({
  workflows,
  hovered,
  onHover,
  onSelect,
}: {
  workflows: Workflow[]
  hovered: number | null
  onHover: (id: number | null) => void
  onSelect: (id: number) => void
}) {
  const width = 560
  const height = 440

  const nodes = useMemo(() => layout(workflows, width, height), [workflows])

  return (
    <div
      className="relative h-full w-full"
      onMouseLeave={() => onHover(null)}
      role="group"
      aria-label="Workflow bubble map"
    >
      <svg viewBox={`0 0 ${width} ${height}`} className="h-full w-full">
        {nodes.map((n, i) => {
          const color = FEAS_COLOR[n.feasibility] ?? FEAS_COLOR.low
          const isHover = hovered === n.id
          const delay = i * 90
          return (
            <g
              key={n.id}
              className="bubble-enter"
              style={{ animationDelay: `${delay}ms` }}
              transform={`translate(${n.x} ${n.y})`}
            >
              <circle
                r={n.r}
                fill={hexToRgba(color, isHover ? 0.92 : 0.72)}
                stroke={isHover ? '#111' : color}
                strokeWidth={isHover ? 3 : 2}
                className="cursor-pointer transition-[fill,stroke-width] duration-200"
                tabIndex={0}
                role="button"
                aria-label={`${n.name}, ${n.hours_saved_per_week.toFixed(1)} hours per week`}
                onMouseEnter={() => onHover(n.id)}
                onFocus={() => onHover(n.id)}
                onClick={() => onSelect(n.id)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') onSelect(n.id)
                }}
              />
              <text
                textAnchor="middle"
                className="pointer-events-none select-none"
                fill="#1f2937"
                fontSize={n.r > 46 ? 13 : 11}
                fontWeight={700}
              >
                <tspan y={-4}>{n.hours_saved_per_week.toFixed(1)}h</tspan>
                {n.r > 52 && (
                  <tspan y={12} fontSize={10} fontWeight={500} fill="#4b5563">
                    /wk
                  </tspan>
                )}
              </text>
            </g>
          )
        })}
      </svg>
    </div>
  )
}
