"use client"

import { useState } from "react"
import { CheckCircle2, AlertTriangle, XCircle } from "lucide-react"
import { cn } from "@workspace/ui/lib/utils"
import {
  metadataApi,
  type ContentDetail,
  type PosterCandidateOut,
  type RecommendationsOut,
  type FieldRecommendation,
  type SourceFieldRec,
} from "@/lib/api"
import { PosterRow } from "@/components/contents/recommend/PosterRow"
import { MetadataDiffPanel } from "@/components/contents/MetadataDiffPanel"

interface ReviewPaneProps {
  content: ContentDetail
  contentId: number
  recommendations: RecommendationsOut | null
  posterCandidates: PosterCandidateOut[]
  primaryId: number | null
  appliedFields: Set<string>
  onSelectPrimary: (id: number) => Promise<void>
  onApply: (rec: FieldRecommendation, source: SourceFieldRec) => Promise<void>
  onApplyAll: () => Promise<void>
  onDecision: (action: "approve" | "reject") => void
}

export function ReviewPane({
  content,
  contentId,
  recommendations,
  posterCandidates,
  primaryId,
  onSelectPrimary,
  onApply,
  onApplyAll,
  onDecision,
}: ReviewPaneProps) {
  const [reviewer, setReviewer] = useState("")
  const [memo, setMemo] = useState("")
  const [submitting, setSubmitting] = useState<"approve" | "reject" | null>(null)
  const [error, setError] = useState<string | null>(null)

  const hasPrimary = primaryId !== null || posterCandidates.some((c) => c.is_primary)

  const synopsisConflict = recommendations
    ? recommendations.conflicts.find((r) => r.field === "synopsis") ?? null
    : null

  const currentValues: Record<string, string | null> = {
    synopsis:
      content.metadata_record?.final_synopsis ||
      content.metadata_record?.cp_synopsis ||
      null,
  }

  async function handleDecision(action: "approve" | "reject") {
    if (!reviewer.trim()) {
      setError("검수자 이름을 입력해 주세요")
      return
    }
    setError(null)
    setSubmitting(action)
    try {
      await metadataApi.reviewAction(contentId, {
        action,
        reviewer: reviewer.trim(),
        ...(memo.trim() && { final_synopsis: memo.trim() }),
      })
      onDecision(action)
    } catch (err) {
      setError(err instanceof Error ? err.message : "요청 실패")
    } finally {
      setSubmitting(null)
    }
  }

  return (
    <div className="space-y-4">
      {/* [A] 포스터 점검 */}
      <div className="bg-white rounded-lg border border-slate-200 p-4">
        <div className="flex items-center gap-2 mb-3">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide">포스터 점검</p>
          {hasPrimary ? (
            <span className="inline-flex items-center gap-1 text-xs text-green-700 bg-green-50 border border-green-200 rounded-full px-2 py-0.5">
              <CheckCircle2 className="h-3 w-3" /> primary 설정됨
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-full px-2 py-0.5">
              <AlertTriangle className="h-3 w-3" /> primary 미선택
            </span>
          )}
        </div>
        <PosterRow
          contentId={contentId}
          candidates={posterCandidates}
          primaryId={primaryId}
          onSelectPrimary={onSelectPrimary}
          onRecommend={async () => {}}
        />
      </div>

      {/* [B] 시놉시스 점검 */}
      <div className="bg-white rounded-lg border border-slate-200 p-4">
        <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3">
          시놉시스 점검
        </p>
        {synopsisConflict ? (
          <div className="space-y-2">
            <div className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-2 flex items-center gap-1.5">
              <AlertTriangle className="h-3.5 w-3.5 flex-shrink-0" />
              출처 간 충돌 — 검수 후 채택 필요
            </div>
            {synopsisConflict.recommendations.map((r) => (
              <div key={r.source_id} className="border border-slate-200 rounded-lg p-3 text-xs text-slate-700">
                <div className="text-[10px] font-semibold text-slate-400 uppercase mb-1">{r.source_type}</div>
                <p className="leading-relaxed line-clamp-3">{r.value}</p>
                <button
                  onClick={() => void onApply(synopsisConflict, r)}
                  className="mt-2 text-blue-600 hover:text-blue-700 font-medium"
                >
                  이 버전 채택
                </button>
              </div>
            ))}
          </div>
        ) : (
          <div className="flex items-center gap-1.5 text-xs text-green-700">
            <CheckCircle2 className="h-4 w-4" />
            시놉시스 이상없음
          </div>
        )}
      </div>

      {/* [C] 메타 필드 상태 */}
      <div>
        <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2 px-1">
          메타 필드 상태
        </p>
        {recommendations ? (
          <MetadataDiffPanel
            recommendations={recommendations}
            currentValues={currentValues}
            onDismiss={() => {}}
            onApply={onApply}
            onApplyAll={onApplyAll}
            onEditManually={() => {}}
          />
        ) : (
          <div className="bg-white rounded-lg border border-slate-200 p-4 text-xs text-slate-400">
            추천 데이터 없음
          </div>
        )}
        {recommendations && recommendations.missing_fields.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {recommendations.missing_fields.map((f) => (
              <span
                key={f}
                className="text-[10px] px-2 py-0.5 rounded-full bg-amber-50 border border-amber-200 text-amber-700"
              >
                {f} 미입력
              </span>
            ))}
          </div>
        )}
      </div>

      {/* [D] Footer — 검수 결정 */}
      <div className="bg-white rounded-lg border border-slate-200 p-4 space-y-3">
        <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide">검수 결정</p>

        {error && (
          <div className="flex items-center gap-1.5 text-xs text-red-700 bg-red-50 border border-red-200 rounded px-3 py-2">
            <XCircle className="h-3.5 w-3.5 flex-shrink-0" />
            {error}
          </div>
        )}

        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">검수자 *</label>
          <input
            className="w-full px-3 py-2 rounded-lg border border-slate-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-400/30"
            value={reviewer}
            onChange={(e) => setReviewer(e.target.value)}
            placeholder="검수자 이름"
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">메모 (선택)</label>
          <textarea
            className="w-full px-3 py-2 rounded-lg border border-slate-200 bg-white text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-400/30"
            rows={3}
            value={memo}
            onChange={(e) => setMemo(e.target.value)}
            placeholder="검수 의견 또는 수정 내용"
          />
        </div>

        <div className="flex gap-3 pt-1">
          <button
            onClick={() => void handleDecision("approve")}
            disabled={submitting !== null}
            className={cn(
              "flex-1 py-2.5 rounded-lg text-sm font-medium transition-colors",
              "bg-green-600 text-white hover:bg-green-700 disabled:opacity-50",
            )}
          >
            {submitting === "approve" ? "처리 중..." : "승인"}
          </button>
          <button
            onClick={() => void handleDecision("reject")}
            disabled={submitting !== null}
            className={cn(
              "flex-1 py-2.5 rounded-lg text-sm font-medium transition-colors",
              "bg-red-50 text-red-700 border border-red-200 hover:bg-red-100 disabled:opacity-50",
            )}
          >
            {submitting === "reject" ? "처리 중..." : "반려"}
          </button>
        </div>
      </div>
    </div>
  )
}
