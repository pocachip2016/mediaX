"use client"

import React, { useState, useEffect } from "react"
import { ChevronRight, Pencil, Trash2, Play, Search, FolderOpen } from "lucide-react"
import { cn } from "@workspace/ui/lib/utils"
import { catalogApi, type CategorySet, type CategoryNode, type DupPolicy } from "@/lib/api"
import { serializeTree } from "@/lib/customTemplates"
import { ConfirmDialog, InlineRename } from "@/components/catalog/SetDialogs"

type LoadMode = "replace" | "merge"

const PAGE_SIZE = 10

export function SetListPanel({
  sets,
  onLoad,
  onRename,
  onDelete,
  onSaveAsTemplate,
}: {
  sets: CategorySet[]
  onLoad: (id: number, opts?: { mode?: LoadMode; dup_policy?: DupPolicy }) => Promise<void>
  onRename: (id: number, name: string) => Promise<void>
  onDelete: (id: number) => Promise<void>
  onSaveAsTemplate: (set: CategorySet) => void
}) {
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [renamingId, setRenamingId] = useState<number | null>(null)
  const [confirmLoad, setConfirmLoad] = useState<CategorySet | null>(null)
  const [loadMode, setLoadMode] = useState<LoadMode>("replace")
  const [loadDupPolicy, setLoadDupPolicy] = useState<DupPolicy>("merge")
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

  const handleRowClick = (id: number) => {
    setSelectedId((prev) => (prev === id ? null : id))
    setRenamingId(null)
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

        <div className="min-h-0 flex-1 overflow-y-auto py-1">
          {pagedSets.length === 0 ? (
            <div className="flex flex-col items-center gap-2 py-8 text-muted-foreground">
              <FolderOpen className="h-8 w-8 opacity-20" />
              <p className="text-xs text-center">
                {searchQuery ? "검색 결과가 없습니다." : "저장된 세트가 없습니다."}
              </p>
            </div>
          ) : (
            pagedSets.map((s) => (
              <SetRow
                key={s.id}
                set={s}
                isSelected={selectedId === s.id}
                isRenaming={renamingId === s.id}
                onSelect={() => handleRowClick(s.id)}
                onLoad={() => setConfirmLoad(s)}
                onRenameStart={() => { setRenamingId(s.id); setSelectedId(s.id) }}
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
          message="세트를 불러올 방식을 선택하세요."
          warning={loadMode === "replace" ? "현재 작업 트리의 모든 카테고리가 사라집니다. 필요하면 먼저 현재 트리를 카테고리저장하세요." : undefined}
          confirmLabel="작업반영"
          onConfirm={() => onLoad(confirmLoad.id, { mode: loadMode, dup_policy: loadMode === "merge" ? loadDupPolicy : undefined })}
          onClose={() => setConfirmLoad(null)}
          extra={
            <div className="space-y-2 text-xs">
              <div className="flex rounded-md border overflow-hidden">
                {(["replace", "merge"] as const).map((m) => (
                  <button
                    key={m}
                    type="button"
                    onClick={() => setLoadMode(m)}
                    className={cn(
                      "flex-1 py-1.5 text-xs font-medium transition-colors",
                      loadMode === m ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted",
                    )}
                  >
                    {m === "replace" ? "전체교체" : "병합"}
                  </button>
                ))}
              </div>
              {loadMode === "merge" && (
                <div className="flex rounded-md border overflow-hidden">
                  {(["merge", "overwrite", "reject"] as const).map((p) => (
                    <button
                      key={p}
                      type="button"
                      onClick={() => setLoadDupPolicy(p)}
                      className={cn(
                        "flex-1 py-1.5 text-xs font-medium transition-colors",
                        loadDupPolicy === p ? "bg-secondary text-secondary-foreground" : "text-muted-foreground hover:bg-muted",
                      )}
                    >
                      {p === "merge" ? "중복skip" : p === "overwrite" ? "덮어쓰기" : "거부"}
                    </button>
                  ))}
                </div>
              )}
            </div>
          }
        />
      )}

      {/* 삭제 확정 모달 */}
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

// ── 목록 행 ───────────────────────────────────────────────────────────────────

function SetRow({
  set,
  isSelected,
  isRenaming,
  onSelect,
  onLoad,
  onRenameStart,
  onRenameCancel,
  onRenameSave,
  onDeleteStart,
  onSaveAsTemplate,
}: {
  set: CategorySet
  isSelected: boolean
  isRenaming: boolean
  onSelect: () => void
  onLoad: () => void
  onRenameStart: () => void
  onRenameCancel: () => void
  onRenameSave: (name: string) => Promise<void>
  onDeleteStart: () => void
  onSaveAsTemplate: () => void
}) {
  const [treeText, setTreeText] = useState<string | null>(null)
  const [treeLoading, setTreeLoading] = useState(false)

  useEffect(() => {
    if (!isSelected) return
    if (treeText !== null) return
    setTreeLoading(true)
    catalogApi
      .getSetTree(set.id)
      .then((nodes: CategoryNode[]) => setTreeText(serializeTree(nodes) || "(비어 있음)"))
      .catch(() => setTreeText("⚠ 트리 로드 실패"))
      .finally(() => setTreeLoading(false))
  }, [isSelected, set.id, treeText])

  const d = set.created_at ? new Date(set.created_at) : null
  const dateStr = d
    ? `${String(d.getMonth() + 1).padStart(2, "0")}.${String(d.getDate()).padStart(2, "0")}`
    : "—"

  return (
    <div>
      {/* 단일 행 */}
      <button
        onClick={onSelect}
        className={cn(
          "flex w-full items-center gap-1.5 px-2 py-1.5 text-left transition-colors hover:bg-muted/60",
          isSelected && "bg-muted",
        )}
      >
        <ChevronRight
          className={cn(
            "h-3 w-3 shrink-0 text-muted-foreground transition-transform",
            isSelected && "rotate-90",
          )}
        />
        <span className="flex-1 truncate text-sm">{set.name}</span>
        <span className="shrink-0 text-xs text-muted-foreground">{set.category_count}개</span>
        <span className="shrink-0 text-xs text-muted-foreground">{dateStr}</span>
      </button>

      {/* 인라인 미리보기 */}
      {isSelected && (
        <div className="mx-2 mb-1 rounded-md border bg-background">
          {/* 액션 바 */}
          {isRenaming ? (
            <div className="p-2">
              <InlineRename
                initialName={set.name}
                onSave={onRenameSave}
                onCancel={onRenameCancel}
              />
            </div>
          ) : (
            <div className="flex items-center gap-1.5 border-b px-2 py-1.5">
              {/* 템플릿저장 — 가장 왼쪽 */}
              <button
                onClick={onSaveAsTemplate}
                className="flex items-center gap-0.5 rounded border px-2 py-0.5 text-xs text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
              >
                <Play className="h-3 w-3 scale-x-[-1]" />
                템플릿저장
              </button>
              {/* 편집 액션 */}
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
              {/* 작업반영 — 오른쪽 끝 */}
              <button
                onClick={onLoad}
                className="ml-auto flex items-center gap-1 rounded bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary hover:bg-primary/20 transition-colors"
              >
                <Play className="h-3 w-3" />
                작업반영
              </button>
            </div>
          )}

          {/* 트리 미리보기 */}
          <div className="max-h-52 overflow-y-auto p-2">
            {set.description && (
              <p className="mb-1.5 text-[10px] text-muted-foreground leading-snug">{set.description}</p>
            )}
            {treeLoading ? (
              <p className="text-[10px] text-muted-foreground animate-pulse">로딩 중…</p>
            ) : (
              <pre className="whitespace-pre font-mono text-[10px] leading-[1.6] text-foreground/80">
                {treeText}
              </pre>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
