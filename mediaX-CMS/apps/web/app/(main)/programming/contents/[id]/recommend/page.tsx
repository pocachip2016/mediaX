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
import { SecondaryAccordion } from "@/components/contents/recommend/SecondaryAccordion"
import { useContentReviewActions } from "@/hooks/useContentReviewActions"
import { getReturnPath, getReturnHref } from "@/lib/recommendDerive"

export default function ContentRecommendDetailPage() {
  const params = useParams()
  const router = useRouter()
  const searchParams = useSearchParams()
  const contentId = Number(params.id)

  const returnPath = getReturnPath(searchParams)
  const returnInfo = getReturnHref(returnPath, contentId)

  const [content, setContent] = useState<ContentDetail | null>(null)
  const [recommendations, setRecommendations] = useState<RecommendationsOut>({
    content_id: contentId,
    missing_fields: [],
    auto_fill: [],
    conflicts: [],
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
    const [updatedContent, updatedRecs] = await Promise.all([
      metadataApi.getContent(contentId),
      metadataApi.getRecommendations(contentId).catch(() => null),
    ])
    setContent(updatedContent)
    setRecommendations(updatedRecs ?? { content_id: contentId, missing_fields: [], auto_fill: [], conflicts: [] })
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

        {/* Step 1.6 — SecondaryAccordion */}
        <SecondaryAccordion content={content} />
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
