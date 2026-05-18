"use client"

import React, { useState } from "react"
import { X, Check, AlertCircle, Sparkles, Pencil } from "lucide-react"
import { cn } from "@workspace/ui/lib/utils"
import { SourceBadge } from "@/components/source-badge"
import type { RecommendationsOut, FieldRecommendation, SourceFieldRec } from "@/lib/api"

const FIELD_LABELS: Record<string, string> = {
  cast: "주연", director: "감독", synopsis: "줄거리",
  runtime: "런타임", country: "제작국가", genres: "장르",
  title: "제목", original_title: "원제", production_year: "제작연도",
}

type Props = {
  recommendations: RecommendationsOut
  currentValues: Record<string, string | null>
  onDismiss(): void
  onApply(rec: FieldRecommendation, source: SourceFieldRec): Promise<void>
  onApplyAll(): Promise<void>
  onEditManually(field: string): void
}

export function MetadataDiffPanel({
  recommendations,
  currentValues,
  onDismiss,
  onApply,
  onApplyAll,
  onEditManually,
}: Props) {
  const [applying, setApplying] = useState<string | null>(null)
  const [applyingAll, setApplyingAll] = useState(false)

  const missingCount = recommendations.missing_fields.length
  const conflictCount = recommendations.conflicts.length
  const autoCount = recommendations.auto_fill.length

  async function handleApply(rec: FieldRecommendation, src: SourceFieldRec) {
    setApplying(`${rec.field}-${src.source_id}`)
    await onApply(rec, src).catch(() => {})
    setApplying(null)
  }

  async function handleApplyAll() {
    setApplyingAll(true)
    await onApplyAll().catch(() => {})
    setApplyingAll(false)
  }

  return (
    <div className="bg-white rounded-lg border border-blue-200 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-blue-50 border-b border-blue-100">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-blue-600" />
          <span className="text-sm font-semibold text-blue-900">메타 보강 제안</span>
          {missingCount > 0 && (
            <span className="text-xs text-amber-700 bg-amber-100 rounded-full px-2 py-0.5">
              {missingCount}개 미입력
            </span>
          )}
          {conflictCount > 0 && (
            <span className="text-xs text-red-700 bg-red-100 rounded-full px-2 py-0.5">
              {conflictCount}개 충돌
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {autoCount > 1 && (
            <button
              onClick={handleApplyAll}
              disabled={applyingAll}
              className="text-xs px-3 py-1 rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {applyingAll ? "적용중…" : `${autoCount}개 모두 채택`}
            </button>
          )}
          <button onClick={onDismiss} className="text-slate-400 hover:text-slate-600">
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 border-b border-slate-100">
            <tr>
              <th className="text-left px-3 py-2 text-xs font-medium text-slate-500 w-28">Field</th>
              <th className="text-left px-3 py-2 text-xs font-medium text-slate-500 w-40">Current</th>
              <th className="text-left px-3 py-2 text-xs font-medium text-slate-500">Suggestion</th>
              <th className="text-left px-3 py-2 text-xs font-medium text-slate-500 w-24">Source</th>
              <th className="text-right px-3 py-2 text-xs font-medium text-slate-500 w-16">Conf</th>
              <th className="text-right px-3 py-2 text-xs font-medium text-slate-500 w-28">Action</th>
            </tr>
          </thead>
          <tbody>
            {/* auto_fill rows */}
            {recommendations.auto_fill.map((rec) => {
              const top = rec.recommendations[0]!
              const key = `${rec.field}-${top.source_id}`
              return (
                <tr key={rec.field} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="px-3 py-2 text-xs font-medium text-slate-600">
                    <span className="flex items-center gap-1">
                      <Check className="h-3 w-3 text-green-500 flex-shrink-0" />
                      {FIELD_LABELS[rec.field] ?? rec.field}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-xs text-slate-400 italic">
                    {currentValues[rec.field] ?? "—"}
                  </td>
                  <td className="px-3 py-2 text-xs text-slate-800 line-clamp-2">
                    {top.value}
                  </td>
                  <td className="px-3 py-2">
                    <SourceBadge source={top.source_type} score={top.confidence} />
                  </td>
                  <td className="px-3 py-2 text-right text-xs tabular-nums">
                    {(top.confidence * 100).toFixed(0)}%
                  </td>
                  <td className="px-3 py-2 text-right">
                    <button
                      disabled={applying === key}
                      onClick={() => handleApply(rec, top)}
                      className="text-xs px-2 py-1 rounded bg-blue-50 text-blue-700 hover:bg-blue-100 disabled:opacity-50 transition-colors"
                    >
                      {applying === key ? "…" : "Apply"}
                    </button>
                  </td>
                </tr>
              )
            })}

            {/* conflict rows — group per field */}
            {recommendations.conflicts.map((rec) => (
              <React.Fragment key={rec.field}>
                {rec.recommendations.map((r, idx) => (
                  <tr
                    key={`${rec.field}-${r.source_id}`}
                    className={cn(
                      "border-b border-slate-100 hover:bg-amber-50/50",
                      idx === 0 && "border-t-2 border-t-amber-200"
                    )}
                  >
                    {idx === 0 && (
                      <td
                        rowSpan={rec.recommendations.length + (rec.ai_synthesis ? 1 : 0)}
                        className="px-3 py-2 text-xs font-medium text-amber-700 align-top"
                      >
                        <span className="flex items-center gap-1">
                          <AlertCircle className="h-3 w-3 flex-shrink-0" />
                          {FIELD_LABELS[rec.field] ?? rec.field}
                        </span>
                        <span className="text-[10px] text-amber-500 mt-0.5 block">충돌</span>
                      </td>
                    )}
                    {idx === 0 && (
                      <td
                        rowSpan={rec.recommendations.length + (rec.ai_synthesis ? 1 : 0)}
                        className="px-3 py-2 text-xs text-slate-400 italic align-top"
                      >
                        {currentValues[rec.field] ?? "—"}
                      </td>
                    )}
                    <td className="px-3 py-2 text-xs text-slate-700 line-clamp-2">{r.value}</td>
                    <td className="px-3 py-2">
                      <SourceBadge source={r.source_type} score={r.confidence} />
                    </td>
                    <td className="px-3 py-2 text-right text-xs tabular-nums">
                      {(r.confidence * 100).toFixed(0)}%
                    </td>
                    <td className="px-3 py-2 text-right">
                      <button
                        disabled={applying === `${rec.field}-${r.source_id}`}
                        onClick={() => handleApply(rec, r)}
                        className="text-xs px-2 py-1 rounded bg-amber-50 text-amber-700 hover:bg-amber-100 disabled:opacity-50 transition-colors"
                      >
                        {applying === `${rec.field}-${r.source_id}` ? "…" : "Apply"}
                      </button>
                    </td>
                  </tr>
                ))}

                {/* AI synthesis row */}
                {rec.ai_synthesis && (() => {
                  const syn = rec.ai_synthesis
                  const key = `${rec.field}-${syn.source_id}`
                  return (
                    <tr key={`${rec.field}-ai`} className="border-b border-slate-100 bg-purple-50/40 hover:bg-purple-50">
                      <td className="px-3 py-2 text-xs text-slate-700 line-clamp-2">
                        <span className="flex items-center gap-1 text-purple-700 font-medium mb-0.5">
                          <Sparkles className="h-3 w-3" /> AI 종합
                        </span>
                        {syn.value}
                      </td>
                      <td className="px-3 py-2">
                        <SourceBadge source={syn.source_type} score={syn.confidence} />
                      </td>
                      <td className="px-3 py-2 text-right text-xs tabular-nums">
                        {(syn.confidence * 100).toFixed(0)}%
                      </td>
                      <td className="px-3 py-2 text-right">
                        <button
                          disabled={applying === key}
                          onClick={() => handleApply(rec, syn)}
                          className="text-xs px-2 py-1 rounded bg-purple-100 text-purple-700 hover:bg-purple-200 disabled:opacity-50 transition-colors"
                        >
                          {applying === key ? "…" : "Apply"}
                        </button>
                      </td>
                    </tr>
                  )
                })()}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>

      {/* Footer */}
      {recommendations.conflicts.length > 0 && (
        <div className="flex items-center gap-2 px-4 py-2 border-t border-slate-100 bg-slate-50">
          <button
            onClick={() => onEditManually(recommendations.conflicts[0]?.field ?? "")}
            className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-700 transition-colors"
          >
            <Pencil className="h-3 w-3" /> 수동 편집
          </button>
        </div>
      )}
    </div>
  )
}
