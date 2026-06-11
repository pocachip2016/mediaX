"use client"

import { useEffect, useRef, useState } from "react"
import { facetApi, type FacetEventOut } from "@/lib/api"
import { Pause, Play } from "lucide-react"

const EVENT_COLOR: Record<string, string> = {
  batch_started: "text-blue-600 dark:text-blue-400",
  batch_done:    "text-blue-600 dark:text-blue-400",
  item_started:  "text-muted-foreground",
  item_success:  "text-green-600 dark:text-green-400",
  item_failed:   "text-red-600 dark:text-red-400",
}

const EVENT_BADGE: Record<string, string> = {
  batch_started: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  batch_done:    "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  item_started:  "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
  item_success:  "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
  item_failed:   "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
}

const MAX_EVENTS = 300

const PROVIDER_LABEL: Record<string, string> = {
  playwright: "namu",
  wikipedia:  "wiki",
  kowiki:     "kowiki",
  omdb:       "omdb",
  tmdb:       "tmdb",
  kmdb:       "kmdb",
}

interface ProviderEntry { p: string; docs: number; eval: boolean }

function ProviderBadges({ detail }: { detail: Record<string, unknown> | null }) {
  const providers = (detail as { providers?: ProviderEntry[] } | null)?.providers
  if (!providers?.length) return null
  return (
    <span className="ml-1.5 inline-flex flex-wrap gap-0.5">
      {providers.map((pr) => {
        const label = PROVIDER_LABEL[pr.p] ?? pr.p
        return pr.eval ? (
          <span key={pr.p} className="px-1 py-0 rounded text-[10px] bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">
            {label}✓
          </span>
        ) : (
          <span key={pr.p} className="px-1 py-0 rounded text-[10px] bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-500">
            {label}·{pr.docs}
          </span>
        )
      })}
    </span>
  )
}

interface FacetEventLogProps {
  runId?: number
  maxHeight?: string
}

export function FacetEventLog({ runId, maxHeight = "400px" }: FacetEventLogProps) {
  const [events, setEvents]   = useState<FacetEventOut[]>([])
  const [isPaused, setIsPaused] = useState(false)
  const cursorRef = useRef(0)
  const listRef   = useRef<HTMLDivElement>(null)
  const isUserScrollingRef = useRef(false)

  const fetchEvents = async () => {
    try {
      const data = await facetApi.getEvents({
        since: cursorRef.current,
        limit: 50,
        ...(runId !== undefined ? { run_id: runId } : {}),
      })
      if (data.items.length > 0) {
        cursorRef.current = data.next_cursor
        setEvents((prev) => {
          const combined = [...data.items, ...prev].slice(0, MAX_EVENTS)
          return combined
        })
        if (!isUserScrollingRef.current && listRef.current) {
          listRef.current.scrollTop = 0
        }
      }
    } catch {
      // 조용히 실패 — 로그 창이 배치를 막으면 안 됨
    }
  }

  // 최초 로드
  useEffect(() => {
    cursorRef.current = 0
    setEvents([])
    fetchEvents()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId])

  // 1s 폴링
  useEffect(() => {
    if (isPaused) return
    const id = setInterval(fetchEvents, 1000)
    return () => clearInterval(id)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isPaused, runId])

  function fmtTime(iso: string) {
    const m = iso.match(/T(\d{2}):(\d{2}):(\d{2})/)
    return m ? `${m[1]}:${m[2]}:${m[3]}` : iso
  }

  return (
    <div className="space-y-2">
      {/* 컨트롤 바 */}
      <div className="flex items-center justify-between">
        <p className="text-xs text-muted-foreground">
          {events.length > 0
            ? `${events.length}건 표시 (최대 ${MAX_EVENTS})`
            : "이벤트 대기 중..."}
        </p>
        <button
          onClick={() => setIsPaused((p) => !p)}
          className="flex items-center gap-1.5 rounded border border-border px-2 py-1 text-xs text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
        >
          {isPaused
            ? <><Play  className="w-3 h-3" />재개</>
            : <><Pause className="w-3 h-3" />일시정지</>}
        </button>
      </div>

      {/* 로그 스크롤 창 */}
      <div
        ref={listRef}
        className="overflow-y-auto rounded-xl border bg-card shadow-sm font-mono text-xs"
        style={{ maxHeight }}
        onScroll={() => { isUserScrollingRef.current = true }}
        onMouseLeave={() => { isUserScrollingRef.current = false }}
      >
        {events.length === 0 ? (
          <div className="px-4 py-8 text-center text-muted-foreground">
            {isPaused ? "일시정지됨" : "이벤트 없음 — 배치 실행 후 수신됩니다."}
          </div>
        ) : (
          <table className="w-full">
            <tbody>
              {events.map((ev, idx) => (
                <tr key={`${ev.id}-${idx}`} className="border-b border-border/50 hover:bg-muted/50 transition-colors">
                  <td className="px-3 py-1.5 text-muted-foreground w-8 tabular-nums">{ev.id}</td>
                  <td className="px-2 py-1.5 text-muted-foreground w-20 tabular-nums">{fmtTime(ev.created_at)}</td>
                  <td className="px-2 py-1.5 w-28">
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${EVENT_BADGE[ev.event_type] ?? "bg-gray-100 text-gray-600"}`}>
                      {ev.event_type}
                    </span>
                  </td>
                  <td className="px-2 py-1.5 text-muted-foreground w-14 tabular-nums">
                    {ev.content_id != null ? `#${ev.content_id}` : ""}
                  </td>
                  <td className={`px-2 py-1.5 ${EVENT_COLOR[ev.event_type] ?? ""}`}>
                    <span className="inline-flex flex-wrap items-center gap-0.5">
                      {ev.message ?? ""}
                      <ProviderBadges detail={ev.detail} />
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <p className="text-[10px] text-muted-foreground text-right">
        {isPaused ? "⏸ 일시정지됨" : "↻ 2초 간격 갱신"}
      </p>
    </div>
  )
}
