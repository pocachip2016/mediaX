"use client"

import { useRef, useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { ArrowLeft, Film, X, Trash2 } from "lucide-react"
import { cn } from "@workspace/ui/lib/utils"
import { BASE, metadataApi, type ContentType } from "@/lib/api"

// ── 상수 ────────────────────────────────────────────────

const CONTENT_TYPES: { value: ContentType; label: string }[] = [
  { value: "movie",   label: "영화" },
  { value: "series",  label: "시리즈" },
  { value: "season",  label: "시즌" },
  { value: "episode", label: "에피소드" },
]

const FORMATS = ["MP4", "TS", "HLS"]
const RESOLUTIONS = ["4K", "1080p", "720p"]

// ── 타입 ────────────────────────────────────────────────

type FormState = {
  title: string
  original_title: string
  content_type: ContentType
  cp_name: string
  production_year: string
  runtime: string
  country: string
  director: string
  cast: string
  synopsis: string
  extended_synopsis: string
  catchphrase: string
  keywords: string[]
  vodPath: string
  trailerPath: string
  format: "MP4" | "TS" | "HLS"
  resolution: "4K" | "1080p" | "720p"
}

function emptyForm(defaultCp: string): FormState {
  return {
    title: "",
    original_title: "",
    content_type: "movie",
    cp_name: defaultCp,
    production_year: "",
    runtime: "",
    country: "",
    director: "",
    cast: "",
    synopsis: "",
    extended_synopsis: "",
    catchphrase: "",
    keywords: [],
    vodPath: "",
    trailerPath: "",
    format: "MP4",
    resolution: "1080p",
  }
}

export interface SingleContentFormProps {
  /** 좁은 컬럼용: Hero 세로 스택 + 포스터 축소 + 백버튼/취소 숨김 */
  compact?: boolean
  /** CP사 프리필 (기본 "") */
  defaultCp?: string
  /** "등록 후 Enrich 자동 트리거" 체크박스 노출 (기본 false) */
  showAutoEnrich?: boolean
  /** 있으면 상세 리다이렉트 대신 호출 — 폼 리셋 + 인라인 성공 표시 */
  onSubmitted?: (content: { id: number; title: string }) => void
  /** 취소 동작 (기본 router.back()) */
  onCancel?: () => void
}

// ── 공유 폼 컴포넌트 ────────────────────────────────────

export function SingleContentForm({
  compact = false,
  defaultCp = "",
  showAutoEnrich = false,
  onSubmitted,
  onCancel,
}: SingleContentFormProps) {
  const router = useRouter()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const stillsInputRef = useRef<HTMLInputElement>(null)
  const bgInputRef = useRef<HTMLInputElement>(null)

  const [form, setForm] = useState<FormState>(() => emptyForm(defaultCp))
  const [genres, setGenres] = useState<string[]>([])
  const [genreInput, setGenreInput] = useState("")
  const [posterPreview, setPosterPreview] = useState<string | null>(null)
  const [touched, setTouched] = useState<Set<string>>(new Set())
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState<string | null>(null)
  const [submitted, setSubmitted] = useState<{ id: number; title: string } | null>(null)

  const [activeTab, setActiveTab] = useState<"text" | "image" | "video">("text")
  const [stillPreviews, setStillPreviews] = useState<string[]>([])
  const [bgPreview, setBgPreview] = useState<string | null>(null)
  const [keywordInput, setKeywordInput] = useState("")
  const [autoEnrich, setAutoEnrich] = useState(false)

  function set(key: keyof FormState) {
    return (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
      setForm(prev => ({ ...prev, [key]: e.target.value }))
    }
  }

  function touch(key: string) {
    setTouched(prev => new Set([...prev, key]))
  }

  function hasError(key: string, value: string) {
    return touched.has(key) && !value.trim()
  }

  // ── 장르 태그 입력 ──────────────────────────────────

  function handleGenreKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault()
      addGenre()
    }
  }

  function addGenre() {
    const val = genreInput.trim().replace(/,$/, "")
    if (val && !genres.includes(val)) {
      setGenres(prev => [...prev, val])
    }
    setGenreInput("")
  }

  function removeGenre(g: string) {
    setGenres(prev => prev.filter(x => x !== g))
  }

  // ── 키워드 태그 입력 (글자 탭) ──────────────────────

  function handleKeywordKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault()
      addKeyword()
    }
  }

  function addKeyword() {
    const val = keywordInput.trim().replace(/,$/, "")
    if (val && !form.keywords.includes(val)) {
      setForm(prev => ({ ...prev, keywords: [...prev.keywords, val] }))
    }
    setKeywordInput("")
  }

  function removeKeyword(k: string) {
    setForm(prev => ({ ...prev, keywords: prev.keywords.filter(x => x !== k) }))
  }

  // ── 포스터 파일 ─────────────────────────────────────

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = ev => setPosterPreview(ev.target?.result as string)
    reader.readAsDataURL(file)
  }

  // ── 스틸 이미지 (이미지 탭) ─────────────────────────

  function handleStillsChange(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []).slice(0, 5)
    if (files.length > 0) {
      Promise.all(
        files.map(f => {
          return new Promise<string>(resolve => {
            const reader = new FileReader()
            reader.onload = ev => resolve(ev.target?.result as string)
            reader.readAsDataURL(f)
          })
        })
      ).then(previews => setStillPreviews(previews))
    }
  }

  function removeStill(idx: number) {
    setStillPreviews(prev => prev.filter((_, i) => i !== idx))
  }

  // ── 배경 이미지 (이미지 탭) ─────────────────────────

  function handleBgChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = ev => setBgPreview(ev.target?.result as string)
    reader.readAsDataURL(file)
  }

  // ── 폼 리셋 (인라인 등록 후) ───────────────────────

  function resetForm() {
    setForm(emptyForm(defaultCp))
    setGenres([])
    setGenreInput("")
    setKeywordInput("")
    setPosterPreview(null)
    setStillPreviews([])
    setBgPreview(null)
    setTouched(new Set())
    setActiveTab("text")
    if (fileInputRef.current) fileInputRef.current.value = ""
    if (stillsInputRef.current) stillsInputRef.current.value = ""
    if (bgInputRef.current) bgInputRef.current.value = ""
  }

  // ── 제출 ─────────────────────────────────────────────

  async function handleSubmit() {
    const requiredTouched = new Set([...touched, "title", "cp_name"])
    setTouched(requiredTouched)

    if (!form.title.trim() || !form.cp_name.trim()) return

    setSaving(true)
    setServerError(null)
    setSubmitted(null)

    const body: Record<string, unknown> = {
      title: form.title.trim(),
      content_type: form.content_type,
      cp_name: form.cp_name.trim(),
    }
    if (form.production_year) body.production_year = Number(form.production_year)
    if (form.runtime)         body.runtime = Number(form.runtime)
    if (form.original_title.trim()) body.original_title = form.original_title.trim()
    if (form.country.trim())        body.country = form.country.trim()
    if (form.director.trim())       body.director = form.director.trim()
    if (form.cast.trim())           body.cast = form.cast.trim()
    if (form.synopsis.trim())       body.synopsis = form.synopsis.trim()
    if (genres.length > 0)          body.genres = genres.join(",")
    if (form.extended_synopsis.trim())  body.extended_synopsis = form.extended_synopsis.trim()
    if (form.catchphrase.trim())        body.catchphrase = form.catchphrase.trim()
    if (form.keywords.length > 0)       body.keywords = form.keywords.join(",")
    if (form.vodPath.trim())       body.vod_path = form.vodPath.trim()
    if (form.trailerPath.trim())   body.trailer_path = form.trailerPath.trim()
    if (form.vodPath.trim()) {
      body.format = form.format
      body.resolution = form.resolution
    }

    try {
      const res = await fetch(`${BASE}/api/programming/metadata/contents`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error((err as { detail?: string }).detail ?? `요청 실패 (${res.status})`)
      }
      const result = await res.json() as { id: number; title: string }
      if (showAutoEnrich && autoEnrich) {
        await metadataApi.triggerEnrich(result.id).catch(() => {})
      }
      if (onSubmitted) {
        setSubmitted({ id: result.id, title: result.title ?? form.title.trim() })
        resetForm()
        onSubmitted(result)
      } else {
        router.push(`/programming/contents/${result.id}?enrich=true`)
      }
    } catch (err) {
      setServerError(err instanceof Error ? err.message : "알 수 없는 오류")
    } finally {
      setSaving(false)
    }
  }

  const inputCls = "w-full px-2.5 py-1.5 text-sm rounded-lg border border-slate-200 bg-white focus:outline-none focus:ring-2 focus:ring-blue-200 focus:border-blue-400 placeholder:text-slate-300"
  const selectCls = cn(inputCls, "cursor-pointer")

  return (
    <div className="space-y-6">

      {/* ── HERO CARD ─────────────────────────────────── */}
      <div className={cn(compact ? "flex flex-col gap-3" : "flex gap-6")}>

        {/* 좌(또는 상): 포스터 업로드 */}
        <div className={cn("flex-shrink-0", compact ? "w-28 mx-auto" : "w-44")}>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={handleFileChange}
          />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="w-full aspect-[2/3] rounded-xl overflow-hidden bg-slate-100 flex flex-col items-center justify-center shadow-sm border-2 border-dashed border-slate-200 hover:border-blue-300 hover:bg-blue-50/30 transition-colors group"
          >
            {posterPreview ? (
              <img src={posterPreview} alt="포스터 미리보기" className="w-full h-full object-cover" />
            ) : (
              <>
                <Film className="h-10 w-10 text-slate-300 group-hover:text-blue-300 transition-colors mb-2" />
                <span className="text-xs text-slate-400 group-hover:text-blue-400 transition-colors text-center px-2">
                  포스터 업로드
                </span>
              </>
            )}
          </button>
          {posterPreview && (
            <button
              type="button"
              onClick={() => { setPosterPreview(null); if (fileInputRef.current) fileInputRef.current.value = "" }}
              className="mt-1.5 w-full text-xs text-slate-400 hover:text-red-500 transition-colors"
            >
              제거
            </button>
          )}
        </div>

        {/* 우(또는 하): 입력 필드 */}
        <div className="flex-1 min-w-0 flex flex-col">

          {/* 헤더 */}
          <div className="flex items-start gap-3 min-w-0 mb-3">
            {!compact && (
              <Link href="/programming/contents" className="text-slate-400 hover:text-slate-600 mt-1 flex-shrink-0">
                <ArrowLeft className="h-5 w-5" />
              </Link>
            )}
            <div className="flex-1 min-w-0 space-y-1.5">
              <div>
                <input
                  className={cn(inputCls, "text-lg font-semibold", hasError("title", form.title) && "border-red-300 ring-red-100")}
                  placeholder="콘텐츠 제목 *"
                  value={form.title}
                  onChange={set("title")}
                  onBlur={() => touch("title")}
                />
                {hasError("title", form.title) && (
                  <p className="text-xs text-red-500 mt-0.5">필수 항목입니다</p>
                )}
              </div>
              <input
                className={cn(inputCls, "text-sm text-slate-500")}
                placeholder="원제목 (선택)"
                value={form.original_title}
                onChange={set("original_title")}
              />
            </div>
          </div>

          {/* 장르 태그 입력 */}
          <div className="flex flex-wrap gap-1.5 mb-3 items-center min-h-[28px]">
            {genres.map(g => (
              <span
                key={g}
                className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-sm font-medium bg-blue-50 border border-blue-200 text-blue-800"
              >
                {g}
                <button type="button" onClick={() => removeGenre(g)} className="hover:text-red-500">
                  <X className="h-3 w-3" />
                </button>
              </span>
            ))}
            <input
              className="text-sm px-2 py-0.5 rounded-full border border-dashed border-slate-300 focus:outline-none focus:border-blue-300 placeholder:text-slate-300 min-w-[80px] bg-transparent"
              placeholder="장르 입력 후 Enter"
              value={genreInput}
              onChange={e => setGenreInput(e.target.value)}
              onKeyDown={handleGenreKeyDown}
              onBlur={addGenre}
            />
          </div>

          {/* 기본 메타 행 1 */}
          <div className="flex flex-wrap gap-x-4 gap-y-2 mb-2">
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-slate-400 w-6">유형</span>
              <select className={cn(selectCls, "w-28")} value={form.content_type} onChange={set("content_type")}>
                {CONTENT_TYPES.map(t => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-slate-400">📅</span>
              <input
                className={cn(inputCls, "w-20")}
                type="number"
                placeholder="연도"
                value={form.production_year}
                onChange={set("production_year")}
                min={1900} max={2099}
              />
            </div>
          </div>

          {/* 기본 메타 행 2 */}
          <div className="flex flex-wrap gap-x-4 gap-y-2 mb-3">
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-slate-400">🏢</span>
              <div>
                <input
                  className={cn(inputCls, "w-36", hasError("cp_name", form.cp_name) && "border-red-300 ring-red-100")}
                  placeholder="CP사 *"
                  value={form.cp_name}
                  onChange={set("cp_name")}
                  onBlur={() => touch("cp_name")}
                />
                {hasError("cp_name", form.cp_name) && (
                  <p className="text-xs text-red-500 mt-0.5">필수 항목입니다</p>
                )}
              </div>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-slate-400">⏱</span>
              <input
                className={cn(inputCls, "w-16")}
                type="number"
                placeholder="분"
                value={form.runtime}
                onChange={set("runtime")}
                min={1}
              />
            </div>
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-slate-400">🌐</span>
              <input
                className={cn(inputCls, "w-24")}
                placeholder="국가"
                value={form.country}
                onChange={set("country")}
              />
            </div>
          </div>

          {/* 감독 / 주연 / 줄거리 */}
          <div className="space-y-1.5 mb-3 text-sm">
            <div className="flex gap-2 items-center">
              <span className="text-slate-400 w-10 flex-shrink-0">감독</span>
              <input
                className={cn(inputCls, "flex-1")}
                placeholder="감독 이름"
                value={form.director}
                onChange={set("director")}
              />
            </div>
            <div className="flex gap-2 items-center">
              <span className="text-slate-400 w-10 flex-shrink-0">주연</span>
              <input
                className={cn(inputCls, "flex-1")}
                placeholder="배우1, 배우2, … (쉼표 구분)"
                value={form.cast}
                onChange={set("cast")}
              />
            </div>
            <div className="flex gap-2 items-start">
              <span className="text-slate-400 w-10 flex-shrink-0 mt-1.5">줄거리</span>
              <textarea
                className={cn(inputCls, "flex-1 resize-none")}
                rows={2}
                placeholder="시놉시스 (선택)"
                value={form.synopsis}
                onChange={set("synopsis")}
              />
            </div>
          </div>

        </div>
      </div>

      {/* ── 탭 패널 ───────────────────────────────────── */}
      <div className="border-t border-slate-200 pt-6">

        {/* 탭 내비 */}
        <div className="flex gap-4 mb-6 border-b border-slate-200">
          {(["text", "image", "video"] as const).map(tab => (
            <button
              key={tab}
              type="button"
              onClick={() => setActiveTab(tab)}
              className={cn(
                "pb-3 px-1 text-sm font-medium transition-colors border-b-2",
                activeTab === tab
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-slate-500 hover:text-slate-700"
              )}
            >
              {tab === "text" && "글자"}
              {tab === "image" && "이미지"}
              {tab === "video" && "영상"}
            </button>
          ))}
        </div>

        {/* 글자 탭 */}
        {activeTab === "text" && (
          <div className="space-y-4">
            <div className="flex gap-2 items-start">
              <span className="text-sm text-slate-600 w-20 flex-shrink-0 mt-1.5">상세 줄거리</span>
              <textarea
                className={cn(inputCls, "flex-1 resize-none")}
                rows={6}
                placeholder="상세한 줄거리 (선택)"
                value={form.extended_synopsis}
                onChange={set("extended_synopsis")}
              />
            </div>
            <div className="flex gap-2 items-center">
              <span className="text-sm text-slate-600 w-20 flex-shrink-0">광고 문구</span>
              <input
                className={cn(inputCls, "flex-1")}
                placeholder="짧은 광고 문구 (선택)"
                value={form.catchphrase}
                onChange={set("catchphrase")}
              />
            </div>
            <div className="space-y-2">
              <span className="text-sm text-slate-600">키워드</span>
              <div className="flex flex-wrap gap-1.5 items-center min-h-[28px]">
                {form.keywords.map(k => (
                  <span
                    key={k}
                    className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-sm font-medium bg-green-50 border border-green-200 text-green-800"
                  >
                    {k}
                    <button type="button" onClick={() => removeKeyword(k)} className="hover:text-red-500">
                      <X className="h-3 w-3" />
                    </button>
                  </span>
                ))}
                <input
                  className="text-sm px-2 py-0.5 rounded-full border border-dashed border-slate-300 focus:outline-none focus:border-blue-300 placeholder:text-slate-300 min-w-[80px] bg-transparent"
                  placeholder="Enter"
                  value={keywordInput}
                  onChange={e => setKeywordInput(e.target.value)}
                  onKeyDown={handleKeywordKeyDown}
                  onBlur={addKeyword}
                />
              </div>
            </div>
          </div>
        )}

        {/* 이미지 탭 */}
        {activeTab === "image" && (
          <div className="space-y-6">
            <div>
              <div className="text-sm text-slate-600 mb-2">스틸컷 / 추가 이미지 (최대 5장)</div>
              <input
                ref={stillsInputRef}
                type="file"
                multiple
                accept="image/*"
                className="hidden"
                onChange={handleStillsChange}
              />
              <button
                type="button"
                onClick={() => stillsInputRef.current?.click()}
                className="w-full py-6 rounded-lg border-2 border-dashed border-slate-200 hover:border-blue-300 hover:bg-blue-50/20 transition-colors text-sm text-slate-500 hover:text-blue-600"
              >
                이미지 선택 (최대 5장)
              </button>
              {stillPreviews.length > 0 && (
                <div className="grid grid-cols-5 gap-2 mt-3">
                  {stillPreviews.map((prev, idx) => (
                    <div key={idx} className="relative group">
                      <img src={prev} alt={`still-${idx}`} className="w-full aspect-video object-cover rounded" />
                      <button
                        type="button"
                        onClick={() => removeStill(idx)}
                        className="absolute inset-0 flex items-center justify-center bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity rounded"
                      >
                        <Trash2 className="h-4 w-4 text-white" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div>
              <div className="text-sm text-slate-600 mb-2">배경 이미지 (16:9)</div>
              <input
                ref={bgInputRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={handleBgChange}
              />
              <button
                type="button"
                onClick={() => bgInputRef.current?.click()}
                className={cn(
                  "w-full aspect-video rounded-lg border-2 border-dashed border-slate-200 hover:border-blue-300 hover:bg-blue-50/20 transition-colors",
                  bgPreview && "border-solid"
                )}
              >
                {bgPreview ? (
                  <img src={bgPreview} alt="배경" className="w-full h-full object-cover rounded" />
                ) : (
                  <span className="flex flex-col items-center justify-center h-full text-sm text-slate-500 group-hover:text-blue-600">
                    배경 이미지 선택
                  </span>
                )}
              </button>
              {bgPreview && (
                <button
                  type="button"
                  onClick={() => { setBgPreview(null); if (bgInputRef.current) bgInputRef.current.value = "" }}
                  className="mt-1.5 text-xs text-slate-400 hover:text-red-500 transition-colors"
                >
                  제거
                </button>
              )}
            </div>
          </div>
        )}

        {/* 영상 탭 */}
        {activeTab === "video" && (
          <div className="space-y-4">
            <div className="flex gap-2 items-center">
              <span className="text-sm text-slate-600 w-20 flex-shrink-0">VOD 경로</span>
              <input
                className={cn(inputCls, "flex-1")}
                placeholder="/vod/path/to/file.mp4 (선택)"
                value={form.vodPath}
                onChange={set("vodPath")}
              />
            </div>
            <div className="flex gap-2 items-center">
              <span className="text-sm text-slate-600 w-20 flex-shrink-0">예고편 경로</span>
              <input
                className={cn(inputCls, "flex-1")}
                placeholder="/trailer/path.mp4 (선택)"
                value={form.trailerPath}
                onChange={set("trailerPath")}
              />
            </div>
            <div className="flex flex-wrap gap-x-4 gap-y-2">
              <div className="flex items-center gap-2">
                <span className="text-sm text-slate-600 w-16 flex-shrink-0">포맷</span>
                <select className={cn(selectCls, "w-24")} value={form.format} onChange={set("format")}>
                  {FORMATS.map(f => (
                    <option key={f} value={f}>{f}</option>
                  ))}
                </select>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-sm text-slate-600 w-16 flex-shrink-0">해상도</span>
                <select className={cn(selectCls, "w-24")} value={form.resolution} onChange={set("resolution")}>
                  {RESOLUTIONS.map(r => (
                    <option key={r} value={r}>{r}</option>
                  ))}
                </select>
              </div>
            </div>
          </div>
        )}

      </div>

      {/* ── Enrich 자동 트리거 (인라인 모드) ───────────── */}
      {showAutoEnrich && (
        <label className="flex items-center gap-2 text-xs text-slate-500 cursor-pointer">
          <input type="checkbox" checked={autoEnrich} onChange={e => setAutoEnrich(e.target.checked)} className="rounded" />
          등록 후 Enrich 자동 트리거
        </label>
      )}

      {/* ── 피드백 ──────────────────────────────────────── */}
      {serverError && (
        <p className="text-xs text-red-600">{serverError}</p>
      )}
      {submitted && (
        <div className="text-xs px-3 py-2 rounded-lg border border-green-200 bg-green-50 text-green-700">
          ✓ 등록 완료: #{submitted.id} {submitted.title}
        </div>
      )}

      {/* ── 액션 버튼 ────────────────────────────────── */}
      <div className="border-t border-slate-100 pt-3">
        <div className="flex gap-2">
          <button
            type="button"
            onClick={handleSubmit}
            disabled={saving}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 text-white font-medium hover:bg-blue-700 text-sm disabled:opacity-50 transition-colors"
          >
            {saving ? "등록 중…" : "등록"}
          </button>
          {!compact && (
            <button
              type="button"
              onClick={() => (onCancel ? onCancel() : router.back())}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-100 text-slate-700 font-medium hover:bg-slate-200 text-sm transition-colors"
            >
              취소
            </button>
          )}
        </div>
      </div>

    </div>
  )
}
