"use client"

import { useState } from "react"
import { Sparkles, RotateCcw, X } from "lucide-react"
import { cn } from "@workspace/ui/lib/utils"
import type { RecommendationsOut, FieldRecommendation } from "@/lib/api"
import { avgConfidence, summarizeByKind, reasonSummary } from "@/lib/recommendDerive"

interface Props {
  recommendations: RecommendationsOut
  appliedFields: Set<string>
  currentValuesByField?: Record<string, string | null | undefined>
  qualityScore?: number | null  // 메타 완성도 (0~100)
  onApplyAllAuto: () => Promise<void>
  onApplyAll?: () => Promise<void>  // auto + conflict top 전체 적용
  onRegenerate: () => Promise<void>
  onDismiss: () => void
}

export function AISummaryBottom({
  recommendations,
  appliedFields,
  currentValuesByField,
  qualityScore,
  onApplyAllAuto,
  onApplyAll,
  onRegenerate,
  onDismiss,
}: Props) {
  const [applyingAllAuto, setApplyingAllAuto] = useState(false)
  const [applyingAll, setApplyingAll] = useState(false)
  const [regenerating, setRegenerating] = useState(false)

  const avg = avgConfidence([...recommendations.auto_fill, ...recommendations.conflicts])
  const { confirmed, auto, conflict, missing } = summarizeByKind(recommendations, appliedFields, currentValuesByField)

  // auto 추천 중 아직 채택되지 않은 것들만 (summarizeByKind가 유사 건은 이미 confirmed 처리)
  const unconfirmedAuto = auto
  const applicableTotal = auto.length + conflict.length

  async function handleApplyAllAuto() {
    setApplyingAllAuto(true)
    try {
      await onApplyAllAuto()
    } finally {
      setApplyingAllAuto(false)
    }
  }

  async function handleApplyAll() {
    if (!onApplyAll) return
    setApplyingAll(true)
    try {
      await onApplyAll()
    } finally {
      setApplyingAll(false)
    }
  }

  async function handleRegenerate() {
    setRegenerating(true)
    try {
      await onRegenerate()
    } finally {
      setRegenerating(false)
    }
  }

  const qs = qualityScore ?? 0

  return (
    <div className="flex flex-col gap-4 p-5 bg-white rounded-lg border">
      {/* 메타완성도 + 추천신뢰도 게이지 */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <p className="text-xs font-semibold text-slate-700 mb-1.5">메타완성도</p>
          <div className="flex items-center gap-2">
            <div className="flex-1 h-2 bg-slate-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-amber-500 rounded-full transition-all"
                style={{ width: `${qs}%` }}
              />
            </div>
            <span className="text-xs font-semibold text-amber-700 tabular-nums w-10 text-right">
              {qs.toFixed(0)}
            </span>
          </div>
        </div>
        <div>
          <p className="text-xs font-semibold text-slate-700 mb-1.5">추천신뢰도</p>
          <div className="flex items-center gap-2">
            <div className="flex-1 h-2 bg-slate-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-emerald-500 rounded-full transition-all"
                style={{ width: `${avg * 100}%` }}
              />
            </div>
            <span className="text-xs font-semibold text-emerald-700 tabular-nums w-10 text-right">
              {(avg * 100).toFixed(0)}%
            </span>
          </div>
        </div>
      </div>

      {/* 4 카테고리 칩 */}
      <div className="flex flex-wrap gap-2">
        <div className="flex items-center gap-1.5 px-3 py-1.5 bg-green-100 text-green-700 rounded-full text-xs font-medium">
          <span>✓</span>확정 <span className="font-semibold">{confirmed.length}</span>
        </div>
        <div className="flex items-center gap-1.5 px-3 py-1.5 bg-amber-100 text-amber-700 rounded-full text-xs font-medium">
          <span>⚡</span>자동 <span className="font-semibold">{auto.length}</span>
        </div>
        <div className="flex items-center gap-1.5 px-3 py-1.5 bg-red-100 text-red-700 rounded-full text-xs font-medium">
          <span>⚠</span>충돌 <span className="font-semibold">{conflict.length}</span>
        </div>
        <div className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-100 text-slate-700 rounded-full text-xs font-medium">
          <span>❌</span>미입력 <span className="font-semibold">{missing.length}</span>
        </div>
      </div>

      {/* 자동 추천 사유 요약 */}
      {unconfirmedAuto.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-slate-500 mb-2">추천 사유</p>
          <div className="space-y-1">
            {unconfirmedAuto
              .slice(0, 3)
              .map((field) => {
                const rec = [
                  ...recommendations.auto_fill,
                  ...recommendations.conflicts,
                ].find((r) => r.field === field)
                return rec ? (
                  <p key={field} className="text-xs text-slate-600">
                    • <span className="font-medium">{field}</span>: {reasonSummary(rec)}
                  </p>
                ) : null
              })}
            {unconfirmedAuto.length > 3 && (
              <p className="text-xs text-slate-400">
                + {unconfirmedAuto.length - 3}개 더...
              </p>
            )}
          </div>
        </div>
      )}

      {/* Bulk Actions */}
      <div className="flex flex-wrap gap-2 pt-2 border-t border-slate-100">
        {onApplyAll && applicableTotal > 0 && (
          <button
            onClick={handleApplyAll}
            disabled={applyingAll}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-emerald-600 text-white text-xs font-medium hover:bg-emerald-700 disabled:opacity-50"
          >
            <Sparkles className="h-3 w-3" />
            {applyingAll ? "적용 중..." : `✓ 적용 가능 ${applicableTotal}건 모두 적용`}
          </button>
        )}

        {unconfirmedAuto.length > 0 && (
          <button
            onClick={handleApplyAllAuto}
            disabled={applyingAllAuto}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-green-100 text-green-700 text-xs font-medium hover:bg-green-200 disabled:opacity-50"
          >
            <Sparkles className="h-3 w-3" />
            {applyingAllAuto ? "적용 중..." : `✨ 자동 ${unconfirmedAuto.length}건만 채택`}
          </button>
        )}

        <button
          onClick={handleRegenerate}
          disabled={regenerating}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-blue-100 text-blue-700 text-xs font-medium hover:bg-blue-200 disabled:opacity-50"
        >
          <RotateCcw className="h-3 w-3" />
          {regenerating ? "재생성 중..." : "↻ AI 재생성"}
        </button>

        <button
          onClick={onDismiss}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-slate-100 text-slate-700 text-xs font-medium hover:bg-slate-200"
        >
          <X className="h-3 w-3" />
          추천 무시
        </button>
      </div>
    </div>
  )
}
