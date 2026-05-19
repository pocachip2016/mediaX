"use client"

import { useRouter } from "next/navigation"
import { cn } from "@workspace/ui/lib/utils"
import type { StagingItem } from "@/lib/api"

const STATUS_LABEL: Record<string, { label: string; cls: string }> = {
  waiting:    { label: "대기",   cls: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400" },
  processing: { label: "처리중", cls: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300" },
  staging:    { label: "검토대기", cls: "bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300" },
  review:     { label: "검수",   cls: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300" },
  approved:   { label: "승인",   cls: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300" },
  rejected:   { label: "반려",   cls: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300" },
}

function StatusPill({ status }: { status: string }) {
  const s = STATUS_LABEL[status] ?? { label: status, cls: "bg-slate-100 text-slate-600" }
  return <span className={cn("px-1.5 py-0.5 rounded text-xs font-medium", s.cls)}>{s.label}</span>
}

interface ChildrenTableProps {
  children: StagingItem[]
  parentType: "series" | "season"
  loading?: boolean
  onAdd?: () => void
}

export function ChildrenTable({ children, parentType, loading, onAdd }: ChildrenTableProps) {
  const router = useRouter()
  const isSeries = parentType === "series"
  const sectionLabel = isSeries ? "시즌 목록" : "에피소드 목록"
  const addLabel = isSeries ? "+ 시즌 추가" : "+ 에피소드 추가"

  return (
    <div className="rounded-xl border border-border overflow-hidden">
      <div className="px-4 py-3 bg-muted/50 border-b border-border flex items-center justify-between">
        <p className="text-sm font-medium">
          ▼ {sectionLabel} {!loading && `(${children.length}건)`}
        </p>
        {onAdd && (
          <button
            type="button"
            onClick={onAdd}
            className="text-xs text-primary hover:underline"
          >
            {addLabel}
          </button>
        )}
      </div>

      {loading ? (
        <div className="px-4 py-10 text-center text-sm text-muted-foreground">불러오는 중...</div>
      ) : children.length === 0 ? (
        <div className="px-4 py-10 text-center text-sm text-muted-foreground">
          등록된 {isSeries ? "시즌" : "에피소드"}이 없습니다
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="bg-muted/30">
              <tr>
                <th className="px-3 py-2 text-left font-medium text-muted-foreground">번호</th>
                <th className="px-3 py-2 text-left font-medium text-muted-foreground">제목</th>
                <th className="px-3 py-2 text-left font-medium text-muted-foreground">상태</th>
                <th className="px-3 py-2 text-left font-medium text-muted-foreground">품질</th>
                <th className="px-3 py-2 text-left font-medium text-muted-foreground">
                  {isSeries ? "에피소드 수" : "런타임"}
                </th>
              </tr>
            </thead>
            <tbody>
              {children.map((item) => {
                const c = item.content
                const num = isSeries
                  ? (c.season_number != null ? `S${String(c.season_number).padStart(2, "0")}` : "—")
                  : (c.episode_number != null ? `E${String(c.episode_number).padStart(2, "0")}` : "—")
                const last = isSeries
                  ? `${item.children.length} 에피소드`
                  : (c.runtime_minutes != null ? `${c.runtime_minutes}분` : "—")
                return (
                  <tr
                    key={c.id}
                    onClick={() => router.push(`/programming/contents/${c.id}`)}
                    className="border-t border-border cursor-pointer hover:bg-accent/40 transition-colors"
                  >
                    <td className="px-3 py-2 font-mono text-muted-foreground">{num}</td>
                    <td className="px-3 py-2 font-medium max-w-[280px] truncate" title={c.title}>{c.title}</td>
                    <td className="px-3 py-2"><StatusPill status={c.status} /></td>
                    <td className="px-3 py-2 text-muted-foreground">
                      {c.quality_score != null ? Math.round(c.quality_score) : "—"}
                    </td>
                    <td className="px-3 py-2 text-muted-foreground">{last}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
