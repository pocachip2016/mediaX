import { Newspaper } from "lucide-react"
import { BannerReviewPanel } from "@/components/curation/BannerReviewPanel"

export default function BannerReviewPage() {
  return (
    <div className="flex flex-col h-full gap-4 p-1">
      <div className="flex-shrink-0">
        <div className="flex items-center gap-2">
          <Newspaper className="h-6 w-6 text-muted-foreground" />
          <h2 className="text-2xl font-semibold tracking-tight">배너 편성안 관리</h2>
        </div>
        <p className="text-sm text-muted-foreground mt-1">
          주간 배너 편성안의 초안 → 검토 → 승인 → 발행 워크플로우를 관리합니다.
        </p>
      </div>

      <div className="flex-1 min-h-0 overflow-auto">
        <BannerReviewPanel />
      </div>
    </div>
  )
}
