"use client"

import { useEffect, useState, useCallback, useRef } from "react"
import { useParams, useRouter } from "next/navigation"
import Link from "next/link"
import { ArrowLeft, RefreshCw, Trash2, Search, Plus, ChevronUp, ChevronDown, X } from "lucide-react"
import { cn } from "@workspace/ui/lib/utils"
import {
  distributionApi,
  metadataApi,
  type ServiceCategoryWithItemsOut,
  type ServiceCategoryItemOut,
  type ContentOut,
} from "@/lib/api"

// ── 상수 ──────────────────────────────────────────────────────

const PLATFORM_OPTIONS = ["ott", "iptv", "mobile", "web"]
const CATEGORY_TYPE_OPTIONS = [
  "recommendation",
  "ranking",
  "genre",
  "mood",
  "new_release",
  "event",
]

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

const MOCK_CATEGORY: ServiceCategoryWithItemsOut = {
  id: 0,
  name: "(Mock) 주말 영화 추천",
  category_type: "recommendation",
  platform: "ott",
  position: 1,
  is_active: true,
  headline_copy: "퇴근 후 90분의 위로",
  sub_copy: "오늘 저녁을 채울 딱 맞는 영화",
  theme_features: null,
  source_mode: "manual",
  reference_external_id: null,
  is_draft: false,
  created_at: null,
  updated_at: null,
  items: [],
}

// ── 마스터 편집 폼 ─────────────────────────────────────────────

interface MasterFormProps {
  category: ServiceCategoryWithItemsOut
  onSaved: (updated: ServiceCategoryWithItemsOut) => void
  onDeleted: () => void
}

function MasterForm({ category, onSaved, onDeleted }: MasterFormProps) {
  const [name, setName]                 = useState(category.name)
  const [headlineCopy, setHeadlineCopy] = useState(category.headline_copy ?? "")
  const [subCopy, setSubCopy]           = useState(category.sub_copy ?? "")
  const [platform, setPlatform]         = useState(category.platform)
  const [categoryType, setCategoryType] = useState(category.category_type)
  const [isActive, setIsActive]         = useState(category.is_active)
  const [isDraft, setIsDraft]           = useState(category.is_draft)
  const [saving, setSaving]             = useState(false)
  const [deleting, setDeleting]         = useState(false)
  const [error, setError]               = useState<string | null>(null)

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) { setError("이름은 필수입니다."); return }
    setError(null)
    setSaving(true)
    try {
      const updated = await distributionApi.updateCategory(category.id, {
        name: name.trim(),
        headline_copy: headlineCopy.trim() || null,
        sub_copy: subCopy.trim() || null,
        platform,
        category_type: categoryType,
        is_active: isActive,
        is_draft: isDraft,
      })
      onSaved({ ...category, ...updated })
    } catch {
      setError("저장 중 오류가 발생했습니다.")
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    if (!confirm("이 큐레이션을 삭제하시겠습니까?")) return
    setDeleting(true)
    try {
      await distributionApi.deleteCategory(category.id)
      onDeleted()
    } catch {
      setError("삭제 중 오류가 발생했습니다.")
      setDeleting(false)
    }
  }

  return (
    <form onSubmit={handleSave} className="space-y-4">
      <div className="space-y-1.5">
        <label className="text-sm font-medium">
          이름 <span className="text-destructive">*</span>
        </label>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="w-full px-3 py-2 border rounded-lg bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
        />
      </div>

      <div className="space-y-1.5">
        <label className="text-sm font-medium">헤드라인 카피</label>
        <input
          type="text"
          value={headlineCopy}
          onChange={(e) => setHeadlineCopy(e.target.value)}
          placeholder="예: 퇴근 후 90분의 위로"
          className="w-full px-3 py-2 border rounded-lg bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
        />
      </div>

      <div className="space-y-1.5">
        <label className="text-sm font-medium">보조 카피</label>
        <input
          type="text"
          value={subCopy}
          onChange={(e) => setSubCopy(e.target.value)}
          placeholder="예: 오늘 저녁을 채울 딱 맞는 영화"
          className="w-full px-3 py-2 border rounded-lg bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
        />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <label className="text-sm font-medium">플랫폼</label>
          <select
            value={platform}
            onChange={(e) => setPlatform(e.target.value)}
            className="w-full px-3 py-2 border rounded-lg bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
          >
            {PLATFORM_OPTIONS.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>
        <div className="space-y-1.5">
          <label className="text-sm font-medium">유형</label>
          <select
            value={categoryType}
            onChange={(e) => setCategoryType(e.target.value)}
            className="w-full px-3 py-2 border rounded-lg bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
          >
            {CATEGORY_TYPE_OPTIONS.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
      </div>

      <div className="flex items-center gap-6">
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input
            type="checkbox"
            checked={isActive}
            onChange={(e) => setIsActive(e.target.checked)}
            className="rounded"
          />
          활성
        </label>
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input
            type="checkbox"
            checked={isDraft}
            onChange={(e) => setIsDraft(e.target.checked)}
            className="rounded"
          />
          임시저장
        </label>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <div className="flex items-center justify-between pt-2">
        <button
          type="button"
          onClick={handleDelete}
          disabled={deleting}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-destructive/40 text-destructive text-xs hover:bg-destructive/10 disabled:opacity-50 transition-colors"
        >
          <Trash2 className="h-3.5 w-3.5" />
          {deleting ? "삭제 중..." : "삭제"}
        </button>
        <button
          type="submit"
          disabled={saving}
          className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
        >
          {saving ? "저장 중..." : "저장"}
        </button>
      </div>
    </form>
  )
}

// ── ContentPicker — 콘텐츠 검색 + 추가 ──────────────────────────

interface ContentPickerProps {
  categoryId: number
  existingIds: Set<number>
  nextRank: number
  onAdded: (item: ServiceCategoryItemOut) => void
}

function ContentPicker({ categoryId, existingIds, nextRank, onAdded }: ContentPickerProps) {
  const [query, setQuery]         = useState("")
  const [results, setResults]     = useState<ContentOut[]>([])
  const [searching, setSearching] = useState(false)
  const [addingId, setAddingId]   = useState<number | null>(null)
  const debounceRef               = useRef<ReturnType<typeof setTimeout> | null>(null)

  const search = useCallback(async (q: string) => {
    if (!q.trim()) { setResults([]); return }
    setSearching(true)
    try {
      const res = await metadataApi.listContents({ title: q.trim(), size: 10 })
      setResults(res.items)
    } catch {
      setResults([])
    } finally {
      setSearching(false)
    }
  }, [])

  const handleQueryChange = (v: string) => {
    setQuery(v)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => search(v), 300)
  }

  const handleAdd = async (content: ContentOut) => {
    setAddingId(content.id)
    try {
      const item = await distributionApi.addItem(categoryId, {
        content_id: content.id,
        rank: nextRank,
      })
      onAdded({ ...item, content_title: content.title })
      setResults((prev) => prev.filter((c) => c.id !== content.id))
    } catch {
      // 실패 시 조용히 무시 — 사용자가 재시도 가능
    } finally {
      setAddingId(null)
    }
  }

  return (
    <div className="border rounded-lg overflow-hidden mb-4">
      <div className="px-3 py-2 bg-muted/30 border-b">
        <p className="text-xs font-medium text-muted-foreground">콘텐츠 추가</p>
      </div>
      <div className="p-3 space-y-2">
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground pointer-events-none" />
          <input
            type="text"
            value={query}
            onChange={(e) => handleQueryChange(e.target.value)}
            placeholder="제목으로 검색..."
            className="w-full pl-8 pr-3 py-1.5 border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
          />
        </div>

        {searching && (
          <p className="text-xs text-muted-foreground text-center py-2">검색 중...</p>
        )}

        {!searching && query.trim() && results.length === 0 && (
          <p className="text-xs text-muted-foreground text-center py-2">검색 결과 없음</p>
        )}

        {results.length > 0 && (
          <ul className="divide-y max-h-48 overflow-y-auto rounded-md border">
            {results.map((content) => {
              const alreadyAdded = existingIds.has(content.id)
              return (
                <li
                  key={content.id}
                  className="flex items-center justify-between gap-2 px-3 py-2 hover:bg-accent/30 transition-colors"
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-sm truncate">{content.title}</p>
                    <p className="text-xs text-muted-foreground">
                      {content.content_type} · {content.production_year ?? "-"}
                    </p>
                  </div>
                  <button
                    onClick={() => handleAdd(content)}
                    disabled={alreadyAdded || addingId === content.id}
                    className={cn(
                      "shrink-0 flex items-center gap-1 px-2 py-1 rounded text-xs font-medium transition-colors",
                      alreadyAdded
                        ? "opacity-40 cursor-not-allowed text-muted-foreground border"
                        : "bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                    )}
                    title={alreadyAdded ? "이미 추가됨" : "추가"}
                  >
                    <Plus className="h-3 w-3" />
                    {alreadyAdded ? "추가됨" : addingId === content.id ? "..." : "추가"}
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </div>
  )
}

// ── ItemRow — 순서 변경 + 삭제 ────────────────────────────────

interface ItemRowProps {
  item: ServiceCategoryItemOut
  isFirst: boolean
  isLast: boolean
  onMoveUp: () => void
  onMoveDown: () => void
  onRemove: () => void
}

function ItemRow({ item, isFirst, isLast, onMoveUp, onMoveDown, onRemove }: ItemRowProps) {
  return (
    <li className="flex items-center gap-2 py-2.5 px-1 group">
      <span className="text-xs text-muted-foreground w-5 text-right shrink-0 font-mono">
        {item.rank}
      </span>
      <span className="text-sm flex-1 truncate">
        {item.content_title ?? `콘텐츠 #${item.content_id}`}
      </span>
      <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
        <button
          onClick={onMoveUp}
          disabled={isFirst}
          className="p-1 rounded hover:bg-accent disabled:opacity-30 transition-colors"
          title="위로"
        >
          <ChevronUp className="h-3.5 w-3.5" />
        </button>
        <button
          onClick={onMoveDown}
          disabled={isLast}
          className="p-1 rounded hover:bg-accent disabled:opacity-30 transition-colors"
          title="아래로"
        >
          <ChevronDown className="h-3.5 w-3.5" />
        </button>
        <button
          onClick={onRemove}
          className="p-1 rounded hover:bg-destructive/10 text-destructive transition-colors"
          title="제거"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
    </li>
  )
}

// ── 콘텐츠 묶음 패널 ──────────────────────────────────────────

interface ItemsPanelProps {
  categoryId: number
  items: ServiceCategoryItemOut[]
  onItemsChange: (items: ServiceCategoryItemOut[]) => void
}

function ItemsPanel({ categoryId, items, onItemsChange }: ItemsPanelProps) {
  const existingIds = new Set(items.map((i) => i.content_id))

  const handleAdded = (newItem: ServiceCategoryItemOut) => {
    onItemsChange([...items, newItem])
  }

  const handleRemove = async (item: ServiceCategoryItemOut) => {
    try {
      await distributionApi.removeItem(categoryId, item.id)
      const updated = items
        .filter((i) => i.id !== item.id)
        .map((i, idx) => ({ ...i, rank: idx + 1 }))
      onItemsChange(updated)
    } catch {
      // 실패 시 무시 — 사용자 재시도 가능
    }
  }

  const handleMove = async (index: number, direction: "up" | "down") => {
    const newItems = [...items]
    const targetIndex = direction === "up" ? index - 1 : index + 1
    // swap
    ;[newItems[index], newItems[targetIndex]] = [newItems[targetIndex]!, newItems[index]!]
    // reassign ranks
    const reranked = newItems.map((item, idx) => ({ ...item, rank: idx + 1 }))
    onItemsChange(reranked)
    try {
      await distributionApi.reorderItems(
        categoryId,
        reranked.map((i) => ({ id: i.id, rank: i.rank }))
      )
    } catch {
      // 실패 시 롤백 — 원본 복원
      onItemsChange(items)
    }
  }

  return (
    <>
      <ContentPicker
        categoryId={categoryId}
        existingIds={existingIds}
        nextRank={items.length + 1}
        onAdded={handleAdded}
      />

      {items.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 text-center text-muted-foreground">
          <p className="text-sm">아직 묶인 콘텐츠가 없습니다.</p>
          <p className="text-xs mt-1">위 검색창에서 콘텐츠를 추가해보세요.</p>
        </div>
      ) : (
        <ol className="divide-y">
          {items.map((item, idx) => (
            <ItemRow
              key={item.id}
              item={item}
              isFirst={idx === 0}
              isLast={idx === items.length - 1}
              onMoveUp={() => handleMove(idx, "up")}
              onMoveDown={() => handleMove(idx, "down")}
              onRemove={() => handleRemove(item)}
            />
          ))}
        </ol>
      )}
    </>
  )
}

// ── 페이지 ────────────────────────────────────────────────────

export default function CategoryDetailPage() {
  const { id } = useParams<{ id: string }>()
  const router  = useRouter()
  const [category, setCategory] = useState<ServiceCategoryWithItemsOut | null>(null)
  const [loading, setLoading]   = useState(true)

  const fetchCategory = useCallback(async () => {
    setLoading(true)
    try {
      const data = await distributionApi.getCategory(Number(id))
      setCategory(data)
    } catch (err) {
      console.error("[category-detail] API 실패 → Mock 폴백", err)
      setCategory({ ...MOCK_CATEGORY, id: Number(id) })
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => { fetchCategory() }, [fetchCategory])

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (!category) return null

  const updateItems = (items: ServiceCategoryItemOut[]) =>
    setCategory((prev) => prev ? { ...prev, items } : prev)

  return (
    <div className="space-y-5">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/programming/categories"
            className="p-1.5 rounded-lg hover:bg-accent transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div>
            <h1 className="text-xl font-bold">{category.name}</h1>
            <div className="flex items-center gap-2 mt-1">
              <span
                className={cn(
                  "inline-block px-2 py-0.5 rounded-full text-xs font-medium",
                  SOURCE_MODE_CLASS[category.source_mode] ?? SOURCE_MODE_CLASS.manual
                )}
              >
                {SOURCE_MODE_LABEL[category.source_mode] ?? category.source_mode}
              </span>
              {category.is_draft && (
                <span className="text-xs text-amber-600 dark:text-amber-400">임시저장</span>
              )}
            </div>
          </div>
        </div>
        <button
          onClick={fetchCategory}
          className="p-2 rounded-lg border bg-background hover:bg-accent transition-colors"
          title="새로고침"
        >
          <RefreshCw className="h-4 w-4" />
        </button>
      </div>

      {/* 2컬럼 레이아웃 */}
      <div className="grid grid-cols-1 lg:grid-cols-[380px_1fr] gap-6 items-start">
        {/* 마스터 폼 */}
        <div className="rounded-xl border bg-card p-5 shadow-sm">
          <h2 className="text-sm font-semibold mb-4">기본 정보</h2>
          <MasterForm
            category={category}
            onSaved={(updated) => setCategory({ ...updated, items: category.items })}
            onDeleted={() => router.push("/programming/categories")}
          />
        </div>

        {/* 콘텐츠 묶음 패널 */}
        <div className="rounded-xl border bg-card shadow-sm">
          <div className="px-5 py-4 border-b">
            <h2 className="text-sm font-semibold">
              묶인 콘텐츠
              <span className="ml-2 text-xs text-muted-foreground font-normal">
                ({category.items.length})
              </span>
            </h2>
          </div>
          <div className="px-5 py-4">
            <ItemsPanel
              categoryId={category.id}
              items={category.items}
              onItemsChange={updateItems}
            />
          </div>
        </div>
      </div>
    </div>
  )
}
