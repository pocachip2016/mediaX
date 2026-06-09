"use client"

import { useState, useEffect } from "react"
import { Settings, Play, SkipForward, Zap } from "lucide-react"
import { cn } from "@workspace/ui/lib/utils"
import {
  schedulingAutoApi,
  type AutoPolicy,
  type AutoPolicyPatch,
  type ProgrammingNode,
  type AutoNodeAdvanceOut,
  type AutoNodeRunOut,
} from "@/lib/api"

// ── 정책 패널 ─────────────────────────────────────────────────────────────────

interface PolicyPanelProps {
  policy: AutoPolicy
  onUpdate: (updated: AutoPolicy) => void
}

export function AutoPolicyPanel({ policy, onUpdate }: PolicyPanelProps) {
  const [draft, setDraft] = useState<AutoPolicy>(policy)
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)

  useEffect(() => { setDraft(policy) }, [policy])

  const toggle = (key: keyof AutoPolicyPatch) => {
    setDraft(prev => ({ ...prev, [key]: !prev[key as keyof AutoPolicy] }))
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      const { id: _id, updated_at: _ua, ...patch } = draft
      const updated = await schedulingAutoApi.patchPolicy(patch)
      onUpdate(updated)
      setMsg("저장됨")
      setTimeout(() => setMsg(null), 2000)
    } catch {
      setMsg("저장 실패")
    } finally {
      setSaving(false)
    }
  }

  const BoolRow = ({ label, k }: { label: string; k: keyof AutoPolicyPatch }) => (
    <label className="flex items-center justify-between py-1.5 cursor-pointer select-none">
      <span className="text-sm">{label}</span>
      <button
        onClick={() => toggle(k)}
        className={cn(
          "w-10 h-5 rounded-full transition-colors relative shrink-0",
          draft[k as keyof AutoPolicy] ? "bg-blue-500" : "bg-gray-300 dark:bg-gray-600"
        )}
        aria-checked={!!draft[k as keyof AutoPolicy]}
        role="switch"
      >
        <span className={cn(
          "absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform",
          draft[k as keyof AutoPolicy] ? "translate-x-5" : "translate-x-0.5"
        )} />
      </button>
    </label>
  )

  return (
    <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-4 space-y-3">
      <div className="flex items-center gap-2 pb-1 border-b border-gray-100 dark:border-gray-800">
        <Settings className="w-4 h-4 text-gray-400" />
        <span className="font-medium text-sm">자동편성 정책</span>
        {msg && (
          <span className={cn(
            "ml-auto text-xs",
            msg === "저장됨" ? "text-green-500" : "text-red-500"
          )}>{msg}</span>
        )}
      </div>

      {/* 마스터 스위치 */}
      <div className={cn(
        "rounded-md px-3 py-1",
        draft.auto_tick_enabled
          ? "bg-blue-50 dark:bg-blue-950"
          : "bg-gray-50 dark:bg-gray-800"
      )}>
        <BoolRow label="⚡ AUTO Tick 활성" k="auto_tick_enabled" />
      </div>

      {/* per-stage 토글 */}
      <div className="divide-y divide-gray-100 dark:divide-gray-800">
        <BoolRow label="P2 후보생성 AUTO" k="p2_auto" />
        <BoolRow label="P3 AI매칭 AUTO" k="p3_auto" />
        <BoolRow label="P4 자동확정 AUTO" k="p4_auto" />
        <BoolRow label="P5 충돌검사 AUTO" k="p5_auto" />
        <BoolRow label="P6 발행 AUTO" k="p6_auto" />
      </div>

      {/* 수치 설정 */}
      <div className="space-y-3 pt-1">
        <label className="block text-sm">
          <div className="flex justify-between mb-1">
            <span className="text-gray-600 dark:text-gray-400">확정 임계값</span>
            <span className="font-mono text-xs">{draft.confidence_threshold.toFixed(2)}</span>
          </div>
          <input
            type="range" min={0} max={1} step={0.05}
            value={draft.confidence_threshold}
            onChange={e => setDraft(p => ({ ...p, confidence_threshold: parseFloat(e.target.value) }))}
            className="w-full accent-blue-500"
          />
        </label>
        <label className="block text-sm">
          <span className="text-gray-600 dark:text-gray-400">배치 크기</span>
          <input
            type="number" min={1} max={100}
            value={draft.batch_size}
            onChange={e => setDraft(p => ({ ...p, batch_size: Math.max(1, parseInt(e.target.value) || 20) }))}
            className="mt-1 w-full rounded border border-gray-300 dark:border-gray-600 bg-transparent px-2 py-1 text-sm"
          />
        </label>
      </div>

      <button
        onClick={handleSave}
        disabled={saving}
        className="w-full rounded bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm py-1.5 transition-colors font-medium"
      >
        {saving ? "저장 중…" : "정책 저장"}
      </button>
    </div>
  )
}

// ── 노드 단계 액션 바 ─────────────────────────────────────────────────────────

interface StageActionBarProps {
  node: ProgrammingNode
  onAdvance?: (result: AutoNodeAdvanceOut) => void
  onRun?: (result: AutoNodeRunOut) => void
  onToggleEnable?: (enabled: boolean) => void
}

export function StageActionBar({ node, onAdvance, onRun, onToggleEnable }: StageActionBarProps) {
  const [advancing, setAdvancing] = useState(false)
  const [running, setRunning] = useState(false)
  const [toggling, setToggling] = useState(false)

  const handleAdvance = async () => {
    setAdvancing(true)
    try {
      const r = await schedulingAutoApi.advanceNode(node.id)
      onAdvance?.(r)
    } finally {
      setAdvancing(false)
    }
  }

  const handleRun = async () => {
    setRunning(true)
    try {
      const r = await schedulingAutoApi.runNode(node.id)
      onRun?.(r)
    } finally {
      setRunning(false)
    }
  }

  const handleToggle = async () => {
    setToggling(true)
    try {
      const next = !node.auto_enabled
      await schedulingAutoApi.enableAuto(node.id, next)
      onToggleEnable?.(next)
    } finally {
      setToggling(false)
    }
  }

  return (
    <div className="flex items-center gap-2">
      {/* AUTO 토글 */}
      <button
        onClick={handleToggle}
        disabled={toggling}
        className={cn(
          "flex items-center gap-1 text-xs px-2 py-1 rounded border transition-colors disabled:opacity-40",
          node.auto_enabled
            ? "border-blue-400 text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-950"
            : "border-gray-300 dark:border-gray-600 text-gray-500 hover:bg-gray-50 dark:hover:bg-gray-800"
        )}
      >
        <Zap className="w-3 h-3" />
        {node.auto_enabled ? "AUTO ON" : "AUTO OFF"}
      </button>

      {/* 1단계 진행 */}
      <button
        onClick={handleAdvance}
        disabled={advancing || !node.auto_enabled}
        className="flex items-center gap-1 text-xs px-2 py-1 rounded border border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-40 transition-colors"
      >
        <SkipForward className="w-3 h-3" />
        {advancing ? "…" : "1단계"}
      </button>

      {/* 자동 실행 */}
      <button
        onClick={handleRun}
        disabled={running || !node.auto_enabled}
        className="flex items-center gap-1 text-xs px-2 py-1 rounded bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-40 transition-colors"
      >
        <Play className="w-3 h-3" />
        {running ? "실행 중…" : "자동 실행"}
      </button>
    </div>
  )
}
