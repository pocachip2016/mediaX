"use client"

import { useState, useEffect, useCallback } from "react"
import { schedulingApi } from "@/lib/api"
import type { ProgrammingNodeSet, ProgrammingNode, ProgrammingLink } from "@/lib/api"
import { PalettePanel } from "./PalettePanel"
import { LinkCanvas } from "./LinkCanvas"
import { NodePropsPanel } from "./NodePropsPanel"

export function SchedulingBoard() {
  const [sets, setSets] = useState<ProgrammingNodeSet[]>([])
  const [nodes, setNodes] = useState<ProgrammingNode[]>([])
  const [links, setLinks] = useState<ProgrammingLink[]>([])
  const [selectedSetId, setSelectedSetId] = useState<number | null>(null)
  const [selectedNodeId, setSelectedNodeId] = useState<number | null>(null)
  const [selectedNode, setSelectedNode] = useState<ProgrammingNode | null>(null)
  const [loadingSets, setLoadingSets] = useState(true)
  const [loadingNodes, setLoadingNodes] = useState(false)

  useEffect(() => {
    schedulingApi
      .listSets()
      .then(setSets)
      .catch(() => setSets([]))
      .finally(() => setLoadingSets(false))
  }, [])

  useEffect(() => {
    if (!selectedSetId) {
      setNodes([])
      setSelectedNodeId(null)
      return
    }
    setLoadingNodes(true)
    schedulingApi
      .listNodes({ set_id: selectedSetId })
      .then(setNodes)
      .catch(() => setNodes([]))
      .finally(() => setLoadingNodes(false))
    setSelectedNodeId(null)
  }, [selectedSetId])

  const reloadLinks = useCallback(() => {
    if (!selectedNodeId) {
      setLinks([])
      setSelectedNode(null)
      return
    }
    schedulingApi
      .listLinks(selectedNodeId)
      .then(setLinks)
      .catch(() => setLinks([]))
    setSelectedNode(nodes.find((n) => n.id === selectedNodeId) ?? null)
  }, [selectedNodeId, nodes])

  useEffect(() => {
    reloadLinks()
  }, [reloadLinks])

  const handleAddContent = useCallback(
    async (contentId: number) => {
      if (!selectedNodeId) return
      await schedulingApi.addLink(selectedNodeId, { child_content_id: contentId }).catch(() => {})
      reloadLinks()
    },
    [selectedNodeId, reloadLinks]
  )

  const handleAddNode = useCallback(
    async (targetNodeId: number) => {
      if (!selectedNodeId) return
      await schedulingApi.addLink(selectedNodeId, { child_node_id: targetNodeId }).catch(() => {})
      reloadLinks()
    },
    [selectedNodeId, reloadLinks]
  )

  return (
    <div className="flex flex-col h-full gap-3">
      {/* Top bar */}
      <div className="flex items-center gap-3 flex-shrink-0">
        <select
          value={selectedSetId ?? ""}
          onChange={(e) => setSelectedSetId(e.target.value ? Number(e.target.value) : null)}
          disabled={loadingSets}
          className="h-9 rounded-md border bg-background px-3 text-sm w-52 disabled:opacity-50"
        >
          <option value="">{loadingSets ? "로딩중…" : "편성 세트 선택"}</option>
          {sets.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>

        <select
          value={selectedNodeId ?? ""}
          onChange={(e) => setSelectedNodeId(e.target.value ? Number(e.target.value) : null)}
          disabled={!selectedSetId || loadingNodes}
          className="h-9 rounded-md border bg-background px-3 text-sm w-52 disabled:opacity-50"
        >
          <option value="">{loadingNodes ? "로딩중…" : "노드 선택"}</option>
          {nodes.map((n) => (
            <option key={n.id} value={n.id}>
              {n.name}
            </option>
          ))}
        </select>
      </div>

      {/* 3-column board */}
      <div className="flex flex-1 gap-3 min-h-0 overflow-hidden">
        <div className="w-64 flex-shrink-0 min-h-0">
          <PalettePanel
            selectedSetId={selectedSetId}
            selectedNodeId={selectedNodeId}
            onAddContent={handleAddContent}
            onAddNode={handleAddNode}
          />
        </div>

        <div className="flex-1 min-w-0 min-h-0">
          <LinkCanvas nodeId={selectedNodeId} links={links} onReload={reloadLinks} />
        </div>

        <div className="w-72 flex-shrink-0 min-h-0">
          <NodePropsPanel node={selectedNode} links={links} onReload={reloadLinks} />
        </div>
      </div>
    </div>
  )
}
