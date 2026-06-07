"use client"

import { useState } from "react"
import { Pencil, Trash2, FolderOpen, Play, BookmarkPlus, Search } from "lucide-react"
import type { CategorySet } from "@/lib/api"
import { ConfirmDialog, InlineRename } from "@/components/catalog/SetDialogs"

const PAGE_SIZE = 10

export function SetListPanel({
  sets,
  onLoad,
  onRename,
  onDelete,
  onSaveAsTemplate,
}: {
  sets: CategorySet[]
  onLoad: (id: number) => Promise<void>
  onRename: (id: number, name: string) => Promise<void>
  onDelete: (id: number) => Promise<void>
  onSaveAsTemplate: (set: CategorySet) => void
}) {
  const [confirmLoad, setConfirmLoad] = useState<CategorySet | null>(null)
  const [renamingId, setRenamingId] = useState<number | null>(null)
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const [searchQuery, setSearchQuery] = useState("")
  const [page, setPage] = useState(0)

  const q = searchQuery.toLowerCase()
  const filteredSets = sets.filter(
    (s) =>
      s.name.toLowerCase().includes(q) ||
      (s.description ?? "").toLowerCase().includes(q),
  )
  const totalPages = Math.ceil(filteredSets.length / PAGE_SIZE)
  const pagedSets = filteredSets.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)

  const handleSearchChange = (v: string) => {
    setSearchQuery(v)
    setPage(0)
  }

  return (
    <>
      <div className="flex h-full flex-col overflow-hidden rounded-lg border bg-card">
        <div className="shrink-0 border-b px-3 py-2.5">
          <p className="text-sm font-medium">카테고리 목록</p>
          <p className="text-xs text-muted-foreground">{sets.length}개 저장됨</p>
        </div>

        {/* 검색 */}
        <div className="shrink-0 border-b px-2 py-1.5">
          <div className="flex items-center gap-1.5 rounded-md border bg-background px-2 py-1">
            <Search className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
            <input
              value={searchQuery}
              onChange={(e) => handleSearchChange(e.target.value)}
              placeholder="제목/설명으로 검색..."
              className="flex-1 bg-transparent text-xs outline-none placeholder:text-muted-foreground"
            />
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-2 space-y-2">
          {pagedSets.length === 0 ? (
            <div className="flex flex-col items-center gap-2 py-8 text-muted-foreground">
              <FolderOpen className="h-8 w-8 opacity-20" />
              <p className="text-xs text-center">
                {searchQuery ? "검색 결과가 없습니다." : "저장된 세트가 없습니다.\n작업 트리를 세트로 저장하세요."}
              </p>
            </div>
          ) : (
            pagedSets.map((s) => (
              <SetCard
                key={s.id}
                set={s}
                isRenaming={renamingId === s.id}
                onLoad={() => setConfirmLoad(s)}
                onRenameStart={() => setRenamingId(s.id)}
                onRenameCancel={() => setRenamingId(null)}
                onRenameSave={async (name) => { await onRename(s.id, name); setRenamingId(null) }}
                onDeleteStart={() => setDeletingId(s.id)}
                onSaveAsTemplate={() => onSaveAsTemplate(s)}
              />
            ))
          )}
        </div>

        {/* 페이지네이션 */}
        {totalPages > 1 && (
          <div className="shrink-0 border-t px-3 py-2 flex items-center justify-between">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              className="rounded p-1 text-muted-foreground hover:text-foreground disabled:opacity-30"
            >
              ←
            </button>
            <p className="text-xs text-muted-foreground">
              {page + 1} / {totalPages}
            </p>
            <button
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              disabled={page >= totalPages - 1}
              className="rounded p-1 text-muted-foreground hover:text-foreground disabled:opacity-30"
            >
              →
            </button>
          </div>
        )}
      </div>

      {/* 작업반영 확정 모달 */}
      {confirmLoad && (
        <ConfirmDialog
          title={`"${confirmLoad.name}" 작업반영`}
          message="세트를 불러오면 현재 작업 트리가 교체됩니다."
          warning="현재 작업 트리의 모든 카테고리가 사라집니다. 필요하면 먼저 현재 트리를 세트로 저장하세요."
          confirmLabel="작업반영"
          onConfirm={() => onLoad(confirmLoad.id)}
          onClose={() => setConfirmLoad(null)}
        />
      )}

      {/* 세트 삭제 확정 모달 */}
      {deletingId !== null && (() => {
        const target = sets.find((s) => s.id === deletingId)
        if (!target) return null
        return (
          <ConfirmDialog
            title={`"${target.name}" 삭제`}
            message={`이 세트와 소속 카테고리 ${target.category_count}개가 삭제됩니다.`}
            confirmLabel="삭제"
            onConfirm={() => onDelete(deletingId)}
            onClose={() => setDeletingId(null)}
          />
        )
      })()}
    </>
  )
}

// ── 세트 카드 ─────────────────────────────────────────────────────────────────

function SetCard({
  set,
  isRenaming,
  onLoad,
  onRenameStart,
  onRenameCancel,
  onRenameSave,
  onDeleteStart,
  onSaveAsTemplate,
}: {
  set: CategorySet
  isRenaming: boolean
  onLoad: () => void
  onRenameStart: () => void
  onRenameCancel: () => void
  onRenameSave: (name: string) => Promise<void>
  onDeleteStart: () => void
  onSaveAsTemplate: () => void
}) {
  const d = set.created_at ? new Date(set.created_at) : null
  const dateStr = d
    ? `${d.getFullYear()}.${String(d.getMonth() + 1).padStart(2, "0")}.${String(d.getDate()).padStart(2, "0")}`
    : "—"

  return (
    <div className="rounded-md border bg-background p-3 space-y-2">
      {/* 이름 행 */}
      <div className="flex items-start justify-between gap-1">
        {isRenaming ? (
          <InlineRename
            initialName={set.name}
            onSave={onRenameSave}
            onCancel={onRenameCancel}
          />
        ) : (
          <p className="text-sm font-medium leading-tight break-all">{set.name}</p>
        )}
        {!isRenaming && (
          <div className="flex shrink-0 items-center gap-0.5">
            <button
              onClick={onSaveAsTemplate}
              title="템플릿으로 저장"
              className="rounded p-1 text-muted-foreground hover:text-foreground hover:bg-muted"
            >
              <BookmarkPlus className="h-3 w-3" />
            </button>
            <button
              onClick={onRenameStart}
              title="이름 변경"
              className="rounded p-1 text-muted-foreground hover:text-foreground hover:bg-muted"
            >
              <Pencil className="h-3 w-3" />
            </button>
            <button
              onClick={onDeleteStart}
              title="삭제"
              className="rounded p-1 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
            >
              <Trash2 className="h-3 w-3" />
            </button>
          </div>
        )}
      </div>

      {/* 설명 */}
      {set.description && (
        <p className="text-xs text-muted-foreground leading-snug">{set.description}</p>
      )}

      {/* 메타 */}
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <span className="font-medium text-foreground">{set.category_count}개</span>
        <span>·</span>
        <span>{dateStr}</span>
      </div>

      {/* 작업반영 버튼 */}
      <button
        onClick={onLoad}
        className="flex w-full items-center justify-center gap-1.5 rounded-md bg-primary/10 py-1.5 text-xs font-medium text-primary hover:bg-primary/20 transition-colors"
      >
        <Play className="h-3 w-3" />
        작업반영
      </button>
    </div>
  )
}
