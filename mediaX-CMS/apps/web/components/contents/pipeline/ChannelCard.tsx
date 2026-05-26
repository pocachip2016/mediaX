"use client"

import { ChannelStats } from "@/lib/api"

const CHANNELS = {
  email_poll: { icon: "📧", label: "Email Poll" },
  manual: { icon: "✋", label: "Manual" },
  bulk_csv: { icon: "📦", label: "Bulk CSV" },
  dam_webhook: { icon: "🪝", label: "DAM Webhook" },
}

function formatTimeAgo(isoString: string): string {
  const diff = Math.floor((Date.now() - new Date(isoString).getTime()) / 1000)
  if (diff < 60) return "방금"
  if (diff < 3600) return `${Math.floor(diff / 60)}분 전`
  if (diff < 86400) return `${Math.floor(diff / 3600)}시간 전`
  return `${Math.floor(diff / 86400)}일 전`
}

interface ChannelCardProps {
  channel: keyof typeof CHANNELS
  stats: ChannelStats
}

export function ChannelCard({ channel, stats }: ChannelCardProps) {
  const { icon, label } = CHANNELS[channel]
  const statusDot = stats.status === "ok" ? "🟢" : "🟡"
  const timeStr = stats.last_at ? formatTimeAgo(stats.last_at) : "기록 없음"

  return (
    <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 dark:border-slate-700 dark:bg-slate-900">
      <span className="text-lg">{icon}</span>
      <div className="flex flex-col gap-0.5">
        <div className="text-sm font-medium">{stats.count}</div>
        <div className="text-xs text-slate-500 dark:text-slate-400">{label}</div>
      </div>
      <span className="ml-auto text-xs text-slate-400">{statusDot}</span>
      <span className="text-xs text-slate-400">{timeStr}</span>
    </div>
  )
}
