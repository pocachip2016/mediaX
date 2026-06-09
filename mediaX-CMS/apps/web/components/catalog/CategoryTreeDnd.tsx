"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useSensor,
  useSensors,
  useDraggable,
  useDroppable,
  type DragEndEvent,
  type DragOverEvent,
  type DragStartEvent,
} from "@dnd-kit/core"
import { ChevronRight, ChevronDown, Plus, Trash2, FolderOpen, Folder, GripVertical, Pencil } from "lucide-react"
import { cn } from "@workspace/ui/lib/utils"
import { catalogApi, type CategoryNode, type CategoryUpdateRequest } from "@/lib/api"

type DropPosition = "before" | "after" | "inside"

interface DropTarget {
  nodeId: number
  position: DropPosition
}

// ── 유틸 ──────────────────────────────────────────────────────────────────────

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
      style={{ paddingLeft: `${(depth + 1) * 20 + 32}px` }}
    >
      <input
        autoFocus
        value={name}
        onChange={(e) => setName(e.target.value)}
        onKeyDown={(e) => e.key === "Escape" && onCancel()}
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
      <button type="button" onClick={onCancel} className="text-xs text-muted-foreground hover:text-foreground">
        취소
      </button>
    </form>
  )
}

// ── 드래그 오버레이 ───────────────────────────────────────────────────────────

function DragOverlayNode({ node }: { node: CategoryNode }) {
  return (
    <div className="flex items-center gap-1.5 rounded-md border border-primary/30 bg-card px-2 py-1.5 text-sm shadow-lg opacity-90">
      <GripVertical className="h-3.5 w-3.5 text-muted-foreground" />
      <Folder className="h-4 w-4 shrink-0 text-amber-500" />
      <span className="max-w-48 truncate">{node.name}</span>
    </div>
  )
}

// ── 드래그 가능한 노드 행 ─────────────────────────────────────────────────────

function DraggableNodeRow({
  node,
  dropTarget,
  onAdd,
  onDelete,
  onUpdate,
  onSelect,
  selectedId,
  isDragActive,
}: {
  node: CategoryNode
  dropTarget: DropTarget | null
  onAdd: (name: string, parentId: number | null) => Promise<void>
  onDelete: (id: number) => Promise<void>
  onUpdate: (id: number, data: CategoryUpdateRequest) => Promise<void>
  onSelect: (node: CategoryNode) => void
  selectedId: number | null
  isDragActive: boolean
}) {
  const [expanded, setExpanded] = useState(true)
  const [addingChild, setAddingChild] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [renaming, setRenaming] = useState(false)
  const [renameName, setRenameName] = useState(node.name)

  const { attributes, listeners, setNodeRef: setDragRef, isDragging } = useDraggable({
    id: String(node.id),
  })
  const { setNodeRef: setDropRef } = useDroppable({ id: String(node.id) })

  const hasChildren = node.children.length > 0
  const dropPos = dropTarget?.nodeId === node.id ? dropTarget.position : null

  // node.name이 서버에서 바뀌면 rename 입력값도 동기화
  useEffect(() => { setRenameName(node.name) }, [node.name])

  const handleDelete = async () => {
    if (!confirm(`"${node.name}" 카테고리를 삭제할까요?`)) return
    setDeleting(true)
    try {
      await onDelete(node.id)
    } finally {
      setDeleting(false)
    }
  }

  const saveRename = async () => {
    const trimmed = renameName.trim()
    if (!trimmed || trimmed === node.name) {
      setRenaming(false)
      setRenameName(node.name)
      return
    }
    try {
      await onUpdate(node.id, { name: trimmed })
    } catch {
      setRenameName(node.name)
    } finally {
      setRenaming(false)
    }
  }

  return (
    <div>
      {/* before 인디케이터 */}
      {dropPos === "before" && (
        <div
          className="my-0.5 h-0.5 rounded-full bg-primary"
          style={{ marginLeft: `${node.depth * 20 + 28}px`, marginRight: "4px" }}
        />
      )}

      <div
        ref={setDropRef}
        className={cn(
          "group relative flex cursor-default select-none items-center gap-1 rounded px-2 py-1 text-sm transition-colors",
          "hover:bg-muted/50",
          selectedId === node.id && "bg-muted",
          !node.is_active && "opacity-50",
          isDragging && "opacity-25",
          dropPos === "inside" && "bg-primary/10 outline outline-1 -outline-offset-1 outline-primary",
        )}
        style={{ paddingLeft: `${node.depth * 20 + 8}px` }}
        onClick={() => onSelect(node)}
      >
        {/* 펼치기/접기 */}
        <button
          onClick={(e) => { e.stopPropagation(); setExpanded((v) => !v) }}
          disabled={!hasChildren}
          className="flex h-4 w-4 items-center justify-center text-muted-foreground"
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

        {/* 이름 (더블클릭 → 인라인 rename) */}
        {renaming ? (
          <input
            autoFocus
            value={renameName}
            onChange={(e) => setRenameName(e.target.value)}
            onBlur={() => void saveRename()}
            onKeyDown={(e) => {
              if (e.key === "Enter") { e.preventDefault(); void saveRename() }
              if (e.key === "Escape") { setRenaming(false); setRenameName(node.name) }
              e.stopPropagation()
            }}
            onClick={(e) => e.stopPropagation()}
            className="h-6 flex-1 rounded border border-primary bg-background px-1 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
          />
        ) : (
          <span
            className="flex-1 truncate"
            onDoubleClick={(e) => { e.stopPropagation(); setRenaming(true) }}
          >
            {node.name}
          </span>
        )}

        {/* 콘텐츠 수 */}
        {node.content_count != null && (
          <span className="text-xs text-muted-foreground">({node.content_count})</span>
        )}

        {/* hover 액션 (드래그 중 또는 rename 중엔 숨김) */}
        {!isDragActive && !renaming && (
          <div className="ml-1 flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
            <button
              onClick={(e) => { e.stopPropagation(); setRenaming(true) }}
              title="이름 변경"
              className="flex h-5 w-5 items-center justify-center rounded text-muted-foreground hover:bg-accent hover:text-foreground"
            >
              <Pencil className="h-3 w-3" />
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); setAddingChild(true) }}
              title="하위 추가"
              className="flex h-5 w-5 items-center justify-center rounded text-muted-foreground hover:bg-accent hover:text-foreground"
            >
              <Plus className="h-3 w-3" />
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); void handleDelete() }}
              disabled={deleting}
              title="삭제"
              className="flex h-5 w-5 items-center justify-center rounded text-muted-foreground hover:bg-destructive/10 hover:text-destructive disabled:opacity-50"
            >
              <Trash2 className="h-3 w-3" />
            </button>
          </div>
        )}

        {/* 드래그 핸들 */}
        <button
          ref={setDragRef}
          {...attributes}
          {...listeners}
          onClick={(e) => e.stopPropagation()}
          title="드래그로 이동"
          className="ml-1 flex h-5 w-5 cursor-grab items-center justify-center rounded opacity-0 transition-opacity group-hover:opacity-100 hover:bg-accent active:cursor-grabbing"
        >
          <GripVertical className="h-3 w-3 text-muted-foreground" />
        </button>
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
          <DraggableNodeRow
            key={child.id}
            node={child}
            dropTarget={dropTarget}
            onAdd={onAdd}
            onDelete={onDelete}
            onUpdate={onUpdate}
            onSelect={onSelect}
            selectedId={selectedId}
            isDragActive={isDragActive}
          />
        ))}

      {/* after 인디케이터 */}
      {dropPos === "after" && (
        <div
          className="my-0.5 h-0.5 rounded-full bg-primary"
          style={{ marginLeft: `${node.depth * 20 + 28}px`, marginRight: "4px" }}
        />
      )}
    </div>
  )
}

// ── 트리 DnD 래퍼 ─────────────────────────────────────────────────────────────

export function CategoryTreeDnd({
  nodes,
  onAdd,
  onDelete,
  onUpdate,
  onSelect,
  selectedId,
  onRefresh,
}: {
  nodes: CategoryNode[]
  onAdd: (name: string, parentId: number | null) => Promise<void>
  onDelete: (id: number) => Promise<void>
  onUpdate: (id: number, data: CategoryUpdateRequest) => Promise<void>
  onSelect: (node: CategoryNode) => void
  selectedId: number | null
  onRefresh: () => Promise<void>
}) {
  const [activeNode, setActiveNode] = useState<CategoryNode | null>(null)
  const [dropTarget, setDropTarget] = useState<DropTarget | null>(null)
  const dropTargetRef = useRef<DropTarget | null>(null)
  const pointerYRef = useRef(0)

  // 포인터 Y 좌표 추적 (드롭 위치 before/after/inside 계산용)
  useEffect(() => {
    const track = (e: PointerEvent) => { pointerYRef.current = e.clientY }
    window.addEventListener("pointermove", track)
    return () => window.removeEventListener("pointermove", track)
  }, [])

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
  )

  const handleDragStart = useCallback(
    (event: DragStartEvent) => {
      const node = findNodeById(nodes, Number(event.active.id))
      setActiveNode(node)
      setDropTarget(null)
      dropTargetRef.current = null
    },
    [nodes],
  )

  const handleDragOver = useCallback((event: DragOverEvent) => {
    const { over } = event
    if (!over) {
      setDropTarget(null)
      dropTargetRef.current = null
      return
    }
    const nodeId = Number(over.id)
    if (isNaN(nodeId)) return

    const rect = over.rect
    const y = pointerYRef.current
    const ratio = (y - rect.top) / rect.height

    const position: DropPosition =
      ratio < 0.25 ? "before" : ratio > 0.75 ? "after" : "inside"

    const target: DropTarget = { nodeId, position }
    setDropTarget(target)
    dropTargetRef.current = target
  }, [])

  const handleDragEnd = useCallback(
    async (event: DragEndEvent) => {
      const { active, over } = event
      const current = dropTargetRef.current
      setActiveNode(null)
      setDropTarget(null)
      dropTargetRef.current = null

      if (!over || !current) return
      const draggedId = Number(active.id)
      const { nodeId: targetId, position } = current
      if (draggedId === targetId) return

      const targetNode = findNodeById(nodes, targetId)
      if (!targetNode) return

      let new_parent_id: number | null
      let new_sort_order: number | null = null

      if (position === "inside") {
        new_parent_id = targetId
      } else {
        new_parent_id = targetNode.parent_id ?? null
        new_sort_order =
          position === "before" ? targetNode.sort_order : targetNode.sort_order + 1
      }

      try {
        await catalogApi.moveCategory(draggedId, { new_parent_id, new_sort_order })
        await onRefresh()
      } catch (err) {
        const msg = err instanceof Error ? err.message : "이동 실패"
        // eslint-disable-next-line no-console
        console.error("move_category failed:", msg)
        await onRefresh() // 서버 상태로 롤백
        alert(`이동 실패: ${msg}`)
      }
    },
    [nodes, onRefresh],
  )

  if (nodes.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
        <Folder className="mb-3 h-10 w-10 opacity-30" />
        <p className="text-sm">카테고리 없음 — 루트 카테고리를 추가하거나 일괄 입력을 사용하세요.</p>
      </div>
    )
  }

  return (
    <DndContext
      sensors={sensors}
      onDragStart={handleDragStart}
      onDragOver={handleDragOver}
      onDragEnd={handleDragEnd}
    >
      <div className="space-y-0.5">
        {nodes.map((node) => (
          <DraggableNodeRow
            key={node.id}
            node={node}
            dropTarget={dropTarget}
            onAdd={onAdd}
            onDelete={onDelete}
            onUpdate={onUpdate}
            onSelect={onSelect}
            selectedId={selectedId}
            isDragActive={activeNode !== null}
          />
        ))}
      </div>
      <DragOverlay dropAnimation={null}>
        {activeNode && <DragOverlayNode node={activeNode} />}
      </DragOverlay>
    </DndContext>
  )
}
