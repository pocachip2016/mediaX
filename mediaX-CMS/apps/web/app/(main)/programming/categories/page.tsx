"use client"

import { useEffect, useState, useCallback, useMemo } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import {
  Search, RefreshCw, ChevronLeft, ChevronRight, ArrowRight,
  Hand, Sparkles, Globe,
} from "lucide-react"
import { cn } from "@workspace/ui/lib/utils"
import { distributionApi, type ServiceCategoryOut } from "@/lib/api"

// ── 상수 ─────────────────────────────────────────────────────

type ModeFilter = "all" | "manual" | "ai_proposed" | "external_imported"

const SOURCE_MODE_LABEL: Record<string, string> = {
  manual: "수동",
  ai_proposed: "AI 제안",
  external_imported: "외부 참고",
}

const SOURCE_MODE_CLASS: Record<string, string> = {
  manual: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
  ai_proposed: "bg-violet-100 text-violet-700 dark:bg-violet-900 dark:text-violet-300",
  external_imported: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
}

const MODE_FILTERS: { key: ModeFilter; label: string }[] = [
  { key: "all", label: "전체" },
  { key: "manual", label: "수동" },
  { key: "ai_proposed", label: "AI 제안" },
  { key: "external_imported", label: "외부 참고" },
]

const MOCK_CATEGORIES: ServiceCategoryOut[] = [
  {
    id: 1,
    name: "주말 영화 추천",
    category_type: "recommendation",
    platform: "ott",
    position: 1,
    is_active: true,
    headline_copy: "퇴근 후 90분의 위로",
    sub_copy: "오늘 저녁을 채울 딱 맞는 영화",
    theme_features: { genres: ["드라마", "코미디"], moods: ["따뜻한"] },
    source_mode: "ai_proposed",
    reference_external_id: null,
    is_draft: false,
    created_at: "2026-05-28T10:00:00+09:00",
    updated_at: "2026-05-28T10:00:00+09:00",
  },
  {
    id: 2,
    name: "이번 주 TOP10",
    category_type: "ranking",
    platform: "ott",
    position: 2,
    is_active: true,
    headline_copy: "이번 주 TOP10",
    sub_copy: null,
    theme_features: null,
    source_mode: "external_imported",
    reference_external_id: "ott_watcha:top",
    is_draft: false,
    created_at: "2026-05-27T14:00:00+09:00",
    updated_at: "2026-05-27T14:00:00+09:00",
  },
  {
    id: 3,
    name: "신작 모음",
    category_type: "new_release",
    platform: "iptv",
    position: 3,
    is_active: false,
    headline_copy: null,
    sub_copy: null,
    theme_features: { genres: ["액션"] },
    source_mode: "manual",
    reference_external_id: null,
    is_draft: true,
    created_at: "2026-05-26T09:00:00+09:00",
    updated_at: "2026-05-27T08:00:00+09:00",
  },
]

function formatDate(iso: string | null) {
  if (!iso) return "-"
  return iso.slice(0, 10).slice(5) // "MM-DD"
}

// ── CTA 카드 ──────────────────────────────────────────────────

const CTA_MODES = [
  {
    mode: "manual",
    icon: Hand,
    title: "수동 묶기",
    desc: "보유 콘텐츠를 직접 선택해 큐레이션을 만듭니다.",
    accent: "border-slate-200 hover:border-slate-400 dark:border-slate-700 dark:hover:border-slate-500",
  },
  {
    mode: "ai",
    icon: Sparkles,
    title: "AI 제안",
    desc: "테마 특징을 설정하면 AI가 카피와 콘텐츠를 제안합니다.",
    accent: "border-violet-200 hover:border-violet-400 dark:border-violet-800 dark:hover:border-violet-600",
  },
  {
    mode: "external",
    icon: Globe,
    title: "외부 참고",
    desc: "OTT 큐레이션 섹션을 참고해 빠르게 가져옵니다.",
    accent: "border-blue-200 hover:border-blue-400 dark:border-blue-800 dark:hover:border-blue-600",
  },
]

// ── 페이지 ────────────────────────────────────────────────────

export default function CategoriesPage() {
  const router = useRouter()
  const [categories, setCategories] = useState<ServiceCategoryOut[]>([])
  const [loading, setLoading] = useState(true)
  const [usedMock, setUsedMock] = useState(false)
  const [searchQuery, setSearchQuery] = useState("")
  const [modeFilter, setModeFilter] = useState<ModeFilter>("all")
  const [page, setPage] = useState(1)
  const size = 20

  const fetchCategories = useCallback(async () => {
    setLoading(true)
    try {
      const data = await distributionApi.getCategories()
      setCategories(data)
      setUsedMock(false)
    } catch (err) {
      console.error("[categories] API 실패 → Mock 폴백", err)
      setCategories(MOCK_CATEGORIES)
      setUsedMock(true)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchCategories()
  }, [fetchCategories])

  const filtered = useMemo(() => {
    const q = searchQuery.trim().toLowerCase()
    return categories.filter((c) => {
      const matchesSearch =
        !q ||
        c.name.toLowerCase().includes(q) ||
        (c.headline_copy ?? "").toLowerCase().includes(q)
      const matchesMode = modeFilter === "all" || c.source_mode === modeFilter
      return matchesSearch && matchesMode
    })
  }, [categories, searchQuery, modeFilter])

  const totalPages = Math.max(1, Math.ceil(filtered.length / size))
  const pageItems = filtered.slice((page - 1) * size, page * size)

  const handleSearch = (v: string) => {
    setSearchQuery(v)
    setPage(1)
  }
  const handleModeFilter = (m: ModeFilter) => {
    setModeFilter(m)
    setPage(1)
  }

  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">AI 큐레이션</h1>
          <p className="text-sm text-muted-foreground mt-1">
            테마별 콘텐츠 묶음을 설계하고 관리합니다.
            {usedMock && (
              <span className="ml-2 text-amber-600 dark:text-amber-400">(샘플 데이터)</span>
            )}
          </p>
        </div>
        <Link
          href="/programming/categories/new?mode=manual"
          className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors"
        >
          + 새 큐레이션
        </Link>
      </div>

      {/* CTA 카드 3종 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {CTA_MODES.map(({ mode, icon: Icon, title, desc, accent }) => (
          <Link
            key={mode}
            href={`/programming/categories/new?mode=${mode}`}
            className={cn(
              "group rounded-xl border bg-card p-5 shadow-sm hover:shadow-md transition-all flex flex-col gap-3",
              accent
            )}
          >
            <div className="flex items-start justify-between">
              <div className="p-2 rounded-lg bg-muted">
                <Icon className="h-5 w-5 text-muted-foreground" />
              </div>
              <ArrowRight className="h-4 w-4 text-muted-foreground group-hover:text-foreground transition-colors mt-1" />
            </div>
            <div>
              <h3 className="font-semibold text-sm">{title}</h3>
              <p className="text-xs text-muted-foreground mt-1 leading-relaxed">{desc}</p>
            </div>
          </Link>
        ))}
      </div>

      {/* 툴바 */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground pointer-events-none" />
          <input
            type="text"
            placeholder="이름 또는 카피 검색..."
            value={searchQuery}
            onChange={(e) => handleSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-2 border rounded-lg bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
          />
        </div>
        <div className="flex gap-1 border rounded-lg p-1 bg-muted/30">
          {MODE_FILTERS.map(({ key, label }) => (
            <button
              key={key}
              onClick={() => handleModeFilter(key)}
              className={cn(
                "px-3 py-1 text-xs rounded-md transition-colors",
                modeFilter === key
                  ? "bg-background shadow-sm font-medium text-foreground"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {label}
            </button>
          ))}
        </div>
        <button
          onClick={fetchCategories}
          disabled={loading}
          className="p-2 rounded-lg border bg-background hover:bg-accent transition-colors"
          title="새로고침"
        >
          <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
        </button>
      </div>

      {/* 테이블 */}
      <div className="rounded-xl border overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/30">
                <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground">이름</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground">헤드라인 카피</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground w-28">모드</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground w-20">플랫폼</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground w-24">상태</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground w-20">수정일</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={6} className="text-center py-16 text-muted-foreground">
                    <RefreshCw className="h-5 w-5 animate-spin mx-auto mb-2" />
                    불러오는 중...
                  </td>
                </tr>
              ) : pageItems.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center py-16 text-muted-foreground">
                    {searchQuery || modeFilter !== "all"
                      ? "검색 결과가 없습니다."
                      : "큐레이션이 없습니다. 새 큐레이션을 만들어보세요."}
                  </td>
                </tr>
              ) : (
                pageItems.map((item) => (
                  <tr
                    key={item.id}
                    onClick={() => router.push(`/programming/categories/${item.id}`)}
                    className="border-b cursor-pointer hover:bg-accent/30 transition-colors"
                  >
                    <td className="px-4 py-3 font-medium">{item.name}</td>
                    <td className="px-4 py-3 text-muted-foreground max-w-[240px] truncate">
                      {item.headline_copy ?? <span className="italic text-xs">미설정</span>}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={cn(
                          "inline-block px-2 py-0.5 rounded-full text-xs font-medium",
                          SOURCE_MODE_CLASS[item.source_mode] ?? SOURCE_MODE_CLASS.manual
                        )}
                      >
                        {SOURCE_MODE_LABEL[item.source_mode] ?? item.source_mode}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground uppercase text-xs">{item.platform}</td>
                    <td className="px-4 py-3">
                      {item.is_draft ? (
                        <span className="text-xs text-amber-600 dark:text-amber-400">임시저장</span>
                      ) : item.is_active ? (
                        <span className="text-xs text-green-600 dark:text-green-400">활성</span>
                      ) : (
                        <span className="text-xs text-muted-foreground">비활성</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground text-xs">
                      {formatDate(item.updated_at)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* 페이지네이션 */}
        {totalPages > 1 && (
          <div className="px-4 py-3 border-t flex items-center justify-between">
            <span className="text-xs text-muted-foreground">
              {filtered.length}개 중 {Math.min((page - 1) * size + 1, filtered.length)}–
              {Math.min(page * size, filtered.length)}개
            </span>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="p-1.5 rounded border disabled:opacity-40 hover:bg-accent transition-colors"
              >
                <ChevronLeft className="h-3.5 w-3.5" />
              </button>
              <span className="text-xs px-2">
                {page} / {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="p-1.5 rounded border disabled:opacity-40 hover:bg-accent transition-colors"
              >
                <ChevronRight className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
