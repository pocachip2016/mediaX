"use client"

import { useState } from "react"

interface Gate5ContextProps {
  pendingCount: number
  errorCount: number
}

export function Gate5Context({ pendingCount, errorCount }: Gate5ContextProps) {
  const [reviewer, setReviewer] = useState("")
  const [skipFailed, setSkipFailed] = useState(true)

  const quality = pendingCount > 0 ? Math.max(0, Math.round(((pendingCount - errorCount) / pendingCount) * 100)) : 0
  const gaugeColor = quality >= 90 ? "bg-green-500" : quality >= 70 ? "bg-amber-500" : "bg-red-500"

  return (
    <div className="space-y-3">
      {/* Quality Gauge */}
      <div className="space-y-1">
        <div className="flex items-center justify-between text-xs">
          <span className="text-slate-500">품질 게이지</span>
          <span className="font-medium">{quality}%</span>
        </div>
        <div className="w-full h-2 bg-slate-200 dark:bg-slate-700 rounded-full">
          <div className={`h-full rounded-full ${gaugeColor}`} style={{ width: `${quality}%` }} />
        </div>
      </div>

      {/* Reviewer */}
      <div className="space-y-1">
        <label className="text-xs text-slate-600 dark:text-slate-400">검수자</label>
        <input
          type="text"
          value={reviewer}
          onChange={(e) => setReviewer(e.target.value)}
          placeholder="검수자 이름 입력"
          className="w-full rounded border border-slate-300 bg-white px-2 py-1 text-xs dark:border-slate-600 dark:bg-slate-800"
        />
      </div>

      {/* Skip failed */}
      <div className="flex items-center gap-2 text-xs">
        <input
          type="checkbox"
          id="skip-failed"
          checked={skipFailed}
          onChange={(e) => setSkipFailed(e.target.checked)}
          className="h-3 w-3"
        />
        <label htmlFor="skip-failed" className="text-slate-600 dark:text-slate-400">
          실패/반려 콘텐츠 건너뜀 ({errorCount}건)
        </label>
      </div>
    </div>
  )
}
