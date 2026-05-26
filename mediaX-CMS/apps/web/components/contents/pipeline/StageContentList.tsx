"use client"

import { StageCount } from "@/lib/api"
import { useRouter } from "next/navigation"

const SOURCE_RESULT_ICON: Record<string, string> = {
  hit: "✓",
  ok: "✓",
  miss: "✗",
  error: "⚠",
  pending: "…",
}

const SOURCE_RESULT_COLOR: Record<string, string> = {
  hit: "text-green-600 dark:text-green-400",
  ok: "text-green-600 dark:text-green-400",
  miss: "text-gray-500 dark:text-gray-400",
  error: "text-red-600 dark:text-red-400",
  pending: "text-yellow-600 dark:text-yellow-400",
}

interface StageContentListProps {
  stageId: string
  stats: StageCount
}

export function StageContentList({ stageId, stats }: StageContentListProps) {
  const router = useRouter()

  const formatSecondsSinceEntered = (seconds: number | null | undefined) => {
    if (!seconds) return "-"
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    if (mins > 0) return `${mins}분 ${secs}초`
    return `${secs}초`
  }

  const hasSourceTree = stageId === "s4_source_match" || stageId === "s6_websearch_fill"

  return (
    <div className="space-y-3">
      {/* 헤더 */}
      <div className="border-b border-slate-200 pb-2 dark:border-slate-700">
        <div className="text-sm font-semibold mb-1">{stageId.toUpperCase()}</div>
        <div className="text-xs text-slate-500 dark:text-slate-400">
          {stats.count}건 · 평균 {formatSecondsSinceEntered(stats.avg_seconds)}
          {stats.error_count > 0 && (
            <>
              {" "}
              · <span className="text-red-600 dark:text-red-400">에러 {stats.error_count}건</span>
            </>
          )}
        </div>
      </div>

      {/* 콘텐츠 리스트 */}
      <div className="space-y-2 max-h-64 overflow-y-auto">
        {stats.top_contents.length === 0 ? (
          <div className="text-xs text-slate-400 py-4 text-center">콘텐츠 없음</div>
        ) : (
          stats.top_contents.map((content) => (
            <div
              key={content.id}
              className="cursor-pointer rounded border border-slate-200 bg-slate-50 p-2 hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-800 dark:hover:bg-slate-700"
              onClick={() => router.push(`/programming/contents/${content.id}`)}
            >
              {/* 기본 정보 */}
              <div className="flex items-baseline justify-between mb-1">
                <div className="text-xs font-semibold">
                  #{content.id} {content.title}
                </div>
                {content.seconds_in_stage && (
                  <div className="text-xs text-slate-500 dark:text-slate-400">
                    {formatSecondsSinceEntered(content.seconds_in_stage)}
                  </div>
                )}
              </div>

              {/* Source Tree (S4/S6만) */}
              {hasSourceTree && content.sources.length > 0 && (
                <div className="ml-2 space-y-0.5 text-xs">
                  {content.sources.map((src, idx) => (
                    <div key={idx} className="text-slate-600 dark:text-slate-400 font-mono">
                      <span className="mr-1">
                        {idx === content.sources.length - 1 ? "└" : "├"}
                      </span>
                      <span>{src.source}</span>
                      {" "}
                      <span className={SOURCE_RESULT_COLOR[src.result]}>
                        {SOURCE_RESULT_ICON[src.result]} {src.result}
                      </span>
                      {src.latency_ms && (
                        <span className="text-slate-500 ml-1">{src.latency_ms}ms</span>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  )
}
