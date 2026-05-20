"use client"

import { RotateCcw, Lock, Film } from "lucide-react"
import { cn } from "@workspace/ui/lib/utils"
import type { ContentDetail } from "@/lib/api"
import { BreadcrumbNav, type BreadcrumbParent } from "@/components/contents/detail/BreadcrumbNav"
import type { StatusInfo } from "@/components/contents/detail/LeafMetaHeader"

interface DetailHeaderProps {
  content: ContentDetail
  contentId: number
  mode: "view" | "edit" | "review"
  parentChain: BreadcrumbParent[]
  statusInfo: StatusInfo
  onModeChange: (mode: "view" | "edit" | "review") => void
  onReprocess: () => void
  onLock: () => void
  onPreviewClip: () => void
}

const MODE_LABEL: Record<"view" | "edit" | "review", string> = {
  view: "보기",
  edit: "편집",
  review: "검수",
}

export function DetailHeader({
  content, mode, parentChain, statusInfo,
  onModeChange, onReprocess, onLock, onPreviewClip,
}: DetailHeaderProps) {
  return (
    <div className="bg-white border-b border-slate-200 px-6 py-3 space-y-2 sticky top-0 z-10">
      {parentChain.length > 0 && (
        <BreadcrumbNav
          parents={parentChain}
          backLabel={`${parentChain[parentChain.length - 1]!.title}으로`}
        />
      )}
      <div className="flex items-center gap-3 flex-wrap">
        {/* 제목 + 상태 */}
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <h1 className="font-bold text-slate-900 text-base leading-tight truncate">
            {content.title}
          </h1>
          <span
            className={cn(
              "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium flex-shrink-0",
              statusInfo.color,
            )}
          >
            {statusInfo.emoji} {statusInfo.label}
          </span>
          <span className="text-slate-400 text-xs flex-shrink-0">#{content.id}</span>
        </div>

        {/* 모드 토글 */}
        <div className="flex items-center bg-slate-100 rounded-lg p-0.5 gap-0.5">
          {(["view", "edit", "review"] as const).map((m) => (
            <button
              key={m}
              onClick={() => onModeChange(m)}
              className={cn(
                "px-3 py-1.5 rounded-md text-sm font-medium transition-colors",
                mode === m
                  ? "bg-white text-slate-900 shadow-sm"
                  : "text-slate-500 hover:text-slate-700",
              )}
            >
              {MODE_LABEL[m]}
            </button>
          ))}
        </div>

        {/* 액션 버튼 */}
        <div className="flex items-center gap-1.5">
          <button
            onClick={onReprocess}
            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-orange-100 text-orange-700 hover:bg-orange-200 text-xs font-medium"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            AI 재처리
          </button>
          <button
            onClick={onLock}
            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-slate-100 text-slate-700 hover:bg-slate-200 text-xs font-medium"
          >
            <Lock className="h-3.5 w-3.5" />
            잠금
          </button>
          <button
            onClick={onPreviewClip}
            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-blue-100 text-blue-700 hover:bg-blue-200 text-xs font-medium"
          >
            <Film className="h-3.5 w-3.5" />
            Preview
          </button>
        </div>
      </div>
    </div>
  )
}
