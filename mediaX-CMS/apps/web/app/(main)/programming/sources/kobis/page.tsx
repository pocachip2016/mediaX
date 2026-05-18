"use client"

import { useEffect, useState, useCallback } from "react"
import { useRouter } from "next/navigation"
import { RefreshCw, Search, X, CheckCircle, XCircle, AlertCircle, Clock, Database, Film, Tv, ChevronLeft, ChevronRight } from "lucide-react"
import Image from "next/image"
import {
  kobisApi,
  type ExternalSourceStats,
  type MappedExternalItem,
  type TmdbSyncLogItem,
  type ContentStatus,
} from "@/lib/api"

// ── Mock 데이터 ───────────────────────────────────────────

const MOCK_STATS: ExternalSourceStats = {
  total_synced: 254,
  last_run_at: "2026-05-18T07:11:01+09:00",
  last_run_status: "completed",
  last_7d_daily: [
    { date: "2026-05-12", count: 0,  errors: 0 },
    { date: "2026-05-13", count: 0,  errors: 0 },
    { date: "2026-05-14", count: 0,  errors: 0 },
    { date: "2026-05-15", count: 0,  errors: 0 },
    { date: "2026-05-16", count: 0,  errors: 0 },
    { date: "2026-05-17", count: 0,  errors: 0 },
    { date: "2026-05-18", count: 10, errors: 0 },
  ],
}

const MOCK_LOGS: TmdbSyncLogItem[] = [
  { id: 2, run_id: "k2", source: "kobis_daily",    target_year: null, target_date: "2026-05-18", status: "completed", started_at: "2026-05-18T07:00:00+09:00", finished_at: "2026-05-18T07:00:02+09:00", pages_fetched: 1, items_fetched: 10, items_inserted: 2, items_updated: 6, items_unchanged: 2, errors: 0 },
  { id: 1, run_id: "k1", source: "kobis_backfill", target_year: 2025, target_date: null,          status: "completed", started_at: "2026-05-18T06:30:00+09:00", finished_at: "2026-05-18T06:30:10+09:00", pages_fetched: 0, items_fetched: 0, items_inserted: 0, items_updated: 0, items_unchanged: 0, errors: 0 },
]

const MOCK_ITEMS: MappedExternalItem[] = [
  { content_id: 1, title: "파묘", original_title: "Exhuma", content_type: "movie", status: "approved", production_year: 2024, cp_name: "Watcha", external_id: "20240001", poster_url: null, match_confidence: 0.97, matched_at: "2026-05-18T07:11:00+09:00", quality_score: 92 },
  { content_id: 2, title: "범죄도시4", original_title: null, content_type: "movie", status: "review", production_year: 2024, cp_name: "Watcha", external_id: "20240002", poster_url: null, match_confidence: 0.95, matched_at: "2026-05-18T07:11:00+09:00", quality_score: 78 },
]

// ── 상수 ──────────────────────────────────────────────────

const SOURCE_LABEL: Record<string, string> = {
  kobis_daily: "일별 수집",
  kobis_backfill: "전체 백필",
}

const STATUS_LABEL: Record<ContentStatus, string> = {
  waiting: "대기", processing: "처리중", staging: "검토대기",
  review: "검수중", approved: "완료", rejected: "반려",
}

const STATUS_CLASS: Record<ContentStatus, string> = {
  waiting:    "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400",
  processing: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  staging:    "bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-400",
  review:     "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
  approved:   "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
  rejected:   "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
}

const SYNC_STATUS_LABEL: Record<string, string> = { completed: "완료", running: "진행중", failed: "실패" }

function statusIcon(status: string) {
  if (status === "completed") return <CheckCircle className="w-4 h-4 text-green-500" />
  if (status === "running")   return <RefreshCw   className="w-4 h-4 text-blue-500 animate-spin" />
  if (status === "failed")    return <XCircle     className="w-4 h-4 text-red-500" />
  return <AlertCircle className="w-4 h-4 text-amber-500" />
}

function qualityColor(score: number | null) {
  if (score === null) return "text-muted-foreground"
  if (score >= 90) return "text-green-600 dark:text-green-400"
  if (score >= 70) return "text-amber-600 dark:text-amber-400"
  return "text-red-600 dark:text-red-400"
}

function formatDate(iso: string | null) {
  if (!iso) return "-"
  const m = iso.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/)
  return m ? `${m[2]}.${m[3]} ${m[4]}:${m[5]}` : iso
}

function elapsedSec(start: string, end: string | null) {
  if (!end) return "-"
  const s = (new Date(end).getTime() - new Date(start).getTime()) / 1000
  return s < 60 ? `${s.toFixed(0)}s` : `${(s / 60).toFixed(1)}m`
}

function buildPages(current: number, total: number): (number | "…")[] {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1)
  const pages: (number | "…")[] = [1]
  if (current > 3) pages.push("…")
  for (let p = Math.max(2, current - 1); p <= Math.min(total - 1, current + 1); p++) pages.push(p)
  if (current < total - 2) pages.push("…")
  pages.push(total)
  return pages
}

function StatCard({ icon, label, value, sub }: { icon: React.ReactNode; label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-xl border bg-card p-4 shadow-sm flex items-start gap-3">
      <div className="mt-0.5 text-muted-foreground">{icon}</div>
      <div>
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className="text-2xl font-semibold tabular-nums tracking-tight mt-0.5">{value}</p>
        {sub && <p className="text-xs text-muted-foreground mt-0.5">{sub}</p>}
      </div>
    </div>
  )
}

// ── 메인 컴포넌트 ─────────────────────────────────────────

export default function KobisPage() {
  const router = useRouter()

  const [stats,   setStats]   = useState<ExternalSourceStats>(MOCK_STATS)
  const [logs,    setLogs]    = useState<TmdbSyncLogItem[]>(MOCK_LOGS)
  const [items,   setItems]   = useState<MappedExternalItem[]>([])
  const [total,   setTotal]   = useState(0)
  const [page,    setPage]    = useState(1)
  const [loading, setLoading] = useState(false)
  const [search,  setSearch]  = useState("")
  const [applied, setApplied] = useState("")
  const [typeFilter, setTypeFilter] = useState<"" | "movie" | "series">("")

  const SIZE = 20

  const fetchStats = useCallback(async () => {
    try {
      const [s, l] = await Promise.all([
        kobisApi.getStats(),
        kobisApi.getSyncLog({ page: 1, size: 20 }),
      ])
      if (s.total_synced > 0) { setStats(s); setLogs(l.items) }
    } catch { /* Mock 유지 */ }
  }, [])

  const fetchContents = useCallback(async (p: number, title: string, ct: string) => {
    setLoading(true)
    try {
      const data = await kobisApi.listContents({
        title: title || undefined,
        content_type: ct || undefined,
        page: p,
        size: SIZE,
      })
      setItems(data.items)
      setTotal(data.total)
    } catch {
      setItems(MOCK_ITEMS)
      setTotal(MOCK_ITEMS.length)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchStats() }, [fetchStats])
  useEffect(() => { fetchContents(page, applied, typeFilter) }, [page, applied, typeFilter, fetchContents])

  function applySearch() { setApplied(search); setPage(1) }
  function clearSearch()  { setSearch(""); setApplied(""); setPage(1) }

  const totalPages = Math.max(1, Math.ceil(total / SIZE))

  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">KOBIS</h2>
          <p className="text-sm text-muted-foreground mt-1">한국영화진흥위원회 — 매핑 현황 및 콘텐츠 탐색</p>
        </div>
        <button onClick={() => { fetchStats(); fetchContents(page, applied, typeFilter) }}
          className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors">
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />새로고침
        </button>
      </div>

      {/* KPI */}
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        <StatCard icon={<Database    className="w-5 h-5" />} label="매핑 총 건수"   value={stats.total_synced.toLocaleString()} />
        <StatCard icon={<Clock       className="w-5 h-5" />} label="마지막 수집"    value={formatDate(stats.last_run_at)} sub={stats.last_run_status ? (SYNC_STATUS_LABEL[stats.last_run_status] ?? stats.last_run_status) : "-"} />
        <StatCard icon={<CheckCircle className="w-5 h-5" />} label="최근 7일 수집" value={stats.last_7d_daily.reduce((a, d) => a + d.count, 0).toLocaleString()} sub="건" />
      </div>

      {/* 동기화 로그 */}
      <div>
        <h3 className="text-sm font-medium mb-3">동기화 로그</h3>
        <div className="rounded-xl border bg-card shadow-sm overflow-y-auto max-h-[200px]">
          <table className="w-full text-sm">
            <thead className="bg-muted border-b sticky top-0 z-10">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">소스</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">상태</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground hidden md:table-cell">시작</th>
                <th className="text-right px-4 py-3 font-medium text-muted-foreground">수집</th>
                <th className="text-right px-4 py-3 font-medium text-muted-foreground">신규</th>
                <th className="text-right px-4 py-3 font-medium text-muted-foreground hidden lg:table-cell">갱신</th>
                <th className="text-right px-4 py-3 font-medium text-muted-foreground hidden lg:table-cell">오류</th>
                <th className="text-right px-4 py-3 font-medium text-muted-foreground hidden xl:table-cell">소요</th>
              </tr>
            </thead>
            <tbody>
              {logs.length === 0 ? (
                <tr><td colSpan={8} className="px-4 py-10 text-center text-muted-foreground">동기화 이력이 없습니다.</td></tr>
              ) : logs.map((log) => (
                <tr key={log.id} className="border-t hover:bg-muted/30 transition-colors">
                  <td className="px-4 py-3 font-medium">{SOURCE_LABEL[log.source] ?? log.source}</td>
                  <td className="px-4 py-3"><span className="flex items-center gap-1.5">{statusIcon(log.status)}<span className="text-xs">{SYNC_STATUS_LABEL[log.status] ?? log.status}</span></span></td>
                  <td className="px-4 py-3 text-muted-foreground tabular-nums hidden md:table-cell">{formatDate(log.started_at)}</td>
                  <td className="px-4 py-3 text-right tabular-nums text-muted-foreground">{log.items_fetched.toLocaleString()}</td>
                  <td className="px-4 py-3 text-right tabular-nums font-medium text-green-600 dark:text-green-400">+{log.items_inserted.toLocaleString()}</td>
                  <td className="px-4 py-3 text-right tabular-nums text-muted-foreground hidden lg:table-cell">{log.items_updated.toLocaleString()}</td>
                  <td className={`px-4 py-3 text-right tabular-nums hidden lg:table-cell ${log.errors > 0 ? "text-red-500" : "text-muted-foreground"}`}>{log.errors}</td>
                  <td className="px-4 py-3 text-right tabular-nums text-muted-foreground hidden xl:table-cell">{elapsedSec(log.started_at, log.finished_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 매핑 콘텐츠 탐색 */}
      <div>
        <h3 className="text-sm font-medium mb-3">매핑 콘텐츠 탐색</h3>
        <div className="flex flex-wrap gap-2 mb-4">
          <div className="relative flex-1 min-w-[200px] max-w-xs">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && applySearch()}
              placeholder="제목 검색..."
              className="w-full pl-9 pr-8 py-2 text-sm rounded-md border bg-background focus:outline-none focus:ring-2 focus:ring-ring"
            />
            {search && (
              <button onClick={clearSearch} className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
                <X className="w-4 h-4" />
              </button>
            )}
          </div>
          {(["", "movie", "series"] as const).map((t) => (
            <button key={t} onClick={() => { setTypeFilter(t); setPage(1) }}
              className={`flex items-center gap-1.5 px-3 py-2 text-sm rounded-md border transition-colors ${
                typeFilter === t ? "bg-primary text-primary-foreground border-primary" : "bg-background hover:bg-muted border-border"
              }`}>
              {t === "" && "전체"}
              {t === "movie"  && <><Film className="w-3.5 h-3.5" />영화</>}
              {t === "series" && <><Tv   className="w-3.5 h-3.5" />시리즈</>}
            </button>
          ))}
          <button onClick={applySearch}
            className="px-4 py-2 text-sm rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors">
            검색
          </button>
        </div>

        <div className="rounded-xl border bg-card shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 border-b">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground w-12">#</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">콘텐츠</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground hidden sm:table-cell">유형</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground hidden md:table-cell">CP사</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground hidden lg:table-cell">KOBIS ID</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground hidden lg:table-cell">신뢰도</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground hidden md:table-cell">품질</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">상태</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground hidden xl:table-cell">매핑일</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={9} className="px-4 py-12 text-center text-muted-foreground">
                  <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2" />불러오는 중...
                </td></tr>
              ) : items.length === 0 ? (
                <tr><td colSpan={9} className="px-4 py-12 text-center text-muted-foreground">
                  KOBIS 매핑된 콘텐츠가 없습니다.
                </td></tr>
              ) : items.map((item, idx) => (
                <tr key={item.content_id}
                  onClick={() => router.push(`/programming/contents/${item.content_id}`)}
                  className="border-t hover:bg-muted/40 cursor-pointer transition-colors">
                  <td className="px-4 py-3 text-muted-foreground tabular-nums">{(page - 1) * SIZE + idx + 1}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <div className="rounded overflow-hidden bg-muted shrink-0 relative" style={{ width: 36, height: 52 }}>
                        {item.poster_url ? (
                          <Image src={item.poster_url} alt={item.title} fill className="object-cover" unoptimized />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center text-muted-foreground">
                            {item.content_type === "movie" ? <Film className="w-4 h-4" /> : <Tv className="w-4 h-4" />}
                          </div>
                        )}
                      </div>
                      <div className="min-w-0">
                        <p className="font-medium truncate">{item.title}</p>
                        {item.original_title && <p className="text-xs text-muted-foreground truncate">{item.original_title}</p>}
                        {item.production_year && <p className="text-xs text-muted-foreground">{item.production_year}</p>}
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3 hidden sm:table-cell">
                    <span className="flex items-center gap-1 text-muted-foreground">
                      {item.content_type === "movie" ? <><Film className="w-3.5 h-3.5" />영화</> : <><Tv className="w-3.5 h-3.5" />시리즈</>}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground hidden md:table-cell">
                    <span className="truncate block max-w-[120px]">{item.cp_name ?? "-"}</span>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-muted-foreground hidden lg:table-cell">{item.external_id}</td>
                  <td className="px-4 py-3 hidden lg:table-cell tabular-nums text-muted-foreground">
                    {item.match_confidence !== null ? `${(item.match_confidence * 100).toFixed(0)}%` : "-"}
                  </td>
                  <td className={`px-4 py-3 hidden md:table-cell font-medium tabular-nums ${qualityColor(item.quality_score)}`}>
                    {item.quality_score !== null ? item.quality_score.toFixed(1) : "-"}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_CLASS[item.status]}`}>
                      {STATUS_LABEL[item.status]}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground hidden xl:table-cell tabular-nums">{formatDate(item.matched_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 페이지네이션 */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-1">
          <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1}
            className="p-2 rounded-md hover:bg-muted disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
            <ChevronLeft className="w-4 h-4" />
          </button>
          {buildPages(page, totalPages).map((p, i) =>
            p === "…" ? (
              <span key={`e${i}`} className="px-2 text-muted-foreground">…</span>
            ) : (
              <button key={p} onClick={() => setPage(p)}
                className={`min-w-[36px] h-9 px-2 rounded-md text-sm transition-colors ${
                  p === page ? "bg-primary text-primary-foreground font-medium" : "hover:bg-muted text-muted-foreground"
                }`}>{p}</button>
            )
          )}
          <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page === totalPages}
            className="p-2 rounded-md hover:bg-muted disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      )}
    </div>
  )
}
