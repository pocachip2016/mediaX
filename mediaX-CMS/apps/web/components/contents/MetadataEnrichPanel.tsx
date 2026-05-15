"use client"

import { useState, useMemo } from "react"
import { X, Sparkles, RefreshCw, Check, AlertCircle, Circle } from "lucide-react"
import { cn } from "@workspace/ui/lib/utils"
import { SourceBadge } from "@/components/source-badge"
import type { RecommendationsOut, FieldRecommendation, SourceFieldRec } from "@/lib/api"

// ── 상수 ─────────────────────────────────────────────────

const FIELD_LABELS: Record<string, string> = {
  cast: "주연", director: "감독", synopsis: "줄거리",
  runtime: "런타임", country: "제작국가", genres: "장르",
  title: "제목", original_title: "원제", production_year: "제작연도",
}

function fieldLabel(field: string) {
  return FIELD_LABELS[field] ?? field
}

// ── 확정 조건 ─────────────────────────────────────────────

function isConfirmed(rec: FieldRecommendation): boolean {
  return (
    rec.status === "auto" &&
    rec.recommendations.length >= 2 &&
    Math.min(...rec.recommendations.map((r) => r.confidence)) >= 0.90
  )
}

// ── 타입 ─────────────────────────────────────────────────

type FieldKind = "confirmed" | "auto" | "conflict" | "missing"

type FieldEntry = {
  field: string
  kind: FieldKind
  rec: FieldRecommendation | null
}

type Props = {
  recommendations: RecommendationsOut
  currentValues: Record<string, string | null>
  onApply(rec: FieldRecommendation, source: SourceFieldRec): Promise<void>
  onApplyAll(targets: Array<{ rec: FieldRecommendation; source: SourceFieldRec }>): Promise<void>
  onRegenerate(): Promise<void>
  onDismiss(): void
}

// ── 메인 컴포넌트 ─────────────────────────────────────────

export function MetadataEnrichPanel({
  recommendations,
  currentValues,
  onApply,
  onApplyAll,
  onRegenerate,
  onDismiss,
}: Props) {
  const [applying, setApplying] = useState<string | null>(null)
  const [applyingAll, setApplyingAll] = useState(false)
  const [regenerating, setRegenerating] = useState(false)

  // 왼쪽 패널 필드 목록 구성
  const fields: FieldEntry[] = useMemo(() => {
    const entries: FieldEntry[] = []
    const seen = new Set<string>()

    for (const rec of recommendations.auto_fill) {
      seen.add(rec.field)
      entries.push({ field: rec.field, kind: isConfirmed(rec) ? "confirmed" : "auto", rec })
    }
    for (const rec of recommendations.conflicts) {
      seen.add(rec.field)
      entries.push({ field: rec.field, kind: "conflict", rec })
    }
    for (const field of recommendations.missing_fields) {
      if (!seen.has(field)) {
        entries.push({ field, kind: "missing", rec: null })
      }
    }
    return entries
  }, [recommendations])

  const [selectedField, setSelectedField] = useState<string>(fields[0]?.field ?? "")
  const selected = fields.find((f) => f.field === selectedField) ?? fields[0] ?? null

  // Apply confirmed only
  const confirmedTargets = useMemo(() =>
    recommendations.auto_fill
      .filter(isConfirmed)
      .map((rec) => ({ rec, source: rec.recommendations[0]! }))
  , [recommendations])

  async function handleApply(rec: FieldRecommendation, src: SourceFieldRec) {
    const key = `${rec.field}-${src.source_id}`
    setApplying(key)
    await onApply(rec, src).catch(() => {})
    setApplying(null)
  }

  async function handleApplyAll() {
    setApplyingAll(true)
    await onApplyAll(confirmedTargets).catch(() => {})
    setApplyingAll(false)
  }

  async function handleRegenerate() {
    setRegenerating(true)
    await onRegenerate().catch(() => {})
    setRegenerating(false)
  }

  if (fields.length === 0) {
    return (
      <div className="bg-white rounded-lg border border-blue-200 p-6 text-center">
        <Check className="h-8 w-8 mx-auto text-green-500 mb-2" />
        <p className="text-sm font-medium text-slate-700">모든 필드가 채워져 있습니다.</p>
        <button onClick={onDismiss} className="mt-3 text-xs text-slate-400 hover:text-slate-600">닫기</button>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-lg border border-blue-200 overflow-hidden">
      {/* 헤더 */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-blue-50 border-b border-blue-100">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-blue-600" />
          <span className="text-sm font-semibold text-blue-900">AI Enrich</span>
          <span className="text-xs text-blue-600 bg-blue-100 rounded-full px-2 py-0.5">
            {fields.length}개 필드
          </span>
        </div>
        <button onClick={onDismiss} className="text-slate-400 hover:text-slate-600">
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* 본문 2패널 */}
      <div className="flex flex-col lg:flex-row min-h-0">
        {/* 왼쪽: 필드 목록 */}
        <div className="lg:w-52 flex-shrink-0 border-b lg:border-b-0 lg:border-r border-slate-100 overflow-y-auto max-h-72 lg:max-h-96">
          <div className="p-2 space-y-0.5">
            {fields.map((entry) => (
              <button
                key={entry.field}
                onClick={() => setSelectedField(entry.field)}
                className={cn(
                  "w-full flex items-center gap-2 px-2.5 py-2 rounded-md text-left text-xs transition-colors",
                  selectedField === entry.field
                    ? "bg-blue-50 text-blue-800 font-medium"
                    : "text-slate-600 hover:bg-slate-50"
                )}
              >
                <FieldKindIcon kind={entry.kind} />
                <span className="flex-1 truncate">{fieldLabel(entry.field)}</span>
                <span className="text-[10px] text-slate-400 truncate max-w-[60px]">
                  {currentValues[entry.field] ?? "—"}
                </span>
              </button>
            ))}
          </div>
        </div>

        {/* 오른쪽: 추천 상세 */}
        <div className="flex-1 p-4 space-y-3 overflow-y-auto max-h-96">
          {selected ? (
            <FieldRecommendations
              entry={selected}
              applying={applying}
              onApply={handleApply}
            />
          ) : (
            <p className="text-sm text-muted-foreground text-center py-8">
              왼쪽에서 필드를 선택하세요
            </p>
          )}
        </div>
      </div>

      {/* 하단 액션 */}
      <div className="flex items-center gap-2 px-4 py-2.5 border-t border-slate-100 bg-slate-50">
        <button
          onClick={handleApplyAll}
          disabled={applyingAll || confirmedTargets.length === 0}
          className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          title={confirmedTargets.length === 0 ? "확정 후보(2+ DB 일치 + 신뢰도 90% 이상)가 없습니다" : undefined}
        >
          <Check className="h-3 w-3" />
          {applyingAll ? "적용중…" : `Apply confirmed only (${confirmedTargets.length})`}
        </button>
        <button
          onClick={handleRegenerate}
          disabled={regenerating}
          className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded bg-slate-200 text-slate-700 hover:bg-slate-300 disabled:opacity-50 transition-colors"
        >
          <RefreshCw className={cn("h-3 w-3", regenerating && "animate-spin")} />
          {regenerating ? "요청중…" : "Regenerate"}
        </button>
      </div>
    </div>
  )
}

// ── FieldKindIcon ─────────────────────────────────────────

function FieldKindIcon({ kind }: { kind: FieldKind }) {
  if (kind === "confirmed") return <Check className="h-3 w-3 text-green-500 flex-shrink-0" />
  if (kind === "conflict")  return <AlertCircle className="h-3 w-3 text-red-400 flex-shrink-0" />
  if (kind === "auto")      return <Sparkles className="h-3 w-3 text-blue-400 flex-shrink-0" />
  return <Circle className="h-3 w-3 text-slate-300 flex-shrink-0" />
}

// ── FieldRecommendations (오른쪽 패널 내용) ──────────────

function FieldRecommendations({
  entry,
  applying,
  onApply,
}: {
  entry: FieldEntry
  applying: string | null
  onApply(rec: FieldRecommendation, src: SourceFieldRec): void
}) {
  const { field, kind, rec } = entry

  if (!rec) {
    return (
      <div className="text-center py-6">
        <Circle className="h-6 w-6 mx-auto text-slate-200 mb-2" />
        <p className="text-xs text-slate-400">추천 데이터 없음</p>
        <p className="text-[10px] text-slate-300 mt-1">Regenerate로 AI 분석을 요청하세요</p>
      </div>
    )
  }

  const confirmed = isConfirmed(rec)
  const sources = rec.recommendations

  return (
    <div className="space-y-3">
      <p className="text-xs font-semibold text-slate-600">
        {fieldLabel(field)}
        {kind === "conflict" && (
          <span className="ml-1.5 text-red-500 font-normal">— 소스 불일치</span>
        )}
      </p>

      {/* 확정 후보 */}
      {confirmed && (
        <RecommendationCard
          label="확정 후보"
          tone="green"
          description={`${sources.length}개 External DB 일치`}
          confidence={sources[0]!.confidence}
          sourceNames={sources.map((s) => s.source_type.toUpperCase())}
          value={sources[0]!.value}
          applyKey={`${field}-${sources[0]!.source_id}`}
          applying={applying}
          onApply={() => onApply(rec, sources[0]!)}
        />
      )}

      {/* AI Mix (ai_synthesis) */}
      {rec.ai_synthesis && (
        <RecommendationCard
          label="AI Mix 추천"
          tone="purple"
          description="Mixed AI recommendation"
          confidence={rec.ai_synthesis.confidence}
          sourceNames={[...sources.map((s) => s.source_type.toUpperCase()), "AI"]}
          value={rec.ai_synthesis.value}
          applyKey={`${field}-${rec.ai_synthesis.source_id}`}
          applying={applying}
          onApply={() => onApply(rec, rec.ai_synthesis!)}
        />
      )}

      {/* 대체 후보 */}
      {(!confirmed || kind === "conflict") && (
        <div className="border border-slate-100 rounded-lg overflow-hidden">
          <div className="px-3 py-2 bg-slate-50 border-b border-slate-100">
            <span className="text-xs font-medium text-slate-500">대체 후보</span>
          </div>
          <div className="divide-y divide-slate-100">
            {sources.map((src) => (
              <AlternativeRow
                key={src.source_id}
                rec={rec}
                src={src}
                applying={applying}
                onApply={onApply}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ── RecommendationCard ────────────────────────────────────

type CardTone = "green" | "purple"

const CARD_STYLES: Record<CardTone, { border: string; bg: string; badge: string }> = {
  green:  { border: "border-green-200",  bg: "bg-green-50/60",   badge: "bg-green-100 text-green-700" },
  purple: { border: "border-purple-200", bg: "bg-purple-50/60",  badge: "bg-purple-100 text-purple-700" },
}

function RecommendationCard({
  label, tone, description, confidence, sourceNames, value,
  applyKey, applying, onApply,
}: {
  label: string
  tone: CardTone
  description: string
  confidence: number
  sourceNames: string[]
  value: string
  applyKey: string
  applying: string | null
  onApply(): void
}) {
  const s = CARD_STYLES[tone]
  return (
    <div className={cn("rounded-lg border p-3 space-y-2", s.border, s.bg)}>
      <div className="flex items-start justify-between gap-2">
        <div className="space-y-1 flex-1 min-w-0">
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className={cn("text-[10px] font-semibold px-1.5 py-0.5 rounded", s.badge)}>
              {label}
            </span>
            <span className="text-[10px] text-slate-500">
              {(confidence * 100).toFixed(0)}% · {sourceNames.join(" + ")}
            </span>
          </div>
          <p className="text-xs text-slate-500">{description}</p>
          <p className="text-xs text-slate-800 leading-relaxed line-clamp-3">{value}</p>
        </div>
        <button
          onClick={onApply}
          disabled={applying === applyKey}
          className="flex-shrink-0 text-xs px-2.5 py-1 rounded bg-white border border-slate-200 text-slate-700 hover:bg-blue-50 hover:border-blue-300 hover:text-blue-700 disabled:opacity-50 transition-colors"
        >
          {applying === applyKey ? "…" : "Apply"}
        </button>
      </div>
    </div>
  )
}

// ── AlternativeRow ────────────────────────────────────────

function AlternativeRow({
  rec, src, applying, onApply,
}: {
  rec: FieldRecommendation
  src: SourceFieldRec
  applying: string | null
  onApply(rec: FieldRecommendation, src: SourceFieldRec): void
}) {
  const key = `${rec.field}-${src.source_id}`
  return (
    <div className="flex items-center gap-2 px-3 py-2">
      <Circle className="h-3 w-3 text-slate-300 flex-shrink-0" />
      <div className="flex-1 min-w-0">
        <p className="text-xs text-slate-700 line-clamp-1">{src.value}</p>
        <div className="flex items-center gap-1.5 mt-0.5">
          <SourceBadge source={src.source_type} score={src.confidence} />
          <span className="text-[10px] text-slate-400">{(src.confidence * 100).toFixed(0)}%</span>
        </div>
      </div>
      <button
        onClick={() => onApply(rec, src)}
        disabled={applying === key}
        className="flex-shrink-0 text-xs px-2 py-0.5 rounded bg-slate-100 text-slate-600 hover:bg-blue-50 hover:text-blue-700 disabled:opacity-50 transition-colors"
      >
        {applying === key ? "…" : "Apply"}
      </button>
    </div>
  )
}
