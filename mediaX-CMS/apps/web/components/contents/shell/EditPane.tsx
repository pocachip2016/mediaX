"use client"

import { useState } from "react"
import { cn } from "@workspace/ui/lib/utils"
import { BASE, type ContentDetail, type PosterCandidateOut } from "@/lib/api"
import { PosterRow } from "@/components/contents/recommend/PosterRow"

const RATING_OPTIONS = [
  { value: "", label: "선택 안함" },
  { value: "전체이용가", label: "전체이용가" },
  { value: "12세이상", label: "12세 이상" },
  { value: "15세이상", label: "15세 이상" },
  { value: "18세이상", label: "18세 이상" },
]

interface EditPaneProps {
  content: ContentDetail
  contentId: number
  posterCandidates: PosterCandidateOut[]
  primaryId: number | null
  onSelectPrimary: (id: number) => Promise<void>
  onSaved: (updated: ContentDetail) => void
  onCancel: () => void
}

export function EditPane({
  content,
  contentId,
  posterCandidates,
  primaryId,
  onSelectPrimary,
  onSaved,
  onCancel,
}: EditPaneProps) {
  const directors = content.credits
    .filter((c) => c.role.toLowerCase().includes("director") || c.role === "감독")
    .map((c) => c.person.name_ko)
    .join(", ")

  const cast = content.credits
    .filter((c) => ["actor", "cast", "주연", "출연"].includes(c.role.toLowerCase()))
    .sort((a, b) => (a.cast_order ?? 99) - (b.cast_order ?? 99))
    .map((c) => c.person.name_ko)
    .join(", ")

  const genresStr = content.genres.map((g) => g.genre.name_ko).join(", ")

  const [form, setForm] = useState({
    title: content.title,
    cp_name: content.cp_name ?? "",
    production_year: content.production_year ?? "",
    synopsis: content.metadata_record?.cp_synopsis ?? "",
    genres: genresStr,
    country: content.country ?? "",
    runtime: content.runtime_minutes ?? "",
    rating_age: content.metadata_record?.ai_rating_suggestion ?? "",
    cast,
    directors,
    poster_url: content.poster_url ?? "",
  })

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function set(key: keyof typeof form) {
    return (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
      setForm((prev) => ({ ...prev, [key]: e.target.value }))
    }
  }

  async function handleSave() {
    if (!form.title.trim()) { setError("제목은 필수입니다"); return }
    if (!form.cp_name.trim()) { setError("CP사는 필수입니다"); return }
    setError(null)
    setLoading(true)
    try {
      const body: Record<string, unknown> = {
        title: form.title,
        cp_name: form.cp_name,
      }
      if (form.production_year) body.production_year = Number(form.production_year)
      if (form.synopsis) body.synopsis = form.synopsis
      if (form.genres) body.genres = form.genres
      if (form.country) body.country = form.country
      if (form.runtime) body.runtime = Number(form.runtime)
      if (form.rating_age) body.rating_age = form.rating_age
      if (form.cast) body.cast = form.cast
      if (form.directors) body.directors = form.directors
      if (form.poster_url) body.poster_url = form.poster_url

      const res = await fetch(`${BASE}/api/programming/metadata/contents/${contentId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error((err as { detail?: string }).detail ?? `요청 실패 (${res.status})`)
      }
      const updated = (await res.json()) as ContentDetail
      onSaved(updated)
    } catch (err) {
      setError(err instanceof Error ? err.message : "알 수 없는 오류")
    } finally {
      setLoading(false)
    }
  }

  const input = "w-full px-3 py-2 rounded-lg border border-slate-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-400/30"
  const label = "block text-xs font-medium text-slate-500 mb-1"

  return (
    <div className="space-y-4">
      {error && (
        <div className="px-4 py-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm">
          {error}
        </div>
      )}

      {/* [A] 포스터 */}
      <div className="bg-white rounded-lg border border-slate-200 p-4">
        <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3">
          포스터
        </p>
        <div className="mb-3">
          <label className={label}>포스터 URL</label>
          <input className={input} value={form.poster_url} onChange={set("poster_url")} placeholder="https://..." />
        </div>
        {posterCandidates.length > 0 && (
          <PosterRow
            contentId={contentId}
            candidates={posterCandidates}
            primaryId={primaryId}
            onSelectPrimary={onSelectPrimary}
            onRecommend={async () => {}}
          />
        )}
      </div>

      {/* [B] 시놉시스 */}
      <div className="bg-white rounded-lg border border-slate-200 p-4">
        <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3">
          시놉시스
        </p>
        <textarea
          className={cn(input, "resize-none")}
          rows={5}
          value={form.synopsis}
          onChange={set("synopsis")}
          placeholder="콘텐츠 줄거리를 입력하세요"
        />
      </div>

      {/* [C] 메타 필드 */}
      <div className="bg-white rounded-lg border border-slate-200 p-4 space-y-3">
        <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide">
          메타 필드
        </p>

        <div>
          <label className={label}>제목 *</label>
          <input className={input} value={form.title} onChange={set("title")} placeholder="콘텐츠 제목" />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className={label}>CP사 *</label>
            <input className={input} value={form.cp_name} onChange={set("cp_name")} placeholder="CP사명" />
          </div>
          <div>
            <label className={label}>제작연도</label>
            <input className={input} type="number" value={form.production_year} onChange={set("production_year")} placeholder="2024" min={1900} max={2099} />
          </div>
        </div>

        <div>
          <label className={label}>장르 (쉼표 구분)</label>
          <input className={input} value={form.genres} onChange={set("genres")} placeholder="드라마, 스릴러" />
        </div>

        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className={label}>제작국가</label>
            <input className={input} value={form.country} onChange={set("country")} placeholder="한국" />
          </div>
          <div>
            <label className={label}>런타임 (분)</label>
            <input className={input} type="number" value={form.runtime} onChange={set("runtime")} placeholder="120" min={1} />
          </div>
          <div>
            <label className={label}>시청등급</label>
            <select className={input} value={form.rating_age} onChange={set("rating_age")}>
              {RATING_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className={label}>감독 (쉼표 구분)</label>
            <input className={input} value={form.directors} onChange={set("directors")} placeholder="감독명" />
          </div>
          <div>
            <label className={label}>출연진 (쉼표 구분)</label>
            <input className={input} value={form.cast} onChange={set("cast")} placeholder="배우1, 배우2" />
          </div>
        </div>
      </div>

      {/* [D] Footer */}
      <div className="flex gap-3">
        <button
          onClick={() => void handleSave()}
          disabled={loading}
          className="flex-1 py-2.5 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          {loading ? "저장 중..." : "저장"}
        </button>
        <button
          onClick={onCancel}
          className="px-6 py-2.5 rounded-lg border border-slate-200 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors"
        >
          취소
        </button>
      </div>
    </div>
  )
}
