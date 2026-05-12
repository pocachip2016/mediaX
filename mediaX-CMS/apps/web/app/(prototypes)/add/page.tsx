"use client"

import { useState } from "react"
import { Upload, Search, Plus, X } from "lucide-react"
import { cn } from "@workspace/ui/lib/utils"

type AddTab = "single" | "csv" | "external"

export default function PrototypeAddPage() {
  const [activeTab, setActiveTab] = useState<AddTab>("single")
  const [singleForm, setSingleForm] = useState({
    title: "",
    original_title: "",
    production_year: "",
    content_type: "movie",
    cp_name: "",
    synopsis: "",
  })

  return (
    <div className="min-h-screen bg-slate-50 p-6">
      <div className="max-w-2xl mx-auto">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-slate-900">콘텐츠 추가</h1>
          <p className="text-sm text-slate-500 mt-1">단일 입력 / CSV 배치 / 외부 검색 3가지 방식 제공</p>
        </div>

        {/* Modal */}
        <div className="bg-white rounded-lg border border-slate-200 overflow-hidden shadow-lg">
          {/* Tabs */}
          <div className="border-b border-slate-200 flex">
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
          <div className="p-6">
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
                  <button className="px-4 py-2 rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-50 font-medium">취소</button>
                  <button className="px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700 font-medium">등록</button>
                </div>
              </div>
            )}

            {/* CSV Tab */}
            {activeTab === "csv" && (
              <div className="space-y-4">
                <div className="border-2 border-dashed border-slate-300 rounded-lg p-8 text-center hover:border-blue-400 transition-colors">
                  <Upload className="h-8 w-8 text-slate-400 mx-auto mb-2" />
                  <p className="text-sm font-medium text-slate-700">CSV/Excel 파일을 드래그하거나 클릭해서 업로드</p>
                  <p className="text-xs text-slate-500 mt-1">최대 파일 크기: 10MB</p>
                  <button className="mt-3 px-4 py-2 rounded-lg bg-slate-100 text-slate-700 hover:bg-slate-200 text-sm font-medium">파일 선택</button>
                </div>

                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <p className="text-sm font-medium text-blue-900 mb-2">✨ CSV 미리보기 (dry-run)</p>
                  <div className="grid grid-cols-4 gap-2 text-xs text-blue-700">
                    <div>정상 242건</div>
                    <div>누락 241건</div>
                    <div>에러 0건</div>
                    <div>중복 0건</div>
                  </div>
                  <p className="text-xs text-blue-600 mt-2">💡 누락 필드는 TMDB/KOBIS/AI로 자동 보강될 예정입니다.</p>
                </div>

                <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
                  <p className="text-sm font-medium text-amber-900">📊 누락 필드 분포</p>
                  <ul className="text-xs text-amber-700 mt-2 space-y-1">
                    <li>production_year (157건) — TMDB 매칭률 95% 예상</li>
                    <li>synopsis (132건) — AI fallback 필요 가능성 높음</li>
                    <li>cp_name (89건) — CSV 기본값 적용</li>
                  </ul>
                </div>

                <div className="text-xs text-slate-500">
                  <strong>예상 비용:</strong> AI 호출 ~50건 × $0.001 = ~$0.05 | <strong>소요:</strong> 2~3분
                </div>

                <div className="flex gap-2 justify-end pt-4 border-t border-slate-200">
                  <button className="px-4 py-2 rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-50 font-medium">취소</button>
                  <button className="px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700 font-medium">업로드 진행</button>
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
                    className="flex-1 px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                  <button className="px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700 font-medium inline-flex items-center gap-2">
                    <Search className="h-4 w-4" />
                    검색
                  </button>
                </div>

                <div className="space-y-3">
                  {[
                    { title: "Parasite", year: 2019, source: "TMDB", match: 0.94, director: "봉준호" },
                    { title: "기생충", year: 2019, source: "KOBIS", match: 0.87, director: "봉준호" },
                    { title: "Parasite", year: 2019, source: "Watcha", match: 0.79, director: "봉준호" },
                  ].map((result, i) => (
                    <div key={i} className="border border-slate-200 rounded-lg p-4 hover:border-blue-400 transition-colors">
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <p className="font-medium text-slate-900">
                            {result.title}
                            <span className="ml-2 text-xs font-normal text-slate-500">({result.year})</span>
                          </p>
                          <p className="text-sm text-slate-600 mt-1">{result.director}</p>
                          <div className="flex gap-2 mt-2">
                            <span className="inline-block px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-700">{result.source}</span>
                            <span
                              className={cn(
                                "inline-block px-2 py-0.5 rounded-full text-xs font-medium",
                                result.match >= 0.9
                                  ? "bg-green-100 text-green-700"
                                  : result.match >= 0.7
                                    ? "bg-amber-100 text-amber-700"
                                    : "bg-red-100 text-red-700",
                              )}
                            >
                              match {(result.match * 100).toFixed(0)}%
                            </span>
                          </div>
                        </div>
                        <button className="px-3 py-1.5 rounded-lg bg-blue-100 text-blue-700 hover:bg-blue-200 text-sm font-medium">
                          <Plus className="h-4 w-4" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="text-xs text-slate-500">
                  TMDB, KOBIS, KMDB, Watcha 등에서 검색 후 매칭된 메타데이터를 자동으로 가져옵니다.
                </div>

                <div className="flex gap-2 justify-end pt-4 border-t border-slate-200">
                  <button className="px-4 py-2 rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-50 font-medium">취소</button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
