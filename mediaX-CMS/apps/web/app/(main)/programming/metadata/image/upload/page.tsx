"use client"

import { useState, useRef, useCallback } from "react"
import Link from "next/link"
import { ArrowLeft, Upload, CheckCircle, X, Image as ImageIcon } from "lucide-react"

const IMAGE_TYPES = ["poster", "thumbnail", "stillcut", "banner", "logo"] as const
type ImageType = (typeof IMAGE_TYPES)[number]

const IMAGE_TYPE_LABEL: Record<ImageType, string> = {
  poster: "포스터 (2:3 비율 권장, 500×750px+)",
  thumbnail: "썸네일 (16:9 비율 권장, 1280×720px+)",
  stillcut: "스틸컷 (16:9 비율, 1920×1080px+)",
  banner: "배너 (와이드, 2560×480px+)",
  logo: "로고 (투명 PNG 권장, 800×320px+)",
}

const MOCK_CONTENTS = [
  { id: 1, title: "기생충" },
  { id: 2, title: "오징어 게임 시즌2" },
  { id: 3, title: "서울의 봄" },
  { id: 4, title: "외계+인 2부" },
]

interface UploadedFile {
  name: string
  size: number
  preview: string
  status: "ready" | "uploading" | "done" | "error"
}

export default function ImageUploadPage() {
  const [contentId, setContentId] = useState("")
  const [imageType, setImageType] = useState<ImageType>("poster")
  const [file, setFile] = useState<UploadedFile | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const processFile = useCallback((f: File) => {
    if (!f.type.startsWith("image/")) return
    const reader = new FileReader()
    reader.onload = (e) => {
      setFile({
        name: f.name,
        size: f.size,
        preview: e.target?.result as string,
        status: "ready",
      })
    }
    reader.readAsDataURL(f)
  }, [])

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    const dropped = e.dataTransfer.files[0]
    if (dropped) processFile(dropped)
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0]
    if (selected) processFile(selected)
  }

  const handleUpload = async () => {
    if (!file || !contentId) return
    setFile((prev) => prev ? { ...prev, status: "uploading" } : null)

    // 실제 업로드 시뮬레이션 (Mock)
    await new Promise((r) => setTimeout(r, 1000))
    setFile((prev) => prev ? { ...prev, status: "done" } : null)
  }

  const formatSize = (bytes: number) => {
    if (bytes > 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)}MB`
    return `${(bytes / 1024).toFixed(0)}KB`
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* 헤더 */}
      <div className="flex items-center gap-3">
        <Link href="/programming/metadata/image" className="p-1.5 rounded-lg hover:bg-accent">
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <div>
          <h1 className="text-2xl font-bold">이미지 업로드</h1>
          <p className="text-sm text-muted-foreground mt-1">콘텐츠 이미지 에셋 등록</p>
        </div>
      </div>

      {/* 설정 */}
      <div className="rounded-xl border border-border bg-card p-5 space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">콘텐츠 선택 *</label>
            <select
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
              value={contentId}
              onChange={(e) => setContentId(e.target.value)}
            >
              <option value="">콘텐츠를 선택하세요</option>
              {MOCK_CONTENTS.map((c) => (
                <option key={c.id} value={c.id}>{c.title}</option>
              ))}
            </select>
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">이미지 타입 *</label>
            <select
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
              value={imageType}
              onChange={(e) => setImageType(e.target.value as ImageType)}
            >
              {IMAGE_TYPES.map((t) => (
                <option key={t} value={t}>{t === "poster" ? "포스터" : t === "thumbnail" ? "썸네일" : t === "stillcut" ? "스틸컷" : t === "banner" ? "배너" : "로고"}</option>
              ))}
            </select>
          </div>
        </div>

        {/* 선택된 이미지 타입 안내 */}
        <div className="rounded-lg bg-muted/50 px-4 py-2.5 text-xs text-muted-foreground">
          <ImageIcon className="h-3.5 w-3.5 inline mr-1.5" />
          {IMAGE_TYPE_LABEL[imageType]}
        </div>
      </div>

      {/* 드롭존 */}
      <div
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`rounded-xl border-2 border-dashed p-10 text-center cursor-pointer transition-colors ${
          isDragging
            ? "border-primary bg-primary/5"
            : "border-border hover:border-primary/50 hover:bg-accent/30"
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept="image/png,image/jpeg,image/webp"
          className="hidden"
          onChange={handleFileChange}
        />
        {!file ? (
          <div className="space-y-2">
            <Upload className="h-10 w-10 mx-auto text-muted-foreground" />
            <p className="text-sm font-medium">이미지 파일을 드롭하거나 클릭하여 선택</p>
            <p className="text-xs text-muted-foreground">PNG, JPG, WebP — 최대 20MB</p>
          </div>
        ) : (
          <div className="space-y-3" onClick={(e) => e.stopPropagation()}>
            {/* 미리보기 */}
            <div className="flex justify-center">
              <img
                src={file.preview}
                alt="미리보기"
                className="max-h-48 max-w-full rounded-lg border border-border object-contain"
              />
            </div>
            <div className="flex items-center justify-center gap-3 text-sm">
              <span className="font-medium">{file.name}</span>
              <span className="text-muted-foreground">{formatSize(file.size)}</span>
              {file.status === "done" ? (
                <span className="flex items-center gap-1 text-green-600"><CheckCircle className="h-4 w-4" />업로드 완료</span>
              ) : (
                <button
                  onClick={() => setFile(null)}
                  className="text-muted-foreground hover:text-foreground"
                >
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>
          </div>
        )}
      </div>

      {/* 업로드 버튼 */}
      {file && file.status !== "done" && (
        <button
          onClick={handleUpload}
          disabled={!contentId || file.status === "uploading"}
          className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg bg-primary text-primary-foreground font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
        >
          <Upload className={`h-4 w-4 ${file.status === "uploading" ? "animate-bounce" : ""}`} />
          {file.status === "uploading" ? "업로드 중..." : "이미지 업로드"}
        </button>
      )}

      {file?.status === "done" && (
        <div className="rounded-xl border border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-900/20 p-4 flex items-center gap-3">
          <CheckCircle className="h-5 w-5 text-green-600" />
          <div>
            <p className="text-sm font-medium text-green-700 dark:text-green-400">업로드 완료</p>
            <p className="text-xs text-green-600 dark:text-green-500 mt-0.5">이미지가 등록되었습니다. 5종이 모두 등록되면 이미지메타가 완료 처리됩니다.</p>
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
