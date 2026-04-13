"use client"

import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import Link from "next/link"
import {
  ArrowLeft, Film, Tv, Layers, Play, RefreshCw, Image as ImageIcon,
  ChevronRight, CheckCircle, AlertCircle, Clock, XCircle, Loader2,
} from "lucide-react"
import {
  metadataApi, imageMetaApi,
  type ContentOut, type ContentStatus, type ContentType,
  type StagingItem, type ImageMetaOut, type ContentImageOut, type MetadataOut,
} from "@/lib/api"

// ── 상수 ──────────────────────────────────────────────────

const STATUS_LABEL: Record<ContentStatus, string> = {
  waiting: "대기", processing: "처리중", staging: "검토대기",
  review: "검수중", approved: "완료", rejected: "반려",
}
const STATUS_CLASS: Record<ContentStatus, string> = {
  waiting:    "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400",
  processing: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  staging:    "bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-400",
  review:     "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
  approved:   "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
  rejected:   "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
}
const TYPE_LABEL: Record<ContentType, string> = {
  movie: "영화", series: "시리즈", season: "시즌", episode: "에피소드",
}
const TYPE_CLASS: Record<ContentType, string> = {
  movie:   "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  series:  "bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-400",
  season:  "bg-teal-100 text-teal-700 dark:bg-teal-900/30 dark:text-teal-400",
  episode: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
}

const IMAGE_TYPE_LABEL: Record<string, string> = {
  poster: "포스터", thumbnail: "썸네일", stillcut: "스틸컷", banner: "배너", logo: "로고",
}
const IMAGE_ASPECT: Record<string, string> = {
  poster: "aspect-[2/3]", thumbnail: "aspect-video", stillcut: "aspect-video",
  banner: "aspect-[16/3]", logo: "aspect-[5/2]",
}

function TypeIcon({ type }: { type: ContentType }) {
  if (type === "movie") return <Film className="h-4 w-4" />
  if (type === "series") return <Tv className="h-4 w-4" />
  if (type === "season") return <Layers className="h-4 w-4" />
  return <Play className="h-4 w-4" />
}

function StatusIcon({ status }: { status: ContentStatus }) {
  if (status === "approved") return <CheckCircle className="h-3.5 w-3.5" />
  if (status === "rejected") return <XCircle className="h-3.5 w-3.5" />
  if (status === "review") return <AlertCircle className="h-3.5 w-3.5" />
  return <Clock className="h-3.5 w-3.5" />
}

// ── 이미지 섹션 ───────────────────────────────────────────

function ImageSection({ imageMeta }: { imageMeta: ImageMetaOut | null }) {
  const [selectedImg, setSelectedImg] = useState<ContentImageOut | null>(null)

  if (!imageMeta || imageMeta.images.length === 0) {
    return (
      <div className="rounded-xl border border-border bg-card p-6 text-center">
        <ImageIcon className="h-8 w-8 mx-auto text-muted-foreground mb-2" />
        <p className="text-sm text-muted-foreground">등록된 이미지가 없습니다.</p>
      </div>
    )
  }

  const poster = imageMeta.images.find((i) => i.image_type === "poster")
  const others = imageMeta.images.filter((i) => i.image_type !== "poster")

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        {/* 포스터 메인 */}
        {poster && (
          <div
            className="shrink-0 w-28 rounded-xl overflow-hidden border border-border cursor-pointer hover:opacity-90 transition-opacity"
            onClick={() => setSelectedImg(poster)}
          >
            <div className="aspect-[2/3] bg-muted relative">
              <img
                src={poster.url}
                alt={poster.alt_text ?? "포스터"}
                className="w-full h-full object-cover"
                onError={(e) => { (e.target as HTMLImageElement).style.display = "none" }}
              />
            </div>
            <div className="px-2 py-1 text-center text-xs text-muted-foreground border-t border-border">포스터</div>
          </div>
        )}

        {/* 나머지 이미지들 */}
        <div className="flex-1 grid grid-cols-2 gap-2">
          {others.map((img) => (
            <div
              key={img.id}
              className="rounded-lg overflow-hidden border border-border cursor-pointer hover:opacity-90 transition-opacity"
              onClick={() => setSelectedImg(img)}
            >
              <div className={`${IMAGE_ASPECT[img.image_type] ?? "aspect-video"} bg-muted relative`}>
                <img
                  src={img.url}
                  alt={img.alt_text ?? img.image_type}
                  className="w-full h-full object-cover"
                  onError={(e) => { (e.target as HTMLImageElement).style.display = "none" }}
                />
              </div>
              <div className="px-2 py-1 text-center text-xs text-muted-foreground border-t border-border">
                {IMAGE_TYPE_LABEL[img.image_type] ?? img.image_type}
                {img.width && img.height && (
                  <span className="ml-1 text-muted-foreground/60">{img.width}×{img.height}</span>
                )}
              </div>
            </div>
          ))}

          {/* 미등록 타입 표시 */}
          {["poster", "thumbnail", "stillcut", "banner", "logo"]
            .filter((t) => {
              const hasKey = `has_${t}` as keyof ImageMetaOut
              return !imageMeta[hasKey]
            })
            .map((t) => (
              <div key={t} className="rounded-lg border border-dashed border-border overflow-hidden opacity-50">
                <div className={`${IMAGE_ASPECT[t] ?? "aspect-video"} bg-muted/30 flex items-center justify-center`}>
                  <ImageIcon className="h-5 w-5 text-muted-foreground" />
                </div>
                <div className="px-2 py-1 text-center text-xs text-muted-foreground border-t border-border">
                  {IMAGE_TYPE_LABEL[t]} <span className="text-muted-foreground/60">미등록</span>
                </div>
              </div>
            ))
          }
        </div>
      </div>

      {/* 이미지 확대 모달 */}
      {selectedImg && (
        <div
          className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4"
          onClick={() => setSelectedImg(null)}
        >
          <div className="max-w-2xl w-full" onClick={(e) => e.stopPropagation()}>
            <img
              src={selectedImg.url}
              alt={selectedImg.alt_text ?? selectedImg.image_type}
              className="w-full rounded-xl object-contain max-h-[80vh]"
            />
            <div className="mt-2 text-center text-sm text-white/70">
              {IMAGE_TYPE_LABEL[selectedImg.image_type] ?? selectedImg.image_type}
              {selectedImg.width && selectedImg.height && ` · ${selectedImg.width}×${selectedImg.height}px`}
              {selectedImg.source && ` · ${selectedImg.source}`}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Summary 헤더 카드 (포스터 + 핵심 메타 한 줄) ──────────

function SummaryCard({
  content, metadata, imageMeta, onRefresh, loading,
}: {
  content: ContentOut
  metadata: MetadataOut | null
  imageMeta: ImageMetaOut | null
  onRefresh: () => void
  loading: boolean
}) {
  const synopsis = metadata?.final_synopsis ?? metadata?.ai_synopsis ?? metadata?.cp_synopsis
  const genre = metadata?.final_genre ?? metadata?.ai_genre_primary
  const tags = (metadata?.final_tags ?? metadata?.ai_mood_tags) as string[] | null
  const poster = imageMeta?.images.find((i) => i.image_type === "poster")

  return (
    <div className="rounded-xl border border-border bg-card overflow-hidden">
      <div className="flex items-start gap-4 p-4">
        {/* 포스터 썸네일 */}
        <div className="shrink-0 w-16 rounded-lg overflow-hidden border border-border bg-muted">
          <div className="aspect-[2/3]">
            {poster ? (
              <img
                src={poster.url}
                alt="포스터"
                className="w-full h-full object-cover"
                onError={(e) => { (e.target as HTMLImageElement).style.display = "none" }}
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center">
                <ImageIcon className="h-5 w-5 text-muted-foreground" />
              </div>
            )}
          </div>
        </div>

        {/* 제목 + 메타 */}
        <div className="flex-1 min-w-0">
          {/* 뱃지 + 새로고침 */}
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${TYPE_CLASS[content.content_type]}`}>
              <TypeIcon type={content.content_type} />
              {TYPE_LABEL[content.content_type]}
            </span>
            <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${STATUS_CLASS[content.status]}`}>
              <StatusIcon status={content.status} />
              {STATUS_LABEL[content.status]}
            </span>
            <button
              onClick={onRefresh}
              className="ml-auto p-1 rounded hover:bg-accent text-muted-foreground"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
            </button>
          </div>

          {/* 제목 */}
          <h1 className="text-lg font-bold leading-snug truncate">{content.title}</h1>
          {content.original_title && (
            <p className="text-xs text-muted-foreground truncate">{content.original_title}</p>
          )}

          {/* 핵심 메타 — 한 줄 */}
          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
            {content.cp_name && <span>{content.cp_name}</span>}
            {content.production_year && <span>{content.production_year}</span>}
            {content.country && <span>{content.country}</span>}
            {content.runtime_minutes && <span>{content.runtime_minutes}분</span>}
            {metadata?.ai_rating_suggestion && <span>{metadata.ai_rating_suggestion}</span>}
            {genre && <span className="text-foreground/70">{genre}</span>}
            {content.quality_score !== null && (
              <span className={`font-semibold ${content.quality_score >= 90 ? "text-green-600" : content.quality_score >= 70 ? "text-amber-600" : "text-red-600"}`}>
                품질 {content.quality_score.toFixed(0)}
              </span>
            )}
          </div>

          {/* 태그 */}
          {tags && tags.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {tags.map((tag) => (
                <span key={tag} className="px-1.5 py-0.5 rounded-full bg-primary/10 text-primary text-xs">{tag}</span>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 시놉시스 — 접히는 형태 */}
      {synopsis && (
        <div className="px-4 pb-3 border-t border-border pt-3">
          <p className="text-xs leading-relaxed text-muted-foreground line-clamp-3">{synopsis}</p>
        </div>
      )}
    </div>
  )
}

// ── 시즌 목록 (시리즈 전용) ────────────────────────────────

function SeasonList({ seasons }: { seasons: StagingItem[] }) {
  if (seasons.length === 0) {
    return (
      <div className="rounded-xl border border-border bg-card p-6 text-center text-sm text-muted-foreground">
        등록된 시즌이 없습니다.
      </div>
    )
  }

  return (
    <div className="rounded-xl border border-border bg-card overflow-hidden">
      <div className="px-5 py-3 border-b border-border text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        시즌 목록 ({seasons.length}개)
      </div>
      <div className="divide-y divide-border">
        {seasons.map((s) => {
          const epCount = s.children.length
          const approvedCount = s.children.filter((ep) => ep.content.status === "approved").length
          return (
            <div key={s.content.id} className="px-5 py-4 flex items-center gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-medium text-sm">{s.content.title}</span>
                  <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${STATUS_CLASS[s.content.status]}`}>
                    <StatusIcon status={s.content.status} />
                    {STATUS_LABEL[s.content.status]}
                  </span>
                </div>
                <div className="mt-1 flex items-center gap-3 text-xs text-muted-foreground">
                  {epCount > 0 && (
                    <span>
                      에피소드 {epCount}화
                      {epCount > 0 && (
                        <span className="ml-1">
                          (완료 <span className="text-green-600 font-medium">{approvedCount}</span>/{epCount})
                        </span>
                      )}
                    </span>
                  )}
                  {s.content.quality_score !== null && (
                    <span>품질 {s.content.quality_score?.toFixed(0)}</span>
                  )}
                </div>
              </div>
              <Link
                href={`/programming/contents/${s.content.id}`}
                className="shrink-0 flex items-center gap-1 px-3 py-1.5 rounded-lg border border-border text-xs hover:bg-accent transition-colors"
              >
                상세 보기 <ChevronRight className="h-3.5 w-3.5" />
              </Link>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── 에피소드 목록 (시즌 전용) ──────────────────────────────

function EpisodeList({ episodes }: { episodes: StagingItem[] }) {
  if (episodes.length === 0) {
    return (
      <div className="rounded-xl border border-border bg-card p-6 text-center text-sm text-muted-foreground">
        등록된 에피소드가 없습니다.
      </div>
    )
  }

  return (
    <div className="rounded-xl border border-border bg-card overflow-hidden">
      <div className="px-5 py-3 border-b border-border text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        에피소드 목록 ({episodes.length}화)
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/30">
              <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground w-12">화</th>
              <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground">에피소드 제목</th>
              <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground w-20">상영시간</th>
              <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground w-24">상태</th>
              <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground w-16">품질</th>
              <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground w-24">등록일</th>
            </tr>
          </thead>
          <tbody>
            {episodes.map((ep, idx) => (
              <tr
                key={ep.content.id}
                className="border-b border-border last:border-0 hover:bg-accent/30 cursor-pointer transition-colors"
              >
                <td className="px-4 py-2.5 text-xs text-muted-foreground font-medium">
                  {idx + 1}
                </td>
                <td className="px-4 py-2.5">
                  <Link
                    href={`/programming/contents/${ep.content.id}`}
                    className="block"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <div className="font-medium truncate max-w-[260px] hover:text-primary transition-colors">
                      {ep.content.title}
                    </div>
                    {ep.content.original_title && (
                      <div className="text-xs text-muted-foreground truncate max-w-[260px]">{ep.content.original_title}</div>
                    )}
                  </Link>
                </td>
                <td className="px-4 py-2.5 text-xs text-muted-foreground">
                  {ep.content.runtime_minutes ? `${ep.content.runtime_minutes}분` : "—"}
                </td>
                <td className="px-4 py-2.5">
                  <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${STATUS_CLASS[ep.content.status]}`}>
                    <StatusIcon status={ep.content.status} />
                    {STATUS_LABEL[ep.content.status]}
                  </span>
                </td>
                <td className="px-4 py-2.5">
                  {ep.content.quality_score !== null
                    ? <span className={`text-xs font-semibold ${ep.content.quality_score >= 90 ? "text-green-600" : ep.content.quality_score >= 70 ? "text-amber-600" : "text-red-600"}`}>
                        {ep.content.quality_score?.toFixed(0)}
                      </span>
                    : <span className="text-xs text-muted-foreground">—</span>
                  }
                </td>
                <td className="px-4 py-2.5 text-xs text-muted-foreground">
                  {ep.content.created_at.slice(0, 10)}
                </td>
                <td className="px-4 py-2.5 text-right">
                  <Link
                    href={`/programming/contents/${ep.content.id}`}
                    className="inline-flex items-center gap-0.5 text-xs text-muted-foreground hover:text-primary transition-colors"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <ChevronRight className="h-3.5 w-3.5" />
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── 메인 페이지 ───────────────────────────────────────────

export default function ContentDetailPage() {
  const params = useParams()
  const router = useRouter()
  const contentId = Number(params.id)

  const [loading, setLoading] = useState(true)
  const [content, setContent] = useState<ContentOut | null>(null)
  const [metadata, setMetadata] = useState<MetadataOut | null>(null)
  const [imageMeta, setImageMeta] = useState<ImageMetaOut | null>(null)
  const [hierarchy, setHierarchy] = useState<StagingItem | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    if (!contentId || isNaN(contentId)) return
    setLoading(true)
    setError(false)

    Promise.allSettled([
      metadataApi.getContent(contentId),
      imageMetaApi.get(contentId),
      metadataApi.getHierarchy(contentId),
    ]).then(([contentRes, imageRes, hierarchyRes]) => {
      if (contentRes.status === "fulfilled") {
        setContent(contentRes.value)
        setMetadata(contentRes.value.metadata_record ?? null)
      } else {
        setError(true)
      }
      if (imageRes.status === "fulfilled") setImageMeta(imageRes.value)
      if (hierarchyRes.status === "fulfilled") setHierarchy(hierarchyRes.value)
    }).finally(() => setLoading(false))
  }, [contentId])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-32">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (error || !content) {
    return (
      <div className="space-y-4">
        <button onClick={() => router.back()} className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" /> 목록으로
        </button>
        <div className="rounded-xl border border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-900/20 p-8 text-center">
          <p className="text-red-600 dark:text-red-400">콘텐츠를 불러올 수 없습니다.</p>
        </div>
      </div>
    )
  }

  const isSeries = content.content_type === "series"
  const isSeason = content.content_type === "season"
  const seasons = isSeries ? (hierarchy?.children ?? []) : []
  const episodes = isSeason ? (hierarchy?.children ?? []) : []

  const handleRefresh = () => {
    setLoading(true)
    Promise.allSettled([
      metadataApi.getContent(contentId),
      imageMetaApi.get(contentId),
      metadataApi.getHierarchy(contentId),
    ]).then(([contentRes, imageRes, hierarchyRes]) => {
      if (contentRes.status === "fulfilled") {
        setContent(contentRes.value)
        setMetadata(contentRes.value.metadata_record ?? null)
      }
      if (imageRes.status === "fulfilled") setImageMeta(imageRes.value)
      if (hierarchyRes.status === "fulfilled") setHierarchy(hierarchyRes.value)
    }).finally(() => setLoading(false))
  }

  return (
    <div className="space-y-4">
      {/* 뒤로가기 */}
      <button
        onClick={() => router.back()}
        className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft className="h-4 w-4" /> 목록으로
      </button>

      {/* Summary 카드 (포스터 + 핵심 메타) */}
      <SummaryCard
        content={content}
        metadata={metadata}
        imageMeta={imageMeta}
        onRefresh={handleRefresh}
        loading={loading}
      />

      {/* 이미지 에셋 (포스터 제외 나머지 타입) — 영화/에피소드만 */}
      {!isSeries && !isSeason && (
        <div className="space-y-2">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">이미지 에셋</h2>
          <ImageSection imageMeta={imageMeta} />
        </div>
      )}

      {/* 시리즈 → 시즌 목록 */}
      {isSeries && (
        <div className="space-y-2">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">시즌 목록</h2>
          <SeasonList seasons={seasons} />
        </div>
      )}

      {/* 시즌 → 에피소드 목록 */}
      {isSeason && (
        <div className="space-y-2">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">에피소드 목록</h2>
          <EpisodeList episodes={episodes} />
        </div>
      )}
    </div>
  )
}
