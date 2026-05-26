"use client"

import { StageEventStream } from "@/components/monitoring/pipeline/StageEventStream"

export default function PipelineLogPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">파이프라인 이벤트 로그</h1>
        <p className="text-sm text-muted-foreground mt-1">
          ADR-006 StageEvent SSOT — 실시간 스트림 · 필터 · CSV 내보내기
        </p>
      </div>

      <StageEventStream initialLimit={100} />
    </div>
  )
}
