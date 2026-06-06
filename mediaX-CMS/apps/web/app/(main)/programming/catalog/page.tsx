"use client"

import { useEffect, useState, useCallback } from "react"
import { RefreshCw, Save, Trash2 } from "lucide-react"
import { cn } from "@workspace/ui/lib/utils"
import { catalogApi, type CategoryNode, type CategorySet, type CategoryCreateRequest, type CategoryUpdateRequest } from "@/lib/api"
import { CategoryTreeDnd } from "@/components/catalog/CategoryTreeDnd"
import { CategoryDetailPanel } from "@/components/catalog/CategoryDetailPanel"
import { InputPanel } from "@/components/catalog/InputPanel"
import { SetListPanel } from "@/components/catalog/SetListPanel"
import { SaveSetDialog, ConfirmDialog } from "@/components/catalog/SetDialogs"

// ── 페이지 ────────────────────────────────────────────────────────────────────

export default function CatalogCategoryPage() {
  const [tree, setTree] = useState<CategoryNode[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedNode, setSelectedNode] = useState<CategoryNode | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [sets, setSets] = useState<CategorySet[]>([])
  const [saveOpen, setSaveOpen] = useState(false)
  const [confirmClear, setConfirmClear] = useState(false)

  const fetchTree = useCallback(async () => {
    try {
      setError(null)
      const data = await catalogApi.getTree({ counts: true })
      setTree(data)
      setSelectedNode((prev) => {
        if (!prev) return null
        return findNodeById(data, prev.id) ?? null
      })
    } catch (e) {
      setError(e instanceof Error ? e.message : "로드 실패")
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  const fetchSets = useCallback(async () => {
    try {
      const data = await catalogApi.listSets()
      setSets(data)
    } catch {
      // 세트 로드 실패는 트리 작업에 영향 없음
    }
  }, [])

  useEffect(() => {
    void fetchTree()
    void fetchSets()
  }, [fetchTree, fetchSets])

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
    await Promise.all([fetchTree(), fetchSets()])
  }, [fetchTree, fetchSets])

  const handleSaveSet = useCallback(
    async (name: string, description?: string) => {
      await catalogApi.commitSet({ name, description })
      await Promise.all([fetchTree(), fetchSets()])
    },
    [fetchTree, fetchSets],
  )

  const handleClearDraft = useCallback(async () => {
    await catalogApi.clearDraft()
    await fetchTree()
    setSelectedNode(null)
  }, [fetchTree])

  const handleLoadSet = useCallback(
    async (id: number) => {
      await catalogApi.loadSet(id)
      await Promise.all([fetchTree(), fetchSets()])
      setSelectedNode(null)
    },
    [fetchTree, fetchSets],
  )

  const handleRenameSet = useCallback(
    async (id: number, name: string) => {
      await catalogApi.updateSet(id, { name })
      await fetchSets()
    },
    [fetchSets],
  )

  const handleDeleteSet = useCallback(
    async (id: number) => {
      await catalogApi.deleteSet(id)
      await fetchSets()
    },
    [fetchSets],
  )

  const handleSelect = useCallback((node: CategoryNode) => {
    setSelectedNode((prev) => (prev?.id === node.id ? null : node))
  }, [])

  return (
    <div className="flex h-full flex-col gap-3 p-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">카테고리 트리</h1>
          <p className="mt-0.5 text-sm text-muted-foreground">
            N-depth 계층 관리 — 드래그&amp;드롭 재구성, 일괄 입력 지원
          </p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-sm hover:bg-muted disabled:opacity-50"
        >
          <RefreshCw className={cn("h-3.5 w-3.5", refreshing && "animate-spin")} />
          새로고침
        </button>
      </div>

      {/* 3컬럼 워크스페이스 */}
      <div className="flex flex-1 gap-3 overflow-hidden">
        {/* 좌: 입력 패널 */}
        <div className="w-72 shrink-0">
          <InputPanel
            existingTree={tree}
            onCommit={fetchTree}
            onAddRoot={(name) => handleAdd(name, null)}
          />
        </div>

        {/* 중: Draft 작업트리 */}
        <div className="flex min-h-0 flex-1 flex-col gap-2">
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
                  onClick={() => { setLoading(true); void fetchTree() }}
                  className="text-muted-foreground underline hover:text-foreground"
                >
                  다시 시도
                </button>
              </div>
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
              <div className="p-2">
                <CategoryTreeDnd
                  nodes={tree}
                  onAdd={handleAdd}
                  onDelete={handleDelete}
                  onUpdate={handleUpdate}
                  onSelect={handleSelect}
                  selectedId={null}
                  onRefresh={fetchTree}
                />
              </div>
            )}
          </div>

          {/* Draft 하단 액션 바 */}
          <div className="flex shrink-0 items-center justify-between rounded-lg border bg-muted/30 px-3 py-2">
            <div className="flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-primary" />
              <span className="text-xs font-medium text-primary">작업중 (draft)</span>
            </div>
            <div className="flex items-center gap-1.5">
              {selectedNode && (
                <button
                  onClick={() => setSelectedNode(null)}
                  className="rounded border px-2.5 py-1 text-xs hover:bg-muted"
                >
                  트리로 돌아가기
                </button>
              )}
              <button
                onClick={() => setSaveOpen(true)}
                className="flex items-center gap-1 rounded-md border bg-card px-2.5 py-1 text-xs hover:bg-muted"
              >
                <Save className="h-3 w-3" />
                세트로 저장
              </button>
              <button
                onClick={() => setConfirmClear(true)}
                className="flex items-center gap-1 rounded-md border px-2.5 py-1 text-xs text-destructive hover:bg-destructive/10"
              >
                <Trash2 className="h-3 w-3" />
                CLEAR
              </button>
            </div>
          </div>
        </div>

        {/* 우: 저장된 세트 목록 */}
        <div className="w-80 shrink-0">
          <SetListPanel
            sets={sets}
            onLoad={handleLoadSet}
            onRename={handleRenameSet}
            onDelete={handleDeleteSet}
          />
        </div>
      </div>

      {/* 저장 모달 */}
      {saveOpen && (
        <SaveSetDialog onSave={handleSaveSet} onClose={() => setSaveOpen(false)} />
      )}

      {/* CLEAR 확정 모달 */}
      {confirmClear && (
        <ConfirmDialog
          title="작업 트리 비우기"
          message="현재 draft 작업 트리를 모두 삭제합니다."
          warning="저장된 세트는 영향받지 않습니다. 되돌릴 수 없습니다."
          confirmLabel="비우기"
          onConfirm={handleClearDraft}
          onClose={() => setConfirmClear(false)}
        />
      )}
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
