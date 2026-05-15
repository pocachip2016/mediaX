"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { AlertCircle, RefreshCw } from "lucide-react"
import { cn } from "@workspace/ui/lib/utils"
import {
  metadataApi,
  type AiReviewQueueRow,
  type AiReviewQueueSummary,
  type PaginatedAiReviewQueue,
} from "@/lib/api"

// ── Mock 폴백 ─────────────────────────────────────────────

const MOCK_SUMMARY: AiReviewQueueSummary = {
  total: 12, missing: 4, conflict: 2, needs_poster: 3, dam_match: 1, high_risk: 3,
}

const MOCK_ITEMS: AiReviewQueueRow[] = [
  { content_id: 1, title: "기생충", content_type: "movie", input_type: "bulk", content_status: "staging",
    metadata_status: "conflict", poster_status: "needs_selection", dam_match_count: 0,
    risk_level: "high", confidence: 0.42, updated_at: "2026-05-15T09:00:00" },
  { content_id: 2, title: "오징어 게임 시즌2", content_type: "series", input_type: "manual", content_status: "review",
    metadata_status: "missing", poster_status: "no_candidate", dam_match_count: 0,
    risk_level: "high", confidence: 0.65, updated_at: "2026-05-15T10:00:00" },
  { content_id: 3, title: "서울의 봄", content_type: "movie", input_type: "existing", content_status: "approved",
    metadata_status: "enhancement", poster_status: "external_only", dam_match_count: 2,
    risk_level: "medium", confidence: 0.81, updated_at: "2026-05-14T15:00:00" },
  { content_id: 4, title: "범죄도시4", content_type: "movie", input_type: "bulk", content_status: "staging",
    metadata_status: "clean", poster_status: "poster_ok", dam_match_count: 0,
    risk_level: "low", confidence: 0.93, updated_at: "2026-05-13T11:00:00" },
  { content_id: 5, title: "무빙", content_type: "series", input_type: "existing", content_status: "approved",
    metadata_status: "missing", poster_status: "dam_match_found", dam_match_count: 3,
    risk_level: "medium", confidence: 0.77, updated_at: "2026-05-12T08:00:00" },
]

const MOCK_DATA: PaginatedAiReviewQueue = {
  items: MOCK_ITEMS, summary: MOCK_SUMMARY, total: 12, page: 1, size: 50,
}

// ── 상수 ─────────────────────────────────────────────────

type FilterChip = "all" | "missing" | "conflict" | "dam_match" | "external_only" | "high"

const CHIPS: Array<{ key: FilterChip; label: string }> = [
  { key: "all",          label: "전체" },
  { key: "missing",      label: "Missing" },
  { key: "conflict",     label: "Conflict" },
  { key: "dam_match",    label: "Dam Match" },
  { key: "external_only", label: "External Only" },
  { key: "high",         label: "High Risk" },
]

const META_STATUS_CLASS: Record<AiReviewQueueRow["metadata_status"], string> = {
  missing:     "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300",
  conflict:    "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300",
  enhancement: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300",
  clean:       "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300",
}

const POSTER_STATUS_CLASS: Record<AiReviewQueueRow["poster_status"], string> = {
  poster_ok:        "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300",
  needs_selection:  "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300",
  dam_match_found:  "bg-teal-100 text-teal-700 dark:bg-teal-900/30 dark:text-teal-300",
  external_only:    "bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300",
  no_candidate:     "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300",
}

const RISK_CLASS: Record<AiReviewQueueRow["risk_level"], string> = {
  high:   "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300",
  medium: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300",
  low:    "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300",
}

const INPUT_LABEL: Record<AiReviewQueueRow["input_type"], string> = {
  bulk: "Bulk", manual: "Manual", existing: "Existing",
}

function chipToApiParams(chip: FilterChip): Parameters<typeof metadataApi.getAiReviewQueue>[0] {
  if (chip === "missing")      return { metadata_status: "missing",   include_dam: true }
  if (chip === "conflict")     return { metadata_status: "conflict",  include_dam: true }
  if (chip === "dam_match")    return { poster_status:   "dam_match_found", include_dam: true }
  if (chip === "external_only") return { poster_status:  "external_only", include_dam: true }
  if (chip === "high")         return { risk_level:      "high",      include_dam: true }
  return { include_dam: true }
}

function formatDate(iso: string) { return iso.slice(0, 10) }

// ── 메인 ─────────────────────────────────────────────────

export default function AiReviewQueuePage() {
  const router = useRouter()
  const [chip, setChip] = useState<FilterChip>("all")
  const [data, setData] = useState<PaginatedAiReviewQueue | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isMock, setIsMock] = useState(false)

  async function load(activeChip: FilterChip) {
    setLoading(true)
    setError(null)
    try {
      const result = await metadataApi.getAiReviewQueue(chipToApiParams(activeChip))
      setData(result)
      setIsMock(false)
    } catch {
      setData(MOCK_DATA)
      setIsMock(true)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load(chip) }, [chip])

  const summary = data?.summary ?? MOCK_SUMMARY

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-xl font-bold">AI Review Queue</h1>
          <p className="text-sm text-muted-foreground">메타데이터·포스터·DAM 통합 검수 대기열</p>
        </div>
        <button
          onClick={() => load(chip)}
          className="p-1.5 rounded-lg hover:bg-accent transition-colors"
          title="새로고침"
        >
          <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
        </button>
      </div>

      {/* Summary 1행 */}
      <div className="flex flex-wrap gap-2 mb-4 p-3 rounded-lg border border-border bg-muted/30 text-sm">
        <SummaryCell label="Total"       value={summary.total}       />
        <SummaryCell label="Missing"     value={summary.missing}     cls="text-amber-600 dark:text-amber-400" />
        <SummaryCell label="Conflict"    value={summary.conflict}    cls="text-red-600 dark:text-red-400" />
        <SummaryCell label="Needs Poster" value={summary.needs_poster} cls="text-violet-600 dark:text-violet-400" />
        <SummaryCell label="Dam Match"   value={summary.dam_match}   cls="text-teal-600 dark:text-teal-400" />
        <SummaryCell label="High Risk"   value={summary.high_risk}   cls="text-red-700 dark:text-red-400 font-semibold" />
        {isMock && (
          <span className="ml-auto self-center text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-700">
            Mock 데이터
          </span>
        )}
      </div>

      {/* Filter chips */}
      <div className="flex flex-wrap gap-1.5 mb-3">
        {CHIPS.map(c => (
          <button
            key={c.key}
            onClick={() => setChip(c.key)}
            className={cn(
              "px-3 py-1 rounded-full text-xs font-medium transition-colors",
              chip === c.key
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-muted-foreground hover:bg-accent"
            )}
          >
            {c.label}
          </button>
        ))}
      </div>

      {/* 테이블 */}
      {error && (
        <div className="flex items-center gap-2 text-sm text-destructive mb-3">
          <AlertCircle className="h-4 w-4" /> {error}
        </div>
      )}

      <div className="rounded-lg border border-border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted/50">
            <tr>
              <th className="text-left px-3 py-2 font-medium text-muted-foreground">Title</th>
              <th className="text-left px-2 py-2 font-medium text-muted-foreground w-20">Input</th>
              <th className="text-left px-2 py-2 font-medium text-muted-foreground w-28">Metadata</th>
              <th className="text-left px-2 py-2 font-medium text-muted-foreground w-32">Poster</th>
              <th className="text-center px-2 py-2 font-medium text-muted-foreground w-12">Dam</th>
              <th className="text-center px-2 py-2 font-medium text-muted-foreground w-20">Risk</th>
              <th className="text-right px-2 py-2 font-medium text-muted-foreground w-16">Conf</th>
              <th className="text-right px-2 py-2 font-medium text-muted-foreground w-24">Updated</th>
              <th className="px-2 py-2 w-16"></th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={9} className="text-center py-10 text-muted-foreground text-sm">
                  <RefreshCw className="h-4 w-4 animate-spin mx-auto mb-1" />
                  로딩 중...
                </td>
              </tr>
            )}
            {!loading && data?.items.length === 0 && (
              <tr>
                <td colSpan={9} className="text-center py-10 text-muted-foreground text-sm">
                  해당 조건의 검수 항목이 없습니다.
                </td>
              </tr>
            )}
            {!loading && data?.items.map(row => (
              <tr
                key={row.content_id}
                onClick={() => router.push(`/programming/contents/${row.content_id}`)}
                className="border-t border-border hover:bg-accent/40 cursor-pointer transition-colors"
              >
                <td className="px-3 py-1.5">
                  <span className="font-medium truncate max-w-[240px] block">{row.title}</span>
                  <span className="text-xs text-muted-foreground">{row.content_type}</span>
                </td>
                <td className="px-2 py-1.5">
                  <Badge cls="bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                    {INPUT_LABEL[row.input_type]}
                  </Badge>
                </td>
                <td className="px-2 py-1.5">
                  <Badge cls={META_STATUS_CLASS[row.metadata_status]}>
                    {row.metadata_status}
                  </Badge>
                </td>
                <td className="px-2 py-1.5">
                  <Badge cls={POSTER_STATUS_CLASS[row.poster_status]}>
                    {row.poster_status.replace(/_/g, " ")}
                  </Badge>
                </td>
                <td className="px-2 py-1.5 text-center">
                  {row.dam_match_count > 0
                    ? <span className="text-teal-600 dark:text-teal-400 font-medium">●{row.dam_match_count}</span>
                    : <span className="text-muted-foreground">—</span>
                  }
                </td>
                <td className="px-2 py-1.5 text-center">
                  <Badge cls={RISK_CLASS[row.risk_level]}>{row.risk_level}</Badge>
                </td>
                <td className="px-2 py-1.5 text-right tabular-nums text-xs">
                  {(row.confidence * 100).toFixed(0)}%
                </td>
                <td className="px-2 py-1.5 text-right text-xs text-muted-foreground">
                  {formatDate(row.updated_at)}
                </td>
                <td className="px-2 py-1.5 text-right">
                  <span className="text-xs text-primary hover:underline">Review</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* 페이지 정보 */}
      {data && data.total > data.size && (
        <p className="text-xs text-muted-foreground mt-2 text-right">
          {data.items.length} / {data.total}건
        </p>
      )}
    </div>
  )
}

// ── 보조 컴포넌트 ─────────────────────────────────────────

function Badge({ cls, children }: { cls: string; children: React.ReactNode }) {
  return (
    <span className={cn("px-1.5 py-0.5 rounded text-xs font-medium whitespace-nowrap", cls)}>
      {children}
    </span>
  )
}

function SummaryCell({ label, value, cls }: { label: string; value: number; cls?: string }) {
  return (
    <span className="flex items-center gap-1.5 px-2">
      <span className="text-muted-foreground">{label}</span>
      <span className={cn("font-semibold tabular-nums", cls)}>{value}</span>
    </span>
  )
}
