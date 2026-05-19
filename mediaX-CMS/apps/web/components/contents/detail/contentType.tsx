"use client"

import { Film, Tv, Layers, Play } from "lucide-react"
import { cn } from "@workspace/ui/lib/utils"
import type { ContentType } from "@/lib/api"

export const TYPE_LABEL: Record<ContentType, string> = {
  movie: "영화", series: "시리즈", season: "시즌", episode: "에피소드",
}

export const TYPE_CLASS: Record<ContentType, string> = {
  movie:   "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300",
  series:  "bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300",
  season:  "bg-teal-100 text-teal-700 dark:bg-teal-900/30 dark:text-teal-300",
  episode: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
}

export const LEAF_TYPES: ContentType[] = ["movie", "episode"]
export const CONTAINER_TYPES: ContentType[] = ["series", "season"]

export function isLeafType(t: ContentType): boolean {
  return LEAF_TYPES.includes(t)
}

export function TypeIcon({ type, className }: { type: ContentType; className?: string }) {
  const c = className ?? "h-3.5 w-3.5"
  if (type === "movie") return <Film className={c} />
  if (type === "series") return <Tv className={c} />
  if (type === "season") return <Layers className={c} />
  return <Play className={c} />
}

export function ContentTypeBadge({ type }: { type: ContentType }) {
  return (
    <span className={cn("inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium", TYPE_CLASS[type])}>
      <TypeIcon type={type} />
      {TYPE_LABEL[type]}
    </span>
  )
}
