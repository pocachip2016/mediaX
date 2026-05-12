"use client"

import { useState } from "react"
import { AlertCircle, Check, X, Clock } from "lucide-react"
import { cn } from "@workspace/ui/lib/utils"

type BulkStep = "confirm" | "progress" | "result"

const selectedItems = [
  { id: 1, title: "기생충", cp: "CJ ENM", status: "review" },
  { id: 2, title: "부산행", cp: "Next Ent", status: "review" },
  { id: 3, title: "미나리", cp: "A24", status: "staging" },
]

export default function PrototypeBulkPage() {
  const [step, setStep] = useState<BulkStep>("confirm")
  const [reason, setReason] = useState("")
  const [progress, setProgress] = useState(0)

  // Simulate progress
  const startBulkAction = () => {
    setStep("progress")
    let p = 0
    const interval = setInterval(() => {
      p += Math.random() * 20
      if (p >= 100) {
        p = 100
        clearInterval(interval)
        setTimeout(() => setStep("result"), 500)
      }
      setProgress(Math.min(p, 100))
    }, 300)
  }

  return (
    <div className="min-h-screen bg-slate-50 p-6 flex items-center justify-center">
      <div className="w-full max-w-2xl">
        {/* Confirm Step */}
        {step === "confirm" && (
          <div className="bg-white rounded-lg border border-slate-200 shadow-lg overflow-hidden">
            <div className="bg-amber-50 border-b border-amber-200 px-6 py-4 flex items-start gap-3">
              <AlertCircle className="h-5 w-5 text-amber-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold text-amber-900">3개 콘텐츠를 승인하시겠습니까?</p>
                <p className="text-sm text-amber-700 mt-1">이 작업은 되돌릴 수 있습니다 (24시간 내)</p>
              </div>
            </div>

            <div className="p-6 space-y-4">
              <div className="bg-slate-50 rounded-lg p-4">
                <h3 className="font-semibold text-slate-900 mb-3 text-sm">대상 콘텐츠</h3>
                <div className="space-y-2">
                  {selectedItems.map((item) => (
                    <div key={item.id} className="flex items-center justify-between text-sm">
                      <div>
                        <p className="font-medium text-slate-900">{item.title}</p>
                        <p className="text-xs text-slate-500">{item.cp}</p>
                      </div>
                      <span className={cn("px-2 py-0.5 rounded text-xs font-medium", item.status === "staging" ? "bg-violet-100 text-violet-700" : "bg-amber-100 text-amber-700")}>
                        {item.status === "staging" ? "자동검토" : "검수"}
                      </span>
                      <span className="text-xs text-green-700 font-medium">✓ 승인</span>
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">승인 사유 (선택)</label>
                <textarea
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="예: 메타 확인 완료, 외부 소스 일치"
                  rows={3}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500"
                />
              </div>

              <div className="flex items-center gap-2 text-sm">
                <input type="checkbox" id="noask" className="h-4 w-4 cursor-pointer" />
                <label htmlFor="noask" className="text-slate-600 cursor-pointer">이 액션을 다시 묻지 않음 (10건 이하만)</label>
              </div>

              <div className="flex gap-2 justify-end pt-4 border-t border-slate-200">
                <button className="px-4 py-2 rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-50 font-medium">취소</button>
                <button onClick={startBulkAction} className="px-4 py-2 rounded-lg bg-green-600 text-white hover:bg-green-700 font-medium inline-flex items-center gap-2">
                  <Check className="h-4 w-4" />
                  3개 승인
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Progress Step */}
        {step === "progress" && (
          <div className="bg-white rounded-lg border border-slate-200 shadow-lg overflow-hidden">
            <div className="bg-blue-50 border-b border-blue-200 px-6 py-4">
              <p className="font-semibold text-blue-900 flex items-center gap-2">
                <Clock className="h-4 w-4 animate-spin" />
                승인 처리 중...
              </p>
            </div>

            <div className="p-6 space-y-6">
              <div>
                <div className="flex items-center justify-between mb-2">
                  <p className="text-sm font-medium text-slate-700">전체 진행률</p>
                  <span className="text-sm font-semibold text-slate-900">{Math.round(progress)}%</span>
                </div>
                <div className="w-full bg-slate-200 rounded-full h-3 overflow-hidden">
                  <div className="bg-blue-500 h-full transition-all duration-300" style={{ width: `${progress}%` }} />
                </div>
              </div>

              <div className="space-y-2">
                {selectedItems.map((item, i) => {
                  const itemProgress = Math.min(progress * 1.2 - i * 20, 100)
                  const itemStatus = itemProgress >= 100 ? "done" : itemProgress > 0 ? "processing" : "pending"

                  return (
                    <div key={item.id} className="flex items-center gap-3">
                      <div className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium flex-shrink-0" style={{ backgroundColor: itemStatus === "done" ? "#22c55e" : itemStatus === "processing" ? "#3b82f6" : "#e5e7eb" }}>
                        {itemStatus === "done" ? <Check className="h-4 w-4 text-white" /> : itemStatus === "processing" ? <Clock className="h-3 w-3 text-white animate-spin" /> : ""}
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
          </div>
        )}

        {/* Result Step */}
        {step === "result" && (
          <div className="bg-white rounded-lg border border-slate-200 shadow-lg overflow-hidden">
            <div className="bg-green-50 border-b border-green-200 px-6 py-4">
              <p className="font-semibold text-green-900 flex items-center gap-2">
                <Check className="h-5 w-5 text-green-600" />
                3개 콘텐츠를 승인했습니다
              </p>
            </div>

            <div className="p-6 space-y-4">
              <div className="bg-green-50 rounded-lg border border-green-200 p-4">
                <p className="text-sm font-medium text-green-900 mb-3">✓ 성공 3개</p>
                <div className="space-y-1">
                  {selectedItems.map((item) => (
                    <div key={item.id} className="flex items-center gap-2 text-sm">
                      <Check className="h-4 w-4 text-green-600 flex-shrink-0" />
                      <span className="text-green-700">{item.title} (#)</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="border border-slate-200 rounded-lg p-4">
                <div className="flex items-center justify-between mb-3">
                  <p className="text-sm font-medium text-slate-700">다음 액션</p>
                  <button className="text-xs text-blue-600 hover:text-blue-700 font-medium">[↶ 24시간 내 되돌리기]</button>
                </div>
                <p className="text-sm text-slate-600">승인된 콘텐츠는 "승인됨" 상태로 이동했습니다.</p>
              </div>

              <div className="flex gap-2 justify-between pt-4 border-t border-slate-200">
                <button className="px-4 py-2 rounded-lg text-slate-700 hover:bg-slate-50 font-medium">목록으로</button>
                <div className="flex gap-2">
                  <button className="px-4 py-2 rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-50 font-medium">📋 결과 다운로드</button>
                  <button className="px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700 font-medium">다음 검수 시작</button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
