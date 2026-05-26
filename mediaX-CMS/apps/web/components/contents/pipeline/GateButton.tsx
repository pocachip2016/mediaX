"use client"

import { GateInfo } from "@/lib/api"
import { Button } from "@workspace/ui/components/button"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@workspace/ui/components/tooltip"
import { useState } from "react"

interface GateButtonProps {
  gateId: string
  info: GateInfo
  onAdvance?: () => void
  onToggleMode?: (mode: "manual" | "auto") => void
}

export function GateButton({ gateId, info, onAdvance, onToggleMode }: GateButtonProps) {
  const [isToggling, setIsToggling] = useState(false)

  const modeIcon = info.mode === "manual" ? "🔒" : "🤖"
  const modeLabel = info.mode === "manual" ? "Manual" : "Auto"

  const handleToggle = async () => {
    setIsToggling(true)
    try {
      const newMode = info.mode === "manual" ? "auto" : "manual"
      if (confirm(`Change ${gateId} to ${newMode} mode?`)) {
        onToggleMode?.(newMode)
      }
    } finally {
      setIsToggling(false)
    }
  }

  return (
    <TooltipProvider>
      <div className="flex items-center gap-1">
        <Button
          onClick={onAdvance}
          variant="outline"
          size="sm"
          className="text-xs"
        >
          {gateId} ▶ {info.pending}
        </Button>
        <Tooltip>
          <TooltipTrigger asChild>
            <button
              onClick={handleToggle}
              disabled={isToggling}
              className="rounded px-1 py-0.5 hover:bg-slate-200 dark:hover:bg-slate-700"
            >
              {modeIcon}
            </button>
          </TooltipTrigger>
          <TooltipContent>{modeLabel}</TooltipContent>
        </Tooltip>
      </div>
    </TooltipProvider>
  )
}
