"use client"

import { pipelineApi, StageEventOut } from "@/lib/api"
import { useEffect, useState } from "react"
import { Skeleton } from "@workspace/ui/components/skeleton"

const EVENT_TYPE_COLOR: Record<string, string> = {
  ENTERED: "text-blue-600 dark:text-blue-400",
  COMPLETED: "text-green-600 dark:text-green-400",
  SKIPPED: "text-gray-500 dark:text-gray-400",
  FAILED: "text-red-600 dark:text-red-400",
  ADVANCED: "text-purple-600 dark:text-purple-400",
}

export function LiveEventLog() {
  const [events, setEvents] = useState<StageEventOut[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isPaused, setIsPaused] = useState(false)
  const [lastCursor, setLastCursor] = useState(0)

  const fetchEvents = async () => {
    try {
      const data = await pipelineApi.getEvents({ since: lastCursor, limit: 20 })
      setEvents(data.items)
      const last = data.items.at(-1)
      if (last) {
        setLastCursor(last.id)
      }
      setIsLoading(false)
    } catch (err) {
      console.error("Failed to fetch events:", err)
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchEvents()
  }, [])

  useEffect(() => {
    if (isPaused) return
    const interval = setInterval(fetchEvents, 3000)
    return () => clearInterval(interval)
  }, [isPaused, lastCursor])

  if (isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-6 w-full" />
        ))}
      </div>
    )
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between border-b border-slate-200 pb-2 dark:border-slate-700">
        <span className="text-xs font-medium text-slate-600 dark:text-slate-400">최근 이벤트 {events.length}건</span>
        <button
          onClick={() => setIsPaused(!isPaused)}
          className="rounded px-2 py-0.5 text-xs hover:bg-slate-100 dark:hover:bg-slate-800"
        >
          {isPaused ? "재개" : "일시정지"}
        </button>
      </div>

      <div className="space-y-1 max-h-96 overflow-y-auto">
        {events.length === 0 ? (
          <div className="text-center py-4 text-xs text-slate-400">이벤트 없음</div>
        ) : (
          events.map((ev) => (
            <div key={ev.id} className="text-xs text-slate-600 dark:text-slate-300 font-mono">
              <span className="text-slate-400">
                {new Date(ev.started_at).toLocaleTimeString("ko-KR", { hour12: false })}
              </span>
              {" "}
              <span className="font-semibold">#{ev.content_id}</span>
              {" "}
              <span className="text-slate-500">{ev.stage}</span>
              {" "}
              <span className={EVENT_TYPE_COLOR[ev.event_type] || "text-slate-600"}>
                {ev.event_type}
              </span>
              {ev.source && (
                <>
                  {" "}
                  <span className="text-slate-500">{ev.source}</span>
                  {ev.latency_ms && (
                    <>
                      {" "}
                      <span className="text-slate-400">{ev.latency_ms}ms</span>
                    </>
                  )}
                </>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  )
}
