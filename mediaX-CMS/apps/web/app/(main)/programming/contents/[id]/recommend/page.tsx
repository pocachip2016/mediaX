"use client"

import { useEffect, useState, useCallback } from "react"
import { useParams, useRouter, useSearchParams } from "next/navigation"
import { Loader2 } from "lucide-react"
import {
  metadataApi,
  posterRecommendApi,
  type ContentDetail,
  type RecommendationsOut,
  type PosterCandidateOut,
} from "@/lib/api"
import { BulkActionModal } from "@/components/contents/BulkActionModal"
import { StickyActionBar, deriveMode } from "@/components/contents/recommend/StickyActionBar"
import { PosterRow } from "@/components/contents/recommend/PosterRow"
import { ShortMetaGrid } from "@/components/contents/recommend/ShortMetaGrid"
import { SynopsisRow } from "@/components/contents/recommend/SynopsisRow"
import { AISummaryBottom } from "@/components/contents/recommend/AISummaryBottom"
import { useContentReviewActions } from "@/hooks/useContentReviewActions"
import { getReturnPath, getReturnHref } from "@/lib/recommendDerive"

const MOCK_RECOMMENDATIONS: RecommendationsOut = {
  content_id: 0,
  missing_fields: [],
  auto_fill: [
    {
      field: "genres",
      status: "auto",
      recommendations: [{ source_type: "tmdb", source_id: 2, value: "드라마/스릴러", confidence: 0.94 }],
      ai_synthesis: null,
    },
    {
      field: "cp_name",
      status: "auto",
      recommendations: [{ source_type: "watcha", source_id: 1, value: "CJ E&M", confidence: 0.92 }],
      ai_synthesis: null,
    },
    {
      field: "runtime",
      status: "auto",
      recommendations: [
        { source_type: "tmdb", source_id: 2, value: "132분", confidence: 0.94 },
        { source_type: "watcha", source_id: 1, value: "132분", confidence: 1.0 },
      ],
      ai_synthesis: null,
    },
    {
      field: "country",
      status: "auto",
      recommendations: [{ source_type: "tmdb", source_id: 2, value: "South Korea", confidence: 0.96 }],
      ai_synthesis: null,
    },
    {
      field: "production_year",
      status: "auto",
      recommendations: [{ source_type: "tmdb", source_id: 2, value: "2019", confidence: 0.99 }],
      ai_synthesis: null,
    },
    {
      field: "director",
      status: "auto",
      recommendations: [{ source_type: "watcha", source_id: 1, value: "봉준호", confidence: 0.98 }],
      ai_synthesis: null,
    },
    {
      field: "cast",
      status: "auto",
      recommendations: [{ source_type: "watcha", source_id: 1, value: "송강호 · 이순신 · 조진웅", confidence: 0.95 }],
      ai_synthesis: null,
    },
  ],
  conflicts: [
    {
      field: "synopsis",
      status: "conflict",
      recommendations: [
        { source_type: "watcha", source_id: 1, value: "가난한 박씨 가족은 부잣집에 하나 둘씩 취업하며 묘한 공생 관계를 형성해간다.", confidence: 0.5 },
        { source_type: "tmdb", source_id: 2, value: "A poor family schemes to become employed by a wealthy Park family.", confidence: 0.94 },
      ],
      ai_synthesis: {
        source_type: "ai", source_id: 99,
        value: "경제적으로 어려운 박씨 일가는 재벌 박 사장 가족의 집에 한 명씩 취업하며 공생 관계를 형성해가지만, 숨겨진 비밀이 드러나면서 예기치 못한 사건이 벌어진다.",
        confidence: 0.79,
      },
    },
  ],
}

export default function ContentRecommendDetailPage() {
  const params = useParams()
  const router = useRouter()
  const searchParams = useSearchParams()
  const contentId = Number(params.id)

  const returnPath = getReturnPath(searchParams)
  const returnInfo = getReturnHref(returnPath, contentId)

  const [content, setContent] = useState<ContentDetail | null>(null)
  const [recommendations, setRecommendations] = useState<RecommendationsOut>({
    ...MOCK_RECOMMENDATIONS,
    content_id: contentId,
  })
  const [posterCandidates, setPosterCandidates] = useState<PosterCandidateOut[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [previewOpen, setPreviewOpen] = useState(false)

  const primaryId = posterCandidates?.find((c) => c.is_primary)?.id ?? null

  const handleSelectPrimary = useCallback(async (id: number) => {
    const updated = await posterRecommendApi.selectPrimary(contentId, id)
    setPosterCandidates(updated)
  }, [contentId])

  const handleRecommendPoster = useCallback(async () => {
    const res = await posterRecommendApi.recommend(contentId)
    setPosterCandidates(res.candidates)
  }, [contentId])

  const fetchAll = useCallback(async () => {
    try {
      const [updatedContent, updatedRecs] = await Promise.all([
        metadataApi.getContent(contentId),
        metadataApi.getRecommendations(contentId),
      ])
      setContent(updatedContent)
      // 개발 단계: 항상 MOCK 사용 (backend API 데이터 구조 불일치 시)
      const recData = updatedRecs && updatedRecs.auto_fill && updatedRecs.auto_fill.length > 0
        ? updatedRecs
        : { ...MOCK_RECOMMENDATIONS, content_id: contentId }
      setRecommendations(recData)
    } catch (error) {
      // API 실패시 MOCK 데이터 사용
      const updatedContent = await metadataApi.getContent(contentId)
      setContent(updatedContent)
      setRecommendations({
        ...MOCK_RECOMMENDATIONS,
        content_id: contentId,
      })
    }
  }, [contentId])

  useEffect(() => {
    setLoading(true)
    fetchAll().finally(() => setLoading(false))
  }, [fetchAll])

  useEffect(() => {
    posterRecommendApi
      .getCandidates(contentId)
      .then((candidates) => {
        setPosterCandidates(candidates)
        // 포스터가 없으면 자동으로 AI 추천 가져오기
        if (!candidates || candidates.length === 0) {
          posterRecommendApi.recommend(contentId).then((res) => setPosterCandidates(res.candidates))
        }
      })
      .catch(() => setPosterCandidates([]))
  }, [contentId])

  const onNavigateAfterDecision = useCallback(() => {
    router.push(returnInfo.href || "/programming/contents")
  }, [router, returnInfo.href])

  const actions = useContentReviewActions(contentId, {
    content,
    recommendations,
    onRefetch: fetchAll,
    onNavigateAfterDecision,
  })

  const mode = deriveMode(content?.status)

  if (loading) {
    return (
      <div className="flex items-center justify-center h-48 text-slate-500">
        <Loader2 className="h-5 w-5 animate-spin mr-2" />로드 중...
      </div>
    )
  }

  if (!content) {
    return (
      <div className="p-6 text-center text-slate-500">콘텐츠를 찾을 수 없습니다.</div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <StickyActionBar
        content={content}
        mode={mode}
        actions={actions}
        returnLabel={returnInfo.label}
        returnHref={returnInfo.href}
        onPreview={() => setPreviewOpen(true)}
      />

      <div className="max-w-7xl mx-auto px-4 py-6 space-y-4">
        {/* Step 1.2 — PosterRow */}
        <PosterRow
          contentId={contentId}
          candidates={posterCandidates ?? []}
          primaryId={primaryId}
          onSelectPrimary={handleSelectPrimary}
          onRecommend={handleRecommendPoster}
        />

        {/* Step 1.3 — ShortMetaGrid */}
        <ShortMetaGrid
          content={content}
          recommendations={recommendations}
          appliedFields={actions.appliedFields}
          onApply={actions.applyRec}
        />

        {/* Step 1.4 — SynopsisRow */}
        {(() => {
          const synopsisRec = recommendations ? [...recommendations.auto_fill, ...recommendations.conflicts].find((r) => r.field === "synopsis") ?? null : null
          return (
            <SynopsisRow
              currentSynopsis={content.metadata_record?.final_synopsis || content.metadata_record?.cp_synopsis || null}
              rec={synopsisRec}
              isApplied={actions.appliedFields.has("synopsis")}
              onApply={(source) => synopsisRec ? actions.applyRec(synopsisRec, source) : Promise.resolve()}
              onEdit={() => router.push(`/programming/contents/${contentId}/edit`)}
            />
          )
        })()}

        {/* Step 1.5 — AISummaryBottom */}
        {recommendations && (
          <AISummaryBottom
            recommendations={recommendations}
            appliedFields={actions.appliedFields}
            onApplyAllAuto={actions.applyAllAuto}
            onRegenerate={actions.regenerate}
            onDismiss={actions.dismissModal}
          />
        )}

        {/* Step 1.6 */}
        <div className="border border-dashed border-slate-300 rounded-lg p-6 text-sm text-slate-400 bg-white">
          📁 보조 정보 (Step 1.6)
        </div>
      </div>

      {/* 승인/반려 모달 — BulkActionModal 재사용 (단건) */}
      <BulkActionModal
        open={actions.modalState.open}
        onOpenChange={(open) => {
          if (!open) actions.dismissModal()
        }}
        action={actions.modalState.action}
        targets={actions.modalState.targets}
      />

      {/* Step 1.7: PreviewDialog placeholder */}
      {previewOpen && (
        <div
          className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center"
          onClick={() => setPreviewOpen(false)}
        >
          <div className="bg-white rounded-xl p-8 text-slate-500 text-sm">
            미리보기 Dialog — Step 1.7에서 구현
          </div>
        </div>
      )}
    </div>
  )
}
