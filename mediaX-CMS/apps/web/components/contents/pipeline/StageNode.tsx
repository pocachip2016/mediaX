"use client"

import { StageCount } from "@/lib/api"
import { cn } from "@workspace/ui/lib/utils"

const STAGE_CONFIG: Record<string, { name: string; bgColor: string }> = {
  s1_intake: { name: "S1 INTAKE", bgColor: "bg-blue-100 dark:bg-blue-950" },
  s2_normalize: { name: "S2 NORMALIZE", bgColor: "bg-blue-100 dark:bg-blue-950" },
  s3_llm_extract: { name: "S3 LLM", bgColor: "bg-violet-100 dark:bg-violet-950" },
  s4_source_match: { name: "S4 SOURCE", bgColor: "bg-violet-100 dark:bg-violet-950" },
  s5_gap_detect: { name: "S5 GAP", bgColor: "bg-violet-100 dark:bg-violet-950" },
  s6_websearch_fill: { name: "S6 WEBSEARCH", bgColor: "bg-violet-100 dark:bg-violet-950" },
  s7_staging: { name: "S7 STAGING", bgColor: "bg-amber-100 dark:bg-amber-950" },
  s8_review: { name: "S8 REVIEW", bgColor: "bg-orange-100 dark:bg-orange-950" },
  s9_publish: { name: "S9 PUBLISH", bgColor: "bg-green-100 dark:bg-green-950" },
}

interface StageNodeProps {
  stageId: string
  stats: StageCount
  isSelected?: boolean
  onClick?: () => void
}

export function StageNode({ stageId, stats, isSelected, onClick }: StageNodeProps) {
  const config = STAGE_CONFIG[stageId] || { name: stageId.toUpperCase(), bgColor: "bg-slate-100" }

  return (
    <button
      onClick={onClick}
      className={cn(
        "rounded-lg border-2 px-3 py-2 text-center transition-all",
        isSelected ? "border-slate-900 dark:border-slate-100" : "border-slate-300 dark:border-slate-600",
        config.bgColor
      )}
    >
      <div className="text-xs font-semibold">{config.name}</div>
      <div className="text-lg font-bold">{stats.count}</div>
      {stats.error_count > 0 && <div className="text-xs text-red-600">⚠ {stats.error_count}</div>}
    </button>
  )
}
