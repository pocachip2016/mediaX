"use client"

import { useState } from "react"
import { Monitor, Smartphone, Globe, Clock, Tv } from "lucide-react"
import { cn } from "@workspace/ui/lib/utils"
import { curationApi } from "@/lib/api"
import type { SlotOut, CurationDevice, CurationTimeBand, SlotCode, SlotType } from "@/lib/api"
import type { ProgrammingNodeSet } from "@/lib/api"

const SLOT_TYPE_COLOR: Record<SlotType, string> = {
  banner:   "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300",
  theme:    "bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-300",
  personal: "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300",
  genre:    "bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300",
  ranking:  "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300",
  promo:    "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-300",
}

const DEVICE_ICON: Record<CurationDevice, React.ElementType> = {
  all:    Tv,
  tv:     Tv,
  mobile: Smartphone,
  web:    Globe,
}

const TIME_LABEL: Record<CurationTimeBand, string> = {
  all:       "전체",
  morning:   "오전",
  afternoon: "오후",
  evening:   "저녁",
  night:     "심야",
}

interface SlotCardProps {
  slot: SlotOut
  nodeSets: ProgrammingNodeSet[]
  onUpdated: (updated: SlotOut) => void
}

export function SlotCard({ slot, nodeSets, onUpdated }: SlotCardProps) {
  const [saving, setSaving] = useState(false)
  const DeviceIcon = DEVICE_ICON[slot.device]
  const boundSet = nodeSets.find((s) => s.id === slot.node_set_id)

  async function handleBindChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const val = e.target.value
    const nodeSetId = val === "" ? null : Number(val)
    setSaving(true)
    try {
      const updated = await curationApi.patchSlot(slot.id, { node_set_id: nodeSetId })
      onUpdated(updated)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className={cn(
      "rounded-lg border bg-card p-4 flex flex-col gap-3 shadow-sm",
      !slot.is_active && "opacity-50"
    )}>
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <span className="text-2xl font-bold text-foreground">{slot.slot_code}</span>
        <span className={cn("text-xs font-medium px-2 py-0.5 rounded-full", SLOT_TYPE_COLOR[slot.slot_type])}>
          {slot.slot_type}
        </span>
      </div>

      {/* 디바이스 · 시간대 */}
      <div className="flex items-center gap-3 text-xs text-muted-foreground">
        <span className="flex items-center gap-1">
          <DeviceIcon className="h-3.5 w-3.5" />
          {slot.device}
        </span>
        <span className="flex items-center gap-1">
          <Clock className="h-3.5 w-3.5" />
          {TIME_LABEL[slot.time_band]}
        </span>
      </div>

      {/* 현재 연결 세트 */}
      <div className="text-sm min-h-[1.5rem]">
        {boundSet ? (
          <span className="text-foreground font-medium truncate block">● {boundSet.name}</span>
        ) : (
          <span className="text-muted-foreground italic">미연결</span>
        )}
      </div>

      {/* node_set 바인딩 선택 */}
      <select
        value={slot.node_set_id ?? ""}
        onChange={handleBindChange}
        disabled={saving}
        className={cn(
          "w-full text-xs rounded border bg-background px-2 py-1.5",
          "border-input text-foreground focus:outline-none focus:ring-1 focus:ring-ring",
          saving && "opacity-50 cursor-wait"
        )}
      >
        <option value="">— 연결 해제 —</option>
        {nodeSets.map((ns) => (
          <option key={ns.id} value={ns.id}>
            #{ns.id} {ns.name}
          </option>
        ))}
      </select>
    </div>
  )
}
