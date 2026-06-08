"use client"

import { useState, useEffect } from "react"
import { Search, Plus } from "lucide-react"
import { metadataApi, schedulingApi } from "@/lib/api"
import type { ContentOut, ProgrammingNode } from "@/lib/api"
import { cn } from "@workspace/ui/lib/utils"

type Tab = "contents" | "nodes"

type Props = {
  selectedSetId: number | null
  selectedNodeId: number | null
  onAddContent: (contentId: number) => void
  onAddNode: (nodeId: number) => void
}

export function PalettePanel({ selectedSetId, selectedNodeId, onAddContent, onAddNode }: Props) {
  const [tab, setTab] = useState<Tab>("contents")
  const [search, setSearch] = useState("")
  const [contents, setContents] = useState<ContentOut[]>([])
  const [nodes, setNodes] = useState<ProgrammingNode[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (tab === "contents") {
      setLoading(true)
      metadataApi
        .listContents({ title: search || undefined, size: 50 })
        .then((r) => setContents(r.items ?? []))
        .catch(() => setContents([]))
        .finally(() => setLoading(false))
    } else {
      if (!selectedSetId) {
        setNodes([])
        return
      }
      setLoading(true)
      schedulingApi
        .listNodes({ set_id: selectedSetId })
        .then((ns) =>
          setNodes(search ? ns.filter((n) => n.name.includes(search)) : ns)
        )
        .catch(() => setNodes([]))
        .finally(() => setLoading(false))
    }
  }, [tab, search, selectedSetId])

  const canAdd = !!selectedNodeId

  return (
    <div className="h-full flex flex-col border rounded-xl bg-card overflow-hidden">
      {/* Tabs */}
      <div className="flex border-b px-3 pt-2 flex-shrink-0">
        {(["contents", "nodes"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={cn(
              "px-3 pb-2 text-sm font-medium border-b-2 transition-colors",
              tab === t
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            )}
          >
            {t === "contents" ? "작품" : "노드"}
          </button>
        ))}
      </div>

      {/* Search */}
      <div className="px-3 py-2 border-b flex-shrink-0">
        <div className="flex items-center gap-2 rounded-md border bg-background px-2 py-1">
          <Search className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="검색…"
            className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
          />
        </div>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto px-2 py-2 space-y-0.5">
        {loading && (
          <p className="text-xs text-muted-foreground text-center py-4">로딩중…</p>
        )}

        {!loading &&
          tab === "contents" &&
          contents.map((c) => (
            <div
              key={c.id}
              className="flex items-center gap-1 rounded-md px-2 py-1.5 hover:bg-accent group"
            >
              <span className="flex-1 truncate text-xs">{c.title}</span>
              <button
                disabled={!canAdd}
                onClick={() => onAddContent(c.id)}
                className="opacity-0 group-hover:opacity-100 disabled:cursor-not-allowed p-0.5 rounded hover:bg-primary/10 transition-opacity"
                title="링크 추가"
              >
                <Plus className="h-3.5 w-3.5 text-primary" />
              </button>
            </div>
          ))}

        {!loading &&
          tab === "nodes" &&
          nodes.map((n) => (
            <div
              key={n.id}
              className="flex items-center gap-1 rounded-md px-2 py-1.5 hover:bg-accent group"
            >
              <span className="flex-1 truncate text-xs">{n.name}</span>
              <button
                disabled={!canAdd}
                onClick={() => onAddNode(n.id)}
                className="opacity-0 group-hover:opacity-100 disabled:cursor-not-allowed p-0.5 rounded hover:bg-primary/10 transition-opacity"
                title="링크 추가"
              >
                <Plus className="h-3.5 w-3.5 text-primary" />
              </button>
            </div>
          ))}

        {!loading && tab === "contents" && contents.length === 0 && (
          <p className="text-xs text-muted-foreground text-center py-4">결과 없음</p>
        )}

        {!loading && tab === "nodes" && nodes.length === 0 && (
          <p className="text-xs text-muted-foreground text-center py-4">
            {selectedSetId ? "노드 없음" : "세트를 먼저 선택하세요"}
          </p>
        )}
      </div>
    </div>
  )
}
