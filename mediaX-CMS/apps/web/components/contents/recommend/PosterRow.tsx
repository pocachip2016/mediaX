"use client"

import { useState } from "react"
import { Film, Sparkles, Star } from "lucide-react"
import { cn } from "@workspace/ui/lib/utils"
import { resolvePosterUrl, type PosterCandidateOut } from "@/lib/api"

function gcd(a: number, b: number): number {
  return b === 0 ? a : gcd(b, a % b)
}

function aspectLabel(w?: number, h?: number): string | null {
  if (!w || !h) return null
  const g = gcd(w, h)
  return `${w / g}:${h / g}`
}

function sourceLabel(source: string): { text: string; cls: string } {
  switch (source.toLowerCase()) {
    case "tmdb":   return { text: "TMDB",   cls: "bg-amber-100 text-amber-700" }
    case "dam":    return { text: "DAM",    cls: "bg-teal-100 text-teal-700" }
    case "cp":
    case "manual": return { text: "CP",     cls: "bg-green-100 text-green-700" }
    default:       return { text: source.toUpperCase(), cls: "bg-slate-100 text-slate-600" }
  }
}

type Props = {
  contentId: number
  candidates: PosterCandidateOut[]
  primaryId: number | null
  onSelectPrimary: (id: number) => Promise<void>
  onRecommend: () => Promise<void>
}

export function PosterRow({ candidates, primaryId, onSelectPrimary, onRecommend }: Props) {
  const [recommending, setRecommending] = useState(false)
  const [selecting, setSelecting] = useState<number | null>(null)
  const [brokenIds, setBrokenIds] = useState<Set<number>>(new Set())

  const primary = candidates.find((c) => c.id === primaryId || c.is_primary) ?? null
  const others = candidates.filter((c) => c.id !== primary?.id)

  async function handleSelectPrimary(id: number) {
    setSelecting(id)
    try { await onSelectPrimary(id) } finally { setSelecting(null) }
  }

  async function handleRecommend() {
    setRecommending(true)
    try { await onRecommend() } finally { setRecommending(false) }
  }

  if (candidates.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 p-8 bg-white rounded-lg border border-dashed border-slate-300">
        <Film className="h-10 w-10 text-slate-300" />
        <p className="text-sm text-slate-400">포스터 후보가 없습니다</p>
        <button
          onClick={handleRecommend}
          disabled={recommending}
          className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-violet-600 text-white text-sm font-medium hover:bg-violet-700 disabled:opacity-50"
        >
          <Sparkles className="h-4 w-4" />
          {recommending ? "AI 추천 중..." : "✨ AI 추천 가져오기"}
        </button>
      </div>
    )
  }

  return (
    <div className="flex flex-row items-start gap-6 p-5 bg-white rounded-lg border">
      {/* Primary 포스터 */}
      <div className="shrink-0">
        <p className="text-xs font-medium text-slate-500 mb-1.5 flex items-center gap-1">
          <Star className="h-3 w-3 fill-amber-400 text-amber-400" /> Primary
        </p>
        <PosterCard
          candidate={primary}
          isBroken={primary ? brokenIds.has(primary.id) : false}
          onBroken={(id) => setBrokenIds((p) => new Set([...p, id]))}
          highlight
        />
      </div>

      {/* 후보 목록 + 액션 */}
      <div className="flex-1 min-w-0">
        <p className="text-xs font-medium text-slate-500 mb-1.5">
          후보 ({others.length})
        </p>
        <div className="flex flex-row gap-2 overflow-x-auto pb-2">
          {others.map((c) => (
            <div key={c.id} className="shrink-0">
              <PosterCard
                candidate={c}
                isBroken={brokenIds.has(c.id)}
                onBroken={(id) => setBrokenIds((p) => new Set([...p, id]))}
              />
              <button
                onClick={() => void handleSelectPrimary(c.id)}
                disabled={selecting === c.id}
                className="mt-1 w-full text-xs text-center text-blue-600 hover:text-blue-700 disabled:opacity-50 truncate"
              >
                {selecting === c.id ? "적용 중..." : "Set Primary"}
              </button>
            </div>
          ))}
        </div>

        <div className="flex items-center gap-2 mt-3">
          <button
            onClick={handleRecommend}
            disabled={recommending}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-violet-100 text-violet-700 text-xs font-medium hover:bg-violet-200 disabled:opacity-50"
          >
            <Sparkles className="h-3.5 w-3.5" />
            {recommending ? "추천 중..." : "✨ AI 추천 가져오기"}
          </button>
        </div>
      </div>
    </div>
  )
}

interface PosterCardProps {
  candidate: PosterCandidateOut | null
  isBroken: boolean
  onBroken: (id: number) => void
  highlight?: boolean
}

function PosterCard({ candidate, isBroken, onBroken, highlight }: PosterCardProps) {
  const src = candidate ? resolvePosterUrl(candidate.url) : null
  const srcLabel = candidate ? sourceLabel(candidate.source) : null
  const aspect = candidate ? aspectLabel(candidate.width, candidate.height) : null

  return (
    <div className={cn("w-[110px] rounded-lg overflow-hidden border-2", highlight ? "border-blue-500" : "border-transparent")}>
      <div className="relative w-full aspect-[2/3] bg-slate-100 flex items-center justify-center">
        {src && !isBroken ? (
          <img
            src={src}
            alt="poster"
            className="w-full h-full object-cover"
            onError={() => candidate && onBroken(candidate.id)}
          />
        ) : (
          <Film className="h-6 w-6 text-slate-300" />
        )}
        {highlight && (
          <span className="absolute top-1 left-1 bg-blue-500 text-white text-[10px] px-1 py-0.5 rounded font-medium">
            Primary
          </span>
        )}
      </div>
      {candidate && (
        <div className="px-1.5 py-1 bg-white space-y-0.5">
          {srcLabel && (
            <span className={cn("inline-block text-[10px] px-1 py-0.5 rounded font-medium", srcLabel.cls)}>
              {srcLabel.text}
            </span>
          )}
          {(candidate.width || aspect) && (
            <p className="text-[10px] text-slate-400 truncate">
              {candidate.width && candidate.height ? `${candidate.width}×${candidate.height}` : ""}{aspect ? ` (${aspect})` : ""}
            </p>
          )}
        </div>
      )}
    </div>
  )
}
