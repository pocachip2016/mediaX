import { LayoutGrid } from "lucide-react"
import { SlotBoard } from "@/components/curation/SlotBoard"

export default function CurationPage() {
  return (
    <div className="flex flex-col h-full gap-4 p-1">
      <div className="flex-shrink-0 flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <LayoutGrid className="h-6 w-6 text-muted-foreground" />
            <h2 className="text-2xl font-semibold tracking-tight">홈 큐레이션 슬롯 보드</h2>
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            홈 화면 A~F 슬롯의 편성 세트 바인딩을 관리합니다.
          </p>
        </div>
      </div>

      <div className="flex-1 min-h-0 overflow-auto">
        <SlotBoard />
      </div>
    </div>
  )
}
