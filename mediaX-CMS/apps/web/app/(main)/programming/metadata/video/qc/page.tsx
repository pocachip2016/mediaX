"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { ArrowLeft, Check, RefreshCw, AlertTriangle, CheckCircle } from "lucide-react"
import { videoMetaApi, type VideoMetaOut } from "@/lib/api"

const REQUIRED_FIELDS: Array<{ key: keyof VideoMetaOut; label: string }> = [
  { key: "video_resolution", label: "해상도" },
  { key: "codec_video", label: "영상 코덱" },
  { key: "drm_type", label: "DRM" },
]

const ALL_FIELDS: Array<{ key: keyof VideoMetaOut; label: string }> = [
  { key: "video_resolution", label: "해상도" },
  { key: "video_format", label: "포맷" },
  { key: "codec_video", label: "영상 코덱" },
  { key: "codec_audio", label: "오디오 코덱" },
  { key: "video_bitrate_kbps", label: "비트레이트" },
  { key: "video_duration_seconds", label: "재생 시간" },
  { key: "drm_type", label: "DRM" },
  { key: "subtitle_languages", label: "자막" },
]

const MOCK_INCOMPLETE: VideoMetaOut[] = [
  {
    id: 4, title: "외계+인 2부", content_type: "movie", cp_name: "CJ ENM", production_year: 2024,
    video_resolution: "FHD", video_format: null, codec_video: null, codec_audio: null,
    video_bitrate_kbps: null, video_duration_seconds: null, subtitle_languages: null,
    drm_type: null, preview_clip_url: null, video_meta_completed: false,
  },
  {
    id: 5, title: "범죄도시4", content_type: "movie", cp_name: "에이비오엔터테인먼트", production_year: 2024,
    video_resolution: null, video_format: "MP4", codec_video: "H.264", codec_audio: "AAC",
    video_bitrate_kbps: 8000, video_duration_seconds: 6840, subtitle_languages: ["ko"],
    drm_type: null, preview_clip_url: null, video_meta_completed: false,
  },
]

function getMissingRequired(item: VideoMetaOut): string[] {
  return REQUIRED_FIELDS
    .filter(({ key }) => !item[key])
    .map(({ label }) => label)
}

function getMissingOptional(item: VideoMetaOut): string[] {
  return ALL_FIELDS
    .filter(({ key }) => !REQUIRED_FIELDS.some((r) => r.key === key))
    .filter(({ key }) => {
      const val = item[key]
      if (Array.isArray(val)) return val.length === 0
      return !val
    })
    .map(({ label }) => label)
}

export default function VideoQcPage() {
  const [items, setItems] = useState<VideoMetaOut[]>(MOCK_INCOMPLETE)
  const [loading, setLoading] = useState(false)
  const [checkedIds, setCheckedIds] = useState<Set<number>>(new Set())
  const [bulkLoading, setBulkLoading] = useState(false)

  const fetchItems = async () => {
    setLoading(true)
    try {
      const res = await videoMetaApi.list({ completed: false })
      setItems(res.items)
    } catch {
      // Mock 유지
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchItems() }, [])

  const handleBulkComplete = async () => {
    if (checkedIds.size === 0) return
    setBulkLoading(true)
    try {
      await videoMetaApi.bulkComplete(Array.from(checkedIds))
      setItems((prev) => prev.filter((i) => !checkedIds.has(i.id)))
      setCheckedIds(new Set())
    } catch {
      setItems((prev) => prev.filter((i) => !checkedIds.has(i.id)))
      setCheckedIds(new Set())
    } finally {
      setBulkLoading(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/programming/metadata/video" className="p-1.5 rounded-lg hover:bg-accent">
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold">영상 QC</h1>
            <p className="text-sm text-muted-foreground mt-1">영상메타 미완료 항목 검수 — {items.length}건</p>
          </div>
        </div>
        <div className="flex gap-2">
          {checkedIds.size > 0 && (
            <button
              onClick={handleBulkComplete}
              disabled={bulkLoading}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-green-600 text-white text-sm font-medium hover:bg-green-700 disabled:opacity-50"
            >
              <Check className="h-4 w-4" /> 선택 완료 처리 ({checkedIds.size}건)
            </button>
          )}
          <button onClick={fetchItems} className="p-2 rounded-lg border border-border hover:bg-accent">
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {items.length === 0 ? (
        <div className="rounded-xl border border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-900/20 p-8 text-center">
          <CheckCircle className="h-10 w-10 mx-auto text-green-600 mb-3" />
          <p className="text-green-700 dark:text-green-400 font-medium">모든 영상메타가 완료되었습니다</p>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-sm text-muted-foreground px-1">
            <input
              type="checkbox"
              checked={checkedIds.size === items.length && items.length > 0}
              onChange={() => {
                if (checkedIds.size === items.length) {
                  setCheckedIds(new Set())
                } else {
                  setCheckedIds(new Set(items.map((i) => i.id)))
                }
              }}
              className="rounded"
            />
            <span>전체 선택</span>
          </div>

          {items.map((item) => {
            const missingRequired = getMissingRequired(item)
            const missingOptional = getMissingOptional(item)
            const isBlocking = missingRequired.length > 0

            return (
              <div
                key={item.id}
                className={`rounded-xl border bg-card p-4 ${isBlocking ? "border-red-200 dark:border-red-800" : "border-orange-200 dark:border-orange-800"}`}
              >
                <div className="flex items-start gap-3">
                  <input
                    type="checkbox"
                    checked={checkedIds.has(item.id)}
                    onChange={() => {
                      setCheckedIds((prev) => {
                        const next = new Set(prev)
                        next.has(item.id) ? next.delete(item.id) : next.add(item.id)
                        return next
                      })
                    }}
                    className="rounded mt-1 shrink-0"
                  />

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-semibold">{item.title}</span>
                      <span className="text-xs text-muted-foreground">{item.cp_name} · {item.production_year}</span>
                      {isBlocking ? (
                        <span className="flex items-center gap-1 text-xs text-red-600 bg-red-50 dark:bg-red-900/20 px-1.5 py-0.5 rounded">
                          <AlertTriangle className="h-3 w-3" /> 필수 항목 누락
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 text-xs text-orange-600 bg-orange-50 dark:bg-orange-900/20 px-1.5 py-0.5 rounded">
                          <AlertTriangle className="h-3 w-3" /> 선택 항목 누락
                        </span>
                      )}
                    </div>

                    {/* 필드 현황 그리드 */}
                    <div className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-2">
                      {ALL_FIELDS.map(({ key, label }) => {
                        const val = item[key]
                        const hasVal = Array.isArray(val) ? val.length > 0 : !!val
                        const isRequired = REQUIRED_FIELDS.some((r) => r.key === key)
                        return (
                          <div
                            key={key}
                            className={`rounded-lg px-2.5 py-1.5 text-xs border ${
                              hasVal
                                ? "border-green-200 bg-green-50 text-green-700 dark:border-green-800 dark:bg-green-900/20 dark:text-green-400"
                                : isRequired
                                  ? "border-red-200 bg-red-50 text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400"
                                  : "border-orange-200 bg-orange-50 text-orange-700 dark:border-orange-800 dark:bg-orange-900/20 dark:text-orange-400"
                            }`}
                          >
                            <div className="font-medium">{label}</div>
                            <div className="truncate mt-0.5">
                              {hasVal
                                ? (Array.isArray(val) ? (val as string[]).join(", ") : String(val))
                                : (isRequired ? "⚠️ 필수" : "미입력")}
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </div>

                  <Link
                    href="/programming/metadata/video"
                    onClick={() => {/* 선택 상태 전달은 추후 구현 */}}
                    className="shrink-0 px-3 py-1.5 rounded-lg border border-border text-xs hover:bg-accent"
                  >
                    편집
                  </Link>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
