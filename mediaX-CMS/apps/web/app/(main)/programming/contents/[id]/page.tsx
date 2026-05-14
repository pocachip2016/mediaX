"use client"

import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import Link from "next/link"
import {
  ArrowLeft, Check, X, RotateCcw, Eye, AlertCircle, Film, ChevronDown,
} from "lucide-react"
import { cn } from "@workspace/ui/lib/utils"
import Image from "next/image"
import { metadataApi, imageMetaApi, type ContentOut, type ImageMetaOut, resolvePosterUrl } from "@/lib/api"

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
  const contentId = Number(params.id)
  
  const [content, setContent] = useState<ContentOut | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<TabName>("text")
  const [selectedSynopsis, setSelectedSynopsis] = useState<"cp" | "ai" | "tmdb" | "manual">("ai")
  const [changelog, setChangelog] = useState<any>(null)
  const [damAssets, setDamAssets] = useState<any>(null)
  const [imageMeta, setImageMeta] = useState<ImageMetaOut | null>(null)

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

  // Load changelog when ai tab becomes active
  useEffect(() => {
    if (activeTab === "ai") {
      handleLoadChangelog()
    }
  }, [activeTab])

  // Load image meta when image tab becomes active
  useEffect(() => {
    if (activeTab === "image") {
      imageMetaApi.get(contentId).then(setImageMeta).catch(() => setImageMeta(null))
    }
  }, [activeTab, contentId])

  // Load dam assets when assets tab becomes active
  useEffect(() => {
    if (activeTab === "assets") {
      metadataApi.getDamAssets(contentId)
        .then(setDamAssets)
        .catch(() => setDamAssets({ content_id: contentId, assets: [], dam_available: false }))
    }
  }, [activeTab, contentId])

  if (loading) {
    return <div className="p-6 text-center text-slate-600">로드 중...</div>
  }

  if (!content) {
    return <div className="p-6 text-center text-slate-600">콘텐츠를 찾을 수 없습니다.</div>
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

  const mockQualityScore = 82
  const statusInfo = (STATUS_BADGE[content.status] ?? STATUS_BADGE.waiting)!

  return (
    <div className="min-h-screen bg-slate-50 p-6">
      {/* Header */}
      <div className="mb-6 bg-white rounded-lg border border-slate-200 p-6">
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-start gap-4">
            <Link href="/programming/contents" className="text-slate-400 hover:text-slate-600 mt-1">
              <ArrowLeft className="h-5 w-5" />
            </Link>
            <div>
              <h1 className="text-2xl font-bold text-slate-900">{content.title}</h1>
              {content.original_title && (
                <p className="text-slate-600 text-sm mt-1">{content.original_title}</p>
              )}
              <p className="text-slate-500 text-sm mt-2">
                {content.content_type === "movie" ? "영화" : content.content_type === "series" ? "시리즈" : content.content_type} ·
                {content.cp_name ? ` ${content.cp_name} ·` : ""} {content.production_year || ""}
              </p>
            </div>
          </div>
          <div className="text-right">
            <div className={cn("inline-flex items-center gap-2 px-3 py-1 rounded-full text-sm font-medium", statusInfo.color)}>
              {statusInfo.emoji} {statusInfo.label}
            </div>
            <p className="text-slate-500 text-xs mt-2">ID: #{content.id}</p>
          </div>
        </div>

        <div className="flex items-center gap-4 mb-4 pb-4 border-b border-slate-200">
          <div className="flex-1">
            <p className="text-xs text-slate-500 mb-1">품질 점수</p>
            <div className="flex items-center gap-2">
              <div className="flex-1 bg-slate-200 rounded-full h-2 overflow-hidden">
                <div className="bg-amber-500 h-full" style={{ width: `${mockQualityScore}%` }} />
              </div>
              <span className="font-bold text-sm text-amber-700">{mockQualityScore}</span>
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex gap-2">
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
                  <div className="border border-slate-200 rounded-lg p-4 bg-slate-50">
                    <div className="text-xs font-semibold text-slate-600 mb-2">
                      <span className="inline-block px-2 py-0.5 rounded bg-slate-200 text-slate-700">[CP]</span>
                      <span className="ml-2">trust 100</span>
                    </div>
                    <p className="text-sm text-slate-500">(없음)</p>
                    <input type="radio" name="synopsis" disabled className="mt-3" />
                  </div>

                  <div className={cn("border-2 rounded-lg p-4", selectedSynopsis === "ai" ? "border-blue-400 bg-blue-50" : "border-slate-200 bg-white")}>
                    <div className="text-xs font-semibold text-slate-600 mb-2 flex items-center justify-between">
                      <span>
                        <span className="inline-block px-2 py-0.5 rounded bg-purple-100 text-purple-700">[AI]</span>
                        <span className="ml-2">score 89</span>
                      </span>
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

                  <div className={cn("border-2 rounded-lg p-4", selectedSynopsis === "tmdb" ? "border-blue-400 bg-blue-50" : "border-slate-200 bg-white")}>
                    <div className="text-xs font-semibold text-slate-600 mb-2">
                      <span className="inline-block px-2 py-0.5 rounded bg-blue-100 text-blue-700">[TMDB]</span>
                      <span className="ml-2">match .94</span>
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
                  <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-blue-100 text-blue-700 text-sm">
                    드라마 <span className="text-xs">✓ TMDB·.91</span>
                  </span>
                  <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-blue-100 text-blue-700 text-sm">
                    스릴러 <span className="text-xs">✓ AI·.84</span>
                  </span>
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
              {!damAssets ? (
                <p className="text-slate-500 text-sm text-center py-8">로딩 중...</p>
              ) : !damAssets.dam_available ? (
                <p className="text-amber-600 text-sm text-center py-8">Dam API에 연결할 수 없습니다.</p>
              ) : damAssets.assets.length === 0 ? (
                <p className="text-slate-500 text-sm text-center py-8">매핑된 에셋이 없습니다.</p>
              ) : (
                <div className="grid grid-cols-3 gap-4">
                  {damAssets.assets.map((asset: any) => (
                    <div key={asset.asset_id} className="border rounded-lg overflow-hidden">
                      <img
                        src={asset.thumbnail_url}
                        alt={asset.filename}
                        className="w-full h-32 object-cover bg-slate-100"
                        onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
                      />
                      <div className="p-2">
                        <p className="text-xs font-medium truncate">{asset.filename}</p>
                        {asset.confidence != null && (
                          <p className="text-xs text-slate-500">{(asset.confidence * 100).toFixed(0)}% match</p>
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
