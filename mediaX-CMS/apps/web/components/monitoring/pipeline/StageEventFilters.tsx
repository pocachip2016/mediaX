"use client"

const STAGES = ["s1_intake", "s2_normalize", "s3_llm_extract", "s4_source_match", "s5_gap_detect", "s6_websearch_fill", "s7_staging", "s8_review", "s9_publish"]
const SOURCES = ["email_poll", "manual", "bulk_csv", "dam_webhook", "tmdb", "kobis", "dam", "brave", "serpapi", "gemini", "ollama", "system"]
const EVENT_TYPES = ["ENTERED", "COMPLETED", "SKIPPED", "FAILED", "ADVANCED"]

interface StageEventFiltersProps {
  stage: string
  source: string
  eventType: string
  onStageChange: (v: string) => void
  onSourceChange: (v: string) => void
  onEventTypeChange: (v: string) => void
}

export function StageEventFilters({ stage, source, eventType, onStageChange, onSourceChange, onEventTypeChange }: StageEventFiltersProps) {
  return (
    <div className="flex flex-wrap gap-2">
      <select
        value={stage}
        onChange={(e) => onStageChange(e.target.value)}
        className="rounded border border-slate-300 bg-white px-2 py-1 text-xs dark:border-slate-600 dark:bg-slate-800"
      >
        <option value="">모든 Stage</option>
        {STAGES.map((s) => <option key={s} value={s}>{s}</option>)}
      </select>
      <select
        value={source}
        onChange={(e) => onSourceChange(e.target.value)}
        className="rounded border border-slate-300 bg-white px-2 py-1 text-xs dark:border-slate-600 dark:bg-slate-800"
      >
        <option value="">모든 Source</option>
        {SOURCES.map((s) => <option key={s} value={s}>{s}</option>)}
      </select>
      <select
        value={eventType}
        onChange={(e) => onEventTypeChange(e.target.value)}
        className="rounded border border-slate-300 bg-white px-2 py-1 text-xs dark:border-slate-600 dark:bg-slate-800"
      >
        <option value="">모든 이벤트</option>
        {EVENT_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
      </select>
    </div>
  )
}
