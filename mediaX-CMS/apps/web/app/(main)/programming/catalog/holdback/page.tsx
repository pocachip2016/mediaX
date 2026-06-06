"use client"

import { useEffect, useState, useCallback } from "react"
import { Plus, Trash2 } from "lucide-react"
import { cn } from "@workspace/ui/lib/utils"
import { catalogApi, type HoldbackPolicy, type HoldbackSchedule } from "@/lib/api"

const PRICE_RULE_LABELS: Record<string, string> = {
  premium: "프리미엄",
  standard: "일반",
  discount: "할인",
  subscription: "구독형",
}

const STATUS_COLORS: Record<string, string> = {
  scheduled: "text-blue-500",
  active: "text-green-500",
  expired: "text-muted-foreground",
}

// ── 정책 폼 ──────────────────────────────────────────────────────────────────

function PolicyForm({
  initial,
  onSave,
  onCancel,
}: {
  initial?: Partial<HoldbackPolicy>
  onSave: (data: Parameters<typeof catalogApi.upsertHoldbackPolicy>[0]) => Promise<void>
  onCancel: () => void
}) {
  const [cpName, setCpName] = useState(initial?.cp_name ?? "")
  const [windowNo, setWindowNo] = useState(String(initial?.window_no ?? ""))
  const [name, setName] = useState(initial?.name ?? "")
  const [offsetStart, setOffsetStart] = useState(String(initial?.offset_days_start ?? "0"))
  const [offsetEnd, setOffsetEnd] = useState(initial?.offset_days_end != null ? String(initial.offset_days_end) : "")
  const [priceRule, setPriceRule] = useState(initial?.price_rule ?? "premium")
  const [saving, setSaving] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    try {
      await onSave({
        cp_name: cpName,
        window_no: parseInt(windowNo, 10),
        name,
        offset_days_start: parseInt(offsetStart, 10),
        offset_days_end: offsetEnd !== "" ? parseInt(offsetEnd, 10) : null,
        price_rule: priceRule,
      })
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={(e) => void handleSubmit(e)} className="grid grid-cols-2 gap-3 rounded-lg border border-dashed p-3 text-sm">
      <div className="flex flex-col gap-1">
        <label className="text-xs text-muted-foreground">CP명</label>
        <input value={cpName} onChange={(e) => setCpName(e.target.value)} required
          className="h-7 rounded border border-border bg-background px-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring" />
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-xs text-muted-foreground">윈도우 번호</label>
        <input type="number" min={1} value={windowNo} onChange={(e) => setWindowNo(e.target.value)} required
          className="h-7 rounded border border-border bg-background px-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring" />
      </div>
      <div className="col-span-2 flex flex-col gap-1">
        <label className="text-xs text-muted-foreground">이름</label>
        <input value={name} onChange={(e) => setName(e.target.value)} required
          className="h-7 rounded border border-border bg-background px-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring" />
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-xs text-muted-foreground">시작 offset (일)</label>
        <input type="number" min={0} value={offsetStart} onChange={(e) => setOffsetStart(e.target.value)} required
          className="h-7 rounded border border-border bg-background px-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring" />
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-xs text-muted-foreground">종료 offset (일, 빈 칸=무기한)</label>
        <input type="number" min={0} value={offsetEnd} onChange={(e) => setOffsetEnd(e.target.value)}
          placeholder="무기한"
          className="h-7 rounded border border-border bg-background px-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring" />
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-xs text-muted-foreground">가격 규칙</label>
        <select value={priceRule} onChange={(e) => setPriceRule(e.target.value)}
          className="h-7 rounded border border-border bg-background px-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring">
          {Object.entries(PRICE_RULE_LABELS).map(([v, l]) => (
            <option key={v} value={v}>{l}</option>
          ))}
        </select>
      </div>
      <div className="col-span-2 flex justify-end gap-2">
        <button type="button" onClick={onCancel}
          className="rounded px-3 py-1 text-xs text-muted-foreground hover:text-foreground">취소</button>
        <button type="submit" disabled={saving}
          className="rounded bg-primary px-3 py-1 text-xs text-primary-foreground disabled:opacity-50">
          {saving ? "저장 중…" : "저장"}
        </button>
      </div>
    </form>
  )
}

// ── 스케줄 목록 ───────────────────────────────────────────────────────────────

function ScheduleList({
  contentId,
  schedules,
  onActivate,
}: {
  contentId: number
  schedules: HoldbackSchedule[]
  onActivate: (windowNo: number) => void
}) {
  if (schedules.length === 0)
    return <p className="py-2 text-xs text-muted-foreground">스케줄 없음</p>

  return (
    <div className="divide-y divide-border text-xs">
      {schedules.map((s) => (
        <div key={s.id} className="flex items-center gap-3 py-1.5">
          <span className="w-6 text-muted-foreground">W{s.window_no}</span>
          <span>{s.start_date}</span>
          <span className="text-muted-foreground">→ {s.end_date ?? "무기한"}</span>
          <span className={cn("font-medium", STATUS_COLORS[s.status] ?? "")}>
            {s.status}
          </span>
          {s.status === "scheduled" && (
            <button
              onClick={() => onActivate(s.window_no)}
              className="ml-auto rounded bg-green-600/10 px-2 py-0.5 text-xs text-green-600 hover:bg-green-600/20"
            >
              활성화
            </button>
          )}
        </div>
      ))}
    </div>
  )
}

// ── 페이지 ────────────────────────────────────────────────────────────────────

export default function HoldbackPage() {
  const [policies, setPolicies] = useState<HoldbackPolicy[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [filterCp, setFilterCp] = useState("")

  // 콘텐츠 스케줄 패널
  const [contentId, setContentId] = useState("")
  const [schedules, setSchedules] = useState<HoldbackSchedule[]>([])
  const [baseDate, setBaseDate] = useState(
    () => new Date().toISOString().slice(0, 10)
  )
  const [scheduleLoading, setScheduleLoading] = useState(false)

  const fetchPolicies = useCallback(async () => {
    try {
      setError(null)
      const data = await catalogApi.listHoldbackPolicies(filterCp || undefined)
      setPolicies(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : "로드 실패")
    } finally {
      setLoading(false)
    }
  }, [filterCp])

  useEffect(() => { void fetchPolicies() }, [fetchPolicies])

  const handleSavePolicy = async (data: Parameters<typeof catalogApi.upsertHoldbackPolicy>[0]) => {
    await catalogApi.upsertHoldbackPolicy(data)
    setShowForm(false)
    void fetchPolicies()
  }

  const handleDeletePolicy = async (id: number) => {
    if (!confirm("정책을 삭제할까요?")) return
    await catalogApi.deleteHoldbackPolicy(id)
    void fetchPolicies()
  }

  const handleApply = async () => {
    const id = parseInt(contentId, 10)
    if (isNaN(id)) return
    setScheduleLoading(true)
    try {
      await catalogApi.applyHoldback(id, baseDate)
      const s = await catalogApi.listHoldbackSchedules(id)
      setSchedules(s)
    } finally {
      setScheduleLoading(false)
    }
  }

  const handleActivate = async (windowNo: number) => {
    const id = parseInt(contentId, 10)
    if (isNaN(id)) return
    await catalogApi.activateWindow(id, windowNo, {})
    const s = await catalogApi.listHoldbackSchedules(id)
    setSchedules(s)
  }

  return (
    <div className="flex flex-col gap-6 p-6">
      {/* 헤더 */}
      <div>
        <h1 className="text-xl font-semibold">홀드백 정책</h1>
        <p className="mt-0.5 text-sm text-muted-foreground">
          CP별 윈도우 템플릿(Window 1~4)과 콘텐츠 홀드백 스케줄을 관리합니다.
        </p>
      </div>

      {/* ── 정책 목록 ── */}
      <section className="flex flex-col gap-3">
        <div className="flex items-center gap-2">
          <h2 className="font-medium">CP 윈도우 템플릿</h2>
          <div className="flex-1" />
          <input
            value={filterCp}
            onChange={(e) => setFilterCp(e.target.value)}
            placeholder="CP명 필터"
            className="h-7 w-36 rounded border border-border bg-background px-2 text-xs focus:outline-none focus:ring-1 focus:ring-ring"
          />
          <button
            onClick={() => setShowForm(true)}
            className="flex items-center gap-1 rounded-md bg-primary px-2.5 py-1.5 text-xs text-primary-foreground hover:bg-primary/90"
          >
            <Plus className="h-3 w-3" /> 정책 추가
          </button>
        </div>

        {showForm && (
          <PolicyForm
            onSave={handleSavePolicy}
            onCancel={() => setShowForm(false)}
          />
        )}

        <div className="rounded-lg border bg-card">
          {loading ? (
            <div className="space-y-2 p-4">
              {[1, 2].map((i) => <div key={i} className="h-6 animate-pulse rounded bg-muted" />)}
            </div>
          ) : error ? (
            <p className="p-4 text-sm text-destructive">{error}</p>
          ) : policies.length === 0 ? (
            <p className="p-4 text-sm text-muted-foreground">등록된 정책 없음</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/30 text-xs text-muted-foreground">
                  <th className="px-3 py-2 text-left">CP명</th>
                  <th className="px-2 py-2 text-center">윈도우</th>
                  <th className="px-2 py-2 text-left">이름</th>
                  <th className="px-2 py-2 text-right">시작(일)</th>
                  <th className="px-2 py-2 text-right">종료(일)</th>
                  <th className="px-2 py-2 text-center">규칙</th>
                  <th className="px-2 py-2" />
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {policies.map((p) => (
                  <tr key={p.id} className="hover:bg-muted/20">
                    <td className="px-3 py-1.5">{p.cp_name}</td>
                    <td className="px-2 py-1.5 text-center">{p.window_no}</td>
                    <td className="px-2 py-1.5">{p.name}</td>
                    <td className="px-2 py-1.5 text-right">{p.offset_days_start}</td>
                    <td className="px-2 py-1.5 text-right">{p.offset_days_end ?? "무기한"}</td>
                    <td className="px-2 py-1.5 text-center text-xs text-muted-foreground">
                      {PRICE_RULE_LABELS[p.price_rule] ?? p.price_rule}
                    </td>
                    <td className="px-2 py-1.5 text-right">
                      <button
                        onClick={() => void handleDeletePolicy(p.id)}
                        className="rounded p-1 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                      >
                        <Trash2 className="h-3 w-3" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>

      {/* ── 콘텐츠 스케줄 ── */}
      <section className="flex flex-col gap-3">
        <h2 className="font-medium">콘텐츠 홀드백 스케줄</h2>

        <div className="flex items-end gap-2">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground">콘텐츠 ID</label>
            <input
              type="number"
              min={1}
              value={contentId}
              onChange={(e) => setContentId(e.target.value)}
              className="h-7 w-28 rounded border border-border bg-background px-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground">기준일 (base_date)</label>
            <input
              type="date"
              value={baseDate}
              onChange={(e) => setBaseDate(e.target.value)}
              className="h-7 rounded border border-border bg-background px-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
            />
          </div>
          <button
            onClick={() => void handleApply()}
            disabled={scheduleLoading || !contentId}
            className="rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {scheduleLoading ? "적용 중…" : "정책 적용"}
          </button>
        </div>

        {schedules.length > 0 && (
          <div className="rounded-lg border bg-card p-3">
            <ScheduleList
              contentId={parseInt(contentId, 10)}
              schedules={schedules}
              onActivate={(w) => void handleActivate(w)}
            />
          </div>
        )}
      </section>
    </div>
  )
}
