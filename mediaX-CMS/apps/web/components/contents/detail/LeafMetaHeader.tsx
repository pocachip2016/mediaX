"use client"

import Link from "next/link"
import { ArrowLeft, Check, X, RotateCcw, Eye, Film, Sparkles } from "lucide-react"
import { cn } from "@workspace/ui/lib/utils"
import type { ContentDetail } from "@/lib/api"
import { resolvePosterUrl } from "@/lib/api"
import { SourceBadge } from "@/components/source-badge"
import { TYPE_LABEL } from "./contentType"

function MissingBadge() {
  return (
    <span className="text-xs text-slate-400 border border-dashed border-slate-200 rounded px-1.5 py-0.5">
      Missing
    </span>
  )
}

export interface StatusInfo {
  label: string
  emoji: string
  color: string
}

interface LeafMetaHeaderProps {
  content: ContentDetail
  contentId: number
  statusInfo: StatusInfo
  qualityScore: number
  onReprocess: () => void
  onLock: () => void
  onPreviewClip: () => void
}

export function LeafMetaHeader({
  content, contentId, statusInfo, qualityScore,
  onReprocess, onLock, onPreviewClip,
}: LeafMetaHeaderProps) {
  const posterSrc = resolvePosterUrl(content.poster_url)
  const contentTypeLabel = TYPE_LABEL[content.content_type]

  const directors = content.credits.filter(
    (c) => c.role.toLowerCase().includes("director") || c.role === "감독",
  )
  const leads = content.credits
    .filter((c) => ["actor", "cast", "주연", "출연"].includes(c.role.toLowerCase()))
    .sort((a, b) => (a.cast_order ?? 99) - (b.cast_order ?? 99))
    .slice(0, 3)
  const synopsis =
    content.metadata_record?.final_synopsis ||
    content.metadata_record?.ai_synopsis ||
    content.metadata_record?.cp_synopsis ||
    null

  return (
    <div className="bg-white rounded-lg border border-slate-200 p-6">
      <div className="flex gap-6">
        {/* 포스터 (2:3 비율) */}
        <div className="flex-shrink-0 w-44">
          <div className="aspect-[2/3] rounded-xl overflow-hidden bg-slate-100 flex items-center justify-center shadow-sm">
            {posterSrc ? (
              <img src={posterSrc} alt={content.title} className="w-full h-full object-cover" />
            ) : (
              <Film className="h-12 w-12 text-slate-300" />
            )}
          </div>
        </div>

        {/* 메타 정보 */}
        <div className="flex-1 min-w-0 flex flex-col">
          {/* 제목 */}
          <div className="flex items-start gap-3 min-w-0 mb-2">
            <Link href="/programming/contents" className="text-slate-400 hover:text-slate-600 mt-1 flex-shrink-0">
              <ArrowLeft className="h-5 w-5" />
            </Link>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 mb-1">
                <h1 className="text-2xl font-bold text-slate-900 leading-tight">{content.title}</h1>
                <Link
                  href={`/programming/contents/${contentId}/recommend?return=list`}
                  className="shrink-0 inline-flex items-center gap-1.5 px-3 py-1 rounded-md bg-violet-100 text-violet-700 text-xs font-medium hover:bg-violet-200"
                >
                  <Sparkles className="h-3.5 w-3.5" />
                  추천 검수
                </Link>
              </div>
              {content.original_title && (
                <p className="text-slate-500 text-sm mt-0.5">{content.original_title}</p>
              )}
            </div>
          </div>

          {/* 장르 칩 */}
          {content.genres.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mb-2">
              {content.genres.map((g) => (
                <span
                  key={g.genre.id}
                  className={cn(
                    "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-sm font-medium bg-slate-50 border border-slate-200",
                    g.is_primary && "border-blue-300 bg-blue-50 text-blue-800",
                  )}
                >
                  {g.genre.name_ko}
                  {g.source && <SourceBadge source={g.source} />}
                </span>
              ))}
            </div>
          )}

          {/* 기본 메타 필드 */}
          <div className="flex flex-wrap gap-x-5 gap-y-1 text-sm text-slate-600 mb-3">
            <span className="inline-flex items-center gap-1">
              <span className="text-slate-400">유형</span> {contentTypeLabel}
            </span>
            {content.production_year && (
              <span className="inline-flex items-center gap-1">
                <span className="text-slate-400">📅</span> {content.production_year}
              </span>
            )}
            {content.cp_name && (
              <span className="inline-flex items-center gap-1">
                <span className="text-slate-400">🏢</span> {content.cp_name}
              </span>
            )}
            <span className="inline-flex items-center gap-1">
              <span className="text-slate-400">⏱</span>
              {content.runtime_minutes ? `${content.runtime_minutes}분` : <MissingBadge />}
            </span>
            <span className="inline-flex items-center gap-1">
              <span className="text-slate-400">🌐</span>
              {content.country || <MissingBadge />}
            </span>
          </div>

          {/* 감독 / 주연 / 줄거리 */}
          <div className="space-y-1.5 mb-3 text-sm">
            <div className="flex gap-2 items-center">
              <span className="text-slate-400 w-10 flex-shrink-0">감독</span>
              {directors.length > 0
                ? <span className="text-slate-800">{directors.map((d) => d.person.name_ko).join(" · ")}</span>
                : <MissingBadge />}
            </div>
            <div className="flex gap-2 items-center">
              <span className="text-slate-400 w-10 flex-shrink-0">주연</span>
              {leads.length > 0
                ? <span className="text-slate-800">{leads.map((l) => l.person.name_ko).join(" · ")}</span>
                : <MissingBadge />}
            </div>
            <div className="flex gap-2 items-start">
              <span className="text-slate-400 w-10 flex-shrink-0 mt-0.5">줄거리</span>
              {synopsis
                ? <p className="text-slate-700 leading-snug line-clamp-2">{synopsis}</p>
                : <MissingBadge />}
            </div>
          </div>

          {/* 검수 상태 · 품질 점수 · 액션 버튼 */}
          <div className="mt-auto pt-3 border-t border-slate-100">
            <div className="flex items-center gap-3 mb-2.5">
              <div className={cn("inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium", statusInfo.color)}>
                {statusInfo.emoji} {statusInfo.label}
              </div>
              <span className="text-slate-400 text-xs">#{content.id}</span>
              <div className="flex-1 flex items-center gap-2 ml-2">
                <div className="flex-1 bg-slate-200 rounded-full h-1.5 overflow-hidden">
                  <div className="bg-amber-500 h-full" style={{ width: `${qualityScore}%` }} />
                </div>
                <span className="font-bold text-sm text-amber-700 w-8 text-right">{qualityScore}</span>
              </div>
            </div>
            <div className="flex gap-2 flex-wrap">
              <Link
                href={`/programming/contents/${content.id}/edit`}
                className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-100 text-slate-700 font-medium hover:bg-slate-200 text-sm"
              >
                ✏️ 편집
              </Link>
              <button className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-green-100 text-green-700 font-medium hover:bg-green-200 text-sm">
                <Check className="h-4 w-4" />
                승인
              </button>
              <button className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-red-100 text-red-700 font-medium hover:bg-red-200 text-sm">
                <X className="h-4 w-4" />
                반려
              </button>
              <button onClick={onReprocess} className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-orange-100 text-orange-700 font-medium hover:bg-orange-200 text-sm">
                <RotateCcw className="h-4 w-4" />
                AI 재처리
              </button>
              <button className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-blue-100 text-blue-700 font-medium hover:bg-blue-200 text-sm">
                <Eye className="h-4 w-4" />
                외부 재매칭
              </button>
              <button onClick={onLock} className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-100 text-slate-700 font-medium hover:bg-slate-200 text-sm">
                🔒 잠금
              </button>
              <button onClick={onPreviewClip} className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-100 text-slate-700 font-medium hover:bg-slate-200 text-sm">
                <Film className="h-4 w-4" />
                Preview clip
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
