import { SchedulingBoard } from "@/components/scheduling/SchedulingBoard"

export default function SchedulePage() {
  return (
    <div className="flex flex-col h-full gap-4 p-1">
      <div className="flex-shrink-0">
        <h2 className="text-2xl font-semibold tracking-tight">편성 보드</h2>
        <p className="text-sm text-muted-foreground mt-1">
          노드 세트와 링크를 편성하고 AI 추천을 검토합니다.
        </p>
      </div>
      <div className="flex-1 min-h-0">
        <SchedulingBoard />
      </div>
    </div>
  )
}
