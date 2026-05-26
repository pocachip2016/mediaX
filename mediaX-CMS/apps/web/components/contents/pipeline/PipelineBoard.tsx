"use client"

import { pipelineApi, PipelineBoardResponse } from "@/lib/api"
import { useEffect, useState } from "react"
import { ChannelCard } from "./ChannelCard"
import { StageNode } from "./StageNode"
import { GateButton } from "./GateButton"
import { DetailPanel } from "./DetailPanel"
import { GatePanel } from "./GatePanel"
import { Skeleton } from "@workspace/ui/components/skeleton"
import { AlertCircle } from "lucide-react"

const MOCK_BOARD: PipelineBoardResponse = {
  channels_24h: {
    email_poll: { count: 124, last_at: new Date(Date.now() - 3 * 60000).toISOString(), status: "ok" },
    manual: { count: 18, last_at: new Date().toISOString(), status: "ok" },
    bulk_csv: { count: 237, last_at: new Date(Date.now() - 6 * 60000).toISOString(), status: "ok" },
    dam_webhook: { count: 33, last_at: new Date(Date.now() - 12 * 60000).toISOString(), status: "ok" },
  },
  stages: {
    s1_intake: { count: 132, top_contents: [], avg_seconds: null, error_count: 0 },
    s2_normalize: { count: 132, top_contents: [], avg_seconds: null, error_count: 0 },
    s3_llm_extract: { count: 12, top_contents: [], avg_seconds: null, error_count: 1 },
    s4_source_match: { count: 8, top_contents: [], avg_seconds: null, error_count: 0 },
    s5_gap_detect: { count: 5, top_contents: [], avg_seconds: null, error_count: 0 },
    s6_websearch_fill: { count: 21, top_contents: [], avg_seconds: null, error_count: 0 },
    s7_staging: { count: 41, top_contents: [], avg_seconds: null, error_count: 1 },
    s8_review: { count: 23, top_contents: [], avg_seconds: null, error_count: 0 },
    s9_publish: { count: 6, total_published: 189, top_contents: [], avg_seconds: null, error_count: 0 },
  },
  gates: {
    GATE_1: { mode: "manual", pending: 12 },
    GATE_2: { mode: "manual", pending: 8 },
    GATE_3: { mode: "manual", pending: 5 },
    GATE_4: { mode: "auto", pending: 21 },
    GATE_5: { mode: "manual", pending: 41 },
    GATE_6: { mode: "manual", pending: 6 },
  },
  alerts: {
    failed_queue: 2,
    rejected_archive: 17,
    enrichment_blocked: 5,
  },
}

// Stage ID → gate that controls advancing OUT of this stage
const STAGE_TO_GATE: Record<string, string> = {
  s1_intake: "GATE_1",
  s3_llm_extract: "GATE_2",
  s5_gap_detect: "GATE_3",
  s6_websearch_fill: "GATE_4",
  s7_staging: "GATE_5",
  s8_review: "GATE_6",
}

const STAGE_ORDER = ["s1_intake", "s2_normalize", "s3_llm_extract", "s4_source_match", "s5_gap_detect", "s6_websearch_fill", "s7_staging", "s8_review", "s9_publish"]

interface PipelineBoardProps {
  autoRefresh?: boolean
}

export function PipelineBoard({ autoRefresh = true }: PipelineBoardProps) {
  const [board, setBoard] = useState<PipelineBoardResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedStage, setSelectedStage] = useState<string | null>(null)
  const [isAutoRefresh, setIsAutoRefresh] = useState(autoRefresh)
  const [openGate, setOpenGate] = useState<string | null>(null)

  const fetchBoard = async () => {
    try {
      const data = await pipelineApi.getBoard()
      setBoard(data)
      setError(null)
    } catch (err) {
      console.error("Failed to fetch pipeline board:", err)
      setBoard(MOCK_BOARD)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchBoard()
  }, [])

  useEffect(() => {
    if (!isAutoRefresh) return
    const interval = setInterval(fetchBoard, 30000)
    return () => clearInterval(interval)
  }, [isAutoRefresh])

  const handleToggleGateMode = async (gateId: string, mode: "manual" | "auto") => {
    try {
      await pipelineApi.toggleGateMode(gateId, mode)
      fetchBoard()
    } catch (err) {
      console.error("Failed to toggle gate mode:", err)
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  if (!board) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-800 dark:bg-red-900">
        <AlertCircle className="h-5 w-5 text-red-600" />
        <span className="text-sm text-red-600 dark:text-red-200">{error || "Failed to load pipeline board"}</span>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">파이프라인 보드</h2>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsAutoRefresh(!isAutoRefresh)}
            className="rounded px-2 py-1 text-xs hover:bg-slate-200 dark:hover:bg-slate-700"
          >
            {isAutoRefresh ? "↻ 30초" : "⊘ 일시정지"}
          </button>
          <button onClick={fetchBoard} className="rounded px-2 py-1 text-xs hover:bg-slate-200 dark:hover:bg-slate-700">
            ↺
          </button>
        </div>
      </div>

      {/* Channels 24h */}
      <div className="grid grid-cols-4 gap-2">
        {(["email_poll", "manual", "bulk_csv", "dam_webhook"] as const).map((ch) => {
          const stats = board.channels_24h[ch]
          if (!stats) return null
          return <ChannelCard key={ch} channel={ch} stats={stats} />
        })}
      </div>

      {/* Stage Flow + Detail */}
      <div className="grid grid-cols-5 gap-4">
        {/* Left: Stage Flow (60%) */}
        <div className="col-span-3 space-y-1.5 rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900">
          {STAGE_ORDER.map((stageId) => {
            const gateId = STAGE_TO_GATE[stageId]
            const stageStats = board.stages[stageId]
            const gateInfo = gateId ? board.gates[gateId] : undefined
            if (!stageStats) return null
            return (
              <div key={stageId} className="flex items-center gap-2">
                <StageNode
                  stageId={stageId}
                  stats={stageStats}
                  isSelected={selectedStage === stageId}
                  onClick={() => setSelectedStage(selectedStage === stageId ? null : stageId)}
                />
                {gateId && gateInfo && (
                  <GateButton
                    gateId={gateId}
                    info={gateInfo}
                    onAdvance={() => setOpenGate(gateId)}
                    onToggleMode={(mode) => handleToggleGateMode(gateId, mode)}
                  />
                )}
              </div>
            )
          })}
        </div>

        {/* Right: Detail Panel (40%) */}
        <div className="col-span-2">
          <DetailPanel selectedStage={selectedStage} board={board} onClearSelection={() => setSelectedStage(null)} />
        </div>
      </div>

      {/* Alerts */}
      <div className="flex gap-2">
        <div className="inline-flex items-center gap-1 rounded-full bg-red-100 px-3 py-1 dark:bg-red-900">
          <span className="text-xs font-medium text-red-700 dark:text-red-200">⛔ 실패 {board.alerts.failed_queue}</span>
        </div>
        <div className="inline-flex items-center gap-1 rounded-full bg-orange-100 px-3 py-1 dark:bg-orange-900">
          <span className="text-xs font-medium text-orange-700 dark:text-orange-200">🚫 반려 {board.alerts.rejected_archive}</span>
        </div>
        <div className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-3 py-1 dark:bg-amber-900">
          <span className="text-xs font-medium text-amber-700 dark:text-amber-200">⏸ 보강 {board.alerts.enrichment_blocked}</span>
        </div>
      </div>

      {/* Gate Panel Drawer */}
      <GatePanel
        gateId={openGate}
        board={board}
        onClose={() => setOpenGate(null)}
        onAdvanced={() => {
          setOpenGate(null)
          fetchBoard()
        }}
      />
    </div>
  )
}
