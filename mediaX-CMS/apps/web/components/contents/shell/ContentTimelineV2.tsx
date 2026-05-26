"use client"

import { metadataApi, StageOut, StageSourceOut } from "@/lib/api"
import { useEffect, useState } from "react"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@workspace/ui/components/collapsible"

const STAGE_NAMES: Record<string, string> = {
  s1_intake: "S1 입수",
  s2_normalize: "S2 정규화",
  s3_llm_extract: "S3 LLM 추출",
  s4_source_match: "S4 소스 매칭",
  s5_gap_detect: "S5 갭 감지",
  s6_websearch_fill: "S6 웹서치",
  s7_staging: "S7 스테이징",
  s8_review: "S8 검수",
  s9_publish: "S9 게시",
}

const STATUS_ICON: Record<string, string> = {
  done: "●",
  active: "◐",
  pending: "○",
  error: "⚠",
  failed: "⛔",
  skipped: "⏭",
  retrying: "↻",
}

const STATUS_COLOR: Record<string, string> = {
  done: "text-green-600 dark:text-green-400",
  active: "text-blue-600 dark:text-blue-400",
  pending: "text-slate-400",
  error: "text-red-600 dark:text-red-400",
  failed: "text-red-700 dark:text-red-500",
  skipped: "text-slate-500",
}

const SOURCE_RESULT_ICON: Record<string, string> = {
  hit: "✓",
  ok: "✓",
  miss: "✗",
  error: "⚠",
  skipped: "⏭",
  pending: "…",
}

function SourceRow({ src, isLast }: { src: StageSourceOut; isLast: boolean }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="ml-4 text-xs text-slate-600 dark:text-slate-400 font-mono">
      <button onClick={() => setOpen(!open)} className="flex items-center gap-1 hover:text-slate-900 dark:hover:text-slate-100">
        <span>{isLast ? "└" : "├"}</span>
        <span>{src.source}</span>
        <span className={
          src.result === "ok" || src.result === "hit" ? "text-green-500" :
          src.result === "miss" || src.result === "skipped" ? "text-slate-400" :
          "text-red-500"
        }>
          {SOURCE_RESULT_ICON[src.result] ?? "?"}
        </span>
        {src.latency_ms && <span className="text-slate-400">{src.latency_ms}ms</span>}
        {src.detail && <span className="text-slate-400">{open ? "▲" : "▼"}</span>}
      </button>
      {open && src.detail && (
        <div className="ml-5 mt-1 rounded bg-slate-100 dark:bg-slate-800 p-2 text-xs overflow-x-auto">
          <pre className="whitespace-pre-wrap">{JSON.stringify(src.detail, null, 2)}</pre>
        </div>
      )}
    </div>
  )
}

function StageRow({ stage }: { stage: StageOut }) {
  const [open, setOpen] = useState(false)
  const icon = STATUS_ICON[stage.status] ?? "○"
  const colorClass = STATUS_COLOR[stage.status] ?? "text-slate-400"
  const name = STAGE_NAMES[stage.stage] ?? stage.stage

  return (
    <div className="space-y-0.5">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 w-full text-left hover:bg-slate-50 dark:hover:bg-slate-800 rounded px-1 py-0.5"
      >
        <span className={`text-xs font-mono ${colorClass}`}>{icon}</span>
        <span className="text-xs font-medium flex-1">{name}</span>
        {stage.at && (
          <span className="text-xs text-slate-400">
            {new Date(stage.at).toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit", hour12: false })}
          </span>
        )}
        {stage.duration_ms && (
          <span className="text-xs text-slate-400">{(stage.duration_ms / 1000).toFixed(1)}s</span>
        )}
        {stage.sources.length > 0 && (
          <span className="text-xs text-slate-400">{open ? "▲" : "▼"}</span>
        )}
      </button>

      {open && stage.sources.length > 0 && (
        <div className="space-y-0.5 pb-1">
          {stage.sources.map((src, idx) => (
            <SourceRow key={idx} src={src} isLast={idx === stage.sources.length - 1} />
          ))}
        </div>
      )}
    </div>
  )
}

const LOCALSTORAGE_KEY = "timeline-v2-collapsed"

interface ContentTimelineV2Props {
  contentId: number
}

export function ContentTimelineV2({ contentId }: ContentTimelineV2Props) {
  const [stages, setStages] = useState<StageOut[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isOpen, setIsOpen] = useState(() => {
    if (typeof window === "undefined") return false
    return localStorage.getItem(LOCALSTORAGE_KEY) !== "true"
  })

  const toggleOpen = (val: boolean) => {
    setIsOpen(val)
    localStorage.setItem(LOCALSTORAGE_KEY, String(!val))
  }

  useEffect(() => {
    setIsLoading(true)
    metadataApi.getTimelineV2(contentId)
      .then((data) => setStages(data.pipeline_stages))
      .catch(() => {})
      .finally(() => setIsLoading(false))
  }, [contentId])

  return (
    <Collapsible open={isOpen} onOpenChange={toggleOpen}>
      <CollapsibleTrigger className="flex items-center justify-between w-full group">
        <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
          파이프라인 타임라인 V2
        </h3>
        <span className="text-xs text-slate-400 group-hover:text-slate-600">{isOpen ? "▲" : "▼"}</span>
      </CollapsibleTrigger>

      <CollapsibleContent className="mt-2">
        {isLoading ? (
          <div className="text-xs text-slate-400">로딩 중...</div>
        ) : stages.length === 0 ? (
          <div className="text-xs text-slate-400">파이프라인 이벤트 없음</div>
        ) : (
          <div className="space-y-0.5">
            {stages.map((stage) => (
              <StageRow key={stage.stage} stage={stage} />
            ))}
          </div>
        )}
      </CollapsibleContent>
    </Collapsible>
  )
}
