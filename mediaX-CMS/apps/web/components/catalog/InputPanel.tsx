"use client"

import { useState, useEffect } from "react"
import { FolderPlus, Trash2, Search } from "lucide-react"
import { cn } from "@workspace/ui/lib/utils"
import type { CategoryNode } from "@/lib/api"
import { CATEGORY_PRESETS } from "@/lib/categoryBulkParse"
import { BulkImportPanel } from "@/components/catalog/BulkImportPanel"
import { getCustomTemplates, deleteCustomTemplate } from "@/lib/customTemplates"
import type { CustomTemplate } from "@/lib/customTemplates"

type Tab = "template" | "manual" | "bulk"

// ── 루트 추가 폼 (수동 탭) ────────────────────────────────────────────────────

function ManualAddForm({ onAddRoot }: { onAddRoot: (name: string) => Promise<void> }) {
  const [name, setName] = useState("")
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    setLoading(true)
    try {
      await onAddRoot(name.trim())
      setName("")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-3 p-3">
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          autoFocus
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="루트 카테고리 이름"
          disabled={loading}
          className="h-8 flex-1 rounded border border-border bg-background px-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
        />
        <button
          type="submit"
          disabled={loading || !name.trim()}
          className="rounded bg-primary px-2.5 py-1 text-xs text-primary-foreground disabled:opacity-50"
        >
          {loading ? "…" : "추가"}
        </button>
      </form>
      <div className="rounded-md bg-muted/50 p-3 text-xs text-muted-foreground leading-relaxed">
        <p className="font-medium mb-1">하위 카테고리 추가</p>
        <p>트리에서 카테고리 행에 마우스를 올리면 나타나는 <span className="font-mono bg-muted px-1 rounded">+</span> 버튼으로 자식 노드를 추가할 수 있습니다.</p>
      </div>
      <div className="flex flex-col items-center gap-2 py-4 text-muted-foreground">
        <FolderPlus className="h-8 w-8 opacity-20" />
        <p className="text-xs text-center">대량 추가는 &apos;일괄&apos; 탭을,<br />템플릿 적용은 &apos;템플릿&apos; 탭을 이용하세요.</p>
      </div>
    </div>
  )
}

// ── InputPanel ────────────────────────────────────────────────────────────────

export function InputPanel({
  existingTree,
  onCommit,
  onAddRoot,
}: {
  existingTree: CategoryNode[]
  onCommit: () => Promise<void>
  onAddRoot: (name: string) => Promise<void>
}) {
  const [tab, setTab] = useState<Tab>("template")
  const [bulkText, setBulkText] = useState("")
  const [manualSubTab, setManualSubTab] = useState<"single" | "text">("single")
  const [customTemplates, setCustomTemplates] = useState<CustomTemplate[]>(() =>
    getCustomTemplates(),
  )

  const [customTemplateSearch, setCustomTemplateSearch] = useState("")

  useEffect(() => {
    const refresh = () => setCustomTemplates(getCustomTemplates())
    window.addEventListener("storage", refresh)
    window.addEventListener("custom-templates-changed", refresh)
    return () => {
      window.removeEventListener("storage", refresh)
      window.removeEventListener("custom-templates-changed", refresh)
    }
  }, [])

  const tabs: { id: Tab; label: string }[] = [
    { id: "template", label: "템플릿" },
    { id: "manual", label: "건별" },
    { id: "bulk", label: "대량(CSV)" },
  ]

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-lg border bg-card">
      {/* 패널 헤더 */}
      <div className="shrink-0 border-b px-3 py-2.5">
        <p className="text-sm font-medium">카테고리 등록</p>
      </div>

      {/* 탭 헤더 */}
      <div className="flex shrink-0 border-b">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={cn(
              "flex-1 py-2 text-xs font-medium transition-colors",
              tab === t.id
                ? "border-b-2 border-primary text-primary"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* 탭 콘텐츠 */}
      <div className="min-h-0 flex-1 overflow-y-auto">
        {tab === "template" && (
          <div className="p-3 space-y-2">
            <p className="text-xs text-muted-foreground pb-1">프리셋을 선택하면 일괄 탭에 자동 주입됩니다.</p>

            {/* 기본 프리셋 */}
            {CATEGORY_PRESETS.map((preset) => (
              <button
                key={preset.id}
                onClick={() => {
                  setBulkText(preset.text)
                  setTab("manual")
                  setManualSubTab("text")
                }}
                className="w-full rounded-md border bg-background p-3 text-left hover:bg-muted transition-colors"
              >
                <p className="text-sm font-medium">{preset.label}</p>
                <p className="mt-0.5 text-xs text-muted-foreground">{preset.description}</p>
              </button>
            ))}

            {/* 커스텀 템플릿 */}
            {customTemplates.length > 0 && (
              <>
                <div className="pt-2 mt-2 border-t">
                  <p className="text-xs font-medium text-muted-foreground pb-2">내 템플릿 ({customTemplates.length})</p>
                  {customTemplates.length >= 3 && (
                    <div className="flex items-center gap-1.5 rounded-md border bg-background px-2 py-1 mb-2">
                      <Search className="h-3 w-3 shrink-0 text-muted-foreground" />
                      <input
                        value={customTemplateSearch}
                        onChange={(e) => setCustomTemplateSearch(e.target.value)}
                        placeholder="템플릿 검색..."
                        className="flex-1 bg-transparent text-xs outline-none placeholder:text-muted-foreground"
                      />
                    </div>
                  )}
                </div>
                {customTemplates
                  .filter((t) =>
                    customTemplateSearch
                      ? t.label.toLowerCase().includes(customTemplateSearch.toLowerCase())
                      : true,
                  )
                  .map((template) => (
                  <div
                    key={template.id}
                    className="flex items-start gap-2 rounded-md border bg-background p-3"
                  >
                    <button
                      onClick={() => {
                        setBulkText(template.text)
                        setTab("manual")
                        setManualSubTab("text")
                      }}
                      className="flex-1 text-left hover:opacity-80 transition-opacity"
                    >
                      <p className="text-sm font-medium">{template.label}</p>
                      <p className="mt-0.5 text-xs text-muted-foreground">{template.description}</p>
                    </button>
                    <button
                      onClick={() => {
                        deleteCustomTemplate(template.id)
                        setCustomTemplates(getCustomTemplates())
                      }}
                      title="템플릿 삭제"
                      className="shrink-0 rounded p-1.5 text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                ))}
              </>
            )}
          </div>
        )}

        {tab === "manual" && (
          <div className="flex h-full flex-col">
            {/* 서브토글 */}
            <div className="flex shrink-0 border-b">
              {(["single", "text"] as const).map((m) => (
                <button
                  key={m}
                  onClick={() => setManualSubTab(m)}
                  className={cn(
                    "flex-1 py-1.5 text-xs font-medium transition-colors",
                    manualSubTab === m
                      ? "border-b-2 border-primary text-primary"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  {m === "single" ? "단건 추가" : "텍스트 일괄"}
                </button>
              ))}
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto">
              {manualSubTab === "single" ? (
                <ManualAddForm onAddRoot={onAddRoot} />
              ) : (
                <BulkImportPanel
                  existingTree={existingTree}
                  initialText={bulkText}
                  lockedMode="text"
                  onCommit={onCommit}
                />
              )}
            </div>
          </div>
        )}

        {tab === "bulk" && (
          <BulkImportPanel
            existingTree={existingTree}
            lockedMode="file"
            onCommit={onCommit}
          />
        )}
      </div>
    </div>
  )
}
