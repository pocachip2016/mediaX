"use client"

import { useState, useCallback, useEffect } from "react"
import { useRouter } from "next/navigation"
import { ArrowLeft, Upload, FileText, AlertCircle, CheckCircle } from "lucide-react"
import Link from "next/link"
import { cn } from "@workspace/ui/lib/utils"
import { BASE } from "@/lib/api"
import { TemplateModeToggle } from "@/components/contents/upload/TemplateModeToggle"
import { MovieFieldsTable } from "@/components/contents/upload/MovieFieldsTable"
import { SeriesFieldsTable } from "@/components/contents/upload/SeriesFieldsTable"
import { ModeMismatchWarning } from "@/components/contents/upload/ModeMismatchWarning"
import { BulkReviewQueue } from "@/components/contents/BulkReviewQueue"
import {
  validateAgainstMode,
  type TemplateMode,
  type ValidationResult,
} from "@/components/contents/upload/validateAgainstMode"

interface PreviewRow {
  [key: string]: string
}

function parseCSVLine(line: string): string[] {
  const cells: string[] = []
  let current = ""
  let inQuotes = false
  for (let i = 0; i < line.length; i++) {
    const ch = line[i]!
    if (ch === '"') {
      if (inQuotes && line[i + 1] === '"') { current += '"'; i++ }
      else { inQuotes = !inQuotes }
    } else if (ch === "," && !inQuotes) {
      cells.push(current.trim()); current = ""
    } else {
      current += ch
    }
  }
  cells.push(current.trim())
  return cells
}

export default function UploadPage() {
  const router = useRouter()
  const [templateMode, setTemplateMode] = useState<TemplateMode>(null)
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<PreviewRow[]>([])
  const [previewHeaders, setPreviewHeaders] = useState<string[]>([])
  const [totalRows, setTotalRows] = useState(0)
  const [validation, setValidation] = useState<ValidationResult | null>(null)
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState<{ success: number; failed: number; job_id: number } | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (previewHeaders.length > 0) {
      setValidation(validateAgainstMode(previewHeaders, preview, templateMode))
    } else {
      setValidation(null)
    }
  }, [templateMode, previewHeaders, preview])

  const handleFileChange = useCallback(async (selectedFile: File) => {
    setError(null)
    setResult(null)
    setPreview([])
    setPreviewHeaders([])
    setTotalRows(0)

    const isCSV = selectedFile.name.toLowerCase().endsWith(".csv")
    const isExcel = selectedFile.name.toLowerCase().endsWith(".xlsx") || selectedFile.name.toLowerCase().endsWith(".xls")
    if (!isCSV && !isExcel) {
      setError("CSV 또는 Excel(.xlsx) 파일만 허용됩니다")
      return
    }

    setFile(selectedFile)

    if (isCSV) {
      const buffer = await selectedFile.arrayBuffer()
      let text: string | null = null
      try {
        text = new TextDecoder("utf-8", { fatal: true }).decode(buffer)
      } catch {
        try {
          text = new TextDecoder("euc-kr").decode(buffer)
        } catch {
          setError("파일 인코딩을 인식할 수 없습니다 (UTF-8 또는 CP949/EUC-KR만 지원)")
          return
        }
      }
      const lines = text.split("\n").filter(l => l.trim())
      if (lines.length < 2) return
      const headers = parseCSVLine(lines[0]!)
      const rows = lines.slice(1, 4).map(line => {
        const cells = parseCSVLine(line)
        return headers.reduce<PreviewRow>((acc, h, i) => {
          acc[h] = (cells[i] ?? "").trim()
          return acc
        }, {})
      })
      setPreviewHeaders(headers)
      setPreview(rows)
      setTotalRows(lines.length - 1)
    }
  }, [])

  async function handleUpload() {
    if (!file) return
    setError(null)
    setUploading(true)
    try {
      const formData = new FormData()
      formData.append("file", file)

      const res = await fetch(`${BASE}/api/programming/metadata/upload/batch`, {
        method: "POST",
        body: formData,
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error((err as { detail?: string }).detail ?? `업로드 실패 (${res.status})`)
      }

      const data = await res.json() as { success_count: number; failed_count: number; id: number }
      setResult({ success: data.success_count, failed: data.failed_count, job_id: data.id })
    } catch (err) {
      setError(err instanceof Error ? err.message : "업로드 실패")
    } finally {
      setUploading(false)
    }
  }

  function handleReset() {
    setFile(null)
    setPreview([])
    setPreviewHeaders([])
    setTotalRows(0)
    setResult(null)
    setValidation(null)
    setError(null)
  }

  const canUpload = !!file && !!templateMode && !uploading
  const hasMismatch = validation?.modeMismatch === true

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <div className="flex items-center gap-3 mb-6">
        <Link href="/programming/contents" className="p-1.5 rounded-lg hover:bg-accent transition-colors">
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <div>
          <h1 className="text-xl font-bold">일괄 업로드</h1>
          <p className="text-sm text-muted-foreground">CSV 또는 Excel 파일로 여러 콘텐츠를 한 번에 등록합니다</p>
        </div>
      </div>

      {result && (
        <div className="mb-6 space-y-4">
          <div className="p-4 rounded-xl bg-green-50 border border-green-200 flex items-start gap-3">
            <CheckCircle className="h-5 w-5 text-green-600 mt-0.5 shrink-0" />
            <div className="flex-1">
              <p className="font-medium text-green-800">업로드 완료</p>
              <p className="text-sm text-green-700 mt-1">
                성공 {result.success}건 / 실패 {result.failed}건 (Job #{result.job_id})
              </p>
              <div className="mt-2 flex items-center gap-4">
                <button
                  onClick={() => router.push("/programming/contents")}
                  className="text-sm underline text-green-700 hover:text-green-900"
                >
                  콘텐츠 목록으로 이동 →
                </button>
                <span className="text-green-300">│</span>
                <span className="text-sm font-medium text-blue-700">추천 검수 큐 ↓</span>
              </div>
            </div>
          </div>
          <BulkReviewQueue />
        </div>
      )}

      {error && (
        <div className="mb-6 p-4 rounded-xl bg-destructive/10 border border-destructive/20 flex items-start gap-3">
          <AlertCircle className="h-5 w-5 text-destructive mt-0.5 shrink-0" />
          <p className="text-sm text-destructive">{error}</p>
        </div>
      )}

      <div className="space-y-6">
        {/* ① 템플릿 선택 */}
        <TemplateModeToggle value={templateMode} onChange={setTemplateMode} />

        {/* ② 컬럼 안내 + 템플릿 다운로드 */}
        {templateMode && (
          <div className="rounded-xl border border-border">
            <div className="px-4 py-3 bg-muted/50 border-b border-border flex items-center justify-between">
              <p className="text-sm font-medium">
                ② 컬럼 안내 ({templateMode === "movie" ? "Movie" : "Series"})
              </p>
              <a
                href={`/templates/${templateMode}.csv`}
                download
                className="text-xs flex items-center gap-1 text-primary hover:underline"
              >
                📥 {templateMode}.csv 템플릿 다운로드
              </a>
            </div>
            <div className="px-4 py-4">
              {templateMode === "movie" ? <MovieFieldsTable /> : <SeriesFieldsTable />}
            </div>
          </div>
        )}

        {/* ③ 파일 업로드 (드랍존) */}
        <div>
          {!templateMode && (
            <p className="text-xs text-muted-foreground mb-2">먼저 템플릿 모드를 선택하세요</p>
          )}
          <div
            className={cn(
              "rounded-xl border-2 border-dashed p-10 text-center transition-colors",
              !templateMode && "opacity-50 pointer-events-none",
              file ? "border-primary/40 bg-primary/5" : "border-border hover:border-primary/40 hover:bg-accent/30",
            )}
            onDragOver={e => e.preventDefault()}
            onDrop={e => {
              e.preventDefault()
              if (!templateMode) return
              const dropped = e.dataTransfer.files[0]
              if (dropped) void handleFileChange(dropped)
            }}
          >
            <input
              type="file"
              accept=".csv,.xlsx,.xls"
              className="hidden"
              id="fileInput"
              onChange={e => { const f = e.target.files?.[0]; if (f) void handleFileChange(f) }}
            />
            <label htmlFor="fileInput" className="cursor-pointer">
              <Upload className="h-8 w-8 mx-auto text-muted-foreground mb-3" />
              {file ? (
                <div>
                  <p className="font-medium text-foreground flex items-center justify-center gap-2">
                    <FileText className="h-4 w-4" /> {file.name}
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    {(file.size / 1024).toFixed(1)} KB{totalRows > 0 ? ` · ${totalRows}행` : ""}
                  </p>
                </div>
              ) : (
                <div>
                  <p className="font-medium text-foreground">CSV 또는 Excel 파일을 선택하세요</p>
                  <p className="text-sm text-muted-foreground mt-1">또는 이 영역에 드래그하세요</p>
                </div>
              )}
            </label>
          </div>
        </div>

        {/* 모드 미스매치 경고 */}
        {hasMismatch && validation && (
          <ModeMismatchWarning
            mode={templateMode}
            reasons={validation.mismatchReasons}
            onSwitchMode={() => setTemplateMode(templateMode === "movie" ? "series" : "movie")}
            onProceed={handleUpload}
          />
        )}

        {/* ④ 미리보기 */}
        {preview.length > 0 && (
          <div className="rounded-xl border border-border overflow-hidden">
            <div className="px-4 py-3 bg-muted/50 border-b border-border">
              <p className="text-sm font-medium">미리보기 (첫 {preview.length}행)</p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead className="bg-muted/30">
                  <tr>
                    {previewHeaders.map(h => (
                      <th key={h} className="px-3 py-2 text-left font-medium text-muted-foreground border-r border-border last:border-0">
                        {h}
                      </th>
                    ))}
                    {validation && !hasMismatch && (
                      <th className="px-3 py-2 text-left font-medium text-muted-foreground">검증</th>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {preview.map((row, i) => (
                    <tr key={i} className="border-t border-border">
                      {previewHeaders.map(h => (
                        <td key={h} className="px-3 py-2 border-r border-border last:border-0 max-w-[160px] truncate" title={row[h]}>
                          {row[h] ?? "" ? row[h] : <span className="text-muted-foreground/50">—</span>}
                        </td>
                      ))}
                      {validation && !hasMismatch && (
                        <td className="px-3 py-2">
                          {validation.rowOk[i] === false ? (
                            <span
                              className="text-destructive"
                              title={validation.rowErrors[i]?.join(", ")}
                            >
                              ⚠ {validation.rowErrors[i]?.[0]}
                            </span>
                          ) : (
                            <span className="text-green-600">✓ OK</span>
                          )}
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* 버튼 */}
        <div className="flex gap-3">
          <button
            onClick={handleUpload}
            disabled={!canUpload || hasMismatch}
            className="flex-1 py-2.5 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors flex items-center justify-center gap-2"
          >
            <Upload className="h-4 w-4" />
            {uploading ? "업로드 중..." : totalRows > 0 ? `업로드 (${totalRows}건)` : "업로드"}
          </button>
          <button
            onClick={handleReset}
            disabled={uploading}
            className="px-6 py-2.5 rounded-lg border border-border text-sm font-medium hover:bg-accent transition-colors"
          >
            초기화
          </button>
        </div>
      </div>
    </div>
  )
}
