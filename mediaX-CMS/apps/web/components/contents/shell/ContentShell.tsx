"use client"

import { cn } from "@workspace/ui/lib/utils"
import { type ContentDetail, type PosterCandidateOut, type StagingItem } from "@/lib/api"
import { SourceBadge } from "@/components/source-badge"
import { SecondaryAccordion } from "@/components/contents/recommend/SecondaryAccordion"
import { ChildrenTable } from "@/components/contents/detail/ChildrenTable"
import { isLeafType, TYPE_LABEL } from "@/components/contents/detail/contentType"
import { ContentTimelineV2 } from "./ContentTimelineV2"

function MissingBadge() {
  return (
    <span className="text-xs text-slate-400 border border-dashed border-slate-200 rounded px-1.5 py-0.5">
      Missing
    </span>
  )
}

interface ContentShellProps {
  content: ContentDetail
  contentId: number
  posterCandidates: PosterCandidateOut[]
  primaryId: number | null
  childrenItems: StagingItem[]
  childrenLoading: boolean
  onSelectPrimary: (id: number) => Promise<void>
  onRecommendPoster: () => Promise<void>
}

export function ContentShell({
  content, posterCandidates,
  childrenItems, childrenLoading,
}: ContentShellProps) {
  const directors = content.credits.filter(
    (c) => c.role.toLowerCase().includes("director") || c.role === "감독",
  )
  const leads = content.credits
    .filter((c) => ["actor", "cast", "주연", "출연"].includes(c.role.toLowerCase()))
    .sort((a, b) => (a.cast_order ?? 99) - (b.cast_order ?? 99))
    .slice(0, 5)

  const synopsis =
    content.metadata_record?.final_synopsis ||
    content.metadata_record?.ai_synopsis ||
    content.metadata_record?.cp_synopsis ||
    null

  const synopsisSource = content.metadata_record?.final_synopsis
    ? "ai"
    : content.metadata_record?.ai_synopsis
    ? "ai"
    : content.metadata_record?.cp_synopsis
    ? "cp"
    : null

  const isContainer = !isLeafType(content.content_type)
  const parentType: "series" | "season" =
    content.content_type === "series" ? "series" : "season"

  return (
    <div className="space-y-3">
      {/* [1] 식별 정보 (제목은 DetailHeader 담당) */}
      <div className="bg-white rounded-lg border border-slate-200 p-4 space-y-2">
        <div className="text-xs text-slate-600 space-y-1">
          <div className="flex gap-2">
            <span className="text-slate-400 w-10 flex-shrink-0">유형</span>
            <span>{TYPE_LABEL[content.content_type]}</span>
          </div>
          {content.production_year && (
            <div className="flex gap-2">
              <span className="text-slate-400 w-10 flex-shrink-0">연도</span>
              <span>{content.production_year}</span>
            </div>
          )}
          {content.country && (
            <div className="flex gap-2">
              <span className="text-slate-400 w-10 flex-shrink-0">국가</span>
              <span>{content.country}</span>
            </div>
          )}
          {content.runtime_minutes && (
            <div className="flex gap-2">
              <span className="text-slate-400 w-10 flex-shrink-0">상영</span>
              <span>{content.runtime_minutes}분</span>
            </div>
          )}
          {content.cp_name && (
            <div className="flex gap-2">
              <span className="text-slate-400 w-10 flex-shrink-0">CP사</span>
              <span className="truncate">{content.cp_name}</span>
            </div>
          )}
        </div>
      </div>

      {/* [6] 메타 필드 (장르·감독·주연) */}
      <div className="bg-white rounded-lg border border-slate-200 p-4 space-y-2">
        <div className="flex gap-2 items-start">
          <span className="text-xs text-slate-400 w-10 flex-shrink-0 pt-0.5">장르</span>
          <div className="flex flex-wrap gap-1">
            {content.genres.length > 0
              ? content.genres.map((g) => (
                  <span
                    key={g.genre.id}
                    className={cn(
                      "px-2 py-0.5 rounded-full text-xs border border-slate-200 bg-slate-50",
                      g.is_primary && "border-blue-300 bg-blue-50 text-blue-800",
                    )}
                  >
                    {g.genre.name_ko}
                  </span>
                ))
              : <MissingBadge />}
          </div>
        </div>
        <div className="flex gap-2 items-center">
          <span className="text-xs text-slate-400 w-10 flex-shrink-0">감독</span>
          {directors.length > 0
            ? <span className="text-xs text-slate-700">{directors.map((d) => d.person.name_ko).join(" · ")}</span>
            : <MissingBadge />}
        </div>
        <div className="flex gap-2 items-center">
          <span className="text-xs text-slate-400 w-10 flex-shrink-0">주연</span>
          {leads.length > 0
            ? <span className="text-xs text-slate-700">{leads.map((l) => l.person.name_ko).join(" · ")}</span>
            : <MissingBadge />}
        </div>
        {content.metadata_record?.ai_rating_suggestion && (
          <div className="flex gap-2 items-center">
            <span className="text-xs text-slate-400 w-10 flex-shrink-0">등급</span>
            <span className="text-xs text-slate-700">
              {content.metadata_record.ai_rating_suggestion}
            </span>
          </div>
        )}
      </div>

      {/* [5] 시놉시스 — 장르 카드 아래 */}
      <div className="bg-white rounded-lg border border-slate-200 p-4">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide">시놉시스</h3>
          {synopsisSource && <SourceBadge source={synopsisSource} />}
        </div>
        {synopsis ? (
          <p className="text-xs text-slate-700 leading-relaxed line-clamp-5">{synopsis}</p>
        ) : (
          <MissingBadge />
        )}
      </div>

      {/* [7] SecondaryAccordion */}
      <SecondaryAccordion content={content} />

      {/* [8] Pipeline Timeline V2 (ADR-006) */}
      <ContentTimelineV2 contentId={content.id} />

      {/* [9] ChildrenTable (container 전용) */}
      {isContainer && (
        <ChildrenTable
          children={childrenItems}
          parentType={parentType}
          loading={childrenLoading}
        />
      )}
    </div>
  )
}
