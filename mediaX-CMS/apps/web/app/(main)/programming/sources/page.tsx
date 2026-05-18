"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { RefreshCw, Database, Film, Tv, Clock, ArrowRight, CheckCircle, XCircle, AlertCircle } from "lucide-react"
import { tmdbCacheApi, kobisApi, kmdbApi, type TmdbCacheStats, type ExternalSourceStats, type TmdbSyncLogItem } from "@/lib/api"

type CombinedSyncLog = TmdbSyncLogItem & { provider: "TMDB" | "KOBIS" | "KMDB" }

// ── Mock ──────────────────────────────────────────────────

const MOCK_COMBINED_LOGS: CombinedSyncLog[] = [
  { id: 2, run_id: "k2",  source: "kobis_daily",       target_year: null, target_date: "2026-05-18", status: "completed", started_at: "2026-05-18T07:00:00+09:00", finished_at: "2026-05-18T07:00:02+09:00", pages_fetched: 1,    items_fetched: 10,      items_inserted: 2,   items_updated: 6,   items_unchanged: 2, errors: 0, provider: "KOBIS" },
  { id: 2, run_id: "km2", source: "kmdb_backfill",      target_year: 2024, target_date: null,          status: "completed", started_at: "2026-05-18T06:00:05+09:00", finished_at: "2026-05-18T06:01:50+09:00", pages_fetched: 7,    items_fetched: 664,     items_inserted: 664, items_updated: 0,   items_unchanged: 0, errors: 0, provider: "KMDB"  },
  { id: 1, run_id: "k1",  source: "kobis_backfill",     target_year: 2025, target_date: null,          status: "completed", started_at: "2026-05-18T06:30:00+09:00", finished_at: "2026-05-18T06:30:10+09:00", pages_fetched: 0,    items_fetched: 0,       items_inserted: 0,   items_updated: 0,   items_unchanged: 0, errors: 0, provider: "KOBIS" },
  { id: 1, run_id: "km1", source: "kmdb_daily",         target_year: null, target_date: "2026-05-18", status: "completed", started_at: "2026-05-18T05:30:00+09:00", finished_at: "2026-05-18T05:30:45+09:00", pages_fetched: 1,    items_fetched: 12,      items_inserted: 8,   items_updated: 4,   items_unchanged: 0, errors: 0, provider: "KMDB"  },
  { id: 4, run_id: "a4",  source: "daily_new_releases", target_year: null, target_date: "2026-05-05", status: "completed", started_at: "2026-05-05T03:45:00+09:00", finished_at: "2026-05-05T03:52:00+09:00", pages_fetched: 4,    items_fetched: 80,      items_inserted: 65,  items_updated: 12,  items_unchanged: 3, errors: 0, provider: "TMDB"  },
  { id: 3, run_id: "a3",  source: "daily_changes",      target_year: null, target_date: "2026-05-05", status: "completed", started_at: "2026-05-05T03:30:00+09:00", finished_at: "2026-05-05T03:44:00+09:00", pages_fetched: 8,    items_fetched: 143,     items_inserted: 0,   items_updated: 143, items_unchanged: 0, errors: 0, provider: "TMDB"  },
  { id: 1, run_id: "a1",  source: "backfill_discover",  target_year: 2024, target_date: null,          status: "completed", started_at: "2026-05-04T10:00:00+09:00", finished_at: "2026-05-04T14:30:00+09:00", pages_fetched: 4240, items_fetched: 847_230, items_inserted: 847_000, items_updated: 0, items_unchanged: 0, errors: 12, provider: "TMDB" },
]

const MOCK_TMDB: TmdbCacheStats = {
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

const MOCK_KOBIS: ExternalSourceStats = {
  total_synced: 12_840, last_run_at: "2026-05-11T05:10:00+09:00",
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

const MOCK_KMDB: ExternalSourceStats = {
  total_synced: 8_412, last_run_at: "2026-05-11T05:30:00+09:00",
  last_run_status: null, last_7d_daily: [],
}

// ── 유틸 ──────────────────────────────────────────────────

const ALL_SOURCE_LABELS: Record<string, string> = {
  daily_changes: "일별 변경", daily_new_releases: "신규 출시", backfill_discover: "전체 백필", manual: "수동",
  kobis_daily: "일별 수집", kobis_backfill: "전체 백필",
  kmdb_daily: "일별 수집", kmdb_backfill: "연도 백필",
}

const SYNC_STATUS_LABEL: Record<string, string> = { completed: "완료", running: "진행중", failed: "실패", partial: "일부완료" }

const PROVIDER_CLASS: Record<string, string> = {
  TMDB:  "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  KOBIS: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
  KMDB:  "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400",
}

function statusIcon(status: string) {
  if (status === "completed") return <CheckCircle className="w-4 h-4 text-green-500" />
  if (status === "running")   return <RefreshCw   className="w-4 h-4 text-blue-500 animate-spin" />
  if (status === "failed")    return <XCircle     className="w-4 h-4 text-red-500" />
  return <AlertCircle className="w-4 h-4 text-amber-500" />
}

function formatDateTime(iso: string | null) {
  if (!iso) return "-"
  const m = iso.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/)
  return m ? `${m[2]}.${m[3]} ${m[4]}:${m[5]}` : iso
}

function formatDate(iso: string | null) {
  if (!iso) return "-"
  const m = iso.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/)
  return m ? `${m[1]}.${m[2]}.${m[3]} ${m[4]}:${m[5]}` : iso
}

function StatusBadge({ status }: { status: string | null }) {
  if (!status) return <span className="text-xs text-muted-foreground">-</span>
  if (status === "completed") return <span className="flex items-center gap-1 text-xs text-green-600 dark:text-green-400"><CheckCircle className="w-3.5 h-3.5" />완료</span>
  if (status === "running")   return <span className="flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400"><RefreshCw className="w-3.5 h-3.5 animate-spin" />진행중</span>
  if (status === "failed")    return <span className="flex items-center gap-1 text-xs text-red-500"><XCircle className="w-3.5 h-3.5" />실패</span>
  return <span className="flex items-center gap-1 text-xs text-amber-500"><AlertCircle className="w-3.5 h-3.5" />{status}</span>
}

function MiniBar({ data, maxVal }: { data: { count: number }[]; maxVal: number }) {
  return (
    <div className="flex items-end gap-0.5 h-8">
      {data.map((d, i) => (
        <div
          key={i}
          className="flex-1 bg-primary/40 rounded-sm transition-all"
          style={{ height: maxVal > 0 ? `${Math.max(4, (d.count / maxVal) * 100)}%` : "4%" }}
        />
      ))}
    </div>
  )
}

// ── 소스 카드 ─────────────────────────────────────────────

function SourceCard({
  name, description, href, total, lastRun, lastStatus, barData, maxBar, accent,
}: {
  name: string
  description: string
  href: string
  total: string
  lastRun: string | null
  lastStatus: string | null
  barData: { count: number }[]
  maxBar: number
  accent: string
}) {
  return (
    <Link href={href} className={`group rounded-xl border bg-card p-5 shadow-sm hover:shadow-md transition-shadow flex flex-col gap-4 ${accent}`}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs text-muted-foreground">{description}</p>
          <h3 className="text-lg font-semibold mt-0.5">{name}</h3>
        </div>
        <ArrowRight className="w-4 h-4 text-muted-foreground group-hover:text-foreground transition-colors mt-1" />
      </div>

      <div className="flex items-end justify-between gap-4">
        <div>
          <p className="text-3xl font-bold tabular-nums tracking-tight">{total}</p>
          <p className="text-xs text-muted-foreground mt-1">총 캐시 건수</p>
        </div>
        {barData.length > 0 && (
          <div className="flex-1 max-w-[100px]">
            <MiniBar data={barData} maxVal={maxBar} />
            <p className="text-[10px] text-muted-foreground mt-1 text-right">최근 {barData.length}일</p>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between text-xs text-muted-foreground border-t pt-3 mt-auto">
        <span>{lastRun ? `마지막: ${formatDate(lastRun)}` : "수집 이력 없음"}</span>
        <StatusBadge status={lastStatus} />
      </div>
    </Link>
  )
}

// ── 메인 ─────────────────────────────────────────────────

export default function SourcesDashboard() {
  const [tmdb,     setTmdb]     = useState<TmdbCacheStats>(MOCK_TMDB)
  const [kobis,    setKobis]    = useState<ExternalSourceStats>(MOCK_KOBIS)
  const [kmdb,     setKmdb]     = useState<ExternalSourceStats>(MOCK_KMDB)
  const [syncLogs, setSyncLogs] = useState<CombinedSyncLog[]>(MOCK_COMBINED_LOGS)
  const [loading,  setLoading]  = useState(false)

  const fetchAll = async () => {
    setLoading(true)
    try {
      const results = await Promise.allSettled([
        tmdbCacheApi.getStats(),
        kobisApi.getStats(),
        kmdbApi.getStats(),
        tmdbCacheApi.getSyncLog({ page: 1, size: 5 }),
        kobisApi.getSyncLog({ page: 1, size: 5 }),
        kmdbApi.getSyncLog({ page: 1, size: 5 }),
      ])
      const [tr, kr, mr, tl, kl, ml] = results
      if (tr.status === "fulfilled") { const t = tr.value; if (t.total_movies + t.total_tv > 0) setTmdb(t) }
      if (kr.status === "fulfilled") { const k = kr.value; if (k.total_synced > 0) setKobis(k) }
      if (mr.status === "fulfilled") { const m = mr.value; if (m.total_synced > 0) setKmdb(m) }
      const combined: CombinedSyncLog[] = [
        ...(tl.status === "fulfilled" ? tl.value.items.map(l => ({ ...l, provider: "TMDB" as const })) : []),
        ...(kl.status === "fulfilled" ? kl.value.items.map(l => ({ ...l, provider: "KOBIS" as const })) : []),
        ...(ml.status === "fulfilled" ? ml.value.items.map(l => ({ ...l, provider: "KMDB" as const })) : []),
      ].sort((a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime()).slice(0, 15)
      if (combined.length > 0) setSyncLogs(combined)
    } catch {
      // Mock 유지
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchAll() }, [])

  const tmdbTotal = tmdb.total_movies + tmdb.total_tv
  const tmdbBarData = tmdb.last_7d_daily.map((d) => ({ count: d.movies + d.tv }))
  const tmdbMaxBar  = Math.max(...tmdbBarData.map((d) => d.count), 1)
  const kobisMaxBar = Math.max(...kobis.last_7d_daily.map((d) => d.count), 1)

  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">외부 소스</h2>
          <p className="text-sm text-muted-foreground mt-1">TMDB · KOBIS · KMDB 캐시 현황 한눈에</p>
        </div>
        <button onClick={fetchAll} className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors">
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />새로고침
        </button>
      </div>

      {/* 소스 카드 그리드 */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {/* TMDB 탐색 */}
        <Link href="/programming/sources/tmdb" className="group rounded-xl border bg-card p-5 shadow-sm hover:shadow-md transition-shadow flex flex-col gap-4">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-xs text-muted-foreground">매핑 콘텐츠 탐색</p>
              <h3 className="text-lg font-semibold mt-0.5">TMDB 탐색</h3>
            </div>
            <ArrowRight className="w-4 h-4 text-muted-foreground group-hover:text-foreground transition-colors mt-1" />
          </div>
          <div className="flex items-end gap-4">
            <div className="grid grid-cols-2 gap-2 flex-1">
              <div className="rounded-lg bg-muted/50 p-3">
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground mb-1"><Film className="w-3.5 h-3.5" />영화</div>
                <p className="text-xl font-bold tabular-nums">{tmdb.total_movies.toLocaleString()}</p>
              </div>
              <div className="rounded-lg bg-muted/50 p-3">
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground mb-1"><Tv className="w-3.5 h-3.5" />TV</div>
                <p className="text-xl font-bold tabular-nums">{tmdb.total_tv.toLocaleString()}</p>
              </div>
            </div>
            <div className="w-[80px] shrink-0">
              <MiniBar data={tmdbBarData} maxVal={tmdbMaxBar} />
              <p className="text-[10px] text-muted-foreground mt-1 text-right">최근 7일</p>
            </div>
          </div>
          <div className="flex items-center justify-between text-xs text-muted-foreground border-t pt-3 mt-auto">
            <span>{`${tmdb.oldest_movie_year ?? "?"}~${tmdb.newest_movie_year ?? "?"}`}</span>
            <span className="flex items-center gap-1"><Database className="w-3.5 h-3.5" />캐시 DB</span>
          </div>
        </Link>

        {/* KOBIS */}
        <SourceCard
          name="KOBIS"
          description="한국영화진흥위원회"
          href="/programming/sources/kobis"
          total={kobis.total_synced.toLocaleString()}
          lastRun={kobis.last_run_at}
          lastStatus={kobis.last_run_status}
          barData={kobis.last_7d_daily}
          maxBar={kobisMaxBar}
          accent=""
        />

        {/* KMDB */}
        <SourceCard
          name="KMDB"
          description="한국영상자료원"
          href="/programming/sources/kmdb"
          total={kmdb.total_synced.toLocaleString()}
          lastRun={kmdb.last_run_at}
          lastStatus={kmdb.last_run_status}
          barData={[]}
          maxBar={1}
          accent=""
        />
      </div>

      {/* 통합 동기화 로그 */}
      <div className="rounded-xl border bg-card shadow-sm overflow-hidden">
        <div className="px-5 py-3.5 border-b">
          <h3 className="text-sm font-semibold">동기화 로그</h3>
        </div>
        <div className="overflow-y-auto max-h-[260px]">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 sticky top-0 z-10">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">소스</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">작업</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">상태</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground hidden md:table-cell">시작</th>
                <th className="text-right px-4 py-3 font-medium text-muted-foreground">신규</th>
                <th className="text-right px-4 py-3 font-medium text-muted-foreground hidden lg:table-cell">갱신</th>
                <th className="text-right px-4 py-3 font-medium text-muted-foreground hidden lg:table-cell">오류</th>
              </tr>
            </thead>
            <tbody>
              {syncLogs.length === 0 ? (
                <tr><td colSpan={7} className="px-4 py-10 text-center text-muted-foreground">동기화 이력이 없습니다.</td></tr>
              ) : syncLogs.map((log, idx) => (
                <tr key={`${log.provider}-${log.id}-${idx}`} className="border-t hover:bg-muted/30 transition-colors">
                  <td className="px-4 py-3">
                    <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${PROVIDER_CLASS[log.provider]}`}>
                      {log.provider}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground text-xs">{ALL_SOURCE_LABELS[log.source] ?? log.source}</td>
                  <td className="px-4 py-3">
                    <span className="flex items-center gap-1.5">
                      {statusIcon(log.status)}
                      <span className="text-xs">{SYNC_STATUS_LABEL[log.status] ?? log.status}</span>
                    </span>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground tabular-nums hidden md:table-cell text-xs">{formatDateTime(log.started_at)}</td>
                  <td className="px-4 py-3 text-right tabular-nums font-medium text-green-600 dark:text-green-400 text-xs">+{log.items_inserted.toLocaleString()}</td>
                  <td className="px-4 py-3 text-right tabular-nums text-muted-foreground hidden lg:table-cell text-xs">{log.items_updated.toLocaleString()}</td>
                  <td className={`px-4 py-3 text-right tabular-nums hidden lg:table-cell text-xs ${log.errors > 0 ? "text-red-500" : "text-muted-foreground"}`}>{log.errors}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 수집 현황 요약 테이블 */}
      <div className="rounded-xl border bg-card shadow-sm overflow-hidden">
        <div className="px-5 py-3.5 border-b">
          <h3 className="text-sm font-semibold">소스별 현황 요약</h3>
        </div>
        <table className="w-full text-sm">
          <thead className="bg-muted/50">
            <tr>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">소스</th>
              <th className="text-right px-4 py-3 font-medium text-muted-foreground">총 건수</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground hidden md:table-cell">마지막 수집</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">상태</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground hidden lg:table-cell">수집 주기</th>
            </tr>
          </thead>
          <tbody>
            {[
              { name: "TMDB (영화)", total: tmdb.total_movies, lastRun: tmdb.last_run_at, status: tmdb.last_run_status, schedule: "매일 02:00 KST" },
              { name: "TMDB (TV)",   total: tmdb.total_tv,     lastRun: tmdb.last_run_at, status: tmdb.last_run_status, schedule: "매일 02:00 KST" },
              { name: "KOBIS",       total: kobis.total_synced, lastRun: kobis.last_run_at, status: kobis.last_run_status, schedule: "매일 05:00 KST" },
              { name: "KMDB",        total: kmdb.total_synced,  lastRun: kmdb.last_run_at,  status: kmdb.last_run_status,  schedule: "매일 05:30 KST" },
            ].map((row) => (
              <tr key={row.name} className="border-t hover:bg-muted/30 transition-colors">
                <td className="px-4 py-3 font-medium">{row.name}</td>
                <td className="px-4 py-3 text-right tabular-nums">{row.total.toLocaleString()}</td>
                <td className="px-4 py-3 text-muted-foreground hidden md:table-cell tabular-nums">{formatDate(row.lastRun)}</td>
                <td className="px-4 py-3"><StatusBadge status={row.status} /></td>
                <td className="px-4 py-3 text-muted-foreground hidden lg:table-cell">{row.schedule}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
