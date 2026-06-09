"use client"

import { useEffect, useState } from "react"
import { CornerUpLeft, Pin } from "lucide-react"
import { schedulingApi } from "@/lib/api"
import type { BackrefOut, ProgrammingNode } from "@/lib/api"
import { cn } from "@workspace/ui/lib/utils"

type Props = {
  node: ProgrammingNode | null
}

const STATUS_LABEL: Record<string, string> = {
  active: "활성",
  suggested: "추천",
  rejected: "거절",
}

const STATUS_COLOR: Record<string, string> = {
  active: "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-400",
  suggested: "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400",
  rejected: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400",
}

function formatDateRange(start: string | null, end: string | null): string | null {
  if (!start && !end) return null
  if (start && end) return `${start} ~ ${end}`
  if (start) return `${start} 이후`
  return `${end} 까지`
}

export function BackrefList({ node }: Props) {
  const [refs, setRefs] = useState<BackrefOut[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!node) {
      setRefs([])
      return
    }
    setLoading(true)
    schedulingApi
      .getNodeBackrefs(node.id)
      .then(setRefs)
      .catch(() => setRefs([]))
      .finally(() => setLoading(false))
  }, [node?.id])

  if (!node) return null

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <p className="text-xs text-muted-foreground">로딩 중…</p>
      </div>
    )
  }

  if (refs.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-8 gap-1">
        <CornerUpLeft className="h-4 w-4 text-muted-foreground/50" />
        <p className="text-xs text-muted-foreground">등장 위치 없음</p>
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto p-3 space-y-2">
      <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
        등장 노드 ({refs.length})
      </p>
      {refs.map((ref) => {
        const dateRange = formatDateRange(ref.window_start, ref.window_end)
        return (
          <div
            key={ref.link_id}
            className="rounded-lg border bg-muted/30 px-3 py-2 space-y-1"
          >
            <div className="flex items-start justify-between gap-2">
              <span className="text-xs font-medium truncate flex-1">{ref.parent_node_name}</span>
              <span
                className={cn(
                  "text-[10px] px-1.5 py-0.5 rounded-full font-medium flex-shrink-0",
                  STATUS_COLOR[ref.status] ?? "bg-muted text-muted-foreground"
                )}
              >
                {STATUS_LABEL[ref.status] ?? ref.status}
              </span>
            </div>
            <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
              <span>{ref.source === "ai" ? "AI" : ref.source === "rule" ? "규칙" : "수동"}</span>
              <span>순서 {ref.sort_order + 1}</span>
              {ref.is_pinned && (
                <span className="flex items-center gap-0.5 text-amber-500">
                  <Pin className="h-2.5 w-2.5" />
                  고정
                </span>
              )}
            </div>
            {dateRange && (
              <p className="text-[10px] text-muted-foreground">{dateRange}</p>
            )}
          </div>
        )
      })}
    </div>
  )
}
