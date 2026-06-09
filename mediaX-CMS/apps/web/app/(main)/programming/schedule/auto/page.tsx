"use client"

import { useEffect, useState, useCallback } from "react"
import { RefreshCw, Zap } from "lucide-react"
import { cn } from "@workspace/ui/lib/utils"
import {
  schedulingApi,
  schedulingAutoApi,
  type AutoSummary,
  type AutoPolicy,
  type AutoStage,
  type ProgrammingNode,
} from "@/lib/api"
import { AutoPolicyPanel, StageActionBar } from "@/components/scheduling/auto/AutoRunPanel"
import { StageEventLogCard } from "@/components/scheduling/auto/StageEventLog"

// ── 상수 ─────────────────────────────────────────────────────────────────────

const STAGE_LABEL: Record<AutoStage, string> = {
  p1_define:      "P1 조건정의",
  p2_candidate:   "P2 후보생성",
  p3_match:       "P3 AI매칭",
  p4_autoconfirm: "P4 자동확정",
  p5_conflict:    "P5 충돌검사",
  p6_publish:     "P6 발행",
}

const BUCKET_COLOR: Record<number, string> = {
  1: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
  2: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
  3: "bg-violet-100 text-violet-700 dark:bg-violet-900 dark:text-violet-300",
  4: "bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300",
  5: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
}

// ── 버킷 카운트 카드 ──────────────────────────────────────────────────────────

function BucketCard({ bucket, label, stage_range, count }: {
  bucket: number; label: string; stage_range: string; count: number
}) {
  return (
    <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-4 py-3 flex flex-col gap-1">
      <div className="flex items-center justify-between">
        <span className={cn("text-xs px-1.5 py-0.5 rounded font-mono", BUCKET_COLOR[bucket])}>
          {stage_range}
        </span>
        <span className="text-2xl font-semibold tabular-nums">{count}</span>
      </div>
      <span className="text-xs text-gray-500">{label}</span>
    </div>
  )
}

// ── 노드 목록 아이템 ───────────────────────────────────────────────────────────

function NodeItem({ node, selected, onSelect }: {
  node: ProgrammingNode
  selected: boolean
  onSelect: () => void
}) {
  return (
    <button
      onClick={onSelect}
      className={cn(
        "w-full text-left rounded-lg border px-3 py-2 text-sm transition-colors",
        selected
          ? "border-blue-500 bg-blue-50 dark:bg-blue-950"
          : "border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 hover:bg-gray-50 dark:hover:bg-gray-800"
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="truncate font-medium">{node.name}</span>
        {node.auto_enabled && <Zap className="w-3 h-3 text-blue-400 shrink-0" />}
      </div>
      {node.auto_stage && (
        <span className="text-xs text-gray-500 mt-0.5 block">
          {STAGE_LABEL[node.auto_stage]}
        </span>
      )}
    </button>
  )
}

// ── 노드 상세 패널 ────────────────────────────────────────────────────────────

function NodeDetailPanel({
  node,
  onRefresh,
}: {
  node: ProgrammingNode
  onRefresh: () => void
}) {
  return (
    <div className="space-y-4">
      {/* 헤더 + 액션 바 */}
      <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-4">
        <div className="mb-3">
          <h3 className="font-semibold">{node.name}</h3>
          <div className="flex items-center gap-2 mt-1 text-xs text-gray-500">
            <span className="capitalize">{node.kind}</span>
            {node.auto_stage && (
              <>
                <span className="text-gray-300 dark:text-gray-600">·</span>
                <span className="font-mono text-blue-600 dark:text-blue-400">
                  {STAGE_LABEL[node.auto_stage]}
                </span>
              </>
            )}
            {node.schedule_score != null && (
              <>
                <span className="text-gray-300 dark:text-gray-600">·</span>
                <span>점수 {node.schedule_score.toFixed(0)}</span>
              </>
            )}
          </div>
        </div>
        <StageActionBar
          node={node}
          onAdvance={() => onRefresh()}
          onRun={() => onRefresh()}
          onToggleEnable={() => onRefresh()}
        />
      </div>

      {/* 이벤트 로그 */}
      <StageEventLogCard nodeId={node.id} />
    </div>
  )
}

// ── 메인 페이지 ───────────────────────────────────────────────────────────────

export default function AutoSchedulePage() {
  const [summary, setSummary] = useState<AutoSummary | null>(null)
  const [policy, setPolicy] = useState<AutoPolicy | null>(null)
  const [nodes, setNodes] = useState<ProgrammingNode[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [msg, setMsg] = useState<{ text: string; ok: boolean } | null>(null)

  const selectedNode = nodes.find(n => n.id === selectedId) ?? null

  const showMsg = (text: string, ok = true) => {
    setMsg({ text, ok })
    setTimeout(() => setMsg(null), 3000)
  }

  const loadAll = useCallback(async () => {
    setLoading(true)
    try {
      const [s, p, ns] = await Promise.all([
        schedulingAutoApi.getSummary(),
        schedulingAutoApi.getPolicy(),
        schedulingApi.listNodes(),
      ])
      setSummary(s)
      setPolicy(p)
      setNodes(ns)
    } catch {
      showMsg("데이터 로드 실패", false)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadAll() }, [loadAll])

  return (
    <div className="flex flex-col h-full">
      {/* 헤더 */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-800 shrink-0">
        <div>
          <h1 className="text-lg font-semibold">자동편성관리</h1>
          <p className="text-xs text-gray-500 mt-0.5">ADR-012 — P1~P6 단계별 AI 큐레이션 파이프라인</p>
        </div>
        <div className="flex items-center gap-3">
          {msg && (
            <span className={cn(
              "text-xs px-2 py-1 rounded",
              msg.ok
                ? "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300"
                : "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300"
            )}>
              {msg.text}
            </span>
          )}
          <button
            onClick={loadAll}
            disabled={loading}
            className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-900 dark:hover:text-gray-100 transition-colors disabled:opacity-40"
          >
            <RefreshCw className={cn("w-4 h-4", loading && "animate-spin")} />
            새로고침
          </button>
        </div>
      </div>

      {/* 버킷 요약 */}
      {summary && (
        <div className="px-6 py-3 border-b border-gray-200 dark:border-gray-800 shrink-0">
          <div className="grid grid-cols-5 gap-3">
            {summary.buckets.map(b => (
              <BucketCard key={b.bucket} {...b} />
            ))}
          </div>
          <p className="text-xs text-gray-400 mt-2">
            AUTO 대상 노드:{" "}
            <span className="font-medium text-gray-700 dark:text-gray-300">
              {summary.total_auto_enabled}
            </span>건
          </p>
        </div>
      )}

      {/* 3컬럼 본문 */}
      <div className="flex flex-1 overflow-hidden">
        {/* 좌: 노드 목록 */}
        <div className="w-64 shrink-0 border-r border-gray-200 dark:border-gray-800 overflow-y-auto p-3 space-y-1.5">
          <p className="text-xs font-medium text-gray-500 px-1 pb-1">편성 노드</p>
          {loading ? (
            <p className="text-xs text-gray-400 text-center py-8">로딩 중…</p>
          ) : nodes.length === 0 ? (
            <p className="text-xs text-gray-400 text-center py-8">노드 없음</p>
          ) : (
            nodes.map(n => (
              <NodeItem
                key={n.id}
                node={n}
                selected={n.id === selectedId}
                onSelect={() => setSelectedId(n.id)}
              />
            ))
          )}
        </div>

        {/* 중: 노드 상세 */}
        <div className="flex-1 overflow-y-auto p-4">
          {selectedNode ? (
            <NodeDetailPanel node={selectedNode} onRefresh={loadAll} />
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-gray-400 gap-2">
              <Zap className="w-8 h-8" />
              <p className="text-sm">노드를 선택하면 자동편성 제어 패널이 나타납니다</p>
            </div>
          )}
        </div>

        {/* 우: 정책 패널 */}
        <div className="w-64 shrink-0 border-l border-gray-200 dark:border-gray-800 overflow-y-auto p-3">
          {policy ? (
            <AutoPolicyPanel policy={policy} onUpdate={setPolicy} />
          ) : (
            <p className="text-xs text-gray-400 text-center py-8">정책 로딩 중…</p>
          )}
        </div>
      </div>
    </div>
  )
}
