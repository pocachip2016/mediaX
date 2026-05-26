"use client"

import { StageEventOut } from "@/lib/api"

interface ThroughputMiniChartProps {
  events: StageEventOut[]
}

export function ThroughputMiniChart({ events }: ThroughputMiniChartProps) {
  const now = Date.now()
  const buckets = 12
  const bucketMs = 60000

  const counts = Array.from({ length: buckets }, (_, i) => {
    const from = now - (buckets - i) * bucketMs
    const to = now - (buckets - i - 1) * bucketMs
    return events.filter((e) => {
      const t = new Date(e.started_at).getTime()
      return t >= from && t < to
    }).length
  })

  const maxCount = Math.max(...counts, 1)

  return (
    <div className="space-y-1">
      <p className="text-xs text-slate-500">스루풋 (분당 이벤트)</p>
      <div className="flex items-end gap-0.5 h-8">
        {counts.map((cnt, i) => (
          <div
            key={i}
            className="flex-1 bg-blue-400 dark:bg-blue-600 rounded-t"
            style={{ height: `${Math.round((cnt / maxCount) * 100)}%`, minHeight: cnt > 0 ? "4px" : "0px" }}
            title={`${cnt}건`}
          />
        ))}
      </div>
      <p className="text-xs text-slate-400 text-right">최근 12분</p>
    </div>
  )
}
