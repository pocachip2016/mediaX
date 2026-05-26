"use client"

import { useState } from "react"

interface Gate6ContextProps {
  pendingCount: number
}

export function Gate6Context({ pendingCount }: Gate6ContextProps) {
  const [autoPublish, setAutoPublish] = useState(false)

  const autoCount = Math.floor(pendingCount * 0.6)

  return (
    <div className="space-y-3">
      <div className="flex items-start gap-3 rounded-lg border border-green-200 bg-green-50 p-3 dark:border-green-800 dark:bg-green-900/30">
        <span className="text-green-600 text-sm">🚀</span>
        <div className="space-y-1">
          <p className="text-xs font-medium text-green-700 dark:text-green-300">자동 게시 옵션</p>
          <p className="text-xs text-green-600 dark:text-green-400">
            품질 점수 90점 이상 콘텐츠는 검수 없이 즉시 게시됩니다.
          </p>
          <p className="text-xs text-green-500 dark:text-green-500">
            예상 자동 게시: {autoCount}/{pendingCount}건
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2 text-xs">
        <input
          type="checkbox"
          id="auto-publish"
          checked={autoPublish}
          onChange={(e) => setAutoPublish(e.target.checked)}
          className="h-3 w-3"
        />
        <label htmlFor="auto-publish" className="text-slate-600 dark:text-slate-400">
          품질 ≥ 90점 콘텐츠 자동 게시 활성화
        </label>
      </div>

      {autoPublish && (
        <p className="text-xs text-amber-600 dark:text-amber-400">
          ⚠ 자동 게시된 콘텐츠는 즉시 서비스 노출됩니다.
        </p>
      )}
    </div>
  )
}
