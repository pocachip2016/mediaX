"use client"

import { pipelineApi, PipelineBoardResponse, StageContentItem } from "@/lib/api"
import { useState } from "react"
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@workspace/ui/components/sheet"
import { Button } from "@workspace/ui/components/button"
import { Gate1Context } from "./gate-contexts/Gate1Context"
import { AutoGateContext } from "./gate-contexts/AutoGateContext"
import { Gate3Context } from "./gate-contexts/Gate3Context"
import { Gate5Context } from "./gate-contexts/Gate5Context"
import { Gate6Context } from "./gate-contexts/Gate6Context"

const GATE_STAGE: Record<string, string> = {
  GATE_1: "s1_intake",
  GATE_2: "s3_llm_extract",
  GATE_3: "s5_gap_detect",
  GATE_4: "s6_websearch_fill",
  GATE_5: "s7_staging",
  GATE_6: "s8_review",
}

const GATE_NEXT_STAGE: Record<string, string> = {
  GATE_1: "S2",
  GATE_2: "S4",
  GATE_3: "S6",
  GATE_4: "S7",
  GATE_5: "S8",
  GATE_6: "S9",
}

interface GatePanelProps {
  gateId: string | null
  board: PipelineBoardResponse | null
  onClose: () => void
  onAdvanced: () => void
}

function GateContextPanel({ gateId, board }: { gateId: string; board: PipelineBoardResponse | null }) {
  const stageId = GATE_STAGE[gateId] ?? ""
  const stats = stageId ? board?.stages[stageId] : undefined
  const pending = (board?.gates[gateId])?.pending ?? 0
  const errorCount = stats?.error_count ?? 0

  switch (gateId) {
    case "GATE_1": return <Gate1Context />
    case "GATE_2": return <AutoGateContext gateId={gateId} />
    case "GATE_3": return <Gate3Context />
    case "GATE_4": return <AutoGateContext gateId={gateId} />
    case "GATE_5": return <Gate5Context pendingCount={pending} errorCount={errorCount} />
    case "GATE_6": return <Gate6Context pendingCount={pending} />
    default: return null
  }
}

export function GatePanel({ gateId, board, onClose, onAdvanced }: GatePanelProps) {
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
  const [isAdvancing, setIsAdvancing] = useState(false)
  const [lastResult, setLastResult] = useState<{ advanced: number; skipped: number; failed: number } | null>(null)
  const [conflict, setConflict] = useState(false)

  if (!gateId) return null

  const stageId = GATE_STAGE[gateId] ?? ""
  const gateInfo = board?.gates[gateId]
  const stageStats = stageId ? board?.stages[stageId] : undefined
  const topContents: StageContentItem[] = stageStats?.top_contents ?? []
  const pendingCount = gateInfo?.pending ?? 0
  const mode = gateInfo?.mode ?? "manual"

  const toggleSelect = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const handleAdvance = async (simulate: boolean, contentIds?: number[]) => {
    setIsAdvancing(true)
    setConflict(false)
    try {
      const ids = contentIds ?? (selectedIds.size > 0 ? Array.from(selectedIds) : [])
      const result = await pipelineApi.advanceGate(gateId, { content_ids: ids, simulate })
      setLastResult({ advanced: result.advanced, skipped: result.skipped, failed: result.failed })
      if (!simulate) {
        onAdvanced()
      }
    } catch (err: unknown) {
      const status = (err as { status?: number })?.status ?? 0
      if (status === 409) {
        setConflict(true)
      } else {
        console.error("Gate advance error:", err)
      }
    } finally {
      setIsAdvancing(false)
    }
  }

  return (
    <Sheet open={!!gateId} onOpenChange={(open) => { if (!open) onClose() }}>
      <SheetContent side="right" className="w-96 sm:max-w-md overflow-y-auto">
        <SheetHeader>
          <SheetTitle>
            <span className="flex items-center gap-2">
              {gateId}
              <span className={`rounded-full px-2 py-0.5 text-xs ${mode === "auto" ? "bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300" : "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300"}`}>
                {mode === "auto" ? "🤖 Auto" : "🔒 Manual"}
              </span>
              <span className="text-sm text-slate-500 font-normal">
                → {GATE_NEXT_STAGE[gateId]} ({pendingCount}건)
              </span>
            </span>
          </SheetTitle>
        </SheetHeader>

        <div className="mt-4 space-y-4">
          {/* 충돌 경고 */}
          {conflict && (
            <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-700 dark:border-red-800 dark:bg-red-900 dark:text-red-300">
              ⚠ 이미 다른 작업이 진행 중입니다. 보드를 새로고침 후 다시 시도하세요.
            </div>
          )}

          {/* 결과 표시 */}
          {lastResult && (
            <div className="rounded-lg border border-green-200 bg-green-50 p-3 text-xs dark:border-green-800 dark:bg-green-900">
              ✓ 이동: {lastResult.advanced}건 | 건너뜀: {lastResult.skipped}건 | 실패: {lastResult.failed}건
            </div>
          )}

          {/* 대상 콘텐츠 리스트 */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <p className="text-xs font-medium">대상 콘텐츠 (상위 {topContents.length}건)</p>
              {topContents.length > 0 && (
                <button
                  onClick={() => {
                    if (selectedIds.size === topContents.length) setSelectedIds(new Set())
                    else setSelectedIds(new Set(topContents.map((c) => c.id)))
                  }}
                  className="text-xs text-blue-600 hover:underline"
                >
                  {selectedIds.size === topContents.length ? "선택 해제" : "전체 선택"}
                </button>
              )}
            </div>

            <div className="max-h-48 overflow-y-auto space-y-1">
              {topContents.length === 0 ? (
                <p className="text-xs text-slate-400 py-2 text-center">
                  대기 중인 콘텐츠 없음 (전체 {pendingCount}건 진행)
                </p>
              ) : (
                topContents.map((c) => (
                  <div
                    key={c.id}
                    className={`flex items-center gap-2 rounded px-2 py-1 cursor-pointer text-xs border transition-colors ${
                      selectedIds.has(c.id)
                        ? "border-blue-400 bg-blue-50 dark:bg-blue-900"
                        : "border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-700"
                    }`}
                    onClick={() => toggleSelect(c.id)}
                  >
                    <input
                      type="checkbox"
                      checked={selectedIds.has(c.id)}
                      onChange={() => {}}
                      className="h-3 w-3 flex-shrink-0"
                    />
                    <span className="truncate">#{c.id} {c.title}</span>
                    {c.seconds_in_stage && (
                      <span className="text-slate-400 ml-auto">
                        {Math.floor(c.seconds_in_stage / 60)}분
                      </span>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Context 패널 */}
          <div className="rounded-lg border border-slate-200 p-3 dark:border-slate-700">
            <GateContextPanel gateId={gateId} board={board} />
          </div>

          {/* 액션 버튼 */}
          <div className="flex flex-col gap-2 pt-2 border-t border-slate-200 dark:border-slate-700">
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleAdvance(true)}
              disabled={isAdvancing}
              className="text-xs"
            >
              🔍 시뮬레이션
            </Button>
            <Button
              size="sm"
              onClick={() => handleAdvance(false, selectedIds.size > 0 ? Array.from(selectedIds) : undefined)}
              disabled={isAdvancing || pendingCount === 0}
              className="text-xs"
            >
              {isAdvancing ? "처리 중..." : selectedIds.size > 0 ? `▶ 선택 진행 (${selectedIds.size}건)` : `▶ 전체 진행 (${pendingCount}건)`}
            </Button>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  )
}
