import type { FieldRecommendation, SourceFieldRec } from "@/lib/api"
import type { FieldKind } from "@/lib/recommendDerive"

const SOURCE_LABEL: Record<string, string> = {
  tmdb: "TMDB", watcha: "Watcha", kobis: "KOBIS",
  kmdb: "KMDB", ai: "AI", manual: "수동",
}

function srcName(s: string): string {
  return SOURCE_LABEL[s] ?? s.toUpperCase()
}

interface Props {
  rec: FieldRecommendation | null
  kind: FieldKind
  isApplied: boolean
  onApply: (source: SourceFieldRec) => Promise<void>
}

export function DiffCell({ rec, kind, isApplied, onApply }: Props) {
  if (!rec || kind === "missing") {
    return <div className="px-4 py-3 border-r border-slate-100 text-xs text-slate-300">—</div>
  }

  // AI 추천값 (오른쪽 컬럼 기준)
  const aiValue = rec.ai_synthesis?.value ?? rec.recommendations[0]?.value ?? null

  // 같은 value끼리 묶기, AI 추천값과 동일하면 제외
  const groups = new Map<string, SourceFieldRec[]>()
  for (const src of rec.recommendations) {
    if (src.value === aiValue) continue
    const existing = groups.get(src.value)
    if (existing) existing.push(src)
    else groups.set(src.value, [src])
  }

  if (groups.size === 0) {
    return <div className="px-4 py-3 border-r border-slate-100 text-xs text-slate-300">—</div>
  }

  return (
    <div className="px-4 py-3 border-r border-slate-100 space-y-2">
      {[...groups.entries()].map(([value, srcs]) => {
        // 소스 라벨 한 줄: "KOBIS 0.87 · TMDB 0.94"
        const label = srcs
          .map((s) => `${srcName(s.source_type)} ${s.confidence.toFixed(2)}`)
          .join(" · ")
        const representative = srcs[0]!
        return (
          <div key={value} className="flex items-start justify-between gap-2">
            <div className="min-w-0 flex-1">
              <p className="text-[10px] text-slate-400 mb-0.5">{label}</p>
              <p className="text-xs text-slate-700 break-words">{value}</p>
            </div>
            {kind === "conflict" && !isApplied && (
              <button
                onClick={() => void onApply(representative)}
                className="shrink-0 text-[10px] text-blue-600 hover:text-blue-700 font-medium whitespace-nowrap mt-3"
              >
                Apply
              </button>
            )}
          </div>
        )
      })}
    </div>
  )
}
