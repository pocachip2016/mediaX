"use client"

import { useEffect, useState, useCallback } from "react"
import { RefreshCw, Search, X, CheckCircle, XCircle, AlertCircle, Clock, Database } from "lucide-react"
import {
  kobisApi,
  type ExternalSourceStats,
  type ExternalSourceItem,
  type TmdbSyncLogItem,
} from "@/lib/api"

// ── Mock 데이터 ───────────────────────────────────────────

const MOCK_STATS: ExternalSourceStats = {
  total_synced: 12_840,
  last_run_at: "2026-05-11T05:10:00+09:00",
  last_run_status: "completed",
  last_7d_daily: [
    { date: "2026-05-05", count: 42, errors: 0 },
    { date: "2026-05-06", count: 38, errors: 0 },
    { date: "2026-05-07", count: 51, errors: 1 },
    { date: "2026-05-08", count: 44, errors: 0 },
    { date: "2026-05-09", count: 47, errors: 0 },
    { date: "2026-05-10", count: 53, errors: 0 },
    { date: "2026-05-11", count: 49, errors: 0 },
  ],
}

const MOCK_LOGS: TmdbSyncLogItem[] = [
  { id: 3, run_id: "k3", source: "kobis_daily",    target_year: null, target_date: "2026-05-11", status: "completed", started_at: "2026-05-11T05:00:00+09:00", finished_at: "2026-05-11T05:08:00+09:00", pages_fetched: 2, items_fetched: 50, items_inserted: 49, items_updated: 1, items_unchanged: 0, errors: 0 },
  { id: 2, run_id: "k2", source: "kobis_daily",    target_year: null, target_date: "2026-05-10", status: "completed", started_at: "2026-05-10T05:00:00+09:00", finished_at: "2026-05-10T05:09:00+09:00", pages_fetched: 2, items_fetched: 54, items_inserted: 53, items_updated: 0, items_unchanged: 1, errors: 0 },
  { id: 1, run_id: "k1", source: "kobis_backfill", target_year: 2024, target_date: null,          status: "completed", started_at: "2026-05-09T12:00:00+09:00", finished_at: "2026-05-09T13:20:00+09:00", pages_fetched: 256, items_fetched: 12800, items_inserted: 12840, items_updated: 0, items_unchanged: 0, errors: 2 },
]

const MOCK_ITEMS: ExternalSourceItem[] = [
  { id: 1, content_id: 10, source_type: "kobis", external_id: "20240001", title_on_source: "파묘",           match_confidence: 0.97, matched_at: "2026-05-11T05:08:00+09:00", created_at: "2026-05-09T12:00:00+09:00" },
  { id: 2, content_id: 11, source_type: "kobis", external_id: "20240002", title_on_source: "범죄도시4",       match_confidence: 0.95, matched_at: "2026-05-11T05:08:00+09:00", created_at: "2026-05-09T12:00:00+09:00" },
  { id: 3, content_id: null, source_type: "kobis", external_id: "20240003", title_on_source: "미확인 신작",   match_confidence: null, matched_at: null,                        created_at: "2026-05-09T12:00:00+09:00" },
]

// ── 유틸 ──────────────────────────────────────────────────

const SOURCE_LABEL: Record<string, string> = {
  kobis_daily: "일별 수집",
  kobis_backfill: "전체 백필",
}

function statusIcon(status: string) {
  if (status === "completed") return <CheckCircle className="w-4 h-4 text-green-500" />
  if (status === "running")   return <RefreshCw   className="w-4 h-4 text-blue-500 animate-spin" />
  if (status === "failed")    return <XCircle     className="w-4 h-4 text-red-500" />
  return <AlertCircle className="w-4 h-4 text-amber-500" />
}

const STATUS_LABEL: Record<string, string> = { completed: "완료", running: "진행중", failed: "실패" }

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
  const [stats,   setStats]   = useState<ExternalSourceStats>(MOCK_STATS)
  const [logs,    setLogs]    = useState<TmdbSyncLogItem[]>(MOCK_LOGS)
  const [items,   setItems]   = useState<ExternalSourceItem[]>(MOCK_ITEMS)
  const [loading, setLoading] = useState(false)
  const [search,  setSearch]  = useState("")
  const [applied, setApplied] = useState("")

  const fetchAll = useCallback(async (title?: string) => {
    setLoading(true)
    try {
      const [s, l, i] = await Promise.all([
        kobisApi.getStats(),
        kobisApi.getSyncLog({ page: 1, size: 20 }),
        kobisApi.search({ title: title || undefined, size: 20 }),
      ])
      if (s.total_synced > 0) {
        setStats(s)
        setLogs(l.items)
        setItems(i.items)
      }
    } catch {
      // Mock 유지
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchAll() }, [fetchAll])

  function applySearch() { setApplied(search); fetchAll(search) }
  function clearSearch()  { setSearch(""); setApplied(""); fetchAll() }

  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">KOBIS</h2>
          <p className="text-sm text-muted-foreground mt-1">한국영화진흥위원회 캐시 현황</p>
        </div>
        <button onClick={() => fetchAll(applied)} className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors">
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />새로고침
        </button>
      </div>

      {/* KPI */}
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        <StatCard icon={<Database className="w-5 h-5" />} label="캐시 총 건수" value={stats.total_synced.toLocaleString()} />
        <StatCard icon={<Clock    className="w-5 h-5" />} label="마지막 수집" value={formatDate(stats.last_run_at)} sub={stats.last_run_status ? (STATUS_LABEL[stats.last_run_status] ?? stats.last_run_status) : "-"} />
        <StatCard icon={<CheckCircle className="w-5 h-5" />} label="최근 7일 수집" value={stats.last_7d_daily.reduce((a, d) => a + d.count, 0).toLocaleString()} sub="건" />
      </div>

      {/* 동기화 로그 */}
      <div>
        <h3 className="text-sm font-medium mb-3">동기화 로그</h3>
        <div className="rounded-xl border bg-card shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 border-b">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">소스</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">상태</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground hidden md:table-cell">시작</th>
                <th className="text-right px-4 py-3 font-medium text-muted-foreground">신규</th>
                <th className="text-right px-4 py-3 font-medium text-muted-foreground hidden lg:table-cell">오류</th>
                <th className="text-right px-4 py-3 font-medium text-muted-foreground hidden xl:table-cell">소요</th>
              </tr>
            </thead>
            <tbody>
              {logs.length === 0 ? (
                <tr><td colSpan={6} className="px-4 py-10 text-center text-muted-foreground">동기화 이력이 없습니다.</td></tr>
              ) : logs.map((log) => (
                <tr key={log.id} className="border-t hover:bg-muted/30 transition-colors">
                  <td className="px-4 py-3 font-medium">{SOURCE_LABEL[log.source] ?? log.source}</td>
                  <td className="px-4 py-3"><span className="flex items-center gap-1.5">{statusIcon(log.status)}<span className="text-xs">{STATUS_LABEL[log.status] ?? log.status}</span></span></td>
                  <td className="px-4 py-3 text-muted-foreground tabular-nums hidden md:table-cell">{formatDate(log.started_at)}</td>
                  <td className="px-4 py-3 text-right tabular-nums font-medium text-green-600 dark:text-green-400">+{log.items_inserted.toLocaleString()}</td>
                  <td className={`px-4 py-3 text-right tabular-nums hidden lg:table-cell ${log.errors > 0 ? "text-red-500" : "text-muted-foreground"}`}>{log.errors}</td>
                  <td className="px-4 py-3 text-right tabular-nums text-muted-foreground hidden xl:table-cell">{elapsedSec(log.started_at, log.finished_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 캐시 검색 */}
      <div>
        <h3 className="text-sm font-medium mb-3">캐시 검색</h3>
        <div className="flex gap-2 mb-3">
          <div className="relative flex-1 max-w-xs">
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
          <button onClick={applySearch} className="px-4 py-2 text-sm rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors">검색</button>
        </div>
        <div className="rounded-xl border bg-card shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 border-b">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">KOBIS ID</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">제목</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground hidden md:table-cell">신뢰도</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground hidden lg:table-cell">매핑일</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">콘텐츠</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr><td colSpan={5} className="px-4 py-10 text-center text-muted-foreground">결과가 없습니다.</td></tr>
              ) : items.map((item) => (
                <tr key={item.id} className="border-t hover:bg-muted/30 transition-colors">
                  <td className="px-4 py-3 tabular-nums text-muted-foreground font-mono text-xs">{item.external_id ?? "-"}</td>
                  <td className="px-4 py-3 font-medium">{item.title_on_source ?? "-"}</td>
                  <td className="px-4 py-3 text-muted-foreground hidden md:table-cell">{item.match_confidence !== null ? `${(item.match_confidence * 100).toFixed(0)}%` : "-"}</td>
                  <td className="px-4 py-3 text-muted-foreground hidden lg:table-cell tabular-nums">{formatDate(item.matched_at)}</td>
                  <td className="px-4 py-3">{item.content_id ? <span className="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">#{item.content_id}</span> : <span className="text-xs text-muted-foreground">미연결</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
