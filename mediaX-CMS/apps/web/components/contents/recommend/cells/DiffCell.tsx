import type { FieldRecommendation, SourceFieldRec } from "@/lib/api"
import type { FieldKind } from "@/lib/recommendDerive"

const SOURCE_LABEL: Record<string, string> = {
  tmdb: "TMDB", watcha: "Watcha", kobis: "KOBIS",
  kmdb: "KMDB", ai: "AI", manual: "수동",
}

function srcName(source_type: string): string {
  return SOURCE_LABEL[source_type] ?? source_type.toUpperCase()
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

  return (
    <div className="px-4 py-3 border-r border-slate-100 space-y-2">
      {rec.recommendations.map((src, i) => (
        <div key={i} className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <p className="text-[10px] font-medium text-slate-400 uppercase mb-0.5">
              {srcName(src.source_type)}{" "}
              <span className="text-slate-300 font-normal">{src.confidence.toFixed(2)}</span>
            </p>
            <p className="text-xs text-slate-700 break-words">{src.value}</p>
          </div>
          {/* conflict일 때만 DiffCell에서 Apply 가능 */}
          {kind === "conflict" && !isApplied && (
            <button
              onClick={() => void onApply(src)}
              className="shrink-0 text-[10px] text-blue-600 hover:text-blue-700 font-medium whitespace-nowrap mt-3"
            >
              Apply {srcName(src.source_type)}
            </button>
          )}
        </div>
      ))}
    </div>
  )
}
