"use client"

const TRUSTED_CPS = ["KT Alpha", "Studio Dragon", "CJ ENM", "JTBC Studios", "SBS MediaNet"]

export function Gate1Context() {
  return (
    <div className="space-y-2">
      <p className="text-xs font-medium text-slate-600 dark:text-slate-400">신뢰 CP 화이트리스트</p>
      <div className="space-y-1">
        {TRUSTED_CPS.map((cp) => (
          <div key={cp} className="flex items-center gap-2 text-xs">
            <span className="text-green-500">✓</span>
            <span>{cp}</span>
          </div>
        ))}
      </div>
      <p className="text-xs text-slate-400 mt-2">목록에 있는 CP사 콘텐츠는 자동 승인됩니다.</p>
    </div>
  )
}
