"use client"

import { useState, useCallback } from "react"
import { useRouter } from "next/navigation"
import { ArrowLeft, Upload, FileText, AlertCircle, CheckCircle } from "lucide-react"
import Link from "next/link"
import { cn } from "@workspace/ui/lib/utils"
import { BASE } from "@/lib/api"

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

const FIELD_DESCRIPTIONS = [
  { field: "title", required: true, desc: "콘텐츠 제목" },
  { field: "production_year", required: false, desc: "제작년도 (숫자)" },
  { field: "content_type", required: true, desc: "movie / series / season / episode" },
  { field: "cp_name", required: true, desc: "CP사명" },
  { field: "synopsis", required: false, desc: "줄거리" },
  { field: "cast", required: false, desc: "출연진 (쉼표 구분)" },
  { field: "directors", required: false, desc: "감독 (쉼표 구분)" },
  { field: "genres", required: false, desc: "장르 (쉼표 구분)" },
  { field: "country", required: false, desc: "제작국가" },
  { field: "runtime", required: false, desc: "런타임 (분 단위 숫자)" },
  { field: "rating_age", required: false, desc: "시청등급" },
  { field: "poster_url", required: false, desc: "포스터 이미지 URL" },
]

export default function UploadPage() {
  const router = useRouter()
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<PreviewRow[]>([])
  const [previewHeaders, setPreviewHeaders] = useState<string[]>([])
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState<{ success: number; failed: number; job_id: number } | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleFileChange = useCallback(async (selectedFile: File) => {
    setError(null)
    setResult(null)
    setPreview([])

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
        throw new Error(err.detail || `업로드 실패 (${res.status})`)
      }

      const data = await res.json()
      setResult({ success: data.success_count, failed: data.failed_count, job_id: data.id })
    } catch (err) {
      setError(err instanceof Error ? err.message : "업로드 실패")
    } finally {
      setUploading(false)
    }
  }

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

      {/* 결과 메시지 */}
      {result && (
        <div className="mb-6 p-4 rounded-xl bg-green-50 border border-green-200 flex items-start gap-3">
          <CheckCircle className="h-5 w-5 text-green-600 mt-0.5 shrink-0" />
          <div>
            <p className="font-medium text-green-800">업로드 완료</p>
            <p className="text-sm text-green-700 mt-1">
              성공 {result.success}건 / 실패 {result.failed}건 (Job #{result.job_id})
            </p>
            <button
              onClick={() => router.push("/programming/contents")}
              className="mt-2 text-sm underline text-green-700 hover:text-green-900"
            >
              콘텐츠 목록으로 이동 →
            </button>
          </div>
        </div>
      )}

      {error && (
        <div className="mb-6 p-4 rounded-xl bg-destructive/10 border border-destructive/20 flex items-start gap-3">
          <AlertCircle className="h-5 w-5 text-destructive mt-0.5 shrink-0" />
          <p className="text-sm text-destructive">{error}</p>
        </div>
      )}

      <div className="space-y-6">
        {/* 파일 선택 */}
        <div
          className={cn(
            "rounded-xl border-2 border-dashed p-10 text-center transition-colors",
            file ? "border-primary/40 bg-primary/5" : "border-border hover:border-primary/40 hover:bg-accent/30",
          )}
          onDragOver={e => e.preventDefault()}
          onDrop={e => {
            e.preventDefault()
            const dropped = e.dataTransfer.files[0]
            if (dropped) handleFileChange(dropped)
          }}
        >
          <input
            type="file"
            accept=".csv,.xlsx,.xls"
            className="hidden"
            id="fileInput"
            onChange={e => { const f = e.target.files?.[0]; if (f) handleFileChange(f) }}
          />
          <label htmlFor="fileInput" className="cursor-pointer">
            <Upload className="h-8 w-8 mx-auto text-muted-foreground mb-3" />
            {file ? (
              <div>
                <p className="font-medium text-foreground flex items-center justify-center gap-2">
                  <FileText className="h-4 w-4" /> {file.name}
                </p>
                <p className="text-xs text-muted-foreground mt-1">{(file.size / 1024).toFixed(1)} KB</p>
              </div>
            ) : (
              <div>
                <p className="font-medium text-foreground">CSV 또는 Excel 파일을 선택하세요</p>
                <p className="text-sm text-muted-foreground mt-1">또는 이 영역에 드래그하세요</p>
              </div>
            )}
          </label>
        </div>

        {/* 미리보기 */}
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
                  </tr>
                </thead>
                <tbody>
                  {preview.map((row, i) => (
                    <tr key={i} className="border-t border-border">
                      {previewHeaders.map(h => (
                        <td key={h} className="px-3 py-2 border-r border-border last:border-0 max-w-[160px] truncate" title={row[h]}>
                          {row[h] || <span className="text-muted-foreground/50">—</span>}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* 필드 설명 */}
        <details className="rounded-xl border border-border">
          <summary className="px-4 py-3 cursor-pointer text-sm font-medium hover:bg-accent/30 rounded-xl">
            CSV 필드 설명 보기
          </summary>
          <div className="px-4 pb-4">
            <table className="w-full text-xs mt-2">
              <thead>
                <tr className="border-b border-border">
                  <th className="py-2 text-left font-medium text-muted-foreground">필드명</th>
                  <th className="py-2 text-left font-medium text-muted-foreground">필수</th>
                  <th className="py-2 text-left font-medium text-muted-foreground">설명</th>
                </tr>
              </thead>
              <tbody>
                {FIELD_DESCRIPTIONS.map(f => (
                  <tr key={f.field} className="border-b border-border last:border-0">
                    <td className="py-2 font-mono text-primary">{f.field}</td>
                    <td className="py-2">{f.required ? <span className="text-destructive font-medium">필수</span> : <span className="text-muted-foreground">선택</span>}</td>
                    <td className="py-2 text-muted-foreground">{f.desc}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>

        {/* 버튼 */}
        <div className="flex gap-3">
          <button
            onClick={handleUpload}
            disabled={!file || uploading}
            className="flex-1 py-2.5 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors flex items-center justify-center gap-2"
          >
            <Upload className="h-4 w-4" />
            {uploading ? "업로드 중..." : "업로드"}
          </button>
          <button
            onClick={() => { setFile(null); setPreview([]); setResult(null) }}
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
