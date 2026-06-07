"use client"

import { useEffect, useState, useCallback } from "react"
import { RefreshCw, Search, X, CheckCircle, XCircle, AlertCircle, Clock, Database, ChevronLeft, ChevronRight, Film, ArrowLeft } from "lucide-react"
import Image from "next/image"
import Link from "next/link"
import {
  kmdbApi,
  type ExternalSourceStats,
  type KmdbCacheItem,
  type TmdbSyncLogItem,
} from "@/lib/api"

// ── Mock 데이터 ───────────────────────────────────────────

const MOCK_STATS: ExternalSourceStats = {
  total_synced: 664,
  last_run_at: "2026-05-18T06:00:00+09:00",
  last_run_status: "completed",
  last_7d_daily: [
    { date: "2026-05-12", count: 0,   errors: 0 },
    { date: "2026-05-13", count: 0,   errors: 0 },
    { date: "2026-05-14", count: 0,   errors: 0 },
    { date: "2026-05-15", count: 0,   errors: 0 },
    { date: "2026-05-16", count: 0,   errors: 0 },
    { date: "2026-05-17", count: 0,   errors: 0 },
    { date: "2026-05-18", count: 664, errors: 0 },
  ],
}

const MOCK_LOGS: TmdbSyncLogItem[] = [
  { id: 2, run_id: "km2", source: "kmdb_backfill", target_year: 2024, target_date: null, status: "completed", started_at: "2026-05-18T06:00:05+09:00", finished_at: "2026-05-18T06:01:50+09:00", pages_fetched: 7, items_fetched: 664, items_inserted: 664, items_updated: 0, items_unchanged: 0, errors: 0 },
  { id: 1, run_id: "km1", source: "kmdb_daily",    target_year: null, target_date: "2026-05-18", status: "completed", started_at: "2026-05-18T05:30:00+09:00", finished_at: "2026-05-18T05:30:45+09:00", pages_fetched: 1, items_fetched: 12, items_inserted: 8, items_updated: 4, items_unchanged: 0, errors: 0 },
]

const MOCK_CACHE: KmdbCacheItem[] = [
  { docid: "2024K00001", title: "파묘",      title_eng: "Exhuma",        prod_year: 2024, genre: "공포,미스터리", nation: "한국", poster_url: null, first_fetched_at: "2026-05-18T06:00:10+09:00", last_fetched_at: "2026-05-18T06:00:10+09:00" },
  { docid: "2024K00002", title: "범죄도시4", title_eng: "The Roundup 4", prod_year: 2024, genre: "액션,범죄",       nation: "한국", poster_url: null, first_fetched_at: "2026-05-18T06:00:11+09:00", last_fetched_at: "2026-05-18T06:00:11+09:00" },
  { docid: "2024K00003", title: "서울의 봄", title_eng: null,            prod_year: 2024, genre: "드라마,역사",     nation: "한국", poster_url: null, first_fetched_at: "2026-05-18T06:00:12+09:00", last_fetched_at: "2026-05-18T06:00:12+09:00" },
]

// ── 상수 ──────────────────────────────────────────────────

const SOURCE_LABEL: Record<string, string> = {
  kmdb_daily: "일별 수집", kmdb_backfill: "연도 백필",
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

function KmdbDetailPanel({ item, onClose }: { item: KmdbCacheItem; onClose: () => void }) {
  const fields: Array<[string, string | null]> = [
    ["영문제목", item.title_eng],
    ["DOCID",    item.docid],
    ["제작연도", item.prod_year != null ? String(item.prod_year) : null],
    ["장르",     item.genre],
    ["국가",     item.nation],
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
          {item.poster_url ? (
            <Image src={item.poster_url} alt={item.title} width={120} height={180} className="rounded object-cover border border-border" unoptimized />
          ) : (
            <div className="w-[120px] h-[180px] rounded border border-dashed border-border flex items-center justify-center text-muted-foreground">
              <Film className="w-8 h-8" />
            </div>
          )}
        </div>
        <div className="flex justify-center">
          <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400">
            KMDB 영화
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

const CACHE_SIZE = 50

function buildPages(current: number, total: number): (number | "…")[] {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1)
  const pages: (number | "…")[] = [1]
  if (current > 3) pages.push("…")
  for (let p = Math.max(2, current - 1); p <= Math.min(total - 1, current + 1); p++) pages.push(p)
  if (current < total - 2) pages.push("…")
  pages.push(total)
  return pages
}

export default function KmdbPage() {
  const [stats,   setStats]   = useState<ExternalSourceStats>(MOCK_STATS)
  const [logs,    setLogs]    = useState<TmdbSyncLogItem[]>(MOCK_LOGS)
  const [cache,   setCache]   = useState<KmdbCacheItem[]>(MOCK_CACHE)
  const [cacheTotal, setCacheTotal] = useState(MOCK_CACHE.length)
  const [cachePage,  setCachePage]  = useState(1)
  const [cacheSearch, setCacheSearch] = useState("")
  const [applied, setApplied] = useState("")
  const [selectedItem, setSelectedItem] = useState<KmdbCacheItem | null>(null)

  const fetchStats = useCallback(async () => {
    try {
      const [s, l] = await Promise.all([
        kmdbApi.getStats(),
        kmdbApi.getSyncLog({ page: 1, size: 20 }),
      ])
      if (s.total_synced > 0) { setStats(s); setLogs(l.items) }
    } catch { /* Mock 유지 */ }
  }, [])

  const fetchCache = useCallback(async (p: number, title: string) => {
    try {
      const c = await kmdbApi.getCache({ title: title || undefined, page: p, size: CACHE_SIZE })
      setCache(c.items)
      setCacheTotal(c.total)
    } catch { /* Mock 유지 */ }
  }, [])

  useEffect(() => { fetchStats() }, [fetchStats])
  useEffect(() => { fetchCache(cachePage, applied) }, [cachePage, applied, fetchCache])

  function applyCacheSearch() { setApplied(cacheSearch); setCachePage(1) }
  function clearSearch() { setCacheSearch(""); setApplied(""); setCachePage(1) }

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
          <h2 className="text-2xl font-semibold tracking-tight">KMDB</h2>
          <p className="text-sm text-muted-foreground mt-1">한국영상자료원 — 캐시 현황</p>
        </div>
        <button onClick={() => { fetchStats(); fetchCache(cachePage, applied) }}
          className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors">
          <RefreshCw className="w-4 h-4" />새로고침
        </button>
      </div>

      {/* KPI */}
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        <StatCard icon={<Database    className="w-5 h-5" />} label="캐시 총 건수"   value={stats.total_synced.toLocaleString()} />
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
                <th className="text-left px-4 py-3 font-medium text-muted-foreground hidden md:table-cell">대상 연도</th>
                <th className="text-right px-4 py-3 font-medium text-muted-foreground">신규</th>
                <th className="text-right px-4 py-3 font-medium text-muted-foreground hidden lg:table-cell">오류</th>
                <th className="text-right px-4 py-3 font-medium text-muted-foreground hidden xl:table-cell">소요</th>
              </tr>
            </thead>
            <tbody>
              {logs.length === 0 ? (
                <tr><td colSpan={7} className="px-4 py-10 text-center text-muted-foreground">동기화 이력이 없습니다.</td></tr>
              ) : logs.map((log) => (
                <tr key={log.id} className="border-t hover:bg-muted/30 transition-colors">
                  <td className="px-4 py-3 font-medium">{SOURCE_LABEL[log.source] ?? log.source}</td>
                  <td className="px-4 py-3"><span className="flex items-center gap-1.5">{statusIcon(log.status)}<span className="text-xs">{SYNC_STATUS_LABEL[log.status] ?? log.status}</span></span></td>
                  <td className="px-4 py-3 text-muted-foreground tabular-nums hidden md:table-cell">{formatDate(log.started_at)}</td>
                  <td className="px-4 py-3 text-muted-foreground tabular-nums hidden md:table-cell">{log.target_year ?? "-"}</td>
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
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-medium">KMDB 로컬 캐시 검색</h3>
          <span className="text-xs text-muted-foreground">총 {cacheTotal.toLocaleString()}건</span>
        </div>
        <div className="flex gap-2 mb-3">
          <div className="relative flex-1 max-w-xs">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <input value={cacheSearch} onChange={(e) => setCacheSearch(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && applyCacheSearch()}
              placeholder="제목 검색..."
              className="w-full pl-9 pr-8 py-2 text-sm rounded-md border bg-background focus:outline-none focus:ring-2 focus:ring-ring" />
            {cacheSearch && (
              <button onClick={clearSearch}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
                <X className="w-4 h-4" />
              </button>
            )}
          </div>
          <button onClick={applyCacheSearch}
            className="px-4 py-2 text-sm rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors">검색</button>
        </div>
        <div className={`grid gap-4 items-start ${selectedItem ? "xl:grid-cols-[1fr_280px]" : ""}`}>
          <div className="space-y-3">
            <div className="rounded-xl border bg-card shadow-sm overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-muted/50 border-b">
                  <tr>
                    <th className="text-left px-4 py-3 font-medium text-muted-foreground">DOCID</th>
                    <th className="text-left px-4 py-3 font-medium text-muted-foreground">제목</th>
                    <th className="text-left px-4 py-3 font-medium text-muted-foreground hidden md:table-cell">제작연도</th>
                    <th className="text-left px-4 py-3 font-medium text-muted-foreground hidden lg:table-cell">장르</th>
                    <th className="text-left px-4 py-3 font-medium text-muted-foreground hidden lg:table-cell">국가</th>
                    <th className="text-left px-4 py-3 font-medium text-muted-foreground hidden xl:table-cell">마지막 수집</th>
                  </tr>
                </thead>
                <tbody>
                  {cache.length === 0 ? (
                    <tr><td colSpan={6} className="px-4 py-10 text-center text-muted-foreground">결과가 없습니다.</td></tr>
                  ) : cache.map((item) => {
                    const isSelected = selectedItem?.docid === item.docid
                    return (
                      <tr
                        key={item.docid}
                        onClick={() => setSelectedItem(isSelected ? null : item)}
                        className={`border-t hover:bg-muted/30 transition-colors cursor-pointer ${isSelected ? "bg-primary/5 border-l-2 border-l-primary" : ""}`}
                      >
                        <td className="px-4 py-3 tabular-nums text-muted-foreground font-mono text-xs">{item.docid}</td>
                        <td className="px-4 py-3">
                          <span className="font-medium">{item.title}</span>
                          {item.title_eng && <span className="ml-1.5 text-xs text-muted-foreground">{item.title_eng}</span>}
                        </td>
                        <td className="px-4 py-3 text-muted-foreground tabular-nums hidden md:table-cell">{item.prod_year ?? "-"}</td>
                        <td className="px-4 py-3 text-muted-foreground hidden lg:table-cell">{item.genre ?? "-"}</td>
                        <td className="px-4 py-3 text-muted-foreground hidden lg:table-cell">{item.nation ?? "-"}</td>
                        <td className="px-4 py-3 text-muted-foreground tabular-nums hidden xl:table-cell">{formatDate(item.last_fetched_at)}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            {/* 페이지네이션 */}
            {cacheTotal > CACHE_SIZE && (() => {
              const totalPages = Math.ceil(cacheTotal / CACHE_SIZE)
              return (
                <div className="flex items-center justify-center gap-1">
                  <button onClick={() => setCachePage((p) => Math.max(1, p - 1))} disabled={cachePage === 1}
                    className="p-1.5 rounded-md hover:bg-muted disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
                    <ChevronLeft className="w-4 h-4" />
                  </button>
                  {buildPages(cachePage, totalPages).map((p, i) =>
                    p === "…"
                      ? <span key={`ellipsis-${i}`} className="px-1.5 text-muted-foreground text-sm">…</span>
                      : <button key={p} onClick={() => setCachePage(p)}
                          className={`min-w-[32px] h-8 rounded-md text-sm font-medium transition-colors ${cachePage === p ? "bg-primary text-primary-foreground" : "hover:bg-muted"}`}>
                          {p}
                        </button>
                  )}
                  <button onClick={() => setCachePage((p) => Math.min(totalPages, p + 1))} disabled={cachePage === totalPages}
                    className="p-1.5 rounded-md hover:bg-muted disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
              )
            })()}
          </div>

          {selectedItem && <KmdbDetailPanel item={selectedItem} onClose={() => setSelectedItem(null)} />}
        </div>
      </div>
    </div>
  )
}
