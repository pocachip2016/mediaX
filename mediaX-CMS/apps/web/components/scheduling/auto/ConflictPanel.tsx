"use client"

import { useEffect, useState } from "react"
import { AlertTriangle, CheckCircle, Info } from "lucide-react"
import { schedulingAutoApi, type ConflictReport, type ConflictItem } from "@/lib/api"
import { ExposureCalendar } from "@/components/scheduling/ExposureCalendar"
import { cn } from "@workspace/ui/lib/utils"

type Props = {
  setId: number
}

const TYPE_META: Record<ConflictItem["type"], { label: string; color: string; blocking: boolean }> = {
  window_overlap:    { label: "window 겹침",  color: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300",    blocking: true },
  duplicate_content: { label: "중복 편성",     color: "bg-yellow-100 text-yellow-700 dark:bg-yellow-950 dark:text-yellow-300", blocking: false },
}

export function ConflictPanel({ setId }: Props) {
  const [report, setReport] = useState<ConflictReport | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(false)

  useEffect(() => {
    setLoading(true)
    setError(false)
    schedulingAutoApi
      .getSetConflicts(setId)
      .then(setReport)
      .catch(() => setError(true))
      .finally(() => setLoading(false))
  }, [setId])

  if (loading) {
    return (
      <div className="rounded-lg border bg-card p-4 text-xs text-muted-foreground">
        충돌 분석 중…
      </div>
    )
  }

  if (error) {
    return (
      <div className="rounded-lg border bg-card p-4 text-xs text-red-500 flex items-center gap-2">
        <Info className="w-4 h-4 shrink-0" />
        충돌 데이터 로드 실패
      </div>
    )
  }

  if (!report) return null

  const hasBlocking = report.blocking_count > 0

  return (
    <div className="space-y-3">
      {/* 요약 헤더 */}
      <div className={cn(
        "rounded-lg border p-3 flex items-start gap-3",
        hasBlocking
          ? "border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-950/30"
          : "border-green-200 bg-green-50 dark:border-green-800 dark:bg-green-950/30"
      )}>
        {hasBlocking ? (
          <AlertTriangle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
        ) : (
          <CheckCircle className="w-4 h-4 text-green-500 shrink-0 mt-0.5" />
        )}
        <div className="text-xs space-y-0.5">
          {hasBlocking ? (
            <>
              <p className="font-medium text-red-700 dark:text-red-300">
                발행 차단 충돌 {report.blocking_count}건
              </p>
              <p className="text-red-600/80 dark:text-red-400/80">
                window 겹침을 해소해야 P6 발행이 가능합니다.
              </p>
            </>
          ) : (
            <p className="font-medium text-green-700 dark:text-green-300">충돌 없음 — 발행 가능</p>
          )}
          {report.duplicate_content_count > 0 && (
            <p className="text-yellow-600 dark:text-yellow-400">
              중복 편성 {report.duplicate_content_count}건 (발행 차단 아님, 검토 권고)
            </p>
          )}
        </div>
      </div>

      {/* 충돌 목록 */}
      {report.conflicts.length > 0 && (
        <div className="rounded-lg border bg-card overflow-hidden">
          <div className="px-3 py-2 border-b text-xs font-medium text-muted-foreground">
            충돌 항목 ({report.conflict_count})
          </div>
          <ul className="divide-y">
            {report.conflicts.map((c, i) => {
              const meta = TYPE_META[c.type]
              return (
                <li key={i} className="px-3 py-2 text-xs space-y-0.5">
                  <div className="flex items-center gap-2">
                    <span className={cn("px-1.5 py-0.5 rounded text-[10px] font-medium", meta.color)}>
                      {meta.label}
                    </span>
                    <span className="text-muted-foreground">콘텐츠 #{c.content_id}</span>
                    {meta.blocking && (
                      <span className="ml-auto text-[10px] text-red-500 font-medium">차단</span>
                    )}
                  </div>
                  <p className="text-muted-foreground">{c.detail}</p>
                </li>
              )
            })}
          </ul>
        </div>
      )}

      {/* 노출 캘린더 (시각적 확인) */}
      <div className="h-56">
        <ExposureCalendar setId={setId} />
      </div>
    </div>
  )
}
