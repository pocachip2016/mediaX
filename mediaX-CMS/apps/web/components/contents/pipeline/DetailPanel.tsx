"use client"

import { PipelineBoardResponse } from "@/lib/api"
import { LiveEventLog } from "./LiveEventLog"
import { StageContentList } from "./StageContentList"

interface DetailPanelProps {
  selectedStage: string | null
  board: PipelineBoardResponse | null
  onClearSelection?: () => void
}

export function DetailPanel({ selectedStage, board, onClearSelection }: DetailPanelProps) {
  const stageInfo = selectedStage && board ? board.stages[selectedStage] : null

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900 flex flex-col">
      {/* 탭 헤더 */}
      <div className="flex gap-1 border-b border-slate-200 pb-2 dark:border-slate-700">
        <button
          onClick={onClearSelection}
          className={`px-3 py-1 text-xs font-medium transition-colors ${
            !selectedStage
              ? "text-slate-900 dark:text-slate-100 border-b-2 border-slate-900 dark:border-slate-100"
              : "text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100"
          }`}
        >
          📡 Live
        </button>
        {selectedStage && (
          <button
            className={`px-3 py-1 text-xs font-medium text-slate-900 dark:text-slate-100 border-b-2 border-slate-900 dark:border-slate-100`}
          >
            🔍 Stage 상세
          </button>
        )}
      </div>

      {/* 본문 */}
      <div className="flex-1 mt-4 overflow-hidden">
        {!selectedStage ? (
          <LiveEventLog />
        ) : stageInfo ? (
          <StageContentList stageId={selectedStage} stats={stageInfo} />
        ) : (
          <div className="text-xs text-slate-400 py-4 text-center">스테이지 데이터 없음</div>
        )}
      </div>

      {/* 돌아가기 버튼 (선택된 경우) */}
      {selectedStage && (
        <div className="mt-4 pt-3 border-t border-slate-200 dark:border-slate-700">
          <button
            onClick={onClearSelection}
            className="w-full rounded px-2 py-1 text-xs hover:bg-slate-100 dark:hover:bg-slate-800"
          >
            ← Live로 돌아가기
          </button>
        </div>
      )}
    </div>
  )
}
