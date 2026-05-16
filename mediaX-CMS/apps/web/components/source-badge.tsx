import { cn } from "@workspace/ui/lib/utils"

const SOURCE_COLORS: Record<string, string> = {
  cp:    "bg-slate-100 text-slate-700",
  ai:    "bg-purple-100 text-purple-700",
  tmdb:  "bg-blue-100 text-blue-700",
  kobis: "bg-green-100 text-green-700",
}

interface SourceBadgeProps {
  source: string
  score?: number | null
  className?: string
}

export function SourceBadge({ source, score, className }: SourceBadgeProps) {
  const key = source.toLowerCase()
  const color = SOURCE_COLORS[key] ?? "bg-slate-100 text-slate-600"
  return (
    <span className={cn("inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[11px] font-semibold uppercase tracking-wide", color, className)}>
      {source}
      {score != null && <span className="font-normal opacity-70 normal-case">·{score}</span>}
    </span>
  )
}
