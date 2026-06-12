"use client"

import { useState } from "react"
import { AlertCircle, RefreshCw, Search, Sparkles } from "lucide-react"
import { medisearchApi, type MediSearchFreeResult, type MediSearchFacetInfo } from "@/lib/api"
import { MetaColumn, FacetColumn } from "@/components/contents/medisearch/MediSearchColumns"

// ── 상태 타입 ─────────────────────────────────────────────

type SearchState = "idle" | "searching" | "loaded" | "error"
type FacetState = "none" | "stored" | "evaluating" | "fresh" | "eval_error"
type EnrichState = "idle" | "enriching" | "done" | "error"

// ── 메인 페이지 ───────────────────────────────────────────

export default function WebSearchPage() {
  const [title, setTitle] = useState("")
  const [year, setYear] = useState("")
  const [contentType, setContentType] = useState("")

  const [searchState, setSearchState] = useState<SearchState>("idle")
  const [result, setResult] = useState<MediSearchFreeResult | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  const [facetState, setFacetState] = useState<FacetState>("none")
  const [facetData, setFacetData] = useState<MediSearchFacetInfo | null>(null)
  const [evalError, setEvalError] = useState<string | null>(null)

  // 웹+LLM 보강 상태 (fast 레인 이후 백그라운드)
  const [enrichState, setEnrichState] = useState<EnrichState>("idle")

  const handleSearch = async (e?: React.FormEvent) => {
    e?.preventDefault()
    const q = title.trim()
    if (!q) return

    setSearchState("searching")
    setErrorMsg(null)
    setResult(null)
    setFacetState("none")
    setFacetData(null)
    setEvalError(null)
    setEnrichState("idle")

    const params = {
      title: q,
      ...(year ? { production_year: parseInt(year, 10) } : {}),
      ...(contentType ? { content_type: contentType } : {}),
    }

    try {
      // ① fast 레인: 구조화 provider만 (~1.5s) → 즉시 렌더
      const fastData = await medisearchApi.searchByTitle({ ...params, fast: true })
      setResult(fastData)
      setSearchState("loaded")
      if (fastData.facet.origin === "stored") {
        setFacetData(fastData.facet)
        setFacetState("stored")
      }

      // ② full 레인: 웹+LLM 보강 → 백그라운드, 완료 시 결과 갱신
      setEnrichState("enriching")
      medisearchApi.searchByTitle({ ...params, fast: false }).then((fullData) => {
        setResult(fullData)
        setEnrichState("done")
        if (fullData.facet.origin === "stored") {
          setFacetData(fullData.facet)
          setFacetState("stored")
        }
      }).catch(() => {
        setEnrichState("error")
      })
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "MediSearch 검색 실패")
      setSearchState("error")
    }
  }

  const handleEvaluate = async () => {
    if (!result) return
    setFacetState("evaluating")
    setEvalError(null)
    try {
      const data = await medisearchApi.evaluateByTitle({
        title: result.query,
        ...(year ? { production_year: parseInt(year, 10) } : {}),
        ...(result.resolved_tmdb_id != null ? { tmdb_id: result.resolved_tmdb_id } : {}),
        ...(result.resolved_imdb_id ? { imdb_id: result.resolved_imdb_id } : {}),
        ...(contentType ? { content_type: contentType } : {}),
        ...(result.metadata?.original_title ? { original_title: result.metadata.original_title as string } : {}),
      })
      setFacetData(data)
      setFacetState("fresh")
    } catch (err) {
      setEvalError(err instanceof Error ? err.message : "Facet 평가 실패")
      setFacetState("eval_error")
    }
  }

  const activeFacet: MediSearchFacetInfo = facetData ?? { origin: "none" }

  return (
    <div className="px-6 py-6 max-w-[1400px] mx-auto space-y-5">
      {/* 헤더 */}
      <div>
        <h1 className="text-xl font-bold">MediSearch 외부 검색</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          제목으로 기본메타·Facet 확인 — 기본메타는 즉시, Facet은 후보 선택 후 평가
        </p>
      </div>

      {/* 검색 폼 */}
      <form onSubmit={handleSearch} className="flex gap-2 items-end flex-wrap">
        <div className="flex-1 min-w-[200px]">
          <label className="text-xs text-muted-foreground mb-1 block">제목 *</label>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="영화 또는 시리즈 제목..."
            className="w-full px-3 py-2 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
          />
        </div>
        <div className="w-28">
          <label className="text-xs text-muted-foreground mb-1 block">제작연도</label>
          <input
            type="number"
            value={year}
            onChange={(e) => setYear(e.target.value)}
            placeholder="2024"
            className="w-full px-3 py-2 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
          />
        </div>
        <div className="w-32">
          <label className="text-xs text-muted-foreground mb-1 block">유형</label>
          <select
            value={contentType}
            onChange={(e) => setContentType(e.target.value)}
            className="w-full px-3 py-2 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
          >
            <option value="">전체</option>
            <option value="movie">영화</option>
            <option value="series">시리즈</option>
          </select>
        </div>
        <button
          type="submit"
          disabled={!title.trim() || searchState === "searching"}
          className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors flex items-center gap-2"
        >
          {searchState === "searching" ? (
            <RefreshCw className="h-4 w-4 animate-spin" />
          ) : (
            <Search className="h-4 w-4" />
          )}
          검색
        </button>
      </form>

      {/* 검색 중 */}
      {searchState === "searching" && (
        <div className="rounded-xl border bg-card shadow-sm p-8 flex items-center justify-center gap-3">
          <RefreshCw className="h-5 w-5 animate-spin text-muted-foreground" />
          <span className="text-sm text-muted-foreground">MediSearch에서 기본메타를 검색하는 중…</span>
        </div>
      )}

      {/* 에러 */}
      {searchState === "error" && (
        <div className="rounded-xl border bg-destructive/10 border-destructive/30 shadow-sm p-4 space-y-2">
          <div className="flex items-center gap-2">
            <AlertCircle className="h-4 w-4 text-destructive" />
            <span className="text-sm font-medium text-destructive">검색 실패</span>
          </div>
          <p className="text-xs text-muted-foreground">{errorMsg}</p>
          <p className="text-xs text-muted-foreground">MediSearch 서버가 실행 중인지 확인하세요 (포트 8080).</p>
          <button
            onClick={() => handleSearch()}
            className="text-xs px-3 py-1 rounded bg-muted hover:bg-muted/80 transition-colors"
          >
            다시 시도
          </button>
        </div>
      )}

      {/* 결과: 2컬럼 (기본메타 | facet) — 독립 로딩 */}
      {searchState === "loaded" && result && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-xs text-muted-foreground">
              <span className="font-medium text-foreground">{result.query}</span> 검색 결과
              {result.resolved_tmdb_id && (
                <span className="ml-2 text-[10px] px-1.5 py-0.5 rounded bg-muted">
                  TMDB #{result.resolved_tmdb_id}
                </span>
              )}
            </p>
            <button
              onClick={() => handleSearch()}
              className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              <RefreshCw className="h-3 w-3" />재검색
            </button>
          </div>

          <div className="grid grid-cols-2 gap-4 min-h-[400px]">
            {/* 기본메타 컬럼 — fast 즉시 렌더 + full 보강 배지 */}
            <div className="relative">
              {enrichState === "enriching" && (
                <div className="absolute top-2 right-2 z-10 flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-primary/10 text-primary animate-pulse">
                  <RefreshCw className="h-2.5 w-2.5 animate-spin" />웹 보강 중…
                </div>
              )}
              <MetaColumn result={result} />
            </div>

            {/* Facet 컬럼 — 독립 상태 */}
            {facetState === "evaluating" ? (
              <div className="rounded-xl border bg-card shadow-sm overflow-hidden flex flex-col">
                <div className="px-3 py-2 border-b bg-muted/40 text-xs font-semibold text-muted-foreground sticky top-0 z-10 flex items-center gap-1.5">
                  <Sparkles className="h-3 w-3" />Facet 분석
                </div>
                <div className="flex-1 flex flex-col items-center justify-center gap-3 p-6 text-center">
                  <RefreshCw className="h-6 w-6 animate-spin text-primary/60" />
                  <p className="text-sm font-medium">Query 중...</p>
                  <p className="text-xs text-muted-foreground">
                    Facet 평가는 수 분 소요될 수 있습니다.<br />
                    멀티소스 앙상블 + LLM 평가 진행 중.
                  </p>
                </div>
              </div>
            ) : facetState === "eval_error" ? (
              <div className="rounded-xl border bg-card shadow-sm overflow-hidden flex flex-col">
                <div className="px-3 py-2 border-b bg-muted/40 text-xs font-semibold text-muted-foreground sticky top-0 z-10 flex items-center gap-1.5">
                  <Sparkles className="h-3 w-3" />Facet 분석
                </div>
                <div className="flex-1 flex flex-col items-center justify-center gap-3 p-6 text-center">
                  <AlertCircle className="h-6 w-6 text-destructive/60" />
                  <p className="text-sm text-destructive">Facet 평가 실패</p>
                  <p className="text-xs text-muted-foreground">{evalError}</p>
                  <button
                    onClick={handleEvaluate}
                    className="text-xs px-3 py-1.5 rounded-md bg-muted hover:bg-muted/80 transition-colors"
                  >
                    재시도
                  </button>
                </div>
              </div>
            ) : (
              <FacetColumn
                facet={activeFacet}
                onRequestEvaluate={handleEvaluate}
                evaluating={false}
              />
            )}
          </div>
        </div>
      )}

      {/* idle 안내 */}
      {searchState === "idle" && (
        <div className="rounded-xl border border-dashed border-border p-12 text-center">
          <Search className="h-10 w-10 mx-auto text-muted-foreground/40 mb-4" />
          <p className="text-sm font-medium text-muted-foreground">
            제목을 입력하면 MediSearch에서 기본메타를 즉시 검색합니다
          </p>
          <p className="text-xs text-muted-foreground mt-2">
            기본메타(감독·장르·줄거리 등)는 바로 표시 — Facet 분석은 결과 확인 후 직접 요청
          </p>
        </div>
      )}
    </div>
  )
}
