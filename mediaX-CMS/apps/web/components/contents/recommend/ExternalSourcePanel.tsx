"use client"

import { useState } from "react"
import { Search, Loader2, CheckCircle2, XCircle, Info } from "lucide-react"
import { cn } from "@workspace/ui/lib/utils"
import { metadataApi } from "@/lib/api"
import type { ContentDetail } from "@/lib/api"

type EnrichState = "idle" | "loading" | "done" | "error"

const SOURCES = [
  { key: "tmdb",       label: "TMDB",      movieOnly: false },
  { key: "kmdb",       label: "KMDB",      movieOnly: true  },
  { key: "kobis",      label: "KOBIS",     movieOnly: true  },
  { key: "watcha",     label: "Watcha",    movieOnly: false },
  { key: "websearch",  label: "WebSearch", movieOnly: false },
] as const

interface Props {
  content: ContentDetail
  lookupTargetTitle?: string
  onComplete: () => void
}

export function ExternalSourcePanel({ content, lookupTargetTitle, onComplete }: Props) {
  const [state, setState] = useState<EnrichState>("idle")
  const isMovie = content.content_type === "movie"
  const hasMovieOnlyDisabled = !isMovie

  async function handleEnrich() {
    setState("loading")
    try {
      await metadataApi.triggerEnrich(content.id)
      setState("done")
      onComplete()
    } catch {
      setState("error")
    }
  }

  return (
    <div className="bg-white rounded-lg border p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-700">외부 소스 획득</h3>
        {state === "idle" && null}
        {state === "loading" && (
          <span className="inline-flex items-center gap-1 text-xs text-blue-600">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />처리 중…
          </span>
        )}
        {state === "done" && (
          <span className="inline-flex items-center gap-1 text-xs text-green-600">
            <CheckCircle2 className="h-3.5 w-3.5" />완료
          </span>
        )}
        {state === "error" && (
          <span className="inline-flex items-center gap-1 text-xs text-red-600">
            <XCircle className="h-3.5 w-3.5" />오류
          </span>
        )}
      </div>

      {/* 소스 목록 */}
      <div className="flex flex-wrap gap-2">
        {SOURCES.map(({ key, label, movieOnly }) => {
          const disabled = movieOnly && hasMovieOnlyDisabled
          return (
            <span
              key={key}
              className={cn(
                "inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium border",
                disabled
                  ? "bg-slate-50 text-slate-400 border-slate-200"
                  : "bg-slate-100 text-slate-700 border-slate-200"
              )}
            >
              {label}
              {disabled && <span className="text-slate-400">⊘</span>}
            </span>
          )
        })}
      </div>

      {/* tv-type 안내 */}
      {hasMovieOnlyDisabled && (
        <p className="flex items-start gap-1.5 text-xs text-slate-500">
          <Info className="h-3.5 w-3.5 mt-0.5 shrink-0" />
          KMDB·KOBIS = 영화 전용 (ADR D2). TV 콘텐츠는 TMDB(tv)/Watcha/WebSearch로 조회합니다.
        </p>
      )}

      {/* 조회 단위 타이틀 (시리즈 조상) */}
      {lookupTargetTitle && (
        <p className="text-xs text-slate-500">
          ↳ 외부 조회 단위: <span className="font-medium text-slate-700">{lookupTargetTitle}</span>
        </p>
      )}

      {/* 획득 시작 버튼 */}
      <button
        onClick={() => void handleEnrich()}
        disabled={state === "loading" || state === "done"}
        className={cn(
          "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium",
          state === "loading" || state === "done"
            ? "bg-slate-100 text-slate-400 cursor-not-allowed"
            : "bg-blue-100 text-blue-700 hover:bg-blue-200"
        )}
      >
        <Search className="h-3.5 w-3.5" />
        {state === "done" ? "획득 완료" : "🔍 획득 시작"}
      </button>
    </div>
  )
}
