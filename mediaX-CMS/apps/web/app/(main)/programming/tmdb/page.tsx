"use client"

import { useEffect, useState, useCallback } from "react"
import { useRouter } from "next/navigation"
import { Search, X, ChevronLeft, ChevronRight, RefreshCw, Film, Tv, Star } from "lucide-react"
import { tmdbApi, type TmdbSyncedItem, type ContentStatus } from "@/lib/api"
import Image from "next/image"

// ── Mock 데이터 ───────────────────────────────────────────

const MOCK_ITEMS: TmdbSyncedItem[] = [
  { content_id: 1, title: "기생충", original_title: "Parasite", content_type: "movie", status: "approved", production_year: 2019, cp_name: "CJ ENM", tmdb_id: "496243", poster_url: "https://image.tmdb.org/t/p/w300/7IiTTgloJzvGI1TAYymCfbfl3vT.jpg", match_confidence: 0.98, matched_at: "2026-04-13T10:00:00", quality_score: 96 },
  { content_id: 2, title: "오징어 게임", original_title: "Squid Game", content_type: "series", status: "approved", production_year: 2021, cp_name: "넷플릭스", tmdb_id: "93405", poster_url: "https://image.tmdb.org/t/p/w300/dDlEmu3EZ0Pgg93K2SVNLCjCSvE.jpg", match_confidence: 0.97, matched_at: "2026-04-13T10:01:00", quality_score: 93 },
  { content_id: 3, title: "서울의 봄", original_title: "12.12: The Day", content_type: "movie", status: "approved", production_year: 2023, cp_name: "플러스엠엔터테인먼트", tmdb_id: "1165227", poster_url: null, match_confidence: 0.95, matched_at: "2026-04-13T10:02:00", quality_score: 92 },
  { content_id: 4, title: "이상한 변호사 우영우", original_title: "Extraordinary Attorney Woo", content_type: "series", status: "approved", production_year: 2022, cp_name: "에이스토리", tmdb_id: "197067", poster_url: "https://image.tmdb.org/t/p/w300/8Ovm3mz8BgclsOGQMeYtrxMbJGg.jpg", match_confidence: 0.96, matched_at: "2026-04-13T10:03:00", quality_score: 90 },
]

// ── 상수 ──────────────────────────────────────────────────

const STATUS_LABEL: Record<ContentStatus, string> = {
  waiting: "대기",
  processing: "처리중",
  staging: "검토대기",
  review: "검수중",
  approved: "완료",
  rejected: "반려",
}

const STATUS_CLASS: Record<ContentStatus, string> = {
  waiting:    "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400",
  processing: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  staging:    "bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-400",
  review:     "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
  approved:   "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
  rejected:   "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
}

function qualityColor(score: number | null) {
  if (score === null) return "text-muted-foreground"
  if (score >= 90) return "text-green-600 dark:text-green-400"
  if (score >= 70) return "text-amber-600 dark:text-amber-400"
  return "text-red-600 dark:text-red-400"
}

function formatDate(iso: string | null) {
  if (!iso) return "-"
  return new Date(iso).toLocaleDateString("ko-KR", { year: "numeric", month: "2-digit", day: "2-digit" })
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

// ── 컴포넌트 ───────────────────────────────────────────────

export default function TmdbPage() {
  const router = useRouter()

  const [search, setSearch] = useState("")
  const [appliedSearch, setAppliedSearch] = useState("")
  const [typeFilter, setTypeFilter] = useState<"" | "movie" | "series">("")
  const [items, setItems] = useState<TmdbSyncedItem[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const SIZE = 20

  const fetchData = useCallback(async (p: number, s: string, t: string) => {
    setLoading(true)
    try {
      const data = await tmdbApi.list({
        search: s || undefined,
        content_type: t || undefined,
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

  useEffect(() => {
    fetchData(page, appliedSearch, typeFilter)
  }, [page, appliedSearch, typeFilter, fetchData])

  function applySearch() {
    setAppliedSearch(search)
    setPage(1)
  }

  function clearSearch() {
    setSearch("")
    setAppliedSearch("")
    setPage(1)
  }

  const totalPages = Math.max(1, Math.ceil(total / SIZE))

  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">TMDB 탐색</h2>
          <p className="text-sm text-muted-foreground mt-1">
            TMDB에서 매핑된 콘텐츠 목록 ·{" "}
            <span className="font-medium text-foreground">{total.toLocaleString()}</span>건
          </p>
        </div>
        <button
          onClick={() => fetchData(page, appliedSearch, typeFilter)}
          className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          새로고침
        </button>
      </div>

      {/* 검색 / 필터 */}
      <div className="flex flex-wrap gap-2">
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
            <button
              onClick={clearSearch}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        {(["", "movie", "series"] as const).map((t) => (
          <button
            key={t}
            onClick={() => { setTypeFilter(t); setPage(1) }}
            className={`flex items-center gap-1.5 px-3 py-2 text-sm rounded-md border transition-colors ${
              typeFilter === t
                ? "bg-primary text-primary-foreground border-primary"
                : "bg-background hover:bg-muted border-border"
            }`}
          >
            {t === "" && "전체"}
            {t === "movie" && <><Film className="w-3.5 h-3.5" />영화</>}
            {t === "series" && <><Tv className="w-3.5 h-3.5" />시리즈</>}
          </button>
        ))}

        <button
          onClick={applySearch}
          className="px-4 py-2 text-sm rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          검색
        </button>
      </div>

      {/* 목록 테이블 */}
      <div className="rounded-xl border bg-card shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 border-b">
            <tr>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground w-12">#</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">콘텐츠</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground hidden sm:table-cell">유형</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground hidden md:table-cell">CP사</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground hidden lg:table-cell">TMDB ID</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground hidden lg:table-cell">신뢰도</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground hidden md:table-cell">품질</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">상태</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground hidden xl:table-cell">매핑일</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={9} className="px-4 py-12 text-center text-muted-foreground">
                  <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2" />
                  불러오는 중...
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={9} className="px-4 py-12 text-center text-muted-foreground">
                  TMDB 매핑된 콘텐츠가 없습니다.
                </td>
              </tr>
            ) : (
              items.map((item, idx) => (
                <tr
                  key={item.content_id}
                  onClick={() => router.push(`/programming/contents/${item.content_id}`)}
                  className="border-t hover:bg-muted/40 cursor-pointer transition-colors"
                >
                  {/* 번호 */}
                  <td className="px-4 py-3 text-muted-foreground tabular-nums">
                    {(page - 1) * SIZE + idx + 1}
                  </td>

                  {/* 포스터 + 제목 */}
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <div
                        className="rounded overflow-hidden bg-muted shrink-0 relative"
                        style={{ width: 36, height: 52 }}
                      >
                        {item.poster_url ? (
                          <Image
                            src={item.poster_url}
                            alt={item.title}
                            fill
                            className="object-cover"
                            unoptimized
                          />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center text-muted-foreground">
                            {item.content_type === "movie"
                              ? <Film className="w-4 h-4" />
                              : <Tv className="w-4 h-4" />}
                          </div>
                        )}
                      </div>
                      <div className="min-w-0">
                        <p className="font-medium truncate">{item.title}</p>
                        {item.original_title && (
                          <p className="text-xs text-muted-foreground truncate">{item.original_title}</p>
                        )}
                        {item.production_year && (
                          <p className="text-xs text-muted-foreground">{item.production_year}</p>
                        )}
                      </div>
                    </div>
                  </td>

                  {/* 유형 */}
                  <td className="px-4 py-3 hidden sm:table-cell">
                    <span className="flex items-center gap-1 text-muted-foreground">
                      {item.content_type === "movie"
                        ? <><Film className="w-3.5 h-3.5" />영화</>
                        : <><Tv className="w-3.5 h-3.5" />시리즈</>}
                    </span>
                  </td>

                  {/* CP사 */}
                  <td className="px-4 py-3 text-muted-foreground hidden md:table-cell">
                    <span className="truncate block max-w-[120px]">{item.cp_name ?? "-"}</span>
                  </td>

                  {/* TMDB ID */}
                  <td className="px-4 py-3 hidden lg:table-cell">
                    <a
                      href={`https://www.themoviedb.org/${item.content_type === "movie" ? "movie" : "tv"}/${item.tmdb_id}`}
                      target="_blank"
                      rel="noreferrer"
                      onClick={(e) => e.stopPropagation()}
                      className="flex items-center gap-1 text-blue-600 dark:text-blue-400 hover:underline tabular-nums"
                    >
                      <Star className="w-3 h-3" />
                      {item.tmdb_id}
                    </a>
                  </td>

                  {/* 신뢰도 */}
                  <td className="px-4 py-3 hidden lg:table-cell tabular-nums text-muted-foreground">
                    {item.match_confidence !== null
                      ? `${(item.match_confidence * 100).toFixed(0)}%`
                      : "-"}
                  </td>

                  {/* 품질 */}
                  <td className={`px-4 py-3 hidden md:table-cell font-medium tabular-nums ${qualityColor(item.quality_score)}`}>
                    {item.quality_score !== null ? item.quality_score.toFixed(1) : "-"}
                  </td>

                  {/* 상태 */}
                  <td className="px-4 py-3">
                    <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_CLASS[item.status]}`}>
                      {STATUS_LABEL[item.status]}
                    </span>
                  </td>

                  {/* 매핑일 */}
                  <td className="px-4 py-3 text-muted-foreground hidden xl:table-cell tabular-nums">
                    {formatDate(item.matched_at)}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* 페이지네이션 */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-1">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="p-2 rounded-md hover:bg-muted disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>

          {buildPages(page, totalPages).map((p, i) =>
            p === "…" ? (
              <span key={`ellipsis-${i}`} className="px-2 text-muted-foreground">…</span>
            ) : (
              <button
                key={p}
                onClick={() => setPage(p)}
                className={`min-w-[36px] h-9 px-2 rounded-md text-sm transition-colors ${
                  p === page
                    ? "bg-primary text-primary-foreground font-medium"
                    : "hover:bg-muted text-muted-foreground"
                }`}
              >
                {p}
              </button>
            )
          )}

          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="p-2 rounded-md hover:bg-muted disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      )}
    </div>
  )
}
