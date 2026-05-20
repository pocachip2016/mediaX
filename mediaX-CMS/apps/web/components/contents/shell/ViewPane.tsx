"use client"

import type {
  ContentDetail,
  PosterCandidateOut,
  RecommendationsOut,
  FieldRecommendation,
  SourceFieldRec,
} from "@/lib/api"
import { PosterRow } from "@/components/contents/recommend/PosterRow"
import { SynopsisRow } from "@/components/contents/recommend/SynopsisRow"
import { ShortMetaGrid } from "@/components/contents/recommend/ShortMetaGrid"
import { AISummaryBottom } from "@/components/contents/recommend/AISummaryBottom"

interface ViewPaneProps {
  content: ContentDetail
  contentId: number
  recommendations: RecommendationsOut | null
  posterCandidates: PosterCandidateOut[]
  primaryId: number | null
  appliedFields: Set<string>
  inheritedFields?: string[]
  onSelectPrimary: (id: number) => Promise<void>
  onRecommendPoster: () => Promise<void>
  onApply: (rec: FieldRecommendation, source: SourceFieldRec) => Promise<void>
  onApplyAllAuto: () => Promise<void>
  onRegenerate: () => Promise<void>
  onEditSynopsis: () => void
}

export function ViewPane({
  content,
  contentId,
  recommendations,
  posterCandidates,
  primaryId,
  appliedFields,
  inheritedFields,
  onSelectPrimary,
  onRecommendPoster,
  onApply,
  onApplyAllAuto,
  onRegenerate,
  onEditSynopsis,
}: ViewPaneProps) {
  const synopsisRec = recommendations
    ? [...recommendations.auto_fill, ...recommendations.conflicts].find(
        (r) => r.field === "synopsis",
      ) ?? null
    : null

  const currentSynopsis =
    content.metadata_record?.final_synopsis ||
    content.metadata_record?.cp_synopsis ||
    null

  return (
    <div className="space-y-4">
      {/* [A] 포스터 */}
      <div>
        <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2 px-1">
          포스터
        </p>
        <PosterRow
          contentId={contentId}
          candidates={posterCandidates}
          primaryId={primaryId}
          onSelectPrimary={onSelectPrimary}
          onRecommend={onRecommendPoster}
        />
      </div>

      {/* [B] 시놉시스 */}
      <SynopsisRow
        currentSynopsis={currentSynopsis}
        rec={synopsisRec}
        isApplied={appliedFields.has("synopsis")}
        onApply={(source) =>
          synopsisRec ? onApply(synopsisRec, source) : Promise.resolve()
        }
        onEdit={onEditSynopsis}
      />

      {/* [C] 메타 필드 추천 */}
      {recommendations && (
        <>
          <ShortMetaGrid
            content={content}
            recommendations={recommendations}
            appliedFields={appliedFields}
            onApply={onApply}
            inheritedFields={inheritedFields}
          />
          <AISummaryBottom
            recommendations={recommendations}
            appliedFields={appliedFields}
            onApplyAllAuto={onApplyAllAuto}
            onRegenerate={onRegenerate}
            onDismiss={() => {}}
          />
        </>
      )}
    </div>
  )
}
