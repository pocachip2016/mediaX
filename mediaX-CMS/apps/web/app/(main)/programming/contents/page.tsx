"use client"

import { useEffect, useState, useCallback, useMemo, useRef } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import {
  Search, X, ChevronLeft, ChevronRight, RefreshCw,
  Film, Tv, Layers, Play, Check, RotateCcw, Link2, Trash2,
  ChevronDown,
} from "lucide-react"
import { cn } from "@workspace/ui/lib/utils"
import { metadataApi, type ContentOut, type ContentStatus, type ContentType, resolvePosterUrl } from "@/lib/api"
import { BulkActionModal, type BulkTarget } from "@/components/contents/BulkActionModal"
import { buildContentTree, countDescendants, type ContentTreeNode } from "@/lib/contentTree"

// ── 타입 ───────────────────────────────────────────────────

type UiGroup = "processing" | "review" | "approved" | "rejected"

type Enrichment = {
  ai_fields: number
  sources: string[]
  confidence?: "high" | "medium" | "low"
}

type ContentRow = ContentOut & { enrichment?: Enrichment }

// ── Mock 데이터 (백엔드 폴백) ──────────────────────────────

const MOCK_CONTENTS: ContentRow[] = [
  { id: 1, title: "기생충", original_title: "Parasite", content_type: "movie", status: "approved", cp_name: "CJ ENM", production_year: 2019, runtime_minutes: 132, country: "KR", created_at: "2026-04-01T09:00:00", quality_score: 96, poster_url: null,
    enrichment: { ai_fields: 0, sources: ["TMDB"], confidence: "high" } },
  { id: 2, title: "오징어 게임 시즌2", original_title: "Squid Game S2", content_type: "series", status: "ai", cp_name: "넷플릭스", production_year: 2024, runtime_minutes: null, country: "KR", created_at: "2026-04-02T10:00:00", quality_score: 88, poster_url: null,
    enrichment: { ai_fields: 3, sources: ["TMDB", "AI"], confidence: "high" } },
  { id: 3, title: "서울의 봄", original_title: null, content_type: "movie", status: "approved", cp_name: "플러스엠", production_year: 2023, runtime_minutes: 141, country: "KR", created_at: "2026-04-03T11:00:00", quality_score: 91, poster_url: null,
    enrichment: { ai_fields: 1, sources: ["TMDB", "KOBIS"], confidence: "high" } },
  { id: 4, title: "범죄도시4", original_title: null, content_type: "movie", status: "review", cp_name: "에이비오엔터테인먼트", production_year: 2024, runtime_minutes: 109, country: "KR", created_at: "2026-04-04T12:00:00", quality_score: 74, poster_url: null,
    enrichment: { ai_fields: 5, sources: ["AI"], confidence: "medium" } },
  { id: 5, title: "무빙", original_title: "Moving", content_type: "series", status: "approved", cp_name: "Disney+", production_year: 2023, runtime_minutes: null, country: "KR", created_at: "2026-04-05T13:00:00", quality_score: 93, poster_url: null,
    enrichment: { ai_fields: 0, sources: ["TMDB"], confidence: "high" } },
  { id: 6, title: "외계+인 2부", original_title: null, content_type: "movie", status: "raw", cp_name: "CJ ENM", production_year: 2024, runtime_minutes: 122, country: "KR", created_at: "2026-04-06T14:00:00", quality_score: null, poster_url: null },
  { id: 7, title: "헤어질 결심", original_title: "Decision to Leave", content_type: "movie", status: "approved", cp_name: "CJ ENM", production_year: 2022, runtime_minutes: 138, country: "KR", created_at: "2026-04-07T15:00:00", quality_score: 95, poster_url: null,
    enrichment: { ai_fields: 0, sources: ["TMDB", "KOBIS"], confidence: "high" } },
]

// ── 상수 ─────────────────────────────────────────────────

const STATUS_LABEL: Record<ContentStatus, string> = {
  raw: "수신", enriched: "회수완료", ai: "AI처리완료",
  review: "검수", approved: "승인", rejected: "반려",
}

const STATUS_CLASS: Record<ContentStatus, string> = {
  raw:      "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
  enriched: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300",
  ai:       "bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300",
  review:   "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300",
  approved: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300",
  rejected: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300",
}

const TYPE_LABEL: Record<ContentType, string> = {
  movie: "영화", series: "시리즈", season: "시즌", episode: "에피소드",
}

const TYPE_CLASS: Record<ContentType, string> = {
  movie:   "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300",
  series:  "bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300",
  season:  "bg-teal-100 text-teal-700 dark:bg-teal-900/30 dark:text-teal-300",
  episode: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
}

const UI_GROUPS: Array<{ key: UiGroup | "all"; label: string }> = [
  { key: "all",        label: "전체" },
  { key: "processing", label: "처리중" },
  { key: "review",     label: "검수필요" },
  { key: "approved",   label: "승인됨" },
  { key: "rejected",   label: "반려됨" },
]

function statusToUiGroup(status: ContentStatus): UiGroup {
  if (status === "raw" || status === "enriched") return "processing"
  if (status === "ai" || status === "review") return "review"
  if (status === "approved") return "approved"
  return "rejected"
}

// ── 보조 컴포넌트 ─────────────────────────────────────────

function TypeIcon({ type }: { type: ContentType }) {
  if (type === "movie") return <Film className="h-3.5 w-3.5" />
  if (type === "series") return <Tv className="h-3.5 w-3.5" />
  if (type === "season") return <Layers className="h-3.5 w-3.5" />
  return <Play className="h-3.5 w-3.5" />
}

function QualityBadge({ score }: { score: number | null }) {
  if (score === null) return <span className="text-muted-foreground text-xs">—</span>
  const cls =
    score >= 90 ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300" :
    score >= 70 ? "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300" :
    "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300"
  return <span className={cn("px-1.5 py-0.5 rounded text-xs font-semibold", cls)}>{score.toFixed(0)}</span>
}

function EnrichmentBadge({ enrichment }: { enrichment?: Enrichment }) {
  if (!enrichment) return <span className="text-muted-foreground text-xs">—</span>
  const colors =
    enrichment.confidence === "high"   ? "bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-300" :
    enrichment.confidence === "medium" ? "bg-yellow-50 text-yellow-700 dark:bg-yellow-900/20 dark:text-yellow-300" :
                                         "bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-300"
  return (
    <span className={cn("inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs", colors)}>
      ✨ AI{enrichment.ai_fields > 0 ? ` ${enrichment.ai_fields}` : ""}
      {enrichment.sources.length > 0 && <span>· {enrichment.sources.join("/")}</span>}
    </span>
  )
}

function formatDate(iso: string) {
  return iso.slice(0, 10)
}

// ── 검색 폼 ──────────────────────────────────────────────

interface SearchForm {
  title: string
  content_type: ContentType | ""
  cp_name: string
  production_year: string
}

const EMPTY_FORM: SearchForm = { title: "", content_type: "", cp_name: "", production_year: "" }

// ── 메인 페이지 ───────────────────────────────────────────

export default function ContentsPage() {
  const router = useRouter()

  // 검색 폼 (UI 그룹과 별도 — 그룹은 client-side 필터)
  const [form, setForm] = useState<SearchForm>(EMPTY_FORM)
  const [appliedForm, setAppliedForm] = useState<SearchForm>(EMPTY_FORM)
  const [uiGroup, setUiGroup] = useState<UiGroup | "all">("all")

  // 목록
  const [items, setItems] = useState<ContentRow[]>(MOCK_CONTENTS)
  const [total, setTotal] = useState(MOCK_CONTENTS.length)
  const [page, setPage] = useState(1)
  const [size, setSize] = useState(20)
  const [loading, setLoading] = useState(false)

  // 다중 선택
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())

  // 삭제
  const [deleting, setDeleting] = useState(false)

  // 계층 트리 뷰
  const [viewMode, setViewMode] = useState<"flat" | "tree">("tree")
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set())
  const [loadingChildren, setLoadingChildren] = useState<Set<number>>(new Set())
  const mergedItemsRef = useRef<Map<number, ContentRow>>(new Map())

  // 모달
  const [bulkModalOpen, setBulkModalOpen] = useState(false)
  const [bulkAction, setBulkAction] = useState<"approve" | "reject" | "reprocess" | "rematch">("approve")
  const bulkTargets: BulkTarget[] = Array.from(selectedIds).map(id => {
    const item = items.find(i => i.id === id)
    return { id, title: item?.title || "", cp_name: item?.cp_name, status: item?.status }
  })

  // ── 목록 로드 ──
  const fetchList = useCallback(async (f: SearchForm, p: number, s: number) => {
    setLoading(true)
    try {
      const res = await metadataApi.listContents({
        status: "approved",
        title: f.title || undefined,
        content_type: (f.content_type || undefined) as ContentType | undefined,
        cp_name: f.cp_name || undefined,
        production_year: f.production_year ? Number(f.production_year) : undefined,
        page: p,
        size: s,
      })
      const rootItems = res.items
      const m = new Map<number, ContentRow>()
      rootItems.forEach((it) => m.set(it.id, it))

      // 시리즈/시즌 루트의 자식을 병합해 트리 계층 구성 (S1 동작과 일치)
      const containerIds = rootItems
        .filter((it) => it.content_type === "series" || it.content_type === "season")
        .map((it) => it.id)
      const childrenAll: ContentRow[] = []
      await Promise.allSettled(
        containerIds.map(async (id) => {
          try {
            const hierarchy = await metadataApi.getHierarchy(id)
            const extract = (stagingChildren: typeof hierarchy.children) => {
              for (const s of stagingChildren) {
                if (!m.has(s.content.id)) {
                  m.set(s.content.id, s.content as ContentRow)
                  childrenAll.push(s.content as ContentRow)
                }
                if (s.children?.length) extract(s.children)
              }
            }
            extract(hierarchy.children)
          } catch { /* 개별 실패는 무시 */ }
        })
      )

      mergedItemsRef.current = m
      setItems([...rootItems, ...childrenAll])
      setTotal(res.total)
      // 시리즈/시즌 루트 기본 펼침 (S1 PipelineTreeList 동작과 일치)
      setExpandedIds(new Set(containerIds))
    } catch {
      setItems(MOCK_CONTENTS)
      setTotal(MOCK_CONTENTS.length)
      const m = new Map<number, ContentRow>()
      MOCK_CONTENTS.forEach((it) => m.set(it.id, it))
      mergedItemsRef.current = m
      setExpandedIds(new Set())
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchList(appliedForm, page, size) }, [appliedForm, page, size, fetchList])

  // ── UI 그룹 필터 (client-side) ──
  const filteredItems = useMemo(() => {
    if (uiGroup === "all") return items
    return items.filter((it) => statusToUiGroup(it.status) === uiGroup)
  }, [items, uiGroup])

  // 그룹별 카운트 (현재 페이지 기준)
  const groupCounts = useMemo(() => {
    const counts: Record<string, number> = { all: items.length, processing: 0, review: 0, approved: 0, rejected: 0 }
    items.forEach((it) => { counts[statusToUiGroup(it.status)] = (counts[statusToUiGroup(it.status)] ?? 0) + 1 })
    return counts
  }, [items])

  // ── 계층 트리 ──
  // filteredItems + mergedRef의 모든 항목(자식 포함)으로 트리 빌드
  const allMergedItems = useMemo(
    () => Array.from(mergedItemsRef.current.values()),
    // items 변경 시 ref도 동기화됐으므로 items를 dep로 사용
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [items]
  )
  const treeRoots = useMemo(() => {
    const uiFiltered = uiGroup === "all" ? allMergedItems : allMergedItems.filter((it) => statusToUiGroup(it.status) === uiGroup)
    return buildContentTree(uiFiltered).roots
  }, [allMergedItems, uiGroup])

  // 트리 노드를 depth 순서대로 평탄화 (펼침 상태 기준)
  function flattenTree(nodes: ContentTreeNode[], depth: number): Array<{ node: ContentTreeNode; depth: number }> {
    const result: Array<{ node: ContentTreeNode; depth: number }> = []
    for (const node of nodes) {
      result.push({ node, depth })
      if (expandedIds.has(node.item.id) && node.children.length > 0) {
        result.push(...flattenTree(node.children, depth + 1))
      }
    }
    return result
  }
  const flattenedTree = useMemo(() => flattenTree(treeRoots, 0), [treeRoots, expandedIds])

  const toggleExpand = async (node: ContentTreeNode) => {
    const id = node.item.id
    const isExpanding = !expandedIds.has(id)
    setExpandedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })

    // 펼칠 때 자식이 아직 없으면 lazy 로드
    if (isExpanding && node.children.length === 0 && (node.item.content_type === "series" || node.item.content_type === "season")) {
      setLoadingChildren((prev) => new Set(prev).add(id))
      try {
        const hierarchy = await metadataApi.getHierarchy(id)
        if (hierarchy?.children?.length) {
          // StagingItem.content 추출 → mergedItemsRef에 병합 → items 갱신
          const newItems: ContentRow[] = []
          const extract = (stagingChildren: typeof hierarchy.children) => {
            for (const s of stagingChildren) {
              if (!mergedItemsRef.current.has(s.content.id)) {
                newItems.push(s.content as ContentRow)
                mergedItemsRef.current.set(s.content.id, s.content as ContentRow)
              }
              if (s.children?.length) extract(s.children)
            }
          }
          extract(hierarchy.children)
          if (newItems.length > 0) {
            setItems((prev) => [...prev, ...newItems])
          }
        }
      } catch {
        // lazy 로드 실패 — 접힘으로 롤백
        setExpandedIds((prev) => { const next = new Set(prev); next.delete(id); return next })
      } finally {
        setLoadingChildren((prev) => { const next = new Set(prev); next.delete(id); return next })
      }
    }
  }

  // ── 선택 ──
  const allSelected = filteredItems.length > 0 && filteredItems.every((it) => selectedIds.has(it.id))
  const someSelected = filteredItems.some((it) => selectedIds.has(it.id))

  const toggleAll = () => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (allSelected) filteredItems.forEach((it) => next.delete(it.id))
      else filteredItems.forEach((it) => next.add(it.id))
      return next
    })
  }

  const toggleRow = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id); else next.add(id)
      return next
    })
  }

  const clearSelection = () => setSelectedIds(new Set())

  // ── Bulk 액션 가능 여부 ──
  const selectedItems = useMemo(
    () => items.filter((it) => selectedIds.has(it.id)),
    [items, selectedIds]
  )
  const canApprove = selectedItems.length > 0 && selectedItems.every((it) => it.status === "ai" || it.status === "review")
  const canReject  = canApprove
  const canRetryAI = selectedItems.length > 0 && selectedItems.every((it) => it.status === "review" || it.status === "enriched")
  const canRematch = selectedItems.length > 0

  // ── 삭제 핸들러 ──
  const handleBulkDelete = async () => {
    if (selectedIds.size === 0) return
    const confirmed = window.confirm(`선택한 ${selectedIds.size}건을 삭제합니다.\n삭제된 항목은 목록에서 숨겨집니다. 계속하시겠습니까?`)
    if (!confirmed) return
    setDeleting(true)
    try {
      await metadataApi.bulkDelete({ ids: Array.from(selectedIds) })
      clearSelection()
      fetchList(appliedForm, page, size)
    } catch {
      alert("삭제 중 오류가 발생했습니다.")
    } finally {
      setDeleting(false)
    }
  }

  // ── 검색 핸들러 ──
  const handleSearch = () => { setPage(1); setAppliedForm({ ...form }); clearSelection() }
  const handleReset  = () => { setForm(EMPTY_FORM); setPage(1); setAppliedForm(EMPTY_FORM); clearSelection() }

  const totalPages = Math.max(1, Math.ceil(total / size))

  return (
    <div className="space-y-3">
      {/* 헤더 */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-4 min-w-0">
          <h2 className="text-lg font-semibold tracking-tight shrink-0">콘텐츠 목록</h2>
          <span className="text-xs text-muted-foreground">
            총 <strong className="text-foreground">{total.toLocaleString()}</strong>건
          </span>
        </div>
        <div className="flex items-center gap-2">
          {/* 평면/계층 토글 */}
          <div className="flex items-center gap-1 text-xs">
            <span className="text-muted-foreground mr-1">목록:</span>
            {(["flat", "tree"] as const).map((mode) => (
              <button
                key={mode}
                type="button"
                onClick={() => setViewMode(mode)}
                className={cn(
                  "px-2 py-0.5 rounded transition-colors",
                  viewMode === mode
                    ? "bg-primary/15 text-primary font-medium"
                    : "text-muted-foreground hover:bg-accent"
                )}
              >
                {mode === "flat" ? "평면" : "계층"}
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={() => fetchList(appliedForm, page, size)}
            className="shrink-0 p-1.5 rounded-lg border border-border hover:bg-accent"
            title="새로고침"
          >
            <RefreshCw className={cn("h-3.5 w-3.5", loading && "animate-spin")} />
          </button>
        </div>
      </div>

      {/* Status 칩 (UI 4 그룹) */}
      <div className="flex gap-2 overflow-x-auto pb-1">
        {UI_GROUPS.map((g) => (
          <button
            key={g.key}
            onClick={() => { setUiGroup(g.key); clearSelection() }}
            className={cn(
              "px-3 py-1.5 rounded-full text-sm font-medium whitespace-nowrap transition-colors border",
              uiGroup === g.key
                ? "bg-foreground text-background border-foreground"
                : "bg-card text-foreground border-border hover:bg-accent",
            )}
          >
            {g.label}
            <span className={cn("ml-1.5 text-xs", uiGroup === g.key ? "opacity-70" : "text-muted-foreground")}>
              {groupCounts[g.key] ?? 0}
            </span>
          </button>
        ))}
      </div>

      {/* 검색 바 */}
      <div className="rounded-xl border border-border bg-card shadow-sm">
        <div className="flex items-center gap-2 px-3 py-2 flex-wrap">
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
          <input
            type="text"
            placeholder="CP사"
            value={form.cp_name}
            onChange={(e) => setForm((f) => ({ ...f, cp_name: e.target.value }))}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            className="w-28 px-3 py-1.5 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-1 focus:ring-primary"
          />
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
          <button
            onClick={handleSearch}
            className="shrink-0 flex items-center gap-1 px-3 py-1.5 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors"
          >
            <Search className="h-3.5 w-3.5" /> 검색
          </button>
          {(form.title || form.cp_name || form.content_type || form.production_year) && (
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

      {/* Sticky 액션 바 (선택 시 노출) */}
      {selectedIds.size > 0 && (
        <div className="sticky top-2 z-30 rounded-xl border border-primary/40 bg-primary/5 backdrop-blur shadow-md px-4 py-2.5 flex items-center justify-between">
          <div className="flex items-center gap-3 text-sm">
            <input
              type="checkbox"
              checked={allSelected}
              ref={(el) => { if (el) el.indeterminate = !allSelected && someSelected }}
              onChange={toggleAll}
              className="h-4 w-4 cursor-pointer"
            />
            <span className="font-medium">
              {selectedIds.size}개 선택됨
              {selectedIds.size > filteredItems.length && (
                <span className="ml-2 text-xs text-muted-foreground">(다른 페이지/그룹 포함)</span>
              )}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <BulkBtn icon={<Check className="h-3.5 w-3.5" />} label={`승인 (${selectedIds.size})`} enabled={canApprove} variant="green"
              onClick={() => { setBulkAction("approve"); setBulkModalOpen(true) }} />
            <BulkBtn icon={<X className="h-3.5 w-3.5" />} label={`반려 (${selectedIds.size})`} enabled={canReject} variant="red"
              onClick={() => { setBulkAction("reject"); setBulkModalOpen(true) }} />
            <BulkBtn icon={<RotateCcw className="h-3.5 w-3.5" />} label="AI 재처리" enabled={canRetryAI} variant="orange"
              onClick={() => { setBulkAction("reprocess"); setBulkModalOpen(true) }} />
            <BulkBtn icon={<Link2 className="h-3.5 w-3.5" />} label="외부소스 매칭" enabled={canRematch} variant="violet"
              onClick={() => alert(`[Step 2 예정] ${selectedIds.size}건 외부소스 매칭 모달`)} />
            <button
              type="button"
              disabled={deleting}
              onClick={handleBulkDelete}
              className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors bg-red-600 text-white hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Trash2 className="h-3.5 w-3.5" />
              {deleting ? "삭제 중…" : `삭제 (${selectedIds.size})`}
            </button>
            <button onClick={clearSelection}
              className="px-2.5 py-1.5 rounded-lg border border-border text-xs hover:bg-accent">
              해제
            </button>
          </div>
        </div>
      )}

      {/* 목록 테이블 */}
      <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
        <div className="px-5 py-3 border-b border-border flex items-center justify-between">
          <span className="text-sm text-muted-foreground">
            현재 표시 <span className="font-semibold text-foreground">{filteredItems.length.toLocaleString()}</span>건
            {(appliedForm.title || appliedForm.cp_name || appliedForm.content_type || appliedForm.production_year) && (
              <span className="ml-2 text-xs text-primary">(검색 적용 중)</span>
            )}
            {uiGroup !== "all" && (
              <span className="ml-2 text-xs text-primary">(그룹: {UI_GROUPS.find((g) => g.key === uiGroup)?.label})</span>
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

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/30">
                <th className="px-3 py-3 w-10">
                  <input
                    type="checkbox"
                    checked={allSelected}
                    ref={(el) => { if (el) el.indeterminate = !allSelected && someSelected }}
                    onChange={toggleAll}
                    className="h-4 w-4 cursor-pointer"
                  />
                </th>
                <th className="px-2 py-3 w-10" />
                <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground">콘텐츠명</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground w-24">유형</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground w-32">CP사</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground w-16">연도</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground w-24">상태</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground w-16">품질</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground w-32">Enrichment</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground w-24">등록일</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={10} className="text-center py-16 text-muted-foreground text-sm">
                  <RefreshCw className="h-5 w-5 animate-spin mx-auto mb-2" /> 불러오는 중...
                </td></tr>
              ) : (viewMode === "flat" ? filteredItems : flattenedTree.map((e) => e.node.item as ContentRow)).length === 0 ? (
                <tr><td colSpan={10} className="text-center py-16 text-muted-foreground text-sm">
                  표시할 콘텐츠가 없습니다.
                </td></tr>
              ) : viewMode === "flat" ? (
                filteredItems.map((item) => {
                  const selected = selectedIds.has(item.id)
                  return (
                    <tr
                      key={item.id}
                      onClick={() => router.push(`/programming/contents/${item.id}`)}
                      className={cn(
                        "border-b border-border last:border-0 cursor-pointer transition-colors",
                        selected ? "bg-primary/5 hover:bg-primary/10" : "hover:bg-accent/30",
                      )}
                    >
                      <td className="px-3 py-3" onClick={(e) => e.stopPropagation()}>
                        <input type="checkbox" checked={selected} onChange={() => toggleRow(item.id)} className="h-4 w-4 cursor-pointer" />
                      </td>
                      <td className="px-2 py-2" onClick={(e) => e.stopPropagation()}>
                        {resolvePosterUrl(item.poster_url) ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img src={resolvePosterUrl(item.poster_url)!} alt={item.title} className="rounded" style={{ width: 36, height: "auto" }} />
                        ) : (
                          <div className="flex items-center justify-center rounded bg-muted" style={{ width: 36, height: 52 }}>
                            <Film className="h-4 w-4 text-muted-foreground" />
                          </div>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <div className="font-medium truncate max-w-[240px]">{item.title}</div>
                        {item.original_title && <div className="text-xs text-muted-foreground truncate max-w-[240px]">{item.original_title}</div>}
                      </td>
                      <td className="px-4 py-3">
                        <span className={cn("inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium", TYPE_CLASS[item.content_type])}>
                          <TypeIcon type={item.content_type} />{TYPE_LABEL[item.content_type]}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm truncate max-w-[120px]">{item.cp_name ?? "—"}</td>
                      <td className="px-4 py-3 text-sm">{item.production_year ?? "—"}</td>
                      <td className="px-4 py-3">
                        <span className={cn("inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium", STATUS_CLASS[item.status])}>
                          {item.status === "enriched" && <span className="h-1.5 w-1.5 rounded-full bg-blue-400 animate-pulse" />}
                          {STATUS_LABEL[item.status]}
                        </span>
                      </td>
                      <td className="px-4 py-3"><QualityBadge score={item.quality_score} /></td>
                      <td className="px-4 py-3"><EnrichmentBadge enrichment={item.enrichment} /></td>
                      <td className="px-4 py-3 text-xs text-muted-foreground">{formatDate(item.created_at)}</td>
                      <td className="px-3 py-3" onClick={(e) => e.stopPropagation()}>
                        <Link href={`/programming/contents/${item.id}/edit`} className="inline-flex items-center px-2.5 py-1 rounded-md border border-border text-xs font-medium hover:bg-accent transition-colors">편집</Link>
                      </td>
                    </tr>
                  )
                })
              ) : (
                // ── 계층 트리 모드 ──
                flattenedTree.map(({ node, depth }) => {
                  const item = node.item as ContentRow
                  const selected = selectedIds.has(item.id)
                  const hasChildren = node.children.length > 0
                  const isExpanded = expandedIds.has(item.id)
                  const isLoadingChild = loadingChildren.has(item.id)
                  const descCount = countDescendants(node)
                  const canExpand = hasChildren || item.content_type === "series" || item.content_type === "season"
                  return (
                    <tr
                      key={item.id}
                      onClick={() => router.push(`/programming/contents/${item.id}`)}
                      className={cn(
                        "border-b border-border last:border-0 cursor-pointer transition-colors",
                        selected ? "bg-primary/5 hover:bg-primary/10" : "hover:bg-accent/30",
                      )}
                    >
                      <td className="px-3 py-3" onClick={(e) => e.stopPropagation()}>
                        <input type="checkbox" checked={selected} onChange={() => toggleRow(item.id)} className="h-4 w-4 cursor-pointer" />
                      </td>
                      <td className="px-2 py-2" onClick={(e) => e.stopPropagation()}>
                        {resolvePosterUrl(item.poster_url) ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img src={resolvePosterUrl(item.poster_url)!} alt={item.title} className="rounded" style={{ width: 36, height: "auto" }} />
                        ) : (
                          <div className="flex items-center justify-center rounded bg-muted" style={{ width: 36, height: 52 }}>
                            <Film className="h-4 w-4 text-muted-foreground" />
                          </div>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {/* 들여쓰기 + chevron + 제목 */}
                        <div className="flex items-center gap-1.5" style={{ paddingLeft: `${depth * 20}px` }}>
                          <span
                            className="shrink-0 w-4 h-4 flex items-center justify-center text-muted-foreground"
                            onClick={(e) => {
                              if (canExpand) { e.stopPropagation(); void toggleExpand(node) }
                            }}
                          >
                            {isLoadingChild ? (
                              <RefreshCw className="h-3 w-3 animate-spin" />
                            ) : canExpand ? (
                              isExpanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />
                            ) : (
                              <span className="w-3.5" />
                            )}
                          </span>
                          <div className="min-w-0">
                            <div className="font-medium truncate max-w-[200px]">{item.title}</div>
                            {item.original_title && <div className="text-xs text-muted-foreground truncate max-w-[200px]">{item.original_title}</div>}
                          </div>
                          {descCount > 0 && (
                            <span className="shrink-0 text-[10px] bg-muted text-muted-foreground px-1.5 py-0.5 rounded-full">
                              {descCount}건
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span className={cn("inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium", TYPE_CLASS[item.content_type])}>
                          <TypeIcon type={item.content_type} />{TYPE_LABEL[item.content_type]}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm truncate max-w-[120px]">{item.cp_name ?? "—"}</td>
                      <td className="px-4 py-3 text-sm">{item.production_year ?? "—"}</td>
                      <td className="px-4 py-3">
                        <span className={cn("inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium", STATUS_CLASS[item.status])}>
                          {item.status === "enriched" && <span className="h-1.5 w-1.5 rounded-full bg-blue-400 animate-pulse" />}
                          {STATUS_LABEL[item.status]}
                        </span>
                      </td>
                      <td className="px-4 py-3"><QualityBadge score={item.quality_score} /></td>
                      <td className="px-4 py-3"><EnrichmentBadge enrichment={item.enrichment} /></td>
                      <td className="px-4 py-3 text-xs text-muted-foreground">{formatDate(item.created_at)}</td>
                      <td className="px-3 py-3" onClick={(e) => e.stopPropagation()}>
                        <Link href={`/programming/contents/${item.id}/edit`} className="inline-flex items-center px-2.5 py-1 rounded-md border border-border text-xs font-medium hover:bg-accent transition-colors">편집</Link>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>

        {/* 페이지네이션 */}
        {totalPages > 1 && (
          <div className="px-5 py-3 border-t border-border flex items-center justify-between">
            <span className="text-xs text-muted-foreground">{page} / {totalPages} 페이지</span>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="p-1.5 rounded-md border border-border hover:bg-accent disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              {Array.from({ length: Math.min(7, totalPages) }, (_, i) => {
                let p: number
                if (totalPages <= 7) p = i + 1
                else if (page <= 4) p = i + 1
                else if (page >= totalPages - 3) p = totalPages - 6 + i
                else p = page - 3 + i
                return (
                  <button
                    key={p}
                    onClick={() => setPage(p)}
                    className={cn(
                      "min-w-[32px] h-8 rounded-md text-xs border transition-colors",
                      p === page ? "bg-primary text-primary-foreground border-primary" : "border-border hover:bg-accent",
                    )}
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
      {/* Modals */}
      <BulkActionModal open={bulkModalOpen} onOpenChange={setBulkModalOpen} action={bulkAction} targets={bulkTargets} />

    </div>
  )
}

// ── Bulk 액션 버튼 ──────────────────────────────────────

function BulkBtn({
  icon, label, enabled, variant, onClick,
}: {
  icon: React.ReactNode
  label: string
  enabled: boolean
  variant: "green" | "red" | "orange" | "violet"
  onClick: () => void
}) {
  const enabledClass = {
    green:  "bg-green-100 text-green-700 hover:bg-green-200 dark:bg-green-900/30 dark:text-green-300",
    red:    "bg-red-100 text-red-700 hover:bg-red-200 dark:bg-red-900/30 dark:text-red-300",
    orange: "bg-orange-100 text-orange-700 hover:bg-orange-200 dark:bg-orange-900/30 dark:text-orange-300",
    violet: "bg-violet-100 text-violet-700 hover:bg-violet-200 dark:bg-violet-900/30 dark:text-violet-300",
  }[variant]

  return (
    <button
      type="button"
      disabled={!enabled}
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors",
        enabled ? `${enabledClass} cursor-pointer` : "bg-muted text-muted-foreground cursor-not-allowed",
      )}
    >
      {icon} {label}
    </button>
  )
}
