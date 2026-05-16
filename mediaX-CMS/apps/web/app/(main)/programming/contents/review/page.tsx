"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { AlertCircle, CheckSquare, RefreshCw, Square } from "lucide-react"
import { cn } from "@workspace/ui/lib/utils"
import {
  metadataApi,
  type AiReviewQueueRow,
  type AiReviewQueueSummary,
  type PaginatedAiReviewQueue,
} from "@/lib/api"
import { checkBulkApplyGuard } from "@/lib/reviewQueueGuard"

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

// ── 필터 상태 ─────────────────────────────────────────────

type FilterState = {
  metadata_status: AiReviewQueueRow["metadata_status"] | null
  poster_status: AiReviewQueueRow["poster_status"] | null
  risk_level: AiReviewQueueRow["risk_level"] | null
  input_type: AiReviewQueueRow["input_type"] | null
}

const EMPTY_FILTER: FilterState = {
  metadata_status: null, poster_status: null, risk_level: null, input_type: null,
}

function filterToParams(f: FilterState): Parameters<typeof metadataApi.getAiReviewQueue>[0] {
  return {
    ...(f.metadata_status && { metadata_status: f.metadata_status }),
    ...(f.poster_status   && { poster_status: f.poster_status }),
    ...(f.risk_level      && { risk_level: f.risk_level }),
    ...(f.input_type      && { input_type: f.input_type }),
    include_dam: true,
  }
}

function isEmptyFilter(f: FilterState) {
  return !f.metadata_status && !f.poster_status && !f.risk_level && !f.input_type
}

// ── 배지 클래스 ────────────────────────────────────────────

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

function formatDate(iso: string) { return iso.slice(0, 10) }

// ── 메인 ─────────────────────────────────────────────────

export default function AiReviewQueuePage() {
  const router = useRouter()
  const [filter, setFilter] = useState<FilterState>(EMPTY_FILTER)
  const [data, setData] = useState<PaginatedAiReviewQueue | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isMock, setIsMock] = useState(false)
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [bulkLoading, setBulkLoading] = useState(false)

  async function load(f: FilterState) {
    setLoading(true)
    setError(null)
    setSelected(new Set())
    try {
      const result = await metadataApi.getAiReviewQueue(filterToParams(f))
      setData(result)
      setIsMock(false)
    } catch {
      setData(MOCK_DATA)
      setIsMock(true)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load(filter) }, [filter])

  function toggleDimension<K extends keyof FilterState>(key: K, value: FilterState[K]) {
    setFilter(prev => ({ ...prev, [key]: prev[key] === value ? null : value }))
  }

  function setSummaryFilter(partial: Partial<FilterState>) {
    setFilter(prev => {
      const next = { ...EMPTY_FILTER, ...partial }
      const alreadyActive = (Object.keys(partial) as (keyof FilterState)[]).every(
        k => prev[k] === partial[k]
      )
      return alreadyActive ? EMPTY_FILTER : next
    })
  }

  const summary = data?.summary ?? MOCK_SUMMARY
  const items = data?.items ?? []

  // ── 선택 / Bulk Apply ──────────────────────────────────
  const allSelected = items.length > 0 && items.every(r => selected.has(r.content_id))
  const selectedRows = items.filter(r => selected.has(r.content_id))
  const guardResult = checkBulkApplyGuard(selectedRows)

  function toggleSelectAll() {
    if (allSelected) {
      setSelected(new Set())
    } else {
      setSelected(new Set(items.map(r => r.content_id)))
    }
  }

  function toggleRow(id: number) {
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id); else next.add(id)
      return next
    })
  }

  async function handleBulkApply() {
    if (!guardResult.allowed) return
    setBulkLoading(true)
    setError(null)
    try {
      await metadataApi.bulkApprove({ content_ids: [...selected], reviewer: "operator" })
      await load(filter)
    } catch (e) {
      setError(e instanceof Error ? e.message : "일괄 승인 실패")
    } finally {
      setBulkLoading(false)
    }
  }

  const bulkTooltip = !guardResult.allowed && guardResult.violatingIds.length > 0
    ? `위배 ${guardResult.violatingIds.length}건: ${guardResult.violatingIds.join(", ")}`
    : undefined

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-xl font-bold">AI Review Queue</h1>
          <p className="text-sm text-muted-foreground">메타데이터·포스터·DAM 통합 검수 대기열</p>
        </div>
        <button
          onClick={() => load(filter)}
          className="p-1.5 rounded-lg hover:bg-accent transition-colors"
          title="새로고침"
        >
          <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
        </button>
      </div>

      {/* Summary 1행 (클릭 = 필터 토글) */}
      <div className="flex flex-wrap gap-0 mb-4 rounded-lg border border-border bg-muted/30 text-sm divide-x divide-border overflow-hidden">
        <SummaryCell
          label="Total" value={summary.total}
          active={isEmptyFilter(filter)}
          onClick={() => setFilter(EMPTY_FILTER)}
        />
        <SummaryCell
          label="Missing" value={summary.missing} cls="text-amber-600 dark:text-amber-400"
          active={filter.metadata_status === "missing"}
          onClick={() => setSummaryFilter({ metadata_status: "missing" })}
        />
        <SummaryCell
          label="Conflict" value={summary.conflict} cls="text-red-600 dark:text-red-400"
          active={filter.metadata_status === "conflict"}
          onClick={() => setSummaryFilter({ metadata_status: "conflict" })}
        />
        <SummaryCell
          label="Needs Poster" value={summary.needs_poster} cls="text-violet-600 dark:text-violet-400"
          active={filter.poster_status === "needs_selection"}
          onClick={() => setSummaryFilter({ poster_status: "needs_selection" })}
        />
        <SummaryCell
          label="Dam Match" value={summary.dam_match} cls="text-teal-600 dark:text-teal-400"
          active={filter.poster_status === "dam_match_found"}
          onClick={() => setSummaryFilter({ poster_status: "dam_match_found" })}
        />
        <SummaryCell
          label="High Risk" value={summary.high_risk} cls="text-red-700 dark:text-red-400 font-semibold"
          active={filter.risk_level === "high"}
          onClick={() => setSummaryFilter({ risk_level: "high" })}
        />
        {isMock && (
          <span className="ml-auto self-center text-xs px-3 text-amber-700">Mock</span>
        )}
      </div>

      {/* Filter chips — 다중 차원 */}
      <div className="flex flex-wrap items-center gap-1 mb-3">
        <Chip active={isEmptyFilter(filter)} onClick={() => setFilter(EMPTY_FILTER)}>전체</Chip>

        <Divider />

        <span className="text-[10px] text-muted-foreground px-1">메타</span>
        {(["missing", "conflict", "enhancement", "clean"] as const).map(v => (
          <Chip
            key={v}
            active={filter.metadata_status === v}
            onClick={() => toggleDimension("metadata_status", v)}
          >
            {v.charAt(0).toUpperCase() + v.slice(1)}
          </Chip>
        ))}

        <Divider />

        <span className="text-[10px] text-muted-foreground px-1">포스터</span>
        {([
          ["needs_selection", "Needs Sel."],
          ["external_only",   "External"],
          ["dam_match_found", "Dam Match"],
        ] as const).map(([v, label]) => (
          <Chip
            key={v}
            active={filter.poster_status === v}
            onClick={() => toggleDimension("poster_status", v)}
          >
            {label}
          </Chip>
        ))}

        <Divider />

        <span className="text-[10px] text-muted-foreground px-1">리스크</span>
        {(["low", "medium", "high"] as const).map(v => (
          <Chip
            key={v}
            active={filter.risk_level === v}
            onClick={() => toggleDimension("risk_level", v)}
          >
            {v.charAt(0).toUpperCase() + v.slice(1)}
          </Chip>
        ))}

        <Divider />

        <span className="text-[10px] text-muted-foreground px-1">입력</span>
        {(["bulk", "manual", "existing"] as const).map(v => (
          <Chip
            key={v}
            active={filter.input_type === v}
            onClick={() => toggleDimension("input_type", v)}
          >
            {INPUT_LABEL[v]}
          </Chip>
        ))}
      </div>

      {/* 선택 툴바 */}
      {selected.size > 0 && (
        <div className="flex items-center gap-3 mb-2 px-3 py-1.5 rounded-lg bg-primary/5 border border-primary/20 text-sm">
          <span className="text-primary font-medium">{selected.size}개 선택됨</span>
          <div title={bulkTooltip}>
            <button
              onClick={handleBulkApply}
              disabled={!guardResult.allowed || bulkLoading}
              className={cn(
                "px-3 py-1 rounded text-xs font-medium transition-colors",
                guardResult.allowed
                  ? "bg-primary text-primary-foreground hover:bg-primary/90"
                  : "bg-muted text-muted-foreground cursor-not-allowed"
              )}
            >
              {bulkLoading ? "승인 중…" : "선택 일괄 승인"}
            </button>
          </div>
          {!guardResult.allowed && guardResult.violatingIds.length > 0 && (
            <span className="text-xs text-destructive">
              위배 {guardResult.violatingIds.length}건 포함 (clean + poster_ok + low만 가능)
            </span>
          )}
          <button
            onClick={() => setSelected(new Set())}
            className="ml-auto text-xs text-muted-foreground hover:text-foreground"
          >
            선택 해제
          </button>
        </div>
      )}

      {/* 오류 */}
      {error && (
        <div className="flex items-center gap-2 text-sm text-destructive mb-3">
          <AlertCircle className="h-4 w-4" /> {error}
        </div>
      )}

      {/* 테이블 */}
      <div className="rounded-lg border border-border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted/50">
            <tr>
              <th className="px-2 py-2 w-8">
                <button onClick={toggleSelectAll} className="text-muted-foreground hover:text-foreground">
                  {allSelected
                    ? <CheckSquare className="h-3.5 w-3.5" />
                    : <Square className="h-3.5 w-3.5" />
                  }
                </button>
              </th>
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
                <td colSpan={10} className="text-center py-10 text-muted-foreground text-sm">
                  <RefreshCw className="h-4 w-4 animate-spin mx-auto mb-1" />
                  로딩 중...
                </td>
              </tr>
            )}
            {!loading && items.length === 0 && (
              <tr>
                <td colSpan={10} className="text-center py-10 text-muted-foreground text-sm">
                  해당 조건의 검수 항목이 없습니다.
                </td>
              </tr>
            )}
            {!loading && items.map(row => (
              <tr
                key={row.content_id}
                onClick={() => router.push(`/programming/contents/${row.content_id}`)}
                className={cn(
                  "border-t border-border hover:bg-accent/40 cursor-pointer transition-colors",
                  selected.has(row.content_id) && "bg-primary/5"
                )}
              >
                <td className="px-2 py-1.5 text-center" onClick={e => { e.stopPropagation(); toggleRow(row.content_id) }}>
                  {selected.has(row.content_id)
                    ? <CheckSquare className="h-3.5 w-3.5 text-primary mx-auto" />
                    : <Square className="h-3.5 w-3.5 text-muted-foreground mx-auto" />
                  }
                </td>
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

function SummaryCell({
  label, value, cls, active, onClick,
}: {
  label: string; value: number; cls?: string; active: boolean; onClick(): void
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex items-center gap-1.5 px-3 py-2.5 transition-colors text-sm",
        active
          ? "bg-primary/10 text-foreground"
          : "hover:bg-muted/60 text-muted-foreground",
      )}
    >
      <span>{label}</span>
      <span className={cn("font-semibold tabular-nums", cls)}>{value}</span>
    </button>
  )
}

function Chip({ active, onClick, children }: { active: boolean; onClick(): void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "px-2.5 py-0.5 rounded-full text-xs font-medium transition-colors",
        active
          ? "bg-primary text-primary-foreground"
          : "bg-muted text-muted-foreground hover:bg-accent"
      )}
    >
      {children}
    </button>
  )
}

function Divider() {
  return <span className="text-border text-xs select-none px-0.5">│</span>
}
