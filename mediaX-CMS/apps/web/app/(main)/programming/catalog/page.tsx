"use client"

import { useEffect, useState, useCallback } from "react"
import { ChevronRight, ChevronDown, Plus, Trash2, FolderOpen, Folder } from "lucide-react"
import { cn } from "@workspace/ui/lib/utils"
import { catalogApi, type CategoryNode, type CategoryCreateRequest } from "@/lib/api"

// ── 인라인 추가 폼 ────────────────────────────────────────────────────────────

function AddCategoryInline({
  parentId,
  depth,
  onAdd,
  onCancel,
}: {
  parentId: number | null
  depth: number
  onAdd: (name: string, parentId: number | null) => Promise<void>
  onCancel: () => void
}) {
  const [name, setName] = useState("")
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    setLoading(true)
    try {
      await onAdd(name.trim(), parentId)
      setName("")
    } finally {
      setLoading(false)
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex items-center gap-2 py-1"
      style={{ paddingLeft: `${(depth + 1) * 20 + 8}px` }}
    >
      <input
        autoFocus
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="카테고리 이름"
        disabled={loading}
        className="h-7 rounded border border-border bg-background px-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
      />
      <button
        type="submit"
        disabled={loading || !name.trim()}
        className="rounded bg-primary px-2 py-1 text-xs text-primary-foreground disabled:opacity-50"
      >
        {loading ? "추가중…" : "추가"}
      </button>
      <button
        type="button"
        onClick={onCancel}
        className="text-xs text-muted-foreground hover:text-foreground"
      >
        취소
      </button>
    </form>
  )
}

// ── 노드 ─────────────────────────────────────────────────────────────────────

function CategoryNodeItem({
  node,
  onAdd,
  onDelete,
}: {
  node: CategoryNode
  onAdd: (name: string, parentId: number | null) => Promise<void>
  onDelete: (id: number) => Promise<void>
}) {
  const [expanded, setExpanded] = useState(true)
  const [addingChild, setAddingChild] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const hasChildren = node.children.length > 0

  const handleDelete = async () => {
    if (!confirm(`"${node.name}" 카테고리를 삭제할까요?`)) return
    setDeleting(true)
    try {
      await onDelete(node.id)
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div>
      <div
        className={cn(
          "group flex items-center gap-1 rounded px-2 py-1 text-sm hover:bg-muted/50",
          !node.is_active && "opacity-50"
        )}
        style={{ paddingLeft: `${node.depth * 20 + 8}px` }}
      >
        {/* 펼치기/접기 */}
        <button
          onClick={() => setExpanded((v) => !v)}
          className="flex h-4 w-4 items-center justify-center text-muted-foreground"
          disabled={!hasChildren}
        >
          {hasChildren ? (
            expanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />
          ) : (
            <span className="h-3 w-3" />
          )}
        </button>

        {/* 폴더 아이콘 */}
        {hasChildren && expanded ? (
          <FolderOpen className="h-4 w-4 shrink-0 text-amber-500" />
        ) : (
          <Folder className="h-4 w-4 shrink-0 text-muted-foreground" />
        )}

        {/* 이름 */}
        <span className="flex-1 truncate">{node.name}</span>

        {/* 콘텐츠 수 */}
        {node.content_count != null && (
          <span className="text-xs text-muted-foreground">({node.content_count})</span>
        )}

        {/* 액션 버튼 (hover 시 노출) */}
        <div className="ml-1 flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
          <button
            onClick={() => setAddingChild(true)}
            title="하위 카테고리 추가"
            className="flex h-5 w-5 items-center justify-center rounded text-muted-foreground hover:bg-accent hover:text-foreground"
          >
            <Plus className="h-3 w-3" />
          </button>
          <button
            onClick={handleDelete}
            disabled={deleting}
            title="삭제"
            className="flex h-5 w-5 items-center justify-center rounded text-muted-foreground hover:bg-destructive/10 hover:text-destructive disabled:opacity-50"
          >
            <Trash2 className="h-3 w-3" />
          </button>
        </div>
      </div>

      {/* 하위 추가 폼 */}
      {addingChild && (
        <AddCategoryInline
          parentId={node.id}
          depth={node.depth}
          onAdd={async (name, pid) => {
            await onAdd(name, pid)
            setAddingChild(false)
          }}
          onCancel={() => setAddingChild(false)}
        />
      )}

      {/* 자식 노드 */}
      {expanded &&
        node.children.map((child) => (
          <CategoryNodeItem key={child.id} node={child} onAdd={onAdd} onDelete={onDelete} />
        ))}
    </div>
  )
}

// ── 트리 ─────────────────────────────────────────────────────────────────────

function CategoryTree({
  nodes,
  onAdd,
  onDelete,
}: {
  nodes: CategoryNode[]
  onAdd: (name: string, parentId: number | null) => Promise<void>
  onDelete: (id: number) => Promise<void>
}) {
  if (nodes.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
        <Folder className="mb-3 h-10 w-10 opacity-30" />
        <p className="text-sm">카테고리 없음 — 루트 카테고리를 추가해주세요.</p>
      </div>
    )
  }

  return (
    <div className="space-y-0.5">
      {nodes.map((node) => (
        <CategoryNodeItem key={node.id} node={node} onAdd={onAdd} onDelete={onDelete} />
      ))}
    </div>
  )
}

// ── 페이지 ────────────────────────────────────────────────────────────────────

export default function CatalogCategoryPage() {
  const [tree, setTree] = useState<CategoryNode[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [addingRoot, setAddingRoot] = useState(false)

  const fetchTree = useCallback(async () => {
    try {
      setError(null)
      const data = await catalogApi.getTree({ counts: true })
      setTree(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : "로드 실패")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void fetchTree()
  }, [fetchTree])

  const handleAdd = useCallback(
    async (name: string, parentId: number | null) => {
      const req: CategoryCreateRequest = { name, parent_id: parentId }
      await catalogApi.createCategory(req)
      await fetchTree()
    },
    [fetchTree]
  )

  const handleDelete = useCallback(
    async (id: number) => {
      await catalogApi.deleteCategory(id)
      await fetchTree()
    },
    [fetchTree]
  )

  return (
    <div className="flex flex-col gap-4 p-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">카테고리 트리</h1>
          <p className="mt-0.5 text-sm text-muted-foreground">
            서비스 VOD 카탈로그의 N-depth 카테고리 계층을 관리합니다.
          </p>
        </div>
        <button
          onClick={() => setAddingRoot(true)}
          className="flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground hover:bg-primary/90"
        >
          <Plus className="h-4 w-4" />
          루트 카테고리
        </button>
      </div>

      {/* 루트 추가 폼 */}
      {addingRoot && (
        <div className="rounded-lg border border-dashed p-2">
          <AddCategoryInline
            parentId={null}
            depth={-1}
            onAdd={async (name, pid) => {
              await handleAdd(name, pid)
              setAddingRoot(false)
            }}
            onCancel={() => setAddingRoot(false)}
          />
        </div>
      )}

      {/* 본문 */}
      <div className="rounded-lg border bg-card p-2">
        {loading ? (
          <div className="space-y-2 p-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-6 animate-pulse rounded bg-muted" />
            ))}
          </div>
        ) : error ? (
          <div className="flex flex-col items-center gap-2 py-12 text-sm text-destructive">
            <p>{error}</p>
            <button
              onClick={() => {
                setLoading(true)
                void fetchTree()
              }}
              className="text-muted-foreground underline hover:text-foreground"
            >
              다시 시도
            </button>
          </div>
        ) : (
          <CategoryTree nodes={tree} onAdd={handleAdd} onDelete={handleDelete} />
        )}
      </div>
    </div>
  )
}
