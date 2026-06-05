"use client"

import { useEffect, useState, useCallback } from "react"
import { Search, X, ChevronLeft, ChevronRight, RefreshCw, Film, Tv, Database, Clock, CheckCircle, XCircle, AlertCircle } from "lucide-react"
import { tmdbCacheApi, type TmdbCacheStats, type TmdbSyncLogItem, type TmdbCacheRecentItem } from "@/lib/api"
import Image from "next/image"

// ── Mock 데이터 ───────────────────────────────────────────

const MOCK_STATS: TmdbCacheStats = {
  total_movies: 847_230, total_tv: 192_440, total_persons: 0,
  last_24h_movies_added: 65, last_24h_tv_added: 16, last_24h_errors: 0,
  last_7d_daily: [
    { date: "2026-05-05", movies: 42, tv: 11, errors: 0 },
    { date: "2026-05-06", movies: 58, tv: 14, errors: 0 },
    { date: "2026-05-07", movies: 31, tv: 8,  errors: 1 },
    { date: "2026-05-08", movies: 77, tv: 22, errors: 0 },
    { date: "2026-05-09", movies: 55, tv: 18, errors: 0 },
    { date: "2026-05-10", movies: 65, tv: 16, errors: 0 },
    { date: "2026-05-11", movies: 0,  tv: 0,  errors: 0 },
  ],
  oldest_movie_year: 1900, newest_movie_year: 2026,
  last_run_at: "2026-05-10T18:45:00+09:00", last_run_status: "completed",
}

const MOCK_LOGS: TmdbSyncLogItem[] = [
  { id: 4, run_id: "a4", source: "daily_new_releases", target_year: null, target_date: "2026-05-05", status: "completed", started_at: "2026-05-05T03:45:00+09:00", finished_at: "2026-05-05T03:52:00+09:00", pages_fetched: 4, items_fetched: 80, items_inserted: 65, items_updated: 12, items_unchanged: 3, errors: 0 },
  { id: 3, run_id: "a3", source: "daily_changes",      target_year: null, target_date: "2026-05-05", status: "completed", started_at: "2026-05-05T03:30:00+09:00", finished_at: "2026-05-05T03:44:00+09:00", pages_fetched: 8, items_fetched: 143, items_inserted: 0, items_updated: 143, items_unchanged: 0, errors: 0 },
  { id: 2, run_id: "a2", source: "daily_new_releases", target_year: null, target_date: "2026-05-04", status: "completed", started_at: "2026-05-04T03:45:00+09:00", finished_at: "2026-05-04T03:51:00+09:00", pages_fetched: 3, items_fetched: 55, items_inserted: 55, items_updated: 8,   items_unchanged: 0, errors: 0 },
  { id: 1, run_id: "a1", source: "backfill_discover",  target_year: 2024, target_date: null,          status: "completed", started_at: "2026-05-04T10:00:00+09:00", finished_at: "2026-05-04T14:30:00+09:00", pages_fetched: 4240, items_fetched: 847_230, items_inserted: 847_000, items_updated: 0, items_unchanged: 0, errors: 12 },
]

const MOCK_CACHE: TmdbCacheRecentItem[] = [
  { id: 496243, title: "기생충", original_title: "Parasite", release_date: "2019-05-30", first_air_date: null, popularity: 42.5, vote_average: 8.5, poster_url: "https://image.tmdb.org/t/p/w300/7IiTTgloJzvGI1TAYymCfbfl3vT.jpg", kind: "movie", fetched_at: "2026-05-10T18:45:00+09:00" },
  { id: 93405, title: "오징어 게임", original_title: "Squid Game", release_date: null, first_air_date: "2021-09-17", popularity: 88.2, vote_average: 7.9, poster_url: "https://image.tmdb.org/t/p/w300/dDlEmu3EZ0Pgg93K2SVNLCjCSvE.jpg", kind: "tv", fetched_at: "2026-05-10T18:45:00+09:00" },
  { id: 1165227, title: "서울의 봄", original_title: "12.12: The Day", release_date: "2023-11-22", first_air_date: null, popularity: 31.4, vote_average: 8.0, poster_url: null, kind: "movie", fetched_at: "2026-05-09T03:52:00+09:00" },
  { id: 197067, title: "이상한 변호사 우영우", original_title: "Extraordinary Attorney Woo", release_date: null, first_air_date: "2022-06-29", popularity: 55.3, vote_average: 8.8, poster_url: "https://image.tmdb.org/t/p/w300/8Ovm3mz8BgclsOGQMeYtrxMbJGg.jpg", kind: "tv", fetched_at: "2026-05-08T03:44:00+09:00" },
]

// ── 상수 ──────────────────────────────────────────────────

const SOURCE_LABEL: Record<string, string> = {
  daily_changes: "일별 변경",
  daily_new_releases: "신규 출시",
  backfill_discover: "전체 백필",
  manual: "수동",
}

const SYNC_STATUS_LABEL: Record<string, string> = {
  completed: "완료",
  running: "진행중",
  failed: "실패",
  partial: "일부완료",
}

function formatDate(iso: string | null) {
  if (!iso) return "-"
  return new Date(iso).toLocaleDateString("ko-KR", { year: "numeric", month: "2-digit", day: "2-digit" })
}

function formatDateTime(iso: string | null) {
  if (!iso) return "-"
  const m = iso.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/)
  return m ? `${m[2]}.${m[3]} ${m[4]}:${m[5]}` : iso
}

function statusIcon(status: string) {
  if (status === "completed") return <CheckCircle className="w-4 h-4 text-green-500" />
  if (status === "running")   return <RefreshCw   className="w-4 h-4 text-blue-500 animate-spin" />
  if (status === "failed")    return <XCircle     className="w-4 h-4 text-red-500" />
  return <AlertCircle className="w-4 h-4 text-amber-500" />
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

function BarChart({ data }: { data: TmdbCacheStats["last_7d_daily"] }) {
  const max = Math.max(...data.map((d) => d.movies + d.tv), 1)
  return (
    <div className="rounded-xl border bg-card p-4 shadow-sm">
      <p className="text-sm font-medium mb-4">최근 7일 수집량</p>
      <div className="flex items-end gap-2 h-32">
        {data.map((d) => {
          const total = d.movies + d.tv
          const moviePct = (d.movies / max) * 100
          const tvPct    = (d.tv    / max) * 100
          const label = d.date.slice(5)
          return (
            <div key={d.date} className="flex-1 flex flex-col items-center gap-1 h-full justify-end">
              <span className="text-xs text-muted-foreground tabular-nums">{total > 0 ? total : ""}</span>
              <div className="w-full flex flex-col justify-end gap-px" style={{ height: "80%" }}>
                <div className="w-full bg-blue-400/80 dark:bg-blue-500/70 rounded-sm transition-all" style={{ height: `${tvPct}%` }} />
                <div className="w-full bg-primary/70 rounded-sm transition-all" style={{ height: `${moviePct}%` }} />
              </div>
              <span className="text-[10px] text-muted-foreground">{label}</span>
            </div>
          )
        })}
      </div>
      <div className="flex items-center gap-4 mt-3">
        <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <span className="inline-block w-3 h-2 rounded-sm bg-primary/70" />영화
        </span>
        <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <span className="inline-block w-3 h-2 rounded-sm bg-blue-400/80 dark:bg-blue-500/70" />TV
        </span>
      </div>
    </div>
  )
}

function TmdbDetailPanel({ item, onClose }: { item: TmdbCacheRecentItem; onClose: () => void }) {
  const fields: Array<[string, string | null]> = [
    ["원제",    item.original_title],
    ["출시일",  item.release_date ?? item.first_air_date],
    ["인기도",  item.popularity != null ? item.popularity.toFixed(1) : null],
    ["평점",    item.vote_average != null ? `${item.vote_average.toFixed(1)} / 10` : null],
    ["TMDB ID", String(item.id)],
    ["수집일",  formatDate(item.fetched_at)],
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
          {item.poster_url ? (
            <Image src={item.poster_url} alt={item.title} width={120} height={180} className="rounded object-cover border border-border" unoptimized />
          ) : (
            <div className="w-[120px] h-[180px] rounded border border-dashed border-border flex items-center justify-center text-muted-foreground">
              {item.kind === "movie" ? <Film className="w-8 h-8" /> : <Tv className="w-8 h-8" />}
            </div>
          )}
        </div>
        <div className="flex justify-center">
          <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${item.kind === "movie" ? "bg-primary/10 text-primary" : "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400"}`}>
            {item.kind === "movie" ? "영화" : "TV 시리즈"}
          </span>
        </div>
        <div className="space-y-1.5">
          {fields.map(([label, value]) => value != null && (
            <div key={label} className="flex gap-2">
              <span className="text-xs text-muted-foreground w-16 shrink-0">{label}</span>
              <span className="text-xs flex-1 truncate">{value}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default function TmdbPage() {
  const [stats, setStats] = useState<TmdbCacheStats>(MOCK_STATS)
  const [logs,  setLogs]  = useState<TmdbSyncLogItem[]>(MOCK_LOGS)

  // Cache 검색
  const [cacheSearch,  setCacheSearch]  = useState("")
  const [appliedCache, setAppliedCache] = useState("")
  const [kindFilter,   setKindFilter]   = useState<"movie" | "tv">("movie")
  const [cacheItems,   setCacheItems]   = useState<TmdbCacheRecentItem[]>(MOCK_CACHE)
  const [cacheTotal,   setCacheTotal]   = useState(MOCK_CACHE.length)
  const [cachePage,    setCachePage]    = useState(1)
  const [cacheLoading, setCacheLoading] = useState(false)
  const [selectedItem, setSelectedItem] = useState<TmdbCacheRecentItem | null>(null)

  const SIZE = 20

  const fetchStats = useCallback(async () => {
    try {
      const [s, l] = await Promise.all([
        tmdbCacheApi.getStats(),
        tmdbCacheApi.getSyncLog({ page: 1, size: 20 }),
      ])
      if (s.total_movies + s.total_tv > 0) {
        setStats(s)
        setLogs(l.items)
      }
    } catch { /* Mock 유지 */ }
  }, [])

  const fetchCache = useCallback(async (p: number, title: string, kind: "movie" | "tv") => {
    setCacheLoading(true)
    try {
      const data = await tmdbCacheApi.search({ title: title || undefined, kind, page: p, size: SIZE })
      setCacheItems(data.items)
      setCacheTotal(data.total)
    } catch {
      setCacheItems(MOCK_CACHE.filter(i => i.kind === kind))
      setCacheTotal(MOCK_CACHE.filter(i => i.kind === kind).length)
    } finally {
      setCacheLoading(false)
    }
  }, [])

  useEffect(() => { fetchStats() }, [fetchStats])
  useEffect(() => { fetchCache(cachePage, appliedCache, kindFilter) }, [cachePage, appliedCache, kindFilter, fetchCache])

  function applySearch() { setAppliedCache(cacheSearch); setCachePage(1) }
  function clearSearch()  { setCacheSearch(""); setAppliedCache(""); setCachePage(1) }

  const totalPages = Math.max(1, Math.ceil(cacheTotal / SIZE))

  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">TMDB</h2>
          <p className="text-sm text-muted-foreground mt-1">
            로컬 TMDB 캐시 DB 수집 현황 — 영화 {stats.oldest_movie_year ?? "?"}~{stats.newest_movie_year ?? "?"}
          </p>
        </div>
        <button onClick={fetchStats} className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors">
          <RefreshCw className="w-4 h-4" />새로고침
        </button>
      </div>

      {/* KPI 카드 4개 */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="rounded-xl border bg-card p-4 shadow-sm flex items-start gap-3">
          <div className="mt-0.5 text-muted-foreground"><Film className="w-5 h-5" /></div>
          <div className="min-w-0">
            <p className="text-xs text-muted-foreground">영화 총 건수</p>
            <p className="text-2xl font-semibold tabular-nums tracking-tight mt-0.5">{stats.total_movies.toLocaleString()}</p>
            <p className="text-xs text-muted-foreground mt-0.5">어제 +{stats.last_24h_movies_added}</p>
          </div>
        </div>
        <div className="rounded-xl border bg-card p-4 shadow-sm flex items-start gap-3">
          <div className="mt-0.5 text-muted-foreground"><Tv className="w-5 h-5" /></div>
          <div className="min-w-0">
            <p className="text-xs text-muted-foreground">TV 총 건수</p>
            <p className="text-2xl font-semibold tabular-nums tracking-tight mt-0.5">{stats.total_tv.toLocaleString()}</p>
            <p className="text-xs text-muted-foreground mt-0.5">어제 +{stats.last_24h_tv_added}</p>
          </div>
        </div>
        <div className="rounded-xl border bg-card p-4 shadow-sm flex items-start gap-3">
          <div className="mt-0.5 text-muted-foreground"><Database className="w-5 h-5" /></div>
          <div className="min-w-0">
            <p className="text-xs text-muted-foreground">전체 합계</p>
            <p className="text-2xl font-semibold tabular-nums tracking-tight mt-0.5">{(stats.total_movies + stats.total_tv).toLocaleString()}</p>
          </div>
        </div>
        <div className="rounded-xl border bg-card p-4 shadow-sm flex items-start gap-3">
          <div className="mt-0.5 text-muted-foreground"><Clock className="w-5 h-5" /></div>
          <div className="min-w-0">
            <p className="text-xs text-muted-foreground">마지막 실행</p>
            <p className="text-2xl font-semibold tabular-nums tracking-tight mt-0.5">{stats.last_run_at ? formatDateTime(stats.last_run_at) : "-"}</p>
            <p className="text-xs text-muted-foreground mt-0.5">{stats.last_run_status ? SYNC_STATUS_LABEL[stats.last_run_status] ?? stats.last_run_status : "-"}</p>
          </div>
        </div>
      </div>

      {/* 7일 바 차트 */}
      <BarChart data={stats.last_7d_daily} />

      {/* 동기화 로그 테이블 */}
      <div>
        <h3 className="text-sm font-medium mb-3">동기화 로그</h3>
        <div className="rounded-xl border bg-card shadow-sm overflow-y-auto max-h-[200px]">
          <table className="w-full text-sm">
            <thead className="bg-muted border-b sticky top-0 z-10">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">소스</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">상태</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground hidden md:table-cell">시작</th>
                <th className="text-right px-4 py-3 font-medium text-muted-foreground">페이지</th>
                <th className="text-right px-4 py-3 font-medium text-muted-foreground">신규</th>
                <th className="text-right px-4 py-3 font-medium text-muted-foreground hidden lg:table-cell">갱신</th>
                <th className="text-right px-4 py-3 font-medium text-muted-foreground hidden lg:table-cell">오류</th>
              </tr>
            </thead>
            <tbody>
              {logs.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-10 text-center text-muted-foreground">동기화 이력이 없습니다.</td>
                </tr>
              ) : (
                logs.map((log) => (
                  <tr key={log.id} className="border-t hover:bg-muted/30 transition-colors">
                    <td className="px-4 py-3 font-medium">{SOURCE_LABEL[log.source] ?? log.source}</td>
                    <td className="px-4 py-3">
                      <span className="flex items-center gap-1.5">
                        {statusIcon(log.status)}
                        <span className="text-xs">{SYNC_STATUS_LABEL[log.status] ?? log.status}</span>
                      </span>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground tabular-nums hidden md:table-cell">{formatDateTime(log.started_at)}</td>
                    <td className="px-4 py-3 text-right tabular-nums text-muted-foreground">{log.pages_fetched.toLocaleString()}</td>
                    <td className="px-4 py-3 text-right tabular-nums font-medium text-green-600 dark:text-green-400">+{log.items_inserted.toLocaleString()}</td>
                    <td className="px-4 py-3 text-right tabular-nums text-muted-foreground hidden lg:table-cell">{log.items_updated.toLocaleString()}</td>
                    <td className={`px-4 py-3 text-right tabular-nums hidden lg:table-cell ${log.errors > 0 ? "text-red-500" : "text-muted-foreground"}`}>{log.errors}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* TMDB 로컬 캐시 */}
      <div>
        <h3 className="text-sm font-medium mb-3">TMDB 로컬 캐시</h3>
        <div className="flex flex-wrap gap-2 mb-4">
          <div className="relative flex-1 min-w-[200px] max-w-xs">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <input
              value={cacheSearch}
              onChange={(e) => setCacheSearch(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && applySearch()}
              placeholder="제목 검색..."
              className="w-full pl-9 pr-8 py-2 text-sm rounded-md border bg-background focus:outline-none focus:ring-2 focus:ring-ring"
            />
            {cacheSearch && (
              <button onClick={clearSearch} className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
                <X className="w-4 h-4" />
              </button>
            )}
          </div>
          {(["movie", "tv"] as const).map((k) => (
            <button key={k} onClick={() => { setKindFilter(k); setCachePage(1) }}
              className={`flex items-center gap-1.5 px-3 py-2 text-sm rounded-md border transition-colors ${
                kindFilter === k ? "bg-primary text-primary-foreground border-primary" : "bg-background hover:bg-muted border-border"
              }`}>
              {k === "movie" ? <><Film className="w-3.5 h-3.5" />영화</> : <><Tv className="w-3.5 h-3.5" />TV</>}
            </button>
          ))}
          <button onClick={applySearch}
            className="px-4 py-2 text-sm rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors">
            검색
          </button>
        </div>
      </div>

      {/* 캐시 목록 + 상세 패널 */}
      <div className={`grid gap-4 items-start ${selectedItem ? "xl:grid-cols-[1fr_280px]" : ""}`}>
        <div className="space-y-3">
          <div className="rounded-xl border bg-card shadow-sm overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-muted/50 border-b">
                <tr>
                  <th className="text-left px-4 py-3 font-medium text-muted-foreground">제목</th>
                  <th className="text-left px-4 py-3 font-medium text-muted-foreground hidden sm:table-cell">원제</th>
                  <th className="text-left px-4 py-3 font-medium text-muted-foreground hidden md:table-cell">유형</th>
                  <th className="text-left px-4 py-3 font-medium text-muted-foreground hidden md:table-cell">출시일</th>
                  <th className="text-right px-4 py-3 font-medium text-muted-foreground hidden lg:table-cell">인기도</th>
                  <th className="text-right px-4 py-3 font-medium text-muted-foreground hidden lg:table-cell">평점</th>
                  <th className="text-left px-4 py-3 font-medium text-muted-foreground hidden xl:table-cell">수집일</th>
                </tr>
              </thead>
              <tbody>
                {cacheLoading ? (
                  <tr><td colSpan={7} className="px-4 py-12 text-center text-muted-foreground">
                    <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2" />불러오는 중...
                  </td></tr>
                ) : cacheItems.length === 0 ? (
                  <tr><td colSpan={7} className="px-4 py-12 text-center text-muted-foreground">
                    TMDB 캐시 항목이 없습니다.
                  </td></tr>
                ) : cacheItems.map((item) => {
                  const isSelected = selectedItem?.id === item.id && selectedItem?.kind === item.kind
                  return (
                    <tr
                      key={`${item.kind}-${item.id}`}
                      onClick={() => setSelectedItem(isSelected ? null : item)}
                      className={`border-t hover:bg-muted/30 transition-colors cursor-pointer ${isSelected ? "bg-primary/5 border-l-2 border-l-primary" : ""}`}
                    >
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          <div className="rounded overflow-hidden bg-muted shrink-0 relative" style={{ width: 28, height: 40 }}>
                            {item.poster_url ? (
                              <Image src={item.poster_url} alt={item.title} fill className="object-cover" unoptimized />
                            ) : (
                              <div className="w-full h-full flex items-center justify-center text-muted-foreground">
                                {item.kind === "movie" ? <Film className="w-3 h-3" /> : <Tv className="w-3 h-3" />}
                              </div>
                            )}
                          </div>
                          <span className="font-medium truncate">{item.title}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-muted-foreground text-xs truncate max-w-[160px] hidden sm:table-cell">{item.original_title ?? "-"}</td>
                      <td className="px-4 py-3 hidden md:table-cell">
                        <span className="flex items-center gap-1 text-muted-foreground text-xs">
                          {item.kind === "movie" ? <><Film className="w-3 h-3" />영화</> : <><Tv className="w-3 h-3" />TV</>}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-muted-foreground tabular-nums hidden md:table-cell">
                        {item.release_date ?? item.first_air_date ?? "-"}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums text-muted-foreground hidden lg:table-cell">
                        {item.popularity != null ? item.popularity.toFixed(1) : "-"}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums font-medium hidden lg:table-cell">
                        {item.vote_average != null ? item.vote_average.toFixed(1) : "-"}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground tabular-nums hidden xl:table-cell">
                        {formatDate(item.fetched_at)}
                      </td>
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

        {selectedItem && <TmdbDetailPanel item={selectedItem} onClose={() => setSelectedItem(null)} />}
      </div>
    </div>
  )
}
