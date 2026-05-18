import type { FieldRecommendation, SourceFieldRec } from "@/lib/api"
import type { FieldKind } from "@/lib/recommendDerive"
import { reasonSummary } from "@/lib/recommendDerive"

interface Props {
  rec: FieldRecommendation | null
  kind: FieldKind
  isApplied: boolean
  onApply: (source: SourceFieldRec) => Promise<void>
}

export function RecomCell({ rec, kind, isApplied, onApply }: Props) {
  if (kind === "missing" || !rec) {
    return <div className="px-4 py-3 text-xs text-slate-300">—</div>
  }

  if (isApplied) {
    return (
      <div className="px-4 py-3">
        <span className="inline-block text-xs bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded">
          채택됨
        </span>
      </div>
    )
  }

  if (kind === "conflict") {
    return (
      <div className="px-4 py-3 text-xs text-amber-600 flex items-center gap-1">
        ⚠ 충돌 — Diff에서 선택
      </div>
    )
  }

  // confirmed or auto
  const top = rec.ai_synthesis ?? rec.recommendations[0]
  const summary = reasonSummary(rec)

  if (kind === "confirmed") {
    return (
      <div className="px-4 py-3">
        <span className="inline-block text-xs bg-green-100 text-green-700 px-1.5 py-0.5 rounded font-medium">
          ✓ 채택됨
        </span>
        <p className="text-[10px] text-slate-400 mt-1">{summary}</p>
      </div>
    )
  }

  // auto
  return (
    <div className="px-4 py-3 space-y-1">
      {top && <p className="text-xs text-slate-700 break-words">{top.value}</p>}
      <p className="text-[10px] text-slate-400">{summary}</p>
      {top && (
        <button
          onClick={() => void onApply(top)}
          className="text-[10px] text-blue-600 hover:text-blue-700 font-medium"
        >
          개별 적용
        </button>
      )}
    </div>
  )
}
