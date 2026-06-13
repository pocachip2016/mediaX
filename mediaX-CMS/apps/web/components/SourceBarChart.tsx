import React from "react"

export interface BarChartData {
  date: string
  movies?: number
  tv?: number
  count?: number
  errors?: number
}

interface SourceBarChartProps {
  data: BarChartData[]
  title?: string
  showLegend?: boolean
}

export function SourceBarChart({ data, title = "최근 7일 수집량", showLegend = true }: SourceBarChartProps) {
  const isTmdb = data.some(d => d.movies !== undefined || d.tv !== undefined)
  const max = Math.max(...data.map(d => {
    if (isTmdb) return (d.movies ?? 0) + (d.tv ?? 0)
    return d.count ?? 0
  }), 1)

  return (
    <div className="rounded-xl border bg-card p-4 shadow-sm">
      <p className="text-sm font-medium mb-4">{title}</p>
      <div className="flex items-end gap-2 h-32">
        {data.map(d => {
          const label = d.date.slice(5)
          if (isTmdb) {
            const movies = d.movies ?? 0
            const tv = d.tv ?? 0
            const total = movies + tv
            const moviePct = (movies / max) * 100
            const tvPct = (tv / max) * 100
            return (
              <div key={d.date} className="flex-1 flex flex-col items-center gap-1 h-full justify-end">
                <span className="text-xs text-muted-foreground tabular-nums">{total > 0 ? total : ""}</span>
                <div className="w-full flex flex-col justify-end gap-px" style={{ height: "80%" }}>
                  <div className="w-full bg-blue-400/80 dark:bg-blue-500/70 rounded-sm transition-all" style={{ height: `${tvPct}%` }} />
                  <div className="w-full bg-primary/70 rounded-sm transition-all" style={{ height: `${moviePct}%` }} />
                </div>
                <span className="text-[10px] text-muted-foreground">{label}</span>
              </div>
            )
          }
          const count = d.count ?? 0
          const pct = (count / max) * 100
          return (
            <div key={d.date} className="flex-1 flex flex-col items-center gap-1 h-full justify-end">
              <span className="text-xs text-muted-foreground tabular-nums">{count > 0 ? count : ""}</span>
              <div className="w-full flex flex-col justify-end gap-px" style={{ height: "80%" }}>
                <div className="w-full bg-primary/70 rounded-sm transition-all" style={{ height: `${pct}%` }} />
              </div>
              <span className="text-[10px] text-muted-foreground">{label}</span>
            </div>
          )
        })}
      </div>
      {showLegend && isTmdb && (
        <div className="flex items-center gap-4 mt-3">
          <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <span className="inline-block w-3 h-2 rounded-sm bg-primary/70" />영화
          </span>
          <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <span className="inline-block w-3 h-2 rounded-sm bg-blue-400/80 dark:bg-blue-500/70" />TV
          </span>
        </div>
      )}
    </div>
  )
}
