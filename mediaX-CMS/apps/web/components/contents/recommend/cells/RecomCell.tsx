import type { FieldRecommendation, SourceFieldRec } from "@/lib/api"
import type { FieldKind } from "@/lib/recommendDerive"
import { reasonSummary, isSimilar } from "@/lib/recommendDerive"

interface Props {
  rec: FieldRecommendation | null
  kind: FieldKind
  isApplied: boolean
  onApply: (source: SourceFieldRec) => Promise<void>
  long?: boolean
  currentValue?: string | null
}

function ApplyButton({ src, currentValue, onApply }: { src: SourceFieldRec; currentValue?: string | null; onApply: (src: SourceFieldRec) => Promise<void> }) {
  if (isSimilar(src.value, currentValue)) {
    return <span className="text-[10px] text-slate-400 italic shrink-0">현재 값과 동일</span>
  }
  return (
    <button
      onClick={() => void onApply(src)}
      className="text-[10px] text-blue-600 hover:text-blue-700 font-medium shrink-0"
    >
      개별 적용
    </button>
  )
}

export function RecomCell({ rec, kind, isApplied, onApply, long, currentValue }: Props) {
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
    const srcs = [
      ...rec.recommendations,
      ...(rec.ai_synthesis ? [rec.ai_synthesis] : [])
    ]

    if (long) {
      return (
        <div className="px-3 py-2 space-y-2">
          {srcs.map((src) => (
            <div key={`${src.source_type}-${src.source_id}`} className="border border-amber-100 rounded p-2 space-y-1.5 bg-amber-50/30">
              <div className="flex items-center gap-1.5">
                <span className="text-[10px] bg-amber-100 text-amber-700 px-1 rounded uppercase font-medium">{src.source_type}</span>
                <span className="text-[10px] text-slate-400">{src.confidence.toFixed(2)}</span>
              </div>
              <div className="max-h-16 overflow-y-auto text-xs text-slate-700 whitespace-pre-wrap border border-amber-50 rounded px-1.5 py-1 bg-white">
                {src.value}
              </div>
              <ApplyButton src={src} currentValue={currentValue} onApply={onApply} />
            </div>
          ))}
        </div>
      )
    }

    return (
      <div className="px-3 py-2 divide-y divide-amber-50">
        {srcs.map((src) => (
          <div key={`${src.source_type}-${src.source_id}`} className="py-1.5 flex items-baseline gap-1.5 flex-wrap">
            <span className="text-xs text-slate-700 flex-1 min-w-0 truncate">{src.value}</span>
            <span className="text-[10px] bg-amber-100 text-amber-700 px-1 rounded uppercase shrink-0">
              {src.source_type}({src.confidence.toFixed(2)})
            </span>
            <ApplyButton src={src} currentValue={currentValue} onApply={onApply} />
          </div>
        ))}
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

  // auto — 한 줄 (short) 또는 스크롤 박스 (long) 레이아웃
  if (long) {
    return (
      <div className="px-4 py-2 space-y-1.5">
        {top && (
          <div className="max-h-20 overflow-y-auto text-xs text-slate-700 border border-slate-100 rounded px-2 py-1.5 bg-slate-50 whitespace-pre-wrap">
            {top.value}
          </div>
        )}
        <div className="flex items-baseline gap-1.5 flex-wrap">
          <span className="text-[10px] bg-slate-100 text-slate-500 px-1 rounded uppercase">{top?.source_type}</span>
          <span className="text-[10px] text-slate-400">{top?.confidence.toFixed(2)}</span>
          {top && <ApplyButton src={top} currentValue={currentValue} onApply={onApply} />}
        </div>
      </div>
    )
  }

  // short (default) — 한 줄
  return (
    <div className="px-4 py-2.5 flex items-baseline gap-1.5 flex-wrap">
      {top && <span className="text-xs text-slate-700">{top.value}</span>}
      <span className="text-[10px] bg-slate-100 text-slate-500 px-1 rounded uppercase">{top?.source_type}</span>
      <span className="text-[10px] text-slate-400">{top?.confidence.toFixed(2)}</span>
      {top && <ApplyButton src={top} currentValue={currentValue} onApply={onApply} />}
    </div>
  )
}
