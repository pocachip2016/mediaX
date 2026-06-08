"use client"

import { useState } from "react"
import { Sparkles, Check, X, ChevronDown, ChevronUp } from "lucide-react"
import { schedulingApi } from "@/lib/api"
import type { ProgrammingNode, ProgrammingLink } from "@/lib/api"
import { cn } from "@workspace/ui/lib/utils"

type Props = {
  node: ProgrammingNode | null
  links: ProgrammingLink[]
  onReload: () => void
}

export function NodePropsPanel({ node, links, onReload }: Props) {
  const [suggesting, setSuggesting] = useState(false)
  const [suggestResult, setSuggestResult] = useState<{ saved: number; skipped: number } | null>(null)
  const [threshold, setThreshold] = useState(0.3)
  const [showSuggested, setShowSuggested] = useState(true)
  const [busyId, setBusyId] = useState<number | null>(null)

  const suggestedLinks = links.filter((l) => l.status === "suggested")
  const activeCount = links.filter((l) => l.status === "active").length

  async function handleSuggest() {
    if (!node) return
    setSuggesting(true)
    setSuggestResult(null)
    try {
      const result = await schedulingApi.suggestLinks(node.id, { threshold })
      setSuggestResult({ saved: result.saved.length, skipped: result.skipped_count })
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
    onReload()
  }

  async function handleReject(linkId: number) {
    setBusyId(linkId)
    await schedulingApi.rejectLink(linkId).catch(() => {})
    setBusyId(null)
    onReload()
  }

  if (!node) {
    return (
      <div className="h-full flex items-center justify-center border rounded-xl bg-card">
        <p className="text-sm text-muted-foreground">노드를 선택하세요</p>
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col border rounded-xl bg-card overflow-hidden">
      {/* Node info */}
      <div className="px-4 py-3 border-b space-y-1 flex-shrink-0">
        <p className="text-xs text-muted-foreground">노드</p>
        <p className="font-semibold text-sm truncate">{node.name}</p>
        {node.headline_copy && (
          <p className="text-xs text-muted-foreground line-clamp-2">{node.headline_copy}</p>
        )}
        <div className="flex gap-3 pt-1">
          <span className="text-xs text-muted-foreground">
            <span className="font-medium text-foreground">{activeCount}</span> 활성
          </span>
          <span className="text-xs text-muted-foreground">
            <span className={cn("font-medium", suggestedLinks.length > 0 ? "text-amber-600" : "text-foreground")}>
              {suggestedLinks.length}
            </span>{" "}
            추천
          </span>
        </div>
      </div>

      {/* AI Suggest */}
      <div className="px-4 py-3 border-b space-y-2 flex-shrink-0">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-blue-500" />
          <span className="text-sm font-medium">AI 자동 추천</span>
        </div>

        <div className="flex items-center gap-2">
          <label className="text-xs text-muted-foreground whitespace-nowrap">임계값</label>
          <input
            type="range"
            min={0.1}
            max={0.9}
            step={0.05}
            value={threshold}
            onChange={(e) => setThreshold(Number(e.target.value))}
            className="flex-1 h-1 accent-primary"
          />
          <span className="text-xs text-muted-foreground w-8 text-right">{threshold.toFixed(2)}</span>
        </div>

        <button
          onClick={handleSuggest}
          disabled={suggesting}
          className="w-full text-sm py-1.5 rounded-md bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          {suggesting ? "분석중…" : "추천 실행"}
        </button>

        {suggestResult && (
          <p className="text-xs text-center text-muted-foreground">
            <span className="text-green-600 font-medium">{suggestResult.saved}</span>건 저장 ·{" "}
            {suggestResult.skipped}건 제외
          </p>
        )}
      </div>

      {/* Suggested list */}
      {suggestedLinks.length > 0 ? (
        <div className="flex-1 overflow-hidden flex flex-col">
          <button
            onClick={() => setShowSuggested((v) => !v)}
            className="flex items-center justify-between px-4 py-2 text-xs font-medium text-muted-foreground hover:text-foreground border-b flex-shrink-0"
          >
            <span>추천 링크 ({suggestedLinks.length})</span>
            {showSuggested ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
          </button>

          {showSuggested && (
            <div className="flex-1 overflow-y-auto p-3 space-y-1.5">
              {suggestedLinks.map((link) => {
                const aiReason = link.copy_override?.["_ai_reason"] as string | undefined
                const label =
                  link.child_content_id != null
                    ? `콘텐츠 #${link.child_content_id}`
                    : `노드 #${link.child_node_id}`
                return (
                  <div key={link.id} className="rounded-lg border bg-amber-50/50 px-3 py-2 space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-medium truncate flex-1">{label}</span>
                      <div className="flex items-center gap-1 flex-shrink-0">
                        {link.confidence != null && (
                          <span className="text-xs text-muted-foreground">
                            {Math.round(link.confidence * 100)}%
                          </span>
                        )}
                        <button
                          disabled={busyId === link.id}
                          onClick={() => handleConfirm(link.id)}
                          title="확정"
                          className="p-0.5 rounded hover:bg-green-100 text-green-600 disabled:opacity-50"
                        >
                          <Check className="h-3.5 w-3.5" />
                        </button>
                        <button
                          disabled={busyId === link.id}
                          onClick={() => handleReject(link.id)}
                          title="거부"
                          className="p-0.5 rounded hover:bg-red-100 text-red-600 disabled:opacity-50"
                        >
                          <X className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </div>
                    {aiReason && (
                      <p className="text-xs text-muted-foreground line-clamp-2">{aiReason}</p>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center">
          <p className="text-xs text-muted-foreground">추천 링크 없음</p>
        </div>
      )}
    </div>
  )
}
