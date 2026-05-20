"use client"

import { cn } from "@workspace/ui/lib/utils"
import type { FieldRecommendation, RecommendationsOut, SourceFieldRec } from "@/lib/api"
import { classifyField } from "@/lib/recommendDerive"
import { RecomCell } from "@/components/contents/recommend/cells/RecomCell"

const FIELDS = [
  { field: "production_year", label: "연도",   icon: "📅" },
  { field: "country",         label: "국가",   icon: "🌐" },
  { field: "runtime",         label: "런타임", icon: "⏱" },
  { field: "cp_name",         label: "CP사",   icon: "🏢" },
  { field: "genres",          label: "장르",   icon: "🎭" },
  { field: "director",        label: "감독",   icon: "🎬" },
  { field: "cast",            label: "주연",   icon: "👤" },
  { field: "synopsis",        label: "줄거리", icon: "📖" },
] as const

function findRec(recs: RecommendationsOut | null, field: string): FieldRecommendation | null {
  if (!recs) return null
  return [...recs.auto_fill, ...recs.conflicts].find((r) => r.field === field) ?? null
}

type Props = {
  recommendations: RecommendationsOut | null
  appliedFields: Set<string>
  onApply: (rec: FieldRecommendation, source: SourceFieldRec) => Promise<void>
}

export function AIRecColumn({ recommendations, appliedFields, onApply }: Props) {
  return (
    <div className="bg-white rounded-lg border overflow-hidden">
      <div className="px-4 py-2.5 border-b bg-slate-50">
        <span className="text-xs font-semibold text-slate-500">AI 추천</span>
      </div>

      {FIELDS.map(({ field, label, icon }, idx) => {
        const rec = findRec(recommendations, field)
        const kind = classifyField(rec)
        const isApplied = appliedFields.has(field)

        return (
          <div
            key={field}
            className={cn("flex items-start", idx > 0 && "border-t border-slate-100")}
          >
            <div className="flex flex-col items-center justify-start pt-3 gap-0.5 px-2 w-12 shrink-0 border-r border-slate-100">
              <span className="text-base leading-none">{icon}</span>
              <span className="text-[10px] text-slate-400 leading-tight">{label}</span>
            </div>
            <div className="flex-1 min-w-0">
              <RecomCell
                rec={rec}
                kind={kind}
                isApplied={isApplied}
                onApply={(src) => onApply(rec!, src)}
              />
            </div>
          </div>
        )
      })}
    </div>
  )
}
