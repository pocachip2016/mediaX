"use client"

import { BASE, type ContentDetail } from "@/lib/api"
import { TYPE_LABEL } from "@/components/contents/detail/contentType"
import { InlineField } from "./InlineField"

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-2 items-start">
      <span className="text-slate-400 w-10 flex-shrink-0 pt-0.5 text-xs">{label}</span>
      <span className="flex-1 text-xs text-slate-700">{children}</span>
    </div>
  )
}

type Props = {
  content: ContentDetail
  contentId: number
  onSaved: (updated: ContentDetail) => void
}

export function CurrentStateColumn({ content, contentId, onSaved }: Props) {
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

  const patch = async (body: Record<string, unknown>) => {
    const res = await fetch(`${BASE}/api/programming/metadata/contents/${contentId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: content.title, cp_name: content.cp_name, ...body }),
    })
    if (!res.ok) throw new Error("저장 실패")
    onSaved((await res.json()) as ContentDetail)
  }

  return (
    <div className="space-y-3">
      {/* 식별 정보 */}
      <div className="bg-white rounded-lg border border-slate-200 p-4 space-y-2">
        <div className="text-sm font-bold text-slate-900">
          <InlineField
            value={content.title}
            onSave={(v) => patch({ title: v })}
            placeholder="제목"
          />
        </div>
        {content.original_title && (
          <p className="text-xs text-slate-400">{content.original_title}</p>
        )}
        <div className="text-xs text-slate-600 space-y-1.5 pt-0.5">
          <Row label="유형"><span>{TYPE_LABEL[content.content_type]}</span></Row>
          <Row label="연도">
            <InlineField
              value={content.production_year != null ? String(content.production_year) : null}
              onSave={(v) => patch({ production_year: Number(v) })}
              type="number"
              placeholder="2024"
            />
          </Row>
          <Row label="국가">
            <InlineField
              value={content.country ?? null}
              onSave={(v) => patch({ country: v })}
              placeholder="한국"
            />
          </Row>
          <Row label="상영">
            <InlineField
              value={content.runtime_minutes != null ? String(content.runtime_minutes) : null}
              onSave={(v) => patch({ runtime: Number(v) })}
              type="number"
              placeholder="120"
            />
          </Row>
          <Row label="CP사">
            <InlineField
              value={content.cp_name ?? null}
              onSave={(v) => patch({ cp_name: v })}
              placeholder="CP사명"
            />
          </Row>
        </div>
        <div className="pt-1 flex items-center gap-2">
          <span className="text-xs text-slate-400">#{content.id}</span>
          <div className="flex-1 flex items-center gap-1.5">
            <div className="flex-1 bg-slate-200 rounded-full h-1 overflow-hidden">
              <div className="bg-amber-500 h-full" style={{ width: `${qualityScore}%` }} />
            </div>
            <span className="text-xs font-semibold text-amber-700">{qualityScore}</span>
          </div>
        </div>
      </div>

      {/* 메타 필드 */}
      <div className="bg-white rounded-lg border border-slate-200 p-4 space-y-2">
        <Row label="장르">
          <InlineField
            value={genres || null}
            onSave={(v) => patch({ genres: v })}
            placeholder="드라마, 스릴러"
          />
        </Row>
        <Row label="감독">
          <InlineField
            value={directors || null}
            onSave={(v) => patch({ directors: v })}
            placeholder="감독명"
          />
        </Row>
        <Row label="주연">
          <InlineField
            value={cast || null}
            onSave={(v) => patch({ cast: v })}
            placeholder="배우1, 배우2"
          />
        </Row>
      </div>

      {/* 시놉시스 */}
      <div className="bg-white rounded-lg border border-slate-200 p-4">
        <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">시놉시스</h3>
        <InlineField
          value={synopsis}
          onSave={(v) => patch({ synopsis: v })}
          type="textarea"
          placeholder="줄거리를 입력하세요"
        />
      </div>
    </div>
  )
}
