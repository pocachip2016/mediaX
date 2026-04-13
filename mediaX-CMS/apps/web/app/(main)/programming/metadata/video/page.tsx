"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import {
  ArrowLeft, CheckCircle, AlertCircle, RefreshCw, Check, Video,
} from "lucide-react"
import { videoMetaApi, type VideoMetaOut } from "@/lib/api"

const RESOLUTION_OPTIONS = ["4K", "FHD", "HD", "SD"] as const
const FORMAT_OPTIONS = ["MP4", "TS", "MKV", "MOV"] as const
const CODEC_VIDEO_OPTIONS = ["H.264", "H.265", "AV1", "VP9"] as const
const CODEC_AUDIO_OPTIONS = ["AAC", "AC3", "EAC3", "MP3"] as const
const DRM_OPTIONS = ["Widevine", "PlayReady", "FairPlay", "없음"] as const

const MOCK_ITEMS: VideoMetaOut[] = [
  {
    id: 1, title: "기생충", content_type: "movie", cp_name: "CJ ENM", production_year: 2019,
    video_resolution: "4K", video_format: "MP4", codec_video: "H.265", codec_audio: "AAC",
    video_bitrate_kbps: 20000, video_duration_seconds: 8208, subtitle_languages: ["ko", "en", "ja"],
    drm_type: "Widevine", preview_clip_url: null, video_meta_completed: true,
  },
  {
    id: 2, title: "오징어 게임 시즌2", content_type: "series", cp_name: "넷플릭스", production_year: 2024,
    video_resolution: "FHD", video_format: "TS", codec_video: "H.264", codec_audio: "AC3",
    video_bitrate_kbps: 8000, video_duration_seconds: null, subtitle_languages: ["ko", "en"],
    drm_type: "PlayReady", preview_clip_url: null, video_meta_completed: true,
  },
  {
    id: 3, title: "서울의 봄", content_type: "movie", cp_name: "플러스엠", production_year: 2023,
    video_resolution: "FHD", video_format: "MP4", codec_video: "H.264", codec_audio: "AAC",
    video_bitrate_kbps: 10000, video_duration_seconds: 8160, subtitle_languages: ["ko"],
    drm_type: "Widevine", preview_clip_url: null, video_meta_completed: true,
  },
  {
    id: 4, title: "외계+인 2부", content_type: "movie", cp_name: "CJ ENM", production_year: 2024,
    video_resolution: "FHD", video_format: null, codec_video: null, codec_audio: null,
    video_bitrate_kbps: null, video_duration_seconds: null, subtitle_languages: null,
    drm_type: null, preview_clip_url: null, video_meta_completed: false,
  },
]

function formatDuration(seconds: number | null) {
  if (!seconds) return "-"
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  return h > 0 ? `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}` : `${m}:${String(s).padStart(2, "0")}`
}

interface EditPanelProps {
  item: VideoMetaOut
  onSaved: () => void
}

function EditPanel({ item, onSaved }: EditPanelProps) {
  const [form, setForm] = useState({
    video_resolution: item.video_resolution ?? "",
    video_format: item.video_format ?? "",
    codec_video: item.codec_video ?? "",
    codec_audio: item.codec_audio ?? "",
    video_bitrate_kbps: item.video_bitrate_kbps ? String(item.video_bitrate_kbps) : "",
    video_duration_seconds: item.video_duration_seconds ? String(item.video_duration_seconds) : "",
    subtitle_languages: (item.subtitle_languages ?? []).join(", "),
    drm_type: item.drm_type ?? "",
    preview_clip_url: item.preview_clip_url ?? "",
  })
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  const set = (key: string, val: string) => setForm((prev) => ({ ...prev, [key]: val }))

  const handleSave = async (complete: boolean) => {
    setSaving(true)
    try {
      await videoMetaApi.update(item.id, {
        video_resolution: form.video_resolution || undefined,
        video_format: form.video_format || undefined,
        codec_video: form.codec_video || undefined,
        codec_audio: form.codec_audio || undefined,
        video_bitrate_kbps: form.video_bitrate_kbps ? parseInt(form.video_bitrate_kbps) : undefined,
        video_duration_seconds: form.video_duration_seconds ? parseInt(form.video_duration_seconds) : undefined,
        subtitle_languages: form.subtitle_languages ? form.subtitle_languages.split(",").map((s) => s.trim()).filter(Boolean) : undefined,
        drm_type: form.drm_type || undefined,
        preview_clip_url: form.preview_clip_url || undefined,
        completed: complete,
      })
      setSaved(true)
      onSaved()
    } catch {
      setSaved(true)
      onSaved()
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="h-full flex flex-col">
      <div className="px-5 py-4 border-b border-border">
        <div className="flex items-center gap-2">
          <Video className="h-4 w-4 text-muted-foreground" />
          <div>
            <h3 className="font-bold">{item.title}</h3>
            <p className="text-xs text-muted-foreground">{item.cp_name} · {item.production_year}</p>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-5 space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">해상도</label>
            <select
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
              value={form.video_resolution}
              onChange={(e) => set("video_resolution", e.target.value)}
            >
              <option value="">선택</option>
              {RESOLUTION_OPTIONS.map((o) => <option key={o} value={o}>{o}</option>)}
            </select>
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">포맷</label>
            <select
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
              value={form.video_format}
              onChange={(e) => set("video_format", e.target.value)}
            >
              <option value="">선택</option>
              {FORMAT_OPTIONS.map((o) => <option key={o} value={o}>{o}</option>)}
            </select>
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">영상 코덱</label>
            <select
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
              value={form.codec_video}
              onChange={(e) => set("codec_video", e.target.value)}
            >
              <option value="">선택</option>
              {CODEC_VIDEO_OPTIONS.map((o) => <option key={o} value={o}>{o}</option>)}
            </select>
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">오디오 코덱</label>
            <select
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
              value={form.codec_audio}
              onChange={(e) => set("codec_audio", e.target.value)}
            >
              <option value="">선택</option>
              {CODEC_AUDIO_OPTIONS.map((o) => <option key={o} value={o}>{o}</option>)}
            </select>
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">비트레이트 (kbps)</label>
            <input
              type="number"
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
              value={form.video_bitrate_kbps}
              onChange={(e) => set("video_bitrate_kbps", e.target.value)}
              placeholder="예: 8000"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">재생 시간 (초)</label>
            <input
              type="number"
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
              value={form.video_duration_seconds}
              onChange={(e) => set("video_duration_seconds", e.target.value)}
              placeholder="예: 7200"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">DRM</label>
            <select
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
              value={form.drm_type}
              onChange={(e) => set("drm_type", e.target.value)}
            >
              <option value="">선택</option>
              {DRM_OPTIONS.map((o) => <option key={o} value={o}>{o}</option>)}
            </select>
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">자막 언어 (쉼표 구분)</label>
            <input
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
              value={form.subtitle_languages}
              onChange={(e) => set("subtitle_languages", e.target.value)}
              placeholder="ko, en, ja"
            />
          </div>
        </div>
        <div className="space-y-1.5">
          <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">미리보기 클립 URL</label>
          <input
            className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
            value={form.preview_clip_url}
            onChange={(e) => set("preview_clip_url", e.target.value)}
            placeholder="https://cdn.example.com/preview/..."
          />
        </div>
      </div>

      <div className="px-5 py-4 border-t border-border flex gap-2">
        <button
          onClick={() => handleSave(false)}
          disabled={saving}
          className="flex-1 px-3 py-2 rounded-lg border border-border text-sm hover:bg-accent disabled:opacity-50"
        >
          저장
        </button>
        <button
          onClick={() => handleSave(true)}
          disabled={saving || saved}
          className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-green-600 text-white text-sm font-medium hover:bg-green-700 disabled:opacity-60"
        >
          <Check className="h-4 w-4" />
          {saved ? "완료됨" : "완료 처리"}
        </button>
      </div>
    </div>
  )
}

export default function VideoMetaPage() {
  const [items, setItems] = useState<VideoMetaOut[]>(MOCK_ITEMS)
  const [loading, setLoading] = useState(false)
  const [selected, setSelected] = useState<VideoMetaOut | null>(null)
  const [checkedIds, setCheckedIds] = useState<Set<number>>(new Set())
  const [tabFilter, setTabFilter] = useState<"all" | "completed" | "incomplete">("all")
  const [bulkLoading, setBulkLoading] = useState(false)

  const fetchItems = async () => {
    setLoading(true)
    try {
      const params: { completed?: boolean } = {}
      if (tabFilter === "completed") params.completed = true
      if (tabFilter === "incomplete") params.completed = false
      const res = await videoMetaApi.list(params)
      setItems(res.items)
    } catch {
      // Mock 유지
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchItems() }, [tabFilter])

  const handleBulkComplete = async () => {
    if (checkedIds.size === 0) return
    setBulkLoading(true)
    try {
      await videoMetaApi.bulkComplete(Array.from(checkedIds))
      setCheckedIds(new Set())
      fetchItems()
    } catch {
      setCheckedIds(new Set())
      fetchItems()
    } finally {
      setBulkLoading(false)
    }
  }

  return (
    <div className="space-y-4">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/programming/metadata" className="p-1.5 rounded-lg hover:bg-accent">
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold">영상 파일 정보</h1>
            <p className="text-sm text-muted-foreground mt-1">영상메타 완성도 관리 — 총 {items.length}건</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {checkedIds.size > 0 && (
            <button
              onClick={handleBulkComplete}
              disabled={bulkLoading}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-green-600 text-white text-sm font-medium hover:bg-green-700 disabled:opacity-50"
            >
              <Check className="h-4 w-4" /> 선택 완료 ({checkedIds.size}건)
            </button>
          )}
          <button onClick={fetchItems} className="p-2 rounded-lg border border-border hover:bg-accent">
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* 필터 */}
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

      {/* 메인 레이아웃 */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4 min-h-[600px]">
        {/* 좌: 목록 테이블 */}
        <div className="lg:col-span-2 rounded-xl border border-border bg-card overflow-hidden flex flex-col">
          <div className="px-4 py-3 border-b border-border bg-muted/30 text-sm font-medium text-muted-foreground">
            콘텐츠 목록
          </div>
          <div className="flex-1 overflow-y-auto">
            {items.map((item) => (
              <div
                key={item.id}
                onClick={() => setSelected(item)}
                className={`flex items-center gap-2 px-4 py-3 hover:bg-accent/50 border-b border-border/50 cursor-pointer transition-colors ${selected?.id === item.id ? "bg-accent" : ""}`}
              >
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
                  onClick={(e) => e.stopPropagation()}
                  className="rounded shrink-0"
                />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium truncate">{item.title}</div>
                  <div className="text-xs text-muted-foreground">
                    {item.video_resolution ?? "-"} · {item.codec_video ?? "-"} · {item.drm_type ? `DRM: ${item.drm_type}` : "DRM 없음"}
                  </div>
                  {item.subtitle_languages && item.subtitle_languages.length > 0 && (
                    <div className="text-xs text-muted-foreground">자막: {item.subtitle_languages.join(", ")}</div>
                  )}
                </div>
                <div className="flex flex-col items-end gap-1 shrink-0">
                  {item.video_meta_completed
                    ? <CheckCircle className="h-4 w-4 text-green-600" />
                    : <AlertCircle className="h-4 w-4 text-orange-500" />
                  }
                  <span className="text-xs text-muted-foreground">{formatDuration(item.video_duration_seconds)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* 우: 편집 패널 */}
        <div className="lg:col-span-3 rounded-xl border border-border bg-card overflow-hidden flex flex-col">
          {!selected ? (
            <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground gap-3">
              <Video className="h-8 w-8 opacity-30" />
              <p className="text-sm">왼쪽에서 콘텐츠를 선택하세요</p>
            </div>
          ) : (
            <EditPanel
              key={selected.id}
              item={selected}
              onSaved={() => {
                fetchItems()
                setSelected(null)
              }}
            />
          )}
        </div>
      </div>
    </div>
  )
}
