"use client"

import { cn } from "@workspace/ui/lib/utils"
import type { TemplateMode } from "./validateAgainstMode"

interface TemplateModeToggleProps {
  value: TemplateMode
  onChange: (mode: TemplateMode) => void
}

export function TemplateModeToggle({ value, onChange }: TemplateModeToggleProps) {
  return (
    <div>
      <p className="text-sm font-semibold mb-3">① 템플릿 선택</p>
      <div className="grid grid-cols-2 gap-3">
        <button
          type="button"
          onClick={() => onChange("movie")}
          className={cn(
            "flex flex-col items-start gap-1 rounded-xl border-2 p-4 text-left transition-colors",
            value === "movie"
              ? "border-primary bg-primary/5"
              : "border-border hover:border-primary/40 hover:bg-accent/30",
          )}
        >
          <p className="font-medium">🎬 영화 (Movie)</p>
          <p className="text-xs text-muted-foreground">평면 영화 일괄 업로드</p>
          <p className="text-xs text-muted-foreground">1 행 = 1 영화</p>
        </button>

        <button
          type="button"
          onClick={() => onChange("series")}
          className={cn(
            "flex flex-col items-start gap-1 rounded-xl border-2 p-4 text-left transition-colors",
            value === "series"
              ? "border-primary bg-primary/5"
              : "border-border hover:border-primary/40 hover:bg-accent/30",
          )}
        >
          <p className="font-medium">📺 시리즈 (Series)</p>
          <p className="text-xs text-muted-foreground">series → season → episode</p>
          <p className="text-xs text-muted-foreground">계층 일괄 업로드</p>
        </button>
      </div>
    </div>
  )
}
