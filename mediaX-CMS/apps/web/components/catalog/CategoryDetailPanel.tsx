"use client"

import { useEffect, useMemo, useState } from "react"
import { Check, ChevronRight, Pencil, Plus, Trash2, X } from "lucide-react"
import { cn } from "@workspace/ui/lib/utils"
import { catalogApi, type CategoryNode } from "@/lib/api"

// ── 브레드크럼 계산 ───────────────────────────────────────────────────────────

function buildBreadcrumb(nodes: CategoryNode[], targetId: number): CategoryNode[] {
  const map = new Map<number, CategoryNode>()
  function flatten(list: CategoryNode[]) {
    for (const n of list) {
      map.set(n.id, n)
      flatten(n.children)
    }
  }
  flatten(nodes)

  const path: CategoryNode[] = []
  let current = map.get(targetId)
  while (current) {
    path.unshift(current)
    current = current.parent_id != null ? map.get(current.parent_id) : undefined
  }
  return path
}

// ── 편집 가능한 필드 행 ───────────────────────────────────────────────────────

function EditableField({
  label,
  value,
  placeholder,
  onSave,
  mono = false,
}: {
  label: string
  value: string
  placeholder: string
  onSave: (v: string) => Promise<void>
  mono?: boolean
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(value)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    setDraft(value)
  }, [value])

  const save = async () => {
    if (draft === value) { setEditing(false); return }
    setSaving(true)
    try {
      await onSave(draft.trim())
      setEditing(false)
    } catch {
      setDraft(value)
      setEditing(false)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-0.5">
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      {editing ? (
        <div className="flex items-center gap-1">
          <input
            autoFocus
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") void save()
              if (e.key === "Escape") { setDraft(value); setEditing(false) }
            }}
            onBlur={() => void save()}
            disabled={saving}
            placeholder={placeholder}
            className={cn(
              "h-7 flex-1 rounded border border-primary bg-background px-2 text-sm focus:outline-none",
              mono && "font-mono text-xs",
            )}
          />
          <button
            onMouseDown={(e) => { e.preventDefault(); void save() }}
            disabled={saving}
            className="flex h-6 w-6 items-center justify-center rounded text-primary hover:bg-primary/10"
          >
            <Check className="h-3 w-3" />
          </button>
          <button
            onMouseDown={(e) => { e.preventDefault(); setDraft(value); setEditing(false) }}
            className="flex h-6 w-6 items-center justify-center rounded text-muted-foreground hover:bg-muted"
          >
            <X className="h-3 w-3" />
          </button>
        </div>
      ) : (
        <button
          onClick={() => setEditing(true)}
          className="group flex w-full items-center justify-between rounded px-1 py-0.5 text-left hover:bg-muted/50"
        >
          <span className={cn("text-sm", mono && "font-mono text-xs", !value && "text-muted-foreground italic")}>
            {value || placeholder}
          </span>
          <Pencil className="h-3 w-3 shrink-0 opacity-0 text-muted-foreground group-hover:opacity-100" />
        </button>
      )}
    </div>
  )
}

// ── 삭제 확인 모달 ────────────────────────────────────────────────────────────

function DeleteConfirmModal({
  node,
  onConfirm,
  onCancel,
}: {
  node: CategoryNode
  onConfirm: (cascade: boolean) => Promise<void>
  onCancel: () => void
}) {
  const [loading, setLoading] = useState(false)
  const hasChildren = node.children.length > 0
  const hasContents = (node.content_count ?? 0) > 0

  const handleDelete = async (cascade: boolean) => {
    setLoading(true)
    try {
      await onConfirm(cascade)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="mx-4 w-full max-w-sm rounded-lg border bg-card p-5 shadow-xl">
        <h3 className="font-semibold">카테고리 삭제</h3>
        <p className="mt-1 text-sm text-muted-foreground">
          <span className="font-medium text-foreground">"{node.name}"</span>을 삭제합니다.
        </p>

        {(hasChildren || hasContents) && (
          <div className="mt-3 rounded-md bg-destructive/10 p-3 text-sm text-destructive">
            {hasChildren && <p>• 하위 카테고리 {node.children.length}개 포함</p>}
            {hasContents && <p>• 연결된 콘텐츠 {node.content_count}건 포함</p>}
            <p className="mt-1 font-medium">하위/콘텐츠까지 모두 삭제하시겠습니까?</p>
          </div>
        )}

        <div className="mt-4 flex justify-end gap-2">
          <button
            onClick={onCancel}
            disabled={loading}
            className="rounded px-3 py-1.5 text-sm hover:bg-muted disabled:opacity-50"
          >
            취소
          </button>
          {(hasChildren || hasContents) ? (
            <>
              <button
                onClick={() => void handleDelete(false)}
                disabled={loading}
                className="rounded border px-3 py-1.5 text-sm text-destructive hover:bg-destructive/10 disabled:opacity-50"
              >
                {loading ? "삭제 중…" : "이 카테고리만"}
              </button>
              <button
                onClick={() => void handleDelete(true)}
                disabled={loading}
                className="rounded bg-destructive px-3 py-1.5 text-sm text-destructive-foreground hover:bg-destructive/90 disabled:opacity-50"
              >
                {loading ? "삭제 중…" : "하위까지 삭제"}
              </button>
            </>
          ) : (
            <button
              onClick={() => void handleDelete(false)}
              disabled={loading}
              className="rounded bg-destructive px-3 py-1.5 text-sm text-destructive-foreground hover:bg-destructive/90 disabled:opacity-50"
            >
              {loading ? "삭제 중…" : "삭제"}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

// ── CategoryDetailPanel ───────────────────────────────────────────────────────

export function CategoryDetailPanel({
  node,
  allNodes,
  onRefresh,
  onDeselect,
  onAddChild,
}: {
  node: CategoryNode
  allNodes: CategoryNode[]
  onRefresh: () => Promise<void>
  onDeselect: () => void
  onAddChild: (parentId: number) => void
}) {
  const [active, setActive] = useState(node.is_active)
  const [togglingActive, setTogglingActive] = useState(false)
  const [deleteModal, setDeleteModal] = useState(false)

  useEffect(() => {
    setActive(node.is_active)
  }, [node.is_active])

  const breadcrumb = useMemo(
    () => buildBreadcrumb(allNodes, node.id),
    [allNodes, node.id],
  )

  const saveName = async (name: string) => {
    if (!name) return
    await catalogApi.updateCategory(node.id, { name })
    await onRefresh()
  }

  const saveSlug = async (slug: string) => {
    await catalogApi.updateCategory(node.id, { slug: slug || null })
    await onRefresh()
  }

  const toggleActive = async () => {
    const next = !active
    setActive(next)
    setTogglingActive(true)
    try {
      await catalogApi.updateCategory(node.id, { is_active: next })
      await onRefresh()
    } catch {
      setActive(!next)
    } finally {
      setTogglingActive(false)
    }
  }

  const handleDelete = async (cascade: boolean) => {
    await catalogApi.deleteCategory(node.id, cascade)
    await onRefresh()
    onDeselect()
    setDeleteModal(false)
  }

  return (
    <>
      {deleteModal && (
        <DeleteConfirmModal
          node={node}
          onConfirm={handleDelete}
          onCancel={() => setDeleteModal(false)}
        />
      )}

      <div className="flex h-full flex-col">
        {/* 헤더 */}
        <div className="flex items-center justify-between border-b px-4 py-3">
          <span className="text-sm font-medium">카테고리 상세</span>
          <button
            onClick={onDeselect}
            className="flex h-5 w-5 items-center justify-center rounded text-muted-foreground hover:bg-muted"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>

        {/* 본문 */}
        <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-4">
          {/* 경로 */}
          {breadcrumb.length > 1 && (
            <div className="flex flex-wrap items-center gap-1 text-xs text-muted-foreground">
              {breadcrumb.slice(0, -1).map((n, i) => (
                <span key={n.id} className="flex items-center gap-1">
                  {i > 0 && <ChevronRight className="h-2.5 w-2.5" />}
                  <span>{n.name}</span>
                </span>
              ))}
              <ChevronRight className="h-2.5 w-2.5" />
              <span className="font-medium text-foreground">{node.name}</span>
            </div>
          )}

          {/* 이름 */}
          <EditableField
            label="이름"
            value={node.name}
            placeholder="카테고리 이름"
            onSave={saveName}
          />

          {/* slug */}
          <EditableField
            label="Slug"
            value={node.slug ?? ""}
            placeholder="(없음)"
            onSave={saveSlug}
            mono
          />

          {/* 메타 정보 */}
          <div className="space-y-1 text-sm text-muted-foreground">
            <div className="flex justify-between">
              <span>Depth</span>
              <span className="font-mono text-xs">{node.depth}</span>
            </div>
            {node.content_count != null && (
              <div className="flex justify-between">
                <span>콘텐츠</span>
                <span>{node.content_count}건</span>
              </div>
            )}
            <div className="flex justify-between">
              <span>하위 카테고리</span>
              <span>{node.children.length}개</span>
            </div>
          </div>

          {/* 활성 토글 */}
          <div className="flex items-center justify-between">
            <span className="text-sm">활성</span>
            <button
              onClick={() => void toggleActive()}
              disabled={togglingActive}
              className={cn(
                "relative inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent transition-colors",
                active ? "bg-primary" : "bg-muted",
                togglingActive && "opacity-50",
              )}
              role="switch"
              aria-checked={active}
            >
              <span
                className={cn(
                  "pointer-events-none block h-4 w-4 rounded-full bg-white shadow-sm transition-transform",
                  active ? "translate-x-4" : "translate-x-0",
                )}
              />
            </button>
          </div>
        </div>

        {/* 하단 액션 */}
        <div className="flex gap-2 border-t p-3">
          <button
            onClick={() => onAddChild(node.id)}
            className="flex flex-1 items-center justify-center gap-1.5 rounded-md border px-2 py-1.5 text-sm hover:bg-muted"
          >
            <Plus className="h-3.5 w-3.5" />
            하위 추가
          </button>
          <button
            onClick={() => setDeleteModal(true)}
            className="flex items-center justify-center gap-1.5 rounded-md border border-destructive/30 px-2 py-1.5 text-sm text-destructive hover:bg-destructive/10"
          >
            <Trash2 className="h-3.5 w-3.5" />
            삭제
          </button>
        </div>
      </div>
    </>
  )
}
