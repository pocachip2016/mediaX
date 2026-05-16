"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { cn } from "@workspace/ui/lib/utils"
import { BASE } from "@/lib/api"

export interface ContentFormData {
  title: string
  content_type: "movie" | "series" | "season" | "episode"
  cp_name: string
  production_year?: number
  synopsis?: string
  cast?: string
  directors?: string
  genres?: string
  country?: string
  runtime?: number
  rating_age?: string
  poster_url?: string
}

interface ContentFormProps {
  contentId?: number
  initialData?: Partial<ContentFormData>
}

const CONTENT_TYPES = [
  { value: "movie", label: "영화" },
  { value: "series", label: "시리즈" },
  { value: "season", label: "시즌" },
  { value: "episode", label: "에피소드" },
]

const RATING_OPTIONS = [
  { value: "", label: "선택 안함" },
  { value: "전체이용가", label: "전체이용가" },
  { value: "12세이상", label: "12세 이상" },
  { value: "15세이상", label: "15세 이상" },
  { value: "18세이상", label: "18세 이상" },
]

export function ContentForm({ contentId, initialData }: ContentFormProps) {
  const router = useRouter()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [form, setForm] = useState<ContentFormData>({
    title: initialData?.title ?? "",
    content_type: initialData?.content_type ?? "movie",
    cp_name: initialData?.cp_name ?? "",
    production_year: initialData?.production_year,
    synopsis: initialData?.synopsis ?? "",
    cast: initialData?.cast ?? "",
    directors: initialData?.directors ?? "",
    genres: initialData?.genres ?? "",
    country: initialData?.country ?? "",
    runtime: initialData?.runtime,
    rating_age: initialData?.rating_age ?? "",
    poster_url: initialData?.poster_url ?? "",
  })

  function set(key: keyof ContentFormData) {
    return (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
      const val = e.target.type === "number" ? (e.target.value ? Number(e.target.value) : undefined) : e.target.value
      setForm(prev => ({ ...prev, [key]: val }))
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)

    if (!form.title.trim()) { setError("제목은 필수입니다"); return }
    if (!form.cp_name.trim()) { setError("CP사는 필수입니다"); return }

    setLoading(true)
    try {
      const body: Record<string, unknown> = { ...form }
      // 빈 문자열 제거
      Object.keys(body).forEach(k => { if (body[k] === "" || body[k] === undefined) delete body[k] })

      const url = contentId
        ? `${BASE}/api/programming/metadata/contents/${contentId}`
        : `${BASE}/api/programming/metadata/contents`
      const method = contentId ? "PUT" : "POST"

      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || `요청 실패 (${res.status})`)
      }

      const result = await res.json()
      const targetId = result.id ?? contentId
      router.push(`/programming/contents/${targetId}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : "알 수 없는 오류")
    } finally {
      setLoading(false)
    }
  }

  const inputClass = "w-full px-3 py-2 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
  const labelClass = "block text-sm font-medium text-foreground mb-1"

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {error && (
        <div className="px-4 py-3 rounded-lg bg-destructive/10 text-destructive text-sm">{error}</div>
      )}

      {/* 필수 필드 */}
      <div className="rounded-xl border border-border bg-card p-5 space-y-4">
        <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">기본 정보 (필수)</h2>

        <div>
          <label className={labelClass}>제목 *</label>
          <input className={inputClass} value={form.title} onChange={set("title")} placeholder="콘텐츠 제목" required />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>CP사 *</label>
            <input className={inputClass} value={form.cp_name} onChange={set("cp_name")} placeholder="CP사명" required />
          </div>
          <div>
            <label className={labelClass}>제작년도</label>
            <input className={inputClass} type="number" value={form.production_year ?? ""} onChange={set("production_year")} placeholder="2024" min={1900} max={2099} />
          </div>
        </div>

        <div>
          <label className={labelClass}>콘텐츠 유형 *</label>
          <select className={inputClass} value={form.content_type} onChange={set("content_type")}>
            {CONTENT_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select>
        </div>
      </div>

      {/* 선택 필드 */}
      <div className="rounded-xl border border-border bg-card p-5 space-y-4">
        <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">추가 메타데이터 (선택)</h2>

        <div>
          <label className={labelClass}>줄거리</label>
          <textarea className={cn(inputClass, "resize-none")} rows={3} value={form.synopsis} onChange={set("synopsis")} placeholder="콘텐츠 줄거리" />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>출연진</label>
            <input className={inputClass} value={form.cast} onChange={set("cast")} placeholder="배우1, 배우2, ..." />
            <p className="text-xs text-muted-foreground mt-1">쉼표로 구분</p>
          </div>
          <div>
            <label className={labelClass}>감독</label>
            <input className={inputClass} value={form.directors} onChange={set("directors")} placeholder="감독1, ..." />
          </div>
        </div>

        <div>
          <label className={labelClass}>장르</label>
          <input className={inputClass} value={form.genres} onChange={set("genres")} placeholder="드라마, 판타지, ..." />
        </div>

        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className={labelClass}>제작국가</label>
            <input className={inputClass} value={form.country} onChange={set("country")} placeholder="한국" />
          </div>
          <div>
            <label className={labelClass}>런타임 (분)</label>
            <input className={inputClass} type="number" value={form.runtime ?? ""} onChange={set("runtime")} placeholder="120" min={1} />
          </div>
          <div>
            <label className={labelClass}>시청등급</label>
            <select className={inputClass} value={form.rating_age} onChange={set("rating_age")}>
              {RATING_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </div>
        </div>

        <div>
          <label className={labelClass}>포스터 URL</label>
          <input className={inputClass} value={form.poster_url} onChange={set("poster_url")} placeholder="https://..." />
        </div>
      </div>

      <div className="flex gap-3">
        <button
          type="submit"
          disabled={loading}
          className="flex-1 py-2.5 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
        >
          {loading ? "저장 중..." : contentId ? "수정 저장" : "등록"}
        </button>
        <button
          type="button"
          onClick={() => router.back()}
          className="px-6 py-2.5 rounded-lg border border-border text-sm font-medium hover:bg-accent transition-colors"
        >
          취소
        </button>
      </div>
    </form>
  )
}
