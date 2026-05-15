"use client"

import { useRef, useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { ArrowLeft, Film, X } from "lucide-react"
import { cn } from "@workspace/ui/lib/utils"
import { BASE, type ContentType } from "@/lib/api"

// ── 상수 ────────────────────────────────────────────────

const CONTENT_TYPES: { value: ContentType; label: string }[] = [
  { value: "movie",   label: "영화" },
  { value: "series",  label: "시리즈" },
  { value: "season",  label: "시즌" },
  { value: "episode", label: "에피소드" },
]

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
}

const EMPTY_FORM: FormState = {
  title: "",
  original_title: "",
  content_type: "movie",
  cp_name: "",
  production_year: "",
  runtime: "",
  country: "",
  director: "",
  cast: "",
  synopsis: "",
}

// ── 메인 페이지 ─────────────────────────────────────────

export default function NewContentPage() {
  const router = useRouter()
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [form, setForm] = useState<FormState>(EMPTY_FORM)
  const [genres, setGenres] = useState<string[]>([])
  const [genreInput, setGenreInput] = useState("")
  const [posterPreview, setPosterPreview] = useState<string | null>(null)
  const [touched, setTouched] = useState<Set<string>>(new Set())
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState<string | null>(null)

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

  // ── 포스터 파일 ─────────────────────────────────────

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = ev => setPosterPreview(ev.target?.result as string)
    reader.readAsDataURL(file)
  }

  // ── 제출 ─────────────────────────────────────────────

  async function handleSubmit() {
    const requiredTouched = new Set([...touched, "title", "cp_name"])
    setTouched(requiredTouched)

    if (!form.title.trim() || !form.cp_name.trim()) return

    setSaving(true)
    setServerError(null)

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
      const result = await res.json() as { id: number }
      router.push(`/programming/contents/${result.id}?enrich=true`)
    } catch (err) {
      setServerError(err instanceof Error ? err.message : "알 수 없는 오류")
    } finally {
      setSaving(false)
    }
  }

  const inputCls = "w-full px-2.5 py-1.5 text-sm rounded-lg border border-slate-200 bg-white focus:outline-none focus:ring-2 focus:ring-blue-200 focus:border-blue-400 placeholder:text-slate-300"
  const selectCls = cn(inputCls, "cursor-pointer")

  return (
    <div className="min-h-screen bg-slate-50 p-6">
      <div className="bg-white rounded-lg border border-slate-200 p-6">
        <div className="flex gap-6">

          {/* ── 좌: 포스터 업로드 ─────────────────────── */}
          <div className="flex-shrink-0 w-44">
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

          {/* ── 우: 입력 필드 ──────────────────────────── */}
          <div className="flex-1 min-w-0 flex flex-col">

            {/* 헤더 */}
            <div className="flex items-start gap-3 min-w-0 mb-3">
              <Link href="/programming/contents" className="text-slate-400 hover:text-slate-600 mt-1 flex-shrink-0">
                <ArrowLeft className="h-5 w-5" />
              </Link>
              <div className="flex-1 min-w-0 space-y-1.5">
                {/* 제목 */}
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
                {/* 원제목 */}
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

            {/* 기본 메타 행 1: 유형 + 제작연도 */}
            <div className="flex flex-wrap gap-x-4 gap-y-2 mb-2">
              <div className="flex items-center gap-1.5">
                <span className="text-xs text-slate-400 w-6">유형</span>
                <select className={cn(selectCls, "w-28")} value={form.content_type} onChange={set("content_type")}>
                  {CONTENT_TYPES.map(t => (
                    <option key={t.value} value={t.value}>{t.label}</option>
                  ))}
                </select>
                <span className="text-red-400 text-xs">*</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="text-xs text-slate-400 whitespace-nowrap">📅</span>
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

            {/* 기본 메타 행 2: CP사 + 런타임 + 국가 */}
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

            {/* 감독 / 주연 / 줄거리 — 상세 페이지와 동일한 라벨+입력 구조 */}
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
                  placeholder="시놉시스 (선택 — 등록 후 AI가 제안합니다)"
                  value={form.synopsis}
                  onChange={set("synopsis")}
                />
              </div>
            </div>

            {/* 서버 에러 */}
            {serverError && (
              <p className="text-xs text-red-600 mb-2">{serverError}</p>
            )}

            {/* 액션 버튼 (상세 페이지 border-t 행과 동일 위치) */}
            <div className="mt-auto pt-3 border-t border-slate-100">
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={handleSubmit}
                  disabled={saving}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 text-white font-medium hover:bg-blue-700 text-sm disabled:opacity-50 transition-colors"
                >
                  {saving ? "등록 중…" : "등록"}
                </button>
                <button
                  type="button"
                  onClick={() => router.back()}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-100 text-slate-700 font-medium hover:bg-slate-200 text-sm transition-colors"
                >
                  취소
                </button>
              </div>
            </div>

          </div>
        </div>
      </div>
    </div>
  )
}
