"use client"

import { useState } from "react"
import { AlertCircle, RefreshCw, Search } from "lucide-react"
import {
  medisearchApi,
  metadataApi,
  type MediSearchResult,
  type ContentDetail,
} from "@/lib/api"
import {
  MetaColumn,
  FacetColumn,
  ColHeader,
  FieldRow,
  META_FIELDS,
} from "./MediSearchColumns"
import { cn } from "@workspace/ui/lib/utils"

// ── Col1: 현재값 ──────────────────────────────────────────

function CurrentValuesColumn({ currentValues }: { currentValues: Record<string, string | null> }) {
  return (
    <div className="rounded-xl border bg-card shadow-sm overflow-hidden flex flex-col">
      <ColHeader>현재 저장값</ColHeader>
      <div className="overflow-y-auto flex-1">
        {META_FIELDS.map(({ key, label }) => (
          <FieldRow key={key} label={label}>
            <span className={cn("text-xs break-words", currentValues[key] ? "text-foreground" : "text-muted-foreground italic")}>
              {currentValues[key] ?? "없음"}
            </span>
          </FieldRow>
        ))}
      </div>
    </div>
  )
}

// ── MediSearchPanel (메인) ────────────────────────────────

interface MediSearchPanelProps {
  contentId: number
  currentValues: Record<string, string | null>
  onContentRefresh(updated: ContentDetail): void
}

export function MediSearchPanel({ contentId, currentValues, onContentRefresh }: MediSearchPanelProps) {
  const [state, setState] = useState<"idle" | "loading" | "loaded" | "error">("idle")
  const [result, setResult] = useState<MediSearchResult | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [applying, setApplying] = useState<string | null>(null)
  const [applied, setApplied] = useState<Set<string>>(new Set())
  const [evaluating, setEvaluating] = useState(false)

  const handleSearch = async () => {
    setState("loading")
    setErrorMsg(null)
    try {
      const data = await medisearchApi.search(contentId, { include_facet: true, force_facet: false })
      setResult(data)
      setState("loaded")
      setApplied(new Set())
    } catch (err) {
      const msg = err instanceof Error ? err.message : "MediSearch 검색 실패"
      setErrorMsg(msg)
      setState("error")
    }
  }

  const handleApply = async (field: string) => {
    if (!result) return
    setApplying(field)
    try {
      await metadataApi.applyExternalFields(contentId, result.meta_source_id, [field])
      const updated = await metadataApi.getContent(contentId)
      onContentRefresh(updated)
      setApplied((prev) => new Set([...prev, field]))
    } catch (err) {
      alert(err instanceof Error ? `적용 실패: ${err.message}` : "적용 실패")
    } finally {
      setApplying(null)
    }
  }

  const handleRequestEvaluate = async () => {
    setEvaluating(true)
    try {
      const data = await medisearchApi.search(contentId, { include_facet: true, force_facet: true })
      setResult(data)
      setState("loaded")
    } catch {
      alert("Facet 평가 요청 실패")
    } finally {
      setEvaluating(false)
    }
  }

  if (state === "idle") {
    return (
      <div className="rounded-xl border bg-card shadow-sm p-6 flex flex-col items-center justify-center gap-3 min-h-[120px]">
        <p className="text-sm text-muted-foreground">MediSearch에서 메타/Facet를 검색합니다.</p>
        <button
          onClick={handleSearch}
          className="flex items-center gap-1.5 px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm hover:bg-primary/90 transition-colors"
        >
          <Search className="h-4 w-4" />검색 시작
        </button>
      </div>
    )
  }

  if (state === "loading") {
    return (
      <div className="rounded-xl border bg-card shadow-sm p-6 flex items-center justify-center gap-2 min-h-[120px]">
        <RefreshCw className="h-4 w-4 animate-spin text-muted-foreground" />
        <span className="text-sm text-muted-foreground">MediSearch 검색 중…</span>
      </div>
    )
  }

  if (state === "error") {
    return (
      <div className="rounded-xl border bg-destructive/10 border-destructive/30 shadow-sm p-4 space-y-2">
        <div className="flex items-center gap-2">
          <AlertCircle className="h-4 w-4 text-destructive" />
          <span className="text-sm font-medium text-destructive">검색 실패</span>
        </div>
        <p className="text-xs text-muted-foreground">{errorMsg}</p>
        <p className="text-xs text-muted-foreground">MediSearch 서버가 실행 중인지 확인하세요 (포트 8080).</p>
        <button
          onClick={handleSearch}
          className="text-xs px-3 py-1 rounded bg-muted hover:bg-muted/80 transition-colors"
        >
          다시 시도
        </button>
      </div>
    )
  }

  if (!result) return null
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <p className="text-xs text-muted-foreground">
          <span className="font-medium text-foreground">{result.query}</span> 검색 결과
        </p>
        <button
          onClick={handleSearch}
          className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          <RefreshCw className="h-3 w-3" />재검색
        </button>
      </div>

      <div className="grid grid-cols-3 gap-3 min-h-[360px]">
        <CurrentValuesColumn currentValues={currentValues} />
        <MetaColumn
          result={result}
          applying={applying}
          applied={applied}
          onApply={handleApply}
        />
        <FacetColumn
          facet={result.facet}
          onRequestEvaluate={handleRequestEvaluate}
          evaluating={evaluating}
        />
      </div>
    </div>
  )
}
