"use client"

import { cn } from "@workspace/ui/lib/utils"
import type { ContentDetail, FieldRecommendation, RecommendationsOut, SourceFieldRec } from "@/lib/api"
import { classifyField } from "@/lib/recommendDerive"
import { MetaCell } from "./cells/MetaCell"
import { DiffCell } from "./cells/DiffCell"
import { RecomCell } from "./cells/RecomCell"
import { InheritedLockCell } from "./cells/InheritedLockCell"

const FIELDS = [
  { field: "genres",          label: "장르",   icon: "🎭" },
  { field: "cp_name",         label: "CP사",   icon: "🏢" },
  { field: "runtime",         label: "런타임", icon: "⏱" },
  { field: "country",         label: "국가",   icon: "🌐" },
  { field: "production_year", label: "연도",   icon: "📅" },
  { field: "director",        label: "감독",   icon: "🎬" },
  { field: "cast",            label: "주연",   icon: "👤" },
] as const

function getMetaValue(content: ContentDetail, field: string): string | null {
  switch (field) {
    case "genres":
      return content.genres.map((g) => g.genre.name_ko).join(", ") || null
    case "cp_name":
      return content.cp_name
    case "runtime":
      return content.runtime_minutes != null ? `${content.runtime_minutes}분` : null
    case "country":
      return content.country ?? null
    case "production_year":
      return content.production_year != null ? String(content.production_year) : null
    case "director":
      return (
        content.credits
          .filter((c) => c.role === "director" || c.role === "감독")
          .map((c) => c.person.name_ko)
          .join(", ") || null
      )
    case "cast":
      return (
        content.credits
          .filter((c) => c.role === "actor" || c.role === "주연")
          .slice(0, 3)
          .map((c) => c.person.name_ko)
          .join(", ") || null
      )
    default:
      return null
  }
}

function findRec(recs: RecommendationsOut | null, field: string): FieldRecommendation | null {
  if (!recs) return null
  return [...recs.auto_fill, ...recs.conflicts].find((r) => r.field === field) ?? null
}

type Props = {
  content: ContentDetail
  recommendations: RecommendationsOut | null
  appliedFields: Set<string>
  onApply: (rec: FieldRecommendation, source: SourceFieldRec) => Promise<void>
  inheritedFields?: string[]
}

export function ShortMetaGrid({ content, recommendations, appliedFields, onApply, inheritedFields }: Props) {
  return (
    <div className="bg-white rounded-lg border overflow-hidden">
      {/* 컬럼 헤더 — sticky 처리 안 함 (7행이라 noise) */}
      <div className="grid grid-cols-[200px_1fr_1fr] border-b bg-slate-50">
        <div className="px-4 py-2 text-xs font-semibold text-slate-500 border-r border-slate-100">현재 메타</div>
        <div className="px-4 py-2 text-xs font-semibold text-slate-500 border-r border-slate-100">Diff (소스 비교)</div>
        <div className="px-4 py-2 text-xs font-semibold text-slate-500">AI 추천</div>
      </div>

      {/* 필드 행 (7개 고정) */}
      {FIELDS.map(({ field, label, icon }, idx) => {
        const value = getMetaValue(content, field)
        const rec = findRec(recommendations, field)
        const kind = classifyField(rec)
        const isApplied = appliedFields.has(field)
        const isInherited = inheritedFields?.includes(field) ?? false

        return (
          <div
            key={field}
            className={cn(
              "grid grid-cols-[200px_1fr_1fr]",
              idx > 0 && "border-t border-slate-100"
            )}
          >
            {isInherited ? (
              <>
                <div className="relative">
                  <MetaCell label={label} icon={icon} value={value} kind={kind} isApplied={isApplied} />
                  <span className="absolute top-1 right-1 text-[10px] text-slate-400">🔒</span>
                </div>
                <InheritedLockCell />
              </>
            ) : (
              <>
                <MetaCell label={label} icon={icon} value={value} kind={kind} isApplied={isApplied} />
                <DiffCell
                  rec={rec}
                  kind={kind}
                  isApplied={isApplied}
                  onApply={(src) => onApply(rec!, src)}
                />
                <RecomCell
                  rec={rec}
                  kind={kind}
                  isApplied={isApplied}
                  onApply={(src) => onApply(rec!, src)}
                />
              </>
            )}
          </div>
        )
      })}
    </div>
  )
}
