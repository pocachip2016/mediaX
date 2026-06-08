"use client"

import { useState } from "react"
import { Sparkles, Check, X, ChevronDown, ChevronUp } from "lucide-react"
import { schedulingApi } from "@/lib/api"
import type { InterpretedOut, ProgrammingLink, ProgrammingNode } from "@/lib/api"
import { cn } from "@workspace/ui/lib/utils"

type Props = {
  node: ProgrammingNode | null
  links: ProgrammingLink[]
  onReload: () => void
}

export function AiSuggestPanel({ node, links, onReload }: Props) {
  const [intent, setIntent] = useState("")
  const [threshold, setThreshold] = useState(0.3)
  const [autoExclude, setAutoExclude] = useState(true)
  const [suggesting, setSuggesting] = useState(false)
  const [result, setResult] = useState<{ saved: number; skipped: number } | null>(null)
  const [interpreted, setInterpreted] = useState<InterpretedOut | null>(null)
  const [showList, setShowList] = useState(true)
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
  const [busyId, setBusyId] = useState<number | null>(null)
  const [confirming, setConfirming] = useState(false)

  const suggestedLinks = links.filter((l) => l.status === "suggested")

  async function handleSuggest() {
    if (!node) return
    setSuggesting(true)
    setResult(null)
    setInterpreted(null)
    setSelectedIds(new Set())
    try {
      const res = await schedulingApi.suggestLinks(node.id, {
        threshold: autoExclude ? threshold : 0,
        intent: intent.trim() || undefined,
      })
      setResult({ saved: res.saved.length, skipped: res.skipped_count })
      if (res.interpreted) setInterpreted(res.interpreted)
      onReload()
    } catch {
      /* ignore */
    } finally {
      setSuggesting(false)
    }
  }

  async function handleConfirm(linkId: number) {
    setBusyId(linkId)
    await schedulingApi.confirmLink(linkId).catch(() => {})
    setBusyId(null)
    setSelectedIds((prev) => { const s = new Set(prev); s.delete(linkId); return s })
    onReload()
  }

  async function handleReject(linkId: number) {
    setBusyId(linkId)
    await schedulingApi.rejectLink(linkId).catch(() => {})
    setBusyId(null)
    setSelectedIds((prev) => { const s = new Set(prev); s.delete(linkId); return s })
    onReload()
  }

  async function handleConfirmSelected() {
    if (!selectedIds.size) return
    setConfirming(true)
    await Promise.all([...selectedIds].map((id) => schedulingApi.confirmLink(id).catch(() => {})))
    setSelectedIds(new Set())
    setConfirming(false)
    onReload()
  }

  async function handleConfirmAll() {
    setConfirming(true)
    await Promise.all(suggestedLinks.map((l) => schedulingApi.confirmLink(l.id).catch(() => {})))
    setSelectedIds(new Set())
    setConfirming(false)
    onReload()
  }

  function toggleSelect(id: number) {
    setSelectedIds((prev) => {
      const s = new Set(prev)
      s.has(id) ? s.delete(id) : s.add(id)
      return s
    })
  }

  function toggleSelectAll() {
    if (selectedIds.size === suggestedLinks.length) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(suggestedLinks.map((l) => l.id)))
    }
  }

  if (!node) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <p className="text-sm text-muted-foreground">노드를 선택하세요</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Intent + controls */}
      <div className="px-4 py-3 border-b space-y-2.5 flex-shrink-0">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-blue-500 flex-shrink-0" />
          <span className="text-sm font-medium">AI 자동 추천</span>
        </div>

        <textarea
          value={intent}
          onChange={(e) => setIntent(e.target.value)}
          placeholder="편성 의도 입력 (선택) — 예: 주말 가족이 몰아볼 따뜻한 한국 드라마"
          rows={2}
          className="w-full resize-none rounded-md border bg-background px-3 py-2 text-xs placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
        />

        <div className="flex items-center gap-2">
          <label className="text-xs text-muted-foreground whitespace-nowrap">임계값</label>
          <input
            type="range"
            min={0.1}
            max={0.9}
            step={0.05}
            value={threshold}
            onChange={(e) => setThreshold(Number(e.target.value))}
            disabled={!autoExclude}
            className="flex-1 h-1 accent-primary disabled:opacity-40"
          />
          <span className="text-xs text-muted-foreground w-8 text-right">{threshold.toFixed(2)}</span>
        </div>

        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={autoExclude}
            onChange={(e) => setAutoExclude(e.target.checked)}
            className="h-3.5 w-3.5 rounded accent-primary"
          />
          <span className="text-xs text-muted-foreground">신뢰도 미달 자동제외</span>
        </label>

        <button
          onClick={handleSuggest}
          disabled={suggesting}
          className="w-full text-sm py-1.5 rounded-md bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          {suggesting ? "분석중…" : "추천 실행"}
        </button>

        {/* AI 해석 결과 칩 */}
        {interpreted && (
          <div className="space-y-1">
            <p className="text-xs text-muted-foreground">
              AI 해석 <span className="text-blue-500">({interpreted.provider_used})</span>
            </p>
            <div className="flex flex-wrap gap-1">
              {Object.entries(interpreted.rule_query).map(([k, v]) => (
                <span key={k} className="text-xs rounded-full bg-blue-100 text-blue-700 px-2 py-0.5">
                  {k}={String(v)}
                </span>
              ))}
              {Object.entries(interpreted.facets).flatMap(([k, v]) =>
                Array.isArray(v)
                  ? v.map((val) => (
                      <span key={`${k}-${val}`} className="text-xs rounded-full bg-violet-100 text-violet-700 px-2 py-0.5">
                        {val}
                      </span>
                    ))
                  : []
              )}
            </div>
          </div>
        )}

        {result && (
          <p className="text-xs text-center text-muted-foreground">
            <span className="text-green-600 font-medium">{result.saved}</span>건 저장 ·{" "}
            {result.skipped}건 제외
          </p>
        )}
      </div>

      {/* Suggested list */}
      {suggestedLinks.length > 0 ? (
        <div className="flex-1 overflow-hidden flex flex-col min-h-0">
          <button
            onClick={() => setShowList((v) => !v)}
            className="flex items-center justify-between px-4 py-2 text-xs font-medium text-muted-foreground hover:text-foreground border-b flex-shrink-0"
          >
            <span className="flex items-center gap-2">
              추천 링크 ({suggestedLinks.length})
              <button
                onClick={(e) => { e.stopPropagation(); toggleSelectAll() }}
                className="text-xs text-blue-500 hover:underline"
              >
                {selectedIds.size === suggestedLinks.length ? "전체해제" : "전체선택"}
              </button>
            </span>
            {showList ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
          </button>

          {showList && (
            <div className="flex-1 overflow-y-auto p-3 space-y-1.5">
              {suggestedLinks.map((link) => {
                const aiReason = link.copy_override?.["_ai_reason"] as string | undefined
                const label =
                  link.child_content_id != null
                    ? `콘텐츠 #${link.child_content_id}`
                    : `노드 #${link.child_node_id}`
                const isSelected = selectedIds.has(link.id)
                return (
                  <div
                    key={link.id}
                    className={cn(
                      "rounded-lg border px-3 py-2 space-y-1 cursor-pointer",
                      isSelected ? "bg-blue-50/60 border-blue-200" : "bg-amber-50/50"
                    )}
                    onClick={() => toggleSelect(link.id)}
                  >
                    <div className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => toggleSelect(link.id)}
                        onClick={(e) => e.stopPropagation()}
                        className="h-3.5 w-3.5 rounded accent-primary flex-shrink-0"
                      />
                      <span className="text-xs font-medium truncate flex-1">{label}</span>
                      <div className="flex items-center gap-1 flex-shrink-0">
                        {link.confidence != null && (
                          <span className="text-xs text-muted-foreground">
                            {Math.round(link.confidence * 100)}%
                          </span>
                        )}
                        <button
                          disabled={busyId === link.id}
                          onClick={(e) => { e.stopPropagation(); handleConfirm(link.id) }}
                          title="확정"
                          className="p-0.5 rounded hover:bg-green-100 text-green-600 disabled:opacity-50"
                        >
                          <Check className="h-3.5 w-3.5" />
                        </button>
                        <button
                          disabled={busyId === link.id}
                          onClick={(e) => { e.stopPropagation(); handleReject(link.id) }}
                          title="거부"
                          className="p-0.5 rounded hover:bg-red-100 text-red-600 disabled:opacity-50"
                        >
                          <X className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </div>
                    {aiReason && (
                      <p className="text-xs text-muted-foreground line-clamp-2 pl-5">{aiReason}</p>
                    )}
                  </div>
                )
              })}
            </div>
          )}

          {/* 하단 액션바 */}
          <div className="px-3 py-2 border-t flex gap-2 flex-shrink-0">
            <button
              onClick={handleConfirmSelected}
              disabled={!selectedIds.size || confirming}
              className="flex-1 text-xs py-1.5 rounded-md bg-green-600 text-white hover:bg-green-700 disabled:opacity-40 transition-colors"
            >
              선택 확정 ({selectedIds.size})
            </button>
            <button
              onClick={handleConfirmAll}
              disabled={!suggestedLinks.length || confirming}
              className="flex-1 text-xs py-1.5 rounded-md border hover:bg-accent disabled:opacity-40 transition-colors"
            >
              전체 확정
            </button>
          </div>
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center">
          <p className="text-xs text-muted-foreground">추천 링크 없음</p>
        </div>
      )}
    </div>
  )
}
