"use client"

import { useRouter } from "next/navigation"
import { ChevronRight, ArrowLeft } from "lucide-react"

export interface BreadcrumbParent {
  id: number
  title: string
  content_type: string
}

interface BreadcrumbNavProps {
  parents: BreadcrumbParent[]
  /** 직속 부모로 돌아가는 라벨 (예: "시즌으로", "시리즈로") */
  backLabel?: string
}

export function BreadcrumbNav({ parents, backLabel }: BreadcrumbNavProps) {
  const router = useRouter()
  if (parents.length === 0) return null

  const directParent = parents[parents.length - 1]!

  return (
    <div className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400 min-w-0">
      <button
        type="button"
        onClick={() => router.push(`/programming/contents/${directParent.id}`)}
        className="flex items-center gap-1 shrink-0 hover:text-slate-700 dark:hover:text-slate-200 transition-colors"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        {backLabel ?? `${directParent.title}로`}
      </button>
      <span className="text-slate-300 dark:text-slate-600">│</span>
      <nav className="flex items-center gap-1 min-w-0 overflow-hidden">
        {parents.map((p, i) => (
          <span key={p.id} className="flex items-center gap-1 min-w-0">
            <button
              type="button"
              onClick={() => router.push(`/programming/contents/${p.id}`)}
              className="truncate hover:text-slate-700 dark:hover:text-slate-200 hover:underline transition-colors"
              title={p.title}
            >
              {p.title}
            </button>
            {i < parents.length - 1 && (
              <ChevronRight className="h-3 w-3 shrink-0 text-slate-300 dark:text-slate-600" />
            )}
          </span>
        ))}
      </nav>
    </div>
  )
}
