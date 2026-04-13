"use client"

import { useEffect, useState, useCallback } from "react"
import { useRouter } from "next/navigation"
import { Search, X, ChevronLeft, ChevronRight, RefreshCw, Film, Tv, Layers, Play } from "lucide-react"
import { metadataApi, type ContentOut, type ContentStatus, type ContentType } from "@/lib/api"

// ── Mock 데이터 ───────────────────────────────────────────

const MOCK_CONTENTS: ContentOut[] = [
  { id: 1, title: "기생충", original_title: "Parasite", content_type: "movie", status: "approved", cp_name: "CJ ENM", production_year: 2019, runtime_minutes: 132, country: "KR", created_at: "2026-04-01T09:00:00", quality_score: 96 },
  { id: 2, title: "오징어 게임 시즌2", original_title: "Squid Game S2", content_type: "series", status: "staging", cp_name: "넷플릭스", production_year: 2024, runtime_minutes: null, country: "KR", created_at: "2026-04-02T10:00:00", quality_score: 88 },
  { id: 3, title: "서울의 봄", original_title: null, content_type: "movie", status: "approved", cp_name: "플러스엠", production_year: 2023, runtime_minutes: 141, country: "KR", created_at: "2026-04-03T11:00:00", quality_score: 91 },
  { id: 4, title: "범죄도시4", original_title: null, content_type: "movie", status: "review", cp_name: "에이비오엔터테인먼트", production_year: 2024, runtime_minutes: 109, country: "KR", created_at: "2026-04-04T12:00:00", quality_score: 74 },
  { id: 5, title: "무빙", original_title: "Moving", content_type: "series", status: "approved", cp_name: "Disney+", production_year: 2023, runtime_minutes: null, country: "KR", created_at: "2026-04-05T13:00:00", quality_score: 93 },
  { id: 6, title: "외계+인 2부", original_title: null, content_type: "movie", status: "waiting", cp_name: "CJ ENM", production_year: 2024, runtime_minutes: 122, country: "KR", created_at: "2026-04-06T14:00:00", quality_score: null },
  { id: 7, title: "헤어질 결심", original_title: "Decision to Leave", content_type: "movie", status: "approved", cp_name: "CJ ENM", production_year: 2022, runtime_minutes: 138, country: "KR", created_at: "2026-04-07T15:00:00", quality_score: 95 },
]

// ── 상수 ─────────────────────────────────────────────────

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

const TYPE_LABEL: Record<ContentType, string> = {
  movie: "영화",
  series: "시리즈",
  season: "시즌",
  episode: "에피소드",
}

const TYPE_CLASS: Record<ContentType, string> = {
  movie:   "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  series:  "bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-400",
  season:  "bg-teal-100 text-teal-700 dark:bg-teal-900/30 dark:text-teal-400",
  episode: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
}

function TypeIcon({ type }: { type: ContentType }) {
  if (type === "movie") return <Film className="h-3.5 w-3.5" />
  if (type === "series") return <Tv className="h-3.5 w-3.5" />
  if (type === "season") return <Layers className="h-3.5 w-3.5" />
  return <Play className="h-3.5 w-3.5" />
}

function QualityBadge({ score }: { score: number | null }) {
  if (score === null) return <span className="text-muted-foreground text-xs">—</span>
  const cls =
    score >= 90 ? "text-green-600 font-semibold" :
    score >= 70 ? "text-amber-600 font-semibold" :
    "text-red-600 font-semibold"
  return <span className={`text-xs ${cls}`}>{score.toFixed(0)}</span>
}

function formatDate(iso: string) {
  return iso.slice(0, 10)
}

// ── 검색 폼 상태 ──────────────────────────────────────────

interface SearchForm {
  title: string
  content_type: ContentType | ""
  status: ContentStatus | ""
  cp_name: string
  production_year: string
}

const EMPTY_FORM: SearchForm = {
  title: "",
  content_type: "",
  status: "",
  cp_name: "",
  production_year: "",
}

// ── 메인 페이지 ───────────────────────────────────────────

export default function ContentsPage() {
  const router = useRouter()

  // 통계
  const [stats, setStats] = useState({ total: 0, approved: 0, review: 0, waiting: 0 })

  // 검색 폼
  const [form, setForm] = useState<SearchForm>(EMPTY_FORM)
  const [appliedForm, setAppliedForm] = useState<SearchForm>(EMPTY_FORM)

  // 목록
  const [items, setItems] = useState<ContentOut[]>(MOCK_CONTENTS)
  const [total, setTotal] = useState(MOCK_CONTENTS.length)
  const [page, setPage] = useState(1)
  const [size, setSize] = useState(20)
  const [loading, setLoading] = useState(false)

  // ── 통계 로드 ──
  const fetchStats = useCallback(async () => {
    try {
      const dash = await metadataApi.getDashboard()
      // dashboard에서 status별 집계는 없으므로 전체 목록으로 계산
      const all = await metadataApi.listContents({ size: 1 })
      const [approvedRes, reviewRes, waitingRes] = await Promise.all([
        metadataApi.listContents({ status: "approved", size: 1 }),
        metadataApi.listContents({ status: "review", size: 1 }),
        metadataApi.listContents({ status: "waiting", size: 1 }),
      ])
      setStats({
        total: all.total,
        approved: approvedRes.total,
        review: reviewRes.total,
        waiting: waitingRes.total,
      })
    } catch {
      // Mock 통계 유지
      setStats({ total: MOCK_CONTENTS.length, approved: 3, review: 1, waiting: 1 })
    }
  }, [])

  // ── 목록 로드 ──
  const fetchList = useCallback(async (f: SearchForm, p: number, s: number) => {
    setLoading(true)
    try {
      const res = await metadataApi.listContents({
        title: f.title || undefined,
        content_type: (f.content_type || undefined) as ContentType | undefined,
        status: (f.status || undefined) as ContentStatus | undefined,
        cp_name: f.cp_name || undefined,
        production_year: f.production_year ? Number(f.production_year) : undefined,
        page: p,
        size: s,
      })
      setItems(res.items)
      setTotal(res.total)
    } catch {
      setItems(MOCK_CONTENTS)
      setTotal(MOCK_CONTENTS.length)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchStats()
  }, [fetchStats])

  useEffect(() => {
    fetchList(appliedForm, page, size)
  }, [appliedForm, page, size, fetchList])

  const handleSearch = () => {
    setPage(1)
    setAppliedForm({ ...form })
  }

  const handleReset = () => {
    setForm(EMPTY_FORM)
    setPage(1)
    setAppliedForm(EMPTY_FORM)
  }

  const totalPages = Math.max(1, Math.ceil(total / size))

  return (
    <div className="space-y-3">
      {/* 헤더 + 통계 인라인 */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-4 min-w-0">
          <h2 className="text-lg font-semibold tracking-tight shrink-0">콘텐츠 관리</h2>
          <div className="hidden sm:flex items-center gap-3 text-xs text-muted-foreground divide-x divide-border">
            <span className="pl-3">전체 <strong className="text-foreground">{stats.total.toLocaleString()}</strong></span>
            <span className="pl-3">완료 <strong className="text-green-600">{stats.approved.toLocaleString()}</strong></span>
            <span className="pl-3">검수대기 <strong className="text-amber-600">{stats.review.toLocaleString()}</strong></span>
            <span className="pl-3">신규 <strong className="text-foreground">{stats.waiting.toLocaleString()}</strong></span>
          </div>
        </div>
        <button
          onClick={() => { fetchStats(); fetchList(appliedForm, page, size) }}
          className="shrink-0 p-1.5 rounded-lg border border-border hover:bg-accent"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
        </button>
      </div>

      {/* 검색 바 — 한 줄 compact */}
      <div className="rounded-xl border border-border bg-card shadow-sm">
        <div className="flex items-center gap-2 px-3 py-2 flex-wrap">
          {/* 제목 검색 */}
          <div className="relative flex-1 min-w-[140px]">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground pointer-events-none" />
            <input
              type="text"
              placeholder="콘텐츠명 / 시리즈명"
              value={form.title}
              onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              className="w-full pl-8 pr-3 py-1.5 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>

          {/* CP사 */}
          <input
            type="text"
            placeholder="CP사"
            value={form.cp_name}
            onChange={(e) => setForm((f) => ({ ...f, cp_name: e.target.value }))}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            className="w-28 px-3 py-1.5 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-1 focus:ring-primary"
          />

          {/* 유형 */}
          <select
            value={form.content_type}
            onChange={(e) => setForm((f) => ({ ...f, content_type: e.target.value as ContentType | "" }))}
            className="w-24 px-2 py-1.5 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-1 focus:ring-primary"
          >
            <option value="">유형 전체</option>
            <option value="movie">영화</option>
            <option value="series">시리즈</option>
            <option value="season">시즌</option>
            <option value="episode">에피소드</option>
          </select>

          {/* 상태 */}
          <select
            value={form.status}
            onChange={(e) => setForm((f) => ({ ...f, status: e.target.value as ContentStatus | "" }))}
            className="w-24 px-2 py-1.5 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-1 focus:ring-primary"
          >
            <option value="">상태 전체</option>
            <option value="waiting">대기</option>
            <option value="processing">처리중</option>
            <option value="staging">검토대기</option>
            <option value="review">검수중</option>
            <option value="approved">완료</option>
            <option value="rejected">반려</option>
          </select>

          {/* 연도 */}
          <input
            type="number"
            placeholder="연도"
            min={1900}
            max={2099}
            value={form.production_year}
            onChange={(e) => setForm((f) => ({ ...f, production_year: e.target.value }))}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            className="w-20 px-2 py-1.5 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-1 focus:ring-primary"
          />

          {/* 검색 / 초기화 */}
          <button
            onClick={handleSearch}
            className="shrink-0 flex items-center gap-1 px-3 py-1.5 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors"
          >
            <Search className="h-3.5 w-3.5" /> 검색
          </button>
          {(form.title || form.cp_name || form.content_type || form.status || form.production_year) && (
            <button
              onClick={handleReset}
              className="shrink-0 p-1.5 rounded-lg border border-border hover:bg-accent text-muted-foreground transition-colors"
              title="초기화"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* 목록 테이블 */}
      <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
        {/* 목록 헤더 */}
        <div className="px-5 py-3 border-b border-border flex items-center justify-between">
          <span className="text-sm text-muted-foreground">
            총 <span className="font-semibold text-foreground">{total.toLocaleString()}</span>건
            {(appliedForm.title || appliedForm.cp_name || appliedForm.content_type || appliedForm.status || appliedForm.production_year) && (
              <span className="ml-2 text-xs text-primary">(필터 적용 중)</span>
            )}
          </span>
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">페이지당</span>
            <select
              value={size}
              onChange={(e) => { setSize(Number(e.target.value)); setPage(1) }}
              className="text-xs border border-border rounded-md px-2 py-1 bg-background focus:outline-none"
            >
              <option value={20}>20</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
            </select>
          </div>
        </div>

        {/* 테이블 */}
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/30">
                <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground w-10">#</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground">콘텐츠명</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground w-24">유형</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground w-32">CP사</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground w-16">연도</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground w-24">상태</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground w-16">품질</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground w-24">등록일</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={8} className="text-center py-16 text-muted-foreground text-sm">
                    <RefreshCw className="h-5 w-5 animate-spin mx-auto mb-2" />
                    불러오는 중...
                  </td>
                </tr>
              ) : items.length === 0 ? (
                <tr>
                  <td colSpan={8} className="text-center py-16 text-muted-foreground text-sm">
                    검색 결과가 없습니다.
                  </td>
                </tr>
              ) : (
                items.map((item, idx) => (
                  <tr
                    key={item.id}
                    onClick={() => router.push(`/programming/contents/${item.id}`)}
                    className="border-b border-border last:border-0 hover:bg-accent/30 cursor-pointer transition-colors"
                  >
                    <td className="px-4 py-3 text-xs text-muted-foreground">
                      {(page - 1) * size + idx + 1}
                    </td>
                    <td className="px-4 py-3">
                      <div className="font-medium truncate max-w-[220px]">{item.title}</div>
                      {item.original_title && (
                        <div className="text-xs text-muted-foreground truncate max-w-[220px]">{item.original_title}</div>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${TYPE_CLASS[item.content_type]}`}>
                        <TypeIcon type={item.content_type} />
                        {TYPE_LABEL[item.content_type]}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm truncate max-w-[120px]">{item.cp_name ?? "—"}</td>
                    <td className="px-4 py-3 text-sm">{item.production_year ?? "—"}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${STATUS_CLASS[item.status]}`}>
                        {STATUS_LABEL[item.status]}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <QualityBadge score={item.quality_score} />
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">{formatDate(item.created_at)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* 페이지네이션 */}
        {totalPages > 1 && (
          <div className="px-5 py-3 border-t border-border flex items-center justify-between">
            <span className="text-xs text-muted-foreground">
              {page} / {totalPages} 페이지
            </span>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="p-1.5 rounded-md border border-border hover:bg-accent disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              {/* 페이지 번호 (최대 7개) */}
              {Array.from({ length: Math.min(7, totalPages) }, (_, i) => {
                let p: number
                if (totalPages <= 7) {
                  p = i + 1
                } else if (page <= 4) {
                  p = i + 1
                } else if (page >= totalPages - 3) {
                  p = totalPages - 6 + i
                } else {
                  p = page - 3 + i
                }
                return (
                  <button
                    key={p}
                    onClick={() => setPage(p)}
                    className={`min-w-[32px] h-8 rounded-md text-xs border transition-colors ${
                      p === page
                        ? "bg-primary text-primary-foreground border-primary"
                        : "border-border hover:bg-accent"
                    }`}
                  >
                    {p}
                  </button>
                )
              })}
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="p-1.5 rounded-md border border-border hover:bg-accent disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}
      </div>

    </div>
  )
}
