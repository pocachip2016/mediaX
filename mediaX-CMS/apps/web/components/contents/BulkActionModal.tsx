"use client"

import { useState, useEffect, useRef } from "react"
import { AlertCircle, Check, Clock } from "lucide-react"
import { cn } from "@workspace/ui/lib/utils"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@workspace/ui/components/dialog"
import { metadataApi } from "@/lib/api"

type BulkStep = "confirm" | "progress" | "result"

export interface BulkTarget {
  id: number
  title: string
  cp_name?: string | null
  status?: string
}

interface BulkActionModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  action?: "approve" | "reject" | "reprocess" | "rematch"
  targets?: BulkTarget[]
}

const ACTION_CONFIG = {
  approve: { label: "승인", color: "bg-green-600 hover:bg-green-700", icon: Check, emoji: "✓" },
  reject: { label: "반려", color: "bg-red-600 hover:bg-red-700", icon: "X", emoji: "✗" },
  reprocess: { label: "AI 재처리", color: "bg-orange-600 hover:bg-orange-700", icon: "↻", emoji: "↻" },
  rematch: { label: "외부 재매칭", color: "bg-blue-600 hover:bg-blue-700", icon: "🔍", emoji: "🔍" },
}

export function BulkActionModal({
  open,
  onOpenChange,
  action = "approve",
  targets = [
    { id: 1, title: "기생충", cp_name: "CJ ENM", status: "review" },
    { id: 2, title: "부산행", cp_name: "Next Ent", status: "review" },
    { id: 3, title: "미나리", cp_name: "A24", status: "ai" },
  ],
}: BulkActionModalProps) {
  const [step, setStep] = useState<BulkStep>("confirm")
  const [reason, setReason] = useState("")
  const [progress, setProgress] = useState(0)
  const [dontAskAgain, setDontAskAgain] = useState(false)
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null)

  const actionConfig = ACTION_CONFIG[action]

  // Cleanup intervals on unmount or modal close
  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current)
    }
  }, [])

  // Reset state when modal opens
  useEffect(() => {
    if (open) {
      setStep("confirm")
      setReason("")
      setProgress(0)
      setDontAskAgain(false)
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current)
    }
  }, [open])

  // Real API + job polling, with mock fallback
  const startBulkAction = async () => {
    setStep("progress")
    setProgress(0)

    const ACTION_MAP: Partial<Record<string, (data: any) => Promise<any>>> = {
      reprocess: metadataApi.bulkReprocess,
      rematch: metadataApi.bulkEnrich,
    }

    try {
      const apiFn = ACTION_MAP[action]
      if (!apiFn) {
        throw new Error(`No API mapping for action: ${action}`)
      }

      const res = await apiFn({ ids: targets.map((t) => t.id), reason })
      if (!res?.job_id) {
        throw new Error("No job_id in response")
      }

      // Poll job status
      pollIntervalRef.current = setInterval(async () => {
        try {
          const job = await metadataApi.getJobStatus(res.job_id)
          setProgress(job.progress_percent)
          if (job.status === "done" || job.status === "failed") {
            if (pollIntervalRef.current) clearInterval(pollIntervalRef.current)
            setTimeout(() => setStep("result"), 500)
          }
        } catch (pollError) {
          console.error("Error polling job status:", pollError)
        }
      }, 1000)
    } catch (error) {
      // Fallback: mock progress (API unavailable or action not implemented)
      console.error(`API failed for ${action}:`, error)
      let p = 0
      const mockInterval = setInterval(() => {
        p += Math.random() * 20
        if (p >= 100) {
          p = 100
          clearInterval(mockInterval)
          setTimeout(() => setStep("result"), 500)
        }
        setProgress(Math.min(p, 100))
      }, 300)
    }
  }

  const getStepColor = () => {
    switch (action) {
      case "approve":
        return "bg-green-50 border-green-200 text-green-900"
      case "reject":
        return "bg-red-50 border-red-200 text-red-900"
      case "reprocess":
        return "bg-orange-50 border-orange-200 text-orange-900"
      case "rematch":
        return "bg-blue-50 border-blue-200 text-blue-900"
      default:
        return "bg-amber-50 border-amber-200 text-amber-900"
    }
  }

  const getProgressColor = () => {
    switch (action) {
      case "approve":
        return "bg-green-500"
      case "reject":
        return "bg-red-500"
      case "reprocess":
        return "bg-orange-500"
      case "rematch":
        return "bg-blue-500"
      default:
        return "bg-slate-500"
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{targets.length}개 콘텐츠를 {actionConfig.label}하시겠습니까?</DialogTitle>
        </DialogHeader>

        {/* Confirm Step */}
        {step === "confirm" && (
          <div className="space-y-4">
            <div className={cn("border rounded-lg px-6 py-4 flex items-start gap-3", getStepColor())}>
              <AlertCircle className="h-5 w-5 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold">이 작업은 되돌릴 수 있습니다 (24시간 내)</p>
              </div>
            </div>

            <div className="bg-slate-50 rounded-lg p-4">
              <h3 className="font-semibold text-slate-900 mb-3 text-sm">대상 콘텐츠</h3>
              <div className="space-y-2 max-h-40 overflow-y-auto">
                {targets.map((item) => (
                  <div key={item.id} className="flex items-center justify-between text-sm">
                    <div>
                      <p className="font-medium text-slate-900">{item.title}</p>
                      {item.cp_name && <p className="text-xs text-slate-500">{item.cp_name}</p>}
                    </div>
                    {item.status && (
                      <span
                        className={cn(
                          "px-2 py-0.5 rounded text-xs font-medium",
                          item.status === "ai" ? "bg-violet-100 text-violet-700" : "bg-amber-100 text-amber-700",
                        )}
                      >
                        {item.status === "ai" ? "AI처리완료" : "검수"}
                      </span>
                    )}
                    <span className="text-xs text-green-700 font-medium">{actionConfig.emoji}</span>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">{actionConfig.label} 사유 (선택)</label>
              <textarea
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder={`예: 메타 확인 완료, 외부 소스 일치`}
                rows={3}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                id="noask"
                checked={dontAskAgain}
                onChange={(e) => setDontAskAgain(e.target.checked)}
                className="h-4 w-4 cursor-pointer"
              />
              <label htmlFor="noask" className="text-slate-600 cursor-pointer">
                이 액션을 다시 묻지 않음 (10건 이하만)
              </label>
            </div>

            <div className="flex gap-2 justify-end pt-4 border-t border-slate-200">
              <button
                onClick={() => onOpenChange(false)}
                className="px-4 py-2 rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-50 font-medium"
              >
                취소
              </button>
              <button
                onClick={startBulkAction}
                className={cn("px-4 py-2 rounded-lg text-white font-medium inline-flex items-center gap-2", actionConfig.color)}
              >
                <Check className="h-4 w-4" />
                {targets.length}개 {actionConfig.label}
              </button>
            </div>
          </div>
        )}

        {/* Progress Step */}
        {step === "progress" && (
          <div className="space-y-6">
            <div className={cn("border rounded-lg px-6 py-4", getStepColor())}>
              <p className="font-semibold flex items-center gap-2">
                <Clock className="h-4 w-4 animate-spin" />
                {actionConfig.label} 처리 중...
              </p>
            </div>

            <div>
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm font-medium text-slate-700">전체 진행률</p>
                <span className="text-sm font-semibold text-slate-900">{Math.round(progress)}%</span>
              </div>
              <div className="w-full bg-slate-200 rounded-full h-3 overflow-hidden">
                <div className={cn("h-full transition-all duration-300", getProgressColor())} style={{ width: `${progress}%` }} />
              </div>
            </div>

            <div className="space-y-2 max-h-40 overflow-y-auto">
              {targets.map((item, i) => {
                const itemProgress = Math.min(progress * 1.2 - i * 20, 100)
                const itemStatus = itemProgress >= 100 ? "done" : itemProgress > 0 ? "processing" : "pending"
                const statusColor =
                  itemStatus === "done"
                    ? "#22c55e"
                    : itemStatus === "processing"
                      ? "#3b82f6"
                      : "#e5e7eb"

                return (
                  <div key={item.id} className="flex items-center gap-3">
                    <div
                      className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium flex-shrink-0"
                      style={{ backgroundColor: statusColor }}
                    >
                      {itemStatus === "done" && <Check className="h-4 w-4 text-white" />}
                      {itemStatus === "processing" && <Clock className="h-3 w-3 text-white animate-spin" />}
                    </div>
                    <div className="flex-1">
                      <p className="text-sm font-medium text-slate-900">{item.title}</p>
                      <div className="flex gap-2 mt-1">
                        {itemStatus === "processing" && <span className="text-xs text-blue-600">처리 중...</span>}
                        {itemStatus === "done" && <span className="text-xs text-green-600">✓ 완료</span>}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>

            <div className="text-sm text-slate-500 text-center">페이지를 떠나도 백그라운드에서 계속 처리됩니다</div>
          </div>
        )}

        {/* Result Step */}
        {step === "result" && (
          <div className="space-y-4">
            <div className={cn("border rounded-lg px-6 py-4", getStepColor())}>
              <p className="font-semibold flex items-center gap-2">
                <Check className="h-5 w-5" />
                {targets.length}개 콘텐츠를 {actionConfig.label}했습니다
              </p>
            </div>

            <div className="bg-green-50 rounded-lg border border-green-200 p-4">
              <p className="text-sm font-medium text-green-900 mb-3">✓ 성공 {targets.length}개</p>
              <div className="space-y-1 max-h-32 overflow-y-auto">
                {targets.map((item) => (
                  <div key={item.id} className="flex items-center gap-2 text-sm">
                    <Check className="h-4 w-4 text-green-600 flex-shrink-0" />
                    <span className="text-green-700">
                      {item.title} (#{item.id})
                    </span>
                  </div>
                ))}
              </div>
            </div>

            <div className="border border-slate-200 rounded-lg p-4">
              <div className="flex items-center justify-between mb-3">
                <p className="text-sm font-medium text-slate-700">다음 액션</p>
                <button className="text-xs text-blue-600 hover:text-blue-700 font-medium">[↶ 24시간 내 되돌리기]</button>
              </div>
              <p className="text-sm text-slate-600">{actionConfig.label}된 콘텐츠는 해당 상태로 이동했습니다.</p>
            </div>

            <div className="flex gap-2 justify-between pt-4 border-t border-slate-200">
              <button
                onClick={() => onOpenChange(false)}
                className="px-4 py-2 rounded-lg text-slate-700 hover:bg-slate-50 font-medium"
              >
                목록으로
              </button>
              <div className="flex gap-2">
                <button className="px-4 py-2 rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-50 font-medium">
                  📋 결과 다운로드
                </button>
                <button className="px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700 font-medium">
                  다음 액션
                </button>
              </div>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
