"use client"

import { useState } from "react"
import { MetadataEnrichPanel } from "@/components/contents/MetadataEnrichPanel"
import { MetadataDiffPanel } from "@/components/contents/MetadataDiffPanel"
import type { RecommendationsOut, FieldRecommendation, SourceFieldRec } from "@/lib/api"

const MOCK_REC: RecommendationsOut = {
  content_id: 1,
  missing_fields: ["cast", "synopsis", "runtime", "country", "release_date"],
  auto_fill: [
    {
      field: "runtime",
      status: "auto",
      recommendations: [
        { source_type: "tmdb",   source_id: 2, value: "132분", confidence: 0.94 },
        { source_type: "kobis",  source_id: 3, value: "132분", confidence: 0.91 },
      ],
      ai_synthesis: null,
    },
    {
      field: "country",
      status: "auto",
      recommendations: [
        { source_type: "tmdb",   source_id: 2, value: "대한민국", confidence: 0.94 },
        { source_type: "watcha", source_id: 1, value: "대한민국", confidence: 0.92 },
        { source_type: "kobis",  source_id: 3, value: "대한민국", confidence: 0.90 },
      ],
      ai_synthesis: null,
    },
    {
      field: "cast",
      status: "auto",
      recommendations: [
        { source_type: "watcha", source_id: 1, value: "김설현 · 오정세 · 유재명 외 12명", confidence: 1.0 },
      ],
      ai_synthesis: null,
    },
    {
      field: "release_date",
      status: "auto",
      recommendations: [
        { source_type: "tmdb",   source_id: 2, value: "2024-01-12", confidence: 0.92 },
        { source_type: "kobis",  source_id: 3, value: "2024-01-11", confidence: 0.61 },
      ],
      ai_synthesis: null,
    },
  ],
  conflicts: [
    {
      field: "synopsis",
      status: "conflict",
      recommendations: [
        { source_type: "watcha", source_id: 1, value: "가난한 박씨 가족은 부잣집에 하나 둘씩 취업하며 묘한 공생 관계를 형성해간다.", confidence: 0.50 },
        { source_type: "tmdb",   source_id: 2, value: "A poor family schemes to become employed by a wealthy Park family and infiltrates their home.", confidence: 0.94 },
      ],
      ai_synthesis: {
        source_type: "ai", source_id: 99,
        value: "경제적으로 어려운 박씨 일가는 재벌 박 사장 가족의 집에 한 명씩 취업하며 공생 관계를 형성해가지만, 숨겨진 비밀이 드러나면서 예기치 못한 사건이 벌어진다.",
        confidence: 0.79,
      },
    },
  ],
}

const CURRENT: Record<string, string | null> = {
  runtime: null, country: null, cast: null, release_date: null, synopsis: null,
}

type ViewMode = "enrich" | "diff"

export default function EnrichPreviewPage() {
  const [mode, setMode] = useState<ViewMode>("enrich")
  const [rec, setRec] = useState<RecommendationsOut>(MOCK_REC)
  const [log, setLog] = useState<string[]>([])

  function addLog(msg: string) {
    setLog((prev) => [`[${new Date().toLocaleTimeString()}] ${msg}`, ...prev.slice(0, 9)])
  }

  async function handleApply(fieldRec: FieldRecommendation, src: SourceFieldRec) {
    addLog(`Apply: ${fieldRec.field} ← "${src.value}" (${src.source_type} ${(src.confidence * 100).toFixed(0)}%)`)
    // 적용된 필드를 목록에서 제거
    setRec((prev) => ({
      ...prev,
      auto_fill: prev.auto_fill.filter((r) => r.field !== fieldRec.field),
      conflicts: prev.conflicts.filter((r) => r.field !== fieldRec.field),
      missing_fields: prev.missing_fields.filter((f) => f !== fieldRec.field),
    }))
  }

  async function handleApplyAll(targets: Array<{ rec: FieldRecommendation; source: SourceFieldRec }>) {
    for (const { rec: r, source: s } of targets) await handleApply(r, s)
  }

  async function handleRegenerate() {
    addLog("Regenerate 요청 → (mock: 상태 초기화)")
    setRec(MOCK_REC)
  }

  return (
    <div className="max-w-5xl mx-auto px-4 py-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold">MetadataEnrichPanel Preview</h1>
          <p className="text-xs text-muted-foreground">dev-only · mock 데이터로 컴포넌트 확인</p>
        </div>
        <div className="flex gap-1.5">
          {(["enrich", "diff"] as ViewMode[]).map((v) => (
            <button
              key={v}
              onClick={() => setMode(v)}
              className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
                mode === v ? "bg-primary text-primary-foreground border-primary" : "border-border text-muted-foreground hover:bg-accent"
              }`}
            >
              {v === "enrich" ? "AI Enrich (2패널)" : "Diff Table"}
            </button>
          ))}
          <button
            onClick={() => { setRec(MOCK_REC); setLog([]) }}
            className="text-xs px-3 py-1.5 rounded-full border border-border text-muted-foreground hover:bg-accent transition-colors"
          >
            Reset
          </button>
        </div>
      </div>

      {mode === "enrich" ? (
        <MetadataEnrichPanel
          recommendations={rec}
          currentValues={CURRENT}
          onApply={handleApply}
          onApplyAll={handleApplyAll}
          onRegenerate={handleRegenerate}
          onDismiss={() => addLog("Dismiss 클릭")}
        />
      ) : (
        <MetadataDiffPanel
          recommendations={rec}
          currentValues={CURRENT}
          onDismiss={() => addLog("Dismiss 클릭")}
          onApply={handleApply}
          onApplyAll={async () => { for (const r of rec.auto_fill) { const t = r.recommendations[0]; if (t) await handleApply(r, t) } }}
          onEditManually={(f) => addLog(`수동 편집: ${f}`)}
        />
      )}

      {log.length > 0 && (
        <div className="rounded-lg border border-border bg-muted/30 p-3">
          <p className="text-xs font-semibold text-muted-foreground mb-1.5">Action Log</p>
          {log.map((l, i) => (
            <p key={i} className="text-xs text-muted-foreground font-mono">{l}</p>
          ))}
        </div>
      )}
    </div>
  )
}
