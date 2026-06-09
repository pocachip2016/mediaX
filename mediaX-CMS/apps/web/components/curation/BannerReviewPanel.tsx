"use client"

import { useEffect, useState, useCallback } from "react"
import { CheckCircle, Send, Radio, RefreshCw, Plus } from "lucide-react"
import { cn } from "@workspace/ui/lib/utils"
import { curationApi } from "@/lib/api"
import type { BannerPlanOut, BannerPlanStatus } from "@/lib/api"

const STATUS_LABEL: Record<BannerPlanStatus, string> = {
  draft:     "초안",
  review:    "검토중",
  approved:  "승인됨",
  published: "발행됨",
}

const STATUS_COLOR: Record<BannerPlanStatus, string> = {
  draft:     "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400",
  review:    "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-300",
  approved:  "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300",
  published: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300",
}

function nextMonday(): string {
  const d = new Date()
  const day = d.getDay()
  const diff = day === 0 ? 1 : 8 - day
  d.setDate(d.getDate() + diff)
  return d.toISOString().split("T")[0]!
}

export function BannerReviewPanel() {
  const [plans, setPlans] = useState<BannerPlanOut[]>([])
  const [selected, setSelected] = useState<BannerPlanOut | null>(null)
  const [loading, setLoading] = useState(true)
  const [acting, setActing] = useState(false)
  const [reviewerInput, setReviewerInput] = useState("")

  const load = useCallback(() => {
    setLoading(true)
    curationApi
      .listBannerPlans()
      .then((data) => {
        setPlans(data)
        if (data.length > 0 && !selected) setSelected(data[0]!)
      })
      .finally(() => setLoading(false))
  }, [selected])

  useEffect(() => { load() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  async function handleCreate() {
    const weekStart = nextMonday()
    setActing(true)
    try {
      const plan = await curationApi.createBannerPlan(weekStart)
      setPlans((prev) => [plan, ...prev])
      setSelected(plan)
    } finally {
      setActing(false)
    }
  }

  async function handleAction(action: "submit" | "approve" | "publish") {
    if (!selected) return
    setActing(true)
    try {
      let updated: BannerPlanOut
      if (action === "submit")  updated = await curationApi.submitPlan(selected.id)
      else if (action === "approve") updated = await curationApi.approvePlan(selected.id, reviewerInput || "운영자")
      else updated = await curationApi.publishPlan(selected.id)
      setPlans((prev) => prev.map((p) => (p.id === updated.id ? updated : p)))
      setSelected(updated)
    } finally {
      setActing(false)
    }
  }

  return (
    <div className="flex gap-4 h-full">
      {/* 좌측 목록 */}
      <div className="w-52 flex-shrink-0 flex flex-col gap-2">
        <button
          onClick={handleCreate}
          disabled={acting}
          className="flex items-center gap-1.5 text-xs border rounded-md px-3 py-1.5 hover:bg-muted transition-colors w-full justify-center"
        >
          <Plus className="h-3.5 w-3.5" />
          신규 편성안 생성
        </button>

        {loading ? (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-14 rounded-md bg-muted animate-pulse" />
            ))}
          </div>
        ) : plans.length === 0 ? (
          <p className="text-xs text-muted-foreground text-center py-8">편성안 없음</p>
        ) : (
          <div className="flex flex-col gap-1 overflow-y-auto">
            {plans.map((plan) => (
              <button
                key={plan.id}
                onClick={() => setSelected(plan)}
                className={cn(
                  "text-left rounded-md border px-3 py-2 text-xs transition-colors",
                  selected?.id === plan.id
                    ? "border-primary bg-primary/5"
                    : "hover:bg-muted border-transparent"
                )}
              >
                <div className="font-medium">{plan.week_start}</div>
                <span className={cn("text-[10px] px-1.5 py-0.5 rounded-full mt-0.5 inline-block", STATUS_COLOR[plan.status])}>
                  {STATUS_LABEL[plan.status]}
                </span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* 우측 상세 */}
      <div className="flex-1 min-w-0">
        {!selected ? (
          <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
            편성안을 선택하세요
          </div>
        ) : (
          <div className="rounded-lg border bg-card p-5 flex flex-col gap-4">
            {/* 헤더 */}
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold">{selected.week_start} 주간 배너 편성안</h3>
                <span className={cn("text-xs px-2 py-0.5 rounded-full", STATUS_COLOR[selected.status])}>
                  {STATUS_LABEL[selected.status]}
                </span>
              </div>
              <button onClick={load} className="text-muted-foreground hover:text-foreground">
                <RefreshCw className="h-4 w-4" />
              </button>
            </div>

            {/* 메타 정보 */}
            <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
              <dt className="text-muted-foreground">편성 세트</dt>
              <dd>{selected.node_set_id ? `#${selected.node_set_id}` : "—"}</dd>
              <dt className="text-muted-foreground">CTR 예측</dt>
              <dd>{selected.ctr_prediction != null ? selected.ctr_prediction.toFixed(3) : "—"}</dd>
              <dt className="text-muted-foreground">승인자</dt>
              <dd>{selected.reviewer ?? "—"}</dd>
              <dt className="text-muted-foreground">승인 일시</dt>
              <dd>{selected.reviewed_at ? new Date(selected.reviewed_at).toLocaleString("ko-KR") : "—"}</dd>
              <dt className="text-muted-foreground">발행 일시</dt>
              <dd>{selected.published_at ? new Date(selected.published_at).toLocaleString("ko-KR") : "—"}</dd>
            </dl>

            {/* 액션 바 */}
            <div className="flex flex-col gap-2 pt-2 border-t">
              {selected.status === "review" && (
                <input
                  value={reviewerInput}
                  onChange={(e) => setReviewerInput(e.target.value)}
                  placeholder="승인자 이름"
                  className="text-sm border rounded px-2 py-1 bg-background w-48"
                />
              )}
              <div className="flex gap-2">
                {selected.status === "draft" && (
                  <button
                    onClick={() => handleAction("submit")}
                    disabled={acting}
                    className="flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-md bg-yellow-500 text-white hover:bg-yellow-600 disabled:opacity-50 transition-colors"
                  >
                    <Send className="h-3.5 w-3.5" />
                    리뷰 요청
                  </button>
                )}
                {selected.status === "review" && (
                  <button
                    onClick={() => handleAction("approve")}
                    disabled={acting}
                    className="flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-md bg-green-600 text-white hover:bg-green-700 disabled:opacity-50 transition-colors"
                  >
                    <CheckCircle className="h-3.5 w-3.5" />
                    승인
                  </button>
                )}
                {selected.status === "approved" && (
                  <button
                    onClick={() => handleAction("publish")}
                    disabled={acting}
                    className="flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-md bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
                  >
                    <Radio className="h-3.5 w-3.5" />
                    발행
                  </button>
                )}
                {selected.status === "published" && (
                  <span className="text-sm text-muted-foreground">발행 완료</span>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
