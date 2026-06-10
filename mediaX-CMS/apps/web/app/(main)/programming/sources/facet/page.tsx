"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { RefreshCw, Film, CheckCircle, Clock, AlertCircle, XCircle, Activity, Play } from "lucide-react"
import {
  facetApi,
  type FacetBatchRunOut,
  type FacetCoverageOut,
  type FacetDailyPoint,
  type FacetPolicyOut,
} from "@/lib/api"
import { FacetEventLog } from "@/components/sources/FacetEventLog"

// ── 유틸 ──────────────────────────────────────────────────

function fmt(n: number | null | undefined) {
  if (n == null) return "-"
  return n.toLocaleString()
}

function fmtDt(iso: string | null | undefined) {
  if (!iso) return "-"
  const m = iso.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/)
  return m ? `${m[2]}.${m[3]} ${m[4]}:${m[5]}` : iso
}

function statusBadge(status: string) {
  const map: Record<string, string> = {
    done:      "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
    running:   "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
    pending:   "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400",
    failed:    "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
    cancelled: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
  }
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${map[status] ?? "bg-gray-100 text-gray-600"}`}>
      {status}
    </span>
  )
}

function statusIcon(status: string) {
  if (status === "done")    return <CheckCircle className="w-4 h-4 text-green-500" />
  if (status === "running") return <RefreshCw   className="w-4 h-4 text-blue-500 animate-spin" />
  if (status === "failed")  return <XCircle     className="w-4 h-4 text-red-500" />
  return <AlertCircle className="w-4 h-4 text-amber-500" />
}

// ── StatCard ───────────────────────────────────────────────

function StatCard({ icon, label, value, sub }: {
  icon: React.ReactNode
  label: string
  value: string | number
  sub?: string
}) {
  return (
    <div className="rounded-xl border bg-card p-4 shadow-sm flex items-start gap-3">
      <div className="mt-0.5 text-muted-foreground">{icon}</div>
      <div className="min-w-0">
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className="text-2xl font-semibold tabular-nums tracking-tight mt-0.5">{value}</p>
        {sub && <p className="text-xs text-muted-foreground mt-0.5">{sub}</p>}
      </div>
    </div>
  )
}

// ── DailyBarChart ──────────────────────────────────────────

function DailyBarChart({ data }: { data: FacetDailyPoint[] }) {
  const max = Math.max(...data.map((d) => d.success + d.failed), 1)
  return (
    <div className="rounded-xl border bg-card p-4 shadow-sm">
      <p className="text-sm font-medium mb-4">일별 처리 현황 (14일)</p>
      {data.length === 0 ? (
        <p className="text-sm text-muted-foreground text-center py-8">데이터 없음</p>
      ) : (
        <>
          <div className="flex items-end gap-1.5 h-32">
            {data.map((d) => {
              const total = d.success + d.failed
              const sPct = (d.success / max) * 100
              const fPct = (d.failed  / max) * 100
              return (
                <div key={d.date} className="flex-1 flex flex-col items-center gap-1 h-full justify-end">
                  <span className="text-[10px] text-muted-foreground tabular-nums">{total > 0 ? total : ""}</span>
                  <div className="w-full flex flex-col justify-end gap-px" style={{ height: "80%" }}>
                    <div className="w-full bg-red-400/70 rounded-sm transition-all"   style={{ height: `${fPct}%` }} />
                    <div className="w-full bg-green-500/70 rounded-sm transition-all" style={{ height: `${sPct}%` }} />
                  </div>
                  <span className="text-[10px] text-muted-foreground">{d.date.slice(5)}</span>
                </div>
              )
            })}
          </div>
          <div className="flex items-center gap-4 mt-3">
            <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <span className="inline-block w-3 h-2 rounded-sm bg-green-500/70" />성공
            </span>
            <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <span className="inline-block w-3 h-2 rounded-sm bg-red-400/70" />실패
            </span>
          </div>
        </>
      )}
    </div>
  )
}

// ── 메인 페이지 ────────────────────────────────────────────

export default function FacetPage() {
  const [coverage, setCoverage] = useState<FacetCoverageOut | null>(null)
  const [runs,     setRuns]     = useState<FacetBatchRunOut[]>([])
  const [daily,    setDaily]    = useState<FacetDailyPoint[]>([])
  const [policy,   setPolicy]   = useState<FacetPolicyOut | null>(null)
  const [loading,  setLoading]  = useState(true)
  const [triggering, setTriggering] = useState(false)
  const [triggerMsg, setTriggerMsg] = useState<string | null>(null)
  const [policyLoading, setPolicyLoading] = useState(false)

  const hasRunning = runs.some((r) => r.status === "running")
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const fetchAll = useCallback(async () => {
    try {
      const [cov, rs, dl, pol] = await Promise.all([
        facetApi.getCoverage(),
        facetApi.listRuns(20),
        facetApi.getDaily(14),
        facetApi.getPolicy(),
      ])
      setCoverage(cov)
      setRuns(rs)
      setDaily(dl)
      setPolicy(pol)
    } catch {
      // 조용히 실패
    } finally {
      setLoading(false)
    }
  }, [])

  async function handlePolicyToggle() {
    if (!policy) return
    setPolicyLoading(true)
    try {
      const updated = await facetApi.setPolicy(!policy.log_enabled)
      setPolicy(updated)
    } catch {
      // 조용히 실패
    } finally {
      setPolicyLoading(false)
    }
  }

  // 최초 로드
  useEffect(() => { fetchAll() }, [fetchAll])

  // running run 있으면 2s 폴링
  useEffect(() => {
    if (hasRunning) {
      pollRef.current = setInterval(fetchAll, 2000)
    } else {
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
    }
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [hasRunning, fetchAll])

  async function handleTrigger() {
    setTriggering(true)
    setTriggerMsg(null)
    try {
      await facetApi.triggerBatch()
      setTriggerMsg("배치가 큐에 등록됐습니다.")
      await fetchAll()
    } catch (err: unknown) {
      const status = (err as { status?: number })?.status
      if (status === 409) {
        setTriggerMsg("이미 실행 중인 배치가 있습니다.")
      } else {
        setTriggerMsg("오류가 발생했습니다.")
      }
    } finally {
      setTriggering(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-32 text-muted-foreground">
        <RefreshCw className="w-5 h-5 animate-spin mr-2" />로딩 중...
      </div>
    )
  }

  const coveragePct = coverage && coverage.movies_total > 0
    ? ((coverage.with_final_facet / coverage.movies_total) * 100).toFixed(1)
    : "0.0"

  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">나무위키+Facet</h2>
          <p className="text-sm text-muted-foreground mt-1">
            MediSearch 멀티소스 facet 평가 배치 현황 — 커버리지 {coveragePct}%
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={fetchAll}
            className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            <RefreshCw className="w-4 h-4" />새로고침
          </button>
          <button
            onClick={handleTrigger}
            disabled={triggering || hasRunning}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Play className="w-3.5 h-3.5" />
            {triggering ? "등록 중..." : hasRunning ? "실행 중" : "배치 실행"}
          </button>
        </div>
      </div>

      {triggerMsg && (
        <div className="rounded-lg border bg-muted/50 px-4 py-2 text-sm text-muted-foreground">
          {triggerMsg}
        </div>
      )}

      {/* KPI 카드 4개 */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={<Film className="w-5 h-5" />}
          label="전체 영화"
          value={fmt(coverage?.movies_total)}
        />
        <StatCard
          icon={<CheckCircle className="w-5 h-5" />}
          label="Facet 완료"
          value={fmt(coverage?.with_final_facet)}
          sub={`${coveragePct}% 커버리지`}
        />
        <StatCard
          icon={<Clock className="w-5 h-5" />}
          label="대기 중 (pending)"
          value={fmt(coverage?.pending)}
          sub="외부소스 있지만 facet 없음"
        />
        <StatCard
          icon={<Activity className="w-5 h-5" />}
          label="갱신 필요 (stale)"
          value={fmt(coverage?.stale)}
          sub="180일 초과"
        />
      </div>

      {/* 일별 바 차트 */}
      <DailyBarChart data={daily} />

      {/* 로깅 토글 + 실시간 로그 */}
      <div className="rounded-xl border bg-card p-4 shadow-sm space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium">실시간 이벤트 로그</p>
            <p className="text-xs text-muted-foreground mt-0.5">
              로깅 ON 시 배치 진행 이벤트를 실시간으로 기록합니다.
            </p>
          </div>
          <button
            onClick={handlePolicyToggle}
            disabled={policyLoading || !policy}
            className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed ${
              policy?.log_enabled ? "bg-primary" : "bg-input"
            }`}
            role="switch"
            aria-checked={policy?.log_enabled ?? false}
          >
            <span
              className={`pointer-events-none inline-block h-5 w-5 rounded-full bg-background shadow-lg ring-0 transition-transform ${
                policy?.log_enabled ? "translate-x-5" : "translate-x-0"
              }`}
            />
          </button>
        </div>

        {policy?.log_enabled && (
          <FacetEventLog />
        )}
      </div>

      {/* 최근 run 테이블 */}
      <div>
        <h3 className="text-sm font-medium mb-3">최근 배치 실행</h3>
        <div className="rounded-xl border bg-card shadow-sm overflow-y-auto max-h-[280px]">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 border-b sticky top-0 z-10">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground w-12">ID</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">상태</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground hidden sm:table-cell">트리거</th>
                <th className="text-right px-4 py-3 font-medium text-muted-foreground">전체</th>
                <th className="text-right px-4 py-3 font-medium text-muted-foreground">성공</th>
                <th className="text-right px-4 py-3 font-medium text-muted-foreground">실패</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground hidden md:table-cell">시작</th>
                <th className="text-right px-4 py-3 font-medium text-muted-foreground hidden lg:table-cell">ETA</th>
              </tr>
            </thead>
            <tbody>
              {runs.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-4 py-12 text-center text-muted-foreground">
                    배치 실행 이력이 없습니다.
                  </td>
                </tr>
              ) : (
                runs.map((run) => (
                  <tr key={run.id} className="border-t hover:bg-muted/30 transition-colors">
                    <td className="px-4 py-3 text-muted-foreground tabular-nums">#{run.id}</td>
                    <td className="px-4 py-3">
                      <span className="flex items-center gap-1.5">
                        {statusIcon(run.status)}
                        {statusBadge(run.status)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground hidden sm:table-cell">{run.trigger}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{fmt(run.total_count)}</td>
                    <td className="px-4 py-3 text-right tabular-nums text-green-600 dark:text-green-400 font-medium">{fmt(run.success_count)}</td>
                    <td className="px-4 py-3 text-right tabular-nums text-red-500">{fmt(run.failed_count)}</td>
                    <td className="px-4 py-3 text-muted-foreground tabular-nums hidden md:table-cell">{fmtDt(run.created_at)}</td>
                    <td className="px-4 py-3 text-right tabular-nums text-muted-foreground hidden lg:table-cell">
                      {run.eta_seconds != null ? `${Math.round(run.eta_seconds / 60)}분` : "-"}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
