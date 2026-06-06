"use client"

import { useState } from "react"
import { Pencil, Trash2, FolderOpen, Play } from "lucide-react"
import type { CategorySet } from "@/lib/api"
import { ConfirmDialog, InlineRename } from "@/components/catalog/SetDialogs"

export function SetListPanel({
  sets,
  onLoad,
  onRename,
  onDelete,
}: {
  sets: CategorySet[]
  onLoad: (id: number) => Promise<void>
  onRename: (id: number, name: string) => Promise<void>
  onDelete: (id: number) => Promise<void>
}) {
  const [confirmLoad, setConfirmLoad] = useState<CategorySet | null>(null)
  const [renamingId, setRenamingId] = useState<number | null>(null)
  const [deletingId, setDeletingId] = useState<number | null>(null)

  return (
    <>
      <div className="flex h-full flex-col overflow-hidden rounded-lg border bg-card">
        <div className="shrink-0 border-b px-3 py-2.5">
          <p className="text-sm font-medium">저장된 세트</p>
          <p className="text-xs text-muted-foreground">{sets.length}개 저장됨</p>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-2 space-y-2">
          {sets.length === 0 ? (
            <div className="flex flex-col items-center gap-2 py-8 text-muted-foreground">
              <FolderOpen className="h-8 w-8 opacity-20" />
              <p className="text-xs text-center">저장된 세트가 없습니다.<br />작업 트리를 세트로 저장하세요.</p>
            </div>
          ) : (
            sets.map((s) => (
              <SetCard
                key={s.id}
                set={s}
                isRenaming={renamingId === s.id}
                onLoad={() => setConfirmLoad(s)}
                onRenameStart={() => setRenamingId(s.id)}
                onRenameCancel={() => setRenamingId(null)}
                onRenameSave={async (name) => { await onRename(s.id, name); setRenamingId(null) }}
                onDeleteStart={() => setDeletingId(s.id)}
              />
            ))
          )}
        </div>
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
}: {
  set: CategorySet
  isRenaming: boolean
  onLoad: () => void
  onRenameStart: () => void
  onRenameCancel: () => void
  onRenameSave: (name: string) => Promise<void>
  onDeleteStart: () => void
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
