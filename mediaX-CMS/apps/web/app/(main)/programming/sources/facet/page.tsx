"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { RefreshCw, Film, CheckCircle, Clock, AlertCircle, XCircle, Activity, Play, Search, ChevronLeft, ChevronRight } from "lucide-react"
import {
  facetApi,
  type FacetBatchRunOut,
  type FacetCoverageOut,
  type FacetDailyPoint,
  type FacetPolicyOut,
  type FacetResultOut,
  type FacetResultsPage,
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
  const [resultStatus, setResultStatus] = useState<"success" | "skipped" | "failed">("success")
  const [resultSearch, setResultSearch] = useState("")
  const [resultPage, setResultPage] = useState(1)
  const [results, setResults] = useState<FacetResultsPage | null>(null)
  const [resultsLoading, setResultsLoading] = useState(false)
  const [selectedFacet, setSelectedFacet] = useState<FacetResultOut | null>(null)
  const [stopping, setStopping] = useState(false)

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

  const fetchResults = useCallback(async () => {
    setResultsLoading(true)
    try {
      const data = await facetApi.getResults({
        status: resultStatus,
        search: resultSearch || undefined,
        page: resultPage,
        size: 20,
      })
      setResults(data)
      setSelectedFacet(null)
    } catch (e) {
      console.error("fetchResults error:", e)
    } finally {
      setResultsLoading(false)
    }
  }, [resultStatus, resultSearch, resultPage])

  useEffect(() => {
    fetchResults()
  }, [fetchResults])

  async function handleTrigger() {
    setTriggering(true)
    setTriggerMsg(null)
    try {
      // 모든 대상 처리: limit 없음 (설정 기본값 100) → 여러 run 자동 체인
      await facetApi.triggerBatch({ force: false })
      setTriggerMsg("모든 대상 처리가 시작됐습니다. (연속 디스패치 중)")
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

  async function handleStop() {
    setStopping(true)
    setTriggerMsg(null)
    try {
      await facetApi.stopBatch()
      setTriggerMsg("배치 중지 요청이 완료됐습니다.")
      await fetchAll()
    } catch (err: unknown) {
      const status = (err as { status?: number })?.status
      if (status === 404) {
        setTriggerMsg("실행 중인 배치가 없습니다.")
      } else {
        setTriggerMsg("중지 요청 중 오류가 발생했습니다.")
      }
    } finally {
      setStopping(false)
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
          {hasRunning ? (
            <button
              onClick={handleStop}
              disabled={stopping}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md bg-red-600 text-white hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <XCircle className="w-3.5 h-3.5" />
              {stopping ? "중지 중..." : "중지"}
            </button>
          ) : (
            <button
              onClick={handleTrigger}
              disabled={triggering}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <Play className="w-3.5 h-3.5" />
              {triggering ? "등록 중..." : "모두 처리"}
            </button>
          )}
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

      </div>

      {/* 최근 run 테이블 + 실시간 이벤트 로그 (50:50 레이아웃) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div>
          <h3 className="text-sm font-medium mb-3">최근 배치 실행</h3>
          <div className="rounded-xl border bg-card shadow-sm overflow-y-auto" style={{ maxHeight: "7rem" }}>
          <table className="w-full text-sm">
            <thead className="bg-card border-b sticky top-0 z-10">
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

        {/* 실시간 이벤트 로그 */}
        <div>
          <h3 className="text-sm font-medium mb-3">실시간 이벤트</h3>
          <FacetEventLog maxHeight="5.5rem" />
        </div>
      </div>

      {/* Facet 결과 목록 */}
      <div className="xl:grid xl:grid-cols-[1fr_320px] xl:gap-4">
        <div className="space-y-4">
          <h3 className="text-sm font-medium">Facet 결과 목록</h3>

          {/* 필터 바 */}
          <div className="flex gap-2 flex-wrap">
            {(["success", "skipped", "failed"] as const).map((s) => (
              <button
                key={s}
                onClick={() => { setResultStatus(s); setResultPage(1) }}
                className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
                  resultStatus === s
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground hover:bg-muted/80"
                }`}
              >
                ●{" "}
                {{success: "성공", skipped: "스킵", failed: "실패"}[s]}
              </button>
            ))}
            <div className="flex-1 min-w-[200px] relative flex items-center">
              <Search className="absolute left-3 w-4 h-4 text-muted-foreground" />
              <input
                type="text"
                value={resultSearch}
                onChange={(e) => { setResultSearch(e.target.value); setResultPage(1) }}
                placeholder="제목 검색..."
                className="w-full pl-9 pr-8 py-1.5 text-sm rounded-md border bg-background focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <button
              onClick={() => fetchResults()}
              disabled={resultsLoading}
              className="px-3 py-1.5 text-sm rounded-md bg-muted hover:bg-muted/80 disabled:opacity-50"
            >
              새로고침
            </button>
          </div>

          {/* 결과 테이블 */}
          <div className="rounded-xl border bg-card shadow-sm overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/50 border-b">
                <tr>
                  <th className="text-left px-4 py-3 font-medium text-muted-foreground">TMDB ID</th>
                  <th className="text-left px-4 py-3 font-medium text-muted-foreground hidden sm:table-cell">제목</th>
                  <th className="text-center px-4 py-3 font-medium text-muted-foreground hidden md:table-cell">점수</th>
                  <th className="text-center px-4 py-3 font-medium text-muted-foreground">소스</th>
                  <th className="text-left px-4 py-3 font-medium text-muted-foreground hidden lg:table-cell">평가일</th>
                  <th className="text-center px-4 py-3 font-medium text-muted-foreground">상태</th>
                </tr>
              </thead>
              <tbody>
                {resultsLoading ? (
                  <tr><td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">로딩...</td></tr>
                ) : !results || results.items.length === 0 ? (
                  <tr><td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">결과가 없습니다.</td></tr>
                ) : (
                  results.items.map((item) => (
                    <tr
                      key={item.tmdb_id}
                      onClick={() => setSelectedFacet(item)}
                      className={`border-t hover:bg-muted/30 transition-colors cursor-pointer ${
                        selectedFacet?.tmdb_id === item.tmdb_id ? "bg-primary/5 border-l-2 border-l-primary" : ""
                      }`}
                    >
                      <td className="px-4 py-3 text-muted-foreground tabular-nums text-xs">{item.tmdb_id}</td>
                      <td className="px-4 py-3 hidden sm:table-cell truncate">{item.title}</td>
                      <td className="px-4 py-3 text-center hidden md:table-cell tabular-nums">
                        {item.confidence ? `${(item.confidence * 100).toFixed(0)}%` : "-"}
                      </td>
                      <td className="px-4 py-3 text-center tabular-nums">{item.source_count ?? "-"}</td>
                      <td className="px-4 py-3 text-muted-foreground text-xs hidden lg:table-cell">
                        {item.evaluated_at ? new Date(item.evaluated_at).toLocaleDateString("ko-KR") : "-"}
                      </td>
                      <td className="px-4 py-3 text-center">
                        <span className={`inline-block px-2 py-0.5 text-xs rounded-full ${
                          item.status === "success" ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200" :
                          item.status === "skipped" ? "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200" :
                          "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200"
                        }`}>
                          {item.status}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* 페이지네이션 */}
          {results && results.total > 0 && (
            <div className="flex justify-between items-center text-xs text-muted-foreground">
              <div>총 {results.total}건</div>
              <div className="flex gap-1">
                <button
                  onClick={() => setResultPage(Math.max(1, resultPage - 1))}
                  disabled={resultPage === 1}
                  className="p-1 hover:bg-muted disabled:opacity-50"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                {Array.from({ length: Math.ceil(results.total / 20) })
                  .map((_, i) => i + 1)
                  .filter((p) => Math.abs(p - resultPage) < 3 || [1, Math.ceil(results.total / 20)].includes(p))
                  .map((p, i, arr) => (
                    <div key={p}>
                      {i > 0 && arr[i - 1] !== p - 1 && <span className="px-1">…</span>}
                      <button
                        onClick={() => setResultPage(p)}
                        className={`min-w-[32px] h-8 rounded-md transition-colors ${
                          p === resultPage
                            ? "bg-primary text-primary-foreground"
                            : "hover:bg-muted text-muted-foreground"
                        }`}
                      >
                        {p}
                      </button>
                    </div>
                  ))}
                <button
                  onClick={() => setResultPage(Math.min(Math.ceil(results.total / 20), resultPage + 1))}
                  disabled={resultPage >= Math.ceil(results.total / 20)}
                  className="p-1 hover:bg-muted disabled:opacity-50"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}
        </div>

        {/* 상세 패널 */}
        {selectedFacet && (
          <div className="hidden xl:block rounded-xl border bg-card p-4 shadow-sm space-y-4 h-fit">
            <div>
              <p className="font-medium text-sm">{selectedFacet.title}</p>
              <p className="text-xs text-muted-foreground mt-1">{selectedFacet.original_title}</p>
            </div>
            <div className="space-y-2 text-xs">
              <div className="flex justify-between">
                <span className="text-muted-foreground">상태</span>
                <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                  selectedFacet.status === "success" ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200" :
                  selectedFacet.status === "skipped" ? "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200" :
                  "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200"
                }`}>
                  {selectedFacet.status}
                </span>
              </div>
              <div className="flex justify-between"><span className="text-muted-foreground">점수</span><span>{selectedFacet.confidence ? `${(selectedFacet.confidence * 100).toFixed(0)}%` : "-"}</span></div>
              <div className="flex justify-between"><span className="text-muted-foreground">소스</span><span>{selectedFacet.source_count ?? "-"}개</span></div>
              <div className="flex justify-between"><span className="text-muted-foreground">시도</span><span>{selectedFacet.attempt_count}</span></div>
            </div>
            {selectedFacet.facet_json && Object.keys(selectedFacet.facet_json).length > 0 && (
              <div className="border-t pt-3 space-y-2">
                <p className="text-xs font-medium">주요 필드</p>
                <table className="w-full text-xs">
                  <tbody>
                    {Object.entries(selectedFacet.facet_json).map(([k, v]) => (
                      <tr key={k} className="border-t">
                        <td className="px-2 py-1 text-muted-foreground">{k}</td>
                        <td className="px-2 py-1 text-right">{String(v)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {selectedFacet.last_error && (
              <div className="border-t pt-3">
                <p className="text-xs font-medium text-red-600 dark:text-red-400 mb-1">오류</p>
                <p className="text-xs text-muted-foreground break-words">{selectedFacet.last_error}</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
