"use client"

import { Check, Database, RefreshCw, Sparkles } from "lucide-react"
import { cn } from "@workspace/ui/lib/utils"
import { SourceBadge } from "@/components/source-badge"
import type { MediSearchResult, MediSearchFacetInfo } from "@/lib/api"

// ── 필드 정의 ─────────────────────────────────────────────

export const META_FIELDS: { key: string; label: string }[] = [
  { key: "synopsis",        label: "줄거리" },
  { key: "genres",          label: "장르" },
  { key: "director",        label: "감독" },
  { key: "cast",            label: "주연" },
  { key: "production_year", label: "제작연도" },
  { key: "country",         label: "제작국가" },
  { key: "runtime",         label: "런타임" },
]

export const FACET_SCORE_LABELS: Record<string, string> = {
  tension:          "긴장감",
  immersion:        "몰입도",
  boredom_risk:     "지루함",
  rewatch_value:    "재관람",
  attention:        "집중도",
  emotional_energy: "감정에너지",
  violence:         "폭력성",
  gore:             "고어",
  sexual:           "선정성",
  spoiler:          "스포일러",
  sentiment:        "감성",
}

export const FACET_LIST_LABELS: Record<string, string> = {
  primary_genre:        "대표장르",
  sub_genre:            "하위장르",
  theme:                "테마",
  mood:                 "무드",
  emotional_aftertaste: "여운",
  ending_type:          "결말유형",
  conflict:             "갈등",
  pacing_reaction:      "페이싱",
  ending_reaction:      "엔딩반응",
}

// ── 유틸 ──────────────────────────────────────────────────

export function fmt(v: unknown): string {
  if (v == null) return "—"
  if (Array.isArray(v)) return v.join(", ")
  return String(v)
}

export function getMetaValue(metadata: Record<string, unknown>, key: string): string {
  const aliases: Record<string, string[]> = {
    synopsis: ["synopsis", "story", "overview"],
    director: ["directors", "director"],
    cast:     ["cast"],
    country:  ["countries", "country"],
    genres:   ["genres"],
    runtime:  ["runtime", "runtime_minutes"],
    production_year: ["production_year"],
  }
  const keys = aliases[key] ?? [key]
  for (const k of keys) {
    const v = metadata[k]
    if (v == null) continue
    if (Array.isArray(v)) {
      if (v.length === 0) continue
      if (typeof v[0] === "object" && v[0] !== null) {
        return (v as { name?: string }[]).map((x) => x.name ?? String(x)).join(", ")
      }
      return (v as unknown[]).map(String).join(", ")
    }
    return String(v)
  }
  return ""
}

export function getProvenance(provenance: Record<string, string[]>, key: string): string[] {
  const aliases: Record<string, string[]> = {
    synopsis: ["synopsis", "story"],
    director: ["directors", "director"],
    cast:     ["cast"],
    country:  ["countries", "country"],
    genres:   ["genres"],
  }
  const keys = aliases[key] ?? [key]
  for (const k of keys) {
    if (provenance[k]?.length) return provenance[k]!
  }
  return []
}

// ── 원자 컴포넌트 ─────────────────────────────────────────

export function ColHeader({ children }: { children: React.ReactNode }) {
  return (
    <div className="px-3 py-2 border-b bg-muted/40 text-xs font-semibold text-muted-foreground sticky top-0 z-10">
      {children}
    </div>
  )
}

export function FieldRow({
  label,
  children,
  highlight,
}: {
  label: string
  children: React.ReactNode
  highlight?: boolean
}) {
  return (
    <div className={cn("grid grid-cols-[80px_1fr] gap-2 px-3 py-2 border-b last:border-b-0 text-xs", highlight && "bg-blue-50/40")}>
      <span className="text-muted-foreground pt-0.5 shrink-0">{label}</span>
      <div className="min-w-0">{children}</div>
    </div>
  )
}

export function FacetScoreBar({ label, value }: { label: string; value: number }) {
  const pct = Math.round(Math.min(Math.max(value, 0), 1) * 100)
  return (
    <div className="flex items-center gap-2 py-1">
      <span className="w-20 text-xs text-muted-foreground shrink-0">{label}</span>
      <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
        <div
          className={cn("h-full rounded-full transition-all", pct > 70 ? "bg-red-400" : pct > 40 ? "bg-amber-400" : "bg-green-500")}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="w-8 text-right text-xs tabular-nums text-muted-foreground">{pct}</span>
    </div>
  )
}

// ── MetaColumn ────────────────────────────────────────────

export function MetaColumn({
  result,
  applying,
  applied,
  onApply,
}: {
  result: Pick<MediSearchResult, "metadata" | "provenance" | "sources_detail"> & { metadata: Record<string, unknown>; provenance: Record<string, string[]> }
  applying?: string | null
  applied?: Set<string>
  onApply?: (field: string) => void
}) {
  const appliedSet = applied ?? new Set<string>()
  return (
    <div className="rounded-xl border bg-card shadow-sm overflow-hidden flex flex-col">
      <ColHeader>
        <div className="flex items-center justify-between">
          <span>MediSearch 기본 메타</span>
          <div className="flex gap-1">
            {result.sources_detail.map((s) => (
              <SourceBadge key={s.provider as string} source={s.provider as string} />
            ))}
          </div>
        </div>
      </ColHeader>
      <div className="overflow-y-auto flex-1">
        {META_FIELDS.map(({ key, label }) => {
          const value = getMetaValue(result.metadata, key)
          const providers = getProvenance(result.provenance, key)
          const isApplied = appliedSet.has(key)
          return (
            <FieldRow key={key} label={label} highlight={!!value && !isApplied}>
              {value ? (
                <div className="space-y-1">
                  <p className="text-xs break-words line-clamp-2 text-foreground">{value}</p>
                  <div className="flex items-center gap-1.5 flex-wrap">
                    {providers.map((p) => <SourceBadge key={p} source={p} />)}
                    {onApply && (
                      isApplied ? (
                        <span className="flex items-center gap-0.5 text-[10px] text-green-600">
                          <Check className="h-3 w-3" />적용됨
                        </span>
                      ) : (
                        <button
                          onClick={() => onApply(key)}
                          disabled={applying === key}
                          className="text-[11px] px-2 py-0.5 rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
                        >
                          {applying === key ? "…" : "Apply"}
                        </button>
                      )
                    )}
                  </div>
                </div>
              ) : (
                <span className="text-muted-foreground italic text-xs">없음</span>
              )}
            </FieldRow>
          )
        })}
      </div>

      {(result.metadata as Record<string, unknown>).confidence != null && (
        <div className="px-3 py-2 border-t text-xs text-muted-foreground">
          신뢰도 {Math.round(((result.metadata as Record<string, unknown>).confidence as number) * 100)}% · {result.sources_detail.length}개 소스
        </div>
      )}
    </div>
  )
}

// ── FacetColumn ──────────────────────────────────────────

export function FacetColumn({
  facet,
  onRequestEvaluate,
  evaluating,
}: {
  facet: MediSearchFacetInfo
  onRequestEvaluate(): void
  evaluating: boolean
}) {
  const fj = facet.facet_json ?? {}

  const scoreEntries = Object.entries(FACET_SCORE_LABELS).filter(([k]) => fj[k] != null)
  const listEntries = Object.entries(FACET_LIST_LABELS).filter(([k]) => fj[k] != null)
  const safetyFlags = fj.safety_flags as Record<string, unknown> | undefined

  return (
    <div className="rounded-xl border bg-card shadow-sm overflow-hidden flex flex-col">
      <ColHeader>
        <div className="flex items-center justify-between">
          <span className="flex items-center gap-1.5">
            <Sparkles className="h-3 w-3" />Facet 분석
          </span>
          {facet.origin !== "none" && (
            <span className={cn(
              "text-[10px] px-1.5 py-0.5 rounded-full",
              facet.origin === "stored" ? "bg-green-100 text-green-700" : "bg-blue-100 text-blue-700"
            )}>
              {facet.origin === "stored" ? "저장값" : "신규 평가"}
            </span>
          )}
        </div>
      </ColHeader>

      {facet.origin === "none" ? (
        <div className="flex-1 flex flex-col items-center justify-center gap-3 p-6 text-center">
          <Database className="h-8 w-8 text-muted-foreground/40" />
          <p className="text-sm text-muted-foreground">저장된 facet이 없습니다.</p>
          <button
            onClick={onRequestEvaluate}
            disabled={evaluating}
            className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-md bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
          >
            {evaluating ? <RefreshCw className="h-3 w-3 animate-spin" /> : <Sparkles className="h-3 w-3" />}
            {evaluating ? "평가 중..." : "Facet 평가 요청"}
          </button>
          <p className="text-[10px] text-muted-foreground">(수 분 소요 가능)</p>
        </div>
      ) : (
        <div className="overflow-y-auto flex-1 space-y-3 p-3">
          {facet.confidence != null && (
            <div className="text-xs text-muted-foreground flex gap-3">
              <span>신뢰도 {Math.round(facet.confidence * 100)}%</span>
              {facet.source_count != null && <span>소스 {facet.source_count}개</span>}
            </div>
          )}

          {listEntries.length > 0 && (
            <div className="space-y-1.5">
              {listEntries.map(([k, label]) => (
                <div key={k} className="flex items-start gap-2">
                  <span className="text-xs text-muted-foreground w-20 shrink-0">{label}</span>
                  <span className="text-xs text-foreground break-words">{fmt(fj[k])}</span>
                </div>
              ))}
            </div>
          )}

          {scoreEntries.length > 0 && (
            <div className="border-t pt-3">
              <p className="text-xs font-medium text-muted-foreground mb-2">평가 점수 (0–1)</p>
              {scoreEntries.map(([k, label]) => (
                <FacetScoreBar key={k} label={label} value={fj[k] as number} />
              ))}
            </div>
          )}

          {safetyFlags && (
            <div className="border-t pt-3 flex flex-wrap gap-1.5">
              {!!safetyFlags.is_violent && <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-red-100 text-red-700">폭력</span>}
              {!!safetyFlags.is_gory    && <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-red-100 text-red-700">고어</span>}
              {!!safetyFlags.is_sexual  && <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-orange-100 text-orange-700">선정</span>}
              {safetyFlags.age_suggestion != null && (
                <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-slate-100 text-slate-700">
                  {String(safetyFlags.age_suggestion)}세 이상
                </span>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
