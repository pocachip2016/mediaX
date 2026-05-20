"use client"

import { useEffect, useState } from "react"
import { useParams, useRouter, useSearchParams } from "next/navigation"
import {
  AlertCircle, Film, RotateCcw,
} from "lucide-react"
import { cn } from "@workspace/ui/lib/utils"
import Image from "next/image"
import { metadataApi, imageMetaApi, posterRecommendApi, damApi, type ContentDetail, type ImageMetaOut, type PosterCandidateOut, type RecommendationsOut, type FieldRecommendation, type SourceFieldRec, type DamAssetsOut, type StagingItem, resolvePosterUrl } from "@/lib/api"
import { SourceBadge } from "@/components/source-badge"
import { VisualAssetCandidatePanel } from "@/components/contents/VisualAssetCandidatePanel"
import { DetailContainerLayout } from "@/components/contents/detail/DetailContainerLayout"
import { isLeafType } from "@/components/contents/detail/contentType"
import type { BreadcrumbParent } from "@/components/contents/detail/BreadcrumbNav"
import { ContentShell } from "@/components/contents/shell/ContentShell"
import { DetailHeader } from "@/components/contents/shell/DetailHeader"
import { ViewPane } from "@/components/contents/shell/ViewPane"

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

  const [mode, setMode] = useState<"view" | "edit" | "review">("view")
  const [recommendations, setRecommendations] = useState<RecommendationsOut | null>(null)
  const [appliedFields, setAppliedFields] = useState<Set<string>>(new Set())

  const [parentChain, setParentChain] = useState<BreadcrumbParent[]>([])
  const [childrenItems, setChildrenItems] = useState<StagingItem[]>([])
  const [childrenLoading, setChildrenLoading] = useState(false)

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

  // 부모 체인(브레드크럼) — season: [series], episode: [series, season]
  useEffect(() => {
    if (!content || content.parent_id == null) {
      setParentChain([])
      return
    }
    let cancelled = false
    const buildChain = async () => {
      const chain: BreadcrumbParent[] = []
      try {
        let pid: number | null | undefined = content.parent_id
        let guard = 0
        while (pid != null && guard < 5) {
          const p = await metadataApi.getContent(pid)
          chain.unshift({ id: p.id, title: p.title, content_type: p.content_type })
          pid = p.parent_id
          guard += 1
        }
        if (!cancelled) setParentChain(chain)
      } catch {
        if (!cancelled) setParentChain([])
      }
    }
    void buildChain()
    return () => { cancelled = true }
  }, [content])

  // Container(series/season) 자식 목록 — hierarchy 재사용
  useEffect(() => {
    if (!content || isLeafType(content.content_type)) {
      setChildrenItems([])
      return
    }
    let cancelled = false
    setChildrenLoading(true)
    metadataApi.getHierarchy(content.id)
      .then((item) => { if (!cancelled) setChildrenItems(item.children ?? []) })
      .catch(() => { if (!cancelled) setChildrenItems([]) })
      .finally(() => { if (!cancelled) setChildrenLoading(false) })
    return () => { cancelled = true }
  }, [content])


  // Load changelog when ai tab becomes active
  useEffect(() => {
    if (activeTab === "ai") {
      handleLoadChangelog()
    }
  }, [activeTab])

  // Load poster candidates on mount for ContentShell
  useEffect(() => {
    posterRecommendApi.getCandidates(contentId).then(setPosterCandidates).catch(() => setPosterCandidates(null))
  }, [contentId])

  // Load image meta when image tab becomes active
  useEffect(() => {
    if (activeTab === "image") {
      imageMetaApi.get(contentId).then(setImageMeta).catch(() => setImageMeta(null))
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
      setAppliedFields((prev) => new Set([...prev, rec.field]))
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

  // Container(series/season) → 자식 목록 레이아웃으로 디스패치
  if (!isLeafType(content.content_type)) {
    return (
      <DetailContainerLayout
        content={content}
        contentId={contentId}
        parentChain={parentChain}
        statusInfo={statusInfo}
        qualityScore={qualityScore}
        childrenItems={childrenItems}
        childrenLoading={childrenLoading}
        onReprocess={handlePartialReprocess}
        onLock={handleLockFields}
        onPreviewClip={handleRequestPreviewClip}
      />
    )
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <DetailHeader
        content={content}
        contentId={contentId}
        mode={mode}
        parentChain={parentChain}
        statusInfo={statusInfo}
        onModeChange={setMode}
        onReprocess={handlePartialReprocess}
        onLock={handleLockFields}
        onPreviewClip={handleRequestPreviewClip}
      />

      <div className="flex gap-4 p-6 max-w-[1400px] mx-auto">
        {/* 좌측 ContentShell ~380px */}
        <div className="w-[380px] flex-shrink-0">
          <ContentShell
            content={content}
            contentId={contentId}
            posterCandidates={posterCandidates ?? []}
            primaryId={posterCandidates?.find((c) => c.is_primary)?.id ?? null}
            childrenItems={childrenItems}
            childrenLoading={childrenLoading}
            onSelectPrimary={async (id) => {
              const updated = await posterRecommendApi.selectPrimary(contentId, id)
              setPosterCandidates(updated)
            }}
            onRecommendPoster={async () => {
              const res = await posterRecommendApi.recommend(contentId)
              setPosterCandidates(res.candidates)
            }}
          />
        </div>

        {/* 우측 — mode 별 패널 */}
        <div className="flex-1 min-w-0 space-y-4">
          {/* [A][B][C] ViewPane */}
          <ViewPane
            content={content}
            contentId={contentId}
            recommendations={recommendations}
            posterCandidates={posterCandidates ?? []}
            primaryId={posterCandidates?.find((c) => c.is_primary)?.id ?? null}
            appliedFields={appliedFields}
            onSelectPrimary={async (id) => {
              const updated = await posterRecommendApi.selectPrimary(contentId, id)
              setPosterCandidates(updated)
            }}
            onRecommendPoster={async () => {
              const res = await posterRecommendApi.recommend(contentId)
              setPosterCandidates(res.candidates)
            }}
            onApply={handleApplyRec}
            onApplyAllAuto={handleApplyAllAuto}
            onRegenerate={handleRegenerate}
            onEditSynopsis={() => router.push(`/programming/contents/${contentId}/edit`)}
          />

          {/* Tabs (video/sources/assets/ai — Step 3에서 EditPane 구성 후 정리 예정) */}
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
      </div>
    </div>
  )
}
