"use client"

import { useEffect, useState, useCallback } from "react"
import { RefreshCw, Search, X, Clock, Database, Film } from "lucide-react"
import { kmdbApi, type ExternalSourceStats, type ExternalSourceItem } from "@/lib/api"

// ── Mock 데이터 ───────────────────────────────────────────

const MOCK_STATS: ExternalSourceStats = {
  total_synced: 8_412,
  last_run_at: "2026-05-11T05:30:00+09:00",
  last_run_status: null,
  last_7d_daily: [],
}

const MOCK_ITEMS: ExternalSourceItem[] = [
  { id: 1, content_id: 10, source_type: "kmdb", external_id: "K123456", title_on_source: "파묘",      match_confidence: 0.96, matched_at: "2026-05-11T05:30:00+09:00", created_at: "2026-05-09T12:00:00+09:00" },
  { id: 2, content_id: 11, source_type: "kmdb", external_id: "K123457", title_on_source: "서울의 봄", match_confidence: 0.93, matched_at: "2026-05-11T05:30:00+09:00", created_at: "2026-05-09T12:00:00+09:00" },
  { id: 3, content_id: null, source_type: "kmdb", external_id: "K123458", title_on_source: "클래식 영화", match_confidence: null, matched_at: null, created_at: "2026-05-09T12:00:00+09:00" },
]

// ── 유틸 ──────────────────────────────────────────────────

function formatDate(iso: string | null) {
  if (!iso) return "-"
  const m = iso.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/)
  return m ? `${m[2]}.${m[3]} ${m[4]}:${m[5]}` : iso
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

export default function KmdbPage() {
  const [stats,   setStats]   = useState<ExternalSourceStats>(MOCK_STATS)
  const [items,   setItems]   = useState<ExternalSourceItem[]>(MOCK_ITEMS)
  const [loading, setLoading] = useState(false)
  const [search,  setSearch]  = useState("")
  const [applied, setApplied] = useState("")

  const fetchAll = useCallback(async (title?: string) => {
    setLoading(true)
    try {
      const [s, i] = await Promise.all([
        kmdbApi.getStats(),
        kmdbApi.search({ title: title || undefined, size: 20 }),
      ])
      if (s.total_synced > 0) {
        setStats(s)
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
          <h2 className="text-2xl font-semibold tracking-tight">KMDB</h2>
          <p className="text-sm text-muted-foreground mt-1">한국영상자료원 캐시 현황</p>
        </div>
        <button onClick={() => fetchAll(applied)} className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors">
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />새로고침
        </button>
      </div>

      {/* KPI */}
      <div className="grid grid-cols-2 gap-4">
        <StatCard icon={<Database className="w-5 h-5" />} label="캐시 총 건수" value={stats.total_synced.toLocaleString()} />
        <StatCard icon={<Clock    className="w-5 h-5" />} label="마지막 수집" value={formatDate(stats.last_run_at)} sub="QuotaManager 500건/일 관리" />
      </div>

      {/* 안내 배너 */}
      <div className="rounded-xl border border-amber-200 dark:border-amber-800/40 bg-amber-50 dark:bg-amber-900/10 px-4 py-3 flex items-start gap-3">
        <Film className="w-4 h-4 text-amber-600 dark:text-amber-400 mt-0.5 shrink-0" />
        <div className="text-sm text-amber-700 dark:text-amber-300">
          <span className="font-medium">일일 쿼터 500건</span> — KMDB는 별도 sync 로그 없이 Discovery Beat(05:30 KST)가 수집 후 external_meta_sources에 직접 적재합니다.
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
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">KMDB DOCID</th>
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
