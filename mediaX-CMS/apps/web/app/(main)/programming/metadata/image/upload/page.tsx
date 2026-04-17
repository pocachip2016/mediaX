"use client"

import { useState, useCallback } from "react"
import Link from "next/link"
import { ArrowLeft, Upload, CheckCircle, X, Image as ImageIcon, Sparkles, ExternalLink } from "lucide-react"
import { imageMetaApi, type ImageMetaSuggestions } from "@/lib/api"

const IMAGE_TYPES = ["poster", "thumbnail", "stillcut", "banner", "logo"] as const
type ImageType = (typeof IMAGE_TYPES)[number]

const IMAGE_TYPE_LABEL: Record<ImageType, { label: string; spec: string }> = {
  poster:    { label: "포스터",  spec: "2:3 비율 권장, 500×750px+" },
  thumbnail: { label: "썸네일", spec: "16:9 비율 권장, 1280×720px+" },
  stillcut:  { label: "스틸컷", spec: "16:9 비율, 1920×1080px+" },
  banner:    { label: "배너",   spec: "와이드, 2560×480px+" },
  logo:      { label: "로고",   spec: "투명 PNG 권장, 800×320px+" },
}

type UploadStatus = "idle" | "uploading" | "done" | "error"

export default function ImageUploadPage() {
  const [contentId, setContentId] = useState("")
  const [imageType, setImageType] = useState<ImageType>("poster")
  const [url, setUrl] = useState("")
  const [status, setStatus] = useState<UploadStatus>("idle")
  const [errorMsg, setErrorMsg] = useState("")

  // TMDB 제안
  const [suggestions, setSuggestions] = useState<ImageMetaSuggestions | null>(null)
  const [loadingSuggest, setLoadingSuggest] = useState(false)

  const fetchSuggestions = useCallback(async (id: string) => {
    if (!id) { setSuggestions(null); return }
    setLoadingSuggest(true)
    try {
      const data = await imageMetaApi.suggest(Number(id))
      setSuggestions(data)
    } catch {
      setSuggestions(null)
    } finally {
      setLoadingSuggest(false)
    }
  }, [])

  const handleContentChange = (val: string) => {
    setContentId(val)
    setStatus("idle")
    setUrl("")
    fetchSuggestions(val)
  }

  const handleUpload = async () => {
    if (!contentId || !url.trim()) return
    setStatus("uploading")
    setErrorMsg("")
    try {
      await imageMetaApi.uploadUrl(Number(contentId), {
        image_type: imageType,
        url: url.trim(),
        source: "manual",
      })
      setStatus("done")
      setUrl("")
      // 제안 목록 새로고침 (등록 후 해당 타입 제거)
      fetchSuggestions(contentId)
    } catch (e: unknown) {
      setStatus("error")
      setErrorMsg(e instanceof Error ? e.message : "업로드 실패")
    }
  }

  const applySuggestion = async (s: { image_type: string; url: string; width?: number | null; height?: number | null }) => {
    if (!contentId) return
    setStatus("uploading")
    setErrorMsg("")
    try {
      await imageMetaApi.uploadUrl(Number(contentId), {
        image_type: s.image_type,
        url: s.url,
        width: s.width ?? undefined,
        height: s.height ?? undefined,
        source: "tmdb",
      })
      setStatus("done")
      setTimeout(() => setStatus("idle"), 2000)
      fetchSuggestions(contentId)
    } catch (e: unknown) {
      setStatus("error")
      setErrorMsg(e instanceof Error ? e.message : "적용 실패")
    }
  }

  const typeInfo = IMAGE_TYPE_LABEL[imageType]
  const pendingSuggestions = suggestions?.suggestions ?? []

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* 헤더 */}
      <div className="flex items-center gap-3">
        <Link href="/programming/metadata/image" className="p-1.5 rounded-lg hover:bg-accent">
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <div>
          <h1 className="text-2xl font-bold">이미지 등록</h1>
          <p className="text-sm text-muted-foreground mt-1">콘텐츠 이미지 URL 등록 · TMDB 제안 적용</p>
        </div>
      </div>

      {/* 콘텐츠 + 타입 선택 */}
      <div className="rounded-xl border border-border bg-card p-5 space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">콘텐츠 ID *</label>
            <input
              type="number"
              placeholder="콘텐츠 ID 입력"
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
              value={contentId}
              onChange={(e) => handleContentChange(e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">이미지 타입 *</label>
            <select
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
              value={imageType}
              onChange={(e) => setImageType(e.target.value as ImageType)}
            >
              {IMAGE_TYPES.map((t) => (
                <option key={t} value={t}>{IMAGE_TYPE_LABEL[t].label}</option>
              ))}
            </select>
          </div>
        </div>
        <div className="rounded-lg bg-muted/50 px-4 py-2.5 text-xs text-muted-foreground flex items-center gap-2">
          <ImageIcon className="h-3.5 w-3.5 shrink-0" />
          {typeInfo.spec}
        </div>
      </div>

      {/* TMDB 제안 */}
      {contentId && (
        <div className="rounded-xl border border-border bg-card p-5 space-y-3">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-violet-500" />
            <span className="text-sm font-medium">TMDB 제안</span>
            {loadingSuggest && <span className="text-xs text-muted-foreground">조회 중...</span>}
          </div>

          {!loadingSuggest && pendingSuggestions.length === 0 && (
            <p className="text-xs text-muted-foreground">
              TMDB 동기화 데이터가 없거나 모든 이미지 타입이 이미 등록되었습니다.
            </p>
          )}

          {pendingSuggestions.length > 0 && (
            <div className="space-y-2">
              {pendingSuggestions.map((s, i) => (
                <div key={i} className="flex items-center gap-3 rounded-lg border border-border bg-background/50 p-3">
                  {/* 미리보기 */}
                  <div className="h-14 w-10 shrink-0 rounded overflow-hidden bg-muted">
                    <img
                      src={s.url}
                      alt={s.image_type}
                      className="h-full w-full object-cover"
                      onError={(e) => { (e.target as HTMLImageElement).style.display = "none" }}
                    />
                  </div>
                  <div className="flex-1 min-w-0">
                    <span className="text-xs font-medium">{IMAGE_TYPE_LABEL[s.image_type as ImageType]?.label ?? s.image_type}</span>
                    <p className="text-xs text-muted-foreground truncate mt-0.5">{s.url}</p>
                    {s.width && s.height && (
                      <p className="text-xs text-muted-foreground">{s.width}×{s.height}px</p>
                    )}
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    <a href={s.url} target="_blank" rel="noopener noreferrer"
                       className="p-1.5 rounded hover:bg-accent text-muted-foreground">
                      <ExternalLink className="h-3.5 w-3.5" />
                    </a>
                    <button
                      onClick={() => applySuggestion(s)}
                      disabled={status === "uploading"}
                      className="px-3 py-1.5 rounded-lg bg-violet-600 text-white text-xs font-medium hover:bg-violet-700 disabled:opacity-50 transition-colors"
                    >
                      적용
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* URL 직접 입력 */}
      <div className="rounded-xl border border-border bg-card p-5 space-y-4">
        <h3 className="text-sm font-medium">URL 직접 입력</h3>
        <div className="space-y-1.5">
          <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">이미지 URL *</label>
          <input
            type="url"
            placeholder="https://..."
            className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
            value={url}
            onChange={(e) => { setUrl(e.target.value); setStatus("idle") }}
          />
        </div>
        {/* URL 미리보기 */}
        {url && (
          <div className="flex justify-center">
            <img
              src={url}
              alt="미리보기"
              className="max-h-40 max-w-full rounded-lg border border-border object-contain"
              onError={(e) => { (e.target as HTMLImageElement).style.display = "none" }}
            />
          </div>
        )}
        <button
          onClick={handleUpload}
          disabled={!contentId || !url.trim() || status === "uploading"}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
        >
          <Upload className={`h-4 w-4 ${status === "uploading" ? "animate-bounce" : ""}`} />
          {status === "uploading" ? "등록 중..." : "이미지 URL 등록"}
        </button>

        {status === "error" && (
          <p className="text-xs text-red-500 flex items-center gap-1">
            <X className="h-3.5 w-3.5" />{errorMsg}
          </p>
        )}
      </div>

      {/* 완료 알림 */}
      {status === "done" && (
        <div className="rounded-xl border border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-900/20 p-4 flex items-center gap-3">
          <CheckCircle className="h-5 w-5 text-green-600 shrink-0" />
          <div>
            <p className="text-sm font-medium text-green-700 dark:text-green-400">등록 완료</p>
            <p className="text-xs text-green-600 dark:text-green-500 mt-0.5">5종이 모두 등록되면 이미지메타가 완료 처리됩니다.</p>
          </div>
          <Link
            href="/programming/metadata/image"
            className="ml-auto text-xs text-green-700 dark:text-green-400 hover:underline shrink-0"
          >
            목록으로 →
          </Link>
        </div>
      )}
    </div>
  )
}
