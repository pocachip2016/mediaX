"use client"

import { useEffect, useState } from "react"
import { X } from "lucide-react"
import { cn } from "@workspace/ui/lib/utils"
import { catalogApi, type CategoryNode } from "@/lib/api"
import {
  parseBulk,
  diffAgainstTree,
  type DiffResult,
  type ParseResult,
} from "@/lib/categoryBulkParse"

type Phase = "input" | "preview" | "committing"

export function BulkImportPanel({
  existingTree,
  initialText = "",
  onClose,
  onCommit,
}: {
  existingTree: CategoryNode[]
  initialText?: string
  onClose: () => void
  onCommit: () => Promise<void>
}) {
  const [text, setText] = useState(initialText)
  const [phase, setPhase] = useState<Phase>("input")
  const [parseResult, setParseResult] = useState<ParseResult | null>(null)
  const [diffResult, setDiffResult] = useState<DiffResult | null>(null)
  const [commitError, setCommitError] = useState<string | null>(null)

  // initialText 변경 시: 텍스트 + 상태 모두 초기화
  useEffect(() => {
    setText(initialText)
    setPhase("input")
    setParseResult(null)
    setDiffResult(null)
    setCommitError(null)
  }, [initialText])

  // existingTree 변경 시: 파싱 상태만 초기화 (텍스트 유지)
  useEffect(() => {
    setParseResult(null)
    setDiffResult(null)
  }, [existingTree])

  // 포맷 자동 감지 (실시간)
  const detectedFormat = (() => {
    const trimmed = text.trim()
    if (!trimmed) return null
    const lines = trimmed.split("\n").filter((l) => l.trim())
    return lines.some((l) => l.trim().includes("/") && !l.match(/^[ \t]+/))
      ? "경로"
      : "들여쓰기"
  })()

  const handleParse = () => {
    setCommitError(null)
    const result = parseBulk(text)
    setParseResult(result)
    const diff = diffAgainstTree(result.nodes, existingTree)
    setDiffResult(diff)
    setPhase("preview")
  }

  const handleCommit = async () => {
    if (!parseResult) return
    setPhase("committing")
    setCommitError(null)
    try {
      await catalogApi.bulkCreate({ nodes: parseResult.nodes })
      await onCommit()
      onClose()
    } catch (err) {
      setCommitError(err instanceof Error ? err.message : "일괄 생성 실패")
      setPhase("preview")
    }
  }

  return (
    <div className="flex h-full flex-col">
      {/* 헤더 */}
      <div className="flex items-center justify-between border-b px-4 py-3">
        <span className="text-sm font-medium">일괄 입력</span>
        <button
          onClick={onClose}
          className="flex h-5 w-5 items-center justify-center rounded text-muted-foreground hover:bg-muted"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      {phase === "committing" ? (
        <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
          반영 중…
        </div>
      ) : (
        <div className="flex flex-1 flex-col overflow-hidden">
          {/* 입력 영역 */}
          <div className="flex flex-1 flex-col gap-2 overflow-y-auto p-3">
            {/* 포맷 감지 안내 */}
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>들여쓰기 또는 경로(A/B/C) 형식 자동 인식</span>
              {detectedFormat && (
                <span className="rounded bg-muted px-1.5 py-0.5 font-mono">{detectedFormat}</span>
              )}
            </div>

            {/* textarea */}
            <textarea
              value={text}
              onChange={(e) => {
                setText(e.target.value)
                if (phase === "preview") setPhase("input")
                setParseResult(null)
                setDiffResult(null)
              }}
              placeholder={"영화\n  액션\n  코미디\n시리즈\n  드라마\n\n또는 경로 형식:\n영화/액션\n영화/코미디"}
              rows={8}
              className="min-h-32 w-full resize-none rounded border bg-background p-2 font-mono text-xs leading-relaxed focus:outline-none focus:ring-1 focus:ring-ring"
            />

            {/* 파싱 에러 */}
            {parseResult && parseResult.errors.length > 0 && (
              <div className="rounded-md bg-destructive/10 p-2 text-xs text-destructive">
                {parseResult.errors.map((e) => (
                  <p key={e.line}>
                    {e.line}행: {e.message} — &quot;{e.text}&quot;
                  </p>
                ))}
              </div>
            )}

            {/* [검증/미리보기] 버튼 */}
            {phase === "input" && (
              <button
                onClick={handleParse}
                disabled={!text.trim()}
                className="w-full rounded-md bg-secondary py-2 text-sm hover:bg-secondary/80 disabled:opacity-50"
              >
                검증 / 미리보기
              </button>
            )}

            {/* 미리보기 트리 */}
            {phase === "preview" && diffResult && (
              <div className="rounded-md border">
                <div className="border-b px-3 py-2 text-xs font-medium text-muted-foreground">
                  미리보기
                </div>
                <div className="max-h-44 overflow-y-auto p-2">
                  {diffResult.items.length === 0 ? (
                    <p className="text-xs text-muted-foreground">항목 없음</p>
                  ) : (
                    diffResult.items.slice(0, 60).map((item, i) => (
                      <div
                        key={i}
                        className="flex items-center gap-1 py-0.5 text-xs"
                        style={{ paddingLeft: `${(item.path.length - 1) * 12 + 4}px` }}
                      >
                        <span
                          className={cn(
                            "shrink-0 text-[10px]",
                            item.isNew ? "text-green-600" : "text-yellow-600",
                          )}
                        >
                          {item.isNew ? "🆕" : "⚠"}
                        </span>
                        <span className={cn("truncate", !item.isNew && "text-muted-foreground")}>
                          {item.node.name}
                        </span>
                      </div>
                    ))
                  )}
                  {diffResult.items.length > 60 && (
                    <p className="px-1 pt-1 text-xs text-muted-foreground">
                      …외 {diffResult.items.length - 60}건
                    </p>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* 하단 액션 (preview 단계) */}
          {phase === "preview" && diffResult && (
            <div className="shrink-0 space-y-2 border-t p-3">
              <p className="text-xs text-muted-foreground">
                신규{" "}
                <span className="font-medium text-green-600">{diffResult.newCount}건</span>
                {" · "}중복 skip{" "}
                <span className="font-medium text-yellow-600">{diffResult.dupCount}건</span>
              </p>
              {commitError && <p className="text-xs text-destructive">{commitError}</p>}
              <div className="flex gap-2">
                <button
                  onClick={() => setPhase("input")}
                  className="flex-1 rounded border py-1.5 text-sm hover:bg-muted"
                >
                  다시 입력
                </button>
                <button
                  onClick={() => void handleCommit()}
                  disabled={diffResult.newCount === 0}
                  className="flex-1 rounded bg-primary py-1.5 text-sm text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                >
                  트리에 반영
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
