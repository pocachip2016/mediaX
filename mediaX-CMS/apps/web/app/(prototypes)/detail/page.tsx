"use client"

import { useState } from "react"
import { Check, X, RotateCcw, Eye, Edit, Download, AlertCircle, Star, ChevronDown, Film, MessageCircle } from "lucide-react"
import { cn } from "@workspace/ui/lib/utils"

type TabName = "text" | "image" | "video" | "sources" | "ai"

const mockContent = {
  id: 1,
  title: "기생충",
  original_title: "Parasite",
  content_type: "movie",
  status: "review" as const,
  cp_name: "CJ ENM",
  production_year: 2019,
  runtime_minutes: 132,
  country: "대한민국",
  quality_score: 87,
  created_at: "2026-05-13T09:15:00",
}

const tabMeta = {
  text: { label: "글자", status: "completed" as const },
  image: { label: "이미지", status: "completed" as const },
  video: { label: "영상", status: "pending" as const },
  sources: { label: "외부소스", count: 3 },
  ai: { label: "AI 이력", count: 8 },
}

function TabStatusBadge({ tab }: { tab: "text" | "image" | "video" }) {
  const status = tabMeta[tab].status
  const icon = status === "completed" ? "●" : "○"
  const color = status === "completed" ? "text-green-600" : "text-gray-400"
  return <span className={color}>{icon}</span>
}

function TabCountBadge({ tab }: { tab: "sources" | "ai" }) {
  const count = tabMeta[tab].count
  return <span className="text-xs font-medium text-slate-500 ml-2">{count}</span>
}

export default function PrototypeDetailPage() {
  const [activeTab, setActiveTab] = useState<TabName>("text")
  const [selectedSynopsis, setSelectedSynopsis] = useState<"cp" | "ai" | "tmdb" | "manual">("ai")

  return (
    <div className="min-h-screen bg-slate-50 p-6">
      {/* Header */}
      <div className="mb-6 bg-white rounded-lg border border-slate-200 p-6">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">{mockContent.title}</h1>
            {mockContent.original_title && <p className="text-slate-600 text-sm mt-1">{mockContent.original_title}</p>}
            <p className="text-slate-500 text-sm mt-2">
              {mockContent.content_type === "movie" ? "영화" : "시리즈"} · {mockContent.cp_name} · {mockContent.production_year}
            </p>
          </div>
          <div className="text-right">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-100 text-amber-700 text-sm font-medium">
              🟧 검수
            </div>
            <p className="text-slate-500 text-xs mt-2">ID: #{mockContent.id}</p>
          </div>
        </div>

        <div className="flex items-center gap-4 mb-4 pb-4 border-b border-slate-200">
          <div className="flex-1">
            <p className="text-xs text-slate-500 mb-1">품질 점수</p>
            <div className="flex items-center gap-2">
              <div className="flex-1 bg-slate-200 rounded-full h-2 overflow-hidden">
                <div className="bg-amber-500 h-full" style={{ width: `${mockContent.quality_score}%` }} />
              </div>
              <span className="font-bold text-sm text-amber-700">{mockContent.quality_score}</span>
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex gap-2">
          <button className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-green-100 text-green-700 font-medium hover:bg-green-200 text-sm">
            <Check className="h-4 w-4" />
            승인
          </button>
          <button className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-red-100 text-red-700 font-medium hover:bg-red-200 text-sm">
            <X className="h-4 w-4" />
            반려
          </button>
          <button className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-orange-100 text-orange-700 font-medium hover:bg-orange-200 text-sm">
            <RotateCcw className="h-4 w-4" />
            AI 재처리
          </button>
          <button className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-blue-100 text-blue-700 font-medium hover:bg-blue-200 text-sm">
            <Eye className="h-4 w-4" />
            외부 재매칭
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
        <div className="border-b border-slate-200 flex gap-4 px-6">
          {(["text", "image", "video", "sources", "ai"] as TabName[]).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={cn(
                "px-4 py-3 font-medium border-b-2 transition-colors text-sm flex items-center gap-2",
                activeTab === tab ? "border-blue-500 text-blue-600" : "border-transparent text-slate-600 hover:text-slate-900",
              )}
            >
              {tab === "text" && <TabStatusBadge tab="text" />}
              {tab === "image" && <TabStatusBadge tab="image" />}
              {tab === "video" && <TabStatusBadge tab="video" />}
              {tabMeta[tab].label}
              {(tab === "sources" || tab === "ai") && <TabCountBadge tab={tab} />}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        <div className="p-6">
          {activeTab === "text" && (
            <div className="space-y-6">
              {/* Synopsis Field */}
              <div>
                <h3 className="font-semibold text-slate-900 mb-3">시놉시스</h3>
                <div className="grid grid-cols-3 gap-4">
                  {/* CP */}
                  <div className="border border-slate-200 rounded-lg p-4 bg-slate-50">
                    <div className="text-xs font-semibold text-slate-600 mb-2">
                      <span className="inline-block px-2 py-0.5 rounded bg-slate-200 text-slate-700">[CP]</span>
                      <span className="ml-2">trust 100</span>
                    </div>
                    <p className="text-sm text-slate-500">(없음)</p>
                    <input type="radio" name="synopsis" disabled className="mt-3" />
                  </div>

                  {/* AI */}
                  <div className={cn("border-2 rounded-lg p-4", selectedSynopsis === "ai" ? "border-blue-400 bg-blue-50" : "border-slate-200 bg-white")}>
                    <div className="text-xs font-semibold text-slate-600 mb-2 flex items-center justify-between">
                      <span>
                        <span className="inline-block px-2 py-0.5 rounded bg-purple-100 text-purple-700">[AI gemini]</span>
                        <span className="ml-2">score 89</span>
                      </span>
                      <span className="inline-block px-2 py-0.5 rounded bg-green-100 text-green-700 text-xs">자동</span>
                    </div>
                    <p className="text-sm text-slate-700 mb-3">가난한 가족이 부유한 가족의 집에 침투하면서...</p>
                    <button className="text-xs text-blue-600 hover:text-blue-700 font-medium">자세히 보기</button>
                    <div className="mt-3">
                      <input
                        type="radio"
                        name="synopsis"
                        checked={selectedSynopsis === "ai"}
                        onChange={() => setSelectedSynopsis("ai")}
                        className="cursor-pointer"
                      />
                      <label className="ml-2 text-sm text-slate-700">사용</label>
                    </div>
                  </div>

                  {/* TMDB */}
                  <div className={cn("border-2 rounded-lg p-4", selectedSynopsis === "tmdb" ? "border-blue-400 bg-blue-50" : "border-slate-200 bg-white")}>
                    <div className="text-xs font-semibold text-slate-600 mb-2">
                      <span className="inline-block px-2 py-0.5 rounded bg-blue-100 text-blue-700">[TMDB]</span>
                      <span className="ml-2">match .94</span>
                    </div>
                    <p className="text-sm text-slate-700 mb-3">A poor family schemes to become employed by a wealthy...</p>
                    <div className="mt-3">
                      <input
                        type="radio"
                        name="synopsis"
                        checked={selectedSynopsis === "tmdb"}
                        onChange={() => setSelectedSynopsis("tmdb")}
                        className="cursor-pointer"
                      />
                      <label className="ml-2 text-sm text-slate-700">사용</label>
                    </div>
                  </div>
                </div>
                <div className="mt-3 flex gap-2">
                  <button className="text-sm text-blue-600 hover:text-blue-700 font-medium">✏ 직접 작성</button>
                  <button className="text-sm text-blue-600 hover:text-blue-700 font-medium">↻ AI 재생성</button>
                </div>
              </div>

              {/* Genre Field */}
              <div>
                <h3 className="font-semibold text-slate-900 mb-3">장르</h3>
                <div className="flex gap-2 flex-wrap">
                  <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-blue-100 text-blue-700 text-sm">
                    드라마 <span className="text-xs">✓ TMDB·.91</span>
                  </span>
                  <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-blue-100 text-blue-700 text-sm">
                    스릴러 <span className="text-xs">✓ AI·.84</span>
                  </span>
                  <button className="px-3 py-1 rounded-full border border-dashed border-slate-300 text-slate-600 text-sm hover:bg-slate-50">+ 추가</button>
                </div>
              </div>

              {/* Save Button */}
              <div className="pt-4 border-t border-slate-200 flex gap-2 justify-end">
                <button className="px-4 py-2 rounded-lg border border-slate-200 text-slate-700 font-medium hover:bg-slate-50">
                  💾 임시 저장
                </button>
                <button className="px-4 py-2 rounded-lg bg-green-100 text-green-700 font-medium hover:bg-green-200">
                  💾 저장 후 글자 메타 완료
                </button>
              </div>
            </div>
          )}

          {activeTab === "image" && (
            <div className="space-y-4">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold text-slate-900">이미지</h3>
                <button className="px-3 py-2 rounded-lg bg-blue-100 text-blue-700 text-sm font-medium hover:bg-blue-200">
                  + 이미지 업로드
                </button>
              </div>
              <div className="grid grid-cols-5 gap-4">
                {[1, 2, 3, 4, 5].map((i) => (
                  <div key={i} className="border border-slate-200 rounded-lg overflow-hidden hover:border-blue-400 transition-colors">
                    <div className="aspect-[3/4] bg-gradient-to-br from-slate-200 to-slate-300 flex items-center justify-center">
                      <Film className="h-8 w-8 text-slate-400" />
                    </div>
                    <div className="p-2 text-xs text-slate-600">
                      {i === 1 ? "⭐ 대표" : `포스터 ${i}`}
                      <div className="text-xs text-slate-500 mt-1">{i === 1 ? "CP" : "TMDB"}</div>
                    </div>
                  </div>
                ))}
              </div>
              <div className="text-sm text-slate-600 mt-4">
                검수 진행: 5/5 완료
                <button className="ml-4 px-3 py-1 rounded-lg bg-green-100 text-green-700 text-sm font-medium hover:bg-green-200">
                  ✓ 이미지 메타 완료
                </button>
              </div>
            </div>
          )}

          {activeTab === "video" && (
            <div className="space-y-4">
              <div className="border border-slate-200 rounded-lg p-4 bg-slate-50">
                <h3 className="font-semibold text-slate-900 mb-4">영상 파일 정보</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs font-medium text-slate-600">해상도</label>
                    <select className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg">
                      <option>4K</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-xs font-medium text-slate-600">포맷</label>
                    <select className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg">
                      <option>MP4</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-xs font-medium text-slate-600">비디오 코덱</label>
                    <select className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg">
                      <option>H.265</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-xs font-medium text-slate-600">오디오 코덱</label>
                    <select className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg">
                      <option>AAC</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-xs font-medium text-slate-600">비트레이트</label>
                    <input type="number" value="12000" className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg" />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-slate-600">길이</label>
                    <input type="text" value="02:12:00" className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg" />
                  </div>
                </div>
              </div>

              <div className="border border-yellow-200 bg-yellow-50 rounded-lg p-3 flex gap-2 text-sm text-yellow-700">
                <AlertCircle className="h-4 w-4 flex-shrink-0 mt-0.5" />
                <span>자동 감지: ffprobe 미실행</span>
              </div>
            </div>
          )}

          {activeTab === "sources" && (
            <div className="space-y-4">
              <h3 className="font-semibold text-slate-900">매칭된 외부 소스 (3)</h3>

              {/* TMDB */}
              <div className="border border-slate-200 rounded-lg p-4">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <span className="inline-block px-2 py-1 rounded-full bg-blue-100 text-blue-700 font-medium text-sm">[TMDB]</span>
                    <span className="ml-2 text-xs text-slate-600">id: 496243 match .94</span>
                  </div>
                </div>
                <p className="text-sm text-slate-600 mb-3">title: Parasite</p>
                <button className="text-sm text-blue-600 hover:text-blue-700 font-medium">📋 필드별 가져오기</button>
              </div>

              {/* KOBIS */}
              <div className="border border-slate-200 rounded-lg p-4">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <span className="inline-block px-2 py-1 rounded-full bg-green-100 text-green-700 font-medium text-sm">[KOBIS]</span>
                    <span className="ml-2 text-xs text-slate-600">movieCd: 20183782 match .87</span>
                  </div>
                </div>
                <p className="text-sm text-slate-600 mb-3">영화명: 기생충, 감독: 봉준호</p>
                <button className="text-sm text-blue-600 hover:text-blue-700 font-medium">📋 필드별 가져오기</button>
              </div>

              {/* Low confidence */}
              <div className="border border-yellow-200 bg-yellow-50 rounded-lg p-4">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <span className="inline-block px-2 py-1 rounded-full bg-yellow-100 text-yellow-700 font-medium text-sm">[Watcha]</span>
                    <span className="ml-2 text-xs text-yellow-700">id: 12wgQ34 match .79 ⚠</span>
                  </div>
                </div>
                <p className="text-sm text-yellow-700">⚠ 낮은 신뢰도 — 등급/연도 불일치 가능. 검수 권장.</p>
                <button className="text-sm text-blue-600 hover:text-blue-700 font-medium mt-2">📋 필드별 가져오기</button>
              </div>
            </div>
          )}

          {activeTab === "ai" && (
            <div className="space-y-4">
              <h3 className="font-semibold text-slate-900 mb-4">AI 처리 이력 (8)</h3>

              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 border-b border-slate-200">
                    <tr>
                      <th className="px-3 py-2 text-left font-semibold text-slate-600">처리 시각</th>
                      <th className="px-3 py-2 text-left font-semibold text-slate-600">엔진</th>
                      <th className="px-3 py-2 text-left font-semibold text-slate-600">태스크</th>
                      <th className="px-3 py-2 text-left font-semibold text-slate-600">점수</th>
                      <th className="px-3 py-2 text-left font-semibold text-slate-600">액션</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200">
                    {[
                      { time: "2026-05-13 14:30", engine: "gemini", task: "synopsis", score: 89, current: true },
                      { time: "2026-05-13 14:30", engine: "groq", task: "synopsis", score: 82, current: false },
                      { time: "2026-05-13 14:30", engine: "gemini", task: "genre", score: 91, current: true },
                      { time: "2026-05-13 14:30", engine: "gemini", task: "tagging", score: 84, current: true },
                    ].map((row, i) => (
                      <tr key={i} className={row.current ? "bg-green-50" : "hover:bg-slate-50"}>
                        <td className="px-3 py-2 text-slate-700">{row.time}</td>
                        <td className="px-3 py-2 text-slate-700">{row.engine}</td>
                        <td className="px-3 py-2 text-slate-700">{row.task}</td>
                        <td className="px-3 py-2 font-medium text-slate-900">{row.score}</td>
                        <td className="px-3 py-2 text-right">
                          {row.current ? (
                            <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-green-100 text-green-700 text-xs font-medium">
                              ● 현재 채택
                            </span>
                          ) : (
                            <button className="text-blue-600 hover:text-blue-700 text-xs font-medium">채택</button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Footer Info */}
      <div className="mt-4 text-center text-xs text-slate-500">
        <p>프로토타입 — 이 화면은 데이터 없이 UI/UX 만 시뮬레이션합니다.</p>
      </div>
    </div>
  )
}
