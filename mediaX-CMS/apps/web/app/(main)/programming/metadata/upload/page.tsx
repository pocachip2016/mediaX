"use client"

import { useCallback, useState } from "react"
import Link from "next/link"
import { Upload, FileText, CheckCircle, AlertTriangle, XCircle, Download, ArrowLeft } from "lucide-react"
import { metadataApi, type BatchJobOut } from "@/lib/api"

// ── CSV 템플릿 다운로드 ───────────────────────────────────

function downloadTemplate() {
  const headers = "title,production_year,content_type,cp_name,synopsis"
  const rows = [
    "기생충,2019,movie,CJ ENM,전원 백수인 기택 가족이 부유한 박 사장 가족 집에 침투하면서 벌어지는 이야기.",
    "오징어 게임,2021,series,넷플릭스,456억 원의 상금을 건 생존 게임 서바이벌.",
    "서울의 봄,2023,movie,쇼박스,1979년 12월 수도 서울 한복판에서 벌어진 군사반란의 실화.",
  ]
  const csv = [headers, ...rows].join("\n")
  const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8;" })
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = "mediax_upload_template.csv"
  a.click()
  URL.revokeObjectURL(url)
}

// ── 파싱 미리보기 타입 ─────────────────────────────────────

interface ParsedRow {
  row: number
  title: string
  production_year: string
  content_type: string
  cp_name: string
  status: "ok" | "warning" | "error"
  message?: string
}

function parseCSVPreview(text: string, defaultCp: string): ParsedRow[] {
  const lines = text.split("\n").filter((l) => l.trim())
  if (lines.length < 2) return []
  const headers = lines[0]!.split(",").map((h) => h.trim().toLowerCase().replace(/['"]/g, ""))

  const getCol = (row: string[], names: string[]): string => {
    for (const n of names) {
      const idx = headers.indexOf(n)
      if (idx >= 0 && row[idx]) return row[idx]!.replace(/['"]/g, "").trim()
    }
    return ""
  }

  return lines.slice(1).map((line, i) => {
    const cols = line.split(",")
    const title = getCol(cols, ["title", "제목"])
    const year = getCol(cols, ["production_year", "제작연도"])
    const type = getCol(cols, ["content_type", "타입"]) || "movie"
    const cp = getCol(cols, ["cp_name", "cp사"]) || defaultCp

    let status: "ok" | "warning" | "error" = "ok"
    let message: string | undefined

    if (!title) {
      status = "error"
      message = "제목 없음"
    } else if (!year) {
      status = "warning"
      message = "제작연도 미상"
    }

    return { row: i + 1, title, production_year: year, content_type: type, cp_name: cp, status, message }
  }).filter((r) => r.title || r.status === "error")
}

// ── 메인 페이지 ──────────────────────────────────────────

export default function BatchUploadPage() {
  const [dragging, setDragging] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<ParsedRow[]>([])
  const [cpName, setCpName] = useState("")
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState<BatchJobOut | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleFile = useCallback((f: File) => {
    setFile(f)
    setResult(null)
    setError(null)
    if (f.name.toLowerCase().endsWith(".csv")) {
      const reader = new FileReader()
      reader.onload = (e) => {
        const text = e.target?.result as string
        setPreview(parseCSVPreview(text, cpName))
      }
      reader.readAsText(f, "utf-8")
    } else {
      setPreview([])
    }
  }, [cpName])

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const f = e.dataTransfer.files[0]
    if (f) handleFile(f)
  }, [handleFile])

  const onInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (f) handleFile(f)
  }

  const handleUpload = async () => {
    if (!file) return
    setUploading(true)
    setError(null)
    try {
      const fd = new FormData()
      fd.append("file", file)
      if (cpName) fd.append("cp_name", cpName)
      fd.append("created_by", "운영자")
      const res = await metadataApi.uploadBatch(fd)
      setResult(res)
    } catch (err) {
      setError(err instanceof Error ? err.message : "업로드 실패")
    } finally {
      setUploading(false)
    }
  }

  const okCount = preview.filter((r) => r.status === "ok").length
  const warnCount = preview.filter((r) => r.status === "warning").length
  const errCount = preview.filter((r) => r.status === "error").length

  return (
    <div className="space-y-6 max-w-4xl">
      {/* 헤더 */}
      <div className="flex items-center gap-3">
        <Link href="/programming/metadata" className="p-1.5 rounded-lg hover:bg-accent">
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <div>
          <h1 className="text-2xl font-bold">배치 업로드</h1>
          <p className="text-sm text-muted-foreground mt-1">CSV / Excel 파일로 콘텐츠 대량 등록</p>
        </div>
      </div>

      {/* 성공 결과 */}
      {result && (
        <div className="rounded-xl border border-green-200 dark:border-green-800/40 bg-green-50 dark:bg-green-900/10 p-5">
          <div className="flex items-center gap-2 mb-3">
            <CheckCircle className="h-5 w-5 text-green-600" />
            <h2 className="font-semibold text-green-700 dark:text-green-400">업로드 완료</h2>
          </div>
          <div className="grid grid-cols-3 gap-4 text-sm">
            <div><span className="text-muted-foreground">총 건수</span><div className="text-xl font-bold">{result.total_count}</div></div>
            <div><span className="text-muted-foreground">성공</span><div className="text-xl font-bold text-green-600">{result.success_count}</div></div>
            <div><span className="text-muted-foreground">실패</span><div className="text-xl font-bold text-red-500">{result.failed_count}</div></div>
          </div>
          <div className="mt-3 flex gap-2">
            <Link href="/programming/metadata" className="text-sm px-3 py-1.5 rounded-lg bg-green-600 text-white hover:bg-green-700">
              대시보드 이동
            </Link>
            <button
              onClick={() => { setResult(null); setFile(null); setPreview([]) }}
              className="text-sm px-3 py-1.5 rounded-lg border border-border hover:bg-accent"
            >
              새로 업로드
            </button>
          </div>
        </div>
      )}

      {!result && (
        <>
          {/* 드롭 존 */}
          <div
            onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            className={`rounded-xl border-2 border-dashed transition-colors p-10 text-center cursor-pointer ${
              dragging
                ? "border-primary bg-primary/5"
                : "border-border hover:border-primary/50 hover:bg-accent/30"
            }`}
            onClick={() => document.getElementById("file-input")?.click()}
          >
            <input
              id="file-input"
              type="file"
              accept=".csv,.xlsx,.xls"
              className="hidden"
              onChange={onInputChange}
            />
            <Upload className="h-10 w-10 mx-auto mb-3 text-muted-foreground" />
            {file ? (
              <div>
                <div className="font-medium flex items-center justify-center gap-2">
                  <FileText className="h-4 w-4" />
                  {file.name}
                </div>
                <div className="text-xs text-muted-foreground mt-1">{(file.size / 1024).toFixed(1)} KB</div>
              </div>
            ) : (
              <div>
                <div className="font-medium">CSV / Excel 파일 드롭</div>
                <div className="text-sm text-muted-foreground mt-1">또는 클릭해서 파일 선택</div>
                <div className="text-xs text-muted-foreground mt-2">.csv, .xlsx, .xls 최대 10MB</div>
              </div>
            )}
          </div>

          {/* 옵션 */}
          <div className="flex items-center gap-4 flex-wrap">
            <div className="flex items-center gap-2">
              <label className="text-sm font-medium whitespace-nowrap">CP사</label>
              <input
                className="rounded-lg border border-border px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary w-40"
                placeholder="CJ ENM"
                value={cpName}
                onChange={(e) => setCpName(e.target.value)}
              />
            </div>
            <button
              onClick={downloadTemplate}
              className="flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-lg border border-border hover:bg-accent"
            >
              <Download className="h-4 w-4" /> 템플릿 다운로드
            </button>
          </div>

          {/* 파싱 미리보기 */}
          {preview.length > 0 && (
            <div className="space-y-3">
              <div className="flex items-center gap-3 text-sm flex-wrap">
                <span className="font-medium">파싱 미리보기</span>
                <span className="text-muted-foreground">총 {preview.length}건</span>
                {okCount > 0 && <span className="flex items-center gap-1 text-green-600"><CheckCircle className="h-3.5 w-3.5" /> 정상 {okCount}</span>}
                {warnCount > 0 && <span className="flex items-center gap-1 text-yellow-600"><AlertTriangle className="h-3.5 w-3.5" /> 검토 {warnCount}</span>}
                {errCount > 0 && <span className="flex items-center gap-1 text-red-500"><XCircle className="h-3.5 w-3.5" /> 오류 {errCount}</span>}
              </div>

              <div className="rounded-xl border border-border overflow-hidden">
                <div className="overflow-x-auto max-h-64">
                  <table className="w-full text-sm">
                    <thead className="bg-muted/50 sticky top-0">
                      <tr>
                        <th className="text-left px-3 py-2 font-medium text-muted-foreground w-10">#</th>
                        <th className="text-left px-3 py-2 font-medium text-muted-foreground">제목</th>
                        <th className="text-left px-3 py-2 font-medium text-muted-foreground w-20">연도</th>
                        <th className="text-left px-3 py-2 font-medium text-muted-foreground w-20">타입</th>
                        <th className="text-left px-3 py-2 font-medium text-muted-foreground w-28">CP사</th>
                        <th className="text-left px-3 py-2 font-medium text-muted-foreground w-24">상태</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {preview.map((r) => (
                        <tr key={r.row} className={r.status === "error" ? "bg-red-50 dark:bg-red-900/10" : r.status === "warning" ? "bg-yellow-50 dark:bg-yellow-900/10" : ""}>
                          <td className="px-3 py-1.5 text-muted-foreground">{r.row}</td>
                          <td className="px-3 py-1.5 font-medium">{r.title || <span className="italic text-muted-foreground">없음</span>}</td>
                          <td className="px-3 py-1.5 text-muted-foreground">{r.production_year || "-"}</td>
                          <td className="px-3 py-1.5 text-muted-foreground">{r.content_type}</td>
                          <td className="px-3 py-1.5 text-muted-foreground">{r.cp_name || "-"}</td>
                          <td className="px-3 py-1.5">
                            {r.status === "ok" && <span className="flex items-center gap-1 text-green-600 text-xs"><CheckCircle className="h-3 w-3" /> 정상</span>}
                            {r.status === "warning" && <span className="flex items-center gap-1 text-yellow-600 text-xs"><AlertTriangle className="h-3 w-3" /> {r.message}</span>}
                            {r.status === "error" && <span className="flex items-center gap-1 text-red-500 text-xs"><XCircle className="h-3 w-3" /> {r.message}</span>}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* 에러 */}
          {error && (
            <div className="rounded-lg border border-red-200 dark:border-red-800/40 bg-red-50 dark:bg-red-900/10 px-4 py-3 text-sm text-red-600 dark:text-red-400">
              {error}
            </div>
          )}

          {/* 업로드 버튼 */}
          <div className="flex items-center justify-between">
            <div className="text-sm text-muted-foreground">
              {file ? `${file.name} — ${preview.filter((r) => r.status !== "error").length}건 처리 가능` : "파일을 선택하세요"}
            </div>
            <button
              onClick={handleUpload}
              disabled={!file || uploading || errCount === preview.length}
              className="flex items-center gap-2 px-5 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {uploading ? (
                <>
                  <div className="h-4 w-4 border-2 border-primary-foreground/30 border-t-primary-foreground rounded-full animate-spin" />
                  처리 중...
                </>
              ) : (
                <>
                  <Upload className="h-4 w-4" />
                  AI 처리 시작 {preview.length > 0 ? `(${preview.filter((r) => r.status !== "error").length}건)` : ""}
                </>
              )}
            </button>
          </div>
        </>
      )}
    </div>
  )
}
