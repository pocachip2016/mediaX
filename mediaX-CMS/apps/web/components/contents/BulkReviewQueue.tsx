"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { Loader2, ChevronRight } from "lucide-react"
import { cn } from "@workspace/ui/lib/utils"
import { metadataApi, type StagingItem } from "@/lib/api"

type FilterKey = "all" | "pending" | "inherited" | "conflict"

const FILTER_LABELS: Record<FilterKey, string> = {
  all:       "전체",
  pending:   "검수대기",
  inherited: "상속",
  conflict:  "충돌",
}

const CONTENT_TYPE_KO: Record<string, string> = {
  movie: "영화", series: "시리즈", season: "시즌", episode: "에피소드",
}

interface FlatRow {
  item: StagingItem
  depth: number
  isInherited: boolean
  hasConflict: boolean
}

function flattenItems(items: StagingItem[], depth = 0): FlatRow[] {
  const rows: FlatRow[] = []
  for (const item of items) {
    const isInherited = Object.keys(item.inherited_meta ?? {}).length > 0
    const hasConflict = Object.keys(item.diff ?? {}).length > 0
    rows.push({ item, depth, isInherited, hasConflict })
    if (item.children?.length) {
      rows.push(...flattenItems(item.children, depth + 1))
    }
  }
  return rows
}

function applyFilter(rows: FlatRow[], filter: FilterKey): FlatRow[] {
  if (filter === "all") return rows
  if (filter === "pending") return rows.filter((r) => r.item.content.status === "ai")
  if (filter === "inherited") return rows.filter((r) => r.isInherited)
  if (filter === "conflict") return rows.filter((r) => r.hasConflict)
  return rows
}

interface Props {
  className?: string
}

export function BulkReviewQueue({ className }: Props) {
  const router = useRouter()
  const [rows, setRows] = useState<FlatRow[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<FilterKey>("all")

  useEffect(() => {
    setLoading(true)
    metadataApi.getStaging({ page: 1, size: 200 })
      .then((data) => setRows(flattenItems(data.items)))
      .catch(() => setRows([]))
      .finally(() => setLoading(false))
  }, [])

  const displayed = applyFilter(rows, filter)

  return (
    <div className={cn("bg-white rounded-lg border overflow-hidden", className)}>
      {/* 헤더 + 필터 */}
      <div className="px-4 py-3 border-b flex items-center gap-3 flex-wrap">
        <h3 className="text-sm font-semibold text-slate-700 shrink-0">추천 검수 큐</h3>
        <div className="flex items-center gap-1 ml-auto">
          {(Object.keys(FILTER_LABELS) as FilterKey[]).map((k) => (
            <button
              key={k}
              onClick={() => setFilter(k)}
              className={cn(
                "px-2.5 py-1 rounded-full text-xs font-medium",
                filter === k
                  ? "bg-blue-100 text-blue-700"
                  : "bg-slate-100 text-slate-500 hover:bg-slate-200"
              )}
            >
              {FILTER_LABELS[k]}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-10 text-slate-400">
          <Loader2 className="h-4 w-4 animate-spin mr-2" />로드 중…
        </div>
      ) : displayed.length === 0 ? (
        <p className="py-8 text-center text-sm text-slate-400">항목 없음</p>
      ) : (
        <div className="divide-y divide-slate-100">
          {displayed.map(({ item, depth, isInherited, hasConflict }) => {
            const { content } = item
            const isSeason = content.content_type === "season"
            const autoSkip = isSeason && isInherited

            return (
              <button
                key={content.id}
                onClick={() => {
                  if (!autoSkip) router.push(`/programming/contents/${content.id}?mode=review&return=review`)
                }}
                disabled={autoSkip}
                className={cn(
                  "w-full text-left px-4 py-2.5 flex items-center gap-2 text-sm transition-colors",
                  autoSkip
                    ? "bg-slate-50 cursor-default"
                    : "hover:bg-blue-50 cursor-pointer"
                )}
                style={{ paddingLeft: `${16 + depth * 20}px` }}
              >
                {depth > 0 && (
                  <ChevronRight className="h-3 w-3 text-slate-300 shrink-0" />
                )}
                <span className="text-xs text-slate-400 shrink-0 w-12">
                  {CONTENT_TYPE_KO[content.content_type] ?? content.content_type}
                </span>
                <span className={cn("flex-1 truncate", autoSkip && "text-slate-400")}>
                  {content.title}
                </span>
                {autoSkip && (
                  <span className="text-xs text-slate-400 bg-slate-100 px-2 py-0.5 rounded-full shrink-0">
                    상속(자동)
                  </span>
                )}
                {!autoSkip && hasConflict && (
                  <span className="text-xs text-red-600 bg-red-50 px-2 py-0.5 rounded-full shrink-0">
                    충돌
                  </span>
                )}
                {!autoSkip && !hasConflict && isInherited && (
                  <span className="text-xs text-slate-500 bg-slate-100 px-2 py-0.5 rounded-full shrink-0">
                    상속
                  </span>
                )}
              </button>
            )
          })}
        </div>
      )}

      <div className="px-4 py-2 border-t bg-slate-50 text-xs text-slate-400">
        {displayed.length}건 표시
      </div>
    </div>
  )
}
