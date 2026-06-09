import { SchedulingBoard } from "@/components/scheduling/SchedulingBoard"

export default function SchedulePage() {
  return (
    <div className="flex flex-col h-full gap-4 p-1">
      <div className="flex-shrink-0">
        <h2 className="text-2xl font-semibold tracking-tight">편성표 작성</h2>
        <p className="text-sm text-muted-foreground mt-1">
          서비스 단위 편성표(예: 2026 LG IPTV)에 콘텐츠·카테고리·AI 큐레이션을 조합해 노출 타임라인과 AI 추천을 구성합니다.
        </p>
      </div>
      <div className="flex-1 min-h-0">
        <SchedulingBoard />
      </div>
    </div>
  )
}
