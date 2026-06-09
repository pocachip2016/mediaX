"use client"

import { useEffect, useMemo, useState } from "react"
import { schedulingApi } from "@/lib/api"
import type { GraphEdge, ProgrammingNode } from "@/lib/api"

type Props = {
  setId: number
}

// ── 레이아웃 상수 ────────────────────────────────────────────────────────────
const NODE_W = 120
const NODE_H = 40
const H_GAP = 60
const V_GAP = 20

// ── 그래프 분석 ──────────────────────────────────────────────────────────────

/** 노드 → 자식 노드 인접 맵 (node edges만) */
function buildAdj(nodeIds: number[], edges: GraphEdge[]): Map<number, number[]> {
  const adj = new Map<number, number[]>(nodeIds.map((id) => [id, []]))
  for (const e of edges) {
    if (e.child_type === "node" && e.child_node_id != null) {
      adj.get(e.parent_node_id)?.push(e.child_node_id)
    }
  }
  return adj
}

/** DFS로 back-edge(사이클) 탐지. 사이클 관여 노드 ID 집합 반환 */
function findCycleNodes(adj: Map<number, number[]>): Set<number> {
  const visited = new Set<number>()
  const inStack = new Set<number>()
  const cycleNodes = new Set<number>()

  function dfs(id: number) {
    visited.add(id)
    inStack.add(id)
    for (const child of adj.get(id) ?? []) {
      if (!visited.has(child)) {
        dfs(child)
      } else if (inStack.has(child)) {
        cycleNodes.add(id)
        cycleNodes.add(child)
      }
    }
    inStack.delete(id)
  }

  for (const id of adj.keys()) {
    if (!visited.has(id)) dfs(id)
  }
  return cycleNodes
}

/** BFS 레이어 배치 — 루트(in-degree 0)부터 층별로 배분 */
function computeLayers(nodeIds: number[], adj: Map<number, number[]>): Map<number, number> {
  const inDegree = new Map<number, number>(nodeIds.map((id) => [id, 0]))
  for (const children of adj.values()) {
    for (const c of children) {
      inDegree.set(c, (inDegree.get(c) ?? 0) + 1)
    }
  }
  const layer = new Map<number, number>()
  const queue: number[] = []
  for (const [id, deg] of inDegree) {
    if (deg === 0) {
      queue.push(id)
      layer.set(id, 0)
    }
  }
  let qi = 0
  while (qi < queue.length) {
    const cur = queue[qi++]!
    for (const child of adj.get(cur) ?? []) {
      const l = (layer.get(cur) ?? 0) + 1
      if (!layer.has(child) || layer.get(child)! < l) {
        layer.set(child, l)
      }
      if (!queue.includes(child)) queue.push(child)
    }
  }
  // 사이클 등 미배치 노드는 마지막 레이어 + 1
  const maxL = Math.max(0, ...layer.values())
  for (const id of nodeIds) {
    if (!layer.has(id)) layer.set(id, maxL + 1)
  }
  return layer
}

/** 레이어별 x, 같은 레이어 내 위치별 y 결정 */
function computePositions(
  nodeIds: number[],
  layer: Map<number, number>
): Map<number, { x: number; y: number }> {
  const byLayer = new Map<number, number[]>()
  for (const id of nodeIds) {
    const l = layer.get(id) ?? 0
    if (!byLayer.has(l)) byLayer.set(l, [])
    byLayer.get(l)!.push(id)
  }
  const pos = new Map<number, { x: number; y: number }>()
  for (const [l, ids] of byLayer) {
    const x = l * (NODE_W + H_GAP)
    ids.forEach((id, i) => {
      const y = i * (NODE_H + V_GAP)
      pos.set(id, { x, y })
    })
  }
  return pos
}

// ── 컴포넌트 ──────────────────────────────────────────────────────────────────

export function NodeGraph({ setId }: Props) {
  const [nodes, setNodes] = useState<ProgrammingNode[]>([])
  const [edges, setEdges] = useState<GraphEdge[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setLoading(true)
    schedulingApi
      .getSetGraph(setId)
      .then((g) => {
        setNodes(g.nodes)
        setEdges(g.edges)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [setId])

  const { pos, cycleNodes, orphanNodes, contentCount, nodeEdges } = useMemo(() => {
    const nodeIds = nodes.map((n) => n.id)
    const nodeEdges = edges.filter((e) => e.child_type === "node" && e.child_node_id != null)
    const adj = buildAdj(nodeIds, edges)

    // 고아: 노드 엣지에서 parent도 child도 아닌 노드
    const connectedIds = new Set<number>()
    for (const e of nodeEdges) {
      connectedIds.add(e.parent_node_id)
      if (e.child_node_id != null) connectedIds.add(e.child_node_id)
    }
    const orphanNodes = new Set(nodeIds.filter((id) => !connectedIds.has(id)))

    const cycleNodes = findCycleNodes(adj)
    const layer = computeLayers(nodeIds, adj)
    const pos = computePositions(nodeIds, layer)

    // 콘텐츠 자식 개수 (노드별)
    const contentCount = new Map<number, number>()
    for (const e of edges) {
      if (e.child_type === "content") {
        contentCount.set(e.parent_node_id, (contentCount.get(e.parent_node_id) ?? 0) + 1)
      }
    }

    return { pos, cycleNodes, orphanNodes, contentCount, nodeEdges }
  }, [nodes, edges])

  const svgWidth = useMemo(() => {
    if (pos.size === 0) return 400
    return Math.max(...[...pos.values()].map((p) => p.x)) + NODE_W + 40
  }, [pos])

  const svgHeight = useMemo(() => {
    if (pos.size === 0) return 200
    return Math.max(...[...pos.values()].map((p) => p.y)) + NODE_H + 40
  }, [pos])

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center border rounded-xl bg-card">
        <p className="text-sm text-muted-foreground">로딩 중…</p>
      </div>
    )
  }

  if (nodes.length === 0) {
    return (
      <div className="h-full flex items-center justify-center border rounded-xl bg-card">
        <p className="text-sm text-muted-foreground">노드 없음</p>
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col border rounded-xl bg-card overflow-hidden">
      {/* 헤더 */}
      <div className="px-4 py-3 border-b flex items-center gap-4 flex-shrink-0">
        <p className="text-sm font-semibold">노드 그래프</p>
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <LegendItem color="bg-blue-500" label="일반" />
          <LegendItem color="bg-gray-300 dark:bg-gray-600 border-dashed border-2 border-gray-400" label="고아" />
          <LegendItem color="bg-red-400" label="사이클" />
        </div>
        {cycleNodes.size > 0 && (
          <span className="text-xs text-red-600 bg-red-50 dark:bg-red-950/40 px-2 py-0.5 rounded-full">
            사이클 {cycleNodes.size}노드
          </span>
        )}
        {orphanNodes.size > 0 && (
          <span className="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded-full">
            고아 {orphanNodes.size}노드
          </span>
        )}
      </div>

      {/* SVG */}
      <div className="flex-1 overflow-auto p-4">
        <svg
          width={svgWidth}
          height={svgHeight}
          style={{ minWidth: svgWidth, minHeight: svgHeight }}
        >
          {/* 엣지 라인 */}
          {nodeEdges.map((e) => {
            const from = pos.get(e.parent_node_id)
            const to = e.child_node_id != null ? pos.get(e.child_node_id) : null
            if (!from || !to) return null
            const x1 = from.x + NODE_W
            const y1 = from.y + NODE_H / 2
            const x2 = to.x
            const y2 = to.y + NODE_H / 2
            const isCycle =
              cycleNodes.has(e.parent_node_id) &&
              e.child_node_id != null &&
              cycleNodes.has(e.child_node_id)
            return (
              <g key={e.link_id}>
                <path
                  d={`M${x1},${y1} C${(x1 + x2) / 2},${y1} ${(x1 + x2) / 2},${y2} ${x2},${y2}`}
                  fill="none"
                  stroke={isCycle ? "#f87171" : "var(--border)"}
                  strokeWidth={isCycle ? 2 : 1.5}
                  strokeDasharray={isCycle ? "4 2" : undefined}
                  markerEnd="url(#arrow)"
                />
              </g>
            )
          })}

          {/* 화살표 마커 */}
          <defs>
            <marker id="arrow" viewBox="0 0 6 6" refX="5" refY="3" markerWidth="6" markerHeight="6" orient="auto">
              <path d="M0,0 L6,3 L0,6 Z" fill="var(--border)" />
            </marker>
          </defs>

          {/* 노드 박스 */}
          {nodes.map((node) => {
            const p = pos.get(node.id)
            if (!p) return null
            const isOrphan = orphanNodes.has(node.id)
            const isCycle = cycleNodes.has(node.id)
            const cnt = contentCount.get(node.id) ?? 0

            let fill = "var(--card)"
            let stroke = "var(--border)"
            if (isCycle) { fill = "#fee2e2"; stroke = "#f87171" }
            else if (isOrphan) { fill = "var(--muted)"; stroke = "var(--border)" }

            return (
              <g key={node.id} transform={`translate(${p.x + 20},${p.y + 20})`}>
                <rect
                  width={NODE_W}
                  height={NODE_H}
                  rx={6}
                  fill={fill}
                  stroke={stroke}
                  strokeWidth={isCycle ? 2 : 1}
                  strokeDasharray={isOrphan ? "4 2" : undefined}
                />
                <text
                  x={cnt > 0 ? NODE_W / 2 - 8 : NODE_W / 2}
                  y={NODE_H / 2}
                  textAnchor="middle"
                  dominantBaseline="central"
                  fontSize={10}
                  fill="currentColor"
                  style={{ overflow: "hidden" }}
                >
                  <title>{node.name}</title>
                  {node.name.length > 13 ? node.name.slice(0, 12) + "…" : node.name}
                </text>
                {cnt > 0 && (
                  <g transform={`translate(${NODE_W - 14}, 6)`}>
                    <circle r={8} fill="#3b82f6" />
                    <text
                      textAnchor="middle"
                      dominantBaseline="central"
                      fontSize={8}
                      fill="white"
                    >
                      {cnt > 99 ? "99+" : cnt}
                    </text>
                  </g>
                )}
              </g>
            )
          })}
        </svg>
      </div>
    </div>
  )
}

function LegendItem({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1">
      <span className={`inline-block w-3 h-3 rounded-sm ${color}`} />
      {label}
    </span>
  )
}
