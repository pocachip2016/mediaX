"use client"

import Image from "next/image"
import { Film } from "lucide-react"
import { cn } from "@workspace/ui/lib/utils"
import { resolvePosterUrl, type ContentDetail, type PosterCandidateOut } from "@/lib/api"

interface PosterPanelProps {
  content: ContentDetail
  posterCandidates: PosterCandidateOut[]
  primaryId: number | null
  onSelectPrimary: (id: number) => Promise<void>
  onRecommendPoster: () => Promise<void>
}

export function PosterPanel({
  content,
  posterCandidates,
  primaryId,
  onSelectPrimary,
}: PosterPanelProps) {
  const primary = posterCandidates.find((c) => c.id === primaryId) ?? posterCandidates[0]
  const posterSrc = resolvePosterUrl(primary?.url ?? content.poster_url)

  return (
    <div className="space-y-3">
      {/* 포스터 이미지 */}
      <div className="bg-white rounded-lg border border-slate-200 p-3">
        <div className="w-full aspect-[2/3] rounded-lg overflow-hidden bg-slate-100 flex items-center justify-center shadow-sm">
          {posterSrc ? (
            <Image
              src={posterSrc}
              alt={content.title}
              width={200}
              height={300}
              unoptimized
              className="w-full h-full object-cover"
            />
          ) : (
            <Film className="h-12 w-12 text-slate-300" />
          )}
        </div>
      </div>

      {/* AI 추천 썸네일 */}
      {posterCandidates.length > 0 && (
        <div className="bg-white rounded-lg border border-slate-200 p-3">
          <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide mb-2">
            AI 추천 포스터
          </p>
          <div className="grid grid-cols-2 gap-1.5">
            {posterCandidates.slice(0, 4).map((c) => {
              const src = resolvePosterUrl(c.url)
              return (
                <button
                  key={c.id}
                  onClick={() => void onSelectPrimary(c.id)}
                  className={cn(
                    "aspect-[2/3] rounded overflow-hidden border-2 transition-colors",
                    c.id === primaryId
                      ? "border-blue-500"
                      : "border-slate-200 hover:border-blue-300",
                  )}
                >
                  {src ? (
                    <Image
                      src={src}
                      alt=""
                      width={80}
                      height={120}
                      unoptimized
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div className="w-full h-full bg-slate-100 flex items-center justify-center">
                      <Film className="h-4 w-4 text-slate-300" />
                    </div>
                  )}
                </button>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
