"use client"

import { useState } from "react"

interface Props {
  value: string | null
  onSave: (val: string) => Promise<void>
  type?: "text" | "number" | "textarea"
  placeholder?: string
  className?: string
  displayAsBox?: boolean
  alwaysEditing?: boolean
}

export function InlineField({ value, onSave, type = "text", placeholder, className = "", displayAsBox, alwaysEditing }: Props) {
  const [editing, setEditing] = useState(alwaysEditing ?? false)
  const [draft, setDraft] = useState(value ?? "")
  const [saving, setSaving] = useState(false)

  const commit = async () => {
    setSaving(true)
    try { await onSave(draft) } finally { setSaving(false); if (!alwaysEditing) setEditing(false) }
  }

  if (!editing) {
    if (displayAsBox) {
      return (
        <div
          role="button"
          tabIndex={0}
          onClick={() => { setDraft(value ?? ""); setEditing(true) }}
          onKeyDown={(e) => e.key === "Enter" && (setDraft(value ?? ""), setEditing(true))}
          className={`max-h-24 overflow-y-auto text-xs border border-slate-100 rounded px-2 py-1.5 bg-slate-50 whitespace-pre-wrap cursor-text hover:border-blue-300 transition-colors ${className}`}
        >
          {value ?? <span className="text-slate-300 italic">{placeholder ?? "—"}</span>}
        </div>
      )
    }

    return (
      <span
        role="button"
        tabIndex={0}
        onClick={() => { setDraft(value ?? ""); setEditing(true) }}
        onKeyDown={(e) => e.key === "Enter" && (setDraft(value ?? ""), setEditing(true))}
        className={`cursor-text hover:bg-blue-50 hover:text-blue-700 rounded px-1 -mx-1 transition-colors ${className}`}
      >
        {value ?? <span className="text-slate-300 text-xs italic">{placeholder ?? "—"}</span>}
      </span>
    )
  }

  const inputCls = "w-full px-2 py-1 text-xs border border-blue-400 rounded outline-none focus:ring-2 focus:ring-blue-300/40"

  return (
    <span className="flex items-start gap-1 w-full">
      {type === "textarea" ? (
        <textarea
          autoFocus
          rows={3}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder={placeholder}
          className={`${inputCls} resize-none flex-1`}
        />
      ) : (
        <input
          autoFocus
          type={type}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder={placeholder}
          className={`${inputCls} flex-1`}
          onKeyDown={(e) => {
            if (e.key === "Enter") void commit()
            if (e.key === "Escape") setEditing(false)
          }}
        />
      )}
      <span className="flex flex-col gap-0.5 shrink-0">
        <button
          onClick={() => void commit()}
          disabled={saving}
          className="text-[10px] text-blue-600 hover:text-blue-700 font-medium disabled:opacity-50"
        >
          {saving ? "…" : "저장"}
        </button>
        <button
          onClick={() => setEditing(false)}
          className="text-[10px] text-slate-400 hover:text-slate-600"
        >
          취소
        </button>
      </span>
    </span>
  )
}
