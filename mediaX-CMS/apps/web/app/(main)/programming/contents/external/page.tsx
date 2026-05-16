"use client"

import { useState } from "react"
import { ArrowLeft, Search, Plus } from "lucide-react"
import Link from "next/link"
import { cn } from "@workspace/ui/lib/utils"

// Step 5 (Watcha 재크롤) 이후 본격 구현 예정
// 현재는 UI 골격만 제공

export default function ExternalSearchPage() {
  const [query, setQuery] = useState("")
  const [source, setSource] = useState<"tmdb" | "kobis">("tmdb")

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <div className="flex items-center gap-3 mb-6">
        <Link href="/programming/contents" className="p-1.5 rounded-lg hover:bg-accent transition-colors">
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <div>
          <h1 className="text-xl font-bold">외부 검색</h1>
          <p className="text-sm text-muted-foreground">TMDB / KOBIS에서 콘텐츠를 검색해 선택 등록합니다</p>
        </div>
      </div>

      {/* 검색 폼 */}
      <div className="flex gap-2 mb-6">
        <select
          value={source}
          onChange={e => setSource(e.target.value as "tmdb" | "kobis")}
          className="px-3 py-2 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
        >
          <option value="tmdb">TMDB</option>
          <option value="kobis">KOBIS</option>
        </select>
        <input
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={e => e.key === "Enter" && alert("Step 5 이후 구현 예정")}
          className="flex-1 px-3 py-2 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
          placeholder="영화 제목으로 검색..."
        />
        <button
          onClick={() => alert("Step 5 이후 구현 예정")}
          className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors flex items-center gap-2"
        >
          <Search className="h-4 w-4" /> 검색
        </button>
      </div>

      {/* 안내 영역 */}
      <div className="rounded-xl border border-dashed border-border p-12 text-center">
        <Search className="h-10 w-10 mx-auto text-muted-foreground mb-4" />
        <p className="font-medium text-muted-foreground">검색어를 입력하면 {source.toUpperCase()} 결과가 표시됩니다</p>
        <p className="text-sm text-muted-foreground mt-2">
          결과에서 체크박스로 선택 후 &quot;선택 항목 콘텐츠로 추가&quot; 버튼을 클릭하세요
        </p>
        <div className={cn(
          "mt-6 inline-flex items-center gap-2 px-4 py-2 rounded-full text-xs font-medium",
          "bg-amber-50 text-amber-700 border border-amber-200"
        )}>
          🚧 외부 검색 API 연동은 Step 5 이후 구현 예정
        </div>
      </div>
    </div>
  )
}
