"use client"

import { useState, useRef, useEffect } from "react"
import { Save, Trash2, FolderOpen, Pencil, X, Check } from "lucide-react"
import { cn } from "@workspace/ui/lib/utils"
import type { CategorySet } from "@/lib/api"

// ── 저장 모달 ─────────────────────────────────────────────────────────────────

function SaveSetDialog({
  onSave,
  onClose,
}: {
  onSave: (name: string, description?: string) => Promise<void>
  onClose: () => void
}) {
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    setLoading(true)
    try {
      await onSave(name.trim(), description.trim() || undefined)
      onClose()
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="mx-4 w-full max-w-sm rounded-lg border bg-card p-5 shadow-xl">
        <h3 className="font-semibold">세트로 저장</h3>
        <p className="mt-1 text-sm text-muted-foreground">
          현재 작업 트리를 새 세트로 스냅샷합니다. 작업 트리는 유지됩니다.
        </p>
        <form onSubmit={handleSubmit} className="mt-4 space-y-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">세트 이름 *</label>
            <input
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => e.key === "Escape" && onClose()}
              placeholder="예: 2024 개편안"
              disabled={loading}
              className="h-8 w-full rounded border border-border bg-background px-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">설명 (선택)</label>
            <input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="간단한 메모"
              disabled={loading}
              className="h-8 w-full rounded border border-border bg-background px-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
            />
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              className="rounded px-3 py-1.5 text-sm hover:bg-muted disabled:opacity-50"
            >
              취소
            </button>
            <button
              type="submit"
              disabled={loading || !name.trim()}
              className="flex items-center gap-1.5 rounded bg-primary px-3 py-1.5 text-sm text-primary-foreground disabled:opacity-50"
            >
              <Save className="h-3.5 w-3.5" />
              {loading ? "저장 중…" : "저장"}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ── 확정 모달 (load / clear 공용) ─────────────────────────────────────────────

function ConfirmDialog({
  title,
  message,
  warning,
  confirmLabel,
  onConfirm,
  onClose,
}: {
  title: string
  message: string
  warning?: string
  confirmLabel: string
  onConfirm: () => Promise<void>
  onClose: () => void
}) {
  const [loading, setLoading] = useState(false)

  const handleConfirm = async () => {
    setLoading(true)
    try {
      await onConfirm()
      onClose()
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="mx-4 w-full max-w-sm rounded-lg border bg-card p-5 shadow-xl">
        <h3 className="font-semibold">{title}</h3>
        <p className="mt-1 text-sm text-muted-foreground">{message}</p>
        {warning && (
          <div className="mt-3 rounded-md bg-destructive/10 p-3 text-sm text-destructive">
            {warning}
          </div>
        )}
        <div className="mt-4 flex justify-end gap-2">
          <button
            onClick={onClose}
            disabled={loading}
            className="rounded px-3 py-1.5 text-sm hover:bg-muted disabled:opacity-50"
          >
            취소
          </button>
          <button
            onClick={() => void handleConfirm()}
            disabled={loading}
            className="rounded bg-destructive px-3 py-1.5 text-sm text-destructive-foreground hover:bg-destructive/90 disabled:opacity-50"
          >
            {loading ? "처리 중…" : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── 인라인 이름 편집 ──────────────────────────────────────────────────────────

function InlineRename({
  initialName,
  onSave,
  onCancel,
}: {
  initialName: string
  onSave: (name: string) => Promise<void>
  onCancel: () => void
}) {
  const [value, setValue] = useState(initialName)
  const [loading, setLoading] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    inputRef.current?.select()
  }, [])

  const handleSave = async () => {
    if (!value.trim() || value.trim() === initialName) { onCancel(); return }
    setLoading(true)
    try {
      await onSave(value.trim())
    } finally {
      setLoading(false)
    }
  }

  return (
    <form
      onSubmit={(e) => { e.preventDefault(); void handleSave() }}
      className="flex items-center gap-1"
    >
      <input
        ref={inputRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => e.key === "Escape" && onCancel()}
        disabled={loading}
        className="h-6 w-32 rounded border border-ring bg-background px-1.5 text-xs focus:outline-none"
      />
      <button type="submit" disabled={loading} className="text-primary hover:text-primary/80 disabled:opacity-50">
        <Check className="h-3.5 w-3.5" />
      </button>
      <button type="button" onClick={onCancel} className="text-muted-foreground hover:text-foreground">
        <X className="h-3.5 w-3.5" />
      </button>
    </form>
  )
}

// ── SetBar ────────────────────────────────────────────────────────────────────

export function SetBar({
  sets,
  onSave,
  onClear,
  onLoad,
  onRename,
  onDelete,
}: {
  sets: CategorySet[]
  onSave: (name: string, description?: string) => Promise<void>
  onClear: () => Promise<void>
  onLoad: (id: number) => Promise<void>
  onRename: (id: number, name: string) => Promise<void>
  onDelete: (id: number) => Promise<void>
}) {
  const [saveOpen, setSaveOpen] = useState(false)
  const [confirmClear, setConfirmClear] = useState(false)
  const [confirmLoad, setConfirmLoad] = useState<CategorySet | null>(null)
  const [renamingId, setRenamingId] = useState<number | null>(null)
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const [hoveredId, setHoveredId] = useState<number | null>(null)

  return (
    <>
      <div className="flex items-center gap-2 rounded-lg border bg-muted/30 px-3 py-2">
        {/* draft 칩 */}
        <div className="flex items-center gap-1.5 rounded-md bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary ring-1 ring-primary/30">
          <span className="h-1.5 w-1.5 rounded-full bg-primary" />
          작업중 (draft)
        </div>

        {/* 구분선 */}
        {sets.length > 0 && <div className="h-4 w-px bg-border" />}

        {/* 세트 칩 목록 */}
        <div className="flex flex-1 flex-wrap items-center gap-1.5 overflow-x-auto">
          {sets.map((s) => (
            <div
              key={s.id}
              className="group relative flex items-center gap-1"
              onMouseEnter={() => setHoveredId(s.id)}
              onMouseLeave={() => setHoveredId(null)}
            >
              {renamingId === s.id ? (
                <InlineRename
                  initialName={s.name}
                  onSave={async (name) => { await onRename(s.id, name); setRenamingId(null) }}
                  onCancel={() => setRenamingId(null)}
                />
              ) : (
                <button
                  onClick={() => setConfirmLoad(s)}
                  title={s.description ?? undefined}
                  className="flex items-center gap-1 rounded-md border bg-card px-2.5 py-1 text-xs hover:bg-muted"
                >
                  <FolderOpen className="h-3 w-3 text-muted-foreground" />
                  {s.name}
                  <span className="text-muted-foreground">({s.category_count})</span>
                </button>
              )}

              {/* hover 액션 */}
              {hoveredId === s.id && renamingId !== s.id && (
                <div className="flex items-center gap-0.5">
                  <button
                    onClick={() => setRenamingId(s.id)}
                    title="이름 변경"
                    className="rounded p-0.5 text-muted-foreground hover:text-foreground"
                  >
                    <Pencil className="h-3 w-3" />
                  </button>
                  <button
                    onClick={() => setDeletingId(s.id)}
                    title="삭제"
                    className="rounded p-0.5 text-muted-foreground hover:text-destructive"
                  >
                    <Trash2 className="h-3 w-3" />
                  </button>
                </div>
              )}
            </div>
          ))}
          {sets.length === 0 && (
            <span className="text-xs text-muted-foreground">저장된 세트가 없습니다</span>
          )}
        </div>

        {/* 액션 버튼 */}
        <div className="flex shrink-0 items-center gap-1.5">
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

      {/* 저장 모달 */}
      {saveOpen && (
        <SaveSetDialog onSave={onSave} onClose={() => setSaveOpen(false)} />
      )}

      {/* 불러오기 확정 모달 */}
      {confirmLoad && (
        <ConfirmDialog
          title={`"${confirmLoad.name}" 불러오기`}
          message={`세트를 불러오면 현재 작업 트리가 교체됩니다.`}
          warning="현재 작업 트리의 모든 카테고리와 콘텐츠 매핑이 사라집니다. 필요하면 먼저 현재 트리를 저장하세요."
          confirmLabel="불러오기"
          onConfirm={() => onLoad(confirmLoad.id)}
          onClose={() => setConfirmLoad(null)}
        />
      )}

      {/* CLEAR 확정 모달 */}
      {confirmClear && (
        <ConfirmDialog
          title="작업 트리 비우기"
          message="현재 draft 작업 트리를 모두 삭제합니다."
          warning="저장된 세트는 영향받지 않습니다. 되돌릴 수 없습니다."
          confirmLabel="비우기"
          onConfirm={onClear}
          onClose={() => setConfirmClear(false)}
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
