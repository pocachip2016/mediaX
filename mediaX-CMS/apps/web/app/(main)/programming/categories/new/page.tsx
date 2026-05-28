"use client"

import { Suspense } from "react"
import { useSearchParams } from "next/navigation"
import Link from "next/link"
import { ArrowLeft, Hand, Sparkles, Globe } from "lucide-react"

const MODE_INFO: Record<string, { icon: React.ElementType; label: string; step: string }> = {
  manual: { icon: Hand, label: "수동 묶기", step: "Step 6" },
  ai:     { icon: Sparkles, label: "AI 제안 위저드", step: "Step 7–8" },
  external: { icon: Globe, label: "외부 참고 가져오기", step: "Step 9" },
}

function NewCategoryContent() {
  const params = useSearchParams()
  const mode = params.get("mode") ?? "manual"
  const info = MODE_INFO[mode] ?? MODE_INFO["manual"]!
  const Icon = info.icon

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] gap-6">
      <div className="rounded-full p-4 bg-muted">
        <Icon className="h-8 w-8 text-muted-foreground" />
      </div>
      <div className="text-center space-y-2">
        <h2 className="text-xl font-semibold">{info.label}</h2>
        <p className="text-sm text-muted-foreground">
          이 기능은 {info.step}에서 구현됩니다.
        </p>
      </div>
      <Link
        href="/programming/categories"
        className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft className="h-4 w-4" />
        큐레이션 목록으로 돌아가기
      </Link>
    </div>
  )
}

export default function NewCategoryPage() {
  return (
    <Suspense>
      <NewCategoryContent />
    </Suspense>
  )
}
