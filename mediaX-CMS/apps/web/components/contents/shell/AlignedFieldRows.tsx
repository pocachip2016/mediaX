"use client"

import { BASE, type ContentDetail, type FieldRecommendation, type RecommendationsOut, type SourceFieldRec } from "@/lib/api"
import { TYPE_LABEL } from "@/components/contents/detail/contentType"
import { classifyField } from "@/lib/recommendDerive"
import { InlineField } from "./InlineField"
import { RecomCell } from "@/components/contents/recommend/cells/RecomCell"

function findRec(recs: RecommendationsOut | null, field: string): FieldRecommendation | null {
  if (!recs) return null
  return [...recs.auto_fill, ...recs.conflicts].find((r) => r.field === field) ?? null
}

function ColHeaders() {
  return (
    <div className="grid grid-cols-[3rem_1fr_1fr] border-b bg-slate-50">
      <div />
      <div className="py-2 pl-1 text-xs font-semibold text-slate-500">현재 상태</div>
      <div className="py-2 px-4 text-xs font-semibold text-slate-500 border-l border-slate-100">AI 추천</div>
    </div>
  )
}

function FieldRow({ label, current, rec }: { label: string; current: React.ReactNode; rec: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[3rem_1fr_1fr] items-stretch border-b border-slate-100 last:border-0">
      <div className="flex items-start px-4 py-3">
        <span className="text-slate-400 text-xs">{label}</span>
      </div>
      <div className="py-3 pl-1 pr-2 text-xs min-w-0 flex items-start">{current}</div>
      <div className="border-l border-slate-100 min-w-0">{rec}</div>
    </div>
  )
}

type Props = {
  content: ContentDetail
  contentId: number
  onSaved: (updated: ContentDetail) => void
  recommendations: RecommendationsOut | null
  appliedFields: Set<string>
  onApply: (rec: FieldRecommendation, source: SourceFieldRec) => Promise<void>
}

export function AlignedFieldRows({ content, contentId, onSaved, recommendations, appliedFields, onApply }: Props) {
  const patch = async (body: Record<string, unknown>) => {
    const res = await fetch(`${BASE}/api/programming/metadata/contents/${contentId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: content.title, cp_name: content.cp_name, ...body }),
    })
    if (!res.ok) throw new Error("저장 실패")
    onSaved((await res.json()) as ContentDetail)
  }

  const directors = content.credits
    .filter((c) => c.role.toLowerCase().includes("director") || c.role === "감독")
    .map((c) => c.person.name_ko)
    .join(", ")

  const cast = content.credits
    .filter((c) => ["actor", "cast", "주연", "출연"].includes(c.role.toLowerCase()))
    .sort((a, b) => (a.cast_order ?? 99) - (b.cast_order ?? 99))
    .map((c) => c.person.name_ko)
    .join(", ")

  const genres = content.genres.map((g) => g.genre.name_ko).join(", ")

  const synopsis =
    content.metadata_record?.final_synopsis ||
    content.metadata_record?.ai_synopsis ||
    content.metadata_record?.cp_synopsis ||
    null

  const qualityScore = content.quality_score ?? 0

  const recFor = (field: string) => {
    const rec = findRec(recommendations, field)
    return (
      <RecomCell
        rec={rec}
        kind={classifyField(rec)}
        isApplied={appliedFields.has(field)}
        onApply={(src) => onApply(rec!, src)}
      />
    )
  }

  return (
    <div className="space-y-3">
      {/* 제목 + quality bar */}
      <div className="bg-white rounded-lg border border-slate-200 p-4 space-y-1">
        <div className="text-sm font-bold text-slate-900">
          <InlineField value={content.title} onSave={(v) => patch({ title: v })} placeholder="제목" />
        </div>
        {content.original_title && (
          <p className="text-xs text-slate-400">{content.original_title}</p>
        )}
        <div className="flex items-center gap-2 pt-0.5">
          <span className="text-xs text-slate-400">#{content.id}</span>
          <div className="flex-1 flex items-center gap-1.5">
            <div className="flex-1 bg-slate-200 rounded-full h-1 overflow-hidden">
              <div className="bg-amber-500 h-full" style={{ width: `${qualityScore}%` }} />
            </div>
            <span className="text-xs font-semibold text-amber-700">{qualityScore}</span>
          </div>
        </div>
      </div>

      {/* 식별 정보 */}
      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
        <ColHeaders />
        <FieldRow
          label="유형"
          current={<span className="text-slate-700">{TYPE_LABEL[content.content_type]}</span>}
          rec={<div className="px-4 py-3 text-xs text-slate-300">—</div>}
        />
        <FieldRow
          label="연도"
          current={
            <InlineField
              value={content.production_year != null ? String(content.production_year) : null}
              onSave={(v) => patch({ production_year: Number(v) })}
              type="number"
              placeholder="2024"
            />
          }
          rec={recFor("production_year")}
        />
        <FieldRow
          label="국가"
          current={
            <InlineField
              value={content.country ?? null}
              onSave={(v) => patch({ country: v })}
              placeholder="한국"
            />
          }
          rec={recFor("country")}
        />
        <FieldRow
          label="상영"
          current={
            <InlineField
              value={content.runtime_minutes != null ? String(content.runtime_minutes) : null}
              onSave={(v) => patch({ runtime: Number(v) })}
              type="number"
              placeholder="120분"
            />
          }
          rec={recFor("runtime")}
        />
        <FieldRow
          label="CP사"
          current={
            <InlineField
              value={content.cp_name ?? null}
              onSave={(v) => patch({ cp_name: v })}
              placeholder="CP사명"
            />
          }
          rec={recFor("cp_name")}
        />
      </div>

      {/* 메타 필드 */}
      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
        <ColHeaders />
        <FieldRow
          label="장르"
          current={
            <InlineField
              value={genres || null}
              onSave={(v) => patch({ genres: v })}
              placeholder="드라마, 스릴러"
            />
          }
          rec={recFor("genres")}
        />
        <FieldRow
          label="감독"
          current={
            <InlineField
              value={directors || null}
              onSave={(v) => patch({ directors: v })}
              placeholder="감독명"
            />
          }
          rec={recFor("director")}
        />
        <FieldRow
          label="주연"
          current={
            <InlineField
              value={cast || null}
              onSave={(v) => patch({ cast: v })}
              placeholder="배우1, 배우2"
            />
          }
          rec={recFor("cast")}
        />
      </div>

      {/* 시놉시스 */}
      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
        <ColHeaders />
        <FieldRow
          label="줄거리"
          current={
            <InlineField
              value={synopsis}
              onSave={(v) => patch({ synopsis: v })}
              type="textarea"
              placeholder="줄거리를 입력하세요"
            />
          }
          rec={recFor("synopsis")}
        />
      </div>
    </div>
  )
}
