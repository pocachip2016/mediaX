"use client"

import { useState, useCallback, useRef } from "react"
import { Upload, Search, Plus, X } from "lucide-react"
import { cn } from "@workspace/ui/lib/utils"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@workspace/ui/components/dialog"
import { metadataApi } from "@/lib/api"

type AddTab = "single" | "csv" | "external"

interface AddContentModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function AddContentModal({ open, onOpenChange }: AddContentModalProps) {
  const [activeTab, setActiveTab] = useState<AddTab>("single")
  const [singleForm, setSingleForm] = useState({
    title: "",
    original_title: "",
    production_year: "",
    content_type: "movie",
    cp_name: "",
    synopsis: "",
  })

  // CSV 파일 선택 state
  const [selectedFile, setSelectedFile] = useState<File | null>(null)

  // External search state
  const [searchQuery, setSearchQuery] = useState("")
  const [searchResults, setSearchResults] = useState<any[]>([])
  const [searching, setSearching] = useState(false)
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null)
  const fileInputRef = useRef<HTMLInputElement | null>(null)

  // Handle external search with debounce
  const handleSearch = useCallback(async (query: string) => {
    setSearchQuery(query)
    if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current)

    if (!query.trim()) {
      setSearchResults([])
      return
    }

    debounceTimerRef.current = setTimeout(async () => {
      try {
        setSearching(true)
        const result = await metadataApi.sourcesSearch(query, ["tmdb", "kobis", "kmdb"])
        setSearchResults(result.results || [])
      } catch (error) {
        console.error("Search failed:", error)
        setSearchResults([])
      } finally {
        setSearching(false)
      }
    }, 300)
  }, [])

  // Handle creating content from source
  const handleCreateFromSource = async (sourceId: number, sourceName: string) => {
    try {
      const result = await metadataApi.createFromSources({
        source_id: sourceId,
        selected_fields: ["title", "director", "synopsis"],
        cp_name: singleForm.cp_name || "자동생성",
      })
      alert(`콘텐츠 "${result.title}"이 생성되었습니다.`)
      setSearchQuery("")
      setSearchResults([])
      onOpenChange(false)
    } catch (error) {
      console.error("Create from source failed:", error)
      alert("소스에서 콘텐츠 생성에 실패했습니다.")
    }
  }

  // Handle CSV batch upload
  const handleBatchPreview = async (file?: File) => {
    if (!file) return
    try {
      const formData = new FormData()
      formData.append("file", file)
      const result: any = await metadataApi.batchPreviewCsv(formData)
      const total = result.total_count ?? 0
      const success = result.success_count ?? 0
      const failed = result.failed_count ?? 0
      alert(`배치 업로드 완료 (job #${result.id}): 총 ${total}건 중 ${success}건 성공, ${failed}건 실패`)
      setSelectedFile(null)
      onOpenChange(false)
    } catch (error) {
      console.error("[CSV] API call failed:", error)
      alert(`CSV 업로드 실패: ${error instanceof Error ? error.message : String(error)}`)
    }
  }

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      setSelectedFile(file)
      e.target.value = ''
    }
  }, [])

  const handleSave = () => {
    console.log("Mock save:", { tab: activeTab, data: singleForm })
    alert(`[Mock] ${activeTab} 탭에서 저장 시도`)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>콘텐츠 추가</DialogTitle>
        </DialogHeader>

        {/* Tabs */}
        <div className="border-b border-slate-200 flex gap-0 -mx-6 px-6">
          {(["single", "csv", "external"] as AddTab[]).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={cn(
                "flex-1 px-4 py-4 font-medium text-sm border-b-2 transition-colors",
                activeTab === tab ? "border-blue-500 text-blue-600 bg-blue-50" : "border-transparent text-slate-600 hover:text-slate-900",
              )}
            >
              {tab === "single" && "🔹 단일 입력"}
              {tab === "csv" && "📊 CSV 배치"}
              {tab === "external" && "🔍 외부 검색"}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="space-y-4">
          {/* Single Input Tab */}
          {activeTab === "single" && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">제목 *</label>
                  <input
                    type="text"
                    placeholder="예: 기생충"
                    value={singleForm.title}
                    onChange={(e) => setSingleForm({ ...singleForm, title: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">원제</label>
                  <input
                    type="text"
                    placeholder="예: Parasite"
                    value={singleForm.original_title}
                    onChange={(e) => setSingleForm({ ...singleForm, original_title: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">제작년도</label>
                  <input
                    type="number"
                    placeholder="2019"
                    value={singleForm.production_year}
                    onChange={(e) => setSingleForm({ ...singleForm, production_year: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">콘텐츠 유형 *</label>
                  <select
                    value={singleForm.content_type}
                    onChange={(e) => setSingleForm({ ...singleForm, content_type: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="movie">영화</option>
                    <option value="series">시리즈</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">CP사 *</label>
                  <input
                    type="text"
                    placeholder="CJ ENM"
                    value={singleForm.cp_name}
                    onChange={(e) => setSingleForm({ ...singleForm, cp_name: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">시놉시스</label>
                <textarea
                  placeholder="콘텐츠 설명..."
                  value={singleForm.synopsis}
                  onChange={(e) => setSingleForm({ ...singleForm, synopsis: e.target.value })}
                  rows={4}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div className="text-xs text-slate-500">
                입력 완료 후 시스템이 TMDB/KOBIS에서 자동 매칭 및 AI 보강을 진행합니다.
              </div>

              <div className="flex gap-2 justify-end pt-4 border-t border-slate-200">
                <button
                  onClick={() => onOpenChange(false)}
                  className="px-4 py-2 rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-50 font-medium"
                >
                  취소
                </button>
                <button
                  onClick={handleSave}
                  className="px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700 font-medium"
                >
                  등록
                </button>
              </div>
            </div>
          )}

          {/* CSV Tab */}
          {activeTab === "csv" && (
            <div className="space-y-4">
              <label className="block border-2 border-dashed border-slate-300 rounded-lg p-8 text-center hover:border-blue-400 transition-colors cursor-pointer">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".csv,.xlsx,.xls"
                  onChange={handleFileSelect}
                  className="hidden"
                />
                <Upload className="h-8 w-8 text-slate-400 mx-auto mb-2" />
                {selectedFile ? (
                  <p className="text-sm font-medium text-blue-700">{selectedFile.name} ({(selectedFile.size / 1024).toFixed(1)} KB)</p>
                ) : (
                  <p className="text-sm font-medium text-slate-700">CSV/Excel 파일을 드래그하거나 클릭해서 업로드</p>
                )}
                <p className="text-xs text-slate-500 mt-1">최대 파일 크기: 10MB</p>
                <span className="mt-3 inline-block px-4 py-2 rounded-lg bg-slate-100 text-slate-700 hover:bg-slate-200 text-sm font-medium">
                  {selectedFile ? "파일 변경" : "파일 선택"}
                </span>
              </label>

              <div className="bg-slate-50 rounded-lg p-3 text-xs text-slate-600">
                <p className="font-semibold mb-1">CSV 컬럼 (헤더명 또는 한글 대체명)</p>
                <ul className="space-y-0.5">
                  <li><span className="font-mono bg-white px-1 rounded">title</span> / 제목 <span className="text-red-500">*필수</span></li>
                  <li><span className="font-mono bg-white px-1 rounded">production_year</span> / 제작연도</li>
                  <li><span className="font-mono bg-white px-1 rounded">content_type</span> / 타입 (movie/series/season/episode)</li>
                  <li><span className="font-mono bg-white px-1 rounded">cp_name</span> / CP사</li>
                  <li><span className="font-mono bg-white px-1 rounded">synopsis</span> / 시놉시스</li>
                  <li><span className="font-mono bg-white px-1 rounded">poster_url</span> / 포스터URL — 포스터 이미지 URL (선택)</li>
                </ul>
              </div>

              <div className="flex gap-2 justify-end pt-4 border-t border-slate-200">
                <button
                  onClick={() => onOpenChange(false)}
                  className="px-4 py-2 rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-50 font-medium"
                >
                  취소
                </button>
                <button
                  onClick={() => handleBatchPreview(selectedFile ?? undefined)}
                  disabled={!selectedFile}
                  className="px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700 font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  업로드 진행
                </button>
              </div>
            </div>
          )}

          {/* External Search Tab */}
          {activeTab === "external" && (
            <div className="space-y-4">
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="영화/시리즈 제목으로 검색..."
                  value={searchQuery}
                  onChange={(e) => handleSearch(e.target.value)}
                  className="flex-1 px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <button
                  onClick={() => handleSearch(searchQuery)}
                  disabled={searching}
                  className="px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700 font-medium inline-flex items-center gap-2 disabled:opacity-50"
                >
                  <Search className="h-4 w-4" />
                  {searching ? "검색중..." : "검색"}
                </button>
              </div>

              <div className="space-y-3">
                {searchResults.length > 0 ? (
                  searchResults.map((result, i) => (
                    <div key={i} className="border border-slate-200 rounded-lg p-4 hover:border-blue-400 transition-colors">
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <p className="font-medium text-slate-900">
                            {result.title}
                            <span className="ml-2 text-xs font-normal text-slate-500">({result.year || "?"})</span>
                          </p>
                          <p className="text-sm text-slate-600 mt-1">{result.director || "감독정보없음"}</p>
                          <div className="flex gap-2 mt-2">
                            <span className="inline-block px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-700">
                              {result.source}
                            </span>
                            <span
                              className={cn(
                                "inline-block px-2 py-0.5 rounded-full text-xs font-medium",
                                result.match_percent >= 0.9
                                  ? "bg-green-100 text-green-700"
                                  : result.match_percent >= 0.7
                                    ? "bg-amber-100 text-amber-700"
                                    : "bg-red-100 text-red-700",
                              )}
                            >
                              match {(result.match_percent * 100).toFixed(0)}%
                            </span>
                          </div>
                        </div>
                        <button
                          onClick={() => handleCreateFromSource(result.id || i, result.source)}
                          className="px-3 py-1.5 rounded-lg bg-blue-100 text-blue-700 hover:bg-blue-200 text-sm font-medium"
                        >
                          <Plus className="h-4 w-4" />
                        </button>
                      </div>
                    </div>
                  ))
                ) : searchQuery ? (
                  <div className="text-center py-8 text-slate-500">검색 결과가 없습니다.</div>
                ) : (
                  <div className="text-center py-8 text-slate-500">검색어를 입력하세요.</div>
                )}
              </div>

              <div className="text-xs text-slate-500">
                TMDB, KOBIS, KMDB, Watcha 등에서 검색 후 매칭된 메타데이터를 자동으로 가져옵니다.
              </div>

              <div className="flex gap-2 justify-end pt-4 border-t border-slate-200">
                <button
                  onClick={() => onOpenChange(false)}
                  className="px-4 py-2 rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-50 font-medium"
                >
                  취소
                </button>
              </div>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
