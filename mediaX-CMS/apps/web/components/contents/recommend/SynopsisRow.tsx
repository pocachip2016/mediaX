"use client"

import { useState } from "react"
import { ChevronDown, ChevronUp } from "lucide-react"
import { cn } from "@workspace/ui/lib/utils"
import type { FieldRecommendation, SourceFieldRec } from "@/lib/api"
import type { FieldKind } from "@/lib/recommendDerive"
import { classifyField, reasonSummary } from "@/lib/recommendDerive"

interface Props {
  currentSynopsis: string | null
  rec: FieldRecommendation | null
  isApplied: boolean
  onApply: (source: SourceFieldRec) => Promise<void>
  onEdit: () => void
}

const SOURCE_LABEL: Record<string, string> = {
  tmdb: "TMDB",
  watcha: "Watcha",
  kobis: "KOBIS",
  kmdb: "KMDB",
  ai: "AI",
  manual: "수동",
}

function srcName(source_type: string): string {
  return SOURCE_LABEL[source_type] ?? source_type.toUpperCase()
}

function ExpandableText({ text, maxHeightPx = 200 }: { text: string; maxHeightPx?: number }) {
  const [expanded, setExpanded] = useState(false)
  const lines = text.split("\n")
  const isTruncated = text.length > 300 // 간단한 휴리스틱

  if (!isTruncated) {
    return <p className="text-sm text-slate-800 break-words leading-relaxed">{text}</p>
  }

  return (
    <div>
      <div
        className={cn(
          "overflow-hidden transition-all",
          expanded ? "" : `max-h-[${maxHeightPx}px]`
        )}
        style={!expanded ? { maxHeight: `${maxHeightPx}px` } : undefined}
      >
        <p className="text-sm text-slate-800 break-words leading-relaxed">{text}</p>
      </div>
      <button
        onClick={() => setExpanded(!expanded)}
        className="mt-2 inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 font-medium"
      >
        {expanded ? (
          <>
            <ChevronUp className="h-3 w-3" /> 접기
          </>
        ) : (
          <>
            <ChevronDown className="h-3 w-3" /> 더보기
          </>
        )}
      </button>
    </div>
  )
}

export function SynopsisRow({ currentSynopsis, rec, isApplied, onApply, onEdit }: Props) {
  const kind = classifyField(rec)
  const [applyingSource, setApplyingSource] = useState<string | null>(null)

  async function handleApply(source: SourceFieldRec) {
    setApplyingSource(source.source_type)
    try {
      await onApply(source)
    } finally {
      setApplyingSource(null)
    }
  }

  return (
    <div className="flex flex-col gap-3 p-5 bg-white rounded-lg border">
      {/* 현재 메타 섹션 */}
      <div>
        <div className="flex items-center gap-2 mb-2">
          <h3 className="text-sm font-semibold text-slate-700">📖 줄거리</h3>
          <button
            onClick={onEdit}
            className="text-xs text-blue-600 hover:text-blue-700 font-medium"
          >
            편집
          </button>
        </div>
        {currentSynopsis ? (
          <>
            <ExpandableText text={currentSynopsis} />
            {rec && (
              <p className="mt-2 text-xs text-slate-400">
                final · {reasonSummary(rec)}
              </p>
            )}
          </>
        ) : (
          <p className="text-sm text-slate-400 italic">입력 없음</p>
        )}
      </div>

      {/* Diff 섹션 */}
      {rec && rec.recommendations.length > 0 && (
        <div className="pt-3 border-t border-slate-100">
          <h4 className="text-xs font-semibold text-slate-500 mb-2">Diff (소스 비교)</h4>
          <div className="space-y-3">
            {rec.recommendations.map((src, i) => (
              <div key={i} className="flex gap-3">
                <div className="min-w-0 flex-1">
                  <p className="text-[10px] font-medium text-slate-400 uppercase mb-1">
                    {srcName(src.source_type)}{" "}
                    <span className="text-slate-300 font-normal">{src.confidence.toFixed(2)}</span>
                  </p>
                  <ExpandableText text={src.value} maxHeightPx={120} />
                </div>
                {/* conflict일 때만 Apply 가능 */}
                {kind === "conflict" && !isApplied && (
                  <button
                    onClick={() => void handleApply(src)}
                    disabled={applyingSource === src.source_type}
                    className="shrink-0 text-xs text-blue-600 hover:text-blue-700 font-medium whitespace-nowrap disabled:opacity-50"
                  >
                    {applyingSource === src.source_type ? "적용 중..." : `Apply ${srcName(src.source_type)}`}
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* AI 추천 섹션 */}
      {rec && (
        <div className="pt-3 border-t border-slate-100">
          <h4 className="text-xs font-semibold text-slate-500 mb-2">AI 추천</h4>
          {kind === "conflict" ? (
            <p className="text-xs text-amber-600">⚠ 충돌 — Diff에서 선택해주세요</p>
          ) : isApplied ? (
            <span className="inline-block text-xs bg-slate-100 text-slate-500 px-2 py-1 rounded">
              채택됨
            </span>
          ) : (
            <div className="space-y-2">
              {rec.ai_synthesis && (
                <>
                  <p className="text-sm text-slate-800 break-words leading-relaxed">
                    {rec.ai_synthesis.value}
                  </p>
                  <p className="text-[10px] text-slate-400">{reasonSummary(rec)}</p>
                </>
              )}
              {!rec.ai_synthesis && rec.recommendations[0] && (
                <>
                  <p className="text-sm text-slate-800 break-words leading-relaxed">
                    {rec.recommendations[0].value}
                  </p>
                  <p className="text-[10px] text-slate-400">{reasonSummary(rec)}</p>
                </>
              )}
              <button
                onClick={() => void handleApply(rec.ai_synthesis ?? rec.recommendations[0]!)}
                disabled={applyingSource === "apply"}
                className="text-xs text-blue-600 hover:text-blue-700 font-medium disabled:opacity-50"
              >
                {applyingSource === "apply" ? "적용 중..." : "개별 적용"}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
