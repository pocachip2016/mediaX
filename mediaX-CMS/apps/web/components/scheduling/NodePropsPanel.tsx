"use client"

import { useState } from "react"
import { CornerUpLeft, Sparkles } from "lucide-react"
import type { ProgrammingLink, ProgrammingNode } from "@/lib/api"
import { cn } from "@workspace/ui/lib/utils"
import { AiSuggestPanel } from "./AiSuggestPanel"
import { BackrefList } from "./BackrefList"

type Props = {
  node: ProgrammingNode | null
  links: ProgrammingLink[]
  onReload: () => void
}

type Tab = "props" | "ai" | "backref"

export function NodePropsPanel({ node, links, onReload }: Props) {
  const [tab, setTab] = useState<Tab>("props")

  const activeCount = links.filter((l) => l.status === "active").length
  const suggestedCount = links.filter((l) => l.status === "suggested").length

  if (!node) {
    return (
      <div className="h-full flex items-center justify-center border rounded-xl bg-card">
        <p className="text-sm text-muted-foreground">노드를 선택하세요</p>
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col border rounded-xl bg-card overflow-hidden">
      {/* 공통 헤더 */}
      <div className="px-4 py-3 border-b space-y-1 flex-shrink-0">
        <p className="text-xs text-muted-foreground">노드</p>
        <p className="font-semibold text-sm truncate">{node.name}</p>
        {node.headline_copy && (
          <p className="text-xs text-muted-foreground line-clamp-2">{node.headline_copy}</p>
        )}
        <div className="flex gap-3 pt-1">
          <span className="text-xs text-muted-foreground">
            <span className="font-medium text-foreground">{activeCount}</span> 활성
          </span>
          <span className="text-xs text-muted-foreground">
            <span className={cn("font-medium", suggestedCount > 0 ? "text-amber-600" : "text-foreground")}>
              {suggestedCount}
            </span>{" "}
            추천
          </span>
        </div>
      </div>

      {/* 탭 스위처 */}
      <div className="flex border-b flex-shrink-0">
        <button
          onClick={() => setTab("props")}
          className={cn(
            "flex-1 py-2 text-xs font-medium transition-colors",
            tab === "props"
              ? "text-foreground border-b-2 border-primary"
              : "text-muted-foreground hover:text-foreground"
          )}
        >
          속성
        </button>
        <button
          onClick={() => setTab("ai")}
          className={cn(
            "flex-1 py-2 text-xs font-medium transition-colors flex items-center justify-center gap-1",
            tab === "ai"
              ? "text-foreground border-b-2 border-primary"
              : "text-muted-foreground hover:text-foreground"
          )}
        >
          <Sparkles className="h-3.5 w-3.5" />
          AI 추천
          {suggestedCount > 0 && (
            <span className="ml-0.5 rounded-full bg-amber-500 text-white text-[10px] px-1.5 leading-4">
              {suggestedCount}
            </span>
          )}
        </button>
        <button
          onClick={() => setTab("backref")}
          className={cn(
            "flex-1 py-2 text-xs font-medium transition-colors flex items-center justify-center gap-1",
            tab === "backref"
              ? "text-foreground border-b-2 border-primary"
              : "text-muted-foreground hover:text-foreground"
          )}
        >
          <CornerUpLeft className="h-3.5 w-3.5" />
          역참조
        </button>
      </div>

      {/* 탭 콘텐츠 */}
      <div className="flex-1 overflow-hidden flex flex-col min-h-0">
        {tab === "props" ? (
          <NodePropsContent node={node} links={links} />
        ) : tab === "ai" ? (
          <AiSuggestPanel node={node} links={links} onReload={onReload} />
        ) : (
          <BackrefList node={node} />
        )}
      </div>
    </div>
  )
}

function NodePropsContent({ node, links }: { node: ProgrammingNode; links: ProgrammingLink[] }) {
  const activeLinks = links.filter((l) => l.status === "active")

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      {/* 노드 세부 정보 */}
      <div className="space-y-2">
        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">기본 정보</p>
        <div className="space-y-1.5 text-sm">
          <div className="flex gap-2">
            <span className="text-xs text-muted-foreground w-20 flex-shrink-0">종류</span>
            <span className="text-xs">{node.kind}</span>
          </div>
          {node.sub_copy && (
            <div className="flex gap-2">
              <span className="text-xs text-muted-foreground w-20 flex-shrink-0">서브카피</span>
              <span className="text-xs line-clamp-2">{node.sub_copy}</span>
            </div>
          )}
          {node.rule_query && Object.keys(node.rule_query).length > 0 && (
            <div className="flex gap-2">
              <span className="text-xs text-muted-foreground w-20 flex-shrink-0">규칙</span>
              <span className="text-xs text-muted-foreground font-mono line-clamp-3">
                {JSON.stringify(node.rule_query)}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* 활성 링크 요약 */}
      {activeLinks.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
            활성 링크 ({activeLinks.length})
          </p>
          <div className="space-y-1">
            {activeLinks.slice(0, 10).map((l) => (
              <div key={l.id} className="text-xs text-muted-foreground px-2 py-1 rounded bg-muted/50">
                {l.child_content_id != null ? `콘텐츠 #${l.child_content_id}` : `노드 #${l.child_node_id}`}
                {l.is_pinned && <span className="ml-1 text-amber-500">📌</span>}
              </div>
            ))}
            {activeLinks.length > 10 && (
              <p className="text-xs text-muted-foreground text-center">+{activeLinks.length - 10}개 더</p>
            )}
          </div>
        </div>
      )}

      {activeLinks.length === 0 && (
        <div className="flex items-center justify-center py-8">
          <p className="text-xs text-muted-foreground">활성 링크 없음</p>
        </div>
      )}
    </div>
  )
}
