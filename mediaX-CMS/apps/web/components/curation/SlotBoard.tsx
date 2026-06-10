"use client"

import { useEffect, useState, useCallback } from "react"
import { RefreshCw } from "lucide-react"
import { curationApi, schedulingApi } from "@/lib/api"
import type { SlotOut } from "@/lib/api"
import type { ProgrammingNodeSet } from "@/lib/api"
import { SlotCard } from "./SlotCard"

export function SlotBoard() {
  const [slots, setSlots] = useState<SlotOut[]>([])
  const [nodeSets, setNodeSets] = useState<ProgrammingNodeSet[]>([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(() => {
    setLoading(true)
    Promise.all([
      curationApi.listSlots(),
      schedulingApi.listSets(),
    ])
      .then(([s, ns]) => {
        setSlots(s)
        setNodeSets(ns)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  function handleSlotUpdated(updated: SlotOut) {
    setSlots((prev) => prev.map((s) => (s.id === updated.id ? updated : s)))
  }

  if (loading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="rounded-lg border bg-card p-4 h-44 animate-pulse" />
        ))}
      </div>
    )
  }

  if (slots.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-muted-foreground gap-2">
        <p className="text-sm">등록된 슬롯이 없습니다.</p>
        <p className="text-xs">백엔드에서 슬롯을 생성하거나 Docker 환경을 확인하세요.</p>
      </div>
    )
  }

  const activeCount = slots.filter((s) => s.is_active).length

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          활성 슬롯 <span className="font-semibold text-foreground">{activeCount}</span>개
          / 전체 {slots.length}개
        </p>
        <button
          onClick={load}
          className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          새로고침
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {slots.map((slot) => (
          <SlotCard
            key={slot.id}
            slot={slot}
            nodeSets={nodeSets}
            onUpdated={handleSlotUpdated}
          />
        ))}
      </div>
    </div>
  )
}
