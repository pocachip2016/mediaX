"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { RefreshCw, Database, Film, Tv, Clock, ArrowRight, CheckCircle, XCircle, AlertCircle } from "lucide-react"
import { tmdbCacheApi, kobisApi, kmdbApi, type TmdbCacheStats, type ExternalSourceStats } from "@/lib/api"

// ── Mock ──────────────────────────────────────────────────

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
  const [tmdb,    setTmdb]    = useState<TmdbCacheStats>(MOCK_TMDB)
  const [kobis,   setKobis]   = useState<ExternalSourceStats>(MOCK_KOBIS)
  const [kmdb,    setKmdb]    = useState<ExternalSourceStats>(MOCK_KMDB)
  const [loading, setLoading] = useState(false)

  const fetchAll = async () => {
    setLoading(true)
    try {
      const [t, k, m] = await Promise.all([
        tmdbCacheApi.getStats(),
        kobisApi.getStats(),
        kmdbApi.getStats(),
      ])
      setTmdb(t)
      setKobis(k)
      setKmdb(m)
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
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        {/* TMDB 영화/TV 합산 */}
        <SourceCard
          name="TMDB"
          description="The Movie Database"
          href="/programming/sources/tmdb-sync"
          total={tmdbTotal.toLocaleString()}
          lastRun={tmdb.last_run_at}
          lastStatus={tmdb.last_run_status}
          barData={tmdbBarData}
          maxBar={tmdbMaxBar}
          accent=""
        />

        {/* TMDB 탐색 */}
        <Link href="/programming/sources/tmdb" className="group rounded-xl border bg-card p-5 shadow-sm hover:shadow-md transition-shadow flex flex-col gap-4">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-xs text-muted-foreground">매핑 콘텐츠 탐색</p>
              <h3 className="text-lg font-semibold mt-0.5">TMDB 탐색</h3>
            </div>
            <ArrowRight className="w-4 h-4 text-muted-foreground group-hover:text-foreground transition-colors mt-1" />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div className="rounded-lg bg-muted/50 p-3">
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground mb-1"><Film className="w-3.5 h-3.5" />영화</div>
              <p className="text-xl font-bold tabular-nums">{tmdb.total_movies.toLocaleString()}</p>
            </div>
            <div className="rounded-lg bg-muted/50 p-3">
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground mb-1"><Tv className="w-3.5 h-3.5" />TV</div>
              <p className="text-xl font-bold tabular-nums">{tmdb.total_tv.toLocaleString()}</p>
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
