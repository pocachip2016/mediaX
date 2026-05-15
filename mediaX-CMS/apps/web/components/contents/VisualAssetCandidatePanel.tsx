"use client"

import { useState } from "react"
import { Film, RefreshCw } from "lucide-react"
import { cn } from "@workspace/ui/lib/utils"
import { resolvePosterUrl, type PosterCandidateOut } from "@/lib/api"

type RightsBadge = { label: string; tone: "green" | "amber" | "blue" | "teal" | "slate" }

function rightsBadge(source: string): RightsBadge {
  switch (source.toLowerCase()) {
    case "cp":     return { label: "CP Provided", tone: "green" }
    case "manual": return { label: "CP Provided", tone: "green" }
    case "tmdb":   return { label: "External", tone: "amber" }
    case "dam":    return { label: "Internal OK", tone: "teal" }
    default:       return { label: "Review", tone: "slate" }
  }
}

const TONE_CLASS: Record<RightsBadge["tone"], string> = {
  green: "bg-green-100 text-green-700",
  amber: "bg-amber-100 text-amber-700",
  blue:  "bg-blue-100 text-blue-700",
  teal:  "bg-teal-100 text-teal-700",
  slate: "bg-slate-100 text-slate-600",
}

function aspectLabel(w?: number, h?: number): string | null {
  if (!w || !h) return null
  const g = gcd(w, h)
  return `${w / g}:${h / g}`
}

function gcd(a: number, b: number): number {
  return b === 0 ? a : gcd(b, a % b)
}

type Props = {
  contentId: number
  candidates: PosterCandidateOut[]
  primaryId: number | null
  onRecommend(): Promise<void>
  onSelectPrimary(imageId: number): Promise<void>
}

export function VisualAssetCandidatePanel({
  candidates,
  primaryId,
  onRecommend,
  onSelectPrimary,
}: Props) {
  const [recommending, setRecommending] = useState(false)
  const [selecting, setSelecting] = useState<number | null>(null)
  const [brokenIds, setBrokenIds] = useState<Set<number>>(new Set())

  const primary = candidates.find((c) => c.id === primaryId || c.is_primary) ?? null
  const others = candidates.filter((c) => c.id !== primary?.id)

  async function handleRecommend() {
    setRecommending(true)
    await onRecommend().catch(() => {})
    setRecommending(false)
  }

  async function handleSelect(imageId: number) {
    setSelecting(imageId)
    await onSelectPrimary(imageId).catch(() => {})
    setSelecting(null)
  }

  return (
    <div className="space-y-4">
      {/* Recommend button */}
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Poster Candidates</h4>
        <button
          onClick={handleRecommend}
          disabled={recommending}
          className="flex items-center gap-1.5 text-xs px-2.5 py-1 rounded bg-slate-100 hover:bg-blue-50 text-slate-600 hover:text-blue-700 disabled:opacity-50 transition-colors"
        >
          <RefreshCw className={cn("h-3 w-3", recommending && "animate-spin")} />
          {recommending ? "조회 중…" : "TMDB 후보 추천"}
        </button>
      </div>

      {/* Current primary */}
      {primary && (
        <div>
          <p className="text-xs text-slate-500 mb-1.5">Current Primary</p>
          <PosterCard
            candidate={primary}
            isPrimary
            isBroken={brokenIds.has(primary.id)}
            onBroken={(id) => setBrokenIds((s) => new Set([...s, id]))}
          />
        </div>
      )}

      {/* Candidates grid */}
      {candidates.length === 0 ? (
        <div className="border border-dashed border-slate-200 rounded-lg p-6 text-center">
          <Film className="h-8 w-8 mx-auto text-slate-300 mb-2" />
          <p className="text-xs text-slate-400">후보 없음 — TMDB 후보 추천 버튼으로 가져오세요</p>
        </div>
      ) : (
        <div>
          {others.length > 0 && (
            <>
              <p className="text-xs text-slate-500 mb-1.5">Candidates</p>
              <div className="flex flex-wrap gap-3">
                {others.map((c) => (
                  <PosterCard
                    key={c.id}
                    candidate={c}
                    isPrimary={false}
                    isBroken={brokenIds.has(c.id)}
                    onBroken={(id) => setBrokenIds((s) => new Set([...s, id]))}
                    onSelect={handleSelect}
                    selecting={selecting === c.id}
                  />
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}

// ── PosterCard ────────────────────────────────────────────

function PosterCard({
  candidate,
  isPrimary,
  isBroken,
  onBroken,
  onSelect,
  selecting,
}: {
  candidate: PosterCandidateOut
  isPrimary: boolean
  isBroken: boolean
  onBroken(id: number): void
  onSelect?(id: number): void
  selecting?: boolean
}) {
  const src = resolvePosterUrl(candidate.url)
  const badge = rightsBadge(candidate.source)
  const aspect = aspectLabel(candidate.width, candidate.height)

  return (
    <div className={cn(
      "relative border rounded-lg overflow-hidden w-28 flex-shrink-0",
      isPrimary ? "border-blue-400 ring-1 ring-blue-300" : "border-slate-200 hover:border-blue-300 transition-colors",
    )}>
      {/* Thumbnail */}
      <div className="aspect-[2/3] bg-slate-100 flex items-center justify-center overflow-hidden">
        {src && !isBroken ? (
          <img
            src={src}
            alt="poster"
            className="w-full h-full object-cover"
            onError={() => onBroken(candidate.id)}
            data-broken={isBroken ? "true" : undefined}
          />
        ) : (
          <Film className="h-6 w-6 text-slate-300" />
        )}
      </div>

      {/* Primary badge */}
      {isPrimary && (
        <div className="absolute top-1 left-1 bg-blue-500 text-white text-[10px] font-bold px-1 py-0.5 rounded leading-tight">
          primary
        </div>
      )}

      {/* Info */}
      <div className="p-1.5 space-y-1">
        <div className="flex items-center gap-1 flex-wrap">
          <span className={cn("text-[10px] font-medium px-1 py-0.5 rounded", TONE_CLASS[badge.tone])}>
            {badge.label}
          </span>
        </div>
        <div className="text-[10px] text-slate-500">
          {candidate.source}
          {aspect && <> · {aspect}</>}
          {candidate.width && candidate.height && (
            <span className="block text-slate-400">{candidate.width}×{candidate.height}</span>
          )}
        </div>

        {/* Actions */}
        {!isPrimary && (
          <div className="space-y-1">
            <button
              onClick={() => onSelect?.(candidate.id)}
              disabled={selecting}
              className="w-full text-[10px] px-1 py-0.5 bg-slate-100 hover:bg-blue-500 hover:text-white text-slate-600 rounded transition-colors disabled:opacity-50"
            >
              {selecting ? "…" : "Set Primary"}
            </button>
            {candidate.source === "dam" && (
              <button
                disabled
                title="Phase later — DAM 직접 연결 API 구현 예정"
                className="w-full text-[10px] px-1 py-0.5 bg-slate-50 text-slate-300 rounded cursor-not-allowed"
              >
                Link to Dam
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
