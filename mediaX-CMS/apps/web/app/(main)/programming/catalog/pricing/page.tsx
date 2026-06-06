"use client"

import { useEffect, useState, useCallback } from "react"
import { cn } from "@workspace/ui/lib/utils"
import {
  catalogApi,
  type Quality,
  type PurchaseType,
  type PriceMatrix,
  type PriceChangeLog,
} from "@/lib/api"

const QUALITIES: Quality[] = ["SD", "HD", "FHD", "UHD_4K"]
const PURCHASE_TYPES: PurchaseType[] = [
  "single",
  "series_episode",
  "season_package",
  "est_single",
  "est_season",
]
const PURCHASE_LABELS: Record<PurchaseType, string> = {
  single: "단편 개별",
  series_episode: "시리즈 에피",
  season_package: "시즌 패키지",
  est_single: "평생소장 (단편)",
  est_season: "평생소장 (시즌)",
}

// ── 매트릭스 셀 ──────────────────────────────────────────────────────────────

function PriceCell({
  contentId,
  quality,
  purchaseType,
  value,
  onSaved,
}: {
  contentId: number
  quality: Quality
  purchaseType: PurchaseType
  value: number | undefined
  onSaved: () => void
}) {
  const [editing, setEditing] = useState(false)
  const [input, setInput] = useState("")
  const [saving, setSaving] = useState(false)

  const startEdit = () => {
    setInput(value != null ? String(value) : "")
    setEditing(true)
  }

  const handleSave = async () => {
    const price = parseInt(input, 10)
    if (isNaN(price) || price < 0) return
    setSaving(true)
    try {
      await catalogApi.setPrice(contentId, { quality, purchase_type: purchaseType, price })
      onSaved()
      setEditing(false)
    } finally {
      setSaving(false)
    }
  }

  if (editing) {
    return (
      <div className="flex items-center gap-1">
        <input
          autoFocus
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") void handleSave()
            if (e.key === "Escape") setEditing(false)
          }}
          disabled={saving}
          className="w-20 rounded border border-border bg-background px-1 py-0.5 text-right text-xs focus:outline-none focus:ring-1 focus:ring-ring"
        />
        <button
          onClick={() => void handleSave()}
          disabled={saving}
          className="rounded bg-primary px-1.5 py-0.5 text-xs text-primary-foreground disabled:opacity-50"
        >
          {saving ? "…" : "저장"}
        </button>
        <button onClick={() => setEditing(false)} className="text-xs text-muted-foreground">
          취소
        </button>
      </div>
    )
  }

  return (
    <button
      onClick={startEdit}
      className={cn(
        "w-full rounded px-2 py-1 text-right text-xs hover:bg-muted/50",
        value == null && "text-muted-foreground/40"
      )}
    >
      {value != null ? `₩${value.toLocaleString()}` : "—"}
    </button>
  )
}

// ── 변경 이력 ─────────────────────────────────────────────────────────────────

function PriceChangeLogPanel({
  logs,
}: {
  logs: PriceChangeLog[]
}) {
  if (logs.length === 0)
    return <p className="py-4 text-center text-xs text-muted-foreground">변경 이력 없음</p>

  return (
    <div className="divide-y divide-border text-xs">
      {logs.map((log) => (
        <div key={log.id} className="flex items-center gap-3 px-2 py-1.5">
          <span className="w-12 shrink-0 text-muted-foreground">{log.quality}</span>
          <span className="w-28 shrink-0 text-muted-foreground">{log.purchase_type}</span>
          <span className="flex-1">
            {log.old_price != null ? `₩${log.old_price.toLocaleString()} →` : "신규 "}
            <span className="font-medium"> ₩{log.new_price.toLocaleString()}</span>
          </span>
          {log.reason && <span className="truncate text-muted-foreground">{log.reason}</span>}
          <span className="shrink-0 text-muted-foreground">
            {log.created_at ? new Date(log.created_at).toLocaleDateString("ko-KR") : ""}
          </span>
        </div>
      ))}
    </div>
  )
}

// ── 페이지 ────────────────────────────────────────────────────────────────────

export default function PricingPage() {
  const [contentId, setContentId] = useState<string>("")
  const [matrix, setMatrix] = useState<PriceMatrix | null>(null)
  const [logs, setLogs] = useState<PriceChangeLog[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [tab, setTab] = useState<"matrix" | "log">("matrix")

  const fetchData = useCallback(async (id: number) => {
    setLoading(true)
    setError(null)
    try {
      const [m, l] = await Promise.all([
        catalogApi.getPriceMatrix(id),
        catalogApi.listPriceChanges(id),
      ])
      setMatrix(m as PriceMatrix)
      setLogs(l)
    } catch (e) {
      setError(e instanceof Error ? e.message : "로드 실패")
    } finally {
      setLoading(false)
    }
  }, [])

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    const id = parseInt(contentId, 10)
    if (!isNaN(id) && id > 0) void fetchData(id)
  }

  const cid = parseInt(contentId, 10)

  return (
    <div className="flex flex-col gap-4 p-6">
      {/* 헤더 */}
      <div>
        <h1 className="text-xl font-semibold">가격 정책</h1>
        <p className="mt-0.5 text-sm text-muted-foreground">
          콘텐츠별 SD/HD/FHD/4K × 구매유형 가격 매트릭스를 관리합니다.
        </p>
      </div>

      {/* 콘텐츠 ID 입력 */}
      <form onSubmit={handleSearch} className="flex items-center gap-2">
        <input
          type="number"
          min={1}
          value={contentId}
          onChange={(e) => setContentId(e.target.value)}
          placeholder="콘텐츠 ID"
          className="h-8 w-36 rounded border border-border bg-background px-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
        />
        <button
          type="submit"
          className="rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground hover:bg-primary/90"
        >
          조회
        </button>
      </form>

      {loading && (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => <div key={i} className="h-8 animate-pulse rounded bg-muted" />)}
        </div>
      )}

      {error && <p className="text-sm text-destructive">{error}</p>}

      {matrix != null && !loading && (
        <>
          {/* 탭 */}
          <div className="flex gap-2 border-b border-border">
            {(["matrix", "log"] as const).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={cn(
                  "px-3 py-1.5 text-sm",
                  tab === t
                    ? "border-b-2 border-primary font-medium"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                {t === "matrix" ? "가격 매트릭스" : `변경 이력 (${logs.length})`}
              </button>
            ))}
          </div>

          {tab === "matrix" && (
            <div className="overflow-x-auto rounded-lg border bg-card">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted/30">
                    <th className="py-2 pl-3 pr-2 text-left text-xs font-medium text-muted-foreground">
                      구매유형
                    </th>
                    {QUALITIES.map((q) => (
                      <th key={q} className="px-2 py-2 text-right text-xs font-medium text-muted-foreground">
                        {q}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {PURCHASE_TYPES.map((pt) => (
                    <tr key={pt} className="hover:bg-muted/20">
                      <td className="py-1.5 pl-3 pr-2 text-xs text-muted-foreground">
                        {PURCHASE_LABELS[pt]}
                      </td>
                      {QUALITIES.map((q) => (
                        <td key={q} className="px-1 py-1">
                          <PriceCell
                            contentId={cid}
                            quality={q}
                            purchaseType={pt}
                            value={matrix[pt]?.[q]}
                            onSaved={() => void fetchData(cid)}
                          />
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {tab === "log" && (
            <div className="rounded-lg border bg-card">
              <PriceChangeLogPanel logs={logs} />
            </div>
          )}
        </>
      )}
    </div>
  )
}
