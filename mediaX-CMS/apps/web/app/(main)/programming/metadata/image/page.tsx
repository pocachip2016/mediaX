"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { ArrowLeft, CheckCircle, AlertCircle, RefreshCw, Upload, Image as ImageIcon, X } from "lucide-react"
import { imageMetaApi, type ImageMetaOut } from "@/lib/api"

const IMAGE_TYPES = ["poster", "thumbnail", "stillcut", "banner", "logo"] as const
type ImageType = (typeof IMAGE_TYPES)[number]

const IMAGE_TYPE_LABEL: Record<ImageType, string> = {
  poster: "포스터",
  thumbnail: "썸네일",
  stillcut: "스틸컷",
  banner: "배너",
  logo: "로고",
}

const MOCK_ITEMS: ImageMetaOut[] = [
  {
    id: 1, title: "기생충", content_type: "movie", cp_name: "CJ ENM", production_year: 2019,
    images: [
      { id: 1, content_id: 1, image_type: "poster", url: "https://placehold.co/120x180/8B5CF6/white?text=포스터", width: 500, height: 750, alt_text: "기생충 포스터", source: "tmdb" },
      { id: 2, content_id: 1, image_type: "thumbnail", url: "https://placehold.co/320x180/7C3AED/white?text=썸네일", width: 1280, height: 720, alt_text: "기생충 썸네일", source: "tmdb" },
      { id: 3, content_id: 1, image_type: "stillcut", url: "https://placehold.co/320x180/6D28D9/white?text=스틸컷", width: 1920, height: 1080, alt_text: null, source: "cp" },
      { id: 4, content_id: 1, image_type: "banner", url: "https://placehold.co/640x120/5B21B6/white?text=배너", width: 2560, height: 480, alt_text: null, source: "cp" },
      { id: 5, content_id: 1, image_type: "logo", url: "https://placehold.co/200x80/4C1D95/white?text=로고", width: 800, height: 320, alt_text: null, source: "cp" },
    ],
    has_poster: true, has_thumbnail: true, has_stillcut: true, has_banner: true, has_logo: true,
    image_meta_completed: true,
  },
  {
    id: 2, title: "오징어 게임 시즌2", content_type: "series", cp_name: "넷플릭스", production_year: 2024,
    images: [
      { id: 6, content_id: 2, image_type: "poster", url: "https://placehold.co/120x180/059669/white?text=포스터", width: 500, height: 750, alt_text: null, source: "tmdb" },
      { id: 7, content_id: 2, image_type: "stillcut", url: "https://placehold.co/320x180/047857/white?text=스틸컷", width: 1920, height: 1080, alt_text: null, source: "cp" },
    ],
    has_poster: true, has_thumbnail: false, has_stillcut: true, has_banner: false, has_logo: false,
    image_meta_completed: false,
  },
  {
    id: 3, title: "서울의 봄", content_type: "movie", cp_name: "플러스엠", production_year: 2023,
    images: [
      { id: 8, content_id: 3, image_type: "poster", url: "https://placehold.co/120x180/D97706/white?text=포스터", width: 500, height: 750, alt_text: null, source: "tmdb" },
      { id: 9, content_id: 3, image_type: "thumbnail", url: "https://placehold.co/320x180/B45309/white?text=썸네일", width: 1280, height: 720, alt_text: null, source: "tmdb" },
      { id: 10, content_id: 3, image_type: "stillcut", url: "https://placehold.co/320x180/92400E/white?text=스틸컷", width: 1920, height: 1080, alt_text: null, source: "cp" },
      { id: 11, content_id: 3, image_type: "banner", url: "https://placehold.co/640x120/78350F/white?text=배너", width: 2560, height: 480, alt_text: null, source: "cp" },
    ],
    has_poster: true, has_thumbnail: true, has_stillcut: true, has_banner: true, has_logo: false,
    image_meta_completed: false,
  },
]

function ProgressBar({ value, max }: { value: number; max: number }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0
  return (
    <div className="h-1.5 rounded-full bg-muted overflow-hidden mt-1">
      <div
        className="h-full rounded-full transition-all"
        style={{
          width: `${pct}%`,
          backgroundColor: pct === 100 ? "#16a34a" : pct >= 60 ? "#d97706" : "#dc2626",
        }}
      />
    </div>
  )
}

export default function ImageMetaPage() {
  const [items, setItems] = useState<ImageMetaOut[]>(MOCK_ITEMS)
  const [loading, setLoading] = useState(false)
  const [selected, setSelected] = useState<ImageMetaOut | null>(null)
  const [tabFilter, setTabFilter] = useState<"all" | "completed" | "incomplete">("all")

  const fetchItems = async () => {
    setLoading(true)
    try {
      const params: { completed?: boolean } = {}
      if (tabFilter === "completed") params.completed = true
      if (tabFilter === "incomplete") params.completed = false
      const res = await imageMetaApi.list(params)
      setItems(res.items)
    } catch {
      // Mock 유지
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchItems() }, [tabFilter])

  // 타입별 통계
  const stats: Record<ImageType, number> = {
    poster: 0, thumbnail: 0, stillcut: 0, banner: 0, logo: 0,
  }
  items.forEach((item) => {
    if (item.has_poster) stats.poster++
    if (item.has_thumbnail) stats.thumbnail++
    if (item.has_stillcut) stats.stillcut++
    if (item.has_banner) stats.banner++
    if (item.has_logo) stats.logo++
  })
  const total = items.length

  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/programming/metadata" className="p-1.5 rounded-lg hover:bg-accent">
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold">이미지 에셋</h1>
            <p className="text-sm text-muted-foreground mt-1">이미지메타 완성도 관리 — 총 {total}건</p>
          </div>
        </div>
        <div className="flex gap-2">
          <Link
            href="/programming/metadata/image/upload"
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90"
          >
            <Upload className="h-4 w-4" /> 이미지 업로드
          </Link>
          <button onClick={fetchItems} className="p-2 rounded-lg border border-border hover:bg-accent">
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* 이미지 타입별 현황 카드 */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3">
        {IMAGE_TYPES.map((type) => (
          <div key={type} className="rounded-xl border border-border bg-card p-4">
            <div className="text-xs font-medium text-muted-foreground">{IMAGE_TYPE_LABEL[type]}</div>
            <div className="text-2xl font-bold mt-1">{stats[type]}/{total}</div>
            <ProgressBar value={stats[type]} max={total} />
            <div className="text-xs text-muted-foreground mt-1">
              {total > 0 ? Math.round((stats[type] / total) * 100) : 0}% 완성
            </div>
          </div>
        ))}
      </div>

      {/* 필터 + 목록 */}
      <div className="space-y-3">
        <div className="flex rounded-lg border border-border overflow-hidden text-sm w-fit">
          {(["all", "completed", "incomplete"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setTabFilter(f)}
              className={`px-3 py-1.5 transition-colors ${tabFilter === f ? "bg-primary text-primary-foreground" : "hover:bg-accent"}`}
            >
              {f === "all" ? "전체" : f === "completed" ? "완료" : "미완료"}
            </button>
          ))}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {items.map((item) => (
            <div
              key={item.id}
              onClick={() => setSelected(item)}
              className="rounded-xl border border-border bg-card p-4 cursor-pointer hover:bg-accent/30 transition-colors"
            >
              {/* 제목 + 완료 뱃지 */}
              <div className="flex items-start justify-between gap-2 mb-3">
                <div className="min-w-0">
                  <div className="font-medium text-sm truncate">{item.title}</div>
                  <div className="text-xs text-muted-foreground">{item.cp_name} · {item.production_year}</div>
                </div>
                {item.image_meta_completed ? (
                  <CheckCircle className="h-4 w-4 text-green-600 shrink-0" />
                ) : (
                  <AlertCircle className="h-4 w-4 text-orange-500 shrink-0" />
                )}
              </div>

              {/* 이미지 타입 뱃지 */}
              <div className="flex flex-wrap gap-1">
                {IMAGE_TYPES.map((type) => {
                  const has = item[`has_${type}` as keyof ImageMetaOut] as boolean
                  return (
                    <span
                      key={type}
                      className={`text-xs px-1.5 py-0.5 rounded border ${has
                        ? "bg-green-50 text-green-700 border-green-200 dark:bg-green-900/20 dark:text-green-400 dark:border-green-800"
                        : "bg-muted text-muted-foreground border-border"
                      }`}
                    >
                      {has ? "✓" : "✗"} {IMAGE_TYPE_LABEL[type]}
                    </span>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 상세 패널 (슬라이드인 오버레이) */}
      {selected && (
        <div className="fixed inset-0 z-40 flex">
          <div className="flex-1 bg-black/40" onClick={() => setSelected(null)} />
          <div className="w-full max-w-lg bg-background border-l border-border flex flex-col overflow-hidden">
            <div className="px-5 py-4 border-b border-border flex items-center justify-between">
              <div>
                <h2 className="font-bold">{selected.title}</h2>
                <p className="text-sm text-muted-foreground">{selected.cp_name} · {selected.production_year}</p>
              </div>
              <button onClick={() => setSelected(null)} className="p-1.5 hover:bg-accent rounded-lg">
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-5 space-y-4">
              {IMAGE_TYPES.map((type) => {
                const img = selected.images.find((i) => i.image_type === type)
                return (
                  <div key={type} className="space-y-2">
                    <div className="flex items-center justify-between">
                      <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                        {IMAGE_TYPE_LABEL[type]}
                      </label>
                      {img ? (
                        <span className="text-xs text-green-600 flex items-center gap-1">
                          <CheckCircle className="h-3 w-3" /> 등록됨
                        </span>
                      ) : (
                        <span className="text-xs text-muted-foreground flex items-center gap-1">
                          <AlertCircle className="h-3 w-3" /> 없음
                        </span>
                      )}
                    </div>
                    {img ? (
                      <div className="rounded-lg border border-border overflow-hidden bg-muted/30 flex items-center gap-3 p-2">
                        <div className="h-12 w-12 rounded bg-muted flex items-center justify-center shrink-0">
                          <ImageIcon className="h-5 w-5 text-muted-foreground" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="text-xs truncate text-muted-foreground">{img.url}</div>
                          {img.width && img.height && (
                            <div className="text-xs text-muted-foreground">{img.width}×{img.height}px · {img.source}</div>
                          )}
                        </div>
                      </div>
                    ) : (
                      <Link
                        href={`/programming/metadata/image/upload?content_id=${selected.id}&type=${type}`}
                        className="flex items-center justify-center gap-2 h-12 rounded-lg border border-dashed border-border text-sm text-muted-foreground hover:bg-accent/50 transition-colors"
                      >
                        <Upload className="h-4 w-4" /> 업로드
                      </Link>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
