"use client"

const PROVIDERS = [
  { name: "Brave", quota: 400, used: 152, limit: 2000, priority: 1 },
  { name: "SerpAPI", quota: 100, used: 88, limit: 100, priority: 2 },
  { name: "Gemini", quota: 900, used: 300, limit: 1500, priority: 3 },
  { name: "Ollama", quota: null, used: 45, limit: null, priority: 4 },
]

export function Gate3Context() {
  return (
    <div className="space-y-3">
      <p className="text-xs font-medium text-slate-600 dark:text-slate-400">WebSearch 프로바이더 우선순위</p>
      <div className="space-y-2">
        {PROVIDERS.map((p) => {
          const pct = p.limit ? Math.round((p.used / p.limit) * 100) : null
          const isCritical = pct !== null && pct >= 90
          return (
            <div key={p.name} className="space-y-1">
              <div className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-1">
                  <span className="text-slate-500">#{p.priority}</span>
                  <span className="font-medium">{p.name}</span>
                  {isCritical && <span className="text-red-500 text-xs">⚠ 한도 근접</span>}
                </div>
                <span className="text-slate-400">
                  {p.limit ? `${p.used}/${p.limit}` : `${p.used}건`}
                </span>
              </div>
              {p.limit && (
                <div className="w-full h-1.5 bg-slate-200 dark:bg-slate-700 rounded-full">
                  <div
                    className={`h-full rounded-full ${isCritical ? "bg-red-500" : "bg-blue-500"}`}
                    style={{ width: `${Math.min(pct!, 100)}%` }}
                  />
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
