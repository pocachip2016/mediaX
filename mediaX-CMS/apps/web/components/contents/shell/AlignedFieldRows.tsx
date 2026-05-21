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
    <div className="grid grid-cols-[5rem_1fr_1fr] border-b bg-slate-50">
      <div />
      <div className="py-2 pl-1 text-xs font-semibold text-slate-500">현재 상태</div>
      <div className="py-2 px-4 text-xs font-semibold text-slate-500 border-l border-slate-100">AI 추천</div>
    </div>
  )
}

function FieldRow({ label, current, rec }: { label: string; current: React.ReactNode; rec: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[5rem_1fr_1fr] items-stretch border-b border-slate-100 last:border-0">
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
  readOnly?: boolean
}

export function AlignedFieldRows({ content, contentId, onSaved, recommendations, appliedFields, onApply, readOnly }: Props) {
  const patch = async (body: Record<string, unknown>) => {
    try {
      const res = await fetch(`${BASE}/api/programming/metadata/contents/${contentId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      })
      if (!res.ok) {
        const detail = await res.text()
        throw new Error(`저장 실패 (${res.status}): ${detail}`)
      }
      onSaved((await res.json()) as ContentDetail)
      alert("적용되었습니다.")
    } catch (err) {
      alert(err instanceof Error ? err.message : "저장 실패")
      throw err
    }
  }

  const directors = (content.credits ?? [])
    .filter((c) => c.role.toLowerCase().includes("director") || c.role === "감독")
    .map((c) => c.person.name_ko)
    .join(", ")

  const cast = (content.credits ?? [])
    .filter((c) => ["actor", "cast", "주연", "출연"].includes(c.role.toLowerCase()))
    .sort((a, b) => (a.cast_order ?? 99) - (b.cast_order ?? 99))
    .map((c) => c.person.name_ko)
    .join(", ")

  const genres = (content.genres ?? []).map((g) => g.genre.name_ko).join(", ")

  const synopsis =
    content.metadata_record?.final_synopsis ||
    content.metadata_record?.ai_synopsis ||
    content.metadata_record?.cp_synopsis ||
    null

  const recFor = (field: string, currentValue?: string | null, long?: boolean) => {
    const rec = findRec(recommendations, field)
    return (
      <RecomCell
        rec={rec}
        kind={classifyField(rec)}
        isApplied={appliedFields.has(field)}
        onApply={(src) => onApply(rec!, src)}
        long={long}
        currentValue={currentValue}
      />
    )
  }

  return (
    <div className="space-y-3">

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
              alwaysEditing
              readOnly={readOnly}
            />
          }
          rec={recFor("production_year", content.production_year != null ? String(content.production_year) : null)}
        />
        <FieldRow
          label="국가"
          current={
            <InlineField
              value={content.country ?? null}
              onSave={(v) => patch({ country: v })}
              placeholder="한국"
              alwaysEditing
              readOnly={readOnly}
            />
          }
          rec={recFor("country", content.country ?? null)}
        />
        <FieldRow
          label="상영"
          current={
            <InlineField
              value={content.runtime_minutes != null ? String(content.runtime_minutes) : null}
              onSave={(v) => patch({ runtime: Number(v) })}
              type="number"
              placeholder="120분"
              alwaysEditing
              readOnly={readOnly}
            />
          }
          rec={recFor("runtime", content.runtime_minutes != null ? String(content.runtime_minutes) : null)}
        />
        <FieldRow
          label="CP사"
          current={
            <InlineField
              value={content.cp_name ?? null}
              onSave={(v) => patch({ cp_name: v })}
              placeholder="CP사명"
              alwaysEditing
              readOnly={readOnly}
            />
          }
          rec={recFor("cp_name", content.cp_name ?? null)}
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
              alwaysEditing
              readOnly={readOnly}
            />
          }
          rec={recFor("genres", genres || null)}
        />
        <FieldRow
          label="감독"
          current={
            <InlineField
              value={directors || null}
              onSave={(v) => patch({ directors: v })}
              placeholder="감독명"
              alwaysEditing
              readOnly={readOnly}
            />
          }
          rec={recFor("director", directors || null)}
        />
        <FieldRow
          label="주연"
          current={
            <InlineField
              value={cast || null}
              onSave={(v) => patch({ cast: v })}
              placeholder="배우1, 배우2"
              alwaysEditing
              readOnly={readOnly}
            />
          }
          rec={recFor("cast", cast || null)}
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
              displayAsBox
              alwaysEditing
              readOnly={readOnly}
            />
          }
          rec={recFor("synopsis", synopsis, true)}
        />
      </div>
    </div>
  )
}
