"use client"

import { useState, useRef, useEffect } from "react"
import { Save, X, Check } from "lucide-react"

// ── 저장 모달 ─────────────────────────────────────────────────────────────────

export function SaveSetDialog({
  onSave,
  onClose,
  title,
  subtitle,
  initialName,
}: {
  onSave: (name: string, description?: string) => Promise<void>
  onClose: () => void
  title?: string
  subtitle?: string
  initialName?: string
}) {
  const [name, setName] = useState(initialName ?? "")
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
        <h3 className="font-semibold">{title ?? "세트로 저장"}</h3>
        <p className="mt-1 text-sm text-muted-foreground">
          {subtitle ?? "현재 작업 트리를 새 세트로 스냅샷합니다. 작업 트리는 유지됩니다."}
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

// ── 확정 모달 (load / clear / delete 공용) ────────────────────────────────────

export function ConfirmDialog({
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

export function InlineRename({
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
