"use client"

import { useEffect, useState, useCallback } from "react"
import { RefreshCw, Search, X, CheckCircle, XCircle, AlertCircle, Clock, Database, ChevronLeft, ChevronRight, ArrowLeft } from "lucide-react"
import Link from "next/link"
import {
  kobisApi,
  type ExternalSourceStats,
  type KobisCacheItem,
  type TmdbSyncLogItem,
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

const MOCK_CACHE: KobisCacheItem[] = [
  { movie_cd: "20240001", title: "파묘", title_en: "Exhuma", open_dt: "2024-02-22", prdt_year: 2024, rep_genre_nm: "공포,미스터리", rep_nation_nm: "한국", first_fetched_at: "2026-05-18T07:11:00+09:00", last_fetched_at: "2026-05-18T07:11:00+09:00" },
  { movie_cd: "20240002", title: "범죄도시4", title_en: "The Roundup: Punishment", open_dt: "2024-04-24", prdt_year: 2024, rep_genre_nm: "액션,범죄", rep_nation_nm: "한국", first_fetched_at: "2026-05-18T07:11:01+09:00", last_fetched_at: "2026-05-18T07:11:01+09:00" },
]

// ── 상수 ──────────────────────────────────────────────────

const SOURCE_LABEL: Record<string, string> = {
  kobis_daily: "일별 수집",
  kobis_backfill: "전체 백필",
}

const SYNC_STATUS_LABEL: Record<string, string> = { completed: "완료", running: "진행중", failed: "실패" }

function statusIcon(status: string) {
  if (status === "completed") return <CheckCircle className="w-4 h-4 text-green-500" />
  if (status === "running")   return <RefreshCw   className="w-4 h-4 text-blue-500 animate-spin" />
  if (status === "failed")    return <XCircle     className="w-4 h-4 text-red-500" />
  return <AlertCircle className="w-4 h-4 text-amber-500" />
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

// ── 상세 패널 ─────────────────────────────────────────────

function KobisDetailPanel({ item, onClose }: { item: KobisCacheItem; onClose: () => void }) {
  const fields: Array<[string, string | null]> = [
    ["영문제목", item.title_en],
    ["영화코드", item.movie_cd],
    ["개봉일",   item.open_dt],
    ["제작연도", item.prdt_year != null ? String(item.prdt_year) : null],
    ["장르",     item.rep_genre_nm],
    ["국가",     item.rep_nation_nm],
    ["수집일",   formatDate(item.last_fetched_at)],
  ]
  return (
    <div className="rounded-xl border bg-card shadow-sm overflow-hidden sticky top-4">
      <div className="px-4 py-3 bg-muted/50 border-b flex items-center justify-between gap-2">
        <span className="text-sm font-semibold truncate flex-1">{item.title}</span>
        <button onClick={onClose} className="text-muted-foreground hover:text-foreground shrink-0 transition-colors">
          <X className="w-4 h-4" />
        </button>
      </div>
      <div className="p-4 space-y-3">
        <div className="flex justify-center">
          <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
            KOBIS 영화
          </span>
        </div>
        <div className="space-y-1.5">
          {fields.map(([label, value]) => value != null && (
            <div key={label} className="flex gap-2">
              <span className="text-xs text-muted-foreground w-16 shrink-0">{label}</span>
              <span className="text-xs flex-1 break-all">{value}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ── 메인 컴포넌트 ─────────────────────────────────────────

export default function KobisPage() {
  const [stats,   setStats]   = useState<ExternalSourceStats>(MOCK_STATS)
  const [logs,    setLogs]    = useState<TmdbSyncLogItem[]>(MOCK_LOGS)
  const [cache,   setCache]   = useState<KobisCacheItem[]>(MOCK_CACHE)
  const [cacheTotal,   setCacheTotal]   = useState(MOCK_CACHE.length)
  const [cachePage,    setCachePage]    = useState(1)
  const [cacheLoading, setCacheLoading] = useState(false)
  const [search,  setSearch]  = useState("")
  const [applied, setApplied] = useState("")
  const [selectedItem, setSelectedItem] = useState<KobisCacheItem | null>(null)

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

  const fetchCache = useCallback(async (p: number, title: string) => {
    setCacheLoading(true)
    try {
      const data = await kobisApi.getCache({ title: title || undefined, page: p, size: SIZE })
      setCache(data.items)
      setCacheTotal(data.total)
    } catch {
      setCache(MOCK_CACHE)
      setCacheTotal(MOCK_CACHE.length)
    } finally {
      setCacheLoading(false)
    }
  }, [])

  useEffect(() => { fetchStats() }, [fetchStats])
  useEffect(() => { fetchCache(cachePage, applied) }, [cachePage, applied, fetchCache])

  function applySearch() { setApplied(search); setCachePage(1) }
  function clearSearch()  { setSearch(""); setApplied(""); setCachePage(1) }

  const totalPages = Math.max(1, Math.ceil(cacheTotal / SIZE))

  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Link href="/programming/sources" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors">
              <ArrowLeft className="h-4 w-4" />
              외부 소스
            </Link>
          </div>
          <h2 className="text-2xl font-semibold tracking-tight">KOBIS</h2>
          <p className="text-sm text-muted-foreground mt-1">한국영화진흥위원회 — 매핑 현황 및 콘텐츠 탐색</p>
        </div>
        <button onClick={() => { fetchStats(); fetchCache(cachePage, applied) }}
          className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors">
          <RefreshCw className={`w-4 h-4 ${cacheLoading ? "animate-spin" : ""}`} />새로고침
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

      {/* KOBIS 로컬 캐시 검색 */}
      <div>
        <h3 className="text-sm font-medium mb-3">KOBIS 로컬 캐시</h3>
        <div className="flex gap-2 mb-3">
          <div className="relative flex-1 max-w-xs">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <input value={search} onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && applySearch()}
              placeholder="제목 검색..."
              className="w-full pl-9 pr-8 py-2 text-sm rounded-md border bg-background focus:outline-none focus:ring-2 focus:ring-ring" />
            {search && (
              <button onClick={clearSearch} className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
                <X className="w-4 h-4" />
              </button>
            )}
          </div>
          <button onClick={applySearch}
            className="px-4 py-2 text-sm rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors">검색</button>
        </div>
        <div className={`grid gap-4 items-start ${selectedItem ? "xl:grid-cols-[1fr_280px]" : ""}`}>
          <div className="space-y-3">
            <div className="rounded-xl border bg-card shadow-sm overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-muted/50 border-b">
                  <tr>
                    <th className="text-left px-4 py-3 font-medium text-muted-foreground">영화코드</th>
                    <th className="text-left px-4 py-3 font-medium text-muted-foreground">제목</th>
                    <th className="text-left px-4 py-3 font-medium text-muted-foreground hidden sm:table-cell">영문제목</th>
                    <th className="text-left px-4 py-3 font-medium text-muted-foreground hidden md:table-cell">개봉일</th>
                    <th className="text-left px-4 py-3 font-medium text-muted-foreground hidden md:table-cell">제작연도</th>
                    <th className="text-left px-4 py-3 font-medium text-muted-foreground hidden lg:table-cell">장르</th>
                    <th className="text-left px-4 py-3 font-medium text-muted-foreground hidden lg:table-cell">국가</th>
                    <th className="text-left px-4 py-3 font-medium text-muted-foreground hidden xl:table-cell">수집일</th>
                  </tr>
                </thead>
                <tbody>
                  {cacheLoading ? (
                    <tr><td colSpan={8} className="px-4 py-12 text-center text-muted-foreground">
                      <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2" />불러오는 중...
                    </td></tr>
                  ) : cache.length === 0 ? (
                    <tr><td colSpan={8} className="px-4 py-12 text-center text-muted-foreground">결과가 없습니다.</td></tr>
                  ) : cache.map((item) => {
                    const isSelected = selectedItem?.movie_cd === item.movie_cd
                    return (
                      <tr
                        key={item.movie_cd}
                        onClick={() => setSelectedItem(isSelected ? null : item)}
                        className={`border-t hover:bg-muted/30 transition-colors cursor-pointer ${isSelected ? "bg-primary/5 border-l-2 border-l-primary" : ""}`}
                      >
                        <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{item.movie_cd}</td>
                        <td className="px-4 py-3 font-medium">{item.title}</td>
                        <td className="px-4 py-3 text-xs text-muted-foreground hidden sm:table-cell">{item.title_en ?? "-"}</td>
                        <td className="px-4 py-3 text-muted-foreground tabular-nums hidden md:table-cell">{item.open_dt ?? "-"}</td>
                        <td className="px-4 py-3 text-muted-foreground tabular-nums hidden md:table-cell">{item.prdt_year ?? "-"}</td>
                        <td className="px-4 py-3 text-muted-foreground hidden lg:table-cell">{item.rep_genre_nm ?? "-"}</td>
                        <td className="px-4 py-3 text-muted-foreground hidden lg:table-cell">{item.rep_nation_nm ?? "-"}</td>
                        <td className="px-4 py-3 text-muted-foreground tabular-nums hidden xl:table-cell">{formatDate(item.last_fetched_at)}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>

            {/* 페이지네이션 */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-1">
                <button onClick={() => setCachePage((p) => Math.max(1, p - 1))} disabled={cachePage === 1}
                  className="p-2 rounded-md hover:bg-muted disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
                  <ChevronLeft className="w-4 h-4" />
                </button>
                {buildPages(cachePage, totalPages).map((p, i) =>
                  p === "…" ? (
                    <span key={`e${i}`} className="px-2 text-muted-foreground">…</span>
                  ) : (
                    <button key={p} onClick={() => setCachePage(p)}
                      className={`min-w-[36px] h-9 px-2 rounded-md text-sm transition-colors ${
                        p === cachePage ? "bg-primary text-primary-foreground font-medium" : "hover:bg-muted text-muted-foreground"
                      }`}>{p}</button>
                  )
                )}
                <button onClick={() => setCachePage((p) => Math.min(totalPages, p + 1))} disabled={cachePage === totalPages}
                  className="p-2 rounded-md hover:bg-muted disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            )}
          </div>

          {selectedItem && <KobisDetailPanel item={selectedItem} onClose={() => setSelectedItem(null)} />}
        </div>
      </div>
    </div>
  )
}
