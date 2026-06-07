"use client"

import { useEffect, useRef, useState } from "react"
import { Upload, X, FileText, Download } from "lucide-react"
import { cn } from "@workspace/ui/lib/utils"
import { catalogApi, type CategoryNode } from "@/lib/api"
import {
  parseBulk,
  diffAgainstTree,
  type DiffResult,
  type ParseResult,
} from "@/lib/categoryBulkParse"

type Phase = "input" | "preview" | "committing"
type InputMode = "file" | "text"

const TEMPLATE_CSV = `path
영화
영화/액션
영화/코미디
영화/로맨스
시리즈
시리즈/드라마
시리즈/드라마/한국
시리즈/드라마/해외
시리즈/예능
키즈
키즈/애니메이션
`

function downloadTemplate() {
  const blob = new Blob(["﻿" + TEMPLATE_CSV], { type: "text/csv;charset=utf-8;" })
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = "category_template.csv"
  a.click()
  URL.revokeObjectURL(url)
}

async function readFileAsText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = (e) => resolve((e.target?.result as string) ?? "")
    reader.onerror = () => reject(new Error("파일 읽기 실패"))
    reader.readAsText(file, "UTF-8")
  })
}

function csvToPathText(raw: string, filename: string): { text: string; rowCount: number } {
  const nonEmpty = raw.split(/\r?\n/).filter((l) => l.trim())
  if (nonEmpty.length === 0) return { text: "", rowCount: 0 }

  const firstLine = nonEmpty[0]?.trim().toLowerCase() ?? ""
  const isCSV =
    filename.toLowerCase().endsWith(".csv") ||
    firstLine === "path" ||
    firstLine === "카테고리" ||
    firstLine === "name"

  if (!isCSV) {
    // TXT: 들여쓰기 보존 — 원본 그대로 전달
    return { text: raw.trim(), rowCount: nonEmpty.length }
  }

  // CSV: 헤더 제거 + 첫 컬럼만 추출
  const isHeader =
    firstLine === "path" || firstLine === "카테고리" || firstLine === "name"
  const dataLines = isHeader ? nonEmpty.slice(1) : nonEmpty

  const paths = dataLines
    .map((l) => l.split(",")[0]?.replace(/^"|"$/g, "").trim() ?? "")
    .filter(Boolean)

  return { text: paths.join("\n"), rowCount: paths.length }
}

export function BulkImportPanel({
  existingTree,
  initialText = "",
  lockedMode,
  onClose,
  onCommit,
}: {
  existingTree: CategoryNode[]
  initialText?: string
  lockedMode?: InputMode
  onClose?: () => void
  onCommit: () => Promise<void>
}) {
  const [inputMode, setInputMode] = useState<InputMode>(lockedMode ?? "file")
  const [text, setText] = useState(initialText)
  const [phase, setPhase] = useState<Phase>("input")
  const [parseResult, setParseResult] = useState<ParseResult | null>(null)
  const [diffResult, setDiffResult] = useState<DiffResult | null>(null)
  const [commitError, setCommitError] = useState<string | null>(null)

  // 파일 업로드 상태
  const [uploadedFile, setUploadedFile] = useState<File | null>(null)
  const [fileRowCount, setFileRowCount] = useState(0)
  const [fileError, setFileError] = useState<string | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // initialText 변경 시 텍스트 모드로 전환 + 초기화
  useEffect(() => {
    if (initialText) {
      setText(initialText)
      setInputMode("text")
    }
    setPhase("input")
    setParseResult(null)
    setDiffResult(null)
    setCommitError(null)
  }, [initialText])

  useEffect(() => {
    setParseResult(null)
    setDiffResult(null)
  }, [existingTree])

  const detectedFormat = (() => {
    const trimmed = text.trim()
    if (!trimmed) return null
    const lines = trimmed.split("\n").filter((l) => l.trim())
    return lines.some((l) => l.trim().includes("/") && !l.match(/^[ \t]+/))
      ? "경로"
      : "들여쓰기"
  })()

  const resetInput = () => {
    setPhase("input")
    setParseResult(null)
    setDiffResult(null)
    setCommitError(null)
    setUploadedFile(null)
    setFileRowCount(0)
    setFileError(null)
  }

  const handleFileSelect = async (file: File) => {
    setFileError(null)
    if (!file.name.match(/\.(csv|txt)$/i)) {
      setFileError("CSV 또는 TXT 파일만 지원합니다.")
      return
    }
    try {
      const raw = await readFileAsText(file)
      const { text: pathText, rowCount } = csvToPathText(raw, file.name)
      if (rowCount === 0) {
        setFileError("파일에서 카테고리 경로를 찾을 수 없습니다.")
        return
      }
      setUploadedFile(file)
      setFileRowCount(rowCount)
      setText(pathText)
      setPhase("input")
    } catch {
      setFileError("파일 읽기에 실패했습니다.")
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file) void handleFileSelect(file)
  }

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
      onClose?.()
    } catch (err) {
      setCommitError(err instanceof Error ? err.message : "일괄 생성 실패")
      setPhase("preview")
    }
  }

  return (
    <div className="flex h-full flex-col">
      {onClose && (
        <div className="flex items-center justify-between border-b px-4 py-3">
          <span className="text-sm font-medium">일괄 입력</span>
          <button
            onClick={onClose}
            className="flex h-5 w-5 items-center justify-center rounded text-muted-foreground hover:bg-muted"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {phase === "committing" ? (
        <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
          반영 중…
        </div>
      ) : (
        <div className="flex flex-1 flex-col overflow-hidden">
          <div className="flex flex-1 flex-col gap-2 overflow-y-auto p-3">

            {/* 모드 토글 (input 단계, lockedMode 없을 때만) */}
            {phase === "input" && !lockedMode && (
              <div className="flex rounded-md border overflow-hidden shrink-0">
                <button
                  onClick={() => { setInputMode("file"); resetInput() }}
                  className={cn(
                    "flex flex-1 items-center justify-center gap-1.5 py-1.5 text-xs font-medium transition-colors",
                    inputMode === "file"
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:bg-muted",
                  )}
                >
                  <Upload className="h-3.5 w-3.5" />
                  파일 업로드
                </button>
                <button
                  onClick={() => { setInputMode("text"); resetInput() }}
                  className={cn(
                    "flex flex-1 items-center justify-center gap-1.5 py-1.5 text-xs font-medium transition-colors",
                    inputMode === "text"
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:bg-muted",
                  )}
                >
                  <FileText className="h-3.5 w-3.5" />
                  텍스트 입력
                </button>
              </div>
            )}

            {/* ── 파일 업로드 모드 ── */}
            {inputMode === "file" && phase === "input" && (
              <>
                {/* 템플릿 다운로드 */}
                <button
                  onClick={downloadTemplate}
                  className="flex items-center justify-center gap-1.5 rounded-md border border-dashed py-2 text-xs text-muted-foreground hover:bg-muted transition-colors"
                >
                  <Download className="h-3.5 w-3.5" />
                  CSV 템플릿 다운로드
                </button>

                {/* 드래그&드롭 영역 */}
                {!uploadedFile ? (
                  <div
                    onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
                    onDragLeave={() => setDragOver(false)}
                    onDrop={handleDrop}
                    onClick={() => fileInputRef.current?.click()}
                    className={cn(
                      "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed py-8 transition-colors",
                      dragOver
                        ? "border-primary bg-primary/5"
                        : "border-border hover:border-primary/50 hover:bg-muted/30",
                    )}
                  >
                    <Upload className="h-8 w-8 text-muted-foreground opacity-40" />
                    <p className="text-sm text-muted-foreground">
                      CSV 파일을 드래그하거나 클릭하여 선택
                    </p>
                    <p className="text-xs text-muted-foreground opacity-60">
                      지원 형식: .csv · .txt
                    </p>
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept=".csv,.txt"
                      className="hidden"
                      onChange={(e) => {
                        const f = e.target.files?.[0]
                        if (f) void handleFileSelect(f)
                        e.target.value = ""
                      }}
                    />
                  </div>
                ) : (
                  /* 파일 선택 후 — 파일 정보 카드 */
                  <div className="flex items-center justify-between rounded-lg border bg-muted/30 px-3 py-2.5">
                    <div className="flex items-center gap-2">
                      <FileText className="h-4 w-4 shrink-0 text-primary" />
                      <div>
                        <p className="text-sm font-medium">{uploadedFile.name}</p>
                        <p className="text-xs text-muted-foreground">{fileRowCount}개 경로 감지</p>
                      </div>
                    </div>
                    <button
                      onClick={() => { setUploadedFile(null); setFileRowCount(0); setText("") }}
                      className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </div>
                )}

                {fileError && (
                  <p className="text-xs text-destructive">{fileError}</p>
                )}

                {/* CSV 포맷 안내 */}
                <div className="rounded-md bg-muted/50 p-2.5 text-xs text-muted-foreground space-y-1">
                  <p className="font-medium text-foreground">CSV 포맷 안내</p>
                  <p>첫 번째 열에 카테고리 경로를 <span className="font-mono bg-muted px-1 rounded">슬래시(/)</span>로 구분하여 입력합니다.</p>
                  <p className="font-mono bg-muted px-1.5 py-0.5 rounded">영화/액션, 시리즈/드라마/한국</p>
                </div>
              </>
            )}

            {/* ── 텍스트 입력 모드 ── */}
            {inputMode === "text" && phase === "input" && (
              <>
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>들여쓰기 또는 경로(A/B/C) 형식 자동 인식</span>
                  {detectedFormat && (
                    <span className="rounded bg-muted px-1.5 py-0.5 font-mono">{detectedFormat}</span>
                  )}
                </div>
                <textarea
                  value={text}
                  onChange={(e) => {
                    setText(e.target.value)
                    setParseResult(null)
                    setDiffResult(null)
                  }}
                  placeholder={"영화\n  액션\n  코미디\n시리즈\n  드라마\n\n또는 경로 형식:\n영화/액션\n영화/코미디"}
                  rows={8}
                  className="min-h-32 w-full resize-none rounded border bg-background p-2 font-mono text-xs leading-relaxed focus:outline-none focus:ring-1 focus:ring-ring"
                />
              </>
            )}

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
                <div className="border-b px-3 py-2 flex items-center justify-between text-xs text-muted-foreground">
                  <span className="font-medium">미리보기</span>
                  {uploadedFile && (
                    <span className="text-muted-foreground">{uploadedFile.name}</span>
                  )}
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
                  onClick={resetInput}
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
