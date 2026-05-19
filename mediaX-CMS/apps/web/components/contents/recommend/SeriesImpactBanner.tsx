import { AlertTriangle } from "lucide-react"

interface Props {
  seasonCount: number
  episodeCount: number
}

export function SeriesImpactBanner({ seasonCount, episodeCount }: Props) {
  if (seasonCount === 0 && episodeCount === 0) return null

  const parts: string[] = []
  if (seasonCount > 0) parts.push(`${seasonCount} 시즌`)
  if (episodeCount > 0) parts.push(`${episodeCount} 에피소드`)

  return (
    <div className="flex items-center gap-2 px-4 py-2 bg-amber-50 border-b border-amber-200 text-xs text-amber-700">
      <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
      <span>⚠ 승인 시 하위 {parts.join(" · ")} 상속 갱신</span>
    </div>
  )
}
