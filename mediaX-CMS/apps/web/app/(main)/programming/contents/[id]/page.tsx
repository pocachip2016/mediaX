"use client"

import { useEffect, useState } from "react"
import { useParams, useRouter, useSearchParams } from "next/navigation"
import Link from "next/link"
import {
  ArrowLeft, Check, X, RotateCcw, Eye, AlertCircle, Film, ChevronDown, Sparkles,
} from "lucide-react"
import { cn } from "@workspace/ui/lib/utils"
import Image from "next/image"
import { metadataApi, imageMetaApi, posterRecommendApi, damApi, type ContentDetail, type ImageMetaOut, type PosterCandidateOut, type RecommendationsOut, type FieldRecommendation, type SourceFieldRec, type DamAssetsOut, resolvePosterUrl } from "@/lib/api"
import { SourceBadge } from "@/components/source-badge"
import { MetadataDiffPanel } from "@/components/contents/MetadataDiffPanel"
import { MetadataEnrichPanel } from "@/components/contents/MetadataEnrichPanel"
import { VisualAssetCandidatePanel } from "@/components/contents/VisualAssetCandidatePanel"

type TabName = "text" | "image" | "video" | "sources" | "assets" | "ai"


const STATUS_BADGE: Record<string, { label: string; emoji: string; color: string }> = {
  waiting: { label: "대기", emoji: "⏳", color: "bg-slate-100 text-slate-600" },
  processing: { label: "처리중", emoji: "🔄", color: "bg-blue-100 text-blue-700" },
  staging: { label: "검토대기", emoji: "📋", color: "bg-violet-100 text-violet-700" },
  review: { label: "검수", emoji: "🟧", color: "bg-amber-100 text-amber-700" },
  approved: { label: "승인됨", emoji: "✓", color: "bg-green-100 text-green-700" },
  rejected: { label: "반려됨", emoji: "✗", color: "bg-red-100 text-red-700" },
}

const TAB_META = {
  text: { label: "글자", status: "completed" as const },
  image: { label: "이미지", status: "completed" as const },
  video: { label: "영상", status: "pending" as const },
  sources: { label: "외부소스", count: 3 },
  assets: { label: "에셋" },
  ai: { label: "AI 이력", count: 8 },
}

function TabStatusBadge({ tab }: { tab: "text" | "image" | "video" }) {
  const status = TAB_META[tab].status
  const icon = status === "completed" ? "●" : "○"
  const color = status === "completed" ? "text-green-600" : "text-gray-400"
  return <span className={color}>{icon}</span>
}

function TabCountBadge({ tab }: { tab: "sources" | "ai" }) {
  const count = TAB_META[tab].count
  return <span className="text-xs font-medium text-slate-500 ml-2">{count}</span>
}

function MissingBadge() {
  return (
    <span className="text-xs text-slate-400 border border-dashed border-slate-200 rounded px-1.5 py-0.5">
      Missing
    </span>
  )
}

export default function ContentDetailPage() {
  const params = useParams()
  const router = useRouter()
  const searchParams = useSearchParams()
  const contentId = Number(params.id)
  
  const [content, setContent] = useState<ContentDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<TabName>("text")
  const [selectedSynopsis, setSelectedSynopsis] = useState<"cp" | "ai" | "tmdb" | "manual">("ai")
  const [changelog, setChangelog] = useState<any>(null)
  const [damAssets, setDamAssets] = useState<DamAssetsOut | null>(null)
  const [damRetry, setDamRetry] = useState(0)
  const [imageMeta, setImageMeta] = useState<ImageMetaOut | null>(null)
  const [posterCandidates, setPosterCandidates] = useState<PosterCandidateOut[] | null>(null)

  const [castExpanded, setCastExpanded] = useState(false)
  const [recommendations, setRecommendations] = useState<RecommendationsOut | null>(null)
  const [recDismissed, setRecDismissed] = useState(false)
  const [showEnrich, setShowEnrich] = useState(false)

  useEffect(() => {
    const fetchContent = async () => {
      try {
        const data = await metadataApi.getContent(contentId)
        setContent(data)
      } catch (error) {
        console.error("Failed to fetch content:", error)
      } finally {
        setLoading(false)
      }
    }
    fetchContent()
  }, [contentId])

  // Auto-enable EnrichPanel when enrich=true query param present
  useEffect(() => {
    if (searchParams.get("enrich") === "true") {
      setShowEnrich(true)
    }
  }, [searchParams])

  // Load changelog when ai tab becomes active
  useEffect(() => {
    if (activeTab === "ai") {
      handleLoadChangelog()
    }
  }, [activeTab])

  // Load image meta + poster candidates when image tab becomes active
  useEffect(() => {
    if (activeTab === "image") {
      imageMetaApi.get(contentId).then(setImageMeta).catch(() => setImageMeta(null))
      posterRecommendApi.getCandidates(contentId).then(setPosterCandidates).catch(() => setPosterCandidates(null))
    }
  }, [activeTab, contentId])

  // Load dam assets when assets tab becomes active (or retry button clicked)
  useEffect(() => {
    if (activeTab === "assets") {
      setDamAssets(null)
      damApi.getAssetsByContent(contentId)
        .then(setDamAssets)
        .catch(() => setDamAssets({ content_id: contentId, assets: [], dam_available: false }))
    }
  }, [activeTab, contentId, damRetry])

  // Load meta recommendations on mount (mock fallback when backend unavailable)
  useEffect(() => {
    metadataApi.getRecommendations(contentId).then(setRecommendations).catch(() => {
      setRecommendations({
        content_id: contentId,
        missing_fields: ["cast", "synopsis", "runtime", "country"],
        auto_fill: [
          {
            field: "cast",
            status: "auto",
            recommendations: [{ source_type: "watcha", source_id: 1, value: "김설현 · 오정세 · 유재명 외 12명", confidence: 1.0 }],
            ai_synthesis: null,
          },
          {
            field: "runtime",
            status: "auto",
            recommendations: [{ source_type: "tmdb", source_id: 2, value: "132분", confidence: 0.94 }],
            ai_synthesis: null,
          },
          {
            field: "country",
            status: "auto",
            recommendations: [{ source_type: "tmdb", source_id: 2, value: "대한민국", confidence: 0.94 }],
            ai_synthesis: null,
          },
        ],
        conflicts: [
          {
            field: "synopsis",
            status: "conflict",
            recommendations: [
              { source_type: "watcha", source_id: 1, value: "가난한 박씨 가족은 부잣집에 하나 둘씩 취업하며 묘한 공생 관계를 형성해간다.", confidence: 0.5 },
              { source_type: "tmdb", source_id: 2, value: "A poor family schemes to become employed by a wealthy Park family and infiltrates their home.", confidence: 0.94 },
            ],
            ai_synthesis: {
              source_type: "ai", source_id: 99,
              value: "경제적으로 어려운 박씨 일가는 재벌 박 사장 가족의 집에 한 명씩 취업하며 공생 관계를 형성해가지만, 숨겨진 비밀이 드러나면서 예기치 못한 사건이 벌어진다.",
              confidence: 0.79,
            },
          },
        ],
      })
    })
  }, [contentId])

  if (loading) {
    return <div className="p-6 text-center text-slate-600">로드 중...</div>
  }

  if (!content) {
    return <div className="p-6 text-center text-slate-600">콘텐츠를 찾을 수 없습니다.</div>
  }

  // Handler for recommendation apply
  const handleApplyRec = async (rec: FieldRecommendation, sourceRec: SourceFieldRec) => {
    try {
      if (sourceRec.source_type === "ai") {
        await metadataApi.promoteAIResult(contentId, sourceRec.source_id)
      } else {
        await metadataApi.applyExternalFields(contentId, sourceRec.source_id, [rec.field])
      }
      const [updated, updatedRecs] = await Promise.all([
        metadataApi.getContent(contentId),
        metadataApi.getRecommendations(contentId),
      ])
      setContent(updated)
      setRecommendations(updatedRecs)
    } catch (err) {
      console.error("apply rec failed", err)
    }
  }

  const handleApplyAllAuto = async () => {
    if (!recommendations) return
    for (const rec of recommendations.auto_fill) {
      const top = rec.recommendations[0]
      if (top) await handleApplyRec(rec, top)
    }
  }

  const handleApplyMultiple = async (targets: Array<{ rec: FieldRecommendation; source: SourceFieldRec }>) => {
    for (const { rec, source } of targets) {
      await handleApplyRec(rec, source)
    }
  }

  const handleRegenerate = async () => {
    try {
      await metadataApi.triggerEnrich(contentId)
      alert("AI 재분석 요청이 전송됐습니다. 잠시 후 새로고침하세요.")
    } catch {
      alert("재분석 요청에 실패했습니다.")
    }
  }

  // Handler for partialReprocess (AI 재처리)
  const handlePartialReprocess = async () => {
    try {
      await metadataApi.partialReprocess(contentId)
      alert("AI 재처리 요청이 전송되었습니다.")
    } catch (error) {
      console.error("AI 재처리 실패:", error)
      alert("AI 재처리에 실패했습니다.")
    }
  }

  // Handler for applyExternalFields (필드별 가져오기)
  const handleApplyExternalFields = async (sourceId: number) => {
    try {
      await metadataApi.applyExternalFields(contentId, sourceId, ["title", "director"])
      alert("필드가 적용되었습니다.")
    } catch (error) {
      console.error("필드 적용 실패:", error)
      alert("필드 적용에 실패했습니다.")
    }
  }

  // Handler for promoteAIResult (채택)
  const handlePromoteAIResult = async (resultId: number) => {
    try {
      await metadataApi.promoteAIResult(contentId, resultId)
      alert("AI 결과가 채택되었습니다.")
    } catch (error) {
      console.error("AI 결과 채택 실패:", error)
      alert("AI 결과 채택에 실패했습니다.")
    }
  }

  // Handler for getChangelog (변경 이력 조회)
  const handleLoadChangelog = async () => {
    try {
      const data = await metadataApi.getChangelog(contentId)
      setChangelog(data)
    } catch (error) {
      console.error("변경 이력 조회 실패:", error)
    }
  }

  // Handler for lockFields (필드 잠금)
  const handleLockFields = async () => {
    try {
      await metadataApi.lockFields(contentId, ["title", "director"], "품질 검증 완료")
      alert("필드가 잠금 처리되었습니다.")
    } catch (error) {
      console.error("필드 잠금 실패:", error)
      alert("필드 잠금에 실패했습니다.")
    }
  }

  // Handler for requestPreviewClip (Preview clip 요청)
  const handleRequestPreviewClip = async () => {
    try {
      await metadataApi.requestPreviewClip(contentId)
      alert("Preview clip 생성이 요청되었습니다.")
    } catch (error) {
      console.error("Preview clip 요청 실패:", error)
      alert("Preview clip 요청에 실패했습니다.")
    }
  }

  const statusInfo = (STATUS_BADGE[content.status] ?? STATUS_BADGE.waiting)!
  const qualityScore = content.quality_score ?? 0
  const posterSrc = resolvePosterUrl(content.poster_url)
  const contentTypeLabel =
    content.content_type === "movie" ? "영화"
    : content.content_type === "series" ? "시리즈"
    : content.content_type === "season" ? "시즌"
    : "에피소드"

  const directors = content.credits.filter(
    (c) => c.role.toLowerCase().includes("director") || c.role === "감독"
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

  const recCurrentValues: Record<string, string | null> = {
    synopsis,
    cast: leads.map((c) => c.person.name_ko).join(" · ") || null,
    runtime: content.runtime_minutes ? `${content.runtime_minutes}분` : null,
    country: content.country ?? null,
  }

  return (
    <div className="min-h-screen bg-slate-50 p-6">
      <div className="mb-6">
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
                <button onClick={handlePartialReprocess} className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-orange-100 text-orange-700 font-medium hover:bg-orange-200 text-sm">
                  <RotateCcw className="h-4 w-4" />
                  AI 재처리
                </button>
                <button className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-blue-100 text-blue-700 font-medium hover:bg-blue-200 text-sm">
                  <Eye className="h-4 w-4" />
                  외부 재매칭
                </button>
                <button onClick={handleLockFields} className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-100 text-slate-700 font-medium hover:bg-slate-200 text-sm">
                  🔒 잠금
                </button>
                <button onClick={handleRequestPreviewClip} className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-100 text-slate-700 font-medium hover:bg-slate-200 text-sm">
                  <Film className="h-4 w-4" />
                  Preview clip
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 추천 패널 */}
      {recommendations && !recDismissed && (recommendations.auto_fill.length > 0 || recommendations.conflicts.length > 0) && (
        <div className="mt-4 space-y-2">
          {/* 뷰 토글 */}
          <div className="flex justify-end">
            <button
              onClick={() => setShowEnrich((v) => !v)}
              className={cn(
                "flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border transition-colors",
                showEnrich
                  ? "border-blue-300 bg-blue-50 text-blue-700"
                  : "border-slate-200 bg-white text-slate-500 hover:border-blue-200 hover:text-blue-600"
              )}
            >
              <Sparkles className="h-3 w-3" />
              {showEnrich ? "테이블 보기" : "AI Enrich"}
            </button>
          </div>

          {showEnrich ? (
            <MetadataEnrichPanel
              recommendations={recommendations}
              currentValues={recCurrentValues}
              onApply={handleApplyRec}
              onApplyAll={handleApplyMultiple}
              onRegenerate={handleRegenerate}
              onDismiss={() => setRecDismissed(true)}
            />
          ) : (
            <MetadataDiffPanel
              recommendations={recommendations}
              currentValues={recCurrentValues}
              onDismiss={() => setRecDismissed(true)}
              onApply={handleApplyRec}
              onApplyAll={handleApplyAllAuto}
              onEditManually={(field) => console.log("edit manually:", field)}
            />
          )}
        </div>
      )}
      </div>

      {/* 출연진 섹션 */}
      {content.credits.length > 0 && (() => {
        const sorted = [...content.credits].sort((a, b) => {
          if (a.cast_order == null && b.cast_order == null) return 0
          if (a.cast_order == null) return 1
          if (b.cast_order == null) return -1
          return a.cast_order - b.cast_order
        })
        const PREVIEW = 8
        const visible = castExpanded ? sorted : sorted.slice(0, PREVIEW)
        return (
          <div className="mb-6 bg-white rounded-lg border border-slate-200 p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold text-slate-900">출연진 ({content.credits.length})</h2>
              {sorted.length > PREVIEW && (
                <button
                  onClick={() => setCastExpanded((v) => !v)}
                  className="inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 font-medium"
                >
                  {castExpanded ? "접기" : "전체 보기"}
                  <ChevronDown className={cn("h-3.5 w-3.5 transition-transform", castExpanded && "rotate-180")} />
                </button>
              )}
            </div>
            <div className="grid grid-cols-4 gap-3 sm:grid-cols-6 lg:grid-cols-8">
              {visible.map((credit) => (
                <div key={credit.id} className="flex flex-col items-center gap-1.5 text-center">
                  <div className="w-12 h-12 rounded-full bg-slate-200 flex items-center justify-center text-slate-500 font-semibold text-sm flex-shrink-0">
                    {credit.person.name_ko.charAt(0)}
                  </div>
                  <div className="w-full">
                    <p className="text-xs font-medium text-slate-800 truncate leading-tight">{credit.person.name_ko}</p>
                    <p className="text-[10px] text-slate-500 truncate leading-tight mt-0.5">
                      {credit.character_name ?? credit.role}
                    </p>
                    {credit.source && (
                      <div className="mt-1 flex justify-center">
                        <SourceBadge source={credit.source} />
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )
      })()}

      {/* Tabs */}
      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
        <div className="border-b border-slate-200 flex gap-4 px-6">
          {(["text", "image", "video", "sources", "assets", "ai"] as TabName[]).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={cn(
                "px-4 py-3 font-medium border-b-2 transition-colors text-sm flex items-center gap-2",
                activeTab === tab ? "border-blue-500 text-blue-600" : "border-transparent text-slate-600 hover:text-slate-900",
              )}
            >
              {tab === "text" && <TabStatusBadge tab="text" />}
              {tab === "image" && <TabStatusBadge tab="image" />}
              {tab === "video" && <TabStatusBadge tab="video" />}
              {TAB_META[tab].label}
              {(tab === "sources" || tab === "ai") && <TabCountBadge tab={tab} />}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        <div className="p-6">
          {activeTab === "text" && (
            <div className="space-y-6">
              <div>
                <h3 className="font-semibold text-slate-900 mb-3">시놉시스</h3>
                <div className="grid grid-cols-3 gap-4">
                  {/* CP 시놉시스 */}
                  <div className="border border-slate-200 rounded-lg p-4 bg-slate-50">
                    <div className="flex items-center gap-2 mb-2">
                      <SourceBadge source="cp" score={100} />
                    </div>
                    <p className="text-sm text-slate-500">(없음)</p>
                    <input type="radio" name="synopsis" disabled className="mt-3" />
                  </div>

                  {/* AI 시놉시스 */}
                  <div className={cn("border-2 rounded-lg p-4", selectedSynopsis === "ai" ? "border-blue-400 bg-blue-50" : "border-slate-200 bg-white")}>
                    <div className="flex items-center justify-between mb-2">
                      <SourceBadge source="ai" score={89} />
                      <span className="inline-block px-2 py-0.5 rounded bg-green-100 text-green-700 text-xs">자동</span>
                    </div>
                    <p className="text-sm text-slate-700 mb-3">가난한 가족이 부유한 가족의 집에 침투하면서...</p>
                    <div className="mt-3">
                      <input
                        type="radio"
                        name="synopsis"
                        checked={selectedSynopsis === "ai"}
                        onChange={() => setSelectedSynopsis("ai")}
                        className="cursor-pointer"
                      />
                      <label className="ml-2 text-sm text-slate-700">사용</label>
                    </div>
                  </div>

                  {/* TMDB 시놉시스 */}
                  <div className={cn("border-2 rounded-lg p-4", selectedSynopsis === "tmdb" ? "border-blue-400 bg-blue-50" : "border-slate-200 bg-white")}>
                    <div className="flex items-center gap-2 mb-2">
                      <SourceBadge source="tmdb" score={0.94} />
                    </div>
                    <p className="text-sm text-slate-700 mb-3">A poor family schemes to become employed by a wealthy...</p>
                    <div className="mt-3">
                      <input
                        type="radio"
                        name="synopsis"
                        checked={selectedSynopsis === "tmdb"}
                        onChange={() => setSelectedSynopsis("tmdb")}
                        className="cursor-pointer"
                      />
                      <label className="ml-2 text-sm text-slate-700">사용</label>
                    </div>
                  </div>
                </div>
                <div className="mt-3 flex gap-2">
                  <button className="text-sm text-blue-600 hover:text-blue-700 font-medium">✏ 직접 작성</button>
                  <button className="text-sm text-blue-600 hover:text-blue-700 font-medium">↻ AI 재생성</button>
                </div>
              </div>

              <div>
                <h3 className="font-semibold text-slate-900 mb-3">장르</h3>
                <div className="flex gap-2 flex-wrap">
                  {content.genres.length > 0 ? (
                    content.genres.map((g) => (
                      <span key={g.genre.id} className={cn(
                        "inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium bg-slate-50 border border-slate-200",
                        g.is_primary && "border-blue-300 bg-blue-50 text-blue-800",
                      )}>
                        {g.genre.name_ko}
                        {g.source && <SourceBadge source={g.source} />}
                      </span>
                    ))
                  ) : (
                    <>
                      <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full border border-slate-200 bg-slate-50 text-sm">
                        드라마 <SourceBadge source="tmdb" score={0.91} />
                      </span>
                      <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full border border-slate-200 bg-slate-50 text-sm">
                        스릴러 <SourceBadge source="ai" score={0.84} />
                      </span>
                    </>
                  )}
                  <button className="px-3 py-1 rounded-full border border-dashed border-slate-300 text-slate-600 text-sm hover:bg-slate-50">
                    + 추가
                  </button>
                </div>
              </div>

              <div className="pt-4 border-t border-slate-200 flex gap-2 justify-end">
                <button className="px-4 py-2 rounded-lg border border-slate-200 text-slate-700 font-medium hover:bg-slate-50">
                  💾 임시 저장
                </button>
                <button className="px-4 py-2 rounded-lg bg-green-100 text-green-700 font-medium hover:bg-green-200">
                  💾 저장 후 글자 메타 완료
                </button>
              </div>
            </div>
          )}

          {activeTab === "image" && (
            <div className="space-y-4">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold text-slate-900">이미지</h3>
              </div>
              {!imageMeta ? (
                <div className="grid grid-cols-5 gap-4">
                  {(["poster", "thumbnail", "stillcut", "banner", "logo"] as const).map((type) => (
                    <div key={type} className="border border-slate-200 rounded-lg overflow-hidden">
                      <div className="aspect-[3/4] bg-gradient-to-br from-slate-100 to-slate-200 flex items-center justify-center animate-pulse">
                        <Film className="h-8 w-8 text-slate-300" />
                      </div>
                      <div className="p-2 text-xs text-slate-400">{type}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="space-y-6">
                  {(["poster", "thumbnail", "stillcut", "banner", "logo"] as const).map((type) => {
                    const typeImages = imageMeta.images.filter((img) => img.image_type === type)

                    if (type === "poster") {
                      const displayCandidates: PosterCandidateOut[] = posterCandidates ?? typeImages.map((img) => ({
                        id: img.id, url: img.url, source: img.source ?? "", is_primary: false,
                        width: img.width ?? undefined, height: img.height ?? undefined,
                      }))
                      const primaryId = displayCandidates.find((c) => c.is_primary)?.id ?? null
                      return (
                        <div key="poster">
                          <VisualAssetCandidatePanel
                            contentId={contentId}
                            candidates={displayCandidates}
                            primaryId={primaryId}
                            onRecommend={async () => {
                              await posterRecommendApi.recommend(contentId)
                              const updated = await posterRecommendApi.getCandidates(contentId)
                              setPosterCandidates(updated)
                            }}
                            onSelectPrimary={async (imageId) => {
                              const updated = await posterRecommendApi.selectPrimary(contentId, imageId)
                              setPosterCandidates(updated)
                            }}
                          />
                        </div>
                      )
                    }

                    return (
                      <div key={type}>
                        <h4 className="text-xs font-semibold text-slate-500 uppercase mb-2">{type}</h4>
                        {typeImages.length === 0 ? (
                          <div className="border border-dashed border-slate-200 rounded-lg aspect-[3/4] w-24 flex items-center justify-center">
                            <Film className="h-6 w-6 text-slate-300" />
                          </div>
                        ) : (
                          <div className="flex gap-3 flex-wrap">
                            {typeImages.map((img) => {
                              const src = resolvePosterUrl(img.url)
                              return (
                                <div key={img.id} className="border border-slate-200 rounded-lg overflow-hidden hover:border-blue-400 transition-colors w-24">
                                  <div className="aspect-[3/4] bg-slate-100 flex items-center justify-center">
                                    {src ? (
                                      <Image src={src} alt={type} width={96} height={128} unoptimized className="object-cover w-full h-full" />
                                    ) : (
                                      <Film className="h-6 w-6 text-slate-300" />
                                    )}
                                  </div>
                                  <div className="p-1.5 text-xs text-slate-600 truncate">
                                    <span className="font-medium">{img.source ?? "—"}</span>
                                  </div>
                                </div>
                              )
                            })}
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )}

          {activeTab === "video" && (
            <div className="space-y-4">
              <div className="border border-slate-200 rounded-lg p-4 bg-slate-50">
                <h3 className="font-semibold text-slate-900 mb-4">영상 파일 정보</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs font-medium text-slate-600">해상도</label>
                    <select className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg">
                      <option>4K</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-xs font-medium text-slate-600">포맷</label>
                    <select className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg">
                      <option>MP4</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-xs font-medium text-slate-600">비디오 코덱</label>
                    <select className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg">
                      <option>H.265</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-xs font-medium text-slate-600">오디오 코덱</label>
                    <select className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg">
                      <option>AAC</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-xs font-medium text-slate-600">비트레이트</label>
                    <input type="number" value="12000" className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg" />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-slate-600">길이</label>
                    <input type="text" value="02:12:00" className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg" />
                  </div>
                </div>
              </div>

              <div className="border border-yellow-200 bg-yellow-50 rounded-lg p-3 flex gap-2 text-sm text-yellow-700">
                <AlertCircle className="h-4 w-4 flex-shrink-0 mt-0.5" />
                <span>자동 감지: ffprobe 미실행</span>
              </div>
            </div>
          )}

          {activeTab === "sources" && (
            <div className="space-y-4">
              <h3 className="font-semibold text-slate-900">매칭된 외부 소스 (3)</h3>

              <div className="border border-slate-200 rounded-lg p-4">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <span className="inline-block px-2 py-1 rounded-full bg-blue-100 text-blue-700 font-medium text-sm">[TMDB]</span>
                    <span className="ml-2 text-xs text-slate-600">id: 496243 match .94</span>
                  </div>
                </div>
                <p className="text-sm text-slate-600 mb-3">title: Parasite</p>
                <button className="text-sm text-blue-600 hover:text-blue-700 font-medium" onClick={() => handleApplyExternalFields(1)}>
                  📋 필드별 가져오기
                </button>
              </div>

              <div className="border border-slate-200 rounded-lg p-4">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <span className="inline-block px-2 py-1 rounded-full bg-green-100 text-green-700 font-medium text-sm">[KOBIS]</span>
                    <span className="ml-2 text-xs text-slate-600">movieCd: 20183782 match .87</span>
                  </div>
                </div>
                <p className="text-sm text-slate-600 mb-3">영화명: 기생충, 감독: 봉준호</p>
                <button className="text-sm text-blue-600 hover:text-blue-700 font-medium" onClick={() => handleApplyExternalFields(2)}>
                  📋 필드별 가져오기
                </button>
              </div>

              <div className="border border-yellow-200 bg-yellow-50 rounded-lg p-4">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <span className="inline-block px-2 py-1 rounded-full bg-yellow-100 text-yellow-700 font-medium text-sm">[Watcha]</span>
                    <span className="ml-2 text-xs text-yellow-700">id: 12wgQ34 match .79 ⚠</span>
                  </div>
                </div>
                <p className="text-sm text-yellow-700">⚠ 낮은 신뢰도 — 등급/연도 불일치 가능. 검수 권장.</p>
                <button className="text-sm text-blue-600 hover:text-blue-700 font-medium mt-2" onClick={() => handleApplyExternalFields(3)}>
                  📋 필드별 가져오기
                </button>
              </div>
            </div>
          )}

          {activeTab === "assets" && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="font-semibold text-slate-900">Dam Assets</h3>
                <button
                  onClick={() => setDamRetry((n) => n + 1)}
                  className="text-xs text-slate-400 hover:text-slate-600 flex items-center gap-1"
                >
                  <RotateCcw className="h-3 w-3" /> 새로고침
                </button>
              </div>
              {!damAssets ? (
                <p className="text-slate-500 text-sm text-center py-8">로딩 중...</p>
              ) : !damAssets.dam_available ? (
                <div className="text-center py-8 space-y-2">
                  <p className="text-amber-600 text-sm">DAM 미가용 — 연결을 확인하세요.</p>
                  <button
                    onClick={() => setDamRetry((n) => n + 1)}
                    className="text-xs px-3 py-1.5 rounded border border-amber-200 text-amber-700 hover:bg-amber-50 transition-colors"
                  >
                    재시도
                  </button>
                </div>
              ) : damAssets.assets.length === 0 ? (
                <p className="text-slate-500 text-sm text-center py-8">연결된 Dam 에셋 없음</p>
              ) : (
                <div className="grid grid-cols-3 gap-4">
                  {damAssets.assets.map((asset) => (
                    <div key={asset.asset_id} className="border border-slate-200 rounded-lg overflow-hidden hover:border-blue-300 transition-colors">
                      <div className="h-32 bg-slate-100 overflow-hidden flex items-center justify-center">
                        <img
                          src={asset.thumbnail_url}
                          alt={asset.filename}
                          className="w-full h-full object-cover"
                          onError={(e) => { (e.target as HTMLImageElement).style.display = "none" }}
                        />
                      </div>
                      <div className="p-2 space-y-0.5">
                        <p className="text-xs font-medium truncate">{asset.filename}</p>
                        {asset.status && (
                          <span className="text-[10px] px-1 py-0.5 rounded bg-slate-100 text-slate-500">{asset.status}</span>
                        )}
                        {asset.confidence != null && (
                          <p className="text-[10px] text-slate-400">{(asset.confidence * 100).toFixed(0)}% match</p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {activeTab === "ai" && (
            <div className="space-y-4">
              <h3 className="font-semibold text-slate-900 mb-4">AI 처리 이력 (8)</h3>

              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 border-b border-slate-200">
                    <tr>
                      <th className="px-3 py-2 text-left font-semibold text-slate-600">처리 시각</th>
                      <th className="px-3 py-2 text-left font-semibold text-slate-600">엔진</th>
                      <th className="px-3 py-2 text-left font-semibold text-slate-600">태스크</th>
                      <th className="px-3 py-2 text-left font-semibold text-slate-600">점수</th>
                      <th className="px-3 py-2 text-left font-semibold text-slate-600">액션</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200">
                    {[
                      { time: "2026-05-13 14:30", engine: "gemini", task: "synopsis", score: 89, current: true },
                      { time: "2026-05-13 14:30", engine: "groq", task: "synopsis", score: 82, current: false },
                      { time: "2026-05-13 14:30", engine: "gemini", task: "genre", score: 91, current: true },
                      { time: "2026-05-13 14:30", engine: "gemini", task: "tagging", score: 84, current: true },
                    ].map((row, i) => (
                      <tr key={i} className={row.current ? "bg-green-50" : "hover:bg-slate-50"}>
                        <td className="px-3 py-2 text-slate-700">{row.time}</td>
                        <td className="px-3 py-2 text-slate-700">{row.engine}</td>
                        <td className="px-3 py-2 text-slate-700">{row.task}</td>
                        <td className="px-3 py-2 font-medium text-slate-900">{row.score}</td>
                        <td className="px-3 py-2 text-right">
                          {row.current ? (
                            <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-green-100 text-green-700 text-xs font-medium">
                              ● 현재 채택
                            </span>
                          ) : (
                            <button onClick={() => handlePromoteAIResult(i)} className="text-blue-600 hover:text-blue-700 text-xs font-medium">채택</button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
