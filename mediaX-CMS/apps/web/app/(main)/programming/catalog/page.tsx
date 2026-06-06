"use client"

import { useEffect, useState, useCallback } from "react"
import { Plus, RefreshCw, FolderPlus, Upload, FlaskConical } from "lucide-react"
import { cn } from "@workspace/ui/lib/utils"
import { catalogApi, type CategoryNode, type CategoryCreateRequest, type CategoryUpdateRequest } from "@/lib/api"
import { CategoryTreeDnd } from "@/components/catalog/CategoryTreeDnd"
import { CategoryDetailPanel } from "@/components/catalog/CategoryDetailPanel"
import { BulkImportPanel } from "@/components/catalog/BulkImportPanel"
import { CATEGORY_TEST_DATA } from "@/lib/categoryBulkParse"

type RightPanelMode = "idle" | "bulk"

// ── 루트 인라인 추가 ──────────────────────────────────────────────────────────

function AddRootInline({
  onAdd,
  onCancel,
}: {
  onAdd: (name: string) => Promise<void>
  onCancel: () => void
}) {
  const [name, setName] = useState("")
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    setLoading(true)
    try {
      await onAdd(name.trim())
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex items-center gap-2 p-2">
      <input
        autoFocus
        value={name}
        onChange={(e) => setName(e.target.value)}
        onKeyDown={(e) => e.key === "Escape" && onCancel()}
        placeholder="루트 카테고리 이름"
        disabled={loading}
        className="h-8 flex-1 rounded border border-border bg-background px-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
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

// ── 페이지 ────────────────────────────────────────────────────────────────────

export default function CatalogCategoryPage() {
  const [tree, setTree] = useState<CategoryNode[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [addingRoot, setAddingRoot] = useState(false)
  const [selectedNode, setSelectedNode] = useState<CategoryNode | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [rightPanel, setRightPanel] = useState<RightPanelMode>("idle")
  const [bulkInitialText, setBulkInitialText] = useState("")

  const fetchTree = useCallback(async () => {
    try {
      setError(null)
      const data = await catalogApi.getTree({ counts: true })
      setTree(data)
      // 선택된 노드 갱신 (이름/카운트 등이 바뀔 수 있음)
      setSelectedNode((prev) => {
        if (!prev) return null
        const updated = findNodeById(data, prev.id)
        return updated ?? null
      })
    } catch (e) {
      setError(e instanceof Error ? e.message : "로드 실패")
    } finally {
      setLoading(false)
      setRefreshing(false)
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
    [fetchTree],
  )

  const handleDelete = useCallback(
    async (id: number) => {
      await catalogApi.deleteCategory(id)
      await fetchTree()
    },
    [fetchTree],
  )

  const handleUpdate = useCallback(
    async (id: number, data: CategoryUpdateRequest) => {
      await catalogApi.updateCategory(id, data)
      await fetchTree()
    },
    [fetchTree],
  )

  const handleRefresh = useCallback(async () => {
    setRefreshing(true)
    await fetchTree()
  }, [fetchTree])

  const handleSelect = useCallback((node: CategoryNode) => {
    setSelectedNode((prev) => (prev?.id === node.id ? null : node))
    setRightPanel("idle") // bulk 패널 닫고 detail 표시
  }, [])

  const openBulk = useCallback((initialText = "") => {
    setBulkInitialText(initialText)
    setRightPanel("bulk")
    setSelectedNode(null)
  }, [])

  const closeBulk = useCallback(() => {
    setRightPanel("idle")
    setBulkInitialText("")
  }, [])

  return (
    <div className="flex h-full flex-col gap-4 p-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">카테고리 트리</h1>
          <p className="mt-0.5 text-sm text-muted-foreground">
            N-depth 계층 관리 — 드래그&드롭 재구성, 일괄 입력 지원
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-sm hover:bg-muted disabled:opacity-50"
          >
            <RefreshCw className={cn("h-3.5 w-3.5", refreshing && "animate-spin")} />
            새로고침
          </button>
          {/* TEST 데이터 — CATEGORY_TEST_DATA를 bulk 패널에 주입 */}
          <button
            onClick={() => openBulk(CATEGORY_TEST_DATA)}
            className="flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-sm hover:bg-muted"
          >
            <FlaskConical className="h-3.5 w-3.5" />
            TEST 데이터
          </button>
          {/* 일괄 입력 */}
          <button
            onClick={() => openBulk()}
            className={cn(
              "flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-sm hover:bg-muted",
              rightPanel === "bulk" && "bg-muted",
            )}
          >
            <Upload className="h-3.5 w-3.5" />
            일괄 입력
          </button>
          {/* 루트 추가 */}
          <button
            onClick={() => setAddingRoot(true)}
            className="flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground hover:bg-primary/90"
          >
            <Plus className="h-4 w-4" />
            루트 카테고리
          </button>
        </div>
      </div>

      {/* 루트 추가 폼 */}
      {addingRoot && (
        <div className="rounded-lg border border-dashed">
          <AddRootInline
            onAdd={async (name) => {
              await handleAdd(name, null)
              setAddingRoot(false)
            }}
            onCancel={() => setAddingRoot(false)}
          />
        </div>
      )}

      {/* 2컬럼 워크스페이스 */}
      <div className="flex flex-1 gap-4 overflow-hidden">
        {/* 트리 캔버스 */}
        <div className="min-h-0 flex-1 overflow-y-auto rounded-lg border bg-card">
          {loading ? (
            <div className="space-y-2 p-4">
              {[1, 2, 3, 4, 5].map((i) => (
                <div
                  key={i}
                  className="h-6 animate-pulse rounded bg-muted"
                  style={{ width: `${50 + i * 8}%` }}
                />
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
            <div className="p-2">
              <CategoryTreeDnd
                nodes={tree}
                onAdd={handleAdd}
                onDelete={handleDelete}
                onUpdate={handleUpdate}
                onSelect={handleSelect}
                selectedId={selectedNode?.id ?? null}
                onRefresh={fetchTree}
              />
            </div>
          )}
        </div>

        {/* 컨텍스트 패널 */}
        <div className="w-80 shrink-0 overflow-hidden rounded-lg border bg-card">
          {rightPanel === "bulk" ? (
            <BulkImportPanel
              existingTree={tree}
              initialText={bulkInitialText}
              onClose={closeBulk}
              onCommit={fetchTree}
            />
          ) : selectedNode ? (
            <CategoryDetailPanel
              node={selectedNode}
              allNodes={tree}
              onRefresh={fetchTree}
              onDeselect={() => setSelectedNode(null)}
              onAddChild={(parentId) => {
                handleAdd("새 카테고리", parentId).catch(() => null)
              }}
            />
          ) : (
            <div className="flex h-full min-h-40 flex-col items-center justify-center gap-2 p-4 text-muted-foreground">
              <FolderPlus className="h-8 w-8 opacity-30" />
              <p className="text-center text-sm">
                카테고리를 클릭하면 상세 정보를,
                <br />
                &apos;일괄 입력&apos;으로 대량 추가할 수 있습니다.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ── 유틸 ─────────────────────────────────────────────────────────────────────

function findNodeById(nodes: CategoryNode[], id: number): CategoryNode | null {
  for (const node of nodes) {
    if (node.id === id) return node
    if (node.children.length) {
      const found = findNodeById(node.children, id)
      if (found) return found
    }
  }
  return null
}
