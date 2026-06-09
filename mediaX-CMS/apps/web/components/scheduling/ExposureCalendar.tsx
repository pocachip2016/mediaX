"use client"

import { useEffect, useMemo, useState } from "react"
import { AlertTriangle } from "lucide-react"
import { schedulingApi } from "@/lib/api"
import type { GraphEdge, ProgrammingNode } from "@/lib/api"
import { cn } from "@workspace/ui/lib/utils"

type Props = {
  setId: number
}

type NodeRow = {
  node: ProgrammingNode
  /** active 엣지 중 window 있는 것만 */
  windows: { start: Date; end: Date; linkId: number }[]
}

function parseDate(s: string | null): Date | null {
  if (!s) return null
  const d = new Date(s)
  return isNaN(d.getTime()) ? null : d
}

function buildRows(nodes: ProgrammingNode[], edges: GraphEdge[]): NodeRow[] {
  const activeEdges = edges.filter((e) => e.status === "active")
  return nodes.map((node) => {
    const nodeEdges = activeEdges.filter((e) => e.parent_node_id === node.id)
    const windows = nodeEdges
      .map((e) => {
        const start = parseDate(e.window_start)
        const end = parseDate(e.window_end)
        if (!start || !end) return null
        return { start, end, linkId: e.link_id }
      })
      .filter((w): w is { start: Date; end: Date; linkId: number } => w !== null)
    return { node, windows }
  })
}

/** 같은 노드 내 window 쌍 중 겹치는 수 반환 */
function countConflicts(windows: { start: Date; end: Date }[]): number {
  let count = 0
  for (let i = 0; i < windows.length; i++) {
    for (let j = i + 1; j < windows.length; j++) {
      const a = windows[i]!
      const b = windows[j]!
      if (a.start < b.end && b.start < a.end) count++
    }
  }
  return count
}

function addDays(d: Date, n: number): Date {
  const r = new Date(d)
  r.setDate(r.getDate() + n)
  return r
}

function formatMD(d: Date): string {
  return `${d.getMonth() + 1}/${d.getDate()}`
}

const DAY_PX = 20

export function ExposureCalendar({ setId }: Props) {
  const [nodes, setNodes] = useState<ProgrammingNode[]>([])
  const [edges, setEdges] = useState<GraphEdge[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setLoading(true)
    schedulingApi
      .getSetGraph(setId)
      .then((g) => {
        setNodes(g.nodes)
        setEdges(g.edges)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [setId])

  const rows = useMemo(() => buildRows(nodes, edges), [nodes, edges])

  const { minDate, maxDate, totalDays } = useMemo(() => {
    const allDates = rows.flatMap((r) => r.windows.flatMap((w) => [w.start, w.end]))
    if (allDates.length === 0) return { minDate: null, maxDate: null, totalDays: 0 }
    const minDate = new Date(Math.min(...allDates.map((d) => d.getTime())))
    const maxDate = new Date(Math.max(...allDates.map((d) => d.getTime())))
    const totalDays = Math.ceil((maxDate.getTime() - minDate.getTime()) / 86400000) + 1
    return { minDate, maxDate, totalDays }
  }, [rows])

  const totalConflicts = useMemo(
    () => rows.reduce((sum, r) => sum + countConflicts(r.windows), 0),
    [rows]
  )

  const hasWindows = rows.some((r) => r.windows.length > 0)

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center border rounded-xl bg-card">
        <p className="text-sm text-muted-foreground">로딩 중…</p>
      </div>
    )
  }

  if (!hasWindows) {
    return (
      <div className="h-full flex flex-col items-center justify-center border rounded-xl bg-card gap-2">
        <CalendarEmpty />
        <p className="text-sm text-muted-foreground">window 설정된 링크 없음</p>
        <p className="text-xs text-muted-foreground">링크에 window_start/window_end를 지정하면 여기에 표시됩니다.</p>
      </div>
    )
  }

  const canvasWidth = totalDays * DAY_PX

  return (
    <div className="h-full flex flex-col border rounded-xl bg-card overflow-hidden">
      {/* 헤더 */}
      <div className="px-4 py-3 border-b flex items-center gap-3 flex-shrink-0">
        <p className="text-sm font-semibold">노출 캘린더</p>
        {totalConflicts > 0 && (
          <span className="flex items-center gap-1 text-xs text-red-600 bg-red-50 dark:bg-red-950/40 px-2 py-0.5 rounded-full">
            <AlertTriangle className="h-3 w-3" />
            충돌 {totalConflicts}건
          </span>
        )}
        {totalConflicts === 0 && (
          <span className="text-xs text-green-600">충돌 없음</span>
        )}
      </div>

      {/* 스크롤 영역 */}
      <div className="flex-1 overflow-auto">
        <div className="min-w-max">
          {/* 날짜 축 */}
          <div className="flex sticky top-0 bg-card z-10 border-b">
            <div className="w-40 flex-shrink-0 px-3 py-2 text-xs text-muted-foreground font-medium border-r">
              노드
            </div>
            <div className="relative" style={{ width: canvasWidth }}>
              {minDate &&
                Array.from({ length: Math.ceil(totalDays / 7) }, (_, i) => {
                  const d = addDays(minDate, i * 7)
                  return (
                    <span
                      key={i}
                      className="absolute top-1/2 -translate-y-1/2 text-[10px] text-muted-foreground"
                      style={{ left: i * 7 * DAY_PX + 2 }}
                    >
                      {formatMD(d)}
                    </span>
                  )
                })}
            </div>
          </div>

          {/* 행 */}
          {rows.map((row) => {
            const conflicts = countConflicts(row.windows)
            return (
              <div key={row.node.id} className="flex border-b last:border-b-0 hover:bg-muted/20">
                <div className="w-40 flex-shrink-0 px-3 py-2 border-r">
                  <p className="text-xs font-medium truncate">{row.node.name}</p>
                  {conflicts > 0 && (
                    <p className="text-[10px] text-red-500">충돌 {conflicts}</p>
                  )}
                </div>
                <div className="relative" style={{ width: canvasWidth, height: 36 }}>
                  {/* 주 구분선 */}
                  {minDate &&
                    Array.from({ length: Math.ceil(totalDays / 7) }, (_, i) => (
                      <div
                        key={i}
                        className="absolute top-0 bottom-0 border-l border-border/30"
                        style={{ left: i * 7 * DAY_PX }}
                      />
                    ))}
                  {/* window 막대 */}
                  {minDate &&
                    row.windows.map((w, idx) => {
                      const offsetDays = (w.start.getTime() - minDate.getTime()) / 86400000
                      const spanDays = Math.max(
                        1,
                        (w.end.getTime() - w.start.getTime()) / 86400000 + 1
                      )
                      // 충돌 여부: 현재 window가 같은 행의 다른 window와 겹치면 빨강
                      const hasConflict = row.windows.some((other, oi) => {
                        if (oi === idx) return false
                        return w.start < other.end && other.start < w.end
                      })
                      return (
                        <div
                          key={w.linkId}
                          title={`${w.start.toLocaleDateString()} ~ ${w.end.toLocaleDateString()}`}
                          className={cn(
                            "absolute top-1/2 -translate-y-1/2 h-5 rounded text-[10px] flex items-center px-1 truncate",
                            hasConflict
                              ? "bg-red-400 text-white"
                              : "bg-blue-400 dark:bg-blue-600 text-white"
                          )}
                          style={{
                            left: offsetDays * DAY_PX,
                            width: spanDays * DAY_PX - 2,
                          }}
                        />
                      )
                    })}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

function CalendarEmpty() {
  return (
    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-muted-foreground/40">
      <rect x="3" y="4" width="18" height="18" rx="2" />
      <path d="M16 2v4M8 2v4M3 10h18" />
    </svg>
  )
}
