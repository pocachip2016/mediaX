"use client"

import { useEffect, useState, useCallback } from "react"
import { Clock, CheckCircle2, AlertCircle, Play, SkipForward, Layers, RefreshCw } from "lucide-react"
import { cn } from "@workspace/ui/lib/utils"
import { schedulingAutoApi, type AutoStageEventOut, type AutoStage } from "@/lib/api"

const STAGE_LABEL: Record<AutoStage, string> = {
  p1_define:      "P1 조건정의",
  p2_candidate:   "P2 후보생성",
  p3_match:       "P3 AI매칭",
  p4_autoconfirm: "P4 자동확정",
  p5_conflict:    "P5 충돌검사",
  p6_publish:     "P6 발행",
}

const EVENT_ICON: Record<string, React.ReactNode> = {
  entered:   <Clock className="w-3 h-3 text-slate-400" />,
  completed: <CheckCircle2 className="w-3 h-3 text-green-500" />,
  skipped:   <SkipForward className="w-3 h-3 text-orange-400" />,
  failed:    <AlertCircle className="w-3 h-3 text-red-500" />,
  advanced:  <Play className="w-3 h-3 text-blue-500" />,
  rejected:  <AlertCircle className="w-3 h-3 text-red-400" />,
}

interface Props {
  nodeId: number
  /** 외부에서 이미 로드한 이벤트가 있으면 직접 전달. 없으면 내부 폴링. */
  events?: AutoStageEventOut[]
  /** 폴링 간격(ms). 0이면 폴링 안 함. 기본 10000ms */
  pollInterval?: number
  className?: string
}

export function StageEventLog({ nodeId, events: extEvents, pollInterval = 10000, className }: Props) {
  const [events, setEvents] = useState<AutoStageEventOut[]>(extEvents ?? [])
  const [loading, setLoading] = useState(!extEvents)

  const load = useCallback(async () => {
    const data = await schedulingAutoApi.getNodeEvents(nodeId)
    setEvents(data)
    setLoading(false)
  }, [nodeId])

  // extEvents 가 주어지면 외부 상태 동기화
  useEffect(() => {
    if (extEvents) setEvents(extEvents)
  }, [extEvents])

  // 내부 폴링
  useEffect(() => {
    if (extEvents !== undefined) return  // 외부 제어 시 폴링 안 함
    load()
    if (pollInterval <= 0) return
    const id = setInterval(load, pollInterval)
    return () => clearInterval(id)
  }, [nodeId, load, extEvents, pollInterval])

  if (loading) {
    return <p className="text-xs text-gray-400 text-center py-4">로딩 중…</p>
  }
  if (events.length === 0) {
    return <p className="text-xs text-gray-400 text-center py-4">이벤트 없음</p>
  }

  return (
    <ul className={cn("space-y-0.5", className)}>
      {events.map(ev => (
        <li
          key={ev.id}
          className="flex items-start gap-2 text-xs py-1.5 border-b border-gray-100 dark:border-gray-800 last:border-0"
        >
          <span className="mt-0.5 shrink-0">{EVENT_ICON[ev.event_type] ?? <Clock className="w-3 h-3" />}</span>
          <div className="flex-1 min-w-0">
            <span className="font-medium">{STAGE_LABEL[ev.stage] ?? ev.stage}</span>
            <span className="mx-1 text-gray-400">·</span>
            <span className="text-gray-500">{ev.event_type}</span>
            {ev.actor && ev.actor !== "system" && (
              <span className="ml-1 text-gray-400">({ev.actor})</span>
            )}
            {ev.latency_ms != null && (
              <span className="ml-1 text-gray-300 dark:text-gray-600">{ev.latency_ms}ms</span>
            )}
          </div>
          {ev.started_at && (
            <span className="text-gray-400 shrink-0">
              {new Date(ev.started_at).toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
            </span>
          )}
        </li>
      ))}
    </ul>
  )
}

/** 이벤트 로그 카드 래퍼 (제목 + 새로고침 + 스크롤 영역 포함) */
export function StageEventLogCard({ nodeId }: { nodeId: number }) {
  const [events, setEvents] = useState<AutoStageEventOut[]>([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    const data = await schedulingAutoApi.getNodeEvents(nodeId)
    setEvents(data)
    setLoading(false)
  }, [nodeId])

  useEffect(() => { load() }, [load])

  return (
    <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-4">
      <div className="flex items-center gap-2 pb-2 mb-2 border-b border-gray-100 dark:border-gray-800">
        <Layers className="w-3.5 h-3.5 text-gray-400" />
        <span className="text-sm font-medium">단계 이벤트</span>
        <span className="ml-auto text-xs text-gray-400">{events.length}건</span>
        <button
          onClick={load}
          disabled={loading}
          className="text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 disabled:opacity-40"
        >
          <RefreshCw className={cn("w-3 h-3", loading && "animate-spin")} />
        </button>
      </div>
      <div className="max-h-52 overflow-y-auto pr-1">
        <StageEventLog nodeId={nodeId} events={events} pollInterval={0} />
      </div>
    </div>
  )
}
