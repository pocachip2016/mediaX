import { Lock } from "lucide-react"

export function InheritedLockCell() {
  return (
    <div className="col-span-2 flex items-center gap-2 px-4 py-3 bg-slate-50 border-slate-100">
      <Lock className="h-3.5 w-3.5 text-slate-400 shrink-0" />
      <span className="text-xs text-slate-400">시리즈에서 상속</span>
    </div>
  )
}
