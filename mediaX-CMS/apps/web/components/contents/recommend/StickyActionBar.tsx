"use client"

import Link from "next/link"
import { ArrowLeft, Check, X, RotateCcw, Search, Lock, Edit, Play, Eye, Loader2 } from "lucide-react"
import { cn } from "@workspace/ui/lib/utils"
import type { ContentDetail } from "@/lib/api"
import type { useContentReviewActions } from "@/hooks/useContentReviewActions"
import { BreadcrumbNav } from "@/components/contents/detail/BreadcrumbNav"
import type { BreadcrumbParent } from "@/components/contents/detail/BreadcrumbNav"

export type PageMode = "review" | "readonly" | "processing"

export function deriveMode(status?: string): PageMode {
  if (!status) return "processing"
  if (status === "approved" || status === "rejected") return "readonly"
  if (status === "raw" || status === "enriched") return "processing"
  return "review"
}

const STATUS_BADGE: Record<string, { label: string; color: string }> = {
  raw:      { label: "수신",       color: "bg-slate-100 text-slate-600" },
  enriched: { label: "회수완료",   color: "bg-blue-100 text-blue-700" },
  ai:       { label: "AI처리완료", color: "bg-violet-100 text-violet-700" },
  review:   { label: "검수",       color: "bg-amber-100 text-amber-700" },
  approved:   { label: "✓ 승인됨", color: "bg-green-100 text-green-700" },
  rejected:   { label: "✗ 반려됨", color: "bg-red-100 text-red-700" },
}

const CONTENT_TYPE_KO: Record<string, string> = {
  movie: "영화", series: "시리즈", season: "시즌", episode: "에피소드",
}

interface Props {
  content: ContentDetail
  mode: PageMode
  actions: ReturnType<typeof useContentReviewActions>
  returnLabel: string
  returnHref: string
  onPreview: () => void
  breadcrumbParents?: BreadcrumbParent[]
  seriesReviewHref?: string
}

export function StickyActionBar({ content, mode, actions, returnLabel, returnHref, onPreview, breadcrumbParents, seriesReviewHref }: Props) {
  const badge = STATUS_BADGE[content.status] ?? STATUS_BADGE.raw!
  const qualityScore = content.quality_score ?? 0

  return (
    <div className="sticky top-0 z-30 bg-white border-b shadow-sm">
      {/* 브레드크럼 행 */}
      <div className="px-4 pt-2 pb-1 flex items-center gap-3 flex-wrap">
        <Link href={returnHref} className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800">
          <ArrowLeft className="h-3.5 w-3.5" />
          {returnLabel}
        </Link>
        {breadcrumbParents && breadcrumbParents.length > 0 && (
          <>
            <span className="text-slate-300 text-sm">│</span>
            <BreadcrumbNav parents={breadcrumbParents} />
          </>
        )}
        {seriesReviewHref && (
          <Link
            href={seriesReviewHref}
            className="ml-auto text-xs text-blue-600 hover:text-blue-800 hover:underline"
          >
            → 시리즈 검수로 이동
          </Link>
        )}
      </div>

      {/* 콘텐츠 정보 + 액션 행 */}
      <div className="px-4 pb-3 flex items-center gap-3 flex-wrap">
        {/* 제목 + 메타 */}
        <div className="flex items-center gap-2 min-w-0 flex-1">
          <span className="text-xs text-slate-400 shrink-0">#{content.id}</span>
          <h1 className="font-semibold text-slate-800 truncate">{content.title}</h1>
          <span className="text-xs text-slate-400 shrink-0">[{CONTENT_TYPE_KO[content.content_type] ?? content.content_type}]</span>
          <span className={cn("inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium shrink-0", badge.color)}>
            {badge.label}
          </span>
        </div>

        {/* 품질 점수 */}
        <div className="flex items-center gap-2 shrink-0">
          <div className="w-20 h-1.5 bg-slate-200 rounded-full overflow-hidden">
            <div
              className={cn("h-full rounded-full", qualityScore >= 90 ? "bg-green-500" : qualityScore >= 70 ? "bg-amber-500" : "bg-red-400")}
              style={{ width: `${qualityScore}%` }}
            />
          </div>
          <span className="text-xs text-slate-500 tabular-nums">{qualityScore}</span>
        </div>

        {/* 액션 버튼 */}
        <div className="flex items-center gap-1.5 shrink-0">
          {mode === "processing" && (
            <>
              <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
              <span className="text-sm text-slate-500">처리 중...</span>
              <ActionBtn icon={<RotateCcw className="h-3.5 w-3.5" />} label="AI 재처리" onClick={() => void actions.reprocess()} color="orange" />
            </>
          )}

          {mode === "readonly" && (
            <>
              <ActionBtn icon={<RotateCcw className="h-3.5 w-3.5" />} label="검수 재개" onClick={() => void actions.reprocess()} color="slate" />
              <ActionBtn icon={<Eye className="h-3.5 w-3.5" />} label="미리보기" onClick={onPreview} color="slate" />
            </>
          )}

          {mode === "review" && (
            <>
              <ActionBtn icon={<Check className="h-3.5 w-3.5" />} label="승인" onClick={actions.approve} color="green" />
              <ActionBtn icon={<X className="h-3.5 w-3.5" />} label="반려" onClick={actions.reject} color="red" />
              <ActionBtn icon={<RotateCcw className="h-3.5 w-3.5" />} label="AI 재처리" onClick={actions.reprocess} color="orange" />
              <ActionBtn icon={<Search className="h-3.5 w-3.5" />} label="외부 재매칭" onClick={actions.rematch} color="blue" />
              <ActionBtn icon={<Lock className="h-3.5 w-3.5" />} label="잠금" onClick={() => void actions.lockFields(["title", "director"])} color="slate" />
              <Link
                href={`/programming/contents/${content.id}/edit`}
                className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium bg-slate-100 text-slate-700 hover:bg-slate-200"
              >
                <Edit className="h-3.5 w-3.5" />편집
              </Link>
              <ActionBtn icon={<Eye className="h-3.5 w-3.5" />} label="미리보기" onClick={onPreview} color="slate" />
              <ActionBtn icon={<Play className="h-3.5 w-3.5" />} label="Preview" onClick={() => void actions.requestPreviewClip()} color="slate" />
            </>
          )}
        </div>
      </div>
    </div>
  )
}

interface ActionBtnProps {
  icon: React.ReactNode
  label: string
  onClick: () => void
  color: "green" | "red" | "orange" | "blue" | "slate"
}

const COLOR_MAP: Record<ActionBtnProps["color"], string> = {
  green:  "bg-green-100 text-green-700 hover:bg-green-200",
  red:    "bg-red-100 text-red-700 hover:bg-red-200",
  orange: "bg-orange-100 text-orange-700 hover:bg-orange-200",
  blue:   "bg-blue-100 text-blue-700 hover:bg-blue-200",
  slate:  "bg-slate-100 text-slate-700 hover:bg-slate-200",
}

function ActionBtn({ icon, label, onClick, color }: ActionBtnProps) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium",
        COLOR_MAP[color]
      )}
    >
      {icon}{label}
    </button>
  )
}
