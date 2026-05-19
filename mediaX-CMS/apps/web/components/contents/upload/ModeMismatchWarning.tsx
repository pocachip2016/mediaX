"use client"

import { AlertTriangle } from "lucide-react"
import type { TemplateMode } from "./validateAgainstMode"

interface ModeMismatchWarningProps {
  mode: TemplateMode
  reasons: string[]
  onSwitchMode: () => void
  onProceed: () => void
}

export function ModeMismatchWarning({ mode, reasons, onSwitchMode, onProceed }: ModeMismatchWarningProps) {
  const opposite = mode === "series" ? "movie" : "series"

  return (
    <div className="rounded-xl border border-amber-300 bg-amber-50 dark:bg-amber-950/30 dark:border-amber-700 p-4 space-y-3">
      <div className="flex items-start gap-2">
        <AlertTriangle className="h-4 w-4 text-amber-600 mt-0.5 shrink-0" />
        <div className="space-y-1">
          <p className="text-sm font-medium text-amber-800 dark:text-amber-200">
            모드 미스매치 — 선택한 모드: <strong>{mode}</strong>
          </p>
          {reasons.map((r, i) => (
            <p key={i} className="text-xs text-amber-700 dark:text-amber-300">{r}</p>
          ))}
        </div>
      </div>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={onSwitchMode}
          className="text-xs px-3 py-1.5 rounded-lg border border-amber-400 text-amber-800 dark:text-amber-200 hover:bg-amber-100 dark:hover:bg-amber-900/50 transition-colors"
        >
          모드를 {opposite} 로 전환
        </button>
        <button
          type="button"
          onClick={onProceed}
          className="text-xs px-3 py-1.5 rounded-lg bg-amber-600 text-white hover:bg-amber-700 transition-colors"
        >
          그래도 업로드
        </button>
      </div>
    </div>
  )
}
