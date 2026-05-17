import { cn } from "@workspace/ui/lib/utils"
import type { FieldKind } from "@/lib/recommendDerive"

const KIND_DOT: Record<FieldKind, string> = {
  confirmed: "bg-green-400",
  auto:      "bg-amber-400",
  conflict:  "bg-red-400",
  missing:   "bg-slate-300",
}

interface Props {
  label: string
  icon: string
  value: string | null
  kind: FieldKind
  isApplied: boolean
}

export function MetaCell({ label, icon, value, kind, isApplied }: Props) {
  return (
    <div className="flex items-start gap-2 px-4 py-3 border-r border-slate-100">
      <span className="text-base shrink-0 leading-none mt-0.5">{icon}</span>
      <div className="min-w-0 flex-1">
        <p className="text-xs text-slate-400 mb-0.5">{label}</p>
        {isApplied ? (
          <span className="inline-block text-xs bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded">
            채택됨
          </span>
        ) : value ? (
          <p className="text-sm text-slate-800 break-words">{value}</p>
        ) : (
          <span className="text-xs text-slate-300 border border-dashed border-slate-200 rounded px-1.5 py-0.5">
            Missing
          </span>
        )}
      </div>
      <span className={cn("h-2 w-2 rounded-full mt-1.5 shrink-0", KIND_DOT[kind])} />
    </div>
  )
}
