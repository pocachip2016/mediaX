"use client"

import { pipelineApi, StageEventOut } from "@/lib/api"
import { useEffect, useRef, useState } from "react"
import { StageEventFilters } from "./StageEventFilters"
import { ThroughputMiniChart } from "./ThroughputMiniChart"

const EVENT_TYPE_COLOR: Record<string, string> = {
  ENTERED: "text-blue-600 dark:text-blue-400",
  COMPLETED: "text-green-600 dark:text-green-400",
  SKIPPED: "text-gray-500 dark:text-gray-400",
  FAILED: "text-red-600 dark:text-red-400",
  ADVANCED: "text-purple-600 dark:text-purple-400",
}

interface StageEventStreamProps {
  initialLimit?: number
}

export function StageEventStream({ initialLimit = 100 }: StageEventStreamProps) {
  const [events, setEvents] = useState<StageEventOut[]>([])
  const [isPaused, setIsPaused] = useState(false)
  const [cursor, setCursor] = useState(0)

  const [stageFilter, setStageFilter] = useState("")
  const [sourceFilter, setSourceFilter] = useState("")
  const [eventTypeFilter, setEventTypeFilter] = useState("")

  const listRef = useRef<HTMLDivElement>(null)
  const isUserScrolling = useRef(false)

  const fetchEvents = async () => {
    try {
      const data = await pipelineApi.getEvents({
        since: cursor,
        limit: initialLimit,
        ...(stageFilter ? { stage: stageFilter } : {}),
        ...(sourceFilter ? { source: sourceFilter } : {}),
        ...(eventTypeFilter ? { event_type: eventTypeFilter } : {}),
      })
      if (data.items.length > 0) {
        const lastId = data.items.at(-1)?.id ?? cursor
        setCursor(lastId)
        setEvents((prev) => {
          const combined = [...data.items, ...prev].slice(0, 500)
          return combined
        })
        if (!isUserScrolling.current && listRef.current) {
          listRef.current.scrollTop = 0
        }
      }
    } catch (err) {
      console.error("Event stream fetch error:", err)
    }
  }

  useEffect(() => {
    fetchEvents()
  }, [stageFilter, sourceFilter, eventTypeFilter])

  useEffect(() => {
    if (isPaused) return
    const interval = setInterval(fetchEvents, 2000)
    return () => clearInterval(interval)
  }, [isPaused, cursor, stageFilter, sourceFilter, eventTypeFilter])

  const exportCSV = () => {
    const headers = "id,content_id,stage,event_type,source,started_at,actor,latency_ms,error_text"
    const rows = events.map((e) =>
      [e.id, e.content_id, e.stage, e.event_type, e.source ?? "", e.started_at, e.actor, e.latency_ms ?? "", e.error_text ?? ""].join(",")
    )
    const csv = [headers, ...rows].join("\n")
    const blob = new Blob([csv], { type: "text/csv" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `pipeline-events-${Date.now()}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-3">
      {/* 필터 + 액션 */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <StageEventFilters
          stage={stageFilter}
          source={sourceFilter}
          eventType={eventTypeFilter}
          onStageChange={(v) => { setStageFilter(v); setCursor(0); setEvents([]) }}
          onSourceChange={(v) => { setSourceFilter(v); setCursor(0); setEvents([]) }}
          onEventTypeChange={(v) => { setEventTypeFilter(v); setCursor(0); setEvents([]) }}
        />
        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsPaused(!isPaused)}
            className="rounded border border-slate-300 px-2 py-1 text-xs hover:bg-slate-100 dark:border-slate-600 dark:hover:bg-slate-800"
          >
            {isPaused ? "▶ 재개" : "⏸ 일시정지"}
          </button>
          <button
            onClick={exportCSV}
            className="rounded border border-slate-300 px-2 py-1 text-xs hover:bg-slate-100 dark:border-slate-600 dark:hover:bg-slate-800"
          >
            ↓ CSV
          </button>
        </div>
      </div>

      {/* 스루풋 차트 */}
      <ThroughputMiniChart events={events} />

      {/* 이벤트 스트림 */}
      <div
        ref={listRef}
        className="max-h-[600px] overflow-y-auto rounded border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-900"
        onScroll={() => { isUserScrolling.current = true }}
      >
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-slate-50 dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700">
            <tr>
              <th className="px-2 py-1 text-left text-slate-500 w-12">ID</th>
              <th className="px-2 py-1 text-left text-slate-500 w-16">시각</th>
              <th className="px-2 py-1 text-left text-slate-500 w-12">콘텐츠</th>
              <th className="px-2 py-1 text-left text-slate-500">Stage</th>
              <th className="px-2 py-1 text-left text-slate-500 w-24">이벤트</th>
              <th className="px-2 py-1 text-left text-slate-500 w-20">Source</th>
              <th className="px-2 py-1 text-left text-slate-500 w-16">지연</th>
              <th className="px-2 py-1 text-left text-slate-500">에러</th>
            </tr>
          </thead>
          <tbody>
            {events.length === 0 ? (
              <tr><td colSpan={8} className="px-2 py-4 text-center text-slate-400">이벤트 없음</td></tr>
            ) : (
              events.map((ev, idx) => (
                <tr key={`${ev.id}-${idx}`} className="border-b border-slate-100 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/50">
                  <td className="px-2 py-1 text-slate-400 font-mono">{ev.id}</td>
                  <td className="px-2 py-1 text-slate-500 font-mono">
                    {new Date(ev.started_at).toLocaleTimeString("ko-KR", { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" })}
                  </td>
                  <td className="px-2 py-1 text-slate-600 dark:text-slate-300 font-mono">#{ev.content_id}</td>
                  <td className="px-2 py-1 text-slate-500">{ev.stage}</td>
                  <td className={`px-2 py-1 font-medium ${EVENT_TYPE_COLOR[ev.event_type] ?? ""}`}>{ev.event_type}</td>
                  <td className="px-2 py-1 text-slate-500">{ev.source ?? "-"}</td>
                  <td className="px-2 py-1 text-slate-400">{ev.latency_ms != null ? `${ev.latency_ms}ms` : "-"}</td>
                  <td className="px-2 py-1 text-red-500 text-xs truncate max-w-xs">{ev.error_text ?? ""}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <p className="text-xs text-slate-400 text-right">최대 500건 표시 · {isPaused ? "일시정지됨" : "2초 간격 갱신"}</p>
    </div>
  )
}
