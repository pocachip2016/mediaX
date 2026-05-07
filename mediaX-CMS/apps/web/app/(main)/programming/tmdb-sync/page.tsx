"use client"

import { useEffect, useState, useCallback } from "react"
import { RefreshCw, Film, Tv, Database, Clock, CheckCircle, XCircle, AlertCircle } from "lucide-react"
import Image from "next/image"
import {
  tmdbCacheApi,
  type TmdbCacheStats,
  type TmdbSyncLogItem,
  type TmdbCacheRecentItem,
} from "@/lib/api"

// ── Mock 데이터 ───────────────────────────────────────────

const MOCK_STATS: TmdbCacheStats = {
  total_movies: 847_230,
  total_tv: 192_440,
  total_persons: 0,
  last_24h_movies_added: 65,
  last_24h_tv_added: 16,
  last_24h_errors: 0,
  last_7d_daily: [
    { date: "2026-04-30", movies: 42, tv: 11, errors: 0 },
    { date: "2026-05-01", movies: 58, tv: 14, errors: 0 },
    { date: "2026-05-02", movies: 31, tv: 8,  errors: 1 },
    { date: "2026-05-03", movies: 77, tv: 22, errors: 0 },
    { date: "2026-05-04", movies: 55, tv: 18, errors: 0 },
    { date: "2026-05-05", movies: 65, tv: 16, errors: 0 },
    { date: "2026-05-06", movies: 0,  tv: 0,  errors: 0 },
  ],
  oldest_movie_year: 1900,
  newest_movie_year: 2026,
  last_run_at: "2026-05-05T18:45:00+09:00",
  last_run_status: "completed",
}

const MOCK_LOGS: TmdbSyncLogItem[] = [
  { id: 4, run_id: "a4", source: "daily_new_releases", target_year: null, target_date: "2026-05-05", status: "completed", started_at: "2026-05-05T03:45:00+09:00", finished_at: "2026-05-05T03:52:00+09:00", pages_fetched: 4, items_fetched: 80, items_inserted: 65, items_updated: 12, items_unchanged: 3, errors: 0 },
  { id: 3, run_id: "a3", source: "daily_changes",      target_year: null, target_date: "2026-05-05", status: "completed", started_at: "2026-05-05T03:30:00+09:00", finished_at: "2026-05-05T03:44:00+09:00", pages_fetched: 8, items_fetched: 143, items_inserted: 0, items_updated: 143, items_unchanged: 0, errors: 0 },
  { id: 2, run_id: "a2", source: "daily_new_releases", target_year: null, target_date: "2026-05-04", status: "completed", started_at: "2026-05-04T03:45:00+09:00", finished_at: "2026-05-04T03:51:00+09:00", pages_fetched: 3, items_fetched: 55, items_inserted: 55, items_updated: 8,   items_unchanged: 0, errors: 0 },
  { id: 1, run_id: "a1", source: "backfill_discover",  target_year: 2024, target_date: null,          status: "completed", started_at: "2026-05-04T10:00:00+09:00", finished_at: "2026-05-04T14:30:00+09:00", pages_fetched: 4240, items_fetched: 847_230, items_inserted: 847_000, items_updated: 0, items_unchanged: 0, errors: 12 },
]

const MOCK_RECENT: TmdbCacheRecentItem[] = [
  { id: 1337404, title: "미키 17",        original_title: "Mickey 17",              release_date: "2025-02-28", first_air_date: null, popularity: 184.5, vote_average: 7.2, poster_url: null, kind: "movie", fetched_at: "2026-05-05T18:00:00+09:00" },
  { id: 1100782, title: "설국열차 2",      original_title: "Snowpiercer 2",          release_date: null,         first_air_date: "2025-12-01", popularity: 95.2, vote_average: 7.8, poster_url: null, kind: "tv",    fetched_at: "2026-05-05T18:00:00+09:00" },
  { id: 945961,  title: "에이리언: 로물루스", original_title: "Alien: Romulus",       release_date: "2024-08-16", first_air_date: null, popularity: 78.9, vote_average: 7.4, poster_url: null, kind: "movie", fetched_at: "2026-05-05T18:00:00+09:00" },
  { id: 1010600, title: "데드풀 & 울버린", original_title: "Deadpool & Wolverine",   release_date: "2024-07-26", first_air_date: null, popularity: 72.1, vote_average: 7.7, poster_url: null, kind: "movie", fetched_at: "2026-05-05T18:00:00+09:00" },
  { id: 202555,  title: "더 베어",         original_title: "The Bear",               release_date: null,         first_air_date: "2022-06-23", popularity: 68.3, vote_average: 8.5, poster_url: null, kind: "tv",    fetched_at: "2026-05-05T18:00:00+09:00" },
  { id: 1012149, title: "퓨리오사",        original_title: "Furiosa: A Mad Max Saga", release_date: "2024-05-24", first_air_date: null, popularity: 61.7, vote_average: 7.6, poster_url: null, kind: "movie", fetched_at: "2026-05-05T18:00:00+09:00" },
]

// ── 유틸 ──────────────────────────────────────────────────

const SOURCE_LABEL: Record<string, string> = {
  daily_changes: "일별 변경",
  daily_new_releases: "신규 출시",
  backfill_discover: "전체 백필",
  manual: "수동",
}

function statusIcon(status: string) {
  if (status === "completed") return <CheckCircle className="w-4 h-4 text-green-500" />
  if (status === "running")   return <RefreshCw   className="w-4 h-4 text-blue-500 animate-spin" />
  if (status === "failed")    return <XCircle     className="w-4 h-4 text-red-500" />
  return <AlertCircle className="w-4 h-4 text-amber-500" />
}

const STATUS_LABEL: Record<string, string> = {
  completed: "완료",
  running: "진행중",
  failed: "실패",
  partial: "일부완료",
}

function formatDate(iso: string | null) {
  if (!iso) return "-"
  return new Date(iso).toLocaleString("ko-KR", {
    month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
  })
}

function formatNum(n: number) {
  return n.toLocaleString()
}

function elapsedSec(start: string, end: string | null) {
  if (!end) return "-"
  const s = (new Date(end).getTime() - new Date(start).getTime()) / 1000
  if (s < 60) return `${s.toFixed(0)}s`
  return `${(s / 60).toFixed(1)}m`
}

// ── 서브 컴포넌트 ─────────────────────────────────────────

function StatCard({ icon, label, value, sub }: {
  icon: React.ReactNode; label: string; value: string; sub?: string
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
                <div
                  className="w-full bg-blue-400/80 dark:bg-blue-500/70 rounded-sm transition-all"
                  style={{ height: `${tvPct}%` }}
                />
                <div
                  className="w-full bg-primary/70 rounded-sm transition-all"
                  style={{ height: `${moviePct}%` }}
                />
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

// ── 메인 컴포넌트 ─────────────────────────────────────────

export default function TmdbSyncPage() {
  const [stats, setStats] = useState<TmdbCacheStats | null>(null)
  const [logs,  setLogs]  = useState<TmdbSyncLogItem[]>([])
  const [recent, setRecent] = useState<TmdbCacheRecentItem[]>([])
  const [loading, setLoading] = useState(false)

  const fetchAll = useCallback(async () => {
    setLoading(true)
    try {
      const [s, l, r] = await Promise.all([
        tmdbCacheApi.getStats(),
        tmdbCacheApi.getSyncLog({ page: 1, size: 20 }),
        tmdbCacheApi.getRecent({ limit: 12 }),
      ])
      setStats(s)
      setLogs(l.items)
      setRecent(r)
    } catch {
      setStats(MOCK_STATS)
      setLogs(MOCK_LOGS)
      setRecent(MOCK_RECENT)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchAll() }, [fetchAll])

  const s = stats ?? MOCK_STATS

  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">TMDB 캐시 모니터링</h2>
          <p className="text-sm text-muted-foreground mt-1">
            로컬 TMDB 캐시 DB 수집 현황 — 영화 {s.oldest_movie_year ?? "?"}~{s.newest_movie_year ?? "?"}
          </p>
        </div>
        <button
          onClick={fetchAll}
          className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          새로고침
        </button>
      </div>

      {/* KPI 카드 4개 */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={<Film className="w-5 h-5" />}
          label="영화 총 건수"
          value={formatNum(s.total_movies)}
          sub={`어제 +${s.last_24h_movies_added}`}
        />
        <StatCard
          icon={<Tv className="w-5 h-5" />}
          label="TV 총 건수"
          value={formatNum(s.total_tv)}
          sub={`어제 +${s.last_24h_tv_added}`}
        />
        <StatCard
          icon={<Database className="w-5 h-5" />}
          label="전체 합계"
          value={formatNum(s.total_movies + s.total_tv)}
          sub={`${s.oldest_movie_year ?? "-"}~${s.newest_movie_year ?? "-"}`}
        />
        <StatCard
          icon={<Clock className="w-5 h-5" />}
          label="마지막 실행"
          value={s.last_run_at ? formatDate(s.last_run_at) : "-"}
          sub={s.last_run_status ? (STATUS_LABEL[s.last_run_status] ?? s.last_run_status) : "-"}
        />
      </div>

      {/* 7일 바 차트 */}
      <BarChart data={s.last_7d_daily} />

      {/* 동기화 로그 테이블 */}
      <div>
        <h3 className="text-sm font-medium mb-3">동기화 로그</h3>
        <div className="rounded-xl border bg-card shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 border-b">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">소스</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">상태</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground hidden md:table-cell">시작</th>
                <th className="text-right px-4 py-3 font-medium text-muted-foreground">페이지</th>
                <th className="text-right px-4 py-3 font-medium text-muted-foreground">신규</th>
                <th className="text-right px-4 py-3 font-medium text-muted-foreground hidden lg:table-cell">갱신</th>
                <th className="text-right px-4 py-3 font-medium text-muted-foreground hidden lg:table-cell">오류</th>
                <th className="text-right px-4 py-3 font-medium text-muted-foreground hidden xl:table-cell">소요</th>
              </tr>
            </thead>
            <tbody>
              {logs.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-4 py-10 text-center text-muted-foreground">
                    동기화 이력이 없습니다.
                  </td>
                </tr>
              ) : (
                logs.map((log) => (
                  <tr key={log.id} className="border-t hover:bg-muted/30 transition-colors">
                    <td className="px-4 py-3 font-medium">
                      {SOURCE_LABEL[log.source] ?? log.source}
                    </td>
                    <td className="px-4 py-3">
                      <span className="flex items-center gap-1.5">
                        {statusIcon(log.status)}
                        <span className="text-xs">{STATUS_LABEL[log.status] ?? log.status}</span>
                      </span>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground tabular-nums hidden md:table-cell">
                      {formatDate(log.started_at)}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-muted-foreground">
                      {formatNum(log.pages_fetched)}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums font-medium text-green-600 dark:text-green-400">
                      +{formatNum(log.items_inserted)}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-muted-foreground hidden lg:table-cell">
                      {formatNum(log.items_updated)}
                    </td>
                    <td className={`px-4 py-3 text-right tabular-nums hidden lg:table-cell ${log.errors > 0 ? "text-red-500" : "text-muted-foreground"}`}>
                      {log.errors}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-muted-foreground hidden xl:table-cell">
                      {elapsedSec(log.started_at, log.finished_at)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* 최근 수집 항목 그리드 */}
      <div>
        <h3 className="text-sm font-medium mb-3">최근 수집 항목</h3>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
          {recent.map((item) => (
            <a
              key={item.id}
              href={`https://www.themoviedb.org/${item.kind === "movie" ? "movie" : "tv"}/${item.id}`}
              target="_blank"
              rel="noreferrer"
              className="group rounded-lg border bg-card overflow-hidden shadow-sm hover:shadow-md transition-shadow"
            >
              <div className="relative bg-muted aspect-[2/3] overflow-hidden">
                {item.poster_url ? (
                  <Image
                    src={item.poster_url}
                    alt={item.title}
                    fill
                    className="object-cover group-hover:scale-105 transition-transform duration-300"
                    unoptimized
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-muted-foreground">
                    {item.kind === "movie"
                      ? <Film className="w-8 h-8" />
                      : <Tv   className="w-8 h-8" />}
                  </div>
                )}
                <span className={`absolute top-1.5 left-1.5 text-[10px] px-1.5 py-0.5 rounded font-medium ${
                  item.kind === "movie"
                    ? "bg-primary/90 text-primary-foreground"
                    : "bg-blue-500/90 text-white"
                }`}>
                  {item.kind === "movie" ? "영화" : "TV"}
                </span>
              </div>
              <div className="p-2">
                <p className="text-xs font-medium truncate leading-tight">{item.title}</p>
                <p className="text-[10px] text-muted-foreground mt-0.5">
                  {(item.release_date ?? item.first_air_date ?? "").slice(0, 4) || "-"}
                </p>
              </div>
            </a>
          ))}
        </div>
      </div>
    </div>
  )
}
